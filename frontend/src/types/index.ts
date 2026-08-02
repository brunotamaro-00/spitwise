export type MovementType = "expense" | "settlement";
/** `pending` (fecha futura) y `awaiting` (venció, falta confirmar) están FUERA
 *  del balance; solo `confirmed` entra. */
export type MovementStatus = "pending" | "awaiting" | "confirmed";
export type MovementSplit = "shared" | "payer_only" | "other_only";
export type CashbackKind = "pct" | "amount";

export type Movement = {
  id: number; type: MovementType; amount: string; currency: string; amount_usd: string;
  fx_rate: string; fx_source: string; paid_by: number; split: MovementSplit;
  description: string | null; category_id: number | null;
  stop_slug: string | null; city_name: string | null;
  payment_date: string | null; status: MovementStatus;
  // Cashback de tarjeta: 'pct' (value = %) | 'amount' (value = monto fijo local).
  // amount sigue siendo el BRUTO; el neto se deriva (lib/cashback).
  cashback_kind: CashbackKind | null; cashback_value: string | null;
  created_at: string;
};
export type Balance = { debtor_id: number | null; creditor_id: number | null; amount_usd: string };
export type Summary = { total_usd: string; movement_count: number };
export type CategorySpend = { category_id: number | null; name: string | null; icon: string | null; total_usd: string };

export type TripStatus = "not_started" | "in_progress" | "finished";
export type StopPaceStatus = "past" | "current" | "future";

/** Ritmo global: alojamiento prorrateado por noches, generales por todo el viaje. */
export type TripBlock = {
  status: TripStatus;
  start: string | null;
  end: string | null;
  total_nights: number;
  elapsed_nights: number;
  total_usd: string;
  general_usd: string;
  general_per_day_usd: string | null;
  avg_per_day_usd: string | null;
  run_rate_usd: string | null;
  accrued_usd: string;
  projected_total_usd: string | null;
};

export type CityPace = {
  stop_slug: string;
  city_name: string;
  country_flag: string | null;
  order: number;
  status: StopPaceStatus;
  is_archived: boolean;
  is_transit: boolean;
  arrival_date: string | null;
  departure_date: string | null;
  nights: number;
  elapsed_nights: number;
  movement_count: number;
  total_usd: string;
  lodging_usd: string;
  other_usd: string;
  per_day_usd: string | null;
  lodging_per_night_usd: string | null;
  other_per_day_usd: string | null;
  delta_vs_trip_pct: number | null;
};

export type TripPace = { as_of: string; trip: TripBlock; cities: CityPace[] };

/* --- Presupuesto de "vivir" (backend: app/budget.py) --------------------
 * "Vivir" = todo menos alojamiento y generales. Es el mismo `other_usd` que
 * /ciudades muestra como "Vivir /día": el presupuesto solo agrega el plan
 * contra el cual compararlo. Todos los montos son string (decimal).
 *
 * El plan de una parada es un RANGO: el techo (`target_max_usd`) es el límite
 * y el centro (`target_daily_usd`) el objetivo contra el que se miden todos
 * los agregados. */

/** Dónde cae el ritmo real contra la banda: debajo del piso (ahorrando),
 *  adentro (en plan) o arriba del techo (pasados). */
export type BandPosition = "under" | "in" | "over";

export type StopBudget = {
  stop_slug: string;
  daily_min_usd: string;
  daily_max_usd: string;
  note: string | null;
  updated_at: string;
};

export type CityBudget = {
  stop_slug: string;
  city_name: string;
  country_flag: string | null;
  order: number;
  status: StopPaceStatus;
  is_archived: boolean;
  /** false = parada del otro (Pititas): la fila existe porque hay gasto propio,
   *  pero sus noches no cuentan en el presupuesto del viaje. */
  in_itinerary: boolean;
  nights: number;
  elapsed_nights: number;
  movement_count: number;
  target_min_usd: string | null;
  target_max_usd: string | null;
  /** El centro de la banda. */
  target_daily_usd: string | null;
  note: string | null;
  living_usd: string;
  living_per_day_usd: string | null;
  budget_accrued_usd: string | null;
  variance_usd: string | null;
  band_position: BandPosition | null;
  /** Desvío contra el borde violado; null adentro de la banda. */
  edge_delta_pct: number | null;
  /** null sin plan, sin noches, o en futuras (solo tienen prepago). */
  delta_pct: number | null;
};

