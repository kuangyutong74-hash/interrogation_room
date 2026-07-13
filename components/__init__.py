# components/__init__.py
from . import header
from . import suspect_panel
from . import defense_bar
from . import evidence_panel
from . import dialogue_panel
from . import control_panel
from . import forensic_popup   # 新增
__all__ = [
    "header",
    "suspect_panel",
    "dialogue_panel",
    "evidence_panel",
    "defense_bar",
    "control_panel",
    "forensic_popup"
]