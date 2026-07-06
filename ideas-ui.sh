#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "Erro: uv nao encontrado. Instale com: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx ollama; then
  echo "Ollama nao esta rodando. Execute ./start.sh primeiro ou inicie o container manualmente."
  exit 1
fi

echo "UI de ideias em http://127.0.0.1:8502"
exec uv run streamlit run ./webui/Ideas.py \
  --browser.gatherUsageStats=False \
  --server.showEmailPrompt=False \
  --server.port 8502 \
  --server.address 127.0.0.1
