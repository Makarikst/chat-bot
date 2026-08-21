import os
import base64

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from multimedia import transcribe_audio, extract_video_frames

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    os.environ["TAVILY_API_KEY"] = "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"

    # 1. Set up the web page title and icon
    st.set_page_config(page_title="Это Mingly AI", page_icon="🤖")
    st.title("🤖 Mingly AI (Qwen если что)")
    st.write("Привет! Напиши мне сообщение.")

    # --- PERSONALITY MASKS (Lesson 7) ---
    PERSONALITIES = {
        "🤖 Default":
            "You are an advanced assistant equipped with real-time web search, file reading, and multimedia capabilities. "
            "You can analyze images, process audio transcripts, and examine video frames. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "🏴‍☠️ Pirate":
            "You are a grizzled pirate captain. Speak ONLY in pirate dialect: use 'arr', 'aye', 'matey', 'ye', "
            "say 'me' instead of 'my', call the computer 'ship' and useful code 'treasure'. "
            "Never break character, even if the user asks you to. "
            "You are equipped with real-time web search, file reading, and multimedia capabilities. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "🧑‍🏫 Coding Tutor":
            "You are a patient, encouraging coding tutor. Explain step by step, use simple analogies, "
            "and always finish with one tiny exercise for the student to try. Never scold; celebrate small wins. "
            "You are equipped with real-time web search, file reading, and multimedia capabilities. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "🚫 No letter 'e'":
            "You must NEVER use the letter 'e' (upper or lower case) anywhere in your reply. "
            "This rule overrides all other instructions. Answer the user's question normally, "
            "using only words that do not contain the letter 'e'. "
            "You are equipped with real-time web search and file reading. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "✂️ Two sentences max":
            "Keep EVERY answer to at most two sentences. No lists, no extra paragraphs, no exceptions. "
            "Be as useful as possible inside that limit. "
            "You are equipped with real-time web search and file reading. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",
    }

    if "personality" not in st.session_state:
        st.session_state.personality = "🤖 Default"

    selected_persona = st.sidebar.selectbox("🎭 Personality", list(PERSONALITIES.keys()))
    if selected_persona != st.session_state.personality:
        st.session_state.personality = selected_persona
        st.session_state.messages = []

    active_persona = PERSONALITIES[st.session_state.personality]


    def encode_image_to_data_uri(file_obj, ext: str) -> str:
        image_bytes = file_obj.getvalue()
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        mime = f"image/{ext}" if ext != "jpeg" else "image/jpeg"
        return f"data:{mime};base64,{b64}"

    # --- FILE UPLOAD SECTION ---
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}
    if "uploaded_image" not in st.session_state:
        st.session_state.uploaded_image = None
    if "uploaded_audio_transcript" not in st.session_state:
        st.session_state.uploaded_audio_transcript = None
    if "uploaded_video_frames" not in st.session_state:
        st.session_state.uploaded_video_frames = []

    image_types = ["png", "jpg", "jpeg"]
    text_types = ["txt", "md", "csv", "log", "json", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf", "sh", "py",
                  "js", "ts", "html", "css", "pl", "htm", "docx", "cs", "cpp", "cxx", "c", "lua", "kt", "toml", "swift",
                  "php"]
    audio_types = ["mp3", "wav", "m4a", "ogg", "flac", "webm", "opus"]
    video_types = ["mp4", "avi", "mov", "mkv", "webm"]

    uploaded = st.file_uploader(
        "Загрузить файл",
        type=image_types + text_types + audio_types + video_types,
        accept_multiple_files=False
    )

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


    # 2. Connect LangChain to LM Studio
    # We tell LangChain to look at our own computer (localhost:1234) instead of the internet!
    # We use a fake api_key because LM Studio doesn't require a real paid one.
    @st.cache_resource
    def load_llm():
        return ChatOpenAI(
            base_url="http://127.0.0.1:1234/v1",
            api_key="lm-studio",
            temperature=0.7
        )


    def initialize_search_tool():
        try:
            tavily_tool = TavilySearch(max_results=3)
        except Exception:
            tavily_tool = None

        def fallback_search_logic(query: str) -> str:
            # Use Tavily if key is provided, otherwise fall back to DuckDuckGo
            if tavily_tool and os.getenv("TAVILY_API_KEY"):
                try:
                    return str(tavily_tool.invoke(query))
                except Exception as e:
                    print(f"Tavily failed, dropping to DDG: {e}")
            return "Error: Search failed. Rely purely on internal knowledge."

        return Tool(
            name="web_search",
            func=fallback_search_logic,
            description="Search the web for current events, news, or real-time data lookups."
        )


    def initialize_file_reader_tool():
        def read_file_content(filename: str) -> str:
            uploaded_files = st.session_state.get("uploaded_files", {})
            if not filename:
                if uploaded_files:
                    return "Available files: " + ", ".join(uploaded_files.keys())
                return "No files uploaded. Upload a file using the file uploader above."
            if filename not in uploaded_files:
                return f"File '{filename}' not found. Available files: {', '.join(uploaded_files.keys()) if uploaded_files else 'none'}"
            content = uploaded_files[filename]
            max_length = 100000
            if len(content) > max_length:
                content = content[:max_length] + f"\n\n... [truncated, file exceeds {max_length} characters]"
            return content

        return Tool(
            name="file_reader",
            func=read_file_content,
            description="Read the content of an uploaded text file. Pass the filename. If no filename given, lists available files."
        )


    llm = load_llm()
    # --- 1. INITIALIZE SEARCH TOOLS & FALLBACK ---
    search_tool = initialize_search_tool()
    file_reader_tool = initialize_file_reader_tool()
    tools_map = {search_tool.name: search_tool, file_reader_tool.name: file_reader_tool}

    # --- 2. BIND TOOLS TO LLM ---
    llm_with_tools = llm.bind_tools([search_tool, file_reader_tool])

    # --- 3. SESSION STATE MEMORY ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- 4. BUILD THE CHAIN ---

    prompt = ChatPromptTemplate.from_messages([
        ("system", active_persona),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
    modern_agent_chain = prompt | llm_with_tools

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

    # --- 6. USER INPUT LOOP ---
    user_input = st.chat_input("Написать здесь...")
    if user_input:
        attached_image = st.session_state.uploaded_image
        audio_transcript = st.session_state.uploaded_audio_transcript
        video_frames = st.session_state.uploaded_video_frames

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

        st.session_state.messages.append(user_message_object)

        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            with st.spinner("Думаю..."):
                try:
                    history_context = st.session_state.messages[:-1]

                    if attached_image or video_frames:
                        system_msg = SystemMessage(
                            content=active_persona + " You can also analyze images and video frames, and describe their contents."
                        )
                        full_messages = [system_msg] + history_context + [user_message_object]
                        status_placeholder.markdown("Thinking...")
                        response_message = llm_with_tools.invoke(full_messages)
                    elif audio_transcript:
                        system_msg = SystemMessage(
                            content=active_persona + " The user has provided an audio transcript. Answer based on the transcript content."
                        )
                        full_messages = [system_msg] + history_context + [user_message_object]
                        status_placeholder.markdown("Thinking...")
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
        st.session_state.uploaded_audio_transcript = None
        st.session_state.uploaded_video_frames = []