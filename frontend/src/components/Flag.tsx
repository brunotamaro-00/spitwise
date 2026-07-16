import { countryCodeFromFlag } from "@/lib/countryCodeFromFlag";

/** CDN de flag-icons (mismo set SVG que Andiamo). Sin assets locales ni
 *  dependencia npm: Vite no empaqueta cientos de SVG y el image push de
 *  Railway no se hincha. */
const FLAG_CDN =
  "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.5.0/flags/4x3";

/**
 * Renders a country flag that looks the same on every OS.
 *
 * Converts the stored emoji to an ISO code and loads the SVG from jsDelivr.
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
      src={`${FLAG_CDN}/${code}.svg`}
      alt=""
      aria-hidden="true"
      loading="lazy"
      decoding="async"
      className={`inline-block h-[1em] w-[1.333em] shrink-0 rounded-[2px] align-[-0.15em] object-cover ${className}`}
    />
  );
}
