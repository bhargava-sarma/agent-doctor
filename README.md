# Agent Doctor

**An AI agent that fixes other AI agents, and proves the fix through traces.**

Agents fail in ways unit tests don't catch: a tool schema drifts from its implementation, a prompt and a parser disagree on a key, a rate gets inverted. The evidence is in the execution traces, but someone has to read them. Agent Doctor reads them for you.

Point it at a failing agent and it runs on its own:

1. **Examine:** runs the agent's test suite. Every run is traced in [neatlogs](https://neatlogs.com).
2. **Read the traces:** pulls each failing run back through the neatlogs public API: every LLM call, tool call, argument, output and exception.
3. **Diagnose:** finds the root cause and quotes the spans that prove it.
4. **Treat:** patches the agent's code. It never touches the tests.
5. **Verify:** re-runs the suite. A patch is kept only if the new traces show the original failure gone and nothing regressed; otherwise it's reverted and the Doctor tries again with that lesson in hand.
6. **Discharge:** commits each verified fix (each commit carries an [Entire](https://entire.io) checkpoint), writes a before/after report, and opens a pull request.

## Demo: the patient

[`patient/`](patient/) is an expense-auditor agent: it converts receipts to USD, totals them, and flags travel-policy violations. It ships with three layered bugs, each hidden behind the previous one:

| Layer | Bug | Symptom in traces |
|---|---|---|
| 1 | Tool schema says `meal/hotel/taxi`, policy table uses `meals/lodging/transport` | `check_policy` span → `KeyError: 'meal'` |
| 2 | Prompt asks for `total_usd`, parser reads `total` | final LLM output is correct, run still crashes |
| 3 | Exchange rates are inverted | `calculate("150 * 0.92")`: the totals are wrong |

A typical run:

```
0/4 passing, 4 crashed
Round 1  schema/policy key mismatch   → original failure cleared, deeper bug exposed
Round 2  parser reads wrong key       → 0/4 → 1/4
Round 3  inverted exchange rates      → 1/4 → 4/4
Discharge summary: 0/4 → 4/4 passing, crashes 4 → 0  (PR opened)
```

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in keys
.venv/bin/python -m patient.run --session try-1     # see the patient fail
.venv/bin/python -m agent_doctor heal               # heal it and open a PR
.venv/bin/python -m agent_doctor heal --no-pr       # heal locally only
```

`.env`:

| Variable | Purpose |
|---|---|
| `NEATLOGS_API_KEY` | project key, used by the SDK to send traces |
| `NEATLOGS_PUBLIC_API_KEY` | service-account token (`nlsa_…`), used by the Doctor to read traces |
| `LITELLM_API_KEY`, `LITELLM_BASE_URL` | OpenAI-compatible endpoint (neatHack LiteLLM) |
| `GITHUB_TOKEN` | pushes the treatment branch |

The patient runs on `claude-haiku` and the Doctor on `claude-sonnet-4.6` (override with `PATIENT_MODEL` / `DOCTOR_MODEL`).

## How it uses the stack

- **neatlogs** is both the Doctor's eyes and its proof. The SDK traces the patient (and the Doctor's own reasoning). The public API (`/traces`, `/spans`, `/spans/{id}/payload`) gives the Doctor span-level inputs, outputs and errors to diagnose from. A re-run's traces are the evidence that a fix worked.
- **Entire** records every treatment commit as a checkpoint, so each fix is linked to the session context that produced it.
- **cfo.ai** was used to plan pricing, costs and runway for Agent Doctor as a product (see submission).

## Layout

```
agent_doctor/
  doctor.py         examine → diagnose → treat → verify loop, git + PR
  neatlogs_api.py   neatlogs public API client (traces, spans, payload timelines)
  llm.py            traced LiteLLM client
  ui.py             terminal presentation
patient/
  agent.py, tools.py   the agent under treatment
  cases.py, run.py     ground truth + harness (off limits to the Doctor)
reports/            healing reports written by the Doctor
```
