# vllm-eval-harness

Evaluation harness for [vllm-test-audit](https://github.com/TorchedHat/ai-marketplace), a Claude Code plugin that identifies coincidentally correct tests in [vLLM](https://github.com/vllm-project/vllm).

Coincidentally correct tests pass today but rely on exact numeric output that can silently break when PyTorch changes kernel selection, accumulation order, or compiler behavior. The vllm-test-audit plugin uses a two-phase agentic pipeline to find these tests: Phase 1 (audit-agent) classifies test assertions, Phase 2 (review-agent) adversarially verifies. This harness evaluates that pipeline against an expert-verified golden dataset using [agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness).

## Installation

```bash
pip install scikit-learn
```

For online evaluation with token capture:

```bash
claude plugin marketplace add opendatahub-io/agent-eval-harness
claude plugin install agent-eval-harness@agent-eval-harness-dev
```

## Usage

### Offline

```bash
# Rebuild golden dataset (only needed if results/ changes)
python3 build_golden.py

# Evaluate
python3 eval_metrics.py
```

### Online

From a vLLM checkout directory:

```bash
/eval-run --config /path/to/vllm-eval-harness/eval.yaml --model <model>
```

## License

Apache-2.0
