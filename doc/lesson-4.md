# Plan: Document Processing File Reader                                                                                                 
                                                                                                                                      
## 1. Create `file_reader` tool (main.py)                                                                                                  
                                                                                                                                      
   - Build a `Tool` that accepts a `filename` argument                                                                                       
   - Reads uploaded file content from the session state (in-memory, no disk I/O)                                                             
   - Supports listing available files when no filename is given                                                                          
   - Returns file content or an error message if a file is not found                

```python
    # 1. Set up the web page title and icon
    # st.set_page_config(page_title="Это Mingly AI", page_icon="🤖")
    # st.title("🤖 Mingly AI (Qwen если что)")
    # st.write("Привет! Напиши мне сообщение.")

    # --- FILE UPLOAD SECTION ---
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}

    uploaded = st.file_uploader(
        "Загрузить текстовый файл",
        type=["txt", "md", "csv", "log", "json", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf", "sh", "py", "js", "ts", "html", "css"],
        accept_multiple_files=True
    )
```
                                                                                                                                      
## 2. Store uploaded files in a session state                                                                                              
                                                                                                                                      
   - Add `uploaded_files` dict to `st.session_state` (filename → content)                                                                    
   - On upload, decode all text-based formats (`.txt`, `.md`, `.csv`, `.log`, `.json`, `.xml`, etc.)                                                 
   - Store decoded text in memory          

```python
    if uploaded:
        for file in uploaded:
            try:
                content = file.read().decode("utf-8")
            except UnicodeDecodeError:
                file.seek(0)
                content = file.read().decode("latin-1")
            st.session_state.uploaded_files[file.name] = content
        st.success(f"Загружено файлов: {len(uploaded)}")
        st.session_state.messages = []
```
                                                                                                                                      
## 3. Add Streamlit file upload UI                                                                                                       
                                                                                                                                      
   - `st.file_uploader` widget (multi-file, accept all text types)                                                                         
   - Show uploaded file names in the UI so the user knows what's available                                                               
   - Display a brief confirmation on upload                                                                                              
                                                                                                                                      
## 4. Wire the tool into the agent loop                                                                                                      
                                                                                                                                      
   - Add `file_reader` to `tools_map` and bind to `llm_with_tools`                                                                             
   - Update system prompt to mention file reading capability                                                                             
   - Tool execution flows through the existing `tool_calls` handling (no loop changes needed) 

```python
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
```

```python
    # --- 1. INITIALIZE SEARCH TOOLS & FALLBACK ---
    search_tool = initialize_search_tool()
    file_reader_tool = initialize_file_reader_tool()
    tools_map = {search_tool.name: search_tool, file_reader_tool.name: file_reader_tool}

    # --- 2. BIND TOOLS TO LLM ---
    llm_with_tools = llm.bind_tools([search_tool, file_reader_tool])
```

```python
    # --- 4. BUILD THE CHAIN ---
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an advanced assistant equipped with real-time web search and file reading capabilities. If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
```

```python
                            # Fetch tool function and query arguments from the incoming payload
                            target_tool = tools_map[tool_name]
                            query_arg = tool_args.get("query") or tool_args.get("filename") or tool_args.get("__arg1") or str(tool_args)
```
                                                                                                                                      
## 5. Update pyproject.toml                                                                                                              
                                                                                                                                      
   - No new dependencies are needed — all uses existing `langchain_core` and `streamlit`                                                         
                                                                                                                                      
## Key design decisions                                                                                                                  
                                                                                                                                      
- **In-memory only**: Files live in session_state, cleared on page reload (simple, no temp file cleanup)                                                                                                                       
- **Size guard**: Truncate files >~100KB to avoid blowing up the context window                                                               
- **Encoding**: UTF-8 with fallback to latin-1 