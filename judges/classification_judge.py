"""Judge that scores vllm-test-audit output against expert-verified golden.csv."""

import csv
import json
from pathlib import Path


def _load_golden(golden_path):
    golden = {}
    with open(golden_path) as f:
        for row in csv.DictReader(f):
            golden[row["test_name"]] = row["is_coincidentally_correct"] == "True"
    return golden


def _extract_predictions(files):
    preds = {}
    for name, content in files.items():
        if not name.endswith(".json"):
            continue
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data.get("candidates", [])
        for c in candidates:
            key = f"{c['file']}::{c['candidate']}"
            preds[key] = c.get("coincidentally_correct", False)
    return preds


def judge(outputs=None, golden_path="golden.csv", **kwargs):
    """Compare pipeline classifications against golden labels.

    Args:
        outputs: Case record dict from the harness (contains 'files', 'token_usage', etc.)
        golden_path: Path to golden.csv relative to eval directory.

    Returns:
        (pass: bool, rationale: str)
    """
    golden = _load_golden(Path(golden_path))
    files = outputs.get("files", {})
    preds = _extract_predictions(files)

    if not preds:
        return False, "No predictions found in output files"

    matched = 0
    total = 0
    mismatches = []

    for test_name, golden_label in golden.items():
        if test_name not in preds:
            continue
        total += 1
        pred_label = preds[test_name]
        if pred_label == golden_label:
            matched += 1
        else:
            mismatches.append(
                f"{test_name.split('::')[-1]}: predicted={pred_label}, golden={golden_label}"
            )

    if total == 0:
        return False, "No overlap between predictions and golden labels"

    rate = matched / total
    passed = rate >= 0.90

    rationale = f"{matched}/{total} ({rate:.1%}) correct"
    if mismatches:
        rationale += f". Mismatches: {'; '.join(mismatches[:10])}"
        if len(mismatches) > 10:
            rationale += f" (+{len(mismatches) - 10} more)"

    return passed, rationale