/** En qué se va el vivir de la parada, contra la mezcla del viaje. */
export type CategoryMix = {
  category_id: number | null;
  living_usd: string;
  share_pct: number | null;
  trip_share_pct: number | null;
  /** share de la parada / share del viaje. >1 = acá se te va más en esto. */
  ratio: number | null;
  /** La misma comparación en plata: $/día acá, $/día promedio del viaje, y la
   *  diferencia con signo. El ratio dice si el desvío existe; esto, cuánto es. */
  per_day_usd: string | null;
  trip_per_day_usd: string | null;
  delta_per_day_usd: string | null;
};

export type CurrentCityBudget = {
  stop_slug: string;
  city_name: string;
  country_flag: string | null;
  arrival_date: string | null;
  departure_date: string | null;
  lived_nights: number;
  total_nights: number;
  remaining_days: number;
  target_min_usd: string | null;
  target_max_usd: string | null;
  target_daily_usd: string | null;
  living_usd: string;
  living_per_day_usd: string | null;
  budget_to_date_usd: string | null;
  variance_usd: string | null;
  remaining_budget_usd: string | null;
  /** Puede ser negativo: ya se pasaron. Cambia el copy, no el signo. */
  remaining_daily_usd: string | null;
  band_position: BandPosition | null;
  edge_delta_pct: number | null;
  delta_pct: number | null;
  by_category: CategoryMix[];
};

export type NextStopBudget = {
  stop_slug: string;
  city_name: string;
  country_flag: string | null;
  arrival_date: string | null;
  nights: number;
  target_min_usd: string | null;
  target_max_usd: string | null;
  target_daily_usd: string | null;
};

/** Colchón acumulado y ritmo necesario: la palanca de control del viaje. */
export type TripCushion = {
  covered_nights: number;
  budget_to_date_usd: string | null;
  living_to_date_usd: string;
  /** Puede ser negativo: van arriba del plan. */
  cushion_usd: string | null;
  remaining_nights: number;
  needed_daily_usd: string | null;
  avg_target_daily_usd: string | null;
  needed_delta_pct: number | null;
};

export type TripPlan = {
  budget_nights: number;
  covered_nights: number;
  coverage_pct: number | null;
  uncovered_slugs: string[];
  living_budget_min_usd: string | null;
  living_budget_max_usd: string | null;
  living_budget_usd: string | null;
  avg_target_daily_usd: string | null;
  next_stop: NextStopBudget | null;
};

export type BudgetProjection = {
  budget_nights: number;
  covered_nights: number;
  coverage_pct: number | null;
  uncovered_slugs: string[];
  living_budget_min_usd: string | null;
  living_budget_max_usd: string | null;
  living_budget_usd: string | null;
  living_to_date_usd: string;
  living_run_rate_usd: string | null;
  projected_living_usd: string | null;
  variance_usd: string | null;
};

export type FixedBlock = {
  lodging_usd: string;
  general_usd: string;
  total_usd: string;
  booked_nights: number;
  total_nights: number;
  per_night_usd: string | null;
};

export type BudgetAnalysis = {
  as_of: string;
  trip_status: TripStatus;
  current: CurrentCityBudget | null;
  cushion: TripCushion;
  plan: TripPlan;
  cities: CityBudget[];
  projection: BudgetProjection;
  fixed: FixedBlock;
};

export type Category = { id: number; name: string; icon: string | null; sort_order: number };
export type User = { id: number; username: string };
export type Stop = {
  slug: string;
  name: string;
  country: string | null;
  country_flag: string | null;
  currency_code: string | null;
  arrival_date: string | null;
  departure_date: string | null;
  order: number;
  is_archived: boolean;
};

export type AppConfig = {
  andiamo_url: string | null;
  demo: boolean;
  /** URL de la demo pública; solo viene en producción (en la demo es null). */
  demo_url: string | null;
};

export type CitySummary = {
  total_usd: string;
  movement_count: number;
  days: number;
  avg_per_day_usd: string;
  arrival_date: string | null;
  departure_date: string | null;
};
