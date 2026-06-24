import asyncio
import json
import os
import secrets
import threading
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from minime_core.runtime_env import configure_utf8
from minime_core.text_cleaning import clean_generated_reply
from minime_core.topic_guard import (
    finalize_identity_reply,
    garbage_reply_reason,
    identity_policy,
    is_bot_identity_prompt,
    is_name_identity_prompt,
    needs_identity_retry,
    validate_reply,
)

configure_utf8()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_ADAPTER_PATH = ROOT / "output" / "captain-lora"
ADAPTER_ENV_VAR = "MINIME_ADAPTER_PATH"
ADAPTER_PATH = Path(os.environ.get(ADAPTER_ENV_VAR, str(DEFAULT_ADAPTER_PATH)))
if not ADAPTER_PATH.is_absolute():
    ADAPTER_PATH = ROOT / ADAPTER_PATH
ADAPTER_PATH = ADAPTER_PATH.resolve()
ACCESS_KEY_ENV_VAR = "MINIME_ACCESS_KEY"
ACCESS_COOKIE_NAME = "minime_access"
ACCESS_KEY = os.environ.get(ACCESS_KEY_ENV_VAR, "").strip()
ACCESS_COOKIE_MAX_AGE = 60 * 60 * 24 * 7
MAX_SEQ_LEN = 2048
MAX_HISTORY_MESSAGES = 6
RUNTIME_SYSTEM_PROMPT = (
    "ตอบสั้นแบบแชทไทยในสไตล์กัปปิตัน ตอบจากบทสนทนาล่าสุดเท่านั้น "
    "ถ้าขาดข้อมูลสำคัญให้ถามกลับสั้น ๆ ได้ แต่อย่าถามวนคำเดิม "
    "ห้ามเดาชื่อคน สถานที่ กิจกรรม ความสัมพันธ์ หรือสถานะของตัวเองที่ user ไม่ได้พูด"
)
GARBAGE_RETRY_SYSTEM_HINT = (
    "ตอบเป็นภาษาไทยเท่านั้น ห้ามใช้ภาษาอังกฤษหรือจีน "
    "ห้ามตอบคำประหลาด เช่น ไอแพน หรือ คูณายาว ถ้าไม่แน่ใจให้ตอบสั้น ๆ แบบแชทไทย"
)
NAME_IDENTITY_RETRY_SYSTEM_HINT = (
    "ถ้าผู้ใช้ถามชื่อหรือตัวตน ให้ตอบสั้น ๆ ว่า กัปปิตัน หรือ กัปปิตันก็ได้"
)
BOT_IDENTITY_RETRY_SYSTEM_HINT = (
    "ถ้าผู้ใช้ถามว่าเป็น AI หรือบอท ให้ตอบสั้น ๆ เช่น ใช่ๆ หรือ ก็ประมาณนั้น "
    "ห้ามลากเรื่องเรียน งาน เกม หรือสถานที่อื่น"
)
SYSTEM_AWARE_CHAT_TEMPLATE = """{%- for message in messages %}
    {%- if message['role'] == 'system' %}
{{- '<|im_start|>system\n' + message['content'] + '<|im_end|>\n' }}
    {%- elif message['role'] == 'user' %}
{{- '<|im_start|>user\n' + message['content'] + '<|im_end|>\n' }}
    {%- elif message['role'] == 'assistant' %}
{{- '<|im_start|>assistant\n' + message['content'] + '<|im_end|>\n' }}
    {%- endif %}
{%- endfor %}
{%- if add_generation_prompt %}
{{- '<|im_start|>assistant\n' }}
{%- endif %}"""
app = FastAPI(title="MiniMe Chat")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

model = None
tokenizer = None
chat_tokenizer = None
torch = None
model_status = "loading"
model_error = None
model_lock = threading.Lock()
generation_lock = threading.Lock()


def access_is_enabled() -> bool:
    return bool(ACCESS_KEY)


