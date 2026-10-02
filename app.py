"""From ChatGPT to AI Agents: live demo app.

Tabs: 1) Plain LLM  2) RAG over the handbook  3) Multi-agent team with MCP tools + human approval.
Models: Claude API (online) with automatic fallback to a local Ollama model. Agents: AWS Strands.
Run:  streamlit run app.py
"""
import os
import time

import streamlit as st

from core import team
from core.models import DEFAULT_CLAUDE, DEFAULT_OLLAMA, Settings, load_env, candidates, ollama_models
from core.rag import Index, format_context, load_chunks
from core.runner import stream_agent

st.set_page_config(page_title="From ChatGPT to AI Agents", page_icon=":material/smart_toy:", layout="wide")

QUESTIONS = [
    "What is the condonation fee if my attendance is 70% in the CSE department at Vel Tech High Tech?",
    "When is TechVerse 2026 and what is the registration fee?",
    "Where and when does the NeuralNest AI club meet? Cite your source.",
    "What is the hostel curfew time?",  # not in the handbook → RAG should say it doesn't know
]
PLAIN_SYSTEM = "You are a helpful college assistant chatbot. Answer the student's question in under 120 words."
RAG_SYSTEM = ("You are the CSE department assistant. Answer ONLY from the numbered handbook passages in the "
              "user message and cite them like [1]. If the passages do not contain the answer, say exactly: "
              "\"I don't know — the handbook doesn't cover that.\" Keep answers under 120 words.")


# ---------------------------------------------------------------- shared state
def secret_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


@st.cache_resource(show_spinner="Indexing the handbook…")
def get_index(_stamp: float) -> Index:
    return Index(load_chunks())


def handbook_stamp() -> float:
    return max(p.stat().st_mtime for p in team.ROOT.joinpath("data", "handbook").glob("*.md"))


for _k in ("q_plain", "q_rag"):
    st.session_state.setdefault(_k, QUESTIONS[0])

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Model settings")
    choice = st.segmented_control("Provider", ["Auto", "Claude", "Ollama"], default="Auto",
                                  help="Auto = Claude API first, local Ollama if Claude fails or is offline.")
    load_env()  # re-read demo/.env each run, so a newly saved key works without restarting
    key = secret_key() or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        st.warning("No Claude key found. Add ANTHROPIC_API_KEY to demo/.env and save. Using local Ollama until then.",
                   icon=":material/key_off:")
    claude_model = st.text_input("Claude model", DEFAULT_CLAUDE)
    local = ollama_models()
    ollama_model = st.selectbox("Ollama model", local or ["(Ollama not running)"],
                                index=next((i for i, m in enumerate(local) if m == DEFAULT_OLLAMA), 0))
    st.caption(f"Claude key: {':green[set]' if key else ':orange[missing]'} · "
               f"Ollama: {':green[' + str(len(local)) + ' models]' if local else ':red[offline]'}")
    st.divider()
    st.caption("Demo data is fictional. Emails are only saved as drafts; nothing is really sent.")

settings = Settings({"Auto": "auto", "Claude": "claude", "Ollama": "ollama"}.get(choice or "Auto"),
                    claude_model, ollama_model, key)
CANDS = candidates(settings)


def render_stream(events, box):
    """Write streamed text into `box`; show model badge, fallback warnings and tool calls. Returns final text."""
    text, model = "", ""
    for ev in events:
        kind = ev[0]
        if kind == "model":
            model = ev[1]
        elif kind == "fallback":
            st.toast(ev[1], icon=":material/swap_horiz:")
        elif kind == "warn":
            st.warning(ev[1], icon=":material/content_cut:")
        elif kind == "text":
            text += ev[1]
            box.markdown(text + "▌")
        elif kind == "tool":
            st.markdown(f":material/build: **Tool call** `{ev[1]}` `{ev[2]}`")
        elif kind == "tool_result":
            with st.expander(f"Result of `{ev[1]}`", icon=":material/output:"):
                st.code(ev[2][:3000] or "(empty)", language="json", wrap_lines=True)
        elif kind == "done":
            text = text or ev[1]
        elif kind == "error":
            st.error(ev[1], icon=":material/error:")
    box.markdown(text)
    if model:
        st.caption(f":material/memory: Answered by {model}")
    return text


def question_picker(key: str):
    pick = st.pills("Try a question", [f"Q{i + 1}" for i in range(len(QUESTIONS))], key=f"pick_{key}",
                    help="\n\n".join(f"Q{i + 1}: {q}" for i, q in enumerate(QUESTIONS)))
    if pick and st.session_state.get(f"last_{key}") != pick:
        st.session_state[f"last_{key}"] = pick
        st.session_state[f"q_{key}"] = QUESTIONS[int(pick[1:]) - 1]
    return st.text_area("Question", key=f"q_{key}", height=80)


