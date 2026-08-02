from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


MovementType = Literal["expense", "settlement"]
SplitType = Literal["shared", "payer_only", "other_only"]
CashbackKind = Literal["pct", "amount"]


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
    # Fecha en que se paga/pagó. None => día de carga. Futura => status pending
    # (TC proxy hasta liquidar); pasada => TC histórico. status siempre lo
    # deriva el server: no es escribible.
    payment_date: date | None = None
    # Cashback de tarjeta: kind+value se setean juntos o ninguno. amount sigue
    # siendo el bruto; el neto se hornea en amount_usd (app/cashback.py).
    cashback_kind: CashbackKind | None = None
    cashback_value: Decimal | None = Field(default=None, gt=0)

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
    # Mandarlo (aun null) recalcula status y TC; null explícito => día de carga.
    payment_date: date | None = None
    # Cashback: mandar kind+value juntos setea/actualiza; mandar ambos null
    # explícitos lo saca. Cualquiera de los dos recalcula amount_usd.
    cashback_kind: CashbackKind | None = None
    cashback_value: Decimal | None = Field(default=None, gt=0)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class MovementConfirm(BaseModel):
    """Confirmación manual de un gasto vencido (status pending/awaiting): valida
    el pagador y lo pasa a confirmed. `paid_by` opcional => corrige quién pagó;
    sin él, se acepta el pagador actual. No toca monto/split/ciudad/FX."""

    paid_by: int | None = None


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
    cashback_kind: str | None
    cashback_value: Decimal | None
    created_at: datetime

    @field_serializer("amount", "amount_usd", "fx_rate")
    def _ser_decimal(self, v: Decimal) -> str:
        return str(v)

    @field_serializer("cashback_value")
    def _ser_cashback(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None

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
# Dónde cae el ritmo real contra la banda del plan: debajo del piso (ahorrando),
# adentro (en plan) o arriba del techo (pasados). El techo es el límite.
BandPosition = Literal["under", "in", "over"]


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


# ---------------------------------------------------------------------------
# Presupuesto de "vivir" (ver app/budget.py). Todo monto es str, como el resto
# del dashboard; solo los porcentajes son float.
# ---------------------------------------------------------------------------


class StopBudgetIn(BaseModel):
    """El plan de una parada es un rango, no un número.

    `le=1000` es una cota anti-typo: nadie vive con USD 1.000/día en este viaje,
    así que un "500" con un cero de más muere en 422 en vez de arruinar el
    veredicto de la ciudad en silencio.
    """

    daily_min_usd: Decimal = Field(gt=0, le=1000)
    daily_max_usd: Decimal = Field(gt=0, le=1000)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_band(self) -> "StopBudgetIn":
        # Una banda invertida no es un plan: `app/budget.py` la descartaría en
        # silencio (baja la cobertura), así que se rechaza en el borde.
        if self.daily_max_usd < self.daily_min_usd:
            raise ValueError("el máximo no puede ser menor que el mínimo")
        return self


class StopBudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stop_slug: str
    daily_min_usd: Decimal
    daily_max_usd: Decimal
    note: str | None
    updated_at: datetime

    @field_serializer("daily_min_usd", "daily_max_usd")
    def _ser_daily(self, v: Decimal) -> str:
        return f"{v:.2f}"

    @field_serializer("updated_at")
    def _ser_updated(self, v: datetime) -> str:
        aware = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return aware.isoformat().replace("+00:00", "Z")


class CityBudgetOut(BaseModel):
    stop_slug: str
    city_name: str
    country_flag: str | None
    order: int
    status: StopPaceStatus
    is_archived: bool
    # False = parada del otro (Pititas): la fila existe porque el usuario gastó
    # ahí, pero sus noches no cuentan en el presupuesto del viaje.
    in_itinerary: bool
    nights: int
    elapsed_nights: int
    movement_count: int
    target_min_usd: str | None
    target_max_usd: str | None
    # El centro de la banda: el objetivo contra el que se miden los agregados.
    target_daily_usd: str | None
    note: str | None
    living_usd: str
    living_per_day_usd: str | None
    budget_accrued_usd: str | None
    variance_usd: str | None
    # "under" | "in" | "over": el veredicto que pinta la barra.
    band_position: BandPosition | None
    # Desvío contra el borde violado; None adentro de la banda.
    edge_delta_pct: float | None
    # None sin banda, sin noches, o en futuras (solo tienen prepago imputado).
    delta_pct: float | None


class CategoryMixOut(BaseModel):
    """En qué se va el vivir de la parada, contra la mezcla del viaje.

    Dos lecturas: el **share** dice si esta ciudad se te va en algo distinto que
    el resto (inmune a cuántos días llevás acá), y el **$/día** le pone magnitud
    a ese desvío. Ver `budget.category_mix` para por qué las dos bases difieren.
    """

    category_id: int | None
    living_usd: str
    share_pct: float | None
    trip_share_pct: float | None
    ratio: float | None
    # $/día de esta categoría en la parada, el promedio del viaje, y la
    # diferencia (con signo: menos que el promedio también es información).
    per_day_usd: str | None
    trip_per_day_usd: str | None
    delta_per_day_usd: str | None


class CurrentCityBudgetOut(BaseModel):
    """La parada en curso: el pote que queda y cómo va el día de hoy."""

    stop_slug: str
    city_name: str
    country_flag: str | None
    arrival_date: date | None
    departure_date: date | None
    lived_nights: int
    total_nights: int
    remaining_days: int
    target_min_usd: str | None
    target_max_usd: str | None
    target_daily_usd: str | None
    living_usd: str
    living_per_day_usd: str | None
    budget_to_date_usd: str | None
    variance_usd: str | None
    # El pote de la parada (centro × noches) y su techo (máximo × noches). El
    # techo solo se marca en la barra: el veredicto sigue midiéndose contra el
    # centro, igual que el colchón y la proyección.
    envelope_usd: str | None
    envelope_max_usd: str | None
    remaining_budget_usd: str | None
    # Puede ser negativo: ya se pasaron. La página cambia el copy, no el signo.
    remaining_daily_usd: str | None
    # El día de hoy. `spent_today_usd` existe siempre (es un hecho, no una
    # comparación); `left_today_usd` = tasa por día − gastado hoy, sin clampear.
    spent_today_usd: str
    left_today_usd: str | None
    band_position: BandPosition | None
    edge_delta_pct: float | None
    delta_pct: float | None
    by_category: list[CategoryMixOut]


class NextStopBudgetOut(BaseModel):
    stop_slug: str
    city_name: str
    country_flag: str | None
    arrival_date: date | None
    nights: int
    target_min_usd: str | None
    target_max_usd: str | None
    target_daily_usd: str | None


class TripCushionOut(BaseModel):
    """Colchón acumulado y ritmo necesario: la palanca de control del viaje.

    `cushion_usd` puede ser negativo (van arriba del plan) y no se clampea.
    `needed_daily_usd` es None cuando no queda viaje por delante.
    """

    covered_nights: int
    budget_to_date_usd: str | None
    living_to_date_usd: str
    cushion_usd: str | None
    remaining_nights: int
    needed_daily_usd: str | None
    avg_target_daily_usd: str | None
    needed_delta_pct: float | None


class TripPlanOut(BaseModel):
    """El plan de vivir del viaje: lo que se ve antes de arrancar."""

    budget_nights: int
    covered_nights: int
    coverage_pct: float | None
    uncovered_slugs: list[str]
    living_budget_min_usd: str | None
    living_budget_max_usd: str | None
    living_budget_usd: str | None
    avg_target_daily_usd: str | None
    next_stop: NextStopBudgetOut | None


class BudgetProjectionOut(BaseModel):
    """Presupuesto contra proyección del ritmo real.

    `coverage_pct` y `uncovered_slugs` viajan acá a propósito, junto a
    `variance_usd`: con cobertura parcial el presupuesto es parcial, y mostrar
    la varianza sin decirlo al lado es mentir.
    """

    budget_nights: int
    covered_nights: int
    coverage_pct: float | None
    uncovered_slugs: list[str]
    # El presupuesto se muestra como el rango que es; la varianza se mide
    # contra el centro (`living_budget_usd`).
    living_budget_min_usd: str | None
    living_budget_max_usd: str | None
    living_budget_usd: str | None
    living_to_date_usd: str
    living_run_rate_usd: str | None
    projected_living_usd: str | None
    variance_usd: str | None


class FixedBlockOut(BaseModel):
    """Alojamiento + generales: informativo, sin veredicto."""

    lodging_usd: str
    general_usd: str
    total_usd: str
    # Noches con alojamiento cargado (denominador de `per_night_usd`) vs noches
    # del itinerario: la web muestra la cobertura al lado del precio por noche.
    booked_nights: int
    total_nights: int
    per_night_usd: str | None


class TripCostOut(BaseModel):
    """Cuánto sale el viaje entero: vivir + alojamiento + generales.

    `basis` elige el copy: `projected` (hay ritmo de ciudades cerradas) o
    `committed` (todavía ninguna cerrada, así que el total es lo comprometido
    hasta hoy y no una proyección). `lodging_is_estimated` avisa que parte del
    alojamiento son noches sin reservar estimadas a `per_night_usd`.
    """

    unbooked_nights: int
    lodging_estimated_usd: str | None
    lodging_projected_usd: str
    living_usd: str
    general_usd: str
    total_usd: str
    basis: Literal["projected", "committed"]
    lodging_is_estimated: bool


class BudgetOut(BaseModel):
    as_of: date
    trip_status: TripStatus
    current: CurrentCityBudgetOut | None
    cushion: TripCushionOut
    plan: TripPlanOut
    cities: list[CityBudgetOut]
    projection: BudgetProjectionOut
    fixed: FixedBlockOut
    cost: TripCostOut


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
    demo: bool = False
    # URL de la demo pública. Solo tiene sentido cuando demo=False: es el CTA
    # principal del /login de producción.
    demo_url: str | None = None
