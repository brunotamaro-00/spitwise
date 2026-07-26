"""Estandarización de descripciones de movimientos.

El prompt del parser ya pide sentence case con nombres propios capitalizados;
esto es la red de seguridad server-side en los bordes de escritura (bot y API):
primera letra en mayúscula y los nombres propios del viaje (nombres de Stops)
con su capitalización canónica. Solo "sube" mayúsculas — nunca baja las que ya
vengan puestas — así es idempotente y respeta lo que escribió el usuario.
"""
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def fold(s: str) -> str:
    """Minúsculas sin acentos, para comparar texto que tipeó un humano.
    'Zurich' y 'Zúrich' son la misma parada; el teclado del celular no siempre
    pone la tilde."""
    s = unicodedata.normalize("NFD", s.casefold())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def normalize_description(desc: str | None, proper_nouns=()) -> str | None:
    """strip + colapsar espacios; primera letra en mayúscula; tokens que
    matchean un nombre propio conocido toman la capitalización del nombre."""
    if desc is None:
        return None
    s = " ".join(str(desc).split())
    if not s:
        return None

    lookup: dict[str, str] = {}
    for name in proper_nouns:
        for tok in (name or "").split():
            # Solo tokens con sustancia: evita capitalizar "de"/"la" de nombres
            # compuestos en medio de una frase.
            if len(tok) >= 3 and tok[:1].isalpha():
                lookup[tok.casefold()] = tok

    def _lift(m: re.Match) -> str:
        w = m.group(0)
        canonical = lookup.get(w.casefold())
        return canonical if canonical and w.islower() else w

    s = _WORD.sub(_lift, s)
    return s[:1].upper() + s[1:]


async def load_proper_nouns(session: AsyncSession) -> list[str]:
    """Nombres propios del viaje = nombres de Stops (incluidas archivadas y
    locales): el vocabulario sale de la DB, no de un hardcode."""
    from app.db.models import Stop

    rows = (await session.execute(select(Stop.name))).scalars().all()
    return [n for n in rows if n]
