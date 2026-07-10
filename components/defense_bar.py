import streamlit as st


def render(score):

    st.markdown("### Psychological Defense")

    st.progress(score / 100)

    st.write(f"{score}/100")