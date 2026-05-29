"""Interactive demo: persona-driven sycophancy in LLM policy analysis.

Three views:
  - "What we found"  : precomputed charts from the experiment data.
  - "Try it yourself": live model call — pick a persona + question, see
                       the model's policy analysis and an automated
                       lean score. Side-by-side compares two personas
                       on the same question.
  - "Methodology"    : the experimental design and caveats.

Live mode is gated behind a password and a per-session call cap so the
self-funded API budget isn't drained. Set the password and API key as
secrets / env vars (see demo/README.md).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Import the shared topic config (single source of truth with the
# experiment scripts). The config lives in ../analysis.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "analysis"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow a local copy too

try:
    from sycophancy_configs import (  # type: ignore
        PERSONA_ORDER,
        TOPICS,
        build_judge_prompt,
        build_system_prompt,
    )
except ImportError:
    st.error(
        "Could not import sycophancy_configs. Ensure analysis/sycophancy_configs.py "
        "is on the path (deploy the repo, or copy the file into demo/)."
    )
    st.stop()

ANALYSIS_DIR = REPO_ROOT / "analysis"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="LLM Political Sycophancy", layout="wide")

# Live mode runs through OpenRouter (OpenAI-compatible), matching the
# provider used for the committed result data so the live numbers line up
# with the charts.
SUBJECT_MODEL = "anthropic/claude-haiku-4.5"
JUDGE_MODEL = "anthropic/claude-sonnet-4.5"
MAX_LIVE_CALLS_PER_SESSION = 24  # protects the self-funded budget

# Data files used by the "What we found" charts.
# Cross-model headline + immigration baseline are clean, committed runs.
# The L0 and healthcare files are produced by run_sycophancy.py once API
# credits are topped up; until then those charts show a "pending" note.
CROSS_MODEL_FILE = "persona_belief_pilot_rows.json"          # 6-model headline (clean)
IMM_BASELINE_FILE = "persona_belief_scaled_rows.json"        # Haiku 15Q baseline (clean)
IMM_L0_FILE = "sycophancy_immigration_l0_rows.json"          # pending credit top-up
HEALTHCARE_FILE = "sycophancy_healthcare_baseline_rows.json" # pending credit top-up

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_judge(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_RE.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Password gate
# ---------------------------------------------------------------------------

def _expected_password() -> str | None:
    # st.secrets first (HF Spaces / Streamlit Cloud), then env var.
    try:
        if "DEMO_PASSWORD" in st.secrets:
            return str(st.secrets["DEMO_PASSWORD"])
    except Exception:
        pass
    return os.environ.get("SYCOPHANCY_DEMO_PASSWORD")


def password_ok() -> bool:
    """Gate live mode. 'What we found' and 'Methodology' are always open."""
    expected = _expected_password()
    if not expected:
        # No password configured -> live mode disabled entirely (safe default).
        return False
    if st.session_state.get("authed"):
        return True
    with st.sidebar:
        st.markdown("**Live mode is password-protected**")
        entered = st.text_input("Access password", type="password", key="pw_input")
        if entered:
            if entered == expected:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


# ---------------------------------------------------------------------------
# Live API (OpenRouter, OpenAI-compatible) — only used in "Try it yourself"
# ---------------------------------------------------------------------------

def _api_key() -> str | None:
    try:
        if "OPENROUTER_API_KEY" in st.secrets:
            return str(st.secrets["OPENROUTER_API_KEY"])
    except Exception:
        pass
    return os.environ.get("OPENROUTER_API_KEY")


def _live_client():
    from openai import OpenAI

    key = _api_key()
    if not key:
        return None
    return OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")


def live_subject_call(client, system_prompt: str, user_prompt: str) -> str:
    msg = client.chat.completions.create(
        model=SUBJECT_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (msg.choices[0].message.content or "") if msg.choices else ""


def live_judge_call(client, judge_prompt: str) -> dict | None:
    msg = client.chat.completions.create(
        model=JUDGE_MODEL,
        max_tokens=320,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    text = (msg.choices[0].message.content or "") if msg.choices else ""
    return parse_judge(text)


def _budget_left() -> int:
    used = st.session_state.get("live_calls_used", 0)
    return MAX_LIVE_CALLS_PER_SESSION - used


def _charge(n: int) -> None:
    st.session_state["live_calls_used"] = st.session_state.get("live_calls_used", 0) + n


# ---------------------------------------------------------------------------
# Data loading for "What we found"
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_result(filename: str) -> pd.DataFrame | None:
    path = ANALYSIS_DIR / filename
    if not path.exists():
        return None
    rows = json.loads(path.read_text())
    recs = []
    for r in rows:
        js = r.get("judge_scores")
        if not js or "policy_lean" not in js:
            continue
        recs.append({
            "model": r.get("model", "haiku"),
            "persona_key": r["persona_key"],
            "persona_ordinal": r.get("persona_ordinal"),
            "policy_lean": js["policy_lean"],
            "evidence_balance": js.get("evidence_balance"),
            "persona_validation": js.get("persona_validation"),
        })
    return pd.DataFrame(recs) if recs else None


def persona_means(df: pd.DataFrame, model: str | None = None) -> pd.Series:
    sub = df if model is None else df[df["model"] == model]
    means = sub.groupby("persona_key")["policy_lean"].mean()
    ordered = [p for p in PERSONA_ORDER if p in means.index]
    return means.reindex(ordered)


# Human-readable axis labels, in the correct left -> right order. Using
# these (not the raw "left_strong" keys) fixes the alphabetical-sort bug
# in st.line_chart and reads better for a non-technical reviewer.
PERSONA_LABELS = {
    "left_strong": "Strongly progressive",
    "left_mild": "Lean progressive",
    "moderate": "Moderate",
    "right_mild": "Lean conservative",
    "right_strong": "Strongly conservative",
}
PERSONA_X_ORDER = [
    "Strongly progressive", "Lean progressive", "Moderate",
    "Lean conservative", "Strongly conservative",
]


def lean_chart(series_dict: dict[str, pd.Series], color_title: str) -> alt.LayerChart:
    """Build an Altair line chart with the x-axis explicitly ordered from
    strongly-progressive to strongly-conservative (Altair respects the
    `sort` order; st.line_chart does not). A dashed zero line marks a
    perfectly balanced response."""
    records = []
    for series_name, s in series_dict.items():
        for pkey, lean in s.items():
            if pkey == "unspecified" or pd.isna(lean):
                continue
            records.append({
                "User's stated identity": PERSONA_LABELS.get(pkey, pkey),
                color_title: series_name,
                "Policy lean": float(lean),
            })
    df = pd.DataFrame(records)
    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="#777", strokeDash=[4, 4])
        .encode(y="y:Q")
    )
    line = (
        alt.Chart(df)
        .mark_line(point=alt.OverlayMarkDef(size=70, filled=True), strokeWidth=3)
        .encode(
            x=alt.X(
                "User's stated identity:N",
                sort=PERSONA_X_ORDER,
                axis=alt.Axis(labelAngle=-25, title="User's stated political identity"),
            ),
            y=alt.Y(
                "Policy lean:Q",
                scale=alt.Scale(domain=[-10, 10]),
                axis=alt.Axis(title="Model's policy lean   (−10 … +10)"),
            ),
            color=alt.Color(
                f"{color_title}:N", title=color_title,
                scale=alt.Scale(scheme="tableau10"),
            ),
            tooltip=[color_title, "User's stated identity", "Policy lean"],
        )
    )
    return (
        (zero + line)
        .properties(height=440)
        .configure_view(stroke=None)
        .configure_axis(
            grid=True, gridColor="#1c2438", domainColor="#33405f",
            labelColor="#aab6cc", titleColor="#cdd8ec",
            labelFontSize=12, titleFontSize=12, titleFontWeight=600,
        )
        .configure_legend(
            labelColor="#c6d2e6", titleColor="#e0e8f6",
            labelFontSize=12, titleFontSize=12, orient="bottom",
        )
    )


# ---------------------------------------------------------------------------
# Self-funding notice
# ---------------------------------------------------------------------------

SELF_FUNDING_NOTICE = (
    "**This demo is self-funded by an independent research team.** Live "
    "model calls cost real money on our personal API budget. A handful of "
    "queries is plenty to see the effect — please don't run bulk or "
    "automated queries, which would exhaust the budget and take the demo "
    "offline. Thank you for being considerate."
)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def view_what_we_found() -> None:
    st.subheader("The question")
    st.markdown(
        "When someone uses an LLM as a civic-information source, does the "
        "model give them a stable, even-handed analysis — or does it tell "
        "them what their stated political identity suggests they want to "
        "hear?\n\n"
        "We ask a panel of language models to analyze neutrally-phrased "
        "policy questions, varying **only the user's stated political "
        "identity** in the system prompt. A separate judge model rates each "
        "response on a signed **policy-lean** scale from −10 to +10. If the "
        "model is even-handed, the rating should not depend on the user's "
        "identity."
    )

    # Load datasets used below.
    cross = load_result(CROSS_MODEL_FILE)
    base = load_result(IMM_BASELINE_FILE)
    l0 = load_result(IMM_L0_FILE)
    hc = load_result(HEALTHCARE_FILE)

    # --- Key findings band (computed from the data) ---
    st.subheader("Key findings")
    c1, c2, c3 = st.columns(3)
    if base is not None:
        bm = persona_means(base)
        swing = bm.get("left_strong", float("nan")) - bm.get("right_strong", float("nan"))
        c1.metric(
            "Identity-driven swing",
            f"{swing:.1f} pts",
            help="On a 20-point scale (−10 to +10). Difference in the model's "
                 "policy lean between a strongly-progressive and a "
                 "strongly-conservative user — same question, same model.",
        )
    if cross is not None:
        n_models = cross["model"].nunique()
        c2.metric(
            "Models affected",
            f"{n_models} of {n_models}",
            help="Every model tested shows the effect in the same direction.",
        )
    if base is not None and l0 is not None:
        bm = persona_means(base)
        lm = persona_means(l0)
        bswing = bm.get("left_strong") - bm.get("right_strong")
        lswing = lm.get("left_strong") - lm.get("right_strong")
        if bswing:
            c3.metric(
                "Reduction with a fairness instruction",
                f"{(1 - lswing / bswing) * 100:.0f}%",
                help="A single fairness instruction in the system prompt "
                     "roughly halves the effect — but does not eliminate it.",
            )

    st.divider()

    # --- Chart 1: cross-model ---
    st.subheader("Every model tracks the user's stated identity")
    if cross is not None:
        models = sorted(cross["model"].unique())
        st.altair_chart(
            lean_chart({m.split("/")[-1]: persona_means(cross, m) for m in models}, "Model"),
            width='stretch',
        )
        st.caption(
            "Immigration topic. Each line is one model; the x-axis is the "
            "user's stated identity. A **downward slope means the model leans "
            "toward the user's own position** (sycophancy). Every model shows "
            "it (per-model slope p < 10⁻⁷)."
        )
    else:
        st.info("Cross-model data not found.")

    st.divider()

    # --- Chart 2: baseline vs L0 mitigation ---
    st.subheader("A fairness instruction roughly halves the effect")
    if base is not None and l0 is not None:
        st.altair_chart(
            lean_chart(
                {"Baseline": persona_means(base),
                 "With fairness instruction": persona_means(l0)},
                "Condition",
            ),
            width='stretch',
        )
        st.caption(
            "Same model (Claude Haiku), same 15 immigration questions. Adding "
            "one fairness instruction to the system prompt flattens the slope "
            "by about half — the residual effect is still statistically "
            "significant, so prompting helps but is not a complete fix."
        )
    elif base is not None:
        st.info("L0 mitigation data not found.")

    st.divider()

    # --- Chart 3: cross-topic ---
    st.subheader("It generalizes across topics")
    if base is not None and hc is not None:
        st.altair_chart(
            lean_chart(
                {"Immigration": persona_means(base), "Healthcare": persona_means(hc)},
                "Topic",
            ),
            width='stretch',
        )
        st.caption(
            "The same persona ladder on two different policy domains. Both "
            "slope the same way; the effect is, if anything, slightly larger "
            "on healthcare. The bias is not specific to one topic."
        )
    elif base is not None:
        st.info("Healthcare cross-topic data not found.")

    st.divider()
    st.caption(
        "Method in brief: 6 personas × 15 questions × 3 repetitions per "
        "topic. Subject model rated by an independent judge model. The "
        "no-persona control (not shown) sits near zero, so the model's "
        "default analysis is balanced — the persona is what moves it. See "
        "the Methodology tab for full detail and caveats."
    )


def view_try_it(authed: bool) -> None:
    st.header("Try it yourself")
    st.markdown(SELF_FUNDING_NOTICE)

    if not authed:
        st.warning(
            "Live mode is password-protected (enter the password in the "
            "sidebar). The **What we found** and **Methodology** tabs are "
            "open to everyone."
        )
        return

    client = _live_client()
    if client is None:
        st.error("No OPENROUTER_API_KEY configured for live calls.")
        return

    left = _budget_left()
    st.caption(f"Live-call budget remaining this session: **{left} / "
               f"{MAX_LIVE_CALLS_PER_SESSION}** (each comparison uses ~4 calls).")
    if left <= 0:
        st.error("Session live-call budget exhausted. Reload to reset.")
        return

    topic_key = st.selectbox(
        "Topic", list(TOPICS.keys()),
        format_func=lambda k: TOPICS[k].label,
    )
    topic = TOPICS[topic_key]

    q_options = topic.questions
    q_idx = st.selectbox(
        "Question", range(len(q_options)),
        format_func=lambda i: q_options[i][1],
    )
    q_id, q_text = q_options[q_idx]

    persona_keys = [p for p in PERSONA_ORDER if p in topic.personas]
    col_a, col_b = st.columns(2)
    with col_a:
        pa = st.selectbox("Persona A", persona_keys,
                          index=persona_keys.index("left_strong") if "left_strong" in persona_keys else 0,
                          key="pa")
        st.caption(topic.personas[pa][1])
    with col_b:
        pb = st.selectbox("Persona B", persona_keys,
                          index=persona_keys.index("right_strong") if "right_strong" in persona_keys else 0,
                          key="pb")
        st.caption(topic.personas[pb][1])

    if st.button("Run side-by-side comparison", type="primary"):
        if _budget_left() < 4:
            st.error("Not enough budget left for a comparison (needs 4 calls).")
            return
        _charge(4)
        results = {}
        for label, pkey in (("A", pa), ("B", pb)):
            desc = topic.personas[pkey][1]
            sys_prompt = build_system_prompt(desc, l0=False)
            with st.spinner(f"Asking the model (persona {label})…"):
                resp = live_subject_call(client, sys_prompt, q_text)
            with st.spinner(f"Scoring response {label}…"):
                judge_prompt = build_judge_prompt(topic, desc, q_text, resp)
                scores = live_judge_call(client, judge_prompt)
            results[label] = (pkey, resp, scores)

        c1, c2 = st.columns(2)
        for col, label in ((c1, "A"), (c2, "B")):
            pkey, resp, scores = results[label]
            with col:
                st.markdown(f"**Persona {label}: `{pkey}`**")
                if scores and "policy_lean" in scores:
                    lean = scores["policy_lean"]
                    st.metric("Policy lean", f"{lean:+d}",
                              help="−10 = one pole, +10 = the other, 0 = balanced")
                    st.caption(
                        f"balance={scores.get('evidence_balance', '?')}, "
                        f"validation={scores.get('persona_validation', '?')}"
                    )
                st.markdown(resp)

        # Highlight the gap.
        sa = results["A"][2]
        sb = results["B"][2]
        if sa and sb and "policy_lean" in sa and "policy_lean" in sb:
            gap = sa["policy_lean"] - sb["policy_lean"]
            st.success(
                f"**Lean gap between the two personas: {gap:+d} points** on a "
                f"−10…+10 scale — same model, same question, only the user's "
                f"stated identity changed."
            )


def view_methodology() -> None:
    st.header("Methodology")
    st.markdown(
        """
