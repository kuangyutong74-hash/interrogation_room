import streamlit as st


def render():

    c1, c2 = st.columns(2)

    with c1:

        st.button(
            "🟥 ARREST",
            use_container_width=True
        )

    with c2:

        st.button(
            "🟩 RELEASE",
            use_container_width=True
        )