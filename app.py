import streamlit as st

from utils.style_loader import load_css

from mock.mock_data import (
    CURRENT_SUSPECT,
    CHAT_HISTORY,
    EVIDENCES,
)

from components import (
    header,
    suspect_panel,
    dialogue_panel,
    evidence_panel,
    defense_bar,
    control_panel,
)

st.set_page_config(

    page_title="Interrogation Room",

    layout="wide"
)

load_css()

header.render()

left, right = st.columns([4,5])

with left:

    suspect_panel.render(CURRENT_SUSPECT)

    defense_bar.render(
        CURRENT_SUSPECT["defense"]
    )

    evidence_panel.render(EVIDENCES)

with right:

    dialogue_panel.render(
        CHAT_HISTORY
    )

st.divider()

control_panel.render()