def access_key_matches(value: str | None) -> bool:
    return bool(value) and secrets.compare_digest(value, ACCESS_KEY)


def request_has_access(request: Request) -> bool:
    if not access_is_enabled():
        return True
    return access_key_matches(request.cookies.get(ACCESS_COOKIE_NAME))


def access_form_response(*, invalid_key: bool = False) -> HTMLResponse:
    error = "<p class=\"error\">Access key ไม่ถูกต้อง ลองใหม่อีกครั้ง</p>" if invalid_key else ""
    return HTMLResponse(
        f"""<!doctype html>
<html lang="th">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MiniMe Access</title>
    <style>
      * {{ box-sizing: border-box; }}
      body {{
        min-height: 100dvh;
        margin: 0;
        display: grid;
        place-items: center;
        background: linear-gradient(135deg, #123232, #0f2928);
        color: #fff7ec;
        font-family: "Segoe UI", "Noto Sans Thai", system-ui, sans-serif;
      }}
      form {{
        width: min(92vw, 380px);
        padding: 24px;
        border: 1px solid rgba(215, 232, 228, 0.2);
        border-radius: 8px;
        background: rgba(255, 247, 236, 0.08);
      }}
      h1 {{ margin: 0 0 8px; font-size: 24px; }}
      p {{ margin: 0 0 18px; color: rgba(255, 247, 236, 0.72); }}
      .error {{ color: #ffb08a; }}
      input, button {{
        width: 100%;
        min-height: 44px;
        border-radius: 8px;
        font: inherit;
      }}
      input {{
        margin-bottom: 12px;
        border: 1px solid rgba(215, 232, 228, 0.28);
        padding: 0 12px;
        background: rgba(255, 247, 236, 0.1);
        color: #fff7ec;
        outline: none;
      }}
      input:focus {{ border-color: #f7b733; }}
      button {{
        border: 0;
        background: #f46a21;
        color: #fff7ec;
        cursor: pointer;
        font-weight: 800;
      }}
    </style>
  </head>
  <body>
    <form method="get" action="/">
      <h1>MiniMe</h1>
      <p>ใส่ access key เพื่อเข้าทดสอบแชทบอท</p>
      {error}
      <input name="key" type="password" autocomplete="current-password" autofocus required />
      <button type="submit">เข้าใช้งาน</button>
    </form>
  </body>
</html>""",
        status_code=401,
    )


@app.middleware("http")
async def require_access_key(request: Request, call_next):
    if not access_is_enabled():
        return await call_next(request)

    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        return await call_next(request)
    if not request_has_access(request):
        return access_form_response()
    return await call_next(request)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    flagged: bool = False


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    max_new_tokens: int = Field(default=24, ge=1, le=24)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    debug: bool = False


def sse_event(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def latest_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "").strip()
    return ""


def context_text_before_latest_user(messages: list[dict]) -> str:
    latest_index = None
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            latest_index = index
            break
    if latest_index is None:
        return ""
    return " ".join(
        message.get("content", "")
        for message in messages[max(0, latest_index - MAX_HISTORY_MESSAGES) : latest_index]
        if message.get("role") in {"user", "assistant"}
    )


def recent_chat_messages(messages: list[dict]) -> list[dict]:
    chat_messages = [
        message
        for message in messages
        if (
            message.get("role") in {"user", "assistant"}
            and message.get("content", "").strip()
            and not message.get("flagged")
        )
    ]
    return chat_messages[-MAX_HISTORY_MESSAGES:]


def messages_for_generation(
    messages: list[dict],
    *,
    extra_system_hint: str | None = None,
) -> list[dict]:
    clean_recent = recent_chat_messages(messages)
    system_prompt = RUNTIME_SYSTEM_PROMPT
    if extra_system_hint:
        system_prompt = f"{system_prompt} {extra_system_hint}"
    return [
        {"role": "system", "content": system_prompt},
        *clean_recent,
    ]


