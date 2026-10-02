"""Runs a Strands agent in a background thread and streams its events to the Streamlit thread.

Events yielded: ("model", label) · ("text", chunk) · ("tool", name, input) · ("tool_result", name, text)
                ("fallback", reason) · ("warn", message) · ("done", final_text) · ("error", message)
If a model fails before producing any output, the next candidate (e.g. local Ollama) is tried.
"""
import queue
import threading

from strands import Agent
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent
from strands.types.exceptions import MaxTokensReachedException

from .models import Candidate


def _result_text(result) -> str:
    parts = [c.get("text", "") for c in (result or {}).get("content", []) if isinstance(c, dict)]
    return "\n".join(p for p in parts if p)


def _run_once(cand: Candidate, system: str, prompt: str, tools: list, q: queue.Queue):
    def on_event(**kw):
        if "data" in kw and kw["data"]:
            q.put(("text", kw["data"]))

    agent = Agent(model=cand.build(), system_prompt=system, tools=tools or [], callback_handler=on_event)
    agent.hooks.add_callback(BeforeToolCallEvent,
                             lambda e: q.put(("tool", e.tool_use["name"], e.tool_use.get("input"))))
    agent.hooks.add_callback(AfterToolCallEvent,
                             lambda e: q.put(("tool_result", e.tool_use["name"], _result_text(e.result))))
    return str(agent(prompt)).strip()


def stream_agent(cands: list[Candidate], system: str, prompt: str, tools: list | None = None):
    if not cands:
        yield ("error", "No model available. Add a Claude API key or start Ollama.")
        return
    for i, cand in enumerate(cands):
        q: queue.Queue = queue.Queue()
        produced = False

        def work(c=cand):
            try:
                q.put(("done", _run_once(c, system, prompt, tools, q)))
            except MaxTokensReachedException:  # keep the partial answer that was already streamed
                q.put(("warn", "The answer hit the model's length limit, so it may be cut off."))
                q.put(("done", ""))
            except Exception as e:  # network / auth / model errors
                q.put(("error", f"{type(e).__name__}: {e}"))

        threading.Thread(target=work, daemon=True).start()
        yield ("model", cand.label)
        while True:
            ev = q.get()
            if ev[0] == "error" and not produced and i + 1 < len(cands):
                yield ("fallback", f"{cand.label} failed ({ev[1][:120]}). Switching to {cands[i + 1].label}.")
                break
            if ev[0] in ("text", "tool"):
                produced = True
            yield ev
            if ev[0] in ("done", "error"):
                return
