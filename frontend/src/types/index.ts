export type Movement = {
  id: number; type: string; amount: string; currency: string; amount_usd: string;
  fx_rate: string; fx_source: string; paid_by: number; split: string;
  description: string | null; category_id: number | null;
  stop_slug: string | null; city_name: string | null; movement_date: string;
  created_at: string;
};
export type Balance = { debtor_id: number | null; creditor_id: number | null; amount_usd: string };
export type Summary = { total_usd: string; movement_count: number };
export type CitySpend = { stop_slug: string | null; city_name: string | null; total_usd: string };
export type CategorySpend = { category_id: number | null; name: string | null; icon: string | null; total_usd: string };
export type TimePoint = { date: string; cumulative_usd: string };
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

export type CityDaily = { date: string; total_usd: string };
export type CityBreakdown = {
  stop_slug: string | null;
  city_name: string | null;
  country_flag: string | null;
  total_usd: string;
  movement_count: number;
  days: number;
  is_archived: boolean | null;
};
export type CitySummary = {
  total_usd: string;
  movement_count: number;
  days: number;
  avg_per_day_usd: string;
  arrival_date: string | null;
  departure_date: string | null;
};
