from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


class MovementIn(BaseModel):
    type: str = "expense"
    amount: Decimal
    currency: str = "USD"
    split: str = "shared"
    paid_by: int | None = None  # default: usuario actual
    description: str | None = None
    category_id: int | None = None
    stop_slug: str | None = None
    city_name: str | None = None
    movement_date: date | None = None
    fx_rate: Decimal | None = None  # override manual


class MovementUpdate(BaseModel):
    """PATCH parcial: todos opcionales; solo se aplica lo que vino en el body
    (via model_fields_set). Nunca usar MovementIn acá: sus campos obligatorios
    romperían las ediciones parciales."""

    type: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    split: str | None = None
    paid_by: int | None = None
    description: str | None = None
    category_id: int | None = None
    stop_slug: str | None = None
    city_name: str | None = None
    movement_date: date | None = None
    fx_rate: Decimal | None = None  # setearlo => fx_source='manual'


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
