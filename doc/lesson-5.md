# Plan: Image Upload & Multimodal Vision

## 1. Update imports (main.py, lines 1-10)

**Find** the import block at the top of the file:

```python
import os

from dotenv import load_dotenv
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
```

**Replace** with:

```python
import os
import base64

from dotenv import load_dotenv
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
```

**What changed:**
- Added `import base64` — stdlib module for encoding images
- Added `SystemMessage` to the `langchain_core.messages` import — needed for the vision system prompt

## 2. Add the base64 encoding function (main.py, after line 18)

**Find** the line after `st.write("Привет! Напиши мне сообщение.")` (line 18).

**Insert** the encoding function here — it must appear before the file upload section since Streamlit executes top-to-bottom:

```python
    def encode_image_to_data_uri(file_obj, ext: str) -> str:
        image_bytes = file_obj.getvalue()
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        mime = f"image/{ext}" if ext != "jpeg" else "image/jpeg"
        return f"data:{mime};base64,{b64}"
```

**Why base64?** The OpenAI-compatible API (which LM Studio exposes) accepts images as base64-encoded data URIs inside the message payload. This avoids disk I/O and temp file management.

## 3. Extend the file uploader to accept images (main.py, lines 20-38)

**Find** the existing file upload section (marked `# --- FILE UPLOAD SECTION ---`):

```python
    # --- FILE UPLOAD SECTION ---
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}

    uploaded = st.file_uploader(
        "Загрузить текстовый файл",
        type=["txt", "md", "csv", "log", "json", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf", "sh", "py", "js", "ts", "html", "css"],
        accept_multiple_files=False
    )

    if uploaded:
        try:
            content = uploaded.read().decode("utf-8")
        except UnicodeDecodeError:
            uploaded.seek(0)
            content = uploaded.read().decode("latin-1")
        st.session_state.uploaded_files[uploaded.name] = content
        st.session_state.messages = []
```

**Replace** with:

```python
    # --- FILE UPLOAD SECTION ---
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}

    if "uploaded_image" not in st.session_state:
        st.session_state.uploaded_image = None

    image_types = ["png", "jpg", "jpeg"]
    text_types = ["txt", "md", "csv", "log", "json", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf", "sh", "py", "js", "ts", "html", "css"]

    uploaded = st.file_uploader(
        "Загрузить файл",
        type=image_types + text_types,
        accept_multiple_files=False
    )

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

**What changed:**
- Added `uploaded_image` to session state to hold the base64 data URI
- Split file types into `image_types` and `text_types` lists
- Label changed from `"Загрузить текстовый файл"` to `"Загрузить файл"`
- On upload, check extension: if image → encode to data URI, clear text files, show preview; if text → decode as before, clear image
- `st.image()` renders the preview immediately below the uploader

## 4. Render multimodal messages in chat history (main.py, section `# --- 5. RENDER THE CHAT HISTORY ---`)

**Find** the chat history rendering loop:

```python
    # --- 5. RENDER THE CHAT HISTORY ---
    for msg in st.session_state.messages:
        if isinstance(msg, ToolMessage):
            continue  # Don't render raw tool JSON messages directly to the user UI
        with st.chat_message("user" if isinstance(msg, HumanMessage) else "assistant"):
            st.markdown(msg.content)
```

**Replace** with:

```python
    # --- 5. RENDER THE CHAT HISTORY ---
    for msg in st.session_state.messages:
        if isinstance(msg, ToolMessage):
            continue
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        with st.chat_message(role):
            if isinstance(msg.content, list):
                for item in msg.content:
                    if item["type"] == "text":
                        st.markdown(item["text"])
                    elif item["type"] == "image_url":
                        st.image(item["image_url"]["url"], use_container_width=False)
            else:
                st.markdown(msg.content)
```

**What changed:**
- If `msg.content` is a `list` (multimodal message), iterate items: render `"text"` as markdown, `"image_url"` via `st.image()`
- If `msg.content` is a `str` (plain text), render as before

## 5. Update the user input loop (main.py, section `# --- 6. USER INPUT LOOP ---`)

**Find** the user input section starting at `# --- 6. USER INPUT LOOP ---`:

```python
    # --- 6. USER INPUT LOOP ---
    user_input = st.chat_input("Написать здесь...")
    # 5. What happens when the user presses Enter?
    if user_input:
        # Render user query immediately
        with st.chat_message("user"):
            st.markdown(user_input)
            if uploaded:
                st.info(f"📄 Attached file: {uploaded.name}")

        user_message_object = HumanMessage(content=user_input)
        st.session_state.messages.append(user_message_object)

        # Show a loading spinner while the local AI thinks
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            with st.spinner("Думаю..."):
                try:
                    # Pull history up to (but not including) the current question
                    history_context = st.session_state.messages[:-1]
                    # Step A: Invoke the first layer of the chain to check if a tool call is needed
                    status_placeholder.markdown("🧠 *Thinking...*")
                    response_message = modern_agent_chain.invoke({
                        "input": user_input,
                        "chat_history": history_context
                    })

                    # Step B: Check if the AI wants to use our search tool
                    if response_message.tool_calls:
                        # Store the AI's intent to call a tool
                        st.session_state.messages.append(response_message)

                        for tool_call in response_message.tool_calls:
                            tool_name = tool_call["name"]
                            tool_args = tool_call["args"]

                            status_placeholder.markdown(f"🔍 *Executing tool lookup: {tool_name}...*")

                            # Fetch tool function and query arguments from the incoming payload
                            target_tool = tools_map[tool_name]
                            query_arg = tool_args.get("query") or tool_args.get("__arg1") or str(tool_args)
                            tool_output = target_tool.invoke(query_arg)

                            # Store the tool outcome results back in history
                            tool_message = ToolMessage(content=tool_output, tool_call_id=tool_call["id"])
                            st.session_state.messages.append(tool_message)

                        # Step C: Re-run the LLM with the new search context attached to its history
                        status_placeholder.markdown("✍️ *Writing final answer...*")
                        final_response = llm.invoke(st.session_state.messages)
                        bot_response = final_response.content
                    else:
                        # No tool was needed, use the standard immediate text response
                        bot_response = response_message.content
                except Exception as e:
                    bot_response = f"Oops! Is your LM Studio Local Server running? Error: {e}"

            # Clean up indicators and print the real text answer
            status_placeholder.empty()
            st.markdown(bot_response)

            # Store final response object to complete memory loop
            st.session_state.messages.append(AIMessage(content=bot_response))
```

