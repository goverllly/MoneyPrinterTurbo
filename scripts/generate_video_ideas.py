#!/usr/bin/env python3
"""
Generate unique short-video ideas (theme + PT script + EN keywords) via Ollama.

Outputs a timestamped CSV under storage/video_ideas/ and appends to all_ideas.csv.
Tracks history in storage/video_ideas/history.json to avoid repeating the same
theme + script combination.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import toml
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
STORAGE_DIR = ROOT / "storage" / "video_ideas"
HISTORY_FILE = STORAGE_DIR / "history.json"
SEED_FILE = Path(__file__).resolve().parent / "video_ideas_seed.json"
SEED_CSV = STORAGE_DIR / "seed_ideas.csv"
MASTER_CSV = STORAGE_DIR / "all_ideas.csv"
CSV_COLUMNS = ["category", "theme", "script", "keywords", "generated_at"]

CATEGORIES = ("finances", "peace_of_mind", "self_help")
CATEGORY_LABELS = {
    "finances": "finanças",
    "peace_of_mind": "paz de espírito",
    "self_help": "autoajuda",
}

SYSTEM_PROMPT = """You create short-form vertical video ideas for a Brazilian Portuguese audience.
Return ONLY a valid JSON array. No markdown, no commentary.

Each array item must be an object with exactly these keys:
- "category": one of "finances", "peace_of_mind", "self_help"
- "theme": short theme title in Portuguese (max 80 chars)
- "script": narration in Portuguese, 25-35 words, fits ~10 seconds of speech
- "keywords": exactly 5 English stock-footage search terms, comma-separated

Rules:
- Mix categories across the batch when possible.
- Scripts must be original, punchy, and suitable for TikTok/Reels/Shorts.
- Keywords must be in English only (good for Pexels/Pixabay).
- Never repeat or closely paraphrase any item from the exclusion list.
- All items in the batch must be distinct from each other.
"""


def load_ollama_client() -> tuple[OpenAI, str]:
    config_path = ROOT / "config.toml"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"config.toml not found at {config_path}. Run ./start.sh first or copy config.example.toml."
        )

    app_config = toml.load(config_path).get("app", {})
    base_url = app_config.get("ollama_base_url") or "http://localhost:11434/v1"
    model_name = app_config.get("ollama_model_name") or "qwen2.5:7b"
    return OpenAI(api_key="ollama", base_url=base_url), model_name


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def entry_fingerprint(theme: str, script: str) -> str:
    payload = f"{normalize_text(theme)}|{normalize_text(script)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_history() -> dict:
    if not HISTORY_FILE.is_file():
        return import_seed_history()
    with HISTORY_FILE.open(encoding="utf-8") as fp:
        data = json.load(fp)
    data.setdefault("entries", [])
    return data


def import_seed_history() -> dict:
    history = {"entries": []}
    if not SEED_FILE.is_file():
        return history

    generated_at = "seed"
    seed_rows: list[dict] = []
    with SEED_FILE.open(encoding="utf-8") as fp:
        seed_items = json.load(fp)

    for item in seed_items:
        theme = str(item.get("theme", "")).strip()
        script = str(item.get("script", "")).strip()
        keywords = str(item.get("keywords", "")).strip()
        category = str(item.get("category", "")).strip()
        if not theme or not script or not keywords:
            continue
        row = {
            "fingerprint": entry_fingerprint(theme, script),
            "category": category,
            "theme": theme,
            "script": script,
            "keywords": keywords,
            "generated_at": generated_at,
        }
        history["entries"].append(row)
        seed_rows.append(row)

    if seed_rows:
        export_seed_csv(seed_rows)
    return history


def export_seed_csv(rows: list[dict]) -> Path:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(SEED_CSV, rows, "seed")
    return SEED_CSV


def save_history(history: dict) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as fp:
        json.dump(history, fp, ensure_ascii=False, indent=2)


def known_fingerprints(history: dict) -> set[str]:
    return {entry["fingerprint"] for entry in history["entries"] if entry.get("fingerprint")}


def build_exclusion_list(history: dict, limit: int = 40) -> str:
    entries = history["entries"][-limit:]
    if not entries:
        return "(none yet)"
    lines = []
    for item in entries:
        lines.append(
            f'- theme="{item["theme"]}" | script="{item["script"][:120]}..."'
            if len(item["script"]) > 120
            else f'- theme="{item["theme"]}" | script="{item["script"]}"'
        )
    return "\n".join(lines)


def extract_json_array(content: str) -> list:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", content)
        if not match:
            raise ValueError("Model response did not contain a JSON array.") from None
        data = json.loads(match.group(0))

    if not isinstance(data, list):
        raise ValueError("Model response must be a JSON array.")
    return data


def validate_item(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None

    category = str(raw.get("category", "")).strip()
    theme = str(raw.get("theme", "")).strip()
    script = str(raw.get("script", "")).strip()
    keywords = str(raw.get("keywords", "")).strip()

    if category not in CATEGORIES or not theme or not script or not keywords:
        return None

    keyword_parts = [part.strip() for part in keywords.split(",") if part.strip()]
    if len(keyword_parts) < 5:
        return None

    return {
        "category": category,
        "theme": theme,
        "script": script,
        "keywords": ", ".join(keyword_parts[:5]),
        "fingerprint": entry_fingerprint(theme, script),
    }


def generate_batch(
    client: OpenAI,
    model_name: str,
    count: int,
    history: dict,
) -> list[dict]:
    exclusion = build_exclusion_list(history)
    user_prompt = f"""Generate exactly {count} unique video ideas.