**Design.** For each topic we define a ladder of user personas spanning the
political spectrum (strongly progressive → strongly conservative) plus an
*unspecified* control with no persona. Each persona is a one-sentence
biographical description with a stated policy belief, placed in the
**system prompt**. We then ask the model a set of neutrally-phrased policy
questions and request substantive analysis.

**Scoring.** A separate judge model (Claude Sonnet) rates each response on a
signed **policy-lean** axis (−10 … +10), plus evidence-balance and
persona-validation. A *negative slope* of policy-lean against the persona's
position = the model tilts toward what the user already believes
(sycophancy).

**Sample.** 6 personas × 15 questions × 3 reps per topic. Subject model:
Claude Haiku. Judge: Claude Sonnet. The cross-model chart additionally
sweeps GPT-4o-mini, Gemini Flash, Llama 3.3-70B, DeepSeek, and Qwen.

**Headline finding.** On immigration, the pooled slope is ≈ −2.3 with
p ≈ 10⁻⁵²; the same neutral question swings ≈ 10 points on the 20-point
lean scale between a strongly-progressive and a strongly-conservative
persona. The unspecified-persona control sits near 0, so the shift is
driven by the **stated user identity**, not the model's own default.

**Caveats.** Judge bias can affect absolute lean magnitudes (the
direction and slope are robust). The lean axis assumes a clean left/right
policy structure. The Haiku-judge variant was tested and rejected for the
signed axis (sign-flips ~27% of the time); Sonnet judges these runs.
        """
    )
    st.caption(
        "Independent, self-funded research. Full methodology, data, and "
        "writeups are in the project repository."
    )


# ---------------------------------------------------------------------------
# Visual identity (CSS + hero)
# ---------------------------------------------------------------------------

_CSS = """
<style>
.block-container { max-width: 1080px; padding-top: 1.4rem; padding-bottom: 3rem; }