# ---------------------------------------------------------------- header
st.title("From ChatGPT to AI Agents")
st.caption("Same question, three levels of intelligence · Claude API + Ollama fallback · AWS Strands Agents · MCP")
tab1, tab2, tab3 = st.tabs([":material/chat: 1 · Plain LLM", ":material/menu_book: 2 · RAG",
                            ":material/groups: 3 · Agents + MCP"])

# ---------------------------------------------------------------- 1. Plain LLM
with tab1:
    st.subheader("Demo 1 · A plain LLM, no tools, no documents")
    st.info("Watch for confident answers with no real source. That's a hallucination.", icon=":material/visibility:")
    q = question_picker("plain")
    if st.button("Ask the plain LLM", type="primary", icon=":material/send:", key="ask_plain"):
        with st.chat_message("assistant"):
            render_stream(stream_agent(CANDS, PLAIN_SYSTEM, q), st.empty())

# ---------------------------------------------------------------- 2. RAG
with tab2:
    st.subheader("Demo 2 · Retrieval-Augmented Generation over our handbook")
    st.info("Watch for answers quoting our documents with [n] citations, and \"I don't know\" when the "
            "handbook is silent.", icon=":material/visibility:")
    q2 = question_picker("rag")
    if st.button("Retrieve + answer", type="primary", icon=":material/search:", key="ask_rag"):
        index = get_index(handbook_stamp())
        with st.chat_message("assistant"):
            with st.status("Retrieving relevant chunks", type="step") as s:
                t0 = time.time()
                hits = index.search(q2, k=4)
                st.caption(f"{len(index.chunks)} chunks indexed · {index.method} · {1000 * (time.time() - t0):.0f} ms")
                for i, (score, c) in enumerate(hits):
                    with st.expander(f"[{i + 1}] {c.section} · similarity {score:.2f}", icon=":material/description:"):
                        st.markdown(c.text)
                        st.caption(c.source)
                s.update(label=f"Retrieved {len(hits)} chunks", state="complete")
            with st.status("Generating a grounded answer", type="step") as s:
                prompt = f"Handbook passages:\n{format_context(hits)}\n\nQuestion: {q2}"
                render_stream(stream_agent(CANDS, RAG_SYSTEM, prompt), st.empty())
                s.update(label="Grounded answer", state="complete", expanded=True)

# ---------------------------------------------------------------- 3. Agents + MCP
with tab3:
    st.subheader("Demo 3 · A multi-agent team using tools through MCP")
    st.info("Watch each agent's step, the MCP tool calls, the reviewer's check, and the human approval at the end.",
            icon=":material/visibility:")
    goal = st.text_area("Goal for the agent team", team.DEFAULT_GOAL, height=90)
    if st.button("Run the agent team", type="primary", icon=":material/rocket_launch:", key="run_team"):
        team.clear_drafts()
        index = get_index(handbook_stamp())
        notes, t_start = {}, time.time()
        try:
            mcp = team.college_mcp()
            with mcp:
                mcp_tools = mcp.list_tools_sync()
                st.caption(f":material/hub: Connected to MCP server `college-db` · tools: "
                           + ", ".join(f"`{t.tool_name}`" for t in mcp_tools))
                for step in team.build_steps(goal, index, mcp_tools):
                    with st.status(step.title, type="step", expanded=True) as s:
                        st.caption(f"Tools: {', '.join(t.tool_name for t in step.tools) or 'none'}")
                        out = render_stream(stream_agent(CANDS, step.system, team.step_prompt(step, goal, notes),
                                                         step.tools), st.empty())
                        notes[step.key] = out
                        s.update(label=f"{step.title} · done", state="complete", expanded=step.key != "researcher")
            st.success(f"Team finished in {time.time() - t_start:.0f} s", icon=":material/check_circle:")
        except Exception as e:
            st.error(f"Agent run failed: {e}", icon=":material/error:")

    drafts = team.list_drafts()
    if drafts:
        st.markdown(f"#### :material/outgoing_mail: Human in the loop · {len(drafts)} draft(s) awaiting approval")
        for d in drafts:
            with st.expander(f"To: {d['to']} · {d['subject']}", icon=":material/mail:"):
                st.markdown(d["body"])
        if st.button("Approve & send all", type="primary", icon=":material/verified:"):
            n = team.approve_all()
            st.toast(f"{n} email(s) approved and moved to outbox/sent (simulated send).", icon=":material/send:")
            st.balloons()
            time.sleep(1.2)
            st.rerun()
