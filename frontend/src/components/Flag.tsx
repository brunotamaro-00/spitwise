import { countryCodeFromFlag } from "@/lib/countryCodeFromFlag";

/**
 * Renders a country flag that looks the same on every OS.
 *
 * Windows system fonts don't include regional-indicator flag glyphs, so raw
 * flag emoji render as two letters ("ES") or a black flag. We convert the
 * stored emoji to an ISO code and draw an SVG flag via the `flag-icons` CSS
 * (imported once in `main.tsx`). Non-flag emoji (🌍, etc.) render verbatim —
 * those glyphs exist on every platform.
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

  // `.fi` is a 4:3 inline-block sized by font-size, so text-* utilities from the
  // caller (e.g. `text-4xl`) scale it just like the emoji it replaces.
  return (
    <span
      className={`fi fi-${code} rounded-[2px] align-[-0.15em] ${className}`}
      role="img"
      aria-hidden="true"
    />
  );
}