.hero {
  background:
    radial-gradient(1100px 280px at 12% -30%, rgba(59,130,246,.20), transparent),
    radial-gradient(900px 280px at 98% -10%, rgba(244,114,182,.15), transparent),
    linear-gradient(135deg, #0f1626 0%, #131b2c 60%, #1c1422 100%);
  border: 1px solid #243049;
  border-radius: 18px;
  padding: 2.3rem 2.5rem;
  margin-bottom: 1.5rem;
  display: flex; flex-wrap: wrap; gap: 1.4rem;
  align-items: center; justify-content: space-between;
}
.hero-text { flex: 1 1 360px; }
.hero-eyebrow { letter-spacing:.16em; font-size:.72rem; font-weight:700;
  color:#7f9bc9; text-transform:uppercase; margin-bottom:.55rem; }
.hero-title { font-size:2.45rem; line-height:1.08; font-weight:800;
  color:#f3f7ff; margin:0 0 .7rem; }
.hero-sub { font-size:1.03rem; color:#c2cee2; max-width:560px; margin:0; }
.hero-art { flex: 0 0 auto; opacity:.97; }

[data-testid="stMetric"] {
  background:#121a2a; border:1px solid #273350; border-radius:14px;
  padding:1rem 1.15rem;
}
[data-testid="stMetricValue"] { color:#6fb1ff; font-weight:800; }

h3 { border-left:3px solid #3b82f6; padding-left:.6rem; margin-top:.3rem; }
[data-testid="stCaptionContainer"] { color:#9fb0cc; }
</style>
"""

# Inline SVG: six lines diverging downward by user identity — the visual
# signature of the finding (high lean for progressive users, low for
# conservative). No emojis; a real graphic.
_HERO_SVG = (
    '<svg width="330" height="168" viewBox="0 0 400 192" fill="none" '
    'xmlns="http://www.w3.org/2000/svg" role="img" '
    'aria-label="Model policy lean diverging downward by user identity">'
    '<line x1="30" y1="92" x2="380" y2="92" stroke="#46527a" stroke-width="1" stroke-dasharray="5 5"/>'
    '<polyline points="30,52 205,70 380,150" stroke="#5b8ff9" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>'
    '<polyline points="30,58 205,74 380,134" stroke="#34d39a" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>'
    '<polyline points="30,55 205,72 380,120" stroke="#f06595" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>'
    '<polyline points="30,62 205,78 380,108" stroke="#ff8787" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>'
    '<polyline points="30,60 205,80 380,99" stroke="#9775fa" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>'
    '<polyline points="30,64 205,82 380,93" stroke="#fcc419" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>'
    '<circle cx="380" cy="150" r="3.2" fill="#5b8ff9"/><circle cx="380" cy="134" r="3.2" fill="#34d39a"/>'
    '<circle cx="380" cy="120" r="3.2" fill="#f06595"/><circle cx="380" cy="108" r="3.2" fill="#ff8787"/>'
    '<circle cx="380" cy="99" r="3.2" fill="#9775fa"/><circle cx="380" cy="93" r="3.2" fill="#fcc419"/>'
    '<text x="30" y="184" fill="#8aa0c6" font-size="11" font-family="sans-serif">progressive user</text>'
    '<text x="286" y="184" fill="#8aa0c6" font-size="11" font-family="sans-serif">conservative user</text>'
    "</svg>"
)


def inject_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown(
        '<div class="hero">'
        '<div class="hero-text">'
        '<div class="hero-eyebrow">Civic AI Reliability · Independent Research</div>'
        '<h1 class="hero-title">Does an LLM tell you<br>what you want to hear?</h1>'
        '<p class="hero-sub">Measuring persona-driven political sycophancy across six '
        "frontier language models — how much a model tilts its policy analysis toward "
        "the user's stated political identity, and whether it can be mitigated.</p>"
        "</div>"
        f'<div class="hero-art">{_HERO_SVG}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    inject_style()
    render_hero()

    authed = password_ok()

    mode = st.sidebar.radio(
        "View", ["What we found", "Try it yourself", "Methodology"]
    )
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Live mode: " + ("unlocked" if authed else "locked")
    )

    if mode == "What we found":
        view_what_we_found()
    elif mode == "Try it yourself":
        view_try_it(authed)
    else:
        view_methodology()


if __name__ == "__main__":
    main()
