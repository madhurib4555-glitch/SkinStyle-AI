/**
 * API client and shared types for the SkinStyle backend.
 *
 * Types mirror the Pydantic models in backend/app/models.py. They are kept in
 * sync by hand; the backend's OpenAPI schema at /docs is the source of truth if
 * they ever drift.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Undertone = "warm" | "cool" | "neutral";
export type ToneDepth = "fair" | "light" | "medium" | "tan" | "deep";
export type Season = "spring" | "summer" | "autumn" | "winter";

export interface SkinAnalysis {
  tone_depth: ToneDepth;
  undertone: Undertone;
  season: Season;
  skin_hex: string;
  lightness: number;
  contrast: number;
  confidence: number;
}

export interface ColorRecommendation {
  name: string;
  hex: string;
  rationale: string;
  score: number;
}

export interface ColorToAvoid {
  name: string;
  hex: string;
  reason: string;
}

export interface AnalyzeResponse {
  image_id: string;
  summary: string;
  analysis: SkinAnalysis;
  recommendations: ColorRecommendation[];
  avoid: ColorToAvoid[];
  skin_concerns: Record<string, number> | null;
}

export interface Garment {
  id: string;
  name: string;
  category: string;
}

export interface TryOnResponse {
  task_id: string;
  status: string;
  result_url: string | null;
}

/** Error carrying the backend's user-facing `detail` message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function unwrap<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>;

  // FastAPI puts human-readable text in `detail` for HTTPException, but returns
  // an array of field errors for 422 validation failures.
  let detail = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      detail = body.detail[0].msg;
    }
  } catch {
    // Non-JSON error body; keep the status-based fallback.
  }
  throw new ApiError(detail, response.status);
}

export async function analyzeSelfie(file: File): Promise<AnalyzeResponse> {
  const body = new FormData();
  body.append("file", file);
  return unwrap<AnalyzeResponse>(
    await fetch(`${API_BASE}/api/analyze`, { method: "POST", body }),
  );
}

export async function fetchGarments(): Promise<Garment[]> {
  const data = await unwrap<{ garments: Garment[] }>(
    await fetch(`${API_BASE}/api/garments`),
  );
  return data.garments;
}

export function garmentPreviewUrl(garmentId: string, colorHex: string): string {
  // encodeURIComponent: the leading '#' would otherwise be read as a fragment.
  return `${API_BASE}/api/garments/${garmentId}/preview?color=${encodeURIComponent(colorHex)}`;
}

export async function startTryOn(
  imageId: string,
  garmentId: string,
  colorHex: string,
): Promise<TryOnResponse> {
  return unwrap<TryOnResponse>(
    await fetch(`${API_BASE}/api/try-on`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_id: imageId,
        garment_id: garmentId,
        color_hex: colorHex,
      }),
    }),
  );
}

/**
 * Poll a try-on task until it completes.
 *
 * Bounded by `attempts` so a stuck upstream task cannot spin forever; the
 * default allows roughly 60s at the 1.5s interval, comfortably longer than a
 * normal VTO render.
 */
export async function awaitTryOn(
  taskId: string,
  { intervalMs = 1500, attempts = 40 }: { intervalMs?: number; attempts?: number } = {},
): Promise<string> {
  for (let i = 0; i < attempts; i++) {
    const result = await unwrap<TryOnResponse>(
      await fetch(`${API_BASE}/api/try-on/${taskId}`),
    );
    if (result.status === "success" && result.result_url) {
      return result.result_url;
    }
    if (result.status === "error") {
      throw new ApiError("The try-on could not be generated.", 502);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new ApiError("The try-on is taking longer than expected.", 504);
}
