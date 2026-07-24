"""Cost efficiency judge for nightly triage — $/group, lower is better."""

import json


def _count_groups(files: dict[str, str]) -> int:
    for name, content in files.items():
        if name == "triage-output.json":
            try:
                data = json.loads(content)
                return len(data)
            except (json.JSONDecodeError, TypeError):
                return 0
    return 0


def judge(
    outputs: dict | None = None,
    target_cost_per_group: float = 1.00,
    **kwargs: object,
) -> tuple[float, str]:
    if outputs is None:
        return 0.0, "No outputs provided"

    cost = outputs.get("cost_usd")
    if cost is None:
        return 0.0, "No cost data available (traces.metrics not enabled?)"

    num_groups = _count_groups(outputs.get("files", {}))
    if num_groups == 0:
        return 0.0, f"No groups found in output. Cost=${cost:.2f}"

    actual = cost / num_groups
    score = min(1.0, target_cost_per_group / actual) if actual > 0 else 1.0

    turns = outputs.get("num_turns") or 0
    tokens = outputs.get("token_usage") or {}
    output_tokens = tokens.get("output", 0)
    duration = outputs.get("duration_s") or 0

    rationale = (
        f"${cost:.2f} total, {num_groups} groups, "
        f"${actual:.3f}/group (target=${target_cost_per_group:.2f}). "
        f"Score={score:.3f}. "
        f"{turns} turns, {duration:.0f}s, "
        f"{output_tokens:,} output tokens"
    )

    return score, rationale
