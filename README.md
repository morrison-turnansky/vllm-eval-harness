# vllm-eval-harness

Evaluation harness for [vllm-test-audit](https://github.com/TorchedHat/ai-marketplace), a Claude Code plugin that identifies coincidentally correct tests in [vLLM](https://github.com/vllm-project/vllm).

Coincidentally correct tests pass today but rely on exact numeric output that can silently break when PyTorch changes kernel selection, accumulation order, or compiler behavior. The vllm-test-audit plugin uses a two-phase agentic pipeline to find these tests: Phase 1 (audit-agent) classifies test assertions, Phase 2 (review-agent) adversarially verifies. This harness evaluates that pipeline against an expert-verified golden dataset using [agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness).

## Installation

```bash
pip install -e ".[dev]"
```

For online evaluation with token capture:

```bash
claude plugin marketplace add opendatahub-io/agent-eval-harness
claude plugin install agent-eval-harness@agent-eval-harness-dev
```

## Usage

### Offline

Evaluate correctness (F1) against the golden dataset using existing audit results:

```bash
python3 build_golden.py
python3 eval_metrics.py
```

### Online

Run the plugin with token capture from a vLLM checkout directory:

```bash
/eval-run --config /path/to/vllm-eval-harness/eval.yaml --model <model>
```

## Example Output

```
$ python3 eval_metrics.py

F1 (Phase 1 only):    0.911
F1 (Phase 1 + Phase 2): 0.917

--- Per-Directory: Phase 1 Only ---
Directory            Tests   TP   FP   FN   Prec    Rec     F1
-----------------------------------------------------------------
basic_correctness       13    2    0    0  1.000  1.000  1.000
compile                  5    5    0    0  1.000  1.000  1.000
distributed            261    3    2    0  0.600  1.000  0.750
entrypoints             51   13    1    0  0.929  1.000  0.963
lora                   142    1    0    2  1.000  0.333  0.500
v1_e2e                  56   12    2    0  0.857  1.000  0.923

--- Phase 2 Delta ---
Test                                                P1     P2   Gold     Effect
test_tp_language_embedding                        True  False  False     HELPED
test_pp_cudagraph                                 True  False  False     HELPED
test_batch_completions                            True  False   True       HURT
test_streaming_input_output_equivalence           True  False  False     HELPED
test_mtp_speculative_mixed_batch_short_prefill    True  False  False     HELPED
```

## License

Apache-2.0
