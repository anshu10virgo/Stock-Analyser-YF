"""Shared visual styling for the Streamlit application."""

from __future__ import annotations

import streamlit as st


def apply_app_theme() -> None:
    """Apply the approved desktop visual system without altering widgets."""
    st.markdown(
        """
        <style>
        :root {
            --sa-navy: #102a43;
            --sa-blue: #2563a6;
            --sa-teal: #0f8b8d;
            --sa-green: #1f9d68;
            --sa-amber: #e59f23;
            --sa-surface: #f3f6fa;
            --sa-raised: #f8fafc;
        }
        html, body, [class*="st-"] {
            font-size: 0.96rem;
        }
        [data-testid="stAppViewContainer"] {
            color: var(--sa-navy);
            background:
                radial-gradient(circle at 95% 0%, rgba(15, 139, 141, 0.10), transparent 24rem),
                linear-gradient(180deg, #eef4f9 0%, var(--sa-surface) 24rem);
        }
        [data-testid="stHeader"] {
            background: rgba(243, 246, 250, 0.94);
        }
        .sa-app-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            padding: 0.8rem 1rem;
            margin: -0.25rem 0 1rem;
            color: white;
            background: linear-gradient(115deg, var(--sa-navy), var(--sa-blue) 58%, var(--sa-teal));
            border-radius: 0.75rem;
            box-shadow: 0 0.55rem 1.4rem rgba(16, 42, 67, 0.16);
        }
        .sa-app-header h1 {
            margin: 0;
            color: white;
            font-size: 1.55rem;
        }
        .sa-app-header p {
            margin: 0.15rem 0 0;
            color: rgba(255, 255, 255, 0.82);
            font-size: 0.82rem;
        }
        .sa-market-pill {
            padding: 0.35rem 0.7rem;
            border: 1px solid rgba(255, 255, 255, 0.38);
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.12);
            white-space: nowrap;
        }
        .sa-hero-copy {
            padding: 1.1rem 0.4rem 1rem 0;
        }
        .sa-hero-copy .sa-kicker {
            color: var(--sa-teal);
            font-weight: 700;
            letter-spacing: 0.08em;
            font-size: 0.75rem;
        }
        .sa-hero-copy h2 {
            margin: 0.45rem 0 0.7rem;
            color: var(--sa-navy);
            font-size: 1.75rem;
            line-height: 1.15;
        }
        .sa-accent-rule {
            width: 4rem;
            height: 0.3rem;
            margin: 0.7rem 0;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--sa-green), var(--sa-amber));
        }
        [data-testid="stImage"] img {
            border-radius: 0.75rem;
        }
        [data-testid="stMetric"] {
            padding: 0.75rem 0.9rem;
            border: 1px solid rgba(37, 99, 166, 0.16);
            border-radius: 0.65rem;
            background: rgba(248, 250, 252, 0.92);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(37, 99, 166, 0.14);
            border-radius: 0.6rem;
            overflow: hidden;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(105deg, var(--sa-blue), var(--sa-teal));
            border: 0;
        }
        .sa-section-note {
            padding: 0.75rem 0.9rem;
            border-left: 4px solid var(--sa-teal);
            border-radius: 0.35rem;
            background: rgba(15, 139, 141, 0.08);
        }
        .st-key-workflow_navigation [role="radiogroup"] {
            justify-content: center;
            gap: 0.35rem;
            padding: 0.35rem;
            margin: 0 auto 0.75rem;
            border: 1px solid #cbd8e6;
            border-radius: 0.75rem;
            background: #e7eef5;
        }
        .st-key-workflow_navigation label[data-baseweb="radio"] {
            justify-content: center;
            min-width: 7.25rem;
            padding: 0.38rem 0.65rem;
            margin: 0;
            border: 1px solid #cbd8e6;
            border-radius: 0.55rem;
            background: #f8fafc;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
        }
        .st-key-workflow_navigation label[data-baseweb="radio"] p {
            font-size: 0.84rem;
        }
        .st-key-workflow_navigation label[data-baseweb="radio"] > div:first-child {
            display: none;
        }
        .st-key-workflow_navigation label[data-baseweb="radio"]:has(input:checked) {
            color: white;
            border-color: transparent;
            background: linear-gradient(105deg, var(--sa-blue), var(--sa-teal));
            box-shadow: 0 0.25rem 0.7rem rgba(37, 99, 166, 0.22);
        }
        .st-key-workflow_navigation label[data-baseweb="radio"]:has(input:checked) p {
            color: white;
            font-weight: 700;
        }
        @media (max-width: 768px) {
            .sa-app-header {
                flex-wrap: wrap;
                align-items: flex-start;
                padding: 0.7rem 0.8rem;
            }
            .sa-app-header h1 {
                font-size: 1.3rem;
            }
            .sa-market-pill {
                font-size: 0.78rem;
            }
            .sa-hero-copy {
                padding: 0.35rem 0 0.5rem;
            }
            .sa-hero-copy h2 {
                font-size: 1.35rem;
            }
            [data-testid="stRadio"] [role="radiogroup"] {
                flex-wrap: wrap;
                row-gap: 0.35rem;
            }
            .st-key-workflow_navigation [role="radiogroup"] {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                width: 100%;
            }
            .st-key-workflow_navigation label[data-baseweb="radio"] {
                min-width: 0;
                width: 100%;
                padding-inline: 0.45rem;
            }
            [data-testid="stMetric"] {
                padding: 0.6rem 0.7rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_app_header() -> None:
    """Render the display-only application identity."""
    st.markdown(
        """
        <div class="sa-app-header">
          <div>
            <h1>Stock Analyser</h1>
            <p>Technical screening, transparent scoring, and local market insights</p>
          </div>
          <div class="sa-market-pill">India · NSE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def scroll_to_top() -> None:
    """Return the parent Streamlit page to the top after workflow navigation."""
    st.html(
        """
        <script>
        (() => {
          const scrollTargets = [
            document.querySelector('[data-testid="stMain"]'),
            document.querySelector('section.main'),
            document.querySelector('[data-testid="stAppViewContainer"]')
          ].filter(Boolean);
          const scroll = () => {
            window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
            scrollTargets.forEach((target) =>
              target.scrollTo({ top: 0, left: 0, behavior: 'auto' })
            );
          };
          window.requestAnimationFrame(() => window.requestAnimationFrame(scroll));
        })();
        </script>
        """,
        width="content",
        unsafe_allow_javascript=True,
    )
