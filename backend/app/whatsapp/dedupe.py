from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppDedupe

# Cuánto le damos a un mensaje claimed para terminar antes de asumir que el
# proceso se murió a mitad. Holgado a propósito: el peor caso de pasarse de
# corto es procesar dos veces el mismo gasto; el de quedarse largo es que un
# reintento de Meta (que llega en minutos) todavía no re-claimee.
_IN_FLIGHT_GRACE = timedelta(minutes=10)


async def claim_wamid(session: AsyncSession, wamid: str) -> bool:
    """True si este proceso se queda con el mensaje.

    Tres casos:
    - sin fila → claim nuevo. El INSERT puede fallar igual si Meta entrega el
      mismo `wamid` dos veces en paralelo (reintento por timeout). Sin capturar
      el IntegrityError eso era un 500 → Meta reintenta → bucle.
    - fila con `processed_at` → ya lo terminamos, nunca se repite.
    - fila sin `processed_at` → alguien lo está procesando. Dentro de la
      ventana de gracia se descarta; pasada la ventana se RE-CLAIMEA: el
      proceso anterior murió a mitad (deploy, OOM) y el reintento de Meta es la
      única chance de que ese gasto no se pierda en silencio.
    """
    now = datetime.utcnow()
    exists = (
        await session.execute(select(WhatsAppDedupe).where(WhatsAppDedupe.wamid == wamid))
    ).scalar_one_or_none()
    if exists is not None:
        if exists.processed_at is not None:
            return False
        if now - exists.created_at < _IN_FLIGHT_GRACE:
            return False
        exists.created_at = now  # reinicia la ventana: este intento es el vivo
        await session.commit()
        return True
    try:
        session.add(WhatsAppDedupe(wamid=wamid, created_at=now))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def mark_processed(session: AsyncSession, wamid: str) -> None:
    """Cierra el claim: a partir de acá el mensaje no se reprocesa nunca más."""
    await session.execute(
        update(WhatsAppDedupe)
        .where(WhatsAppDedupe.wamid == wamid)
        .values(processed_at=datetime.utcnow())
    )
    await session.commit()


async def purge_old(session: AsyncSession, older_than_hours: int = 48) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    res = await session.execute(
        delete(WhatsAppDedupe).where(WhatsAppDedupe.created_at < cutoff)
    )
    await session.commit()
    return res.rowcount or 0
