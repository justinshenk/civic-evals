# Common dev targets. Soft dependency — every recipe is a thin wrapper
# around `uv run …` or `pnpm …` that you can also paste into a shell
# directly. The justfile exists so mentees don't have to keep the README
# Quickstart open in a second tab; nothing in CI depends on `just`.
#
# Install:  brew install just     (or  cargo install just)
# Discover: `just` with no args lists every recipe.

# Default subject for `just eval` / `just rollup` runs. Override on the
# command line: `just eval voting_access anthropic/claude-sonnet-4-6`.
model := "anthropic/claude-haiku-4-5"

# Show the recipe list and short docs.
default:
    @just --list --unsorted

# pytest — schema validation, scorer fixtures, smoke. No API spend.
smoke:
    uv run pytest

# ruff lint over src/ analysis/ tests/.
lint:
    uv run ruff check src/ analysis/ tests/

# ruff format + lint --fix in place.
fix:
    uv run ruff check --fix src/ analysis/ tests/
    uv run ruff format src/ analysis/ tests/

# Run a single eval. Defaults to voting_access on Haiku; override either:
#   just eval policy_impact_personalization
#   just eval voting_access anthropic/claude-sonnet-4-6
#   just eval fermi_civic_estimation anthropic/claude-haiku-4-5 5
eval eval_name="voting_access" model_id=model limit="":
    uv run inspect eval evals/{{eval_name}}/eval.py \
        --model {{model_id}} \
        --log-dir logs/ \
        {{ if limit == "" { "" } else { "--limit " + limit } }}

# Run every eval against the given model (or default). Useful before a
# rollup regenerate. Skips with-search variants — those cost money and
# are explicitly opt-in (see `just eval-with-search`).
eval-all model_id=model limit="":
    @for e in evals/*/eval.py; do \
        echo "→ $e"; \
        uv run inspect eval "$e" --model {{model_id}} --log-dir logs/ \
            {{ if limit == "" { "" } else { "--limit " + limit } }} || exit 1; \
    done

# Run search-enabled fermi variant (paired with the no-search baseline
# so the site can render the delta). Costs more than the baseline; opt-in.
eval-with-search model_id=model limit="":
    uv run inspect eval evals/fermi_civic_estimation/eval_with_search.py \
        --model {{model_id}} --log-dir logs/ \
        {{ if limit == "" { "" } else { "--limit " + limit } }}

# Regenerate site/public/data/rollup.json from logs/. Site reads this
# at build time; commit it after running.
rollup:
    uv run python analysis/rollup.py logs/ --format json -o site/public/data/rollup.json

# Print the failure markdown table — paste into a PR body or Slack.
failures rollup_path="site/public/data/rollup.json":
    uv run python analysis/failures.py {{rollup_path}}

# Print the per-(eval, model) token usage and cost report.
usage rollup_path="site/public/data/rollup.json":
    uv run python analysis/usage.py {{rollup_path}}

# Diff two rollup.json files — markdown summary of mean shifts.
# Useful in PRs that regenerate the rollup so the diff isn't a wall of
# JSON.  Threshold defaults to 0.02 (2 percentage points of mean score).
diff old new threshold="0.02":
    uv run python analysis/diff_rollups.py {{old}} {{new}} --threshold {{threshold}}

# Slack summary preview (no webhook needed; prints to stdout).
slack rollup_path="site/public/data/rollup.json":
    uv run python analysis/slack_summary.py {{rollup_path}} --print

# Start the Next.js dev server in site/. Site reads rollup.json from disk.
site:
    cd site && pnpm dev

# Production build — what Vercel runs. Catches client/server boundary
# issues that `pnpm dev` will happily live with.
site-build:
    cd site && pnpm build

# pnpm install (only needed once after a fresh checkout).
site-install:
    cd site && pnpm install

# uv sync — Python deps. First-time setup.
sync:
    uv sync
