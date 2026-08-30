"""Session-only Ticksy launcher and initial local-data chat experience."""

from __future__ import annotations

import base64
from pathlib import Path

import requests
import streamlit as st

from models.assistant import AssistantMessage, AssistantRequest
from models.assistant_action import AssistantAction
from services.assistant_actions import apply_action, propose_action
from services.assistant_context import build_local_context
from services.assistant_explanations import explain_stock_prompt
from services.assistant_provider import DisabledProvider, build_provider, load_assistant_settings
from services.assistant_responses import local_response


SESSION_KEY = "ticksy_messages"
PROMPT_KEY = "ticksy_prompt"
ACTION_KEY = "ticksy_pending_action"
LEGACY_GREETING = "I can explain local scan results and Backtester outputs. I do not use internet data."
TICKSY_ICON = Path(__file__).parents[1] / "assets" / "ticksy-icon.svg"


def _messages() -> list[AssistantMessage]:
    """Initialise the chat history without touching scan/backtest state."""
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = []
    st.session_state[SESSION_KEY] = [
        message
        for message in st.session_state[SESSION_KEY]
        if message.content != LEGACY_GREETING
    ]
    return st.session_state[SESSION_KEY]


def _render_ticksy_panel() -> None:
    """Render Ticksy content only after the user opens the launcher."""
    with st.container(key="ticksy_panel", border=True):
        icon, header, reset = st.columns((0.45, 3.55, 1), vertical_alignment="center")
        icon.image(str(TICKSY_ICON), width=34)
        header.subheader("TICKSY")
        if reset.button("New chat", key="ticksy_new_chat"):
            st.session_state.pop(SESSION_KEY, None)
            st.rerun()
        st.info(
            "Ticksy is a local-data-only market assistant that explains Golden Cross, "
            "Impending, and failed-stock results; runs confirmed scans and backtests; "
            "compares stocks and historical signals; summarises the current market setup; "
            "understands natural-language requests; navigates the app; and creates simple "
            "reports while explaining calculation inputs and data sources. It never uses "
            "internet, news, RAG, or external market-data retrieval."
        )
        settings = load_assistant_settings(st.secrets)
        provider = build_provider(settings)
        if isinstance(provider, DisabledProvider):
            st.info("Chat is disabled until the selected provider API key is configured.")
        st.caption("QUICK ACTIONS")
        quick_left, quick_right = st.columns(2)
        if quick_left.button("Explain results", use_container_width=True):
            st.session_state[PROMPT_KEY] = "Explain the current scan results."
        if quick_right.button("Backtest a stock", use_container_width=True):
            st.session_state[PROMPT_KEY] = "I want to backtest a stock."
        if quick_left.button("Why is a stock impending?", use_container_width=True):
            st.session_state[PROMPT_KEY] = "Why is a stock impending a Golden Cross?"
        if quick_right.button("Market setup", use_container_width=True):
            st.session_state[PROMPT_KEY] = "Summarise the current market setup."
        for message in _messages():
            with st.chat_message("assistant" if message.role == "model" else "user"):
                st.write(message.content)
        action = st.session_state.get(ACTION_KEY)
        if isinstance(action, AssistantAction):
            st.warning(f"Proposed action: {action.summary}")
            confirm, cancel = st.columns(2)
            if confirm.button("Apply and run", type="primary", use_container_width=True):
                try:
                    message = apply_action(action, st.session_state)
                except ValueError as error:
                    st.error(str(error))
                else:
                    _messages().append(AssistantMessage("model", message))
                    st.session_state.pop(ACTION_KEY, None)
                    st.rerun()
            if cancel.button("Cancel", use_container_width=True):
                st.session_state.pop(ACTION_KEY, None)
                st.rerun()
        with st.form("ticksy_message", clear_on_submit=True):
            prompt = st.text_input("Ask Ticksy", placeholder="Why did TCS qualify?", label_visibility="collapsed", key=PROMPT_KEY)
            sent = st.form_submit_button("Send", type="primary", use_container_width=True)
        if sent and prompt.strip():
            messages = _messages()
            messages.append(AssistantMessage("user", prompt.strip()))
            action = propose_action(prompt, st.session_state)
            if action:
                st.session_state[ACTION_KEY] = action
                response = "I understood your request. Please confirm the proposed action before I continue."
            else:
                response = local_response(st.session_state, prompt)
                if response is None:
                    response = explain_stock_prompt(st.session_state, prompt)
                if response is None:
                    try:
                        response = provider.respond(AssistantRequest(tuple(messages), build_local_context(st.session_state, prompt)))
                    except requests.RequestException:
                        response = "Ticksy could not reach the configured provider. Your local app data remains unchanged."
                    except RuntimeError as error:
                        response = f"Ticksy could not complete that response: {error}"
            messages.append(AssistantMessage("model", response))
            st.rerun()


def render_ticksy() -> None:
    """Render a compact launcher fixed to the lower-right viewport corner."""
    icon_data = base64.b64encode(TICKSY_ICON.read_bytes()).decode("ascii")
    st.markdown(
        f"""
        <style>
        .st-key-ticksy_launcher [data-testid="stPopoverButton"] {{
            padding-left: 2.45rem;
            background-image: url("data:image/svg+xml;base64,{icon_data}");
            background-repeat: no-repeat;
            background-position: 0.65rem center;
            background-size: 1.45rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="ticksy_launcher"):
        with st.popover("TICKSY"):
            _render_ticksy_panel()
