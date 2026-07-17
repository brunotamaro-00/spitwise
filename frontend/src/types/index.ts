export type Movement = {
  id: number; type: string; amount: string; currency: string; amount_usd: string;
  fx_rate: string; fx_source: string; paid_by: number; split: string;
  description: string | null; category_id: number | null;
  stop_slug: string | null; city_name: string | null; movement_date: string;
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

/** Un día con gasto (parte personal) para el timeline de la tab Viaje. */
export type TimelineDay = {
  date: string;
  total_usd: string;
  movement_count: number;
  top_category_id: number | null;
};
export type Timeline = { as_of: string; days: TimelineDay[] };
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

export type AppConfig = { andiamo_url: string | null };

export type CitySummary = {
  total_usd: string;
  movement_count: number;
  days: number;
  avg_per_day_usd: string;
  arrival_date: string | null;
  departure_date: string | null;
};
