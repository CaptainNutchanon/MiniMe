import re
import unicodedata

BRACKET_TAG_RE = re.compile(r"\[[^\]\r\n]{1,20}\]")
THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)
THINK_TAG_RE = re.compile(r"</?think\b[^>]*>", re.IGNORECASE)
NOISY_TEXT_RE = re.compile(r"(https?://|www\.|\.jpg|\.jpeg|\.png|\.gif|\.webp)", re.IGNORECASE)
FRIEND_STRETCH_RE = re.compile(r"เพื่อนนน+")
LOEI_STRETCH_RE = re.compile(r"เลยยย+")


def clean_content(content: str) -> str:
    return content.strip()


def is_usable_content(content: str) -> bool:
    return bool(content) and not NOISY_TEXT_RE.search(content)


def normalize_prompt(text: str) -> str:
    text = clean_content(text)
    text = re.sub(r"\s+", "", text.strip().lower())
    text = re.sub(r"[!?！？。、,.…]+$", "", text)
    text = re.sub(r"(ครับ|คับ|ค่ะ|คะ|จ้า|จ๊ะ|ฮะ|งับ)$", "", text)
    return text


def clean_generated_reply(text: str) -> str:
    text = clean_content(text)
    text = THINK_BLOCK_RE.sub("", text)
    text = THINK_TAG_RE.sub("", text)
    text = re.sub(r"\s*\[[^\]\r\n]{1,20}\]", "", text)
    text = re.sub(r"(\S{1,12})(?:\s+\1){3,}", r"\1", text)
    text = FRIEND_STRETCH_RE.sub("เพื่อนน", text)
    text = LOEI_STRETCH_RE.sub("เลยย", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def is_emoji_char(char: str) -> bool:
    if char == "\ufffd":
        return True
    if ord(char) > 0xFFFF:
        return True
    return unicodedata.category(char) == "So" and char not in {"ๆ"}


def emoji_count(text: str) -> int:
    return sum(1 for char in text if is_emoji_char(char))


def is_emoji_only(text: str) -> bool:
    compact = re.sub(r"[\s\ufe0f\u200d]+", "", text)
    return bool(compact) and all(is_emoji_char(char) for char in compact)
