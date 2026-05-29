# Interactive demo — persona-driven political sycophancy

A Streamlit app that lets a grant reviewer *see* the finding: change the
user's stated political identity and watch the same model give a
materially different policy analysis to the same question.

## Three views

| View | Auth | What it does |
|---|---|---|
| **What we found** | open | Precomputed charts: cross-model headline, baseline vs L0-mitigation, immigration vs healthcare. |
| **Try it yourself** | password | Live call — pick two personas + a question, see both responses side-by-side with an automated lean score and the gap between them. |
| **Methodology** | open | Design, scoring, sample, caveats. |

## Run locally

```bash
cd demo
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...          # for live mode
export SYCOPHANCY_DEMO_PASSWORD=choose-one   # gates live mode
streamlit run app.py
```

The app imports topic configs from `../analysis/sycophancy_configs.py`
and reads precomputed results from `../analysis/sycophancy_*_rows.json`,
so run it from inside the repo (the full repo, not just `demo/`).

## Deploy (Hugging Face Spaces / Streamlit Community Cloud)

1. Point the Space/app at this repo with `demo/app.py` as the entrypoint.
2. Set secrets (do **not** commit them):
   - `ANTHROPIC_API_KEY` — the live-mode model key
   - `DEMO_PASSWORD` — the password you hand to grant reviewers
3. Make sure `analysis/sycophancy_configs.py` and the
   `analysis/sycophancy_*_rows.json` data files are present in the deploy
   (they ship with the repo).

On HF Spaces / Streamlit Cloud, secrets are read via `st.secrets`; locally
they fall back to environment variables.

## Budget protection (important — this is self-funded)

Live mode makes real Anthropic API calls on a personal budget. Three
guards are in place:

1. **Password gate** — only reviewers with `DEMO_PASSWORD` can run live
   calls. The chart and methodology views are open to everyone.
2. **Per-session call cap** — `MAX_LIVE_CALLS_PER_SESSION` (24) in
   `app.py`. Each side-by-side comparison uses ~4 calls.
3. **Self-funding notice** — shown on the live tab asking reviewers not
   to run bulk/automated queries.

If you expect heavy traffic, lower the per-session cap or disable live
mode (leave `ANTHROPIC_API_KEY` unset) and rely on the precomputed
charts alone.

## Note for reviewers

This is independent, self-funded research. The live demo is a courtesy —
please keep it to a handful of queries so the budget lasts for everyone.
Full data, scripts, and writeups are in the repository under `analysis/`.
