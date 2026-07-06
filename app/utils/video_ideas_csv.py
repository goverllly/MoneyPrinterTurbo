from __future__ import annotations

import csv
import io
from pathlib import Path

REQUIRED_COLUMNS = ("theme", "script", "keywords")


def parse_ideas_csv(content: str | bytes) -> list[dict[str, str]]:
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("CSV vazio ou sem cabecalho.")

    normalized_fields = {
        (name or "").strip().lower(): name for name in reader.fieldnames if name
    }
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized_fields]
    if missing:
        raise ValueError(
            "CSV invalido. Colunas obrigatorias: theme, script, keywords. "
            f"Faltando: {', '.join(missing)}"
        )

    rows: list[dict[str, str]] = []
    for index, raw in enumerate(reader, start=2):
        theme = str(raw.get(normalized_fields["theme"], "")).strip()
        script = str(raw.get(normalized_fields["script"], "")).strip()
        keywords = str(raw.get(normalized_fields["keywords"], "")).strip()
        if not theme and not script and not keywords:
            continue
        if not theme or not script or not keywords:
            raise ValueError(
                f"Linha {index}: theme, script e keywords sao obrigatorios."
            )
        category_key = normalized_fields.get("category")
        category = str(raw.get(category_key, "")).strip() if category_key else ""
        rows.append(
            {
                "category": category,
                "theme": theme,
                "script": script,
                "keywords": keywords,
            }
        )

    if not rows:
        raise ValueError("Nenhuma ideia valida encontrada no CSV.")
    return rows


def list_local_idea_csv_files(root_dir: str | Path) -> list[Path]:
    ideas_dir = Path(root_dir) / "storage" / "video_ideas"
    if not ideas_dir.is_dir():
        return []
    return sorted(
        ideas_dir.glob("*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
