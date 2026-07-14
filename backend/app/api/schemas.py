from datetime import date, datetime
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
    stop_slug: str | None = None
    city_name: str | None = None
    general: bool = False  # gasto general sin ciudad: no derivar la parada por fecha
    movement_date: date | None = None
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
    stop_slug: str | None = None
    city_name: str | None = None
    general: bool | None = None
    movement_date: date | None = None
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
    movement_date: date
    created_at: datetime

    @field_serializer("amount", "amount_usd", "fx_rate")
    def _ser_decimal(self, v: Decimal) -> str:
        return str(v)


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


class CitySpendOut(BaseModel):
    stop_slug: str | None
    city_name: str | None
    total_usd: str


class CategorySpendOut(BaseModel):
    category_id: int | None
    name: str | None
    icon: str | None
    total_usd: str


class TimePointOut(BaseModel):
    date: date
    cumulative_usd: str


class CitySpendPublicOut(BaseModel):
    slug: str | None
    name: str | None
    total_usd: str
    movement_count: int


class CityDailyOut(BaseModel):
    date: date
    total_usd: str


class CityBreakdownOut(BaseModel):
    stop_slug: str | None
    city_name: str | None
    country_flag: str | None
    total_usd: str
    movement_count: int
    days: int


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
