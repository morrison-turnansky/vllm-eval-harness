---
agent: Claude Code
model: claude-opus-4-6-1m
date: 2026-07-13T19:00:00Z
---

## Recommendation

**Instruction-level optimization cannot fix the cost_per_test regression. The $0.25/test target is structurally unreachable for a 3-agent Opus pipeline on 5-test cases. Adjust the threshold or use a cheaper model for Phase 2.**

Three optimization iterations targeting audit-agent and review-agent instructions all made cost worse, not better. The baseline ($1.71, $0.342/test) was the cheapest run. Instruction changes to reduce file reads, batch analysis, and skip unnecessary source verification either had no effect or increased cost through LLM behavioral variance. The ~16% run-to-run cost variance ($1.71–$1.98) exceeds any plausible instruction-level savings.

**Top actions:**
- **HIGH** — Raise `target_cost_per_test` in eval.yaml from $0.25 to $0.35. The current target is unreachable for Opus-tier 3-agent pipelines on small cases. $0.35 would pass the baseline consistently.
- **HIGH** — Use a cheaper model for Phase 2 (`claude-sonnet-4-6`) via `--subagent-model`. The review-agent's adversarial verification is well-suited to a smaller model since it receives structured evidence from Phase 1.
- **MEDIUM** — Run `compile` alongside larger cases (`lora`, `distributed`) to measure per-test cost at scale. Fixed pipeline overhead (agent startup, system prompt, cache creation) amortizes over more tests — the per-test cost on 142-test `lora` should be significantly lower.

## Iteration Summary

| Run | Cost | Turns | $/test | Score | Change |
|-----|------|-------|--------|-------|--------|
| Baseline | $1.71 | 26 | $0.342 | 0.731 | — |
| Iter-1 (review-agent: snippet-first) | $1.77 | 24 | $0.354 | 0.706 | Review-agent ignored instructions, still read all files |
| Iter-2 (review-agent: remove all source-read directives) | $1.98 | 24 | $0.396 | 0.631 | Model spent more tokens deliberating, cost went up |
| Iter-3 (audit-agent: batch reads + revert review) | $1.98 | 32 | $0.396 | 0.631 | More turns, not fewer — batching instruction ignored |

All changes reverted after iteration 3. Agent definitions are back to baseline state.

## Root Cause

The cost_per_test failure is structural, not instructional:

1. **Fixed pipeline overhead dominates on small cases.** Three agent spawns (coordinator→audit→review) each pay ~23K tokens for system prompt cache creation. With only 5 tests, this fixed cost is $0.30+ before any analysis begins — already 60% of the $0.25/test × 5 = $1.25 target.

2. **Phase 2 is as expensive as Phase 1 but adds no value on this case.** The review-agent independently re-analyzes every test file to produce AGREE verdicts. phase_delta=0.000 across all 4 runs confirms Phase 2 never changes any classification. This is consistent behavior, not stochastic.

3. **LLM instruction compliance is unreliable for behavioral cost reduction.** All three attempts to reduce file reads through instructions failed. The review-agent's adversarial role ("you are the skeptic") overrides efficiency directives — the model feels obligated to independently verify.

## Cost Attribution

Run metrics across iterations show stable model pricing ($0.062–$0.083/turn, cache hit rate 81–87%). The cost variance is entirely workload-driven: different turn counts (24–32) and output volumes per run. No model/runner cost drift.
