"""F1 score judge for vllm-test-audit against expert-verified golden.csv."""

import csv
import json
from pathlib import Path


def _load_golden(golden_path: str | Path) -> dict[str, bool]:
    golden: dict[str, bool] = {}
    with open(golden_path) as f:
        for row in csv.DictReader(f):
            golden[row["test_name"]] = row["is_coincidentally_correct"] == "True"
    return golden


def _extract_predictions(files: dict[str, str]) -> dict[str, bool]:
    preds: dict[str, bool] = {}
    for name, content in files.items():
        if not name.endswith(".json"):
            continue
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        for c in data.get("candidates", []):
            key = f"{c['file']}::{c['candidate']}"
            preds[key] = c.get("coincidentally_correct", False)
    return preds


def judge(
    outputs: dict | None = None,
    golden_path: str = "golden.csv",
    **kwargs: object,
) -> tuple[float, str]:
    if outputs is None:
        return 0.0, "No outputs provided"

    golden = _load_golden(Path(golden_path))
    preds = _extract_predictions(outputs.get("files", {}))

    if not preds:
        return 0.0, "No predictions found in output files"

    tp, fp, fn = 0, 0, 0
    fp_tests: list[str] = []
    fn_tests: list[str] = []

    for test_name, golden_label in golden.items():
        if test_name not in preds:
            continue
        pred_label = preds[test_name]
        if pred_label and golden_label:
            tp += 1
        elif pred_label and not golden_label:
            fp += 1
            fp_tests.append(test_name.split("::")[-1])
        elif not pred_label and golden_label:
            fn += 1
            fn_tests.append(test_name.split("::")[-1])

    if tp + fp + fn == 0:
        return 0.0, "No overlap between predictions and golden labels"

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    rationale = f"F1={f1:.3f} P={precision:.3f} R={recall:.3f} (TP={tp} FP={fp} FN={fn})"
    if fp_tests:
        rationale += f". FP: {'; '.join(fp_tests[:10])}"
        if len(fp_tests) > 10:
            rationale += f" (+{len(fp_tests) - 10} more)"
    if fn_tests:
        rationale += f". FN: {'; '.join(fn_tests[:10])}"
        if len(fn_tests) > 10:
            rationale += f" (+{len(fn_tests) - 10} more)"

    return f1, rationale
