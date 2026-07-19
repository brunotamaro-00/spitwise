from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


MovementType = Literal["expense", "settlement"]
SplitType = Literal["shared", "payer_only", "other_only"]


class MovementIn(BaseModel):
    type: MovementType = "expense"
    amount: Decimal = Field(gt=0)
    currency: str = "USD"
    split: SplitType = "shared"
    paid_by: int | None = None  # default: usuario actual
    description: str | None = None
    category_id: int | None = None
    stop_slug: str | None = None  # parada del itinerario; None => parada de hoy
    general: bool = False  # gasto general sin ciudad: no derivar la parada de hoy
    fx_rate: Decimal | None = None  # override manual (multiplicador a USD)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()


class MovementUpdate(BaseModel):
    """PATCH parcial: todos opcionales; solo se aplica lo que vino en el body
    (via model_fields_set). Nunca usar MovementIn acá: sus campos obligatorios
    romperían las ediciones parciales."""

    type: MovementType | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    split: SplitType | None = None
    paid_by: int | None = None
    description: str | None = None
    category_id: int | None = None
    stop_slug: str | None = None  # slug => esa parada; null explícito => parada de hoy
    general: bool | None = None
    fx_rate: Decimal | None = None  # setearlo => fx_source='manual'

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    amount: Decimal
    currency: str
    amount_usd: Decimal
    fx_rate: Decimal
    fx_source: str
    paid_by: int
    split: str
    description: str | None
    category_id: int | None
    stop_slug: str | None
    city_name: str | None
    payment_date: date | None
    status: str
    created_at: datetime

    @field_serializer("amount", "amount_usd", "fx_rate")
    def _ser_decimal(self, v: Decimal) -> str:
        return str(v)

    @field_serializer("created_at")
    def _ser_created(self, v: datetime) -> str:
        # created_at es naive-UTC en ambos motores (func.now()); emitir con Z
        # para que el browser lo convierta bien a su TZ local.
        aware = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return aware.isoformat().replace("+00:00", "Z")


class BalanceOut(BaseModel):
    debtor_id: int | None
    creditor_id: int | None
    amount_usd: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    icon: str | None
    sort_order: int


class SummaryOut(BaseModel):
    total_usd: str
    movement_count: int


class CategorySpendOut(BaseModel):
    category_id: int | None
    name: str | None
    icon: str | None
    total_usd: str


TripStatus = Literal["not_started", "in_progress", "finished"]
StopPaceStatus = Literal["past", "current", "future"]


class TripBlockOut(BaseModel):
    """Ritmo global del viaje: alojamiento prorrateado por noches y generales
    (sin ciudad) prorrateados en todas las noches del itinerario."""

    status: TripStatus
    start: date | None
    end: date | None
    total_nights: int
    elapsed_nights: int
    total_usd: str
    general_usd: str
    general_per_day_usd: str | None
    avg_per_day_usd: str | None
    run_rate_usd: str | None
    accrued_usd: str
    projected_total_usd: str | None


class CityPaceOut(BaseModel):
    stop_slug: str
    city_name: str
    country_flag: str | None
    order: int
    status: StopPaceStatus
    is_archived: bool
    is_transit: bool
    arrival_date: date | None
    departure_date: date | None
    nights: int
    elapsed_nights: int
    movement_count: int
    total_usd: str
    lodging_usd: str
    other_usd: str
    per_day_usd: str | None
    lodging_per_night_usd: str | None
    other_per_day_usd: str | None
    # None para futuras (el prepago no debe "gritar" sobre el promedio).
    delta_vs_trip_pct: float | None


class TripPaceOut(BaseModel):
    as_of: date
    trip: TripBlockOut
    cities: list[CityPaceOut]


class CitySpendPublicOut(BaseModel):
    slug: str | None
    name: str | None
    total_usd: str
    movement_count: int


class CitySummaryOut(BaseModel):
    total_usd: str
    movement_count: int
    days: int
    avg_per_day_usd: str
    # Solo cuando hay exactamente una ciudad seleccionada:
    arrival_date: date | None = None
    departure_date: date | None = None


class StopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    country: str | None
    country_flag: str | None
    currency_code: str | None
    arrival_date: date | None
    departure_date: date | None
    order: int
    is_archived: bool = False


class SpendDetailCategoryOut(BaseModel):
    category_id: int | None
    name: str | None
    icon: str | None
    total_usd: str


class SpendDetailMovementOut(BaseModel):
    description: str | None
    amount: str
    currency: str
    amount_usd: str
    date: date
    category_id: int | None
    paid_by_name: str | None


class SpendDetailOut(BaseModel):
    """Contrato para Andiamo (X-Api-Key). Totales gross del hogar,
    misma regla que /cities/spend."""

    slug: str
    city_name: str | None
    total_usd: str
    movement_count: int
    itinerary_days: int
    avg_per_day_usd: str
    by_category: list[SpendDetailCategoryOut]
    last_movements: list[SpendDetailMovementOut]
    generated_at: datetime


class TripSpendOut(BaseModel):
    total_usd: str
    today_usd: str
    movement_count: int


class ConfigOut(BaseModel):
    andiamo_url: str | None
