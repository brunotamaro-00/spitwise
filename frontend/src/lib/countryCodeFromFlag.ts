/**
 * Turns a regional-indicator flag emoji (e.g. "🇮🇹") into its lowercase ISO
 * 3166-1 alpha-2 code (e.g. "it") for use with `flag-icons` CSS classes.
 *
 * Returns null for anything that isn't a country/subdivision flag — plain
 * emoji like 🌍 fall through so callers can render them verbatim. Windows
 * lacks flag glyphs in its system fonts, so callers use the code to render
 * an SVG flag instead.
 */
export function countryCodeFromFlag(flag: string | null | undefined): string | null {
  if (!flag) return null;
  const cps = Array.from(flag, (ch) => ch.codePointAt(0)!);

  // Subdivision flags (England 🏴󠁧󠁢󠁥󠁮󠁧󠁿, Scotland 🏴󠁧󠁢󠁳󠁣󠁴󠁿, Wales …): a waving black flag
  // followed by ISO 3166-2 tag letters and a cancel-tag terminator. flag-icons
  // expects the code hyphenated (e.g. "gb-eng").
  if (cps[0] === 0x1f3f4 && cps[cps.length - 1] === 0xe007f) {
    let tag = "";
    for (let i = 1; i < cps.length - 1; i++) {
      const c = cps[i];
      if (c < 0xe0061 || c > 0xe007a) return null; // tag latin small a–z
      tag += String.fromCharCode(c - 0xe0000);
    }
    if (tag.length < 3) return null;
    return `${tag.slice(0, 2)}-${tag.slice(2)}`; // "gbeng" → "gb-eng"
  }

  // Standard country flags: exactly two regional-indicator symbols.
  if (cps.length !== 2) return null;
  const [a, b] = cps;
  const A = 0x1f1e6; // 🇦
  const Z = 0x1f1ff; // 🇿
  if (a < A || a > Z || b < A || b > Z) return null;
  return (
    String.fromCharCode(97 + (a - A)) + String.fromCharCode(97 + (b - A))
  );
}