**Replace** with:

```python
    # --- 6. USER INPUT LOOP ---
    user_input = st.chat_input("Написать здесь...")
    if user_input:
        attached_image = st.session_state.uploaded_image

        with st.chat_message("user"):
            st.markdown(user_input)
            if attached_image:
                st.image(attached_image, use_container_width=False)
                st.info(f"🖼️ Attached image: {uploaded.name}")
            elif uploaded:
                st.info(f"📄 Attached file: {uploaded.name}")

        if attached_image:
            user_message_object = HumanMessage(content=[
                {"type": "text", "text": user_input},
                {"type": "image_url", "image_url": {"url": attached_image}}
            ])
        else:
            user_message_object = HumanMessage(content=user_input)

        st.session_state.messages.append(user_message_object)

        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            with st.spinner("Думаю..."):
                try:
                    history_context = st.session_state.messages[:-1]

                    if attached_image:
                        system_msg = SystemMessage(
                            content="You are an advanced assistant equipped with real-time web search "
                                    "and vision capabilities. You can analyze images and describe their "
                                    "contents. If you need information, call the web_search tool."
                        )
                        full_messages = [system_msg] + history_context + [user_message_object]
                        status_placeholder.markdown("🧠 *Thinking...*")
                        response_message = llm_with_tools.invoke(full_messages)
                    else:
                        status_placeholder.markdown("🧠 *Thinking...*")
                        response_message = modern_agent_chain.invoke({
                            "input": user_input,
                            "chat_history": history_context
                        })

                    if response_message.tool_calls:
                        st.session_state.messages.append(response_message)

                        for tool_call in response_message.tool_calls:
                            tool_name = tool_call["name"]
                            tool_args = tool_call["args"]

                            status_placeholder.markdown(f"🔍 *Executing tool lookup: {tool_name}...*")

                            target_tool = tools_map[tool_name]
                            query_arg = tool_args.get("query") or tool_args.get("__arg1") or str(tool_args)
                            tool_output = target_tool.invoke(query_arg)

                            tool_message = ToolMessage(content=tool_output, tool_call_id=tool_call["id"])
                            st.session_state.messages.append(tool_message)

                        status_placeholder.markdown("✍️ *Writing final answer...*")
                        final_response = llm.invoke(st.session_state.messages)
                        bot_response = final_response.content
                    else:
                        bot_response = response_message.content
                except Exception as e:
                    bot_response = f"Oops! Is your LM Studio Local Server running? Error: {e}"

            status_placeholder.empty()
            st.markdown(bot_response)
            st.session_state.messages.append(AIMessage(content=bot_response))

        st.session_state.uploaded_image = None
```

**What changed (3 additions):**

### A. Capture image before sending (line `attached_image = ...`)
- Store `st.session_state.uploaded_image` in a local variable at the start of the block
- This snapshot is used for the rest of the message processing

### B. Render image in user chat bubble (inside `with st.chat_message("user")`)
- If image attached: render it with `st.image()` and show `🖼️ Attached image` badge
- If text file attached: show `📄 Attached file` badge (unchanged)

### C. Build multimodal `HumanMessage` (before `st.session_state.messages.append(...)`)
- If image attached: construct `HumanMessage` with a content **list** containing `{"type": "text", ...}` and `{"type": "image_url", ...}` items
- If no image: construct `HumanMessage` with a plain string (unchanged)

### D. Vision invocation path (inside `with st.spinner(...)`)
- If image attached: build `SystemMessage` with vision-aware prompt, assemble `full_messages` list manually, invoke `llm_with_tools.invoke(full_messages)` directly
- If no image: use existing `modern_agent_chain.invoke(...)` (unchanged)

### E. Clear image after send (at the end of the block)
- `st.session_state.uploaded_image = None` — ensures the image only applies to the single message it was sent with

## 6. Update pyproject.toml

No changes needed — `base64` is stdlib, `SystemMessage` is already in `langchain_core`.

## Key design decisions

- **Single-message scope**: The image is attached only to the next message, then cleared. It does not persist in conversation memory.
- **Mutually exclusive modes**: Uploading an image clears text files and vice versa. The AI sees either an image or text files, never both in the same turn.
- **No disk I/O**: Images live entirely in memory as base64 strings in session state.
- **Two invocation paths**: Text-only messages use the existing `ChatPromptTemplate` chain (unchanged). Image messages bypass the template and invoke the LLM directly with a manually assembled message list.
- **Vision model required**: The LM Studio backend must run a vision-capable model (e.g., LLaVA, Qwen-VL) for image analysis to work.