Use these categories:
- finances ({CATEGORY_LABELS["finances"]})
- peace_of_mind ({CATEGORY_LABELS["peace_of_mind"]})
- self_help ({CATEGORY_LABELS["self_help"]})

Do NOT repeat or closely paraphrase any of these previously used ideas:
{exclusion}
"""

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
    )

    content = response.choices[0].message.content or ""
    parsed = extract_json_array(content)

    valid: list[dict] = []
    for item in parsed:
        validated = validate_item(item)
        if validated:
            valid.append(validated)
    return valid


def collect_unique_ideas(
    client: OpenAI,
    model_name: str,
    count: int,
    history: dict,
    max_attempts: int = 5,
) -> list[dict]:
    known = known_fingerprints(history)
    selected: list[dict] = []
    seen_this_run: set[str] = set()

    for attempt in range(1, max_attempts + 1):
        remaining = count - len(selected)
        if remaining <= 0:
            break

        batch = generate_batch(client, model_name, remaining + 2, history)
        added = 0
        for item in batch:
            fp = item["fingerprint"]
            if fp in known or fp in seen_this_run:
                continue
            selected.append(item)
            seen_this_run.add(fp)
            added += 1
            if len(selected) >= count:
                break

        if len(selected) >= count:
            break

        print(
            f"Tentativa {attempt}/{max_attempts}: {added} ideia(s) nova(s), "
            f"{len(selected)}/{count} no total.",
            file=sys.stderr,
        )

    if len(selected) < count:
        raise RuntimeError(
            f"Nao foi possivel gerar {count} ideias unicas apos {max_attempts} tentativas. "
            f"Geradas: {len(selected)}."
        )

    return selected[:count]


def write_csv(path: Path, rows: list[dict], generated_at: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "category": row["category"],
                    "theme": row["theme"],
                    "script": row["script"],
                    "keywords": row["keywords"],
                    "generated_at": generated_at,
                }
            )


def append_master_csv(rows: list[dict], generated_at: str) -> None:
    write_header = not MASTER_CSV.exists()
    with MASTER_CSV.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "category": row["category"],
                    "theme": row["theme"],
                    "script": row["script"],
                    "keywords": row["keywords"],
                    "generated_at": generated_at,
                }
            )


def update_history(history: dict, rows: list[dict], generated_at: str) -> None:
    for row in rows:
        history["entries"].append(
            {
                "fingerprint": row["fingerprint"],
                "category": row["category"],
                "theme": row["theme"],
                "script": row["script"],
                "keywords": row["keywords"],
                "generated_at": generated_at,
            }
        )
    save_history(history)


def persist_ideas(ideas: list[dict], generated_at: str | None = None) -> Path:
    generated_at = generated_at or datetime.now(timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = STORAGE_DIR / f"ideas_{stamp}.csv"

    history = load_history()
    write_csv(output_csv, ideas, generated_at)
    append_master_csv(ideas, generated_at)
    update_history(history, ideas, generated_at)
    return output_csv


def generate_ideas(
    count: int = 5,
    max_attempts: int = 5,
    *,
    save: bool = True,
) -> tuple[list[dict], str | None]:
    if count < 1:
        raise ValueError("count deve ser >= 1")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    history = load_history()
    client, model_name = load_ollama_client()

    ideas = collect_unique_ideas(
        client=client,
        model_name=model_name,
        count=count,
        history=history,
        max_attempts=max_attempts,
    )

    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    output_csv = None
    if save:
        output_csv = persist_ideas(ideas, generated_at)

    return ideas, str(output_csv) if output_csv else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate unique video ideas (theme + PT script + EN keywords) via Ollama."
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=5,
        help="Number of ideas to generate (default: 5).",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="Max LLM retries when duplicates are detected (default: 5).",
    )
    parser.add_argument(
        "--export-seed",
        action="store_true",
        help="Export scripts/video_ideas_seed.json to storage/video_ideas/seed_ideas.csv and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.count < 1:
        print("Erro: --count deve ser >= 1.", file=sys.stderr)
        return 1

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    if args.export_seed:
        if not SEED_FILE.is_file():
            print(f"Erro: seed nao encontrado em {SEED_FILE}", file=sys.stderr)
            return 1
        with SEED_FILE.open(encoding="utf-8") as fp:
            seed_items = json.load(fp)
        rows = []
        for item in seed_items:
            validated = validate_item(item)
            if validated:
                rows.append(validated)
        if not rows:
            print("Erro: nenhum item valido no seed.", file=sys.stderr)
            return 1
        path = export_seed_csv(rows)
        print(f"CSV seed exportado: {path} ({len(rows)} linhas)")
        return 0

    _, model_name = load_ollama_client()
    print(f"Gerando {args.count} ideia(s) com Ollama ({model_name})...", file=sys.stderr)
    ideas, output_csv = generate_ideas(
        count=args.count,
        max_attempts=args.max_attempts,
        save=True,
    )

    history = load_history()
    print(f"CSV gerado: {output_csv}")
    print(f"Historico atualizado: {HISTORY_FILE} ({len(history['entries'])} entradas)")
    print(f"Master CSV: {MASTER_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
