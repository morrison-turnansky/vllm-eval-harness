# vllm-test-audit Evaluation Harness — Plan

**Date**: 2026-07-08
**Status**: Phase 1 and Phase 3 implemented, Phase 2 scoped
**Goal**: Measure precision/recall and token efficiency of vllm-test-audit, including ablation of Phase 2 (adversarial review)

---

## Data Inventory

All data lives in `/home/devuser/projects/specs/vllm-torch-agentic-ci/results/`.

**Expert-verified ground truth** (`SUMMARY.md`):
- 528 unique tests (534 analyzed, 6 duplicates in distributed_not_cc.json)
- 38 final CC (36 active + 2 skipped)
- Override chain: 41 Phase 1 CC → 7 removed by Phase 2 → 3 reversed by expert → 1 manual reclassification by expert → 2 FN overrides from init-results = **38 CC**

**Phase 1 outputs**: `{dir}_cc.json` + `{dir}_not_cc.json` (6 pairs) + `all_cc.json`
**Phase 2 outputs**: `review_input_{1,2,3}.json` + `review_output_{1,2,3}.json`

---

## Phase 1: Golden Dataset — DONE

**Output**: `results/golden.csv` — 528 rows, columns: `test_name`, `is_coincidentally_correct`

`test_name` format: `{file_path}::{function_name}` (e.g. `tests/v1/e2e/general/test_cascade_attention.py::test_cascade_attention`)

**Script**: `scripts/build_golden.py`

**Flags**:
- 6 duplicates in distributed_not_cc.json (skipped)
- 2 FN overrides: `test_qwen36_moe_mixed_2d_3d_lora_tp2/tp4` — Phase 1 said STRONG_CONTRACT, expert says CC
- 1 manual reclassification: `test_single_chat_session_image_base64encoded_beamsearch` — Phase 2 agreed CC, expert overrode to NOT_REALISTIC

---

## Phase 2: Agent-Eval-Harness Online Setup

**Objective**: Run the vllm-test-audit plugin through agent-eval-harness to capture token metrics per invocation. Correctness scoring uses `golden.csv` and `eval_metrics.py` from Phases 1 and 3.

### Installed

```
claude plugin marketplace add opendatahub-io/agent-eval-harness
claude plugin install agent-eval-harness@agent-eval-harness-dev
```

Plugin version: 1.20.0. Provides 8 skills (`/eval-setup`, `/eval-analyze`, `/eval-dataset`, `/eval-run`, `/eval-review`, `/eval-mlflow`, `/eval-optimize`, `/eval-check`) and the `claude-trace` CLI.

### What the Harness Gives Us

| Feature | How we use it |
|---------|---------------|
| `claude-code` runner | Invokes vllm-test-audit skill headlessly via `claude --print` |
| `claude-trace` CLI | Wraps invocation, captures `input_tokens`, `output_tokens`, `cache_read`, `cache_create`, `cost_usd`, `num_turns`, per-model breakdown |
| `stream_capture.extract_usage()` | Parses stream-json for token metrics |
| `eval.yaml` config | Declares cases, judges, thresholds, runner config |
| Inline `check` judges | Python functions comparing output against golden.csv |
| `cost_budget` builtin judge | Gate on `cost_usd <= max_cost_usd` per invocation |
| MLflow traces | Hierarchical span tree with per-turn token attribution |
| Regression thresholds | `min_pass_rate`, `min_mean` for CI gating |

### Eval Layout

```
eval/vllm-test-audit/
├── eval.yaml
├── golden.csv                        # symlink to results/golden.csv
├── cases/
│   ├── basic_correctness/
│   │   └── input.yaml                # { directory: "tests/basic_correctness/" }
│   ├── compile/
│   │   └── input.yaml                # { directory: "tests/compile/correctness_e2e/" }
│   ├── distributed/
│   │   └── input.yaml
│   ├── entrypoints/
│   │   └── input.yaml
│   ├── lora/
│   │   └── input.yaml
│   └── v1_e2e/
│       └── input.yaml
└── judges/
    └── classification_judge.py       # loads golden.csv, compares per-test
```

