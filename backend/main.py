import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from automation import execute_command
from assignment_solver import is_assignment_command, solve_assignment
from ai_engine import interpret_command, get_ai_status
from workflow_engine import (
    get_all_workflows,
    save_workflow,
    delete_workflow,
    check_and_run_workflow,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# Models
# ─────────────────────────────────────────

class Command(BaseModel):
    text: str = ""        # primary field — Flutter/frontend sends {"text": "..."}
    command: str = ""     # fallback field — handles older clients sending {"command": "..."}


class WorkflowCreate(BaseModel):
    name: str
    trigger: str
    actions: list[str]


class WorkflowDelete(BaseModel):
    name: str


# ─────────────────────────────────────────
# Helper — normalizes execute_command output
# Safely converts str → dict in case any
# code path returns a plain string instead
# of the expected {"result": "..."} dict
# ─────────────────────────────────────────

def _run_automation(cmd_text: str) -> dict:
    res = execute_command(cmd_text)
    if isinstance(res, str):
        return {"result": res}
    return res


# ─────────────────────────────────────────
# Core routes
# ─────────────────────────────────────────

@app.get("/")
def home():
    return {"message": "FlowForge AI Backend is running ✅"}


@app.post("/execute")
async def execute(cmd: Command):
    """
    Standard command execution endpoint.

    Run commands in a thread pool so long-running operations
    (e.g. npm install during React project creation) don't block
    the event loop or time out the HTTP connection.

    Routing order:
    1. Assignment commands → assignment_solver (never touches automation.py)
    2. All other commands  → execute_command via _run_automation wrapper

    After execution, workflow engine checks if the command triggers
    any saved workflow and fires chained actions automatically.

    execute_command and solve_assignment both return a dict shaped
    as {"result": "..."} or {"result": "...", "options": [...]}
    so return directly — no extra wrapping needed.
    """
    loop = asyncio.get_event_loop()

    # Use cmd.text — fall back to cmd.command for older clients
    input_text = cmd.text.strip() if cmd.text else cmd.command.strip()

    # ── Primary command ──────────────────────────────────────────
    if is_assignment_command(input_text):
        result = await loop.run_in_executor(None, solve_assignment, input_text)
    else:
        result = await loop.run_in_executor(None, _run_automation, input_text)

    # ── Workflow chain check (runs AFTER primary command) ────────
    chained = await loop.run_in_executor(
        None,
        check_and_run_workflow,
        input_text,
        _run_automation,          # passed as callable — automation.py untouched
    )

    if chained:
        chain_summary = " | ".join(f"{c['action']}: {c['result']}" for c in chained)
        # If primary command was not recognized, replace error with workflow result
        if result.get("result", "").startswith("❌ Command not recognized:"):
            result["result"] = f"⚡ Workflow Triggered: {chain_summary}"
        else:
            result["result"] += f"\n⚡ Workflow: {chain_summary}"
        result["workflow_actions"] = chained

    return result


@app.post("/smart-execute")
async def smart_execute(cmd: Command):
    """
    AI-powered command execution endpoint.

    Same as /execute but passes the command through ai_engine first,
    which interprets natural language into a precise command string.

    Example:
      "open my code editor" → interpreted → "open vscode" → execute_command

    Adds 'original' and 'interpreted' fields to the response so the
    frontend can show what the AI understood.
    """
    loop = asyncio.get_event_loop()

    # Use cmd.text — fall back to cmd.command for older clients
    input_text = cmd.text.strip() if cmd.text else cmd.command.strip()

    try:
        # Step 1 — AI interprets natural language into a clean command
        interpreted = await loop.run_in_executor(
            None, interpret_command, input_text
        )

        # Step 2 — Route to correct handler using interpreted command
        if is_assignment_command(input_text):
            raw_result = await loop.run_in_executor(
                None, solve_assignment, input_text
            )
        else:
            raw_result = await loop.run_in_executor(
                None, _run_automation, interpreted
            )

        # Step 3 — Workflow chain check (same as /execute)
        chained = await loop.run_in_executor(
            None,
            check_and_run_workflow,
            interpreted,
            _run_automation,
        )

        if chained:
            chain_summary = " | ".join(f"{c['action']}: {c['result']}" for c in chained)
            if raw_result.get("result", "").startswith("❌ Command not recognized:"):
                raw_result["result"] = f"⚡ Workflow Triggered: {chain_summary}"
            else:
                raw_result["result"] += f"\n⚡ Workflow: {chain_summary}"
            raw_result["workflow_actions"] = chained

        # Step 4 — Add AI metadata to response
        raw_result["original"] = input_text
        raw_result["interpreted"] = interpreted
        return raw_result

    except Exception as e:
        return {
            "result": f"❌ Error: {str(e)}",
            "options": [],
            "original": input_text,
            "interpreted": input_text,
        }


# ─────────────────────────────────────────
# Workflow routes
# ─────────────────────────────────────────

@app.get("/workflows")
def list_workflows():
    """Return all saved workflows."""
    return {"workflows": get_all_workflows()}


@app.post("/workflows")
def create_workflow(body: WorkflowCreate):
    """Create or overwrite a workflow."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Workflow name cannot be empty")
    if not body.trigger.strip():
        raise HTTPException(status_code=400, detail="Trigger cannot be empty")
    if not body.actions:
        raise HTTPException(status_code=400, detail="At least one action required")

    workflow = save_workflow(body.name, body.trigger, body.actions)
    return {"message": f"Workflow '{workflow['name']}' saved ✅", "workflow": workflow}


@app.delete("/workflows")
def remove_workflow(body: WorkflowDelete):
    """Delete a workflow by name."""
    deleted = delete_workflow(body.name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{body.name}' not found")
    return {"message": f"Workflow '{body.name}' deleted 🗑️"}


# ─────────────────────────────────────────
# AI Engine route
# ─────────────────────────────────────────

@app.get("/ai-status")
def ai_status_check():
    """Health check for the AI engine."""
    try:
        return get_ai_status()
    except Exception as e:
        return {"status": "error", "error": str(e)}