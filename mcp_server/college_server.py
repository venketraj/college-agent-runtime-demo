"""MCP server exposing the (fictional) college database and an email outbox as tools.

Started automatically by the app over stdio. Run standalone for testing:
    python mcp_server/college_server.py
"""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "college.db"
DRAFTS = ROOT / "outbox" / "drafts"

mcp = FastMCP("college-db", log_level="WARNING")


def _rows(sql, params=()):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


@mcp.tool()
def get_low_attendance_students(threshold: float = 75.0) -> str:
    """List students whose attendance is below `threshold` percent in at least one subject,
    with the subject, percentage, and their mentor's name and email."""
    rows = _rows("""
        SELECT s.roll_no, s.name, s.email AS student_email, a.subject,
               ROUND(a.attended * 100.0 / a.total, 1) AS percent,
               m.name AS mentor, m.email AS mentor_email
        FROM attendance a JOIN students s USING(roll_no) JOIN mentors m ON m.id = s.mentor_id
        WHERE a.attended * 100.0 / a.total < ?
        ORDER BY m.name, s.roll_no""", (threshold,))
    return json.dumps(rows, indent=1)


@mcp.tool()
def get_student(roll_no: str) -> str:
    """Get one student's profile (CGPA, arrears, mentor) and per-subject attendance."""
    prof = _rows("""SELECT s.*, m.name AS mentor, m.email AS mentor_email FROM students s
                    JOIN mentors m ON m.id = s.mentor_id WHERE s.roll_no = ?""", (roll_no.upper(),))
    if not prof:
        return f"No student with roll number {roll_no}"
    att = _rows("""SELECT subject, attended, total, ROUND(attended*100.0/total,1) AS percent
                   FROM attendance WHERE roll_no = ?""", (roll_no.upper(),))
    return json.dumps({"profile": prof[0], "attendance": att}, indent=1)


@mcp.tool()
def run_readonly_sql(query: str) -> str:
    """Run a read-only SELECT query. Tables: mentors(id,name,email),
    students(roll_no,name,year,section,mentor_id,email,cgpa,arrears), attendance(roll_no,subject,attended,total)."""
    if not re.match(r"^\s*select\b", query, re.I) or ";" in query.strip().rstrip(";"):
        return "Only a single SELECT statement is allowed."
    return json.dumps(_rows(query)[:50], indent=1)


@mcp.tool()
def save_email_draft(to: str, subject: str, body: str) -> str:
    """Save an email as a DRAFT in the outbox. Drafts are NOT sent until a human approves them in the app."""
    DRAFTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S%f")
    safe = re.sub(r"[^a-z0-9]+", "_", to.lower())[:40]
    path = DRAFTS / f"{stamp}_{safe}.json"
    path.write_text(json.dumps({"to": to, "subject": subject, "body": body,
                                "created": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")
    return f"Draft saved for {to} (awaiting human approval)."


if __name__ == "__main__":
    mcp.run()
