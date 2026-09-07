"""
LogiScan - Ultra-Robust QuillBot-Style Annotations
Strict HTML/CSS rendering with Session State support.
"""

import html
import os
import re
import sys
from typing import Any

# Ensure backend is in path for shared catalog
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.app.services.fallacy_catalog import get_definition

MAX_ANNOTATIONS = 20

# ============================================================
# FALLACY COLOR PALETTE (Thematic Grouping)
# ============================================================
FALLACY_COLORS = {
    # --- Informal (Relevance) - Reds/Oranges ---
    "ad_hominem": ("#e74c3c", "rgba(231, 76, 60, 0.2)", "#c0392b"),
    "straw_man": ("#e67e22", "rgba(230, 126, 34, 0.2)", "#d35400"),
    "red_herring": ("#1abc9c", "rgba(26, 188, 156, 0.2)", "#148f77"),
    "tu_quoque": ("#f39c12", "rgba(243, 156, 18, 0.2)", "#d68910"),
    "tu_quoque_contextual": ("#f39c12", "rgba(243, 156, 18, 0.2)", "#d68910"),
    "genetic_fallacy": ("#e74c3c", "rgba(231, 76, 60, 0.2)", "#c0392b"),
    "moving_goalposts": ("#e67e22", "rgba(230, 126, 34, 0.2)", "#d35400"),
    # --- Informal (Presumption) - Yellows/Pinks ---
    "false_cause": ("#f39c12", "rgba(243, 156, 18, 0.2)", "#d68910"),
    "hasty_generalization": ("#f39c12", "rgba(243, 156, 18, 0.2)", "#d68910"),
    "slippery_slope": ("#9b59b6", "rgba(155, 89, 182, 0.2)", "#7d3c98"),
    "begging_the_question": ("#7f8c8d", "rgba(127, 140, 141, 0.2)", "#5d6d7e"),
    "no_true_scotsman": ("#ec4899", "rgba(236, 72, 153, 0.2)", "#be185d"),
    "composition": ("#ec4899", "rgba(236, 72, 153, 0.2)", "#be185d"),
    "division": ("#ec4899", "rgba(236, 72, 153, 0.2)", "#be185d"),
    "complex_question": ("#6b7280", "rgba(107, 114, 128, 0.2)", "#374151"),
    # --- Informal (Ambiguity/Nature) - Greens ---
    "equivocation": ("#2ecc71", "rgba(46, 204, 113, 0.2)", "#1e8449"),
    "amphiboly": ("#2ecc71", "rgba(46, 204, 113, 0.2)", "#1e8449"),
    "accent": ("#2ecc71", "rgba(46, 204, 113, 0.2)", "#1e8449"),
    "appeal_to_nature": ("#27ae60", "rgba(39, 174, 96, 0.2)", "#1e8449"),
    "appeal_to_tradition": ("#27ae60", "rgba(39, 174, 96, 0.2)", "#1e8449"),
    # --- Formal Fallacies - Blues/Dark Reds ---
    "false_dilemma": ("#f39c12", "rgba(243, 156, 18, 0.2)", "#d68910"),
    "affirming_consequent": ("#c0392b", "rgba(192, 57, 43, 0.2)", "#922b21"),
    "denying_antecedent": ("#c0392b", "rgba(192, 57, 43, 0.2)", "#922b21"),
    "undistributed_middle": ("#c0392b", "rgba(192, 57, 43, 0.2)", "#922b21"),
    "illicit_major": ("#c0392b", "rgba(192, 57, 43, 0.2)", "#922b21"),
    "illicit_minor": ("#c0392b", "rgba(192, 57, 43, 0.2)", "#922b21"),
    "exclusive_premises": ("#c0392b", "rgba(192, 57, 43, 0.2)", "#922b21"),
    "existential_fallacy": ("#c0392b", "rgba(192, 57, 43, 0.2)", "#922b21"),
    # --- Appeals/Rhetorical - Purples/Blues ---
    "appeal_to_emotion": ("#e74c3c", "rgba(231, 76, 60, 0.2)", "#c0392b"),
    "appeal_to_authority": ("#8e44ad", "rgba(142, 68, 173, 0.2)", "#6c3483"),
    "bandwagon": ("#3498db", "rgba(52, 152, 219, 0.2)", "#2471a3"),
    "factual_statement": ("#3b82f6", "rgba(59, 130, 246, 0.1)", "#1d4ed8"),
    "valid_reasoning": ("#10b981", "rgba(16, 185, 129, 0.1)", "#047857"),
    "default": ("#e74c3c", "rgba(231, 76, 60, 0.2)", "#c0392b"),
}


