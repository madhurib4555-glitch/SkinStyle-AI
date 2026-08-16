"use client";

import type { SkinAnalysis } from "@/lib/api";

const SEASON_BLURB: Record<SkinAnalysis["season"], string> = {
  spring: "Clear, warm colours with life in them suit you best.",
  summer: "Soft, cool and slightly muted shades are your strongest range.",
  autumn: "Deep, earthy and golden tones sit naturally against your skin.",
  winter: "Bold, cool and high-contrast colours carry best on you.",
};

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-stone-500">{label}</dt>
      <dd className="mt-1 text-lg font-medium capitalize text-stone-900">
        {value}
      </dd>
      {hint && <p className="mt-0.5 text-xs text-stone-500">{hint}</p>}
    </div>
  );
}

export default function AnalysisCard({
  analysis,
  summary,
}: {
  analysis: SkinAnalysis;
  summary: string;
}) {
  const lowConfidence = analysis.confidence < 0.6;

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-4">
        <div
          className="h-16 w-16 shrink-0 rounded-full border border-stone-200 shadow-inner"
          style={{ backgroundColor: analysis.skin_hex }}
          // The swatch is decorative; the hex is stated in the metrics below.
          aria-hidden="true"
        />
        <div>
          <h2 className="text-lg font-semibold text-stone-900">Your colouring</h2>
          <p className="mt-1 text-sm leading-relaxed text-stone-600">{summary}</p>
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-4">
        <Metric label="Depth" value={analysis.tone_depth} />
        <Metric label="Undertone" value={analysis.undertone} />
        <Metric label="Season" value={analysis.season} />
        <Metric
          label="Contrast"
          value={analysis.contrast >= 22 ? "high" : "soft"}
          hint={`${analysis.contrast.toFixed(0)} ΔL*`}
        />
      </dl>

      <p className="mt-5 text-sm leading-relaxed text-stone-600">
        {SEASON_BLURB[analysis.season]}
      </p>

      {lowConfidence && (
        <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900">
          Confidence is low ({Math.round(analysis.confidence * 100)}%) — lighting
          or angle limited how much skin could be sampled. A brighter,
          front-facing photo will give a more reliable read.
        </p>
      )}
    </section>
  );
}
