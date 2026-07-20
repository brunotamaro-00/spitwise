"""Stops locales: paradas que existen solo en Spitwise, no en Andiamo.

Andiamo es la fuente de verdad del itinerario, pero hay tramos donde los dos
viajeros no están en el mismo lugar. Un stop local con owner_username imputa
los gastos de ese usuario a su propia parada, sin tocar el itinerario común
ni el contrato con Andiamo (ver sync_stops: is_local queda fuera de la
reconciliación).
"""
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Stop

logger = logging.getLogger(__name__)

PITITAS_SLUG = "pititas"

# Katia viaja con sus amigas mientras Bruno está en Portugal. departure es
# exclusivo => cubre del 4 al 11 de sept; el 12 ya es Estrasburgo para ambos.
_PITITAS = dict(
    name="Pititas",
    country=None,
    country_flag="👭",
    arrival_date=date(2026, 9, 4),
    departure_date=date(2026, 9, 12),
    currency_code="EUR",
    timezone="Europe/Paris",
)

# Orden de fallback si el stop de Portugal todavía no está sincronizado: se
# corrige solo en el próximo arranque, cuando el snapshot ya exista.
_FALLBACK_ORDER = 7


async def _order_near_portugal(session: AsyncSession) -> int:
    """Orden del stop que cubre el 4 de sept, para que Pititas quede pegada a
    Portugal en el recorrido."""
    d = _PITITAS["arrival_date"]
    row = (
        await session.execute(
            select(Stop.order)
            .where(
                Stop.is_local.is_(False),
                Stop.arrival_date <= d,
                Stop.departure_date > d,
            )
            .order_by(Stop.order)
        )
    ).scalars().first()
    return row if row is not None else _FALLBACK_ORDER


async def _sync_counterpart_owner(session: AsyncSession, owner: str) -> None:
    """El reverso de Pititas: mientras Katia está allá, las paradas del
    itinerario común que caen enteras en ese tramo son solo de Bruno.

    Sin esto la asimetría era rara: Bruno no veía Pititas, pero Katia sí veía
    Portugal, donde nunca estuvo. La ventana sale de las fechas de Pititas, así
    que si Andiamo mueve el itinerario esto se recalcula solo en el próximo
    arranque (mismo criterio que `_order_near_portugal`).

    Contención total, no solapamiento: una parada que arranca antes del 4 o
    termina después del 11 la vivieron los dos (aunque sea un día), y ocultársela
    a Katia le borraría noches propias. En esas puntas alcanza con la prioridad
    por dueño de `active_stop._by_priority` para imputar bien por fecha.
    """
    from app.users import get_trip_users

    try:
        a, b = await get_trip_users(session)
    except Exception:
        # Menos de 2 usuarios (arranque en frío): sin contraparte que imputar.
        logger.warning("counterpart_owner_skipped: no hay 2 usuarios todavía")
        return
    other = next((u.username for u in (a, b) if (u.username or "").lower() != owner), None)
    if not other:
        return
    other = other.lower()

    start, end = _PITITAS["arrival_date"], _PITITAS["departure_date"]
    stops = (
        await session.execute(select(Stop).where(Stop.is_local.is_(False)))
    ).scalars().all()
    for s in stops:
        contained = bool(
            s.arrival_date
            and s.departure_date
            and s.arrival_date >= start
            and s.departure_date <= end
        )
        if contained:
            s.owner_username = other
        elif (s.owner_username or "").lower() == other:
            # Ya no solapa (fechas movidas en Andiamo): vuelve a ser compartida.
            s.owner_username = None
    await session.commit()


async def seed_local_stops(session: AsyncSession) -> None:
    """Idempotente: crea/actualiza el stop Pititas si hay owner configurado."""
    owner = (get_settings().pititas_owner or "").strip().lower()
    if not owner:
        return

    # Antes de tocar la sesión: un SELECT posterior haría autoflush de una fila
    # todavía sin `order` (NOT NULL).
    order = await _order_near_portugal(session)
    row = (
        await session.execute(select(Stop).where(Stop.slug == PITITAS_SLUG))
    ).scalar_one_or_none()
    if row is None:
        row = Stop(slug=PITITAS_SLUG)
        session.add(row)

    for k, v in _PITITAS.items():
        setattr(row, k, v)
    row.order = order
    row.owner_username = owner
    row.is_local = True
    row.is_transit = False
    row.is_candidate = False
    row.is_flex_margin = False
    row.is_archived = False
    await session.commit()
    logger.info("local_stop_seeded slug=%s owner=%s", PITITAS_SLUG, owner)
    await _sync_counterpart_owner(session, owner)
