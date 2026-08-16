"use client";

import { garmentPreviewUrl, type ColorRecommendation, type Garment } from "@/lib/api";

interface Props {
  garments: Garment[];
  color: ColorRecommendation;
  selectedGarmentId: string | null;
  onSelect: (garmentId: string) => void;
  disabled?: boolean;
}

export default function GarmentPicker({
  garments,
  color,
  selectedGarmentId,
  onSelect,
  disabled,
}: Props) {
  return (
    <section>
      <h2 className="text-lg font-semibold text-stone-900">
        Try it on in {color.name}
      </h2>
      <p className="mt-1 text-sm text-stone-600">
        Choose a garment to preview.
      </p>

      <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {garments.map((garment) => {
          const selected = selectedGarmentId === garment.id;
          return (
            <li key={garment.id}>
              <button
                type="button"
                onClick={() => onSelect(garment.id)}
                disabled={disabled}
                aria-pressed={selected}
                className={`w-full rounded-xl border p-2 transition disabled:opacity-50
                  ${
                    selected
                      ? "border-stone-900 ring-2 ring-stone-900/15"
                      : "border-stone-200 hover:border-stone-400"
                  }`}
              >
                {/* Plain <img>: the source is a dynamically tinted API route,
                    which next/image would need remotePatterns config for and
                    could not usefully optimise. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={garmentPreviewUrl(garment.id, color.hex)}
                  alt={`${garment.name} in ${color.name}`}
                  className="mx-auto h-28 w-auto object-contain"
                  loading="lazy"
                />
                <span className="mt-1 block text-center text-xs font-medium text-stone-700">
                  {garment.name}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
