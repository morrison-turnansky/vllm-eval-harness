#!/usr/bin/env python3
"""after_each hook: generate FP/FN report from audit output vs golden.csv.

Reads audit-cc.json and audit-not-cc.json from the case workspace,
compares predictions against golden.csv, and writes fp_fn_report.md.

Env vars (injected by the eval harness):
    CASE_WORKSPACE  - absolute path to the case workspace directory
    AGENT_EVAL_CONFIG - absolute path to eval.yaml (golden.csv is a sibling)
"""

import csv
import json
import os
import sys
from pathlib import Path


def load_golden(golden_path: Path) -> dict[str, bool]:
    """Load expert-verified labels from golden.csv."""
    golden: dict[str, bool] = {}
    with open(golden_path) as f:
        for row in csv.DictReader(f):
            golden[row["test_name"]] = row["is_coincidentally_correct"] == "True"
    return golden


def extract_predictions(case_ws: Path) -> dict[str, dict]:
    """Extract predictions with metadata from audit JSON files."""
    preds: dict[str, dict] = {}
    for name in ("audit-cc.json", "audit-not-cc.json"):
        path = case_ws / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for c in data.get("candidates", []):
            key = f"{c['file']}::{c['candidate']}"
            preds[key] = {
                "predicted_cc": c.get("coincidentally_correct", False),
                "classification": c.get("classification", ""),
                "c1": c.get("c1_weak_oracle", ""),
                "c2": c.get("c2_realistic_breakage", ""),
                "c3": c.get("c3_no_strong_contract", ""),
                "comparison": c.get("comparison", ""),
                "oracle": c.get("oracle", ""),
            }
    return preds


def compute_errors(
    golden: dict[str, bool],
    preds: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Compute false positives and false negatives."""
    fps: list[dict] = []
    fns: list[dict] = []
    for test_name, gold_label in golden.items():
        if test_name not in preds:
            continue
        pred = preds[test_name]
        if pred["predicted_cc"] and not gold_label:
            fps.append({"test": test_name, **pred})
        elif not pred["predicted_cc"] and gold_label:
            fns.append({"test": test_name, **pred})
    return fps, fns


def render_report(fps: list[dict], fns: list[dict], total_overlap: int) -> str:
    """Render FP/FN report as markdown."""
    lines = ["# FP/FN Classification Report", ""]

    tp = total_overlap - len(fps) - len(fns)
    lines.append(f"**Overlap with golden:** {total_overlap} tests")
    lines.append(f"**TP:** {tp}  **FP:** {len(fps)}  **FN:** {len(fns)}")
    lines.append("")

    if fps:
        lines.append("## False Positives (predicted CC, actually not)")
        lines.append("")
        for fp in fps:
            short = fp["test"].split("::")[-1]
            lines.append(f"### {short}")
            lines.append(f"- **Test:** `{fp['test']}`")
            lines.append(f"- **Classification:** {fp['classification']}")
            lines.append(f"- **Comparison:** {fp['comparison']}")
            lines.append(f"- **Oracle:** {fp['oracle']}")
            lines.append(f"- **C1 (weak oracle):** {fp['c1']}")
            lines.append(f"- **C2 (realistic breakage):** {fp['c2']}")
            lines.append(f"- **C3 (no strong contract):** {fp['c3']}")
            lines.append("")
    else:
        lines.append("## False Positives")
        lines.append("")
        lines.append("None.")
        lines.append("")

    if fns:
        lines.append("## False Negatives (predicted not CC, actually is)")
        lines.append("")
        for fn in fns:
            short = fn["test"].split("::")[-1]
            lines.append(f"### {short}")
            lines.append(f"- **Test:** `{fn['test']}`")
            lines.append(f"- **Classification:** {fn['classification']}")
            lines.append(f"- **Comparison:** {fn['comparison']}")
            lines.append(f"- **Oracle:** {fn['oracle']}")
            lines.append(f"- **C1 (weak oracle):** {fn['c1']}")
            lines.append(f"- **C2 (realistic breakage):** {fn['c2']}")
            lines.append(f"- **C3 (no strong contract):** {fn['c3']}")
            lines.append("")
    else:
        lines.append("## False Negatives")
        lines.append("")
        lines.append("None.")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    case_ws = Path(os.environ.get("CASE_WORKSPACE", ""))
    if not case_ws.is_dir():
        print("ERROR: CASE_WORKSPACE not set or not a directory", file=sys.stderr)
        sys.exit(1)

    config_path = Path(os.environ.get("AGENT_EVAL_CONFIG", ""))
    if not config_path.is_file():
        print("ERROR: AGENT_EVAL_CONFIG not set or not a file", file=sys.stderr)
        sys.exit(1)

    golden_path = config_path.parent / "golden.csv"
    if not golden_path.exists():
        print(f"WARNING: golden.csv not found at {golden_path}", file=sys.stderr)
        return

    golden = load_golden(golden_path)
    preds = extract_predictions(case_ws)

    if not preds:
        print("WARNING: no predictions found in case workspace", file=sys.stderr)
        Path(case_ws / "fp_fn_report.md").write_text(
            "# FP/FN Classification Report\n\nNo predictions found.\n"
        )
        return

    total_overlap = sum(1 for t in golden if t in preds)
    fps, fns = compute_errors(golden, preds)
    report = render_report(fps, fns, total_overlap)
    Path(case_ws / "fp_fn_report.md").write_text(report)
    print(f"FP/FN report: {len(fps)} FP, {len(fns)} FN ({total_overlap} overlap)")


if __name__ == "__main__":
    main()
