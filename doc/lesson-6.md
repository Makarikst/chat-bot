# Plan: Audio & Video Processing — The Multimedia Superpower

## The idea

A video is just a collection of pictures (frames) played fast. We use OpenCV to extract a few frames and pass them to
our Vision AI. Audio is turned into text using a lightweight, super-fast speech-to-text library called `faster-whisper`.
Both run on CPU without crashing a local Mac.

---

## 1. Add dependencies (pyproject.toml)

**Find** the `[project]` dependencies block:

```toml
dependencies = [
    "langchain-community>=0.4.2",
    "langchain-core>=1.5.1",
    "langchain-openai>=1.4.1",
    "langchain-tavily>=0.2.18",
    "python-dotenv>=1.2.2",
    "streamlit>=1.60.0",
]
```

**Replace** with:

```toml
dependencies = [
    "faster-whisper>=1.1.0",
    "langchain-community>=0.4.2",
    "langchain-core>=1.5.1",
    "langchain-openai>=1.4.1",
    "langchain-tavily>=0.2.18",
    "opencv-python-headless>=4.10.0",
    "python-dotenv>=1.2.2",
    "streamlit>=1.60.0",
]
```

**What changed:**

- `faster-whisper` — CPU-friendly speech-to-text (uses `int8` quantization, the `base` model is only ~5 MB)
- `opencv-python-headless` — video frame extraction without a GUI dependency

Run `uv sync` after editing.

---

## 2. Create the `multimedia.py` module

Create a new file `multimedia.py` in the project root:

```python
import base64
import tempfile

import cv2
import numpy as np
import streamlit as st
from faster_whisper import WhisperModel


@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")


def transcribe_audio(file_obj, sample_rate: int = 16000) -> str:
    ext = file_obj.name.rsplit(".", 1)[-1].lower()
    suffix = f".{ext}" if ext else ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file_obj.seek(0)
        tmp.write(file_obj.read())
        tmp_path = tmp.name

    try:
        model = load_whisper()
        segments, info = model.transcribe(tmp_path, language=None, beam_size=5)
        transcript = "".join(segment.text for segment in segments)
        return transcript.strip() if transcript else "(no speech detected)"
    finally:
        import os
        os.unlink(tmp_path)


def extract_video_frames(file_obj, max_frames: int = 8) -> list[str]:
    ext = file_obj.name.rsplit(".", 1)[-1].lower()
    suffix = f".{ext}" if ext else ".mp4"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file_obj.seek(0)
        tmp.write(file_obj.read())
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0

        if duration <= 0 or total_frames <= 0:
            return []

        frame_indices = np.linspace(0, total_frames - 1, max_frames, dtype=int)
        data_uris = []

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            _, buffer = cv2.imencode(".jpg", frame)
            b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
            data_uris.append(f"data:image/jpeg;base64,{b64}")

        cap.release()
        return data_uris
    finally:
        import os
        os.unlink(tmp_path)
```

**Why this design:**

### `load_whisper()` — cached model

- `@st.cache_resource` ensures the Whisper model loads once and stays in memory across requests
- `device="cpu"` + `compute_type="int8"` keeps it lightweight (~5 MB RAM, no GPU needed)

### `transcribe_audio()` — speech-to-text

- Writes the uploaded file to a temp file (faster-whisper needs a file path, not a stream)
- Auto-detects language, returns plain text transcript
- Cleans up the temp file in `finally`

### `extract_video_frames()` — video-to-images

- Opens the video with `cv2.VideoCapture`
- Calculates total frames and FPS, then uses `np.linspace` to pick 8 evenly-spaced timestamps
- Each frame is converted BGR→RGB, encoded as JPEG, then base64-encoded as a data URI
- Returns a list of `data:image/jpeg;base64,...` strings ready for the vision API

---

## 3. Import the multimedia module (main.py, top of file)

**Find** the import block:

```python
from langchain_tavily import TavilySearch
```

**Add** after it:

```python
from multimedia import transcribe_audio, extract_video_frames
```

---

## 4. Extend session state and file types (main.py, `# --- FILE UPLOAD SECTION ---`)

**Find** the session state initialization for `uploaded_image`:

```text
    if "uploaded_image" not in st.session_state:
        st.session_state.uploaded_image = None
```

**Add** after it (two new session state keys):

```text
    if "uploaded_audio_transcript" not in st.session_state:
        st.session_state.uploaded_audio_transcript = None

    if "uploaded_video_frames" not in st.session_state:
        st.session_state.uploaded_video_frames = []
```

**Find** the file type lists:

```text
    image_types = ["png", "jpg", "jpeg"]
    text_types = ["txt", "md", "csv", ...]
```

**Add** two new type lists:

```text
    audio_types = ["mp3", "wav", "m4a", "ogg", "flac", "webm"]
    video_types = ["mp4", "avi", "mov", "mkv", "webm"]
```

**Find** the `st.file_uploader` call:

