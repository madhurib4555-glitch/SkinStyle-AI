"use client";

import type { ColorRecommendation, ColorToAvoid } from "@/lib/api";

interface Props {
  recommendations: ColorRecommendation[];
  avoid: ColorToAvoid[];
  selectedHex: string | null;
  onSelect: (color: ColorRecommendation) => void;
}

export default function ColorRecommendations({
  recommendations,
  avoid,
  selectedHex,
  onSelect,
}: Props) {
  return (
    <section className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-stone-900">
          Colours that suit you
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          Ranked by fit. Pick one to see it on you.
        </p>

        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {recommendations.map((color) => {
            const selected = selectedHex === color.hex;
            return (
              <li key={color.hex}>
                <button
                  type="button"
                  onClick={() => onSelect(color)}
                  aria-pressed={selected}
                  className={`flex w-full flex-col gap-3 rounded-xl border p-4 text-left transition
                    ${
                      selected
                        ? "border-stone-900 ring-2 ring-stone-900/15"
                        : "border-stone-200 hover:border-stone-400"
                    }`}
                >
                  <div className="flex items-center gap-3">
                    {/* Pure colour block: no text on top of it. Mid-tone
                        swatches like Dusty Teal cannot reach WCAG AA against
                        either black or white, so the score lives on the card
                        background instead, where contrast is guaranteed. */}
                    <span
                      className="h-11 w-11 shrink-0 rounded-lg border border-black/10"
                      style={{ backgroundColor: color.hex }}
                      aria-hidden="true"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium text-stone-900">
                        {color.name}
                      </span>
                      <span className="block font-mono text-xs text-stone-500">
                        {color.hex}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block text-lg font-semibold tabular-nums text-stone-900">
                        {color.score}
                      </span>
                      <span className="block text-[11px] uppercase tracking-wide text-stone-500">
                        fit
                      </span>
                    </span>
                  </div>

                  <p className="text-sm leading-relaxed text-stone-600">
                    {color.rationale}
                  </p>

                  {/* Fit strength, as a bar. Redundant with the numeric badge
                      so the information is not carried by colour alone. */}
                  <span className="h-1 w-full overflow-hidden rounded-full bg-stone-100">
                    <span
                      className="block h-full rounded-full bg-stone-800"
                      style={{ width: `${color.score}%` }}
                    />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-stone-900">
          Colours to approach with care
        </h3>
        <ul className="mt-3 space-y-2">
          {avoid.map((color) => (
            <li
              key={color.hex}
              className="flex items-start gap-3 rounded-lg bg-stone-50 px-3 py-2.5"
            >
              <span
                className="mt-0.5 h-5 w-5 shrink-0 rounded border border-black/10"
                style={{ backgroundColor: color.hex }}
                aria-hidden="true"
              />
              <p className="text-sm leading-relaxed text-stone-600">
                <span className="font-medium text-stone-800">{color.name}</span>
                {" — "}
                {color.reason}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
