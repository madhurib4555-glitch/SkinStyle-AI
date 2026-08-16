"use client";

interface Props {
  status: "idle" | "loading" | "done" | "error";
  resultUrl: string | null;
  error: string | null;
  colorName: string | null;
  isMock: boolean;
}

export default function TryOnResult({
  status,
  resultUrl,
  error,
  colorName,
  isMock,
}: Props) {
  if (status === "idle") return null;

  return (
    <section
      className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm"
      aria-live="polite"
    >
      <h2 className="text-lg font-semibold text-stone-900">Your try-on</h2>

      {status === "loading" && (
        <div className="mt-4 flex h-72 flex-col items-center justify-center gap-3 rounded-xl bg-stone-50">
          <span
            className="h-7 w-7 animate-spin rounded-full border-2 border-stone-300 border-t-stone-800"
            aria-hidden="true"
          />
          <p className="text-sm text-stone-600">
            Generating your try-on{colorName ? ` in ${colorName}` : ""}…
          </p>
        </div>
      )}

      {status === "error" && (
        <p role="alert" className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">
          {error ?? "Something went wrong generating the try-on."}
        </p>
      )}

      {status === "done" && resultUrl && (
        <>
          {/* Plain <img>: the mock returns a base64 data URL and the live API a
              signed remote URL; next/image cannot optimise either. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={resultUrl}
            alt={`Virtual try-on result${colorName ? ` in ${colorName}` : ""}`}
            className="mt-4 w-full rounded-xl border border-stone-200"
          />

          <a
            href={resultUrl}
            download="skinstyle-tryon.jpg"
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-stone-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-stone-700"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
              />
            </svg>
            Download
          </a>

          {isMock && (
            <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900">
              <strong className="font-semibold">Placeholder preview.</strong>{" "}
              No YouCam credentials are configured, so this is a simple overlay
              rather than real virtual try-on. Set{" "}
              <code className="font-mono">YOUCAM_API_KEY</code> and{" "}
              <code className="font-mono">YOUCAM_SECRET_KEY</code> to enable
              genuine garment fitting.
            </p>
          )}
        </>
      )}
    </section>
  );
}
