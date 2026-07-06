import streamlit as st
# 1. Set up the web page title and icon
st.set_page_config(page_title="Хомячок-повторюшка", page_icon="🤖")
st.title("🤖 Хомячок-повторюшка")
st.write("Напиши, я повторю")
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
user_input = st.chat_input("Пиши сюда")
# 5. What happens when the user presses Enter?
if user_input:
    # Show the user's message on the screen immediately
    with st.chat_message("user"):
        st.write(user_input)

    # Save the user's message to the memory list
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # Create the bot's response (For Lesson 1, it just repeats the user)
    bot_response = f"Хомячок-повторюшка: {user_input}"

    # Show the bot's response on the screen
    with st.chat_message("assistant"):
        st.write(bot_response)

    # Save the bot's response to the memory list
    st.session_state.chat_history.append({"role": "assistant", "content": bot_response})