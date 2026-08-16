/** Colour helpers shared between components. */

/**
 * Relative luminance per WCAG 2.1, from an #rrggbb string.
 * Exported for testing; prefer `readableTextOn` at call sites.
 */
export function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map(
    (i) => parseInt(hex.slice(i, i + 2), 16) / 255,
  );
  const [r, g, b] = channels.map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio between two #rrggbb colours, from 1 to 21. */
export function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort(
    (x, y) => y - x,
  );
  return (lighter + 0.05) / (darker + 0.05);
}

export const INK = "#1c1917";
export const PAPER = "#fafaf9";

/**
 * Pick near-black or near-white text for a background, whichever contrasts
 * more. Needed because the palette spans Cream to Charcoal, so no single fixed
 * text colour stays legible across it.
 */
export function readableTextOn(backgroundHex: string): string {
  return contrastRatio(backgroundHex, INK) >= contrastRatio(backgroundHex, PAPER)
    ? INK
    : PAPER;
}
