"""Session-only Ticksy launcher and initial local-data chat experience."""

from __future__ import annotations

import base64

import streamlit as st

from stock_analyser.agents.action_models import AssistantAction
from stock_analyser.agents.actions import propose_action
from stock_analyser.agents.models import AssistantMessage
from stock_analyser.application.commands.update_strategy import apply_action
from stock_analyser.agents.explanations import explain_stock_prompt
from stock_analyser.infrastructure.model_factory import (
    DisabledProvider,
    build_provider,
    load_assistant_settings,
)
from stock_analyser.agents.responses import local_response
from stock_analyser import PROJECT_ROOT
from stock_analyser.agents.orchestrator import AssistantAnswer, AssistantRuntime
from stock_analyser.application.ports.model_provider import (
    ModelProviderError,
    ModelProviderTransportError,
)
from stock_analyser.presentation.streamlit.session_adapter import current_session


SESSION_KEY = "ticksy_messages"
PROMPT_KEY = "ticksy_prompt"
ACTION_KEY = "ticksy_pending_action"
RUNTIME_KEY = "ticksy_runtime"
LEGACY_GREETING = "I can explain local scan results and Backtester outputs. I do not use internet data."
TICKSY_ICON = PROJECT_ROOT / "assets" / "ticksy-icon.svg"


def _runtime() -> AssistantRuntime:
    """Return the tool runtime isolated to the current Streamlit session."""
    session = current_session()
    runtime = session.get(RUNTIME_KEY)
    if not isinstance(runtime, AssistantRuntime):
        runtime = AssistantRuntime()
        session[RUNTIME_KEY] = runtime
    return runtime


def _ground_local_response(response: str) -> str:
    context = AssistantRuntime.context(current_session())
    return AssistantAnswer(
        response,
        scan_time=str(context.get("scan_time")) if context.get("scan_time") else None,
        snapshot_identity=context.snapshot_identity,
    ).render()


def _messages() -> list[AssistantMessage]:
    """Initialise the chat history without touching scan/backtest state."""
    session = current_session()
    if SESSION_KEY not in session:
        session[SESSION_KEY] = []
    session[SESSION_KEY] = [
        message
        for message in session[SESSION_KEY]
        if message.content != LEGACY_GREETING
    ]
    return session[SESSION_KEY]


def _render_ticksy_panel() -> None:
    """Render Ticksy content only after the user opens the launcher."""
    session = current_session()
    with st.container(key="ticksy_panel", border=True):
        icon, header, reset = st.columns((0.45, 3.55, 1), vertical_alignment="center")
        icon.image(str(TICKSY_ICON), width=34)
        header.subheader("TICKSY")
        if reset.button("New chat", key="ticksy_new_chat"):
            session.pop(SESSION_KEY, None)
            session.pop(RUNTIME_KEY, None)
            session.rerun()
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
            st.info(
                "Chat is disabled until the selected provider API key is configured."
            )
        st.caption("QUICK ACTIONS")
        quick_left, quick_right = st.columns(2)
        if quick_left.button("Explain results", use_container_width=True):
            session[PROMPT_KEY] = "Explain the current scan results."
        if quick_right.button("Backtest a stock", use_container_width=True):
            session[PROMPT_KEY] = "I want to backtest a stock."
        if quick_left.button("Why is a stock impending?", use_container_width=True):
            session[PROMPT_KEY] = "Why is a stock impending a Golden Cross?"
        if quick_right.button("Market setup", use_container_width=True):
            session[PROMPT_KEY] = "Summarise the current market setup."
        for message in _messages():
            with st.chat_message("assistant" if message.role == "model" else "user"):
                st.write(message.content)
        action = session.get(ACTION_KEY)
        if isinstance(action, AssistantAction):
            st.warning(f"Proposed action: {action.summary}")
            confirm, cancel = st.columns(2)
            if confirm.button(
                "Apply and run", type="primary", use_container_width=True
            ):
                try:
                    message = apply_action(action, session)
                except ValueError as error:
                    st.error(str(error))
                else:
                    _messages().append(AssistantMessage("model", message))
                    session.pop(ACTION_KEY, None)
                    session.rerun()
            if cancel.button("Cancel", use_container_width=True):
                session.pop(ACTION_KEY, None)
                session.rerun()
        with st.form("ticksy_message", clear_on_submit=True):
            prompt = st.text_input(
                "Ask Ticksy",
                placeholder="Why did TCS qualify?",
                label_visibility="collapsed",
                key=PROMPT_KEY,
            )
            sent = st.form_submit_button(
                "Send", type="primary", use_container_width=True
            )
        if sent and prompt.strip():
            messages = _messages()
            messages.append(AssistantMessage("user", prompt.strip()))
            action = propose_action(prompt, session)
            if action:
                session[ACTION_KEY] = action
                response = "I understood your request. Please confirm the proposed action before I continue."
            else:
                response = local_response(session, prompt)
                if response is None:
                    response = explain_stock_prompt(session, prompt)
                if response is None:
                    try:
                        response = (
                            _runtime()
                            .answer(
                                provider,
                                AssistantRuntime.context(session),
                                tuple(messages),
                                prompt,
                            )
                            .render()
                        )
                    except ModelProviderTransportError as error:
                        status_code = error.status_code
                        if status_code in {500, 502, 503, 504}:
                            response = "Ticksy's configured provider is temporarily unavailable. Please try again in a moment. Your local app data remains unchanged."
                        elif status_code == 429:
                            response = "Ticksy's configured provider is currently rate-limited. Please try again shortly. Your local app data remains unchanged."
                        elif status_code in {401, 403}:
                            response = "Ticksy's configured provider rejected its API key or access settings. Check the provider key and its project permissions. Your local app data remains unchanged."
                        elif status_code is not None:
                            response = "Ticksy could not complete the configured provider request. Your local app data remains unchanged."
                        else:
                            response = "Ticksy could not reach the configured provider. Your local app data remains unchanged."
                    except ModelProviderError as error:
                        response = f"Ticksy could not complete that response: {error}"
                else:
                    response = _ground_local_response(response)
            messages.append(AssistantMessage("model", response))
            session.rerun()


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
