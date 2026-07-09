# Architecture

## Overview

The harness has four components: a golden dataset (expert-verified ground truth), offline evaluation scripts, online evaluation via agent-eval-harness, and an optimize feedback loop targeting the audit contract.

## File Structure

```
vllm-eval-harness/
├── eval.yaml                    # agent-eval-harness config for online runs
├── golden.csv                   # Expert-verified ground truth (528 tests, 38 CC)
├── build_golden.py              # Builds golden.csv from results/ JSON + SUMMARY.md
├── eval_metrics.py              # Offline evaluation against golden.csv
├── cases/                       # One case per vLLM test directory group
│   ├── basic_correctness/
│   ├── compile/
│   ├── distributed/
│   ├── entrypoints/
│   ├── lora/
│   └── v1_e2e/
├── judges/
│   ├── f1_score.py              # F1 (0-1) against golden.csv — primary optimize signal
│   ├── cost_per_test.py         # Token cost efficiency (0-1) — secondary optimize signal
│   └── phase_delta.py           # Phase 2 marginal F1 contribution (-1 to 1)
├── scripts/
│   └── setup_workspace.py       # before_each hook — symlinks vLLM tests into workspace
└── results/                     # Raw audit data (Phase 1 + Phase 2 JSON, SUMMARY.md)
```

## Golden Dataset (build_golden.py → golden.csv)

CSV with columns `test_name` and `is_coincidentally_correct`. Labels are derived by applying an override chain:

1. Phase 1 not-CC files (`{dir}_not_cc.json`)
2. Phase 1 CC candidates (`all_cc.json`)
3. Phase 2 review verdicts (`review_output_{1,2,3}.json`)
4. Expert corrections from SUMMARY.md

## Offline Evaluation (eval_metrics.py)

Compares two conditions against golden.csv:

- **Phase 1 only** — raw audit-agent output
- **Phase 1 + Phase 2** — audit-agent + review-agent, no expert corrections

Reports per-directory breakdown and a delta table showing which tests Phase 2 helped vs hurt.

## Online Evaluation (eval.yaml + judges/)

Runs vllm-test-audit through agent-eval-harness. The pipeline:

```
eval-run
  └─ claude --print (arguments from eval.yaml)
       └─ coordinator-agent (vllm-test-audit:coordinator-agent)
            ├─ audit-agent (Phase 1) → audit-cc.json, audit-not-cc.json
            └─ review-agent (Phase 2) → review-cc.json
```

`skill: ""` in eval.yaml means execute.py sends arguments as a plain prompt (no slash command). The prompt tells the Claude session to spawn the coordinator-agent via the Agent tool.

### Judges

Three numeric judges score each case's output files against golden.csv:

| Judge | Returns | Purpose |
|-------|---------|---------|
| `f1_score` | 0.0–1.0 | F1 against golden — primary optimization metric |
| `cost_per_test` | 0.0–1.0 | `min(1, target / actual_cost_per_test)` — efficiency |
| `phase_delta` | -1.0–1.0 | Phase 2 F1 minus Phase 1 F1 — measures review value |

Reward formula: `0.7 * f1_score + 0.3 * cost_per_test`.

### Optimize Target

`optimize.target: audit-contract` in eval.yaml tells `/eval-optimize` to edit `audit-contract/SKILL.md` — the shared classification knowledge (criteria, strong contract clauses, not-strong clauses) loaded by both agents. This is decoupled from `skill` because execution uses the Agent tool, not a slash command.

## Optimize Feedback Loop

```
/eval-optimize
  ├─ find_skills.py --name audit-contract → SKILL.md path
  └─ loop:
       1. /eval-run → f1_score, cost_per_test, phase_delta
       2. Read summary.yaml → identify FP/FN tests
       3. Read transcripts → trace misclassification cause
       4. Edit audit-contract/SKILL.md (add/refine clause)
       5. /eval-run --baseline <prev> → compare
       6. Repeat if improved and iterations remain
```

FP/FN in the f1_score rationale map to specific contract sections:

| Error | Root cause | Edit target in contract |
|-------|------------|------------------------|
| FP (predicted CC, actually strong contract) | Missing clause | §Strong Contracts |
| FP (predicted CC, actually not realistic) | Missing pattern | §Not CC by Default |
| FN (predicted not CC, actually is CC) | Missing clause | §Not Strong by Default |
| FN (predicted not CC, actually is CC) | Unrecognized pattern | §Assertion Pattern Guidance |
