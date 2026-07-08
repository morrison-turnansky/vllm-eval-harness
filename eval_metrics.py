"""Precision/recall/F1 evaluation and Phase 2 ablation study."""

import csv
import json
from pathlib import Path

from sklearn.metrics import classification_report, confusion_matrix

RESULTS_DIR = Path(__file__).parent / "results"

REVIEW_FILES: list[str] = [
    "review_output_1.json",
    "review_output_2.json",
    "review_output_3.json",
]

NOT_CC_FILES: list[str] = [
    "basic_not_cc.json",
    "compile_not_cc.json",
    "distributed_not_cc.json",
    "entrypoints_not_cc.json",
    "lora_not_cc.json",
    "v1_e2e_not_cc.json",
]

CC_FILE: str = "all_cc.json"

DIR_GROUPS: dict[str, str] = {
    "tests/basic_correctness/": "basic_correctness",
    "tests/compile/": "compile",
    "tests/distributed/": "distributed",
    "tests/entrypoints/": "entrypoints",
    "tests/lora/": "lora",
    "tests/v1/e2e/": "v1_e2e",
}


def load_json(name: str) -> dict:
    """Load a JSON file from the results directory.

    Args:
        name: Filename relative to RESULTS_DIR.

    Returns:
        Parsed JSON content.
    """
    with open(RESULTS_DIR / name) as f:
        return json.load(f)


def dir_group(file_path: str) -> str:
    """Map a test file path to its directory group.

    Args:
        file_path: Relative path to the test file.

    Returns:
        Directory group label, or 'unknown' if no match.
    """
    for prefix, label in DIR_GROUPS.items():
        if file_path.startswith(prefix):
            return label
    return "unknown"


def load_golden() -> dict[str, bool]:
    """Load golden.csv into a dict mapping test_name to is_cc.

    Returns:
        Dict mapping test name strings to boolean CC labels.
    """
    golden: dict[str, bool] = {}
    with open(Path(__file__).parent / "golden.csv") as f:
        for row in csv.DictReader(f):
            golden[row["test_name"]] = row["is_coincidentally_correct"] == "True"
    return golden


def build_phase1_predictions() -> dict[str, bool]:
    """Build Phase 1 prediction map from raw audit JSON files.

    Returns:
        Dict mapping test name strings to predicted CC labels.
    """
    preds: dict[str, bool] = {}
    seen: set[str] = set()
    for fname in NOT_CC_FILES:
        for c in load_json(fname)["candidates"]:
            key = f"{c['file']}::{c['candidate']}"
            if key not in seen:
                seen.add(key)
                preds[key] = False
    for c in load_json(CC_FILE)["candidates"]:
        key = f"{c['file']}::{c['candidate']}"
        if key not in seen:
            seen.add(key)
            preds[key] = True
    return preds


def build_phase2_predictions() -> dict[str, bool]:
    """Build Phase 1+2 prediction map by applying review verdicts.

    Returns:
        Dict mapping test name strings to predicted CC labels after Phase 2.
    """
    preds = build_phase1_predictions()

    review_verdicts: dict[str, bool] = {}
    for fname in REVIEW_FILES:
        for c in load_json(fname)["candidates"]:
            key = f"{c['file']}::{c['candidate']}"
            if c["review"].startswith("RECLASSIFY"):
                review_verdicts[key] = False
            else:
                review_verdicts[key] = True

    for key, is_cc in review_verdicts.items():
        preds[key] = is_cc

    return preds


def print_report(name: str, y_true: list[int], y_pred: list[int]) -> None:
    """Print a classification report and confusion matrix.

    Args:
        name: Display name for this condition.
        y_true: Ground truth binary labels.
        y_pred: Predicted binary labels.
    """
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")
    print(classification_report(y_true, y_pred, target_names=["NOT_CC", "CC"], zero_division=0))

    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    print(f"  Confusion Matrix:  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print()


def print_per_directory(golden: dict[str, bool], predictions: dict[str, bool], name: str) -> None:
    """Print per-directory precision/recall/F1 breakdown.

    Args:
        golden: Ground truth labels.
        predictions: Predicted labels.
        name: Display name for this condition.
    """
    print(f"\n--- Per-Directory: {name} ---")
    header = f"{'Directory':<20} {'Tests':>5} {'TP':>4} {'FP':>4} {'FN':>4}"
    header += f" {'Prec':>6} {'Rec':>6} {'F1':>6}"
    print(header)
    print("-" * 65)

    groups: dict[str, dict[str, list[int]]] = {}
    for key in golden:
        file_path = key.split("::")[0]
        g = dir_group(file_path)
        if g not in groups:
            groups[g] = {"y_true": [], "y_pred": []}
        groups[g]["y_true"].append(int(golden[key]))
        groups[g]["y_pred"].append(int(predictions.get(key, False)))

    for g in sorted(groups):
        yt = groups[g]["y_true"]
        yp = groups[g]["y_pred"]
        tp = sum(1 for t, p in zip(yt, yp) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(yt, yp) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(yt, yp) if t == 1 and p == 0)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        print(f"{g:<20} {len(yt):>5} {tp:>4} {fp:>4} {fn:>4} {prec:>6.3f} {rec:>6.3f} {f1:>6.3f}")


def print_delta(
    golden: dict[str, bool],
    phase1: dict[str, bool],
    phase2: dict[str, bool],
) -> None:
    """Print tests where Phase 2 changed the classification outcome.

    Args:
        golden: Ground truth labels.
        phase1: Phase 1 predicted labels.
        phase2: Phase 1+2 predicted labels.
    """
    print(f"\n{'=' * 60}")
    print("  Phase 2 Delta — Tests Where Phase 2 Changed the Outcome")
    print(f"{'=' * 60}")
    print(f"{'Test':<75} {'P1':>5} {'P2':>5} {'Gold':>5} {'Effect':>10}")
    print("-" * 105)

    for key in sorted(golden):
        p1 = phase1.get(key, False)
        p2 = phase2.get(key, False)
        if p1 != p2:
            gold = golden[key]
            if p2 == gold and p1 != gold:
                effect = "HELPED"
            elif p1 == gold and p2 != gold:
                effect = "HURT"
            else:
                effect = "NEUTRAL"
            short = key.split("::")[-1]
            print(f"{short:<75} {str(p1):>5} {str(p2):>5} {str(gold):>5} {effect:>10}")


def main() -> None:
    """Run the full evaluation and print results."""
    golden = load_golden()
    phase1 = build_phase1_predictions()
    phase2 = build_phase2_predictions()

    keys = sorted(golden.keys())
    y_true = [int(golden[k]) for k in keys]
    y_phase1 = [int(phase1.get(k, False)) for k in keys]
    y_phase2 = [int(phase2.get(k, False)) for k in keys]

    print_report("Phase 1 Only (audit-agent)", y_true, y_phase1)
    print_report("Phase 1 + Phase 2 (audit-agent + review-agent, no expert)", y_true, y_phase2)

    print_per_directory(golden, phase1, "Phase 1 Only")
    print_per_directory(golden, phase2, "Phase 1 + Phase 2")

    print_delta(golden, phase1, phase2)


if __name__ == "__main__":
    main()
