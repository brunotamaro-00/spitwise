export function parseMoney(s: string): number {
  return Number(s);
}

export function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

export function formatUsd(s: string): string {
  const n = parseMoney(s);
  return `USD ${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
