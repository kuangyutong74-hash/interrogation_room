import streamlit as st


def render(suspect):

    st.subheader("Suspect")

    st.image(
        suspect["avatar"],
        width=220
    )

    st.markdown(f"### {suspect['name']}")

    st.caption(suspect["role"])