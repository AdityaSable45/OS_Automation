"""
workflow_engine.py
──────────────────
Stores and runs multi-step workflow chains.
automation.py is NEVER imported or modified here.
main.py calls this AFTER execute_command() returns.
"""

import json
import os
from typing import Callable

WORKFLOW_FILE = os.path.join(os.path.dirname(__file__), "workflows.json")


# ─────────────────────────────────────────
# Storage helpers
# ─────────────────────────────────────────

def _load() -> list[dict]:
    if not os.path.exists(WORKFLOW_FILE):
        return []
    try:
        with open(WORKFLOW_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save(workflows: list[dict]) -> None:
    with open(WORKFLOW_FILE, "w") as f:
        json.dump(workflows, f, indent=2)


# ─────────────────────────────────────────
# Public CRUD API
# ─────────────────────────────────────────

def get_all_workflows() -> list[dict]:
    """Return all saved workflows."""
    return _load()


def save_workflow(name: str, trigger: str, actions: list[str]) -> dict:
    """
    Save a new workflow (or overwrite one with same name).
    Returns the saved workflow dict.
    """
    workflows = _load()

    # Remove existing with same name (case-insensitive)
    workflows = [w for w in workflows if w["name"].lower() != name.lower()]

    new_workflow = {
        "name": name,
        "trigger": trigger.strip().lower(),
        "actions": [a.strip() for a in actions if a.strip()],
    }
    workflows.append(new_workflow)
    _save(workflows)
    return new_workflow


def delete_workflow(name: str) -> bool:
    """Delete workflow by name. Returns True if found and deleted."""
    workflows = _load()
    filtered = [w for w in workflows if w["name"].lower() != name.lower()]
    if len(filtered) == len(workflows):
        return False  # not found
    _save(filtered)
    return True


# ─────────────────────────────────────────
# Trigger matching & execution
# ─────────────────────────────────────────

def _matches(command: str, trigger: str) -> bool:
    """
    True if the user's command matches a workflow trigger.
    Uses simple substring match (case-insensitive).
    Example: trigger="open vscode" matches command="open vscode please"
    """
    return trigger in command.strip().lower()


def check_and_run_workflow(
    command: str,
    executor: Callable[[str], dict],
) -> list[dict]:
    """
    Called from main.py AFTER the primary command has already run.

    Scans all workflows for a matching trigger.
    If found, runs each chained action via `executor`
    (which is execute_command from automation.py, passed in by main.py).

    Returns list of action results so main.py can append them to the response.
    Example return:
        [
            {"action": "open chrome",   "result": "Opened Chrome"},
            {"action": "open spotify",  "result": "Opened Spotify"},
        ]
    """
    workflows = _load()
    results = []

    for workflow in workflows:
        if _matches(command, workflow["trigger"]) or _matches(command, workflow["name"]):
            for action in workflow["actions"]:
                try:
                    res = executor(action)
                    results.append({
                        "action": action,
                        "result": res.get("result", "Done"),
                    })
                except Exception as e:
                    results.append({
                        "action": action,
                        "result": f"Error: {e}",
                    })
            break  # only run first matching workflow

    return results