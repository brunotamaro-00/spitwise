from datetime import date, datetime
from decimal import Decimal
import secrets

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    whatsapp_wa_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    icon: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (
        Index("ix_movements_stop_slug", "stop_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # expense (default) | settlement
    type: Mapped[str] = mapped_column(String(12), server_default=text("'expense'"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'USD'"))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), server_default=text("'1.0'"))
    # frankfurter | dolarapi | manual | fallback
    fx_source: Mapped[str] = mapped_column(String(16), server_default=text("'manual'"))
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # shared | payer_only | other_only  (ignorado para settlement)
    split: Mapped[str] = mapped_column(String(12), server_default=text("'shared'"))
    description: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    stop_slug: Mapped[str | None] = mapped_column(String(80))
    city_name: Mapped[str | None] = mapped_column(String(120))
    raw_message: Mapped[str | None] = mapped_column(Text)
    # Los movimientos nacidos de un mismo mensaje multi-gasto comparten clave
    # (interno del bot: habilita "borrar" del batch completo).
    batch_key: Mapped[str | None] = mapped_column(String(16))
    # Fecha en que se paga/pagó el gasto. NULL = el día de carga (caso normal).
    payment_date: Mapped[date | None] = mapped_column(Date)
    # confirmed | pending | awaiting. pending = payment_date futura con TC proxy;
    # al vencer, la liquidación lazy (app/due.py) recalcula el TC real y lo deja
    # en `awaiting` (esperando confirmación manual en la web); confirm lo pasa a
    # confirmed. pending y awaiting NO entran al balance (ver balance.UNSETTLED).
    # Columna real (no derivada de la fecha): un pending vencido con Frankfurter
    # caído sigue pending hasta poder liquidarse.
    status: Mapped[str] = mapped_column(String(12), server_default=text("'confirmed'"), index=True)
    # Cashback de tarjeta declarado al cargar el gasto. `amount` sigue siendo el
    # BRUTO tipeado (lo que dice el ticket); el neto sale de app/cashback.py y se
    # hornea en amount_usd (de ahí lo toman balance/spend/analytics). NULL = sin
    # cashback (net == gross, comportamiento histórico intacto).
    #   pct    -> cashback_value es el % (2 = 2%)
    #   amount -> cashback_value es un monto fijo en la moneda del gasto
    cashback_kind: Mapped[str | None] = mapped_column(String(8))
    cashback_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    category: Mapped["Category | None"] = relationship()


class Stop(Base):
    """Snapshot local del itinerario (fuente de verdad = Andiamo)."""

    __tablename__ = "stops"

    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(80))
    country_flag: Mapped[str | None] = mapped_column(String(16))
    arrival_date: Mapped[date | None] = mapped_column(Date)
    departure_date: Mapped[date | None] = mapped_column(Date)
    currency_code: Mapped[str | None] = mapped_column(String(3))
    timezone: Mapped[str | None] = mapped_column(String(64))
    is_transit: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_candidate: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_flex_margin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Borrado en Andiamo pero con movimientos asociados: se conserva para agrupar.
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Stop local: no existe en Andiamo, así que la reconciliación del sync lo ignora.
    is_local: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Si está seteado, el stop solo aplica a ese usuario al imputar por fecha.
    owner_username: Mapped[str | None] = mapped_column(String(100))
    synced_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class StopBudget(Base):
    """Target de gasto diario de "vivir" de una parada, en USD **por persona**.

    "Vivir" = todo menos alojamiento y generales (ver `app/budget.py`). Es un
    objetivo cargado a mano en la web, no un límite ni un dato de Andiamo.

    Tabla propia y no una columna en `Stop` porque `Stop` es un snapshot puro
    del itinerario: la reconciliación del sync (`andiamo.py`) borra la fila de
    una parada que desapareció de Andiamo y no tiene movimientos, y el target
    es dato autoral que no tiene por qué morir con eso. Por lo mismo `stop_slug`
    no lleva FK.

    Un target por parada, compartido por los dos: el número ya es por persona,
    y los tramos donde difieren son paradas distintas (Portugal vs Pititas).
    """

    __tablename__ = "stop_budgets"

    stop_slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    daily_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class GuideDoc(Base):
    """Snapshot local de un doc de guía de Andiamo (content/guides).

    Fuente de verdad = Andiamo (export bulk); acá solo se cachea para el
    Q&A de viaje del bot. Reconciliación total en cada sync.
    """

    __tablename__ = "guide_docs"
    __table_args__ = (UniqueConstraint("guide_slug", "doc_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    guide_slug: Mapped[str] = mapped_column(String(80), index=True)
    doc_slug: Mapped[str] = mapped_column(String(80))
    guide_title: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(80))
    # city | daytrip | country | general | resource
    kind: Mapped[str] = mapped_column(String(16))
    file: Mapped[str] = mapped_column(String(255))
    content_md: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class StopGuide(Base):
    """Mapeo stop→guía (viene de STOP_TO_GUIDES en Andiamo, fuente de verdad).
    position 0 = guía primaria. Se reemplaza entero en cada sync de guías."""

    __tablename__ = "stop_guides"

    id: Mapped[int] = mapped_column(primary_key=True)
    stop_slug: Mapped[str] = mapped_column(String(80), index=True)
    guide_slug: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class TripNote(Base):
    """Snapshot local de las notas de Andiamo (por parada o globales)."""

    __tablename__ = "trip_notes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    stop_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    synced_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SyncMeta(Base):
    """Key-value mínimo para metadata de syncs (hoy: guides_version)."""

    __tablename__ = "sync_meta"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("currency", "rate_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate_to_usd: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())


class WhatsAppDedupe(Base):
    __tablename__ = "whatsapp_dedupe"

    wamid: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class BotPendingAction(Base):
    __tablename__ = "bot_pending_actions"
    __table_args__ = (UniqueConstraint("channel", "external_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(24)
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_message_id: Mapped[str | None] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class WhatsAppSessionState(Base):
    __tablename__ = "whatsapp_session_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    wa_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
