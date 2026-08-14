import os
import base64

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    os.environ["TAVILY_API_KEY"] = "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"

    # 1. Set up the web page title and icon
    st.set_page_config(page_title="Это Mingly AI", page_icon="🤖")
    st.title("🤖 Mingly AI (Qwen если что)")
    st.write("Привет! Напиши мне сообщение.")


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

    image_types = ["png", "jpg", "jpeg"]
    text_types = ["txt", "md", "csv", "log", "json", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf", "sh", "py",
                  "js", "ts", "html", "css", "pl", "htm", "docx", "cs", "cpp", "cxx", "c", "lua", "kt", "toml", "swift",
                  "php"]

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
        ("system",
         "You are an advanced assistant equipped with real-time web search and file reading capabilities. If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool."),
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