def get_fallacy_color(fallacy: str) -> tuple:
    key = fallacy.lower().replace(" ", "_")
    return FALLACY_COLORS.get(key, FALLACY_COLORS["default"])


def _conf_badge(conf: float, fallacy_label: str) -> str:
    """Categorical confidence tier with explanatory tooltip."""
    if conf >= 0.80:
        tier, bg = "High confidence", "rgba(16,185,129,0.12)"
        color = "#065f46"
    elif conf >= 0.50:
        tier, bg = "Moderate confidence", "rgba(217,119,6,0.12)"
        color = "#92400e"
    else:
        tier, bg = "Low confidence", "rgba(107,114,128,0.12)"
        color = "#374151"

    pct = f"{conf:.0%}"
    title_attr = f"The model is {pct} confident this phrase contains a {fallacy_label} fallacy."
    return (
        f'<span class="ls-card-badge" '
        f'style="background:{bg};color:{color};" '
        f'title="{html.escape(title_attr)}">'
        f"{tier} · {pct}"
        f"</span>"
    )


def render_editor(text: str, fallacies: list[dict[str, Any]], salient_tokens: list[dict[str, Any]] = None) -> str:
    """
    Final Ultra-Robust Renderer.
    Handles arbitrary nesting by auto-closing and re-opening tags to maintain valid HTML.
    """
    if not text:
        return ""

    # Cap annotations to prevent malformed HTML from overwhelming the renderer
    sorted_fallacies = sorted(
        (f for f in (fallacies or []) if f.get("confidence", 0) >= 0.45),
        key=lambda f: f.get("confidence", 0),
        reverse=True,
    )[:MAX_ANNOTATIONS]

    text_len = len(text)
    events = []

    # 1. Collect Events
    for i, f in enumerate(sorted_fallacies):
        s_start, s_end = f.get("sentence_start"), f.get("sentence_end")
        if s_start is not None and s_end is not None and 0 <= s_start < s_end <= text_len:
            events.append({"idx": s_start, "type": "S_START", "data": f})
            events.append({"idx": s_end, "type": "S_END"})

        for s in f.get("spans", []):
            t_start, t_end = s.get("start"), s.get("end")
            if t_start is not None and t_end is not None and 0 <= t_start < t_end <= text_len:
                accent, bg, dark = get_fallacy_color(f.get("type", "default"))
                meta = {
                    "label": f.get("label", "Issue"),
                    "conf": f.get("confidence", 0.5),
                    "type": f.get("type", "default"),
                    "expl": f.get("explanation", "Reasoning error."),
                    "saliency": s.get("saliency", 0.5),
                    "sentence_id": i,
                    "accent": accent,
                    "bg": bg,
                }
                events.append({"idx": t_start, "type": "T_START", "meta": meta})
                events.append({"idx": t_end, "type": "T_END"})

    # Sort: Index > Type Priority (ENDs before STARTs)
    priority = {"T_END": 0, "S_END": 1, "S_START": 2, "T_START": 3}
    events.sort(key=lambda x: (x["idx"], priority[x["type"]]))

    # 3. ASSEMBLY (Nesting-Aware Stack)
    html_parts = ['<div class="ls-editor-container">']
    last_idx = 0
    # active_tags stores tuples of (type, meta_for_restart)
    active_tags = []

    # Track which fallacy-sentence pairs have already rendered a card
    rendered_cards = set()

    for e in events:
        idx = e["idx"]
        etype = e["type"]

        html_parts.append(html.escape(text[last_idx:idx]))

        if etype == "S_START":
            html_parts.append('<span class="ls-sentence-hl">')
            active_tags.append(("S", None))
        elif etype == "T_START":
            m = e["meta"]
            card_key = f"{m['type']}_{m.get('sentence_id', 0)}"  # Simple key

            definition = get_definition(m["type"], "short")
            # CLAMP SALIENCY
            op = max(0, min(10, int(m.get("saliency", 0.5) * 10)))

            html_parts.append('<span class="ls-trigger-wrapper">')

            if card_key not in rendered_cards:
                html_parts.append(
                    f'<span class="ls-hover-card" style="--ls-card-accent: {m["accent"]};">'
                    f'<span class="ls-card-header">'
                    f'<b class="ls-card-title">{html.escape(m["label"])}</b>'
                    f"{_conf_badge(m['conf'], m['label'])}"
                    f"</span>"
                    f'<i class="ls-card-def">{html.escape(definition)}</i>'
                    f'<span class="ls-card-expl">{html.escape(m["expl"])}</span>'
                    f"</span>"
                )
                rendered_cards.add(card_key)

            html_parts.append(f'<span class="ls-trigger-hl" style="--ls-bg: {m["bg"]}; --ls-border: {m["accent"]};">')
            active_tags.append(("T", (m, op)))

        elif etype in ("S_END", "T_END"):
            target_type = "S" if etype == "S_END" else "T"

            # Find the tag in the stack
            idx_in_stack = -1
            for i in range(len(active_tags) - 1, -1, -1):
                if active_tags[i][0] == target_type:
                    idx_in_stack = i
                    break

            if idx_in_stack != -1:
                # 1. Close all tags above the target to maintain valid HTML
                tags_to_reopen = []
                while len(active_tags) > idx_in_stack + 1:
                    tag_type, meta = active_tags.pop()
                    if tag_type == "T":
                        html_parts.append("</span></span>")
                    else:
                        html_parts.append("</span>")
                    tags_to_reopen.append((tag_type, meta))

                # 2. Close the target tag
                tag_type, _ = active_tags.pop()
                if tag_type == "T":
                    html_parts.append("</span></span>")
                else:
                    html_parts.append("</span>")

                # 3. Re-open the tags we temporarily closed (in correct order)
                for tag_type, meta in reversed(tags_to_reopen):
                    if tag_type == "S":
                        html_parts.append('<span class="ls-sentence-hl">')
                    else:
                        m, op = meta
                        html_parts.append('<span class="ls-trigger-wrapper">')
                        # Note: We don't re-render the hover card on a split span
                        # to avoid duplicate tooltips in the DOM.
                        html_parts.append(
                            f'<span class="ls-trigger-hl" style="--ls-bg: {m["bg"]}; --ls-border: {m["accent"]};">'
                        )
                    active_tags.append((tag_type, meta))

        last_idx = idx

    html_parts.append(html.escape(text[last_idx:]))

    # Final safety close
    while active_tags:
        tag_type, _ = active_tags.pop()
        if tag_type == "T":
            html_parts.append("</span></span>")
        else:
            html_parts.append("</span>")

    html_parts.append("</div>")
    result = "".join(html_parts)

    # Tag balance verification — if mismatched, return plain escaped text
    open_spans = len(re.findall(r"<span(?:\s|>)", result))
    close_spans = result.count("</span>")
    if open_spans != close_spans:
        return f'<div class="ls-editor-container">{html.escape(text)}</div>'

    return result


def render_fallacy_card(fallacy: str, confidence: float) -> str:
    accent, _, _ = get_fallacy_color(fallacy)
    conf_label = "High" if confidence > 0.8 else "Medium" if confidence > 0.5 else "Low"
    return f"""
    <div style="border-left: 4px solid {accent}; background: var(--background-color, #ffffff); color: var(--text-color, #111827); padding: 12px; border-radius: 8px; border: 1px solid var(--secondary-background-color, #e5e7eb); margin-bottom: 8px;">
        <b style="color: {accent}; font-size: 0.85rem;">{fallacy.replace("_", " ").title()}</b>
        <span style="font-size: 0.7rem; float: right; opacity: 0.7;">{conf_label}</span>
    </div>
    """


HIGHLIGHTING_CSS = """
<style>
    .ls-editor-container {
        font-family: var(--font), 'Inter', sans-serif !important;
        font-size: 1.15rem !important;
        line-height: 2.1 !important;
        color: var(--text-color, #1e293b) !important;
        background: var(--background-color, #ffffff) !important;
        padding: 2.5rem !important;
        border-radius: 16px !important;
        border: 1px solid var(--secondary-background-color, #e2e8f0) !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        white-space: pre-wrap !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
    }

    .ls-sentence-hl {
        background-color: rgba(59, 130, 246, 0.07) !important;
        border-radius: 4px !important;
        padding: 4px 0 !important;
    }

    .ls-trigger-wrapper {
        position: relative !important;
        display: inline !important;
        cursor: help !important;
    }

    .ls-trigger-hl {
        border-bottom: 2px solid var(--ls-border, #d97706) !important;
        background-color: var(--ls-bg, rgba(245, 158, 11, 0.2)) !important;
        font-weight: 600 !important;
        transition: background-color 0.1s ease !important;
        display: inline !important;
    }

    .ls-trigger-wrapper:hover .ls-trigger-hl {
        background-color: var(--ls-border) !important;
        color: white !important;
    }

    .ls-hover-card {
        visibility: hidden !important;
        position: absolute !important;
        bottom: calc(100% + 6px) !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 320px !important;
        max-width: min(320px, 85vw) !important;
        background: var(--background-color, #ffffff) !important;
        color: var(--text-color, #1e293b) !important;
        padding: 1.25rem !important;
        border-radius: 12px !important;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2) !important;
        border: 1px solid var(--secondary-background-color, #e2e8f0) !important;
        z-index: 1001 !important;
        opacity: 0 !important;
        transition: opacity 0.15s ease-in-out !important;
        pointer-events: none !important;
        display: block !important;
        line-height: 1.5 !important;
        text-align: left !important;
    }

    /* Invisible hover bridge to prevent flicker */
    .ls-hover-card::before {
        content: "" !important;
        position: absolute !important;
        top: 100% !important;
        left: 0 !important;
        width: 100% !important;
        height: 10px !important;
        background: transparent !important;
    }

    /* Two-tier pointer arrow with border */
    .ls-hover-card::after, .ls-hover-card-arrow-border {
        content: "" !important;
        position: absolute !important;
        top: 100% !important;
        left: 50% !important;
        margin-left: -8px !important;
        border-width: 8px !important;
        border-style: solid !important;
    }
    /* Fill */
    .ls-hover-card::after {
        border-color: var(--background-color, #ffffff) transparent transparent transparent !important;
        z-index: 2 !important;
    }
    /* Border triangle */
    .ls-hover-card-arrow-border {
        margin-top: 1px !important;
        border-color: var(--secondary-background-color, #e2e8f0) transparent transparent transparent !important;
        z-index: 1 !important;
    }

    .ls-trigger-wrapper:hover .ls-hover-card,
    .ls-hover-card:hover {
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
    }

    .ls-card-header { display: flex !important; justify-content: space-between !important; align-items: center !important; margin-bottom: 8px !important; }
    .ls-card-title { font-size: 0.9rem !important; text-transform: uppercase !important; color: var(--ls-card-accent, #d97706) !important; font-weight: 800 !important; }
    .ls-card-badge { font-size: 0.7rem !important; background: rgba(217, 119, 6, 0.1) !important; color: #d97706 !important; padding: 2px 8px !important; border-radius: 12px !important; }
    .ls-card-def { display: block !important; font-size: 0.85rem !important; color: var(--text-color, #1e293b) !important; opacity: 0.7 !important; margin-bottom: 8px !important; font-style: italic !important; }
    .ls-card-expl { display: block !important; font-size: 0.95rem !important; border-top: 1px solid var(--secondary-background-color, #f1f5f9) !important; padding-top: 8px !important; }
</style>
"""