def stop_token_ids() -> list[int]:
    ids = []
    for token_id in (chat_tokenizer.eos_token_id, chat_tokenizer.convert_tokens_to_ids("<|im_end|>")):
        if isinstance(token_id, int) and token_id >= 0 and token_id not in ids:
            ids.append(token_id)
    return ids


def generate_raw_reply(
    messages: list[dict],
    payload: ChatRequest,
    *,
    retry: bool = False,
    max_new_tokens_override: int | None = None,
) -> str:
    encoded = chat_tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    encoded = {key: value.to("cuda") for key, value in encoded.items()}

    generation_kwargs = {
        **encoded,
        "max_new_tokens": max_new_tokens_override or min(payload.max_new_tokens, 24),
        "do_sample": retry or payload.temperature > 0,
        "pad_token_id": chat_tokenizer.eos_token_id,
        "eos_token_id": stop_token_ids(),
        "repetition_penalty": 1.3,
        "no_repeat_ngram_size": 3,
    }
    if retry:
        generation_kwargs["temperature"] = 0.7
        generation_kwargs["top_p"] = 0.9
    elif payload.temperature > 0:
        generation_kwargs["temperature"] = payload.temperature
        generation_kwargs["top_p"] = payload.top_p

    with torch.inference_mode():
        outputs = model.generate(**generation_kwargs)

    prompt_length = encoded["input_ids"].shape[-1]
    return chat_tokenizer.decode(outputs[0][prompt_length:], skip_special_tokens=True)


def load_model_once() -> None:
    global chat_tokenizer, model, model_error, model_status, tokenizer, torch

    with model_lock:
        if model_status == "ready":
            return
        if not ADAPTER_PATH.exists():
            model_status = "error"
            model_error = f"Adapter path not found: {ADAPTER_PATH}"
            return

        try:
            model_status = "loading"

            import unsloth  # noqa: F401
            import torch as torch_module
            from unsloth import FastLanguageModel

            loaded_model, loaded_tokenizer = FastLanguageModel.from_pretrained(
                model_name=str(ADAPTER_PATH),
                max_seq_length=MAX_SEQ_LEN,
                load_in_4bit=True,
                dtype=None,
            )
            FastLanguageModel.for_inference(loaded_model)

            torch = torch_module
            model = loaded_model
            tokenizer = loaded_tokenizer
            chat_tokenizer = getattr(loaded_tokenizer, "tokenizer", loaded_tokenizer)
            chat_tokenizer.chat_template = SYSTEM_AWARE_CHAT_TEMPLATE
            model_error = None
            model_status = "ready"
        except Exception as exc:  # surfaced through /health
            model = None
            tokenizer = None
            chat_tokenizer = None
            model_error = repr(exc)
            model_status = "error"


@app.on_event("startup")
def startup() -> None:
    thread = threading.Thread(target=load_model_once, daemon=True)
    thread.start()