```text
    uploaded = st.file_uploader(
        "Загрузить файл",
        type=image_types + text_types,
        accept_multiple_files=False
    )
```

**Replace** with:

```text
    uploaded = st.file_uploader(
        "Загрузить файл",
        type=image_types + text_types + audio_types + video_types,
        accept_multiple_files=False
    )
```

---

## 5. Handle audio and video upload (main.py, inside `if uploaded:`)

**Find** the existing upload handler:

```text
    if uploaded:
        st.session_state.messages = []
        ext = uploaded.name.rsplit(".", 1)[-1].lower()

        if ext in image_types:
            st.session_state.uploaded_image = encode_image_to_data_uri(uploaded, ext)
            st.session_state.uploaded_files = {}
            st.image(st.session_state.uploaded_image, caption=uploaded.name, use_container_width=False)
        else:
            try:
                content = uploaded.read().decode("utf-8")
            except UnicodeDecodeError:
                uploaded.seek(0)
                content = uploaded.read().decode("latin-1")
            st.session_state.uploaded_files[uploaded.name] = content
            st.session_state.uploaded_image = None
```

**Replace** with:

```text
    if uploaded:
        st.session_state.messages = []
        ext = uploaded.name.rsplit(".", 1)[-1].lower()

        if ext in image_types:
            st.session_state.uploaded_image = encode_image_to_data_uri(uploaded, ext)
            st.session_state.uploaded_files = {}
            st.session_state.uploaded_audio_transcript = None
            st.session_state.uploaded_video_frames = []
            st.image(st.session_state.uploaded_image, caption=uploaded.name, use_container_width=False)
        elif ext in audio_types:
            st.session_state.uploaded_image = None
            st.session_state.uploaded_files = {}
            st.session_state.uploaded_video_frames = []
            with st.spinner("Transcribing audio..."):
                transcript = transcribe_audio(uploaded)
            st.session_state.uploaded_audio_transcript = transcript
            st.info(f"Audio: {uploaded.name}")
            with st.chat_message("user"):
                st.markdown(f"**Transcript:**\n{transcript}")
        elif ext in video_types:
            st.session_state.uploaded_image = None
            st.session_state.uploaded_files = {}
            st.session_state.uploaded_audio_transcript = None
            with st.spinner("Extracting video frames..."):
                frames = extract_video_frames(uploaded)
            st.session_state.uploaded_video_frames = frames
            st.info(f"Video: {uploaded.name} ({len(frames)} frames extracted)")
            if frames:
                cols = st.columns(min(len(frames), 4))
                for i, frame_uri in enumerate(frames):
                    with cols[i % 4]:
                        st.image(frame_uri, caption=f"Frame {i + 1}", use_container_width=True)
        else:
            try:
                content = uploaded.read().decode("utf-8")
            except UnicodeDecodeError:
                uploaded.seek(0)
                content = uploaded.read().decode("latin-1")
            st.session_state.uploaded_files[uploaded.name] = content
            st.session_state.uploaded_image = None
            st.session_state.uploaded_audio_transcript = None
            st.session_state.uploaded_video_frames = []
```

**What changed (3 new branches):**

### A. Audio upload (`elif ext in audio_types`)

- Clears other upload states (image, video, text files)
- Calls `transcribe_audio()` inside a spinner
- Stores transcript in session state, displays it in a chat bubble

### B. Video upload (`elif ext in video_types`)

- Clears other upload states
- Calls `extract_video_frames()` inside a spinner
- Shows a grid of extracted frames as preview thumbnails

### C. Mutual exclusion

- Every branch clears the other upload states — audio, video, image, and text files are mutually exclusive per turn

---

## 6. Update the user input loop (main.py, `# --- 6. USER INPUT LOOP ---`)

**Find** the start of the user input block:

```text
    user_input = st.chat_input("Написать здесь...")
    if user_input:
        attached_image = st.session_state.uploaded_image
```

**Replace** with (capture all three multimedia states):

```text
    user_input = st.chat_input("Написать здесь...")
    if user_input:
        attached_image = st.session_state.uploaded_image
        audio_transcript = st.session_state.uploaded_audio_transcript
        video_frames = st.session_state.uploaded_video_frames
```

### Render badges in user chat bubble

**Find** the user chat bubble rendering:

```text
        with st.chat_message("user"):
            st.markdown(user_input)
            if attached_image:
                st.image(attached_image, use_container_width=False)
                st.info(f"Attached image: {uploaded.name}")
            elif uploaded:
                st.info(f"Attached file: {uploaded.name}")
```

**Replace** with:

```text
        with st.chat_message("user"):
            st.markdown(user_input)
            if attached_image:
                st.image(attached_image, use_container_width=False)
                st.info(f"Attached image: {uploaded.name}")
            elif audio_transcript:
                st.info(f"Audio transcript: {uploaded.name}")
            elif video_frames:
                st.info(f"Video frames: {uploaded.name} ({len(video_frames)} frames)")
            elif uploaded:
                st.info(f"Attached file: {uploaded.name}")
```

