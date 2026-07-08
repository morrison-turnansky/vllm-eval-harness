# vllm-eval-harness

Evaluation harness for the `vllm-test-audit` plugin. Measures classification
accuracy (precision/recall against expert-verified `golden.csv`) and token
efficiency.

## Running evals

```bash
/eval-run --config /home/devuser/projects/vllm-eval-harness/eval.yaml \
  --model claude-opus-4-6 --cases basic_correctness
```

Available cases: `basic_correctness` (13 tests), `compile` (5), `lora` (142),
`v1_e2e` (56), `distributed` (261), `entrypoints` (1302). Start with
`basic_correctness` or `compile` for fast iteration.

## Key conventions

### `skill` field is empty

The `skill:` field in `eval.yaml` is intentionally `""`. The audit is invoked
via the **Agent tool** (`subagent_type: vllm-test-audit:audit-agent`), not a
slash command. When `skill` is empty, `execute.py` sends `execution.arguments`
as a plain natural-language prompt instead of prepending `/{skill_name}`.

**Path implication**: with empty `skill`, run output goes to
`eval/runs/<run-id>/` (no eval-name subdirectory). Both `execute.py --output`
and `score.py` resolve to the same path when `skill` is empty.

### vLLM repo dependency

The audit-agent needs access to vLLM test files at `/home/devuser/projects/vllm`.
The `before_each` hook (`scripts/setup_workspace.py`) handles this automatically:

1. Symlinks `tests/` from the vLLM repo into each case workspace
2. Adds the vLLM repo to workspace `additionalDirectories`
3. Trusts the workspace in `~/.claude.json`

### Model availability

`claude-opus-4-6` works on the Vertex deployment. The 1M-context variant
(`claude-opus-4-6-1m`) is **not available** on Vertex — the headless runner
will fail with "model not available".