@app.get("/")
def index(request: Request, key: str | None = None):
    if access_is_enabled():
        if key:
            if access_key_matches(key):
                response = RedirectResponse("/", status_code=303)
                response.set_cookie(
                    ACCESS_COOKIE_NAME,
                    key,
                    max_age=ACCESS_COOKIE_MAX_AGE,
                    httponly=True,
                    samesite="lax",
                )
                return response
            return access_form_response(invalid_key=True)
        if not request_has_access(request):
            return access_form_response()
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {
        "model_loaded": model_status == "ready",
        "status": model_status,
        "error": model_error,
        "adapter_path": str(ADAPTER_PATH),
        "adapter_env_var": ADAPTER_ENV_VAR,
        "adapter_overridden": ADAPTER_ENV_VAR in os.environ,
        "adapter_exists": ADAPTER_PATH.exists(),
        "runtime_mode": "lora_only",
        "identity_policy": identity_policy(),
        "guard_mode": "light",
        "access_key_enabled": access_is_enabled(),
        "access_key_env_var": ACCESS_KEY_ENV_VAR,
    }


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    if model_status == "error":
        raise HTTPException(status_code=500, detail=model_error)

    async def generate():
        if model_status != "ready":
            yield sse_event("status", {"message": "Model is still loading"})
            while model_status == "loading":
                await asyncio.sleep(0.5)
            if model_status != "ready":
                yield sse_event("error", {"message": model_error or "Model failed to load"})
                return

        raw_messages = [message.model_dump() for message in payload.messages]
        if not generation_lock.acquire(blocking=False):
            yield sse_event("error", {"message": "Model is busy. Please wait for the current reply."})
            return

        try:
            user_text = latest_user_text(raw_messages)
            context_text = context_text_before_latest_user(raw_messages)
            messages = messages_for_generation(raw_messages)

            try:
                raw_reply = generate_raw_reply(messages, payload)
                first_raw_reply = raw_reply
                retry_reason = garbage_reply_reason(raw_reply)
                initial_retry_reason = retry_reason
                retry_count = 0
                identity_retry_reason = None
                while retry_reason and retry_count < 2:
                    retry_count += 1
                    retry_messages = messages_for_generation(
                        raw_messages,
                        extra_system_hint=GARBAGE_RETRY_SYSTEM_HINT,
                    )
                    raw_reply = generate_raw_reply(retry_messages, payload, retry=True)
                    retry_reason = garbage_reply_reason(raw_reply)
            except Exception as exc:
                yield sse_event("error", {"message": repr(exc)})
                return

            clean_raw_reply = clean_generated_reply(raw_reply)
            reply = validate_reply(user_text, context_text, raw_reply)
            if needs_identity_retry(user_text, reply):
                identity_hint = None
                if is_name_identity_prompt(user_text):
                    identity_hint = NAME_IDENTITY_RETRY_SYSTEM_HINT
                    identity_retry_reason = "name_identity"
                elif is_bot_identity_prompt(user_text):
                    identity_hint = BOT_IDENTITY_RETRY_SYSTEM_HINT
                    identity_retry_reason = "bot_identity"

                if identity_hint:
                    try:
                        retry_messages = messages_for_generation(
                            raw_messages,
                            extra_system_hint=identity_hint,
                        )
                        raw_reply = generate_raw_reply(
                            retry_messages,
                            payload,
                            retry=False,
                            max_new_tokens_override=8,
                        )
                        retry_count += 1
                        retry_reason = garbage_reply_reason(raw_reply)
                        clean_raw_reply = clean_generated_reply(raw_reply)
                        reply = validate_reply(user_text, context_text, raw_reply)
                    except Exception as exc:
                        yield sse_event("error", {"message": repr(exc)})
                        return
            reply = finalize_identity_reply(user_text, reply)

            sanitized = bool(reply and reply != clean_raw_reply)
            guard_reason = "sanitized" if sanitized else None
            flagged = False
            debug_fields = {}
            if payload.debug:
                debug_fields = {
                    "raw_reply": raw_reply,
                    "cleaned_reply": clean_raw_reply,
                    "final_reply": reply or "",
                    "first_raw_reply": first_raw_reply,
                    "retry_count": retry_count,
                    "retry_reason": initial_retry_reason,
                    "identity_retry_reason": identity_retry_reason,
                    "last_garbage_reason": retry_reason,
                }
            if reply is None:
                flagged = True
                guard_reason = "guard_rejected"
                yield sse_event("error", {"message": "Guard rejected model reply"})
                yield sse_event(
                    "done",
                    {
                        "ok": False,
                        "flagged": True,
                        "sanitized": False,
                        "guard_reason": guard_reason,
                        **debug_fields,
                    },
                )
                return

            yield sse_event("token", {"text": reply})
            yield sse_event(
                "done",
                {
                    "ok": True,
                    "flagged": flagged,
                    "sanitized": sanitized,
                    "guard_reason": guard_reason,
                    **debug_fields,
                },
            )
        finally:
            generation_lock.release()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
