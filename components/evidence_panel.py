import streamlit as st


def render(evidences):

    st.subheader("Evidence")

    for item in evidences:

        st.button(item["name"])