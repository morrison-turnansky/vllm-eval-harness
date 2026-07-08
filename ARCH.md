# Architecture

## Overview

The harness has three components: a golden dataset (expert-verified ground truth), offline evaluation scripts, and an online evaluation config for token capture via agent-eval-harness.

## File Structure

```
vllm-eval-harness/
├── build_golden.py              # Builds golden.csv from results/ JSON + SUMMARY.md
├── eval_metrics.py              # Offline evaluation against golden.csv
├── golden.csv                   # Expert-verified ground truth
├── eval.yaml                    # agent-eval-harness config for online runs
├── cases/                       # One case per vLLM test directory group
│   ├── basic_correctness/
│   ├── compile/
│   ├── distributed/
│   ├── entrypoints/
│   ├── lora/
│   └── v1_e2e/
├── judges/
│   └── classification_judge.py  # Harness judge — scores output against golden.csv
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

Runs vllm-test-audit through agent-eval-harness to capture token usage during execution. The harness invokes the plugin via `claude --print` per case and the classification judge (`judges/classification_judge.py`) scores output against golden.csv.
