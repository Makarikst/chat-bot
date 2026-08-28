# Plan: Chat Logs & Session Management

## The idea

Right now the bot's memory lives in `st.session_state` — that is **volatile storage**: it sits in RAM and
dies on a page refresh or a reboot. **Persistent storage** is data written to the hard drive; it outlives the
process, the browser, and the computer itself. This lesson moves the conversation from RAM to disk.

Four concepts do the work:

- **JSON serialization** — turning in-memory Python objects into text. LangChain message objects
  (`HumanMessage`, `AIMessage`) are not JSON-serializable, so we convert them to plain
  `{"role": ..., "content": ...}` dicts first.
- **File I/O** — `os.makedirs(..., exist_ok=True)` auto-creates the `chat_logs/` folder, and `open()` plus
  `json.dump` / `json.load` write and read one file per chat.
- **UUIDs** — `uuid.uuid4()` generates 122 random bits. The chance of two chats drawing the same ID is
  negligible, so the ID can safely be a filename: `chat_logs/<uuid>.json`. No central database, no collisions.

Architecture:

```text
main.py (sidebar UI + save trigger)
   ↕
chat_storage.py (pure Python: save / load / list — no Streamlit import)
   ↕
chat_logs/<uuid>.json  (one file per conversation, on the hard drive)
```

---

## 1. Create the `chat_storage.py` module

Create a new file `chat_storage.py` in the project root:

```python
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
```

**Why this design:**

### Conversion layer (`messages_to_records` / `records_to_messages`)

- `json.dump` cannot serialize a `HumanMessage` object, but it can serialize a dict. The two functions are
  exact inverses: objects → records on the way out, records → objects on the way back.
- `ToolMessage` is dropped on save — the archive stores the *visible* conversation, not the raw tool JSON.
- `msg.content` may be a plain string **or** a list of `{"type": "text" | "image_url", ...}` items (lessons 5–6).
  Both shapes are plain JSON, so they round-trip untouched — including the base64 image data.

### `save_chat()` — one file per chat

- Payload carries `id`, a human-readable `title` (first user message, 40 chars), an ISO `updated` timestamp,
  and the message records.
- `ensure_ascii=False` keeps Cyrillic text readable inside the file instead of `\u043f\u0440...` escapes.
- `indent=2` makes the file pleasant to open in a text editor.
- The whole file is rewritten on every save — simple and safe at lesson scale.

### `list_chats()` — the archive index

- Scans the folder, skips anything that is not a `.json` file, and tolerates corrupt files (a half-written
  file must not crash the sidebar).
- ISO timestamps with microsecond precision sort correctly as plain strings, so `sorted(..., reverse=True)`
  gives a deterministic newest-first order (two chats saved in the same second still order correctly).

---

## 2. Import the module (main.py, top of file)

**Find** the import block:

```python
from langchain_tavily import TavilySearch
from multimedia import transcribe_audio, extract_video_frames
```

**Add** after it:

```python
from chat_storage import new_chat_id, save_chat, load_chat, list_chats, records_to_messages
```

---

## 3. Add the sidebar session tray (main.py, after the personality block)

**Find** the line that closes the Lesson 7 block:

```python
    active_persona = PERSONALITIES[st.session_state.personality]

    def encode_image_to_data_uri(file_obj, ext: str) -> str:
```

**Replace** with:

```python
    active_persona = PERSONALITIES[st.session_state.personality]

    # --- CHAT LOGS & SESSIONS (Lesson 8) ---
    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = new_chat_id()

    st.sidebar.divider()
    st.sidebar.subheader("💬 Chats")

    if st.sidebar.button("➕ New Chat", width="stretch"):
        st.session_state.messages = []
        st.session_state.active_chat_id = new_chat_id()
        st.rerun()

    for chat in list_chats():
        label = chat["title"] or "New chat"
        if chat["id"] == st.session_state.active_chat_id:
            label += "  ✓"
        if st.sidebar.button(label, key=f"open_{chat['id']}", width="stretch"):
            if chat["id"] != st.session_state.active_chat_id:
                st.session_state.messages = records_to_messages(chat["messages"])
                st.session_state.active_chat_id = chat["id"]
                st.rerun()

    def encode_image_to_data_uri(file_obj, ext: str) -> str:
```

**What changed (3 additions):**

### A. `active_chat_id` — the current tab

- Every session gets a UUID the moment the app starts. This is the key the save function writes to.

### B. "➕ New Chat" button

- Wipes `st.session_state.messages` and mints a fresh UUID, so the next exchange is saved as a brand-new file.
- `st.rerun()` repaints the page with a clean slate immediately.

