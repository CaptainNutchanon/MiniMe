import os
import re

from .text_cleaning import BRACKET_TAG_RE, clean_generated_reply, emoji_count, is_emoji_only, normalize_prompt

MAX_REPLY_CHARS = 70
IDENTITY_NAME = "กัปปิตัน"
BOT_IDENTITY_REPLY = "ก็ประมาณนั้นแหละ"
IDENTITY_POLICY_ENV = "MINIME_IDENTITY_POLICY"
DEFAULT_IDENTITY_POLICY = "normalize"

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
BAD_GENERATION_RE = re.compile(
    r"(吃什么去啊|客气吧|kappitan(?:_?ton)?|kappitton|captain|kongkai|ไอแพน|คุณายาว)",
    re.IGNORECASE,
)
APP_PACKAGE_RE = re.compile(r"(?:^|[#\s])[a-z]+(?:\.[a-z0-9_]+){2,}", re.IGNORECASE)
LONG_DIGIT_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")

NAME_IDENTITY_PROMPT_RE = re.compile(
    r"(ชื่ออะไร|ชื่อไร|ชื่อว่าอะไร|ชื่อ\s*กัปปิตัน.*(?:ใช่|ปะ|ไหม)|เธอชื่อ|นายชื่อ|แกชื่อ|คุณคือใคร|นายคือใคร|แกคือใคร|"
    r"เธอคือใคร|นี่ใคร|นี้ใคร|มินิมีคือใคร|ขอ(?:ทราบ)?ชื่อ|ให้เรียก(?:ว่า)?อะไร|เรียก.*ว่าอะไร|เรียก.*อะไรดี|เรียก.*ยังไงดี|เรียก.*ไงดี)"
)
BOT_IDENTITY_PROMPT_RE = re.compile(
    r"(เป็น\s*(?:บอท|ai|เอไอ|แชทบอท|โมเดล\s*(?:ai|เอไอ))|"
    r"(?:บอท|ai|เอไอ|แชทบอท|โมเดล\s*(?:ai|เอไอ))หรอ|"
    r"(?:บอท|ai|เอไอ|แชทบอท|โมเดล\s*(?:ai|เอไอ)).*(?:ไหม|ใช่ไหม|หรือเปล่า|หรือคน|อยู่ไหม)|"
    r"นายเป็น\s*(?:ai|เอไอ|บอท))",
    re.IGNORECASE,
)
IDENTITY_PROMPT_RE = re.compile(f"(?:{NAME_IDENTITY_PROMPT_RE.pattern}|{BOT_IDENTITY_PROMPT_RE.pattern})", re.IGNORECASE)
IDENTITY_VARIANT_RE = re.compile(r"(กัปปิ(?!ตัน)|กัปตัน)")
LATIN_IDENTITY_VARIANT_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:kappitan(?:_?ton)?|kappitton|captain|cap|kap)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
BROKEN_THAI_IDENTITY_RE = re.compile(r"^\s*กัป(?!ปิตัน)\S{0,16}")
IDENTITY_DUPLICATE_PREFIX_RE = re.compile(r"^\s*กัป\s*(?=กัปปิตัน)")
BOT_DENIAL_ONLY_RE = re.compile(r"^\s*(?:ไม่ใช่|ไม่อะ|ไม่อ่ะ|ไม่|ป่าว|เปล่า)(?:ดิ|นะ|อะ|อ่ะ|ๆ)?\s*$")
BOT_IDENTITY_ACCEPT_RE = re.compile(r"(ใช่|ใช่ๆ|ก็ประมาณ|ประมาณนั้น|บอท|ai|เอไอ)", re.IGNORECASE)

SPECIFIC_PLACE_REPLY_RE = re.compile(
    r"((?:เข้า|อยู่|ไป|มาถึง|ถึง)ห้อง|ห้อง(?:ละ|แล้ว|มอ|กู|กุ|มึง|เรา)|"
    r"(?:อยู่|ไป|กลับ)หอ|อยู่มอ|กลับบ้าน|อยู่บ้าน|ถึงบ้าน)"
)
PRIVATE_CONTEXT_REPLY_RE = re.compile(
    r"(อยู่กับ\S{1,20}|(?:กู|กุ|เค้า|เรา)?อยู่(?:ข้างนอก|หอ|มอ|ห้อง|บ้าน)|"
    r"ห้องมอ|ห้อง(?:มึง|เธอ|เค้า|กู|กุ)|ถึง(?:ละ|แล้ว)|กำลัง(?:ไป|กลับ)|"
    r"(?:เพิ่ง|พึ่ง)ตื่น|มาหา|ไปหา|กลับบ้าน)"
)
NUMBER_CONTEXT_RE = re.compile(
    r"((?:เซค|ห้อง|ตาราง)\s*\d{3}|\d{3}\s*(?:ออก|เต็ม|เซค|ห้อง|ตาราง))"
)
PERSONAL_NUMBER_RE = re.compile(r"(?<!\d)0\d(?:[\s-]?\d){7,9}(?!\d)")


def context_messages_text(context_messages: list[dict]) -> str:
    return " ".join(
        message.get("content", "")
        for message in context_messages
        if message.get("role") in {"user", "assistant"}
    )


