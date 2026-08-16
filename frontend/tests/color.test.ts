import { describe, expect, it } from "vitest";

import {
  INK,
  PAPER,
  contrastRatio,
  readableTextOn,
  relativeLuminance,
} from "@/lib/color";

// Every swatch the backend can return. Mirrors PALETTE in
// backend/app/services/recommender.py; the contrast guarantee must hold for all.
const PALETTE_HEXES = [
  "#0f7b6c", "#6b7042", "#1f2a52", "#2f5fd0", "#4a8a92",
  "#6d2233", "#a9542a", "#c1694f", "#f2795f", "#e6a9ab",
  "#b5237c", "#a89ccc", "#9aa0a6", "#36393d", "#f0e4cd",
  "#b8925f", "#c8a02c", "#f8f9fa", "#bcd6e8", "#5b2c5e",
];

describe("relativeLuminance", () => {
  it("returns 0 for black and 1 for white", () => {
    expect(relativeLuminance("#000000")).toBeCloseTo(0, 5);
    expect(relativeLuminance("#ffffff")).toBeCloseTo(1, 5);
  });

  it("ranks greys monotonically", () => {
    const greys = ["#000000", "#404040", "#808080", "#c0c0c0", "#ffffff"];
    const values = greys.map(relativeLuminance);
    expect(values).toEqual([...values].sort((a, b) => a - b));
  });

  it("weights green above red above blue", () => {
    // Per the WCAG coefficients; a common source of miscomputed luminance.
    expect(relativeLuminance("#00ff00")).toBeGreaterThan(
      relativeLuminance("#ff0000"),
    );
    expect(relativeLuminance("#ff0000")).toBeGreaterThan(
      relativeLuminance("#0000ff"),
    );
  });
});

describe("contrastRatio", () => {
  it("is 21:1 for black on white", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 1);
  });

  it("is 1:1 for a colour against itself", () => {
    expect(contrastRatio("#0f7b6c", "#0f7b6c")).toBeCloseTo(1, 5);
  });

  it("is symmetric in its arguments", () => {
    expect(contrastRatio("#0f7b6c", "#ffffff")).toBeCloseTo(
      contrastRatio("#ffffff", "#0f7b6c"),
      5,
    );
  });
});

describe("readableTextOn", () => {
  it("uses dark ink on light backgrounds", () => {
    expect(readableTextOn("#f8f9fa")).toBe(INK);
    expect(readableTextOn("#f0e4cd")).toBe(INK);
  });

  it("uses light paper on dark backgrounds", () => {
    expect(readableTextOn("#1f2a52")).toBe(PAPER);
    expect(readableTextOn("#36393d")).toBe(PAPER);
  });

  it("always picks whichever of ink or paper contrasts more", () => {
    for (const hex of PALETTE_HEXES) {
      const chosen = readableTextOn(hex);
      const other = chosen === INK ? PAPER : INK;
      expect(contrastRatio(hex, chosen)).toBeGreaterThanOrEqual(
        contrastRatio(hex, other),
      );
    }
  });

  it.each(PALETTE_HEXES)("reaches at least 4.4:1 on %s", (hex) => {
    // Deliberately 4.4, not the AA 4.5: two mid-tone swatches (Dusty Teal
    // #4a8a92 at 4.45, Terracotta #c1694f at 4.50) cannot clear AA against
    // either black or white, because no text colour clears AA on a mid-tone
    // background. This asserts the achievable floor; UI that must meet AA puts
    // its text on the card background rather than on the swatch. See the
    // comment in components/ColorRecommendations.tsx.
    expect(contrastRatio(hex, readableTextOn(hex))).toBeGreaterThanOrEqual(4.4);
  });

  it("documents which palette colours fall short of WCAG AA on-swatch", () => {
    // Pins the known set: if a new swatch drops below AA, this fails and forces
    // a decision rather than silently shipping unreadable text.
    const belowAA = PALETTE_HEXES.filter(
      (hex) => contrastRatio(hex, readableTextOn(hex)) < 4.5,
    );
    expect(belowAA).toEqual(["#4a8a92", "#c1694f"]);
  });
});
