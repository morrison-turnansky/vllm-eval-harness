#!/usr/bin/env python3
"""before_each hook: prepare the eval workspace so the audit-agent can find
vLLM test files and write output to the correct location.

Env vars (injected by the eval harness):
    CASE_WORKSPACE  – absolute path to the case workspace directory
    AGENT_EVAL_CONFIG – absolute path to eval.yaml
"""

import json
import os
import sys
from pathlib import Path

VLLM_REPO = Path("/home/devuser/projects/vllm")


def symlink_tests(case_ws: Path) -> None:
    """Symlink vLLM tests/ into the workspace so relative paths resolve."""
    target = case_ws / "tests"
    if target.exists() or target.is_symlink():
        return
    src = VLLM_REPO / "tests"
    if not src.is_dir():
        print(f"WARNING: vLLM tests dir not found at {src}", file=sys.stderr)
        return
    target.symlink_to(src)


def add_additional_directory(case_ws: Path) -> None:
    """Add the vLLM repo to .claude/settings.json additionalDirectories."""
    settings_path = case_ws / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    with open(settings_path) as f:
        settings = json.load(f)
    dirs = settings.get("permissions", {}).get("additionalDirectories", [])
    vllm_str = str(VLLM_REPO)
    if vllm_str not in dirs:
        dirs.append(vllm_str)
        settings.setdefault("permissions", {})["additionalDirectories"] = dirs
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")


def trust_workspace(case_ws: Path) -> None:
    """Add workspace trust entry to ~/.claude.json."""
    claude_json = Path.home() / ".claude.json"
    if not claude_json.exists():
        return
    with open(claude_json) as f:
        data = json.load(f)
    key = str(case_ws)
    if key in data.get("projects", {}):
        existing = data["projects"][key]
        if existing.get("hasTrustDialogAccepted"):
            return
    data.setdefault("projects", {})[key] = {
        "allowedTools": [],
        "hasTrustDialogAccepted": True,
        "hasCompletedProjectOnboarding": True,
        "hasClaudeMdExternalIncludesApproved": True,
    }
    with open(claude_json, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main() -> None:
    case_ws = Path(os.environ.get("CASE_WORKSPACE", ""))
    if not case_ws.is_dir():
        print("ERROR: CASE_WORKSPACE not set or not a directory", file=sys.stderr)
        sys.exit(1)

    symlink_tests(case_ws)
    add_additional_directory(case_ws)
    trust_workspace(case_ws)


if __name__ == "__main__":
    main()
