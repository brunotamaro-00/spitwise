"""Eval ad-hoc del canal documentos contra los fixtures de documents-check/.

DESCARTABLE: existe solo para validar la interpretación vision con documentos
reales una vez; se borra junto con la carpeta de fixtures. El ground truth se
parsea EN RUNTIME de la tabla del README de esa carpeta — nada de fechas,
ciudades ni kinds transcriptos acá (regla del proyecto: los fixtures nunca
entran a la lógica ni al repo).

Corre SOLO la extracción (OpenAI vision real, sin Meta ni subida a Andiamo).
El catálogo de paradas sale del Andiamo real (GET /api/stops, read-only) con
ANDIAMO_URL + TRIP_SHARED_API_KEY del .env — el mismo contexto que tendría el
bot en producción.

    cd backend
    .venv/bin/python scripts/bot_document_runner.py
    .venv/bin/python scripts/bot_document_runner.py --only 3,7 --dir /ruta/a/documents-check

Reescribe scripts/bot_document_scenarios.md en cada corrida (sin historial).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=False)

DEFAULT_DIR = "/Users/brunotamaro/Desktop/Trip/documents-check"
OUT_PATH = BACKEND / "scripts" / "bot_document_scenarios.md"


@dataclass
class GroundTruth:
    file_pattern: str
    path: Path | None
    doc_date: str
    city: str
    kind: str
    description: str


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _resolve_file(pattern: str, docs_dir: Path) -> Path | None:
    """El README puede abreviar nombres largos con '…': matchear por prefijo/sufijo."""
    exact = docs_dir / pattern
    if exact.exists():
        return exact
    if "…" in pattern:
        pre, _, post = pattern.partition("…")
        # El sufijo del README puede omitir partes del nombre real: alcanza
        # con que el prefijo identifique un único PDF.
        candidates = [p for p in sorted(docs_dir.glob("*.pdf")) if p.name.startswith(pre.strip())]
        exact = [p for p in candidates if p.name.endswith(post)]
        if len(exact) == 1:
            return exact[0]
        if len(candidates) == 1:
            return candidates[0]
    return None


def parse_ground_truth(docs_dir: Path) -> list[GroundTruth]:
    """Tabla del README: | `archivo` | **fecha** | ciudad | Kind (`enum`) | desc |"""
    text = (docs_dir / "README.md").read_text(encoding="utf-8")
    out: list[GroundTruth] = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or "---" in cells[0] or cells[0].lower().startswith("archivo"):
            continue
        fname = cells[0].strip("`").strip()
        if not fname.lower().endswith(".pdf"):
            continue
        doc_date = cells[1].replace("*", "").strip()
        kind_m = re.search(r"`(\w+)`", cells[3])
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", doc_date) or not kind_m:
            continue
        out.append(GroundTruth(
            file_pattern=fname, path=_resolve_file(fname, docs_dir),
            doc_date=doc_date, city=cells[2], kind=kind_m.group(1),
            description=cells[4],
        ))
    return out


async def load_catalog() -> list[dict]:
    from app.andiamo import fetch_stops
    data = await fetch_stops()
    return [{
        "slug": s["slug"], "name": s["name"], "country": s.get("country"),
        "arrival_date": s.get("arrivalDate"), "departure_date": s.get("departureDate"),
    } for s in data if not s.get("isCandidate")]


def expected_slug(city: str, catalog: list[dict]) -> str | None:
    target = _norm(city)
    for s in catalog:
        if _norm(s["name"]) == target:
            return s["slug"]
    return None


def check(value, expected) -> str:
    return "✅" if value == expected else "❌"


async def run(args: argparse.Namespace) -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: falta OPENAI_API_KEY en spitwise/.env")
        return 1
    from app.bot.documents.kinds import DOC_KINDS
    from app.config import get_settings
    from app.llm.vision import make_vision_llm

    docs_dir = Path(args.dir)
    gts = parse_ground_truth(docs_dir)
    if not gts:
        print(f"ERROR: no encontré ground truth en {docs_dir}/README.md")
        return 1
    if args.only:
        wanted = {int(i) for i in args.only.split(",")}
        gts = [gt for i, gt in enumerate(gts, 1) if i in wanted]

    catalog = await load_catalog()
    vision = make_vision_llm()
    today = date.today()
    s = get_settings()

    lines = [
        "# Eval canal documentos — documents-check (ad-hoc, descartable)",
        "",
        f"Corrida: {today.isoformat()} · modelo `{s.openai_vision_model}` · "
        f"{len(catalog)} paradas del Andiamo real · hoy={today.isoformat()}",
        "",
        "Este archivo se reescribe entero en cada corrida. Ground truth = README "
        "de la carpeta de fixtures (parseado en runtime).",
        "",
    ]
    summary: list[tuple[str, str, str, str, float]] = []
    failures = 0

    for i, gt in enumerate(gts, 1):
        print(f"[{i}/{len(gts)}] {gt.file_pattern} ...", flush=True)
        lines.append(f"## {i}. `{gt.file_pattern}`")
        lines.append("")
        if gt.path is None:
            lines.append("❌ Archivo no encontrado en la carpeta de fixtures.")
            lines.append("")
            failures += 1
            summary.append((gt.file_pattern, "❌", "❌", "❌", 0.0))
            continue

        exp_slug = expected_slug(gt.city, catalog)
        t0 = time.perf_counter()
        try:
            ext = await vision.extract(
                gt.path.read_bytes(), "application/pdf", today=today,
                stops=catalog, kinds=DOC_KINDS, caption=None, filename=gt.path.name,
            )
        except Exception as exc:  # una falla no corta la corrida
            lines.append(f"❌ Extracción falló: {exc}")
            lines.append("")
            failures += 1
            summary.append((gt.file_pattern, "❌", "❌", "❌", time.perf_counter() - t0))
            continue
        dt = time.perf_counter() - t0

        d_ok = check(ext.get("doc_date"), gt.doc_date)
        c_ok = check(ext.get("stop_slug"), exp_slug)
        k_ok = check(ext.get("kind"), gt.kind)
        if "❌" in (d_ok, c_ok, k_ok):
            failures += 1
        summary.append((gt.file_pattern, d_ok, c_ok, k_ok, dt))

        lines += [
            f"- Fecha: {d_ok} `{ext.get('doc_date')}` (esperado `{gt.doc_date}`)",
            f"- Parada: {c_ok} `{ext.get('stop_slug')}` (esperado `{exp_slug}` — {gt.city})",
            f"- Kind: {k_ok} `{ext.get('kind')}` (esperado `{gt.kind}`)",
            f"- Label: `{ext.get('label')}`",
            f"- Nota: `{ext.get('note')}`",
            f"- travel_doc={ext.get('is_travel_doc')} · confidence={ext.get('confidence')} · {dt:.1f}s",
            f"- Referencia (README): {gt.description}",
            "",
        ]

    lines += ["## Resumen", "", "| Doc | Fecha | Parada | Kind | seg |", "|---|---|---|---|---|"]
    for name, d_ok, c_ok, k_ok, dt in summary:
        lines.append(f"| `{name[:48]}` | {d_ok} | {c_ok} | {k_ok} | {dt:.1f} |")
    total = len(summary)
    lines += ["", f"**{total - failures}/{total} documentos con los 3 campos correctos.**", ""]

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{total - failures}/{total} OK → {OUT_PATH}")
    return 0 if failures == 0 else 1


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eval vision de documentos contra ground truth.")
    p.add_argument("--dir", default=DEFAULT_DIR, help="Carpeta de fixtures con README.md")
    p.add_argument("--only", default="", help="Índices 1-based, ej: 1,4")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(run(parse_args())))
