"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import AnalysisCard from "@/components/AnalysisCard";
import ColorRecommendations from "@/components/ColorRecommendations";
import GarmentPicker from "@/components/GarmentPicker";
import SelfieUploader from "@/components/SelfieUploader";
import TryOnResult from "@/components/TryOnResult";
import {
  analyzeSelfie,
  awaitTryOn,
  fetchGarments,
  startTryOn,
  ApiError,
  type AnalyzeResponse,
  type ColorRecommendation,
  type Garment,
} from "@/lib/api";

type TryOnStatus = "idle" | "loading" | "done" | "error";

export default function Home() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const [garments, setGarments] = useState<Garment[]>([]);
  const [isMock, setIsMock] = useState(false);

  const [color, setColor] = useState<ColorRecommendation | null>(null);
  const [garmentId, setGarmentId] = useState<string | null>(null);

  const [tryOnStatus, setTryOnStatus] = useState<TryOnStatus>("idle");
  const [tryOnUrl, setTryOnUrl] = useState<string | null>(null);
  const [tryOnError, setTryOnError] = useState<string | null>(null);

  // Identifies the newest try-on request so slower earlier ones cannot
  // overwrite it when they land out of order.
  const tryOnRequestId = useRef(0);
  const resultsRef = useRef<HTMLDivElement>(null);

  // Load the catalogue and mode flag once; both are static for the session.
  useEffect(() => {
    fetchGarments().then(setGarments).catch(() => setGarments([]));

    const base =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${base}/api/health`)
      .then((r) => r.json())
      .then((body) => setIsMock(body.youcam_mode === "mock"))
      .catch(() => {
        // Health check is advisory; failing it should not block the UI.
      });
  }, []);

  // Object URLs leak until revoked, so release the previous one on change.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleSelect = useCallback(async (file: File, url: string) => {
    setPreviewUrl(url);
    setResult(null);
    setColor(null);
    setGarmentId(null);
    setTryOnStatus("idle");
    setTryOnUrl(null);
    setAnalyzeError(null);
    setAnalyzing(true);

    try {
      const analysis = await analyzeSelfie(file);
      setResult(analysis);
      // Preselect the top colour so the next step is obvious.
      setColor(analysis.recommendations[0] ?? null);
      // Defer until the results have rendered, or there is nothing to scroll to.
      requestAnimationFrame(() =>
        resultsRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        }),
      );
    } catch (err) {
      setAnalyzeError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the analysis service. Is the backend running?",
      );
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const runTryOn = useCallback(
    async (chosenGarmentId: string, chosenColor: ColorRecommendation) => {
      if (!result) return;

      const requestId = ++tryOnRequestId.current;
      setTryOnStatus("loading");
      setTryOnError(null);
      setTryOnUrl(null);

      try {
        const task = await startTryOn(
          result.image_id,
          chosenGarmentId,
          chosenColor.hex,
        );
        const url = await awaitTryOn(task.task_id);

        // Discard if a newer request superseded this one mid-flight.
        if (requestId !== tryOnRequestId.current) return;
        setTryOnUrl(url);
        setTryOnStatus("done");
      } catch (err) {
        if (requestId !== tryOnRequestId.current) return;
        setTryOnError(
          err instanceof ApiError ? err.message : "The try-on request failed.",
        );
        setTryOnStatus("error");
      }
    },
    [result],
  );

  // Changing the colour re-runs an existing try-on with the same garment, which
  // is the whole point: compare the same shirt across recommended colours.
  const handleColorSelect = useCallback(
    (next: ColorRecommendation) => {
      setColor(next);
      if (garmentId) void runTryOn(garmentId, next);
    },
    [garmentId, runTryOn],
  );

  const handleGarmentSelect = useCallback(
    (nextGarmentId: string) => {
      setGarmentId(nextGarmentId);
      if (color) void runTryOn(nextGarmentId, color);
    },
    [color, runTryOn],
  );

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-10 sm:px-8 sm:py-16">
  <header className="relative mb-12 overflow-hidden rounded-[2rem] border border-stone-200 bg-white px-6 py-10 shadow-sm sm:mb-16 sm:px-10 sm:py-14">
  {/* Decorative background */}
  <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-emerald-100/60 blur-3xl" />
  <div className="pointer-events-none absolute -bottom-24 -left-24 h-64 w-64 rounded-full bg-purple-100/50 blur-3xl" />

 <div className="relative">
  {/* Project name */}
  <div className="mb-5 text-center">
    <span className="text-2xl font-bold tracking-tight text-stone-950 sm:text-3xl">
      SkinStyle <span className="text-emerald-700">AI</span>
    </span>
  </div>

  {/* Badge */}
  <div className="mb-6 flex justify-center">
    <span className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-stone-50 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-stone-600">
      <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
      AI-Powered Personal Styling
    </span>
  </div>

    {/* Main heading */}
    <h1 className="mx-auto max-w-3xl text-center text-4xl font-bold leading-tight tracking-tight text-stone-950 sm:text-6xl">
      Find the colours that{" "}
      <span className="bg-gradient-to-r from-emerald-700 via-teal-600 to-purple-600 bg-clip-text text-transparent">
        make you shine.
      </span>
    </h1>

    {/* Description */}
    <p className="mx-auto mt-5 max-w-2xl text-center text-base leading-7 text-stone-600 sm:text-lg">
      SkinStyle AI analyses your natural colouring, recommends your best
      clothing shades, and lets you preview outfits on yourself before you
      buy.
    </p>

    {/* Feature highlights */}
    <div className="mx-auto mt-8 grid max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
      <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-4 text-center">
        <div className="mb-2 text-xl">✨</div>
        <p className="text-sm font-semibold text-stone-900">
          Personalised
        </p>
        <p className="mt-1 text-xs text-stone-500">
          Colour analysis
        </p>
      </div>

      <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-4 text-center">
        <div className="mb-2 text-xl">🎨</div>
        <p className="text-sm font-semibold text-stone-900">
          Smart styling
        </p>
        <p className="mt-1 text-xs text-stone-500">
          Best colours for you
        </p>
      </div>

      <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-4 text-center">
        <div className="mb-2 text-xl">👕</div>
        <p className="text-sm font-semibold text-stone-900">
          Virtual try-on
        </p>
        <p className="mt-1 text-xs text-stone-500">
          See it before you buy
        </p>
      </div>
    </div>

    {/* How it works */}
    <div className="mx-auto mt-10 max-w-2xl border-t border-stone-200 pt-7">
      <p className="mb-4 text-center text-xs font-semibold uppercase tracking-widest text-stone-400">
        How it works
      </p>

      <div className="flex flex-col items-center justify-center gap-3 text-sm text-stone-600 sm:flex-row sm:gap-5">
        <span>
          <strong className="text-stone-900">01</strong> Upload
        </span>

        <span className="hidden text-stone-300 sm:block">→</span>

        <span>
          <strong className="text-stone-900">02</strong> Discover
        </span>

        <span className="hidden text-stone-300 sm:block">→</span>

        <span>
          <strong className="text-stone-900">03</strong> Try it on
        </span>
      </div>
    </div>
  </div>
</header>

      <div className="mt-10">
        <SelfieUploader onSelect={handleSelect} disabled={analyzing} />
      </div>

      {previewUrl && (
        <div className="mt-6 flex items-center gap-5 rounded-3xl border border-stone-200 bg-white p-4 shadow-sm">
          {/* Plain <img>: the source is a local blob: URL from the file picker. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt="Your uploaded selfie"
            className="h-28 w-28 rounded-2xl border border-stone-200 object-cover shadow-sm"
          />
          {analyzing && (
            <p className="flex items-center gap-2.5 text-sm font-medium text-stone-600">
              <span
                className="h-4 w-4 animate-spin rounded-full border-2 border-stone-300 border-t-stone-800"
                aria-hidden="true"
              />
              Analysing your skin tone…
            </p>
          )}
        </div>
      )}

      {analyzeError && (
        <p
          role="alert"
          className="mt-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {analyzeError}
        </p>
      )}

      {result && (
        <div ref={resultsRef} className="mt-10 space-y-10">
          <AnalysisCard analysis={result.analysis} summary={result.summary} />

          <ColorRecommendations
            recommendations={result.recommendations}
            avoid={result.avoid}
            selectedHex={color?.hex ?? null}
            onSelect={handleColorSelect}
          />

          {color && garments.length > 0 && (
            <GarmentPicker
              garments={garments}
              color={color}
              selectedGarmentId={garmentId}
              onSelect={handleGarmentSelect}
              disabled={tryOnStatus === "loading"}
            />
          )}

          <TryOnResult
            status={tryOnStatus}
            resultUrl={tryOnUrl}
            error={tryOnError}
            colorName={color?.name ?? null}
            isMock={isMock}
          />
        </div>
      )}

      <footer className="mt-16 border-t border-stone-200 pt-6 text-xs text-stone-500">
        Skin tone and undertone are detected locally from the uploaded image.
        Virtual try-on is powered by the YouCam Apparel VTO API.
      </footer>
    </main>
  );
}
