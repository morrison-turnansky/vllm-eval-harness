# vllm-test-audit Evaluation Harness — Plan

**Date**: 2026-07-08
**Status**: Phase 1, 2, and 3 implemented
**Goal**: Measure correctness (F1) and token efficiency of vllm-test-audit

---

## Data Inventory

All data lives in `results/`.

**Expert-verified ground truth** (`SUMMARY.md`):
- 528 unique tests (534 analyzed, 6 duplicates removed)
- 38 final CC (36 active + 2 skipped)
- Override chain: 41 Phase 1 CC → 7 removed by Phase 2 → 3 reversed by expert → 1 manual reclassification by expert → 2 FN overrides from init-results

**Phase 1 outputs**: `{dir}_cc.json` + `{dir}_not_cc.json` (6 pairs) + `all_cc.json`
**Phase 2 outputs**: `review_input_{1,2,3}.json` + `review_output_{1,2,3}.json`

---

## Phase 1: Golden Dataset — DONE

**Output**: `golden.csv` — 528 rows, columns: `test_name`, `is_coincidentally_correct`

**Script**: `build_golden.py`

**Flags**:
- 6 duplicates in distributed_not_cc.json (skipped)
- 2 FN overrides: `test_qwen36_moe_mixed_2d_3d_lora_tp2/tp4` — Phase 1 said STRONG_CONTRACT, expert says CC
- 1 manual reclassification: `test_single_chat_session_image_base64encoded_beamsearch` — Phase 2 agreed CC, expert overrode to NOT_REALISTIC

---

## Phase 2: Agent-Eval-Harness Online Setup — DONE

**Objective**: Run vllm-test-audit through agent-eval-harness to capture token metrics. Correctness scoring uses `golden.csv` and `eval_metrics.py`.

### Installed

```
claude plugin marketplace add opendatahub-io/agent-eval-harness
claude plugin install agent-eval-harness@agent-eval-harness-dev
```

### Implemented

- `eval.yaml` — harness config targeting vllm-test-audit skill via `claude-code` runner
- `cases/*/input.yaml` — 6 cases, one per vLLM test directory group
- `judges/classification_judge.py` — module judge, loads `golden.csv`, scores output match rate

### Running

From a vLLM checkout:

```bash
/eval-run --config /path/to/vllm-eval-harness/eval.yaml --model <model>
```

### Token Metrics Captured Per Run

| Metric | Description |
|--------|-------------|
| `input_tokens` | Total input tokens across all turns |
| `output_tokens` | Total output tokens |
| `cache_read` | Prompt cache hits |
| `cache_create` | Prompt cache writes |
| `cost_usd` | Total cost |
| `num_turns` | Number of tool invocations |
| Per-model breakdown | Tokens split by model |

Derived: `tokens_per_test = (input_tokens + output_tokens) / tests_in_scope`

---

## Phase 3: Metrics — DONE

**Script**: `eval_metrics.py`

**Primary metric**: F1 score (single number combining precision and recall)

Compares two conditions against `golden.csv`:
- Phase 1 only (audit-agent)
- Phase 1 + Phase 2 (audit-agent + review-agent, no expert)

Also reports: classification report, confusion matrix, per-directory breakdown, delta analysis.

---

## Future Work

**Ablation**: Phase 1-only vs full pipeline to measure marginal token cost of adversarial review. Requires a phase-1-only mode in vllm-test-audit or a separate eval.yaml invoking only audit-agent.

---

## Summary

| Phase | Status | Script | Output |
|-------|--------|--------|--------|
| **1: Golden Dataset** | DONE | `build_golden.py` | `golden.csv` |
| **2: Harness Setup** | DONE | `eval.yaml` + `judges/` | Online eval with token capture |
| **3: Metrics** | DONE | `eval_metrics.py` | F1, per-directory breakdown, ablation |