One case per directory group (6 cases). Each invocation audits all tests in that directory. Token efficiency is measured as `total_tokens / tests_in_scope` — granularity of the invocation doesn't matter since classification is per-test.

### eval.yaml

```yaml
name: vllm-test-audit-eval
description: Precision/recall and token efficiency of vllm-test-audit pipeline

skill: vllm-test-audit

execution:
  mode: case
  arguments: "/vllm-test-audit:audit-contract {directory}"
  timeout: 3600
  max_budget_usd: 5.00

runner:
  type: claude-code
  effort: high
  plugin_dirs:
    - /home/devuser/projects/ai-marketplace

models:
  skill: opus

traces:
  stdout: true
  stderr: true
  events: true
  metrics: true

outputs:
  - path: "audit-cc.json"
    schema: "Phase 1 CC candidates with classification and c1/c2/c3 criteria"
  - path: "audit-not-cc.json"
    schema: "Phase 1 non-CC candidates"
  - path: "review-cc.json"
    schema: "Phase 2 reviewed candidates with AGREE/RECLASSIFY verdicts"

judges:
  - name: classification_accuracy
    type: module
    module: judges.classification_judge
    function: judge
    description: "Per-test match rate against golden.csv"
    threshold:
      min_pass_rate: 0.90

  - name: token_efficiency
    type: builtin
    builtin: efficiency/cost_budget
    arguments:
      max_cost_usd: 5.00

thresholds:
  classification_accuracy:
    min_pass_rate: 0.90
  token_efficiency:
    min_pass_rate: 1.0
```

### Token Metrics Captured Per Run

From `stream_capture.extract_usage()`:

| Metric | Description |
|--------|-------------|
| `input_tokens` | Total input tokens across all turns |
| `output_tokens` | Total output tokens |
| `cache_read` | Prompt cache hits |
| `cache_create` | Prompt cache writes |
| `cost_usd` | Total cost |
| `num_turns` | Number of tool invocations |
| Per-model breakdown | Tokens split by model (e.g. opus vs sonnet for subagents) |

Derived metric: `tokens_per_test = (input_tokens + output_tokens) / tests_in_scope`

### Pipeline to Run

```bash
# 1. Setup (one-time)
/eval-setup

# 2. Run evaluation (all 6 directory cases)
/eval-run --model opus

# 3. Results include:
#    - Per-case: classification JSON + token metrics
#    - Aggregated: pass_rate, mean scores, cost summary
#    - Traces: MLflow spans with per-turn token attribution

# 4. Score against golden.csv
python3 scripts/eval_metrics.py
```

### What We Need to Build

1. **eval.yaml** — config file pointing at the vllm-test-audit skill
2. **cases/*/input.yaml** — one per directory group (6 files, trivial)
3. **judges/classification_judge.py** — wraps `eval_metrics.py`, loads golden.csv, parses output JSON, returns match rate

### Future Work: Ablation

Phase 1-only vs full pipeline comparison to measure the marginal token cost and precision/recall delta of the adversarial review step. Requires either a phase-1-only mode in vllm-test-audit or a separate eval.yaml that only invokes audit-agent.

---

## Phase 3: Metrics & Ablation — DONE

**Script**: `scripts/eval_metrics.py`

Computes precision/recall/F1 for CC detection using scikit-learn, comparing Phase 1-only vs Phase 1+Phase 2 (no expert) against `golden.csv`.

Includes:
- `classification_report` for both conditions
- Confusion matrix (TP/FP/FN/TN)
- Per-directory breakdown (precision/recall/F1 per directory group)
- Delta analysis (which tests Phase 2 helped vs hurt)

Token efficiency metrics will be added once Phase 2 online runs produce trace data.

---

## Summary

| Phase | Status | Input | Output |
|-------|--------|-------|--------|
| **1: Golden Dataset** | DONE | results/*.json + SUMMARY.md | `results/golden.csv` (528 tests, 38 CC) |
| **2: Harness Setup** | SCOPED | agent-eval-harness plugin + vllm-test-audit | eval.yaml, cases, judges, token capture |
| **3: Metrics** | DONE | golden.csv + phase outputs | `scripts/eval_metrics.py` (precision/recall/F1, ablation, per-directory) |
