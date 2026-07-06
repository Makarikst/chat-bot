import streamlit as st
from langchain_openai import ChatOpenAI

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
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

    llm = load_llm()

    # 2. Create the memory (Session State)
    # Web pages forget everything when they refresh.
    # We use st.session_state to make our bot remember the chat history!
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 3. Display all previous messages from the memory
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # 4. Get new input from the user
    user_input = st.chat_input("Написать здесь...")
    # 5. What happens when the user presses Enter?
    if user_input:
        # Show the user's message on the screen immediately
        with st.chat_message("user"):
            st.write(user_input)

        # Save the user's message to the memory list
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # Show a loading spinner while the local AI thinks
        with st.chat_message("assistant"):
            with st.spinner("Думаю..."):
                try:
                    # Send the message to LM Studio using LangChain
                    ai_response = llm.invoke(user_input)
                    bot_response = ai_response.content
                except Exception as e:
                    bot_response = f"Oops! Is your LM Studio Local Server running? Error: {e}"

                # Show the AI's response on the screen
                st.write(bot_response)

        # Save the bot's response to the memory list
        st.session_state.chat_history.append({"role": "assistant", "content": bot_response})