### C. Historical archive list

- One button per saved chat, newest first, labeled by its derived title.
- Clicking a chat loads its JSON back into `st.session_state.messages` and switches `active_chat_id`.
- The active chat is marked with a `✓`; clicking it again is a no-op.
- `key=f"open_{chat['id']}"` gives every button a stable identity (labels can repeat, keys cannot).
- `width="stretch"` is the modern full-width API (Streamlit ≥ 1.49; the project pins ≥ 1.60).

---

## 4. Save after each exchange (main.py, end of the `# --- 6. USER INPUT LOOP ---` block)

**Find** the state-clearing lines at the very end of the `if user_input:` block:

```python
        st.session_state.uploaded_image = None
        st.session_state.uploaded_audio_transcript = None
        st.session_state.uploaded_video_frames = []
```

**Replace** with:

```python
        st.session_state.uploaded_image = None
        st.session_state.uploaded_audio_transcript = None
        st.session_state.uploaded_video_frames = []

        # --- 7. PERSIST THE CONVERSATION (Lesson 8) ---
        save_chat(st.session_state.active_chat_id, st.session_state.messages)
        st.rerun()
```

**What changed:**

- After the user message and the assistant reply are both in `st.session_state.messages`, the whole conversation
  is flushed to `chat_logs/<active_chat_id>.json`.
- `st.rerun()` repaints the page so the sidebar archive picks up the new/updated chat **in this same turn** —
  without it, the list (rendered top-to-bottom before this point) would only update on the next interaction.
  The repaint is cheap: history re-renders from `st.session_state`, and no LLM call is made.
- The `except` branch still appends an `AIMessage` (the error text), so even a failed turn is archived.
- This app uses `invoke()`, not token streaming — "save whenever a message streams in" therefore means "save
  after each user + assistant turn".

---

## 5. Update .gitignore

**Find**:

```text
.opencode/
```

**Add** a new line:

```text
chat_logs/
```

**Why:** conversation history is user data, not source code — it should never be committed.

---

## 6. Update pyproject.toml

No changes needed — `os`, `json`, `uuid`, and `datetime` are stdlib, and `langchain_core` is already a
dependency.

---

## Experiment checklist

Restart the app (`streamlit run main.py`) and walk through:

| Step                                    | What to look for                                                        |
|-----------------------------------------|-------------------------------------------------------------------------|
| Send 2–3 messages                       | `chat_logs/<uuid>.json` appears; open it — readable Cyrillic, indented JSON |
| Restart `streamlit run main.py`         | the screen is empty, but the file and the sidebar entry survive          |
| Click an old chat in the sidebar        | the full history re-renders, including any uploaded images              |
| Click "➕ New Chat"                      | clean slate; the next message creates a *second* file                    |
| Compare file sizes                      | text-only chat ≈ KB; chat with a photo ≈ MB (the base64 cost)            |
| Corrupt a file by hand                  | delete one character from a JSON file, reload — the sidebar skips it, the app does not crash |

**Observations to make:**

- **Volatile vs. persistent, side by side.** Refresh the page (F5): the screen history is gone, the sidebar
  archive is not. That contrast *is* the lesson.
- **The JSON is the single source of truth.** Edit the file by hand (change a word in a message) and reload the
  chat — the change appears. The app reads the file, it does not remember.
- **Base64 is heavy.** A 2 MB photo becomes ~2.7 MB of JSON text. Fidelity is perfect, size is not.
- **Titles are derived, not stored by hand** — the first user message wins, truncated to 40 characters.

---

## Key design decisions

- **Pure-Python storage module:** `chat_storage.py` imports no Streamlit, so it can be exercised from a plain
  REPL (`python -c "import chat_storage; ..."`). Mirrors the `multimedia.py` precedent from Lesson 6.
- **One file per chat, UUID-keyed:** no central database to corrupt — a bad write can only lose one conversation.
- **Whole-file rewrite per exchange:** simple and safe at lesson scale. No append bookkeeping, no indexes.
- **Base64 saved as-is:** reloaded chats fully restore images and video frames. The trade-off is multi-MB files.
- **Visible turns only:** `ToolMessage` and tool-call internals are dropped on save — the archive is exactly what
  the user sees.
- **Title from content, recency by timestamp:** the archive is self-describing; newest-first sorting is a plain
  string comparison on ISO timestamps.
- **Corrupt-file tolerance:** `list_chats()` skips unreadable files instead of crashing the sidebar.
- **No new dependencies:** everything is stdlib + already-installed `langchain_core`.
