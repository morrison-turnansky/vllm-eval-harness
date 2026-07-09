"""Phase 2 marginal F1 contribution judge for vllm-test-audit."""

import csv
import json
from pathlib import Path


def _load_golden(golden_path: str | Path) -> dict[str, bool]:
    golden: dict[str, bool] = {}
    with open(golden_path) as f:
        for row in csv.DictReader(f):
            golden[row["test_name"]] = row["is_coincidentally_correct"] == "True"
    return golden


def _compute_f1(
    golden: dict[str, bool], preds: dict[str, bool],
) -> tuple[float, int, int, int]:
    tp, fp, fn = 0, 0, 0
    for test_name, golden_label in golden.items():
        if test_name not in preds:
            continue
        pred = preds[test_name]
        if pred and golden_label:
            tp += 1
        elif pred and not golden_label:
            fp += 1
        elif not pred and golden_label:
            fn += 1
    if tp + fp + fn == 0:
        return 0.0, 0, 0, 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return f1, tp, fp, fn


def judge(
    outputs: dict | None = None,
    golden_path: str = "golden.csv",
    **kwargs: object,
) -> tuple[float, str]:
    if outputs is None:
        return 0.0, "No outputs provided"

    files: dict[str, str] = outputs.get("files", {})
    golden = _load_golden(Path(golden_path))

    phase1_preds: dict[str, bool] = {}
    for name, content in files.items():
        if not name.endswith(".json") or "review" in name:
            continue
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        for c in data.get("candidates", []):
            key = f"{c['file']}::{c['candidate']}"
            phase1_preds[key] = c.get("coincidentally_correct", False)

    if not phase1_preds:
        return 0.0, "No Phase 1 predictions found"

    phase2_preds = dict(phase1_preds)
    review_found = False
    for name, content in files.items():
        if not name.endswith(".json") or "review" not in name:
            continue
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        review_found = True
        for c in data.get("candidates", []):
            key = f"{c['file']}::{c['candidate']}"
            if c.get("review", "").startswith("RECLASSIFY"):
                phase2_preds[key] = False
            else:
                phase2_preds[key] = True

    if not review_found:
        return 0.0, "No review-cc.json found — Phase 2 did not run"

    f1_p1, tp1, fp1, fn1 = _compute_f1(golden, phase1_preds)
    f1_p2, tp2, fp2, fn2 = _compute_f1(golden, phase2_preds)
    delta = f1_p2 - f1_p1

    helped: list[str] = []
    hurt: list[str] = []
    for key in golden:
        p1 = phase1_preds.get(key, False)
        p2 = phase2_preds.get(key, False)
        if p1 == p2:
            continue
        gold = golden[key]
        short = key.split("::")[-1]
        if p2 == gold and p1 != gold:
            helped.append(short)
        elif p1 == gold and p2 != gold:
            hurt.append(short)

    rationale = (
        f"Phase1 F1={f1_p1:.3f} Phase2 F1={f1_p2:.3f} delta={delta:+.3f}"
    )
    if helped:
        rationale += f". Helped: {'; '.join(helped[:5])}"
    if hurt:
        rationale += f". Hurt: {'; '.join(hurt[:5])}"

    return delta, rationale
