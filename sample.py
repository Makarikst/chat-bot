import streamlit as st
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_tavily import TavilySearch

if __name__ == 'main':
    os.environ["TAVILY_API_KEY"] = "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"

    # 1. Set up the web page title and icon
    st.set_page_config(page_title="Это Mingly AI", page_icon="🤖")
    st.title("🤖 Mingly AI (Qwen если что)")
    st.write("Привет! Напиши мне сообщение.")

    # 2. Connect LangChain to LM Studio
    # We tell LangChain to look at our own computer (localhost:1234) instead of the internet!
    # We use a fake api_key because LM Studio doesn't require a real paid one.
    @st.cache_resource
    def load_llm():
        return ChatOpenAI(
            base_url="http://192.168.87.7:1234/v1",
            api_key="lm-studio",
            temperature=0.7
        )


    def initialize_search_tool():
        try:
            tavily_tool = TavilySearch(max_results=3)
        except Exception:
            tavily_tool = None

        # ddg_tool = DuckDuckGoSearchRun()

        def fallback_search_logic(query: str) -> str:
            # Use Tavily if key is provided, otherwise fall back to DuckDuckGo
            if tavily_tool and os.getenv("TAVILY_API_KEY"):
                try:
                    return str(tavily_tool.invoke(query))
                except Exception as e:
                    print(f"Tavily failed, dropping to DDG: {e}")
            return "Error: Search failed. Rely purely on internal knowledge."
            # try:
            #     return str(ddg_tool.invoke(query))
            # except Exception:
            #     return "Error: Search failed. Rely purely on internal knowledge."

        return Tool(
            name="web_search",
            func=fallback_search_logic,
            description="Search the web for current events, news, or real-time data lookups."
        )

    llm = load_llm()
    # --- 1. INITIALIZE SEARCH TOOLS & FALLBACK ---
    search_tool = initialize_search_tool()
    tools_map = {search_tool.name: search_tool}

    # --- 2. BIND TOOLS TO LLM ---
    llm_with_tools = llm.bind_tools([search_tool])

    # --- 3. SESSION STATE MEMORY ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- 4. BUILD THE CHAIN ---
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an advanced assistant equipped with real-time web search capabilities. If you need information, call the web_search tool."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    modern_agent_chain = prompt | llm_with_tools

    # --- 5. RENDER THE CHAT HISTORY ---
    for msg in st.session_state.messages:
        if isinstance(msg, ToolMessage):
            continue  # Don't render raw tool JSON messages directly to the user UI
        with st.chat_message("user" if isinstance(msg, HumanMessage) else "assistant"):
            st.markdown(msg.content)

    # --- 6. USER INPUT LOOP ---
    user_input = st.chat_input("Написать здесь...")
    # 5. What happens when the user presses Enter?
    if user_input:
        # Render user query immediately
        with st.chat_message("user"):
            st.markdown(user_input)

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

                            # Execute the actual search execution
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