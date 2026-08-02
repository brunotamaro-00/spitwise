// Baja a public/flags el SUBSET de banderas del viaje (y vecinas probables)
// desde flag-icons, para que la PWA funcione offline (el CDN queda como
// fallback en Flag.tsx para códigos fuera de esta lista).
// Uso: node scripts/fetch-flags.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const VERSION = "7.5.0";
const CDN = `https://cdn.jsdelivr.net/gh/lipis/flag-icons@${VERSION}/flags/4x3`;

// Europa del itinerario + vecinas + AR/US/EU (monedas y visitas probables).
const CODES = [
  "gb", "gb-sct", "pt", "es", "fr", "it", "de", "at", "ch", "nl", "be", "lu",
  "cz", "pl", "hu", "si", "hr", "sk", "dk", "se", "no", "fi", "ie", "gr",
  "ro", "bg", "rs", "ba", "me", "mk", "al", "ar", "us", "eu",
];

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const dir = path.join(root, "public", "flags");
mkdirSync(dir, { recursive: true });

for (const code of CODES) {
  const res = await fetch(`${CDN}/${code}.svg`);
  if (!res.ok) {
    console.error(`✗ ${code}: HTTP ${res.status}`);
    continue;
  }
  writeFileSync(path.join(dir, `${code}.svg`), Buffer.from(await res.arrayBuffer()));
  console.log(`✓ ${code}.svg`);
}