def training_skip_reason(completion: str, context_messages: list[dict]) -> str | None:
    """Return why an assistant turn should be skipped before fine-tuning.

    The training filter is intentionally minimal. It only drops examples that
    expose personal phone-like numbers without grounding in the visible context.
    """
    if not context_messages or context_messages[-1].get("role") != "user":
        return "no_user_context"

    grounding_text = context_messages_text(context_messages)
    completion = clean_generated_reply(completion)
    personal_number_match = PERSONAL_NUMBER_RE.search(completion)
    if personal_number_match and personal_number_match.group(0) not in grounding_text:
        return "personal_number"

    return None


def is_identity_prompt(user_text: str) -> bool:
    return bool(IDENTITY_PROMPT_RE.search(user_text))


def is_name_identity_prompt(user_text: str) -> bool:
    return bool(NAME_IDENTITY_PROMPT_RE.search(user_text))


def is_bot_identity_prompt(user_text: str) -> bool:
    return bool(BOT_IDENTITY_PROMPT_RE.search(user_text))


def needs_identity_retry(user_text: str, reply: str | None) -> bool:
    if not is_identity_prompt(user_text):
        return False
    if not reply:
        return True

    cleaned = clean_generated_reply(reply)
    normalized = normalize_prompt(cleaned)

    if is_name_identity_prompt(user_text):
        if IDENTITY_NAME not in cleaned:
            return True
        if len(normalized) > 16 or re.search(r"\d", cleaned):
            return True
        return bool(
            PRIVATE_CONTEXT_REPLY_RE.search(cleaned)
            or NUMBER_CONTEXT_RE.search(cleaned)
            or PERSONAL_NUMBER_RE.search(cleaned)
            or SPECIFIC_PLACE_REPLY_RE.search(cleaned)
        )

    if is_bot_identity_prompt(user_text):
        if BOT_DENIAL_ONLY_RE.fullmatch(cleaned):
            return True
        if not BOT_IDENTITY_ACCEPT_RE.search(cleaned):
            return True
        return len(normalized) > 18 or bool(PRIVATE_CONTEXT_REPLY_RE.search(cleaned))

    return False


def identity_policy() -> str:
    policy = os.environ.get(IDENTITY_POLICY_ENV, DEFAULT_IDENTITY_POLICY).strip().lower()
    if policy not in {"normalize", "force", "off"}:
        return DEFAULT_IDENTITY_POLICY
    return policy


def normalize_identity_reply(user_text: str, reply: str) -> str:
    if not is_identity_prompt(user_text):
        return reply

    policy = identity_policy()
    if policy == "off":
        return reply
    if is_bot_identity_prompt(user_text):
        if policy == "force":
            return BOT_IDENTITY_REPLY
        reply = LATIN_IDENTITY_VARIANT_RE.sub(IDENTITY_NAME, IDENTITY_VARIANT_RE.sub(IDENTITY_NAME, reply))
        return IDENTITY_DUPLICATE_PREFIX_RE.sub("", reply)
    if policy == "force":
        return IDENTITY_NAME

    reply = LATIN_IDENTITY_VARIANT_RE.sub(IDENTITY_NAME, IDENTITY_VARIANT_RE.sub(IDENTITY_NAME, reply))
    reply = IDENTITY_DUPLICATE_PREFIX_RE.sub("", reply)
    if is_name_identity_prompt(user_text):
        return IDENTITY_NAME
    if IDENTITY_NAME in reply:
        return reply
    if BROKEN_THAI_IDENTITY_RE.search(reply):
        return IDENTITY_NAME
    return reply


def finalize_identity_reply(user_text: str, reply: str | None) -> str | None:
    """Return a deterministic identity answer only when an identity retry still failed."""
    if identity_policy() == "off" or not is_identity_prompt(user_text):
        return reply
    if is_name_identity_prompt(user_text) and needs_identity_retry(user_text, reply):
        return IDENTITY_NAME
    if is_bot_identity_prompt(user_text) and needs_identity_retry(user_text, reply):
        return BOT_IDENTITY_REPLY
    return reply


def garbage_reply_reason(reply: str) -> str | None:
    reply = clean_generated_reply(reply)
    if not reply:
        return "empty"
    if "\ufffd" in reply:
        return "replacement_char"
    if CJK_RE.search(reply):
        return "cjk"
    if BAD_GENERATION_RE.search(reply):
        return "bad_generation"
    if APP_PACKAGE_RE.search(reply):
        return "app_package"
    if LONG_DIGIT_RE.search(reply):
        return "long_number"
    if PERSONAL_NUMBER_RE.search(reply):
        return "personal_number"
    if is_emoji_only(reply) or emoji_count(reply) >= 3:
        return "emoji_spam"
    return None


def validate_reply(user_text: str, context_text: str, reply: str) -> str | None:
    reply = clean_generated_reply(reply)
    if not reply:
        return None

    reply = normalize_identity_reply(user_text, reply)

    if garbage_reply_reason(reply):
        return None
    if BRACKET_TAG_RE.search(reply):
        return None
    if len(reply) > MAX_REPLY_CHARS:
        return None
    return reply
