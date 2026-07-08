"""Build golden.csv from Phase 1, Phase 2, and expert-verified SUMMARY.md."""

import csv
import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"

NOT_CC_FILES: list[str] = [
    "basic_not_cc.json",
    "compile_not_cc.json",
    "distributed_not_cc.json",
    "entrypoints_not_cc.json",
    "lora_not_cc.json",
    "v1_e2e_not_cc.json",
]

REVIEW_FILES: list[str] = [
    "review_output_1.json",
    "review_output_2.json",
    "review_output_3.json",
]

EXPERT_REVERSE_TO_CC: set[str] = {
    "test_batch_completions",
    "test_batch_completions[beam_search_cross_position]",
    "test_batch_completions[streaming_batch]",
}

EXPERT_MANUAL_NOT_CC: set[str] = {
    "test_single_chat_session_image_base64encoded_beamsearch",
}

EXPERT_OVERRIDE_TO_CC: set[str] = {
    "test_qwen36_moe_mixed_2d_3d_lora_tp2",
    "test_qwen36_moe_mixed_2d_3d_lora_tp4",
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


def test_name(candidate: dict) -> str:
    """Build a canonical test identifier from a candidate dict.

    Args:
        candidate: Candidate dict with 'file' and 'candidate' keys.

    Returns:
        String in the format 'file::function'.
    """
    return f"{candidate['file']}::{candidate['candidate']}"


def build_golden() -> tuple[dict[str, bool], list[str]]:
    """Build the golden label mapping from raw audit data and expert overrides.

    Returns:
        Tuple of (rows, flags) where rows maps test_name to is_cc and flags
        lists notable overrides or anomalies.
    """
    rows: dict[str, bool] = {}
    flags: list[str] = []

    for fname in NOT_CC_FILES:
        for c in load_json(fname)["candidates"]:
            key = test_name(c)
            if key in rows:
                continue
            is_cc = c["candidate"] in EXPERT_OVERRIDE_TO_CC
            if is_cc:
                flags.append(
                    f"FN_OVERRIDE: {key} — Phase 1 said {c['classification']}, expert says CC"
                )
            rows[key] = is_cc

    review_map: dict[str, dict] = {}
    for fname in REVIEW_FILES:
        for c in load_json(fname)["candidates"]:
            review_map[test_name(c)] = c

    for c in load_json("all_cc.json")["candidates"]:
        key = test_name(c)
        if key in rows:
            continue

        review = review_map.get(key)
        if review is None:
            flags.append(f"NO_REVIEW: {key}")
            rows[key] = True
            continue

        if c["candidate"] in EXPERT_REVERSE_TO_CC:
            rows[key] = True
        elif c["candidate"] in EXPERT_MANUAL_NOT_CC:
            rows[key] = False
        elif review["review"].startswith("RECLASSIFY"):
            rows[key] = False
        else:
            rows[key] = True

    return rows, flags


def main() -> None:
    """Build and write golden.csv, printing summary and flags."""
    rows, flags = build_golden()

    cc_count = sum(1 for v in rows.values() if v)
    print(f"Total: {len(rows)}, CC: {cc_count}, Not CC: {len(rows) - cc_count}")

    if flags:
        print(f"\nFlags ({len(flags)}):")
        for f in flags:
            print(f"  {f}")

    if cc_count != 38:
        print(f"\nERROR: expected 38 CC, got {cc_count}")
        sys.exit(1)

    out_path = Path(__file__).parent / "golden.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["test_name", "is_coincidentally_correct"])
        for key in sorted(rows):
            writer.writerow([key, rows[key]])

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
