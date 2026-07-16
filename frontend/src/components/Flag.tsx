import { countryCodeFromFlag } from "@/lib/countryCodeFromFlag";

/**
 * Renders a country flag that looks the same on every OS.
 *
 * Windows system fonts don't include regional-indicator flag glyphs, so raw
 * flag emoji render as two letters ("ES") or a black flag. We convert the
 * stored emoji to an ISO code and serve a local SVG from `/flags` (only the
 * trip countries — importing full `flag-icons` CSS made Vite hash ~500 SVGs
 * and ballooned the Docker image). Non-flag emoji render verbatim.
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

  // Sized by font-size like flag-icons `.fi` (4:3), so text-* utilities scale it.
  return (
    <img
      src={`/flags/${code}.svg`}
      alt=""
      aria-hidden="true"
      className={`inline-block h-[1em] w-[1.333em] shrink-0 rounded-[2px] align-[-0.15em] object-cover ${className}`}
    />
  );
}
