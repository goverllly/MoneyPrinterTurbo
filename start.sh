#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/bin:$PATH"

OLLAMA_CONTAINER="ollama"
OLLAMA_URL="http://127.0.0.1:11434"
OLLAMA_MODEL_DEFAULT="qwen2.5:7b"
WEBUI_URL="http://127.0.0.1:8501"

if ! command -v uv >/dev/null 2>&1; then
  echo "Erro: uv nao encontrado. Instale com: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Erro: docker nao encontrado."
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${OLLAMA_CONTAINER}"; then
  echo "Iniciando Ollama (Docker)..."
  if docker ps -a --format '{{.Names}}' | grep -qx "${OLLAMA_CONTAINER}"; then
    docker start "${OLLAMA_CONTAINER}" >/dev/null
  else
    docker run -d --name "${OLLAMA_CONTAINER}" -p 11434:11434 -v ollama_data:/root/.ollama ollama/ollama >/dev/null
  fi
fi

echo "Aguardando Ollama ficar pronto..."
for _ in $(seq 1 30); do
  if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  echo "Erro: Ollama nao respondeu em ${OLLAMA_URL}"
  exit 1
fi

if [ ! -f config.toml ]; then
  cp config.example.toml config.toml
  sed -i \
    -e 's/^llm_provider = .*/llm_provider = "ollama"/' \
    -e 's|^ollama_base_url = .*|ollama_base_url = "http://localhost:11434/v1"|' \
    -e "s/^ollama_model_name = .*/ollama_model_name = \"${OLLAMA_MODEL_DEFAULT}\"/" \
    config.toml
  echo "config.toml criado com provider Ollama (${OLLAMA_MODEL_DEFAULT}). Revise pexels_api_keys se necessario."
fi

OLLAMA_MODEL="$(
  grep -E '^\s*ollama_model_name\s*=' config.toml 2>/dev/null \
    | head -1 \
    | sed -E 's/^[^=]*=\s*"([^"]*)".*/\1/' \
    || true
)"
OLLAMA_MODEL="${OLLAMA_MODEL:-$OLLAMA_MODEL_DEFAULT}"

if ! docker exec "${OLLAMA_CONTAINER}" ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qxF "${OLLAMA_MODEL}"; then
  echo "Baixando modelo Ollama: ${OLLAMA_MODEL}..."
  docker exec "${OLLAMA_CONTAINER}" ollama pull "${OLLAMA_MODEL}"
else
  echo "Modelo Ollama pronto: ${OLLAMA_MODEL}"
fi

echo "Subindo WebUI em ${WEBUI_URL}"
exec uv run streamlit run ./webui/Main.py \
  --browser.gatherUsageStats=False \
  --server.showEmailPrompt=False \
  --server.port 8501 \
  --server.address 127.0.0.1
