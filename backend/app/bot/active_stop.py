import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppSessionState


async def _get_state(session: AsyncSession, wa_id: str) -> WhatsAppSessionState | None:
    return (
        await session.execute(select(WhatsAppSessionState).where(WhatsAppSessionState.wa_id == wa_id))
    ).scalar_one_or_none()


async def resolve_active_stop(session: AsyncSession, wa_id: str, today: date):
    # Plan 4 reemplaza el cuerpo: deriva la parada de `stops` por fecha.
    st = await _get_state(session, wa_id)
    if st:
        data = json.loads(st.payload_json or "{}")
        ov = data.get("active_stop")
        if ov:
            return ov.get("stop_slug"), ov.get("city_name"), ov.get("currency_code", "USD")
    return None, None, "USD"


async def set_active_stop_override(session, wa_id, stop_slug, city_name, currency_code):
    st = await _get_state(session, wa_id)
    payload = {"active_stop": {"stop_slug": stop_slug, "city_name": city_name, "currency_code": currency_code}}
    if st is None:
        session.add(WhatsAppSessionState(wa_id=wa_id, owner=wa_id, payload_json=json.dumps(payload)))
    else:
        st.payload_json = json.dumps(payload)
    await session.commit()
