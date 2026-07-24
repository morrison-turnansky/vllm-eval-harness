"""Pooled cross-umbrella metrics for nightly triage eval.

Loads all per-case triage outputs and golden data, computes a single
macro F1 and ARI from the combined 65-issue pool. Run after eval
completes all cases.

Usage:
    python pooled_metrics.py eval/runs/<run-id>
"""

import csv
import json
import sys
from pathlib import Path

from sklearn.metrics import (
    adjusted_rand_score,
    classification_report,
    f1_score,
)

CLASSIFICATION_MAP = {
    "TORCH_REGRESSION": "torch",
    "TRITON_REGRESSION": "triton",
    "VLLM_BUG": "vllm",
    "PRE_EXISTING": "pre_existing",
}

ALL_LABELS = ["torch", "triton", "vllm", "pre_existing"]

UMBRELLA_ISSUES = ["187473", "180899", "175426", "170433"]


def load_golden(datasets_dir: Path, umbrella_issue: str) -> list[dict]:
    path = datasets_dir / f"dataset_{umbrella_issue}.csv"
    with open(path) as f:
        return list(csv.DictReader(f))


def load_triage_output(run_dir: Path, umbrella_issue: str) -> list[dict]:
    output_path = run_dir / umbrella_issue / "triage-output.json"
    if not output_path.exists():
        return []
    with open(output_path) as f:
        return json.load(f)


def load_golden_mapping(cases_dir: Path, umbrella_issue: str) -> dict:
    mapping_path = cases_dir / umbrella_issue / "golden_mapping.json"
    if not mapping_path.exists():
        return {}
    with open(mapping_path) as f:
        return json.load(f)


def map_classification(raw_classification: str) -> str:
    return CLASSIFICATION_MAP.get(raw_classification, raw_classification.lower())


def compute_pooled_classification(run_dir: Path, datasets_dir: Path) -> None:
    all_golden_types = []
    all_predicted_types = []
    per_umbrella = {}

    for umbrella in UMBRELLA_ISSUES:
        golden_rows = load_golden(datasets_dir, umbrella)
        groups = load_triage_output(run_dir, umbrella)

        if not golden_rows:
            print(f"  {umbrella}: no golden data, skipping")
            continue
        if not groups:
            print(f"  {umbrella}: no triage output, skipping")
            continue

        golden_types = [row["regression_type"] for row in golden_rows]
        remaining_groups = list(groups)
        predicted_types = []

        for golden_row in golden_rows:
            best_group = None
            best_member_count = 0
            for group in remaining_groups:
                member_count = len(group.get("members", []))
                if member_count > best_member_count:
                    best_group = group
                    best_member_count = member_count

            if best_group:
                predicted_types.append(map_classification(best_group.get("classification", "")))
                remaining_groups = [g for g in remaining_groups if g is not best_group]
            else:
                predicted_types.append("unclassified")

        umbrella_f1 = float(
            f1_score(golden_types, predicted_types, labels=ALL_LABELS, average="macro", zero_division=0)
        )
        per_umbrella[umbrella] = {
            "f1": umbrella_f1,
            "total": len(golden_rows),
            "unmatched_groups": len(remaining_groups),
        }

        all_golden_types.extend(golden_types)
        all_predicted_types.extend(predicted_types)

    if not all_golden_types:
        print("No data to score.")
        return

    pooled_f1 = f1_score(all_golden_types, all_predicted_types, labels=ALL_LABELS, average="macro", zero_division=0)

    print(f"\n{'=' * 60}")
    print(f"POOLED CLASSIFICATION (n={len(all_golden_types)})")
    print(f"{'=' * 60}")
    print(f"Pooled Macro F1: {pooled_f1:.3f}")
    print("\nPer-class breakdown:")
    print(classification_report(all_golden_types, all_predicted_types, labels=ALL_LABELS, zero_division=0))

    print("Per-umbrella F1:")
    for umbrella, stats in per_umbrella.items():
        print(f"  #{umbrella}: F1={stats['f1']:.3f} (n={stats['total']}, {stats['unmatched_groups']} unmatched groups)")

    mean_f1 = sum(s["f1"] for s in per_umbrella.values()) / len(per_umbrella)
    print(f"\nMean-of-F1s: {mean_f1:.3f} (what the harness reports)")
    print(f"Pooled F1:   {pooled_f1:.3f} (true cross-dataset score)")


def compute_pooled_grouping(run_dir: Path, cases_dir: Path) -> None:
    all_true_labels = []
    all_pred_labels = []
    per_umbrella = {}

    for umbrella in UMBRELLA_ISSUES:
        golden_mapping = load_golden_mapping(cases_dir, umbrella)
        groups = load_triage_output(run_dir, umbrella)

        if not golden_mapping:
            print(f"  {umbrella}: no golden_mapping.json, skipping")
            continue
        if not groups:
            print(f"  {umbrella}: no triage output, skipping")
            continue

        golden_lookup = {}
        for issue_number, failures in golden_mapping.items():
            for failure in failures:
                key = f"{failure[0]}::{failure[1]}"
                golden_lookup[key] = f"{umbrella}_{issue_number}"

        pred_lookup = {}
        for group in groups:
            group_id = group.get("group_id", 0)
            for member in group.get("members", []):
                key = f"{member['job_name']}::{member['test_id']}"
                pred_lookup[key] = f"{umbrella}_{group_id}"

        shared_keys = sorted(set(golden_lookup.keys()) & set(pred_lookup.keys()))
        if len(shared_keys) < 2:
            print(f"  {umbrella}: only {len(shared_keys)} shared failures, skipping")
            continue

        true_labels = [golden_lookup[k] for k in shared_keys]
        pred_labels = [pred_lookup[k] for k in shared_keys]

        umbrella_ari = float(adjusted_rand_score(true_labels, pred_labels))
        per_umbrella[umbrella] = {
            "ari": umbrella_ari,
            "shared": len(shared_keys),
            "golden_clusters": len(golden_mapping),
            "pred_clusters": len(groups),
        }

        all_true_labels.extend(true_labels)
        all_pred_labels.extend(pred_labels)

    if len(all_true_labels) < 2:
        print("Not enough data for pooled ARI.")
        return

    pooled_ari = adjusted_rand_score(all_true_labels, all_pred_labels)

    print(f"\n{'=' * 60}")
    print(f"POOLED GROUPING (n={len(all_true_labels)} failures)")
    print(f"{'=' * 60}")
    print(f"Pooled ARI: {pooled_ari:.3f}")

    print("\nPer-umbrella ARI:")
    for umbrella, stats in per_umbrella.items():
        print(
            f"  #{umbrella}: ARI={stats['ari']:.3f} "
            f"(shared={stats['shared']}, golden={stats['golden_clusters']} clusters, "
            f"pred={stats['pred_clusters']} clusters)"
        )

    mean_ari = sum(s["ari"] for s in per_umbrella.values()) / len(per_umbrella)
    print(f"\nMean-of-ARIs: {mean_ari:.3f} (what the harness reports)")
    print(f"Pooled ARI:  {pooled_ari:.3f} (true cross-dataset score)")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <run-dir>")
        print(f"  e.g.: {sys.argv[0]} eval/runs/2026-07-24-opus")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    datasets_dir = Path(__file__).parent / "datasets"
    cases_dir = Path(__file__).parent / "nightly-cases"

    print(f"Run: {run_dir}")
    print(f"Datasets: {datasets_dir}")

    compute_pooled_classification(run_dir, datasets_dir)
    compute_pooled_grouping(run_dir, cases_dir)


if __name__ == "__main__":
    main()
