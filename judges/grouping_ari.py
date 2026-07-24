"""Adjusted Rand Index judge for nightly triage failure grouping."""

import json
from pathlib import Path

from sklearn.metrics import adjusted_rand_score


def _load_golden_mapping(case_dir: str | Path) -> dict[str, list[tuple[str, str]]]:
    path = Path(case_dir) / "golden_mapping.json"
    with open(path) as f:
        return json.load(f)


def _extract_groups(files: dict[str, str]) -> list[dict]:
    for name, content in files.items():
        if name == "triage-output.json":
            try:
                return json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return []
    return []


def judge(
    outputs: dict | None = None,
    datasets_dir: str = "datasets",
    **kwargs: object,
) -> tuple[float, str]:
    if outputs is None:
        return 0.0, "No outputs provided"

    case_dir = outputs.get("case_dir", "")
    if not case_dir:
        return 0.0, "Cannot determine case directory"

    try:
        golden_mapping = _load_golden_mapping(case_dir)
    except FileNotFoundError:
        return 0.0, f"golden_mapping.json not found in {case_dir}"

    groups = _extract_groups(outputs.get("files", {}))
    if not groups:
        return 0.0, "No triage groups found in output"

    true_labels = []
    pred_labels = []

    golden_lookup = {}
    for issue_number, failures in golden_mapping.items():
        for failure in failures:
            job_name = failure[0]
            test_id = failure[1]
            key = f"{job_name}::{test_id}"
            golden_lookup[key] = issue_number

    pred_lookup = {}
    for group in groups:
        group_id = group.get("group_id", 0)
        for member in group.get("members", []):
            key = f"{member['job_name']}::{member['test_id']}"
            pred_lookup[key] = str(group_id)

    all_keys = set(golden_lookup.keys()) | set(pred_lookup.keys())
    if not all_keys:
        return 0.0, "No failures to compare"

    shared_keys = set(golden_lookup.keys()) & set(pred_lookup.keys())
    if len(shared_keys) < 2:
        return 0.0, f"Only {len(shared_keys)} shared failures — need at least 2 for ARI"

    for key in sorted(shared_keys):
        true_labels.append(golden_lookup[key])
        pred_labels.append(pred_lookup[key])

    ari = adjusted_rand_score(true_labels, pred_labels)
    clamped_ari = max(0.0, ari)

    golden_cluster_count = len(golden_mapping)
    pred_cluster_count = len(groups)
    coverage = len(shared_keys) / len(golden_lookup) if golden_lookup else 0.0

    only_in_golden = len(set(golden_lookup.keys()) - set(pred_lookup.keys()))
    only_in_pred = len(set(pred_lookup.keys()) - set(golden_lookup.keys()))

    rationale = (
        f"ARI={ari:.3f} (clamped={clamped_ari:.3f}). "
        f"Golden clusters: {golden_cluster_count}, predicted clusters: {pred_cluster_count}. "
        f"Shared failures: {len(shared_keys)}/{len(golden_lookup)} (coverage={coverage:.1%}). "
        f"Only in golden: {only_in_golden}, only in predicted: {only_in_pred}"
    )

    return clamped_ari, rationale
