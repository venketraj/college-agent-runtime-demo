# College Agent Runtime Demo

A Streamlit demo that grows one college-assistant question through three stages: a plain language model, retrieval-augmented generation (RAG), and a multi-agent workflow using Model Context Protocol (MCP) tools. It uses fictional handbook and student data.

## What’s Included

- **Plain LLM:** answers without access to the project’s handbook or database.
- **RAG:** retrieves handbook passages and asks the model to cite them; Ollama `nomic-embed-text` embeddings are used when available, with a local TF-IDF fallback.
- **Agents + MCP:** Planner, Researcher, Analyst, Writer, and Reviewer agents work through a goal. The Researcher searches the handbook, the Analyst reads the student database through MCP, and the Writer saves email drafts.
- **Human approval:** drafts are only moved to `outbox/sent/` after approval in the app. No email is sent.
- **Model choices:** Claude via the Anthropic API, Ollama locally, or Auto. Auto tries Claude first when an API key is configured, then tries Ollama if Claude errors before producing response text. Choosing Claude directly does not fall back.

The default models are `claude-sonnet-5` and `qwen3.5:9b`. The model names can be changed in the sidebar or with environment variables.

## Requirements

- Windows and Python 3.10 or newer.
- Ollama for local inference and RAG embeddings. The app can use TF-IDF if the embedding model is unavailable; Ollama is still needed if you want to use the local chat model.
- An Anthropic API key for Claude. Ollama can be used without one.

## Setup

From PowerShell in the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For local models, install and start Ollama, then pull the default chat and embedding models:

```powershell
ollama pull qwen3.5:9b
ollama pull nomic-embed-text
```

To use Claude, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. Alternatively, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set the key there. These files contain secrets and must not be committed.

## Run

Double-click `start_demo.bat` to warm up Ollama, fetch the embedding model, rebuild the sample database, and launch Streamlit. Or run the steps yourself:

```powershell
python data\build_db.py
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. In the sidebar, select **Auto**, **Claude**, or **Ollama**.

## Demo Flow

1. **Plain LLM:** ask one of the sample questions and compare an uncited answer with later stages.
2. **RAG:** ask the same question, inspect retrieved passages and similarity scores, then compare the cited answer. The hostel-curfew question demonstrates a question the handbook does not answer.
3. **Agents + MCP:** run the default attendance goal, inspect each agent’s tool calls and results, review the drafts, and approve them in the app.

All student, mentor, and handbook information is fictional. The MCP database tools are read-only except for saving drafts to the local outbox. Approval only moves draft files to `outbox/sent/`; it does not deliver email.

## Troubleshooting

| Issue | Check |
|---|---|
| Claude is unavailable | Check the API key in `.env` or Streamlit secrets. Auto mode can fall back to Ollama only if Ollama is running and the selected model is installed. |
| Ollama is offline or a model is missing | Start Ollama and pull `qwen3.5:9b` and `nomic-embed-text`, as needed. |
| RAG uses TF-IDF | Confirm Ollama is running and `nomic-embed-text` is installed, then rerun the question. |
| Database is missing | Run `python data\build_db.py`; `data/college.db` is generated and does not need to be shared. |

## Project Layout

```text
app.py                       Streamlit UI for the three demos
core/models.py               Claude and Ollama configuration
core/runner.py               Strands agent execution and event streaming
core/rag.py                  Handbook chunking, embeddings, and search
core/team.py                 Multi-agent workflow and local draft handling
mcp_server/college_server.py  MCP tools and read-only SQLite access
data/handbook/               Fictional handbook source documents
data/build_db.py             Deterministic sample database builder
outbox/                       Runtime draft and approved-file storage
```
