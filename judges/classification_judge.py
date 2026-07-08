"""Judge that scores vllm-test-audit output against expert-verified golden.csv."""

import csv
import json
from pathlib import Path


def _load_golden(golden_path: str | Path) -> dict[str, bool]:
    """Load golden.csv into a dict mapping test_name to is_cc.

    Args:
        golden_path: Path to golden.csv.

    Returns:
        Dict mapping test name strings to boolean CC labels.
    """
    golden: dict[str, bool] = {}
    with open(golden_path) as f:
        for row in csv.DictReader(f):
            golden[row["test_name"]] = row["is_coincidentally_correct"] == "True"
    return golden


def _extract_predictions(files: dict[str, str]) -> dict[str, bool]:
    """Extract per-test CC predictions from output JSON files.

    Args:
        files: Dict mapping filenames to their string content.

    Returns:
        Dict mapping test name strings to predicted CC labels.
    """
    preds: dict[str, bool] = {}
    for name, content in files.items():
        if not name.endswith(".json"):
            continue
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        candidates: list[dict] = data.get("candidates", [])
        for c in candidates:
            key = f"{c['file']}::{c['candidate']}"
            preds[key] = c.get("coincidentally_correct", False)
    return preds


def judge(
    outputs: dict | None = None,
    golden_path: str = "golden.csv",
    **kwargs: object,
) -> tuple[bool, str]:
    """Compare pipeline classifications against golden labels.

    Args:
        outputs: Case record dict from the harness containing 'files' and metrics.
        golden_path: Path to golden.csv relative to the eval directory.

    Returns:
        Tuple of (passed, rationale) where passed is True if match rate >= 90%.
    """
    if outputs is None:
        return False, "No outputs provided"

    golden = _load_golden(Path(golden_path))
    files: dict[str, str] = outputs.get("files", {})
    preds = _extract_predictions(files)

    if not preds:
        return False, "No predictions found in output files"

    matched = 0
    total = 0
    mismatches: list[str] = []

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
