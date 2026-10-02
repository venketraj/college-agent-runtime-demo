@echo off
REM One-click demo launcher: warms up Ollama, rebuilds data, opens the app.
cd /d "%~dp0"
echo Warming up local models (so the first answer is fast)...
start /b ollama run qwen3.5:9b "hi" >nul 2>&1
ollama pull nomic-embed-text >nul 2>&1
python data\build_db.py
python -m streamlit run app.py --server.port 8501 --server.headless false
