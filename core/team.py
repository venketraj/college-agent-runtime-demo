"""Demo 3: a Strands multi-agent team (Planner → Researcher → Analyst → Writer → Reviewer).

The Planner (an LLM) writes the plan; specialists run in order, each with its own prompt and tools:
- Researcher: RAG tool over the handbook (local @tool)
- Analyst: college database through the MCP server
- Writer: saves email drafts through the MCP server (never sends)
- Reviewer: checks the drafts; a human must still click "Approve" in the UI
"""
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from mcp import StdioServerParameters, stdio_client
from strands import tool
from strands.tools.mcp import MCPClient

from .rag import Index, format_context

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "outbox" / "drafts"
SENT = ROOT / "outbox" / "sent"
SERVER = ROOT / "mcp_server" / "college_server.py"

DEFAULT_GOAL = ("Find every student whose attendance is below 75% in any subject, and draft one email "
                "to each of their mentors listing those students, their subjects and percentages, "
                "and what the handbook says the mentor must do next.")


@dataclass
class Step:
    key: str
    title: str
    icon: str
    system: str
    tools: list = field(default_factory=list)
    prompt: str = ""


def college_mcp() -> MCPClient:
    return MCPClient(lambda: stdio_client(StdioServerParameters(command=sys.executable, args=[str(SERVER)])))


def handbook_tool(index: Index):
    @tool
    def search_handbook(query: str) -> str:
        """Search the CSE student handbook (attendance, mentors, placements, events). Returns numbered passages."""
        return format_context(index.search(query, k=3))
    return search_handbook


def pick(tools, *names):
    return [t for t in tools if t.tool_name in names]


def build_steps(goal: str, index: Index, mcp_tools: list) -> list[Step]:
    return [
        Step("planner", "Planner agent", ":material/account_tree:",
             "You are the planner of a small agent team: researcher (handbook search), analyst (student "
             "database), writer (drafts emails), reviewer (quality check). Break the goal into 4 short "
             "numbered steps, one per team member. Max 80 words. No preamble.",
             prompt=f"Goal: {goal}"),
        Step("researcher", "Researcher agent · RAG", ":material/menu_book:",
             "You are the researcher. Use search_handbook to find the attendance policy and what a mentor "
             "must do when attendance is low. Reply with 3-5 bullet points quoting the rules, with [n] citations.",
             [handbook_tool(index)], "Find the rules relevant to this goal: " + goal),
        Step("analyst", "Analyst agent · MCP database", ":material/database:",
             "You are the data analyst. Call get_low_attendance_students with threshold 75 exactly once. "
             "Then reply with a compact markdown table grouped by mentor: mentor, mentor_email, roll_no, "
             "name, subject, percent. Do not invent rows.",
             pick(mcp_tools, "get_low_attendance_students", "get_student", "run_readonly_sql"),
             "Get the data needed for this goal: " + goal),
        Step("writer", "Writer agent · MCP outbox", ":material/edit_note:",
             "You are the writer. For EACH mentor in the analyst's table, call save_email_draft exactly once "
             "(to = mentor_email). Subject: 'Attendance alert: action needed'. Body: polite, under 150 words, "
             "list that mentor's students with subject and percent, and the required actions from the policy. "
             "Sign as 'CSE Department AI Assistant'. After saving all drafts reply with one line per draft.",
             pick(mcp_tools, "save_email_draft")),
        Step("reviewer", "Reviewer agent", ":material/fact_check:",
             "You are the reviewer. Check the drafts against the data and policy: correct recipients, no "
             "missing students, correct percentages, polite tone. Reply with a short checklist using ✅/⚠️ "
             "and finish with 'READY FOR HUMAN APPROVAL' or 'NEEDS CHANGES'."),
    ]


def step_prompt(step: Step, goal: str, notes: dict) -> str:
    if step.key == "writer":
        return f"Goal: {goal}\n\nPolicy (from researcher):\n{notes.get('researcher', '')}\n\n" \
               f"Data (from analyst):\n{notes.get('analyst', '')}"
    if step.key == "reviewer":
        drafts = "\n\n".join(f"TO: {d['to']}\nSUBJECT: {d['subject']}\n{d['body']}" for d in list_drafts())
        return f"Policy:\n{notes.get('researcher', '')}\n\nData:\n{notes.get('analyst', '')}\n\nDrafts:\n{drafts or '(none)'}"
    return step.prompt


# --- outbox helpers (human-in-the-loop)
def clear_drafts():
    shutil.rmtree(DRAFTS, ignore_errors=True)
    DRAFTS.mkdir(parents=True, exist_ok=True)


def list_drafts() -> list[dict]:
    if not DRAFTS.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) | {"file": p.name} for p in sorted(DRAFTS.glob("*.json"))]


def approve_all() -> int:
    SENT.mkdir(parents=True, exist_ok=True)
    files = list(DRAFTS.glob("*.json"))
    for p in files:
        shutil.move(str(p), SENT / p.name)
    return len(files)
