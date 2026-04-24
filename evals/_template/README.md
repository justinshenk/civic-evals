# _template — copy this folder to start a new eval

## How to use

1. Copy this folder: `cp -r evals/_template evals/my_domain`.
2. Rename `my_domain` to your actual subdomain (snake_case, no spaces).
3. Fill in `tasks.jsonl` with at least 5 rows conforming to `p3.schemas.Task`.
4. Update this README: what the domain covers, what sources you used, known risks.
5. Edit `eval.py` to pick scorers from `p3.scorers`. Do not invent a new scorer without discussion on the PR.
6. Run locally: `uv run inspect eval evals/my_domain/eval.py --model anthropic/claude-haiku-4-5`.
7. Open a PR. CI will schema-validate and smoke-run against Haiku.

## Review happens in the log viewer

Your reviewer will open `inspect view` against one of your runs — not the GitHub diff. Make sure the logs read cleanly: correct inputs, sensible outputs, scorer explanations that would make sense to an outside reader.

## Checklist

- [ ] ≥5 tasks in `tasks.jsonl`, every row schema-valid
- [ ] Every task cites a real `metadata.source` (URL, statute, or document)
- [ ] Every task has `metadata.difficulty` and ≥1 `metadata.tags`
- [ ] Persona embedded via the `persona` slot, never in `input`
- [ ] `target` set for programmatic scoring OR `rubric` set for LLM-judge scoring
- [ ] `eval.py` uses only scorers from `p3.scorers`
- [ ] This README explains the domain, sources, and any judgment calls
