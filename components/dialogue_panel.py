import streamlit as st


def render(history):

    st.subheader("Interrogation")

    for message in history:

        with st.chat_message(message["role"]):

            st.write(message["content"])

    st.chat_input(
        "Ask something..."
    )