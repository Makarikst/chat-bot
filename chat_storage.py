import json
import os
import uuid
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

LOG_DIR = "chat_logs"


def new_chat_id() -> str:
    return uuid.uuid4().hex


def ensure_log_dir() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_DIR


def chat_path(chat_id: str) -> str:
    return os.path.join(LOG_DIR, f"{chat_id}.json")


def messages_to_records(messages) -> list[dict]:
    records = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            continue  # raw tool JSON is not part of the visible conversation
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        records.append({"role": role, "content": msg.content})
    return records


def records_to_messages(records: list[dict]):
    out = []
    for r in records:
        if r["role"] == "user":
            out.append(HumanMessage(content=r["content"]))
        else:
            out.append(AIMessage(content=r["content"]))
    return out


def derive_title(messages) -> str:
    for msg in messages:
        if not isinstance(msg, HumanMessage):
            continue
        if isinstance(msg.content, str):
            return msg.content[:40].strip() or "New chat"
        if isinstance(msg.content, list):
            for item in msg.content:
                if item.get("type") == "text" and item.get("text"):
                    return item["text"][:40].strip() or "New chat"
    return "New chat"


def save_chat(chat_id: str, messages) -> dict:
    ensure_log_dir()
    payload = {
        "id": chat_id,
        "title": derive_title(messages),
        "updated": datetime.now().isoformat(),
        "messages": messages_to_records(messages),
    }
    with open(chat_path(chat_id), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def load_chat(chat_id: str) -> dict | None:
    path = chat_path(chat_id)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_chats() -> list[dict]:
    ensure_log_dir()
    chats = []
    for name in os.listdir(LOG_DIR):
        if not name.endswith(".json"):
            continue
        try:
            data = load_chat(name[:-5])
        except (json.JSONDecodeError, OSError):
            continue  # skip corrupt files
        if data:
            chats.append(data)
    chats.sort(key=lambda c: c.get("updated", ""), reverse=True)
    return chats