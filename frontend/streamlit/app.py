"""
LogiScan Streamlit Dashboard
Interactive web interface for logical fallacy detection and debate.
Provides real-time analysis visualization and logic health tracking.
"""

import time
from datetime import datetime

import plotly.graph_objects as go
import requests
import streamlit as st
from components.fallacy_breakdown import render_fallacy_breakdown
from highlighting import HIGHLIGHTING_CSS

# --- Page Configuration ---
st.set_page_config(
    page_title="LogiScan - Logical Fallacy Detector",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject Global Robust CSS & Keyboard Shortcuts
st.markdown(HIGHLIGHTING_CSS, unsafe_allow_html=True)
st.markdown(
    """
<script>
const doc = window.parent.document;

// Prevent Streamlit's default 'c' key handler from hijacking Ctrl+C (copy).
// Streamlit intercepts 'c' for "Clear caches" even when Ctrl is held.
doc.addEventListener('keydown', function(e) {
    // Allow native Ctrl+C to copy in textareas/inputs
    if (e.ctrlKey && e.key === 'c' && !e.shiftKey && !e.metaKey) {
        const tag = e.target.tagName;
        if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'IFRAME') {
            return; // Let native copy happen
        }
        e.stopPropagation();
        return;
    }

    // Ctrl+Shift+X to toggle "Skip Cache"
    if (e.ctrlKey && e.shiftKey && e.key === 'X') {
        e.preventDefault();
        const spans = doc.querySelectorAll('span');
        for (const span of spans) {
            if (span.innerText.includes('Skip Cache')) {
                span.click();
                break;
            }
        }
    }
}, {capture: true});
</script>
""",
    unsafe_allow_html=True,
)

# --- Constants ---
API_BASE_URL = "http://localhost:8000/api/v1"

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/brain.png", width=80)
    st.markdown("## LogiScan")
    st.markdown("*Sovereign Logic Analysis*")
    st.markdown("---")

    # Navigation
    page = st.radio(
        "Navigation",
        ["Analysis", "Debate", "Logic Health", "System Status"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    LogiScan uses a 4-stage neuro-symbolic pipeline
    to detect logical fallacies in text.

    **Pipeline:**
    1. Gatekeeper (DistilBERT)
    2. Coarse Classification (BERT-Large)
    3. Fine-Grained Detection (RoBERTa-Large)
    4. Formal Verification (Z3 + LLM)
    """)

    st.markdown("---")
    st.markdown(f"*Session: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    if st.sidebar.button("Reset All State", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# --- Helper Functions ---
def call_analyze_api(text: str, skip_cache: bool = False, localize: bool = False, fast_track: bool = False) -> dict:
    """Call the LogiScan analyze endpoint."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/analyze",
            json={
                "text": text,
                "skip_cache": skip_cache,
                "localize": localize,
                "fast_track": fast_track,
                "include_explanations": not fast_track,
            },
            timeout=300,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to LogiScan backend. Ensure the server is running.")
        st.info(
            "Try running: `export PYTHONPATH=$PYTHONPATH:$(pwd) && venv/bin/python3 -m backend.app.main` in your terminal."
        )
        return None
    except requests.exceptions.Timeout:
        st.error("Request timed out. The text may be too long.")
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


def call_debate_api(text: str, session_id: str = None) -> dict:
    """Call the debate endpoint."""
    try:
        payload = {"user_input": text}
        if session_id:
            payload["session_id"] = session_id

        response = requests.post(
            f"{API_BASE_URL}/debate",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Debate error: {str(e)}")
        return None


def get_health_status() -> dict:
    """Get system health status."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.json()
    except Exception:
        return {"status": "unknown"}


def get_logic_history() -> list:
    """Fetch historical logic scores."""
    try:
        response = requests.get(f"{API_BASE_URL}/history", timeout=5)
        return response.json()
    except Exception:
        return []


# --- Page: Analysis Dashboard ---
if page == "Analysis":
    st.header("Logical Fallacy Analysis")
    st.markdown("Enter text to analyze for logical fallacies using the 4-stage pipeline.")

    col1, col2 = st.columns([3, 1])

    with col1:
        text_input = st.text_area(
            "Input Text",
            height=150,
            placeholder="Enter an argument or statement to analyze...\n\nExample: 'If it rains, the ground gets wet. The ground is wet, therefore it rained.'",
            key="analysis_input",
        )

    with col2:
        st.markdown("### Options")
        skip_cache = st.checkbox("Skip Cache", value=True, help="Force fresh inference (Recommended for XAI)")

        # Initialize session state defaults
        if "localize" not in st.session_state:
            st.session_state.localize = False
        if "fast_track" not in st.session_state:
            st.session_state.fast_track = False

        localize = st.checkbox(
            " Localize",
            value=st.session_state.localize,
            help="Force all processing to run locally. No external API calls.",
        )
        fast_track = st.checkbox(
            " Fast Track",
            value=st.session_state.fast_track,
            help="Skip LLM-heavy stages (structural analysis, synthesis, reranking) for faster results.",
        )
        if fast_track:
            st.caption("Fast Track skips LLM explanations; all fallacies are still detected.")

        # Persist to session state on change
        if localize != st.session_state.localize:
            st.session_state.localize = localize
        if fast_track != st.session_state.fast_track:
            st.session_state.fast_track = fast_track

        analyze_btn = st.button("Analyze", type="primary", use_container_width=True)

    if analyze_btn and text_input:
        with st.spinner("Running LogiScan pipeline..."):
            start_time = time.time()
            result = call_analyze_api(text_input, skip_cache=skip_cache, localize=localize, fast_track=fast_track)
            elapsed = time.time() - start_time
            if result:
                st.session_state.analysis_result = result
                st.session_state.persisted_input = text_input
                st.session_state.analysis_elapsed = elapsed

    if "analysis_result" in st.session_state:
        result = st.session_state.analysis_result
        text_input = st.session_state.persisted_input
        elapsed = st.session_state.analysis_elapsed

        st.success(f"Analysis complete in {elapsed:.2f}s {'(cached)' if result.get('cached') else ''}")

        # compact 5-column metrics row
        cols = st.columns(5)
        c1, c2, c3, c4, c5 = cols

        c1.metric("Logic", f"{result.get('logic_score', 0):.2f}")
        c2.metric("Salience", f"{result.get('salience_score', 0):.2f}")

        latency_s = result.get("total_latency_ms", 0) / 1000
        latency_label = f"{latency_s:.0f}s" if latency_s >= 1 else f"{result.get('total_latency_ms', 0):.0f}ms"
        c3.metric("Latency", latency_label)

        z3 = result.get("z3_status", "skipped")
        z3_label = {"unsat": "Valid", "sat": "Invalid", "skipped": "\u2014", "unknown": "?"}.get(z3, z3)
        c4.metric("Z3", z3_label)

        c5.metric("Fallacies", len(result.get("fallacies", [])))

        st.markdown(f"**Category:** {result.get('coarse_category') or 'N/A'}")

        st.markdown("---")

        # --- MERGED INTERACTIVE BREAKDOWN + XAI ---
        st.markdown("### Interactive Fallacy Breakdown")
        salient = result.get("salient_tokens", [])
        render_fallacy_breakdown(text_input, result, salient_tokens=salient)

        # Pipeline Metadata (always visible)
        st.markdown("---")
        st.markdown("### Pipeline Metadata")
        with st.expander("Latency Breakdown"):
            for stage, lat in result.get("stage_latencies", {}).items():
                st.text(f"{stage:.<20} {lat:>6.1f}ms")
        with st.expander("System / Device Info"):
            st.json(result.get("device_info", {}))
        with st.expander("Raw API Response"):
            st.json(result)

# --- Page: Debate Mode ---
elif page == "Debate":
    st.markdown("## RL-Powered Debate")
    st.markdown("Engage in a logical debate with the AI. It learns and adapts to improve discourse quality.")

    # Initialize session state
    if "debate_session" not in st.session_state:
        st.session_state.debate_session = None
        st.session_state.debate_history = []
        st.session_state.debate_turn = 0

    # Display debate history
    for msg in st.session_state.debate_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.write(msg["response"])
                st.caption(f"Action: {msg.get('action', 'N/A')} | Logic Score: {msg.get('logic_score', 0):.2f}")

    # User input
    user_input = st.chat_input("Your argument or response...")

    if user_input:
        # Add user message
        st.session_state.debate_history.append({"role": "user", "content": user_input})

        with st.spinner("Analyzing and responding..."):
            result = call_debate_api(
                text=user_input,
                session_id=st.session_state.debate_session,
            )

        if result:
            st.session_state.debate_session = result.get("session_id")
            assistant_msg = {
                "role": "assistant",
                "response": result.get("agent_response", ""),
                "action": result.get("agent_action", ""),
                "logic_score": result.get("logic_score", 0),
                "fallacies": result.get("detected_fallacies", []),
            }
            st.session_state.debate_history.append(assistant_msg)
            st.session_state.debate_turn = result.get("turn_number", 0)
            st.rerun()

# --- Page: Logic Health ---
elif page == "Logic Health":
    st.header("Logic Health Monitor")

    history = get_logic_history()

    if not history:
        st.info("No analysis history found. Start analyzing text to track your logic health!")
    else:
        st.success("Reasoning improvement tracked based on your session history.")

        # Prepare data for plotting
        dates = [datetime.fromisoformat(h["timestamp"]).strftime("%m-%d %H:%M") for h in history]
        scores = [h["score"] for h in history]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=scores,
                mode="lines+markers",
                name="Logic Score",
                line=dict(color="#667eea", width=3),
                marker=dict(size=10),
            )
        )
        fig.update_layout(
            title="Your Logic Health Trend",
            yaxis=dict(range=[0, 1], title="Logic Score"),
            xaxis=dict(title="Analysis Time"),
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Stats summary
        avg_score = sum(scores) / len(scores)
        st.metric("Average Logic Score", f"{avg_score:.2f}")

# --- Page: System Status ---
elif page == "System Status":
    st.header("System Status")
    health = get_health_status()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"### Status: {'HEALTHY' if health.get('status') == 'healthy' else 'ERROR'}")
    with col2:
        st.markdown(f"### Device: `{health.get('device', {}).get('device_string', 'N/A')}`")
    with col3:
        st.markdown(f"### Cache: {'CONNECTED' if health.get('cache', {}).get('connected') else 'DISCONNECTED'}")
    st.markdown("---")
    st.json(health)

# --- Footer ---
st.markdown("---")
st.caption(f"LogiScan v1.2.0-rc1 | Neuro-Symbolic Fallacy Detection | {datetime.now().year}")
