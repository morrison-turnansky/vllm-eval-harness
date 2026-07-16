"""Cost efficiency judge for vllm-test-audit."""

import json


def _count_candidates(files: dict[str, str]) -> int:
    total = 0
    for name, content in files.items():
        if not name.endswith(".json"):
            continue
        if "review" in name:
            continue
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        total += len(data.get("candidates", []))
    return total


def judge(
    outputs: dict | None = None,
    **kwargs: object,
) -> tuple[float, str]:
    if outputs is None:
        return 0.0, "No outputs provided"

    cost = outputs.get("cost_usd")
    if cost is None:
        return 0.0, "No cost data available (traces.metrics not enabled?)"

    num_tests = _count_candidates(outputs.get("files", {}))
    if num_tests == 0:
        return 0.0, f"No test candidates found in output. Cost=${cost:.2f}"

    actual = cost / num_tests

    turns = outputs.get("num_turns") or 0
    tokens = outputs.get("token_usage") or {}
    cache_read = tokens.get("cache_read", 0)
    cache_create = tokens.get("cache_create", 0)
    output_tokens = tokens.get("output", 0)
    duration = outputs.get("duration_s") or 0

    cache_ratio = f"{cache_read / cache_create:.1f}:1" if cache_create > 0 else "N/A"
    output_per_turn = f"{output_tokens / turns:.0f}" if turns > 0 else "N/A"

    rationale = (
        f"${cost:.2f} total, {num_tests} tests, "
        f"${actual:.3f}/test. "
        f"{turns} turns, {duration:.0f}s, "
        f"{output_tokens:,} output tokens, "
        f"{cache_read:,} cache reads, {cache_create:,} cache writes, "
        f"cache read/create ratio {cache_ratio}, "
        f"output/turn {output_per_turn}"
    )
    return actual, rationale
