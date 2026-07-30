"""Gate de cobertura prompt → escenario.

Los tres prompts del bot (parser, Q&A financiero, Q&A de viaje) son código de
producto: cambiarlos cambia el comportamiento sin que ningún test unitario se
entere. Este gate no juzga el contenido — pide que cada cambio venga con los
escenarios que lo ejercitan, declarados en `prompt_manifest.json` junto al
comando `--only` para reproducirlos.

Si este test falla:
  1. correr los escenarios declarados para ese prompt (o agregar uno nuevo al
     runner que corresponda, con su id estable);
  2. actualizar el `sha256` del prompt en `tests/prompt_manifest.json`;
  3. dejar en el PR el comando `--only` que se corrió.
"""
import hashlib
import json
from pathlib import Path

MANIFEST = Path(__file__).parent / "prompt_manifest.json"


def _prompts() -> dict[str, str]:
    from app.bot import qa, trip_qa
    from app.llm import client

    return {
        "app.llm.client._SYSTEM": client._SYSTEM,
        "app.bot.qa._SYSTEM": qa._SYSTEM,
        "app.bot.trip_qa._SYSTEM": trip_qa._SYSTEM,
    }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_manifest_covers_every_prompt():
    manifest = json.loads(MANIFEST.read_text())
    assert set(manifest) == set(_prompts()), (
        "el manifiesto tiene que listar exactamente los prompts del bot; "
        f"faltan/sobran: {set(manifest) ^ set(_prompts())}"
    )


def test_prompt_changes_come_with_scenarios():
    manifest = json.loads(MANIFEST.read_text())
    stale = {
        name: (_sha(text), manifest[name]["sha256"])
        for name, text in _prompts().items()
        if manifest[name]["sha256"] != _sha(text)
    }
    assert not stale, (
        "Cambió un prompt sin actualizar el manifiesto de escenarios.\n"
        + "\n".join(
            f"  {name}: sha real {real[:12]}… ≠ manifiesto {declared[:12]}…\n"
            f"    escenarios declarados: {manifest[name]['scenarios']}\n"
            f"    reproducir: {manifest[name]['command']}"
            for name, (real, declared) in stale.items()
        )
        + "\n  Corré esos escenarios, actualizá 'sha256' y dejá el comando en el PR."
    )


def test_declared_scenarios_exist():
    """Los ids declarados tienen que existir en los runners (no un typo)."""
    import scripts.bot_scenario_runner as fin
    import scripts.bot_trip_scenario_runner as trip

    known = {c.id for c in fin.CONVERSATIONS} | {c.id for c in trip.CONVERSATIONS}
    manifest = json.loads(MANIFEST.read_text())
    declared = {sid for entry in manifest.values() for sid in entry["scenarios"]}
    assert declared <= known, f"ids de escenario inexistentes: {sorted(declared - known)}"


def test_every_prompt_declares_at_least_one_scenario():
    manifest = json.loads(MANIFEST.read_text())
    empty = [name for name, e in manifest.items() if not e["scenarios"]]
    assert not empty, f"prompts sin escenario que los cubra: {empty}"
