"""Macro F1 judge for nightly triage classification accuracy."""

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import f1_score, precision_recall_fscore_support

CLASSIFICATION_MAP = {
    "TORCH_REGRESSION": "torch",
    "TRITON_REGRESSION": "triton",
    "VLLM_BUG": "vllm",
    "PRE_EXISTING": "pre_existing",
}

ALL_LABELS = ["torch", "triton", "vllm", "pre_existing"]


def _load_golden(datasets_dir: str | Path, umbrella_issue: str) -> list[dict]:
    path = Path(datasets_dir) / f"dataset_{umbrella_issue}.csv"
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def _extract_groups(files: dict[str, str]) -> list[dict]:
    for name, content in files.items():
        if name == "triage-output.json":
            try:
                return json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return []
    return []


def _map_classification(raw_classification: str) -> str:
    return CLASSIFICATION_MAP.get(raw_classification, raw_classification.lower())


def judge(
    outputs: dict | None = None,
    datasets_dir: str = "datasets",
    **kwargs: object,
) -> tuple[float, str]:
    if outputs is None:
        return 0.0, "No outputs provided"

    case_dir = outputs.get("case_dir", "")
    umbrella_issue = Path(case_dir).name if case_dir else ""
    if not umbrella_issue:
        return 0.0, "Cannot determine umbrella issue from case directory"

    golden_rows = _load_golden(datasets_dir, umbrella_issue)
    if not golden_rows:
        return 0.0, f"No golden data for umbrella {umbrella_issue}"

    groups = _extract_groups(outputs.get("files", {}))
    if not groups:
        return 0.0, "No triage groups found in output"

    golden_types = [row["regression_type"] for row in golden_rows]
    golden_issues = [row["issue_number"] for row in golden_rows]

    predicted_types = []
    matched_issues = []

    for golden_row in golden_rows:
        best_group = None
        best_member_count = 0

        for group in groups:
            member_count = len(group.get("members", []))
            if member_count > best_member_count:
                best_group = group
                best_member_count = member_count

        if best_group:
            predicted_type = _map_classification(best_group.get("classification", ""))
            predicted_types.append(predicted_type)
            matched_issues.append(golden_row["issue_number"])
            groups = [g for g in groups if g is not best_group]
        else:
            predicted_types.append("unclassified")
            matched_issues.append(golden_row["issue_number"])

    macro_f1 = float(f1_score(golden_types, predicted_types, labels=ALL_LABELS, average="macro", zero_division=0))

    result: tuple[Any, ...] = precision_recall_fscore_support(
        golden_types, predicted_types, labels=ALL_LABELS, zero_division=0
    )
    precision_arr: np.ndarray = result[0]
    recall_arr: np.ndarray = result[1]
    f1_arr: np.ndarray = result[2]
    support_arr: np.ndarray = result[3]

    per_class = []
    for i, label in enumerate(ALL_LABELS):
        if support_arr[i] > 0 or any(p == label for p in predicted_types):
            per_class.append(
                f"{label}: P={precision_arr[i]:.2f} R={recall_arr[i]:.2f} F1={f1_arr[i]:.2f} n={int(support_arr[i])}"
            )

    mismatches = []
    for issue, golden_type, predicted_type in zip(golden_issues, golden_types, predicted_types):
        if golden_type != predicted_type:
            mismatches.append(f"#{issue}: {golden_type}→{predicted_type}")

    rationale = f"Macro F1={macro_f1:.3f} ({len(golden_rows)} issues, {len(groups)} unmatched groups)"
    if per_class:
        rationale += ". " + "; ".join(per_class)
    if mismatches:
        shown = mismatches[:10]
        rationale += ". Mismatches: " + "; ".join(shown)
        if len(mismatches) > 10:
            rationale += f" (+{len(mismatches) - 10} more)"

    return macro_f1, rationale
