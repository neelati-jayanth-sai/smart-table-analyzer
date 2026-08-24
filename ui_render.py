import json
import re

import streamlit as st

_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")


def _looks_like_markdown_table(text: str) -> bool:
    lines = text.splitlines()
    for i in range(len(lines) - 1):
        if _TABLE_ROW_RE.match(lines[i]) and _TABLE_SEPARATOR_RE.match(lines[i + 1]) and "-" in lines[i + 1]:
            return True
    return False


def render_text_block(text: str) -> None:
    if text and _looks_like_markdown_table(text):
        st.markdown(text)
        return

    try:
        parsed = json.loads(text)
        st.json(parsed)
    except (TypeError, ValueError):
        st.code(text, language="text")
