#!/usr/bin/env bash
set -euo pipefail

echo "Parando WebUI (Streamlit)..."
pkill -f "/MoneyPrinterTurbo/.venv/bin/streamlit run ./webui/Main.py" 2>/dev/null || true
pkill -f "MoneyPrinterTurbo.*streamlit run ./webui/Main.py" 2>/dev/null || true

echo "Parando Ideas UI (Streamlit)..."
pkill -f "/MoneyPrinterTurbo/.venv/bin/streamlit run ./webui/Ideas.py" 2>/dev/null || true
pkill -f "MoneyPrinterTurbo.*streamlit run ./webui/Ideas.py" 2>/dev/null || true

if docker ps --format '{{.Names}}' | grep -qx ollama; then
  echo "Parando Ollama (Docker)..."
  docker stop ollama >/dev/null
fi

echo "MoneyPrinterTurbo parado."