### Build the multimodal message

**Find** the `HumanMessage` construction:

```text
        if attached_image:
            user_message_object = HumanMessage(content=[
                {"type": "text", "text": user_input},
                {"type": "image_url", "image_url": {"url": attached_image}}
            ])
        else:
            user_message_object = HumanMessage(content=user_input)
```

**Replace** with (handles image + audio transcript + video frames):

```text
        message_parts = [{"type": "text", "text": user_input}]

        if attached_image:
            message_parts.append({"type": "image_url", "image_url": {"url": attached_image}})

        if audio_transcript:
            transcript_text = f"\n\n[Audio transcript from {uploaded.name}]:\n{audio_transcript}"
            message_parts[0]["text"] += transcript_text

        if video_frames:
            for frame_uri in video_frames:
                message_parts.append({"type": "image_url", "image_url": {"url": frame_uri}})

        if len(message_parts) == 1 and not audio_transcript:
            user_message_object = HumanMessage(content=user_input)
        else:
            user_message_object = HumanMessage(content=message_parts)
```

**How it works:**

- Audio transcript is appended to the text part of the message — the LLM reads it as context
- Video frames are added as `image_url` items — the vision model sees them as images
- If nothing is attached, falls back to a plain string `HumanMessage`

### Invocation paths

**Find** the LLM invocation inside `with st.spinner(...)`:

```text
                    if attached_image:
                        system_msg = SystemMessage(
                            content="You are an advanced assistant equipped with real-time web search "
                                    "and vision capabilities. You can analyze images and describe their "
                                    "contents. If you need information, call the web_search tool."
                        )
                        full_messages = [system_msg] + history_context + [user_message_object]
                        status_placeholder.markdown("Thinking...")
                        response_message = llm_with_tools.invoke(full_messages)
                    else:
```

**Replace** with (three paths: vision, audio, text):

```text
                    if attached_image or video_frames:
                        system_msg = SystemMessage(
                            content="You are an advanced assistant equipped with real-time web search "
                                    "and vision capabilities. You can analyze images, video frames, and describe their "
                                    "contents. If you need information, call the web_search tool."
                        )
                        full_messages = [system_msg] + history_context + [user_message_object]
                        status_placeholder.markdown("Thinking...")
                        response_message = llm_with_tools.invoke(full_messages)
                    elif audio_transcript:
                        system_msg = SystemMessage(
                            content="You are an advanced assistant equipped with real-time web search. "
                                    "The user has provided an audio transcript. Answer based on the transcript content. "
                                    "If you need information, call the web_search tool."
                        )
                        full_messages = [system_msg] + history_context + [user_message_object]
                        status_placeholder.markdown("Thinking...")
                        response_message = llm_with_tools.invoke(full_messages)
                    else:
```

**What changed:**

- **Vision path** (`attached_image or video_frames`): sends frames as `image_url` items to the vision model
- **Audio path** (`audio_transcript`): sends transcript as enriched text, no vision needed
- **Text path** (`else`): unchanged, uses the existing `modern_agent_chain`

### Clear multimedia state after send

**Find** at the end of the user input block:

```text
        st.session_state.uploaded_image = None
```

**Replace** with:

```text
        st.session_state.uploaded_image = None
        st.session_state.uploaded_audio_transcript = None
        st.session_state.uploaded_video_frames = []
```

---

## 7. Update system prompt (main.py, `# --- 4. BUILD THE CHAIN ---`)

**Find** the prompt template:

```text
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an advanced assistant equipped with real-time web search and file reading capabilities. If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
```

**Replace** with:

```text
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an advanced assistant equipped with real-time web search, file reading, and multimedia capabilities. "
         "You can analyze images, process audio transcripts, and examine video frames. "
         "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
```

---

## Key design decisions

- **`faster-whisper` over OpenAI Whisper**: runs on CPU with `int8` quantization, ~5 MB model, no GPU required. The
  `@st.cache_resource` decorator loads it once and reuses it.
- **Video as frames, not as video**: the vision API can't consume a video file directly. We extract 8 evenly-spaced
  frames with OpenCV and send them as `image_url` items — the AI "sees" a storyboard of the video.
- **Temp files for multimedia**: both `transcribe_audio` and `extract_video_frames` write to
  `tempfile.NamedTemporaryFile` because the underlying libraries (faster-whisper, OpenCV) need file paths. Files are
  cleaned up in `finally` blocks.
- **Audio → text, not audio → LLM**: the LLM doesn't accept raw audio. We transcribe first, then append the transcript
  to the user's text message. The AI reasons over the transcript content.
- **Mutually exclusive upload modes**: audio, video, image, and text file are mutually exclusive per turn. Uploading one
  clears the others.
- **Single-message scope**: multimedia attachments apply only to the next message, then are cleared from session state.
- **Vision model required**: the LM Studio backend must run a vision-capable model (e.g., LLaVA, Qwen-VL) for video
  frame analysis to work. Audio transcription works independently of the vision model.
