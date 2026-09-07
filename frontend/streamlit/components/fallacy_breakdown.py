"""
LogiScan - Robust Fallacy Breakdown Component
Uses direct index-based search to guarantee highlights appear even with whitespace issues.
"""

import html

import streamlit as st
from highlighting import _conf_badge, get_definition, get_fallacy_color, render_editor


def render_fallacy_breakdown(text: str, result: dict, salient_tokens: list = None):
    """Renders the interactive split-pane view with robust highlighting."""
    fallacies = result.get("fallacies", [])
    annotations = result.get("annotations", [])  # From orchestrator

    if not fallacies:
        st.success("No logical fallacies detected.")
        st.markdown(f'<div class="fb-text-container">{html.escape(text)}</div>', unsafe_allow_html=True)
        return

    # 1. Use the unified render_editor to generate the text container HTML
    # We wrap it in our specific fb-text-container class
    editor_html = render_editor(text, annotations, salient_tokens)
    html_output = f'<div class="fb-text-container-wrapper">{editor_html}</div>'

    # 2. Sidebar Cards
    sidebar_html = ""
    # We prioritize showing all unique detected fallacies from the fine labels
    # but use the detailed 'fallacies' list for the cards.
    for i, f in enumerate(fallacies):
        # f["name"] is the machine name, f["quote"] is the trigger text
        # If confidence is missing, use a default
        conf = f.get("confidence", 0.0)
        accent, _, _ = get_fallacy_color(f["name"])
        badge_html = _conf_badge(conf, f["name"].replace("_", " ").title())
        explanation = get_definition(f["name"], "extended")

        sidebar_html += (
            f'<div class="fb-card" id="ls-card-{i}" style="border-left-color:{accent} !important;">'
            f'<div class="fb-card-title" style="color:{accent} !important;">'
            f"{f['name'].replace('_', ' ').title()}"
            f"{badge_html}"
            f"</div>"
            f'<div class="fb-card-expl"><b>Quote:</b> "{html.escape(f["quote"])}"<br><br>{html.escape(explanation)}</div>'
            f"</div>"
        )

    # 3. Inject Styles & JS
    st.markdown(
        f"""
<style>
.fb-container {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1.5rem;
    font-family: 'Inter', sans-serif;
    width: 100%;
    max-width: 100%;
}}

.fb-container > * {{
    min-width: 0;
    max-width: 100%;
    width: 100%;
    overflow-wrap: anywhere;
    word-break: break-word;
    box-sizing: border-box;
}}

.fb-text-container-wrapper {{
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: break-word;
}}

/* Mobile Responsiveness */
@media (max-width: 768px) {{
    .fb-container {{
        grid-template-columns: 1fr;
    }}
    .fb-sidebar {{
        order: 2;
    }}
}}

.fb-text-container-wrapper .ls-editor-container {{
    border: 1px solid var(--secondary-background-color) !important;
    box-shadow: none !important;
    padding: 1.5rem !important;
}}
.fb-sidebar {{
    min-width: 0;
    overflow-wrap: anywhere;
    word-break: break-word;
}}
.fb-card {{ background: var(--background-color); color: var(--text-color); border-radius: 12px; padding: 1.25rem; border: 1px solid var(--secondary-background-color); border-left: 6px solid #cbd5e1; margin-bottom: 1rem; transition: all 0.2s; max-width: 100%; box-sizing: border-box; }}
.fb-card.active {{ transform: translateX(-5px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); background: var(--secondary-background-color); border-left-width: 10px; }}
.fb-card-title {{ font-weight: 900; font-size: 0.9rem; text-transform: uppercase; display: flex; justify-content: space-between; margin-bottom: 0.5rem; }}
.fb-card-conf {{ font-size: 0.65rem; padding: 2px 8px; border-radius: 10px; }}
.fb-card-expl {{ font-size: 0.95rem; line-height: 1.4; opacity: 0.8; overflow-wrap: anywhere; word-break: break-word; }}
</style>
<div class="fb-container">
    <div>{html_output}</div>
    <div class="fb-sidebar">{sidebar_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )
