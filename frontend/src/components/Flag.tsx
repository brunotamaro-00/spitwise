import { countryCodeFromFlag } from "@/lib/countryCodeFromFlag";

/** Banderas del viaje servidas LOCALES (public/flags, subset bajado por
 *  scripts/fetch-flags.mjs) para que la PWA no muestre huecos offline.
 *  Un código fuera del subset degrada al CDN de flag-icons (mismo set SVG
 *  que Andiamo) vía onError — online se ve igual, offline como antes. */
const FLAG_CDN =
  "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.5.0/flags/4x3";

/**
 * Renders a country flag that looks the same on every OS.
 *
 * Converts the stored emoji to an ISO code and loads the SVG (local first).
 * Non-flag emoji (🌍, etc.) render verbatim.
 */
export default function Flag({
  flag,
  className = "",
}: {
  flag: string | null | undefined;
  className?: string;
}) {
  const code = countryCodeFromFlag(flag);

  if (!code) {
    return flag ? (
      <span className={className} aria-hidden="true">
        {flag}
      </span>
    ) : null;
  }

  return (
    <img
      src={`/flags/${code}.svg`}
      onError={(e) => {
        const img = e.currentTarget;
        const fallback = `${FLAG_CDN}/${code}.svg`;
        if (img.src !== fallback) img.src = fallback;
      }}
      alt=""
      aria-hidden="true"
      loading="lazy"
      decoding="async"
      className={`inline-block h-[1em] w-[1.333em] shrink-0 rounded-[2px] align-[-0.15em] object-cover ${className}`}
    />
  );
}
