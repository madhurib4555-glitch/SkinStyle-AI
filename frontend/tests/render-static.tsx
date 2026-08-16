/**
 * Static render harness for visual inspection.
 *
 * Renders the real components to /tmp/render.html using real backend fixture
 * data, so the UI can be screenshotted without binding a port. Runs under
 * Vitest because it is the only TS runner available in this sandbox (tsx needs
 * an IPC socket). Skips silently when the fixture is absent, so it never breaks
 * a normal `npm test` run.
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { it } from "vitest";

import AnalysisCard from "@/components/AnalysisCard";
import ColorRecommendations from "@/components/ColorRecommendations";
import GarmentPicker from "@/components/GarmentPicker";
import SelfieUploader from "@/components/SelfieUploader";
import TryOnResult from "@/components/TryOnResult";
import type { AnalyzeResponse, Garment } from "@/lib/api";

const FIXTURE = "/tmp/fixture.json";

interface Fixture {
  analyze: Omit<AnalyzeResponse, "image_id">;
  selfie: string;
  garments: Garment[];
  previews: Record<string, string>;
  tryon: string;
}

it.skipIf(!existsSync(FIXTURE))("renders the page to /tmp/render.html", () => {
  const fixture: Fixture = JSON.parse(readFileSync(FIXTURE, "utf8"));
  const { analyze } = fixture;
  const topColor = analyze.recommendations[0];

  const markup = renderToStaticMarkup(
    <main className="mx-auto max-w-3xl px-5 py-12 sm:py-16">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight text-stone-900 sm:text-4xl">
          SkinStyle AI
        </h1>
        <p className="mt-3 text-base leading-relaxed text-stone-600">
          Upload a selfie to find the clothing colours that complement your skin
          tone — and see them on you before you buy.
        </p>
      </header>

      <div className="mt-10">
        <SelfieUploader onSelect={() => {}} />
      </div>

      <div className="mt-6 flex items-center gap-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={fixture.selfie}
          alt="Your uploaded selfie"
          className="h-24 w-24 rounded-xl border border-stone-200 object-cover"
        />
      </div>

      <div className="mt-10 space-y-10">
        <AnalysisCard analysis={analyze.analysis} summary={analyze.summary} />
        <ColorRecommendations
          recommendations={analyze.recommendations}
          avoid={analyze.avoid}
          selectedHex={topColor.hex}
          onSelect={() => {}}
        />
        <GarmentPicker
          garments={fixture.garments}
          color={topColor}
          selectedGarmentId="hoodie"
          onSelect={() => {}}
        />
        <TryOnResult
          status="done"
          resultUrl={fixture.tryon}
          error={null}
          colorName={topColor.name}
          isMock
        />
      </div>

      <footer className="mt-16 border-t border-stone-200 pt-6 text-xs text-stone-500">
        Skin tone and undertone are detected locally from the uploaded image.
        Virtual try-on is powered by the YouCam Apparel VTO API.
      </footer>
    </main>,
  );

  // Garment previews normally come from the API; inline them since the harness
  // has no server to fetch from.
  const inlined = markup.replace(
    /src="[^"]*\/api\/garments\/([a-z]+)\/preview[^"]*"/g,
    (_m, id: string) => `src="${fixture.previews[id]}"`,
  );

  writeFileSync("/tmp/render-body.html", inlined);

  // Generate the real Tailwind CSS for exactly these class names, so the
  // screenshot reflects the app's actual styles rather than an approximation.
  // The input file must sit inside the project so `@import "tailwindcss"`
  // resolves against node_modules. cwd is the frontend root under Vitest;
  // import.meta.url is rewritten by the transform and is not usable here.
  const inputCss = join(process.cwd(), "tests", "render-input.css");
  writeFileSync(
    inputCss,
    `@import "tailwindcss" source(none);\n@source "/tmp/render-body.html";\n`,
  );
  execFileSync(
    "npx",
    ["@tailwindcss/cli", "-i", inputCss, "-o", "/tmp/render.css", "--minify"],
    { stdio: "pipe" },
  );

  const css = readFileSync("/tmp/render.css", "utf8");
  writeFileSync(
    "/tmp/render.html",
    `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>${css}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}</style>
</head><body class="bg-stone-50 text-stone-900">${inlined}</body></html>`,
  );
});
