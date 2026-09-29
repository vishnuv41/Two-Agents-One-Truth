# Two Agents, One Truth
Two agents disagree, weigh evidence with MeTTa rules, resolve (concede / conditional / escalate), then learn a rule and a reliability change. Run it again and they converge faster.

## Problem
Conflicting sources (official calendar vs field data) cause bad decisions and nobody can see why one was chosen.

## Solution
Each agent holds a claim and evidence. `core/weigh.metta` computes support = sum(reliability x recency), detects conflict, and picks the resolution. Nothing is hard-coded per scenario. Python only loads atoms and persists memory. An optional LLM only narrates the trace and never decides.

## Technology
Python, Hyperon/MeTTa, FastAPI, single-page UI. Each agent scores evidence through its own MeTTa lens (`pref` atoms): A weights source reliability, B weights recency. Optional LLM (narration and free-text intake): set `LLM_KEY`, `LLM_BASE_URL` (OpenAI-compatible, e.g. Groq/OpenRouter), `LLM_MODEL`.

## Run
```
pip install -r requirements.txt
uvicorn app:app --reload      # open http://localhost:8000
pytest                        # 16 tests
```
Demo: run "campus", then run again: the learned rule applies with no re-argument. `Reset memory` re-records the demo.

## API
`POST /conflict {"text": ...}` is the main endpoint (any domain). `/run/{crop|campus|tie}` are fixtures. Memory is scoped by `context` (domain) so learning in one domain doesn't leak into another; rules are versioned with timestamps.

## Tests
16 pytest cases: strong A/B, close+condition, close+none, same claim, missing evidence, human decision, memory reuse, new domains, context isolation, five rounds, malformed input.

## Free-text intake
Paste a conflict in the UI. With an LLM configured it extracts claims/evidence JSON (validated, retried once, sanitized to safe MeTTa symbols). Without one, use the line format shown in the UI. The LLM never decides the outcome.

## Omega integration
`omega/plugins/twoagents/` is a real Omega plugin (Omega's `loadOmegaPlugin` + `add-skill` API, per its plugin docs) exposing a `(negotiate "...")` skill that calls the engine through a Python bridge. Install: `sh omega/install.sh /path/to/Omega`, `export TWOAGENTS_HOME=<this repo>`, start Omega. Verified: the bridge runs and the install script edits `config/plugins.yaml`. NOT yet verified: loading inside a running Omega (needs its full stack and an LLM); confirm with the mentors.

## What's next
Omega persistence/audit hook, more agents, real data sources.

## AI Disclosure
- Claude (Anthropic) was used for project planning, and for generating the initial code scaffold, MeTTa rules, tests and this README, which the team reviewed and edited.
- At runtime, an optional OpenAI-compatible LLM is used only for (1) turning free text into structured claims JSON and (2) narrating the finished trace. It does not weigh evidence or choose resolutions; that is done by MeTTa rules in `core/weigh.metta`.
- Team: add any other tools you used (Omega inference, Copilot, etc.) before submitting.
