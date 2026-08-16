"use client";

import { useCallback, useRef, useState } from "react";

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 10 * 1024 * 1024;

interface Props {
  onSelect: (file: File, previewUrl: string) => void;
  disabled?: boolean;
}

export default function SelfieUploader({ onSelect, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = useCallback(
    (file: File | undefined) => {
      if (!file) return;

      // Validate client-side too: instant feedback, and it avoids a pointless
      // upload of a file the backend would reject anyway.
      if (!ACCEPTED.includes(file.type)) {
        setError("Please choose a JPEG, PNG or WebP image.");
        return;
      }
      if (file.size > MAX_BYTES) {
        setError("That image is over 10MB. Try a smaller one.");
        return;
      }

      setError(null);
      onSelect(file, URL.createObjectURL(file));
    },
    [onSelect],
  );

  return (
    <div className="w-full">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!disabled) accept(e.dataTransfer.files[0]);
        }}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          // Keyboard parity with the click handler; the div is the control.
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload a selfie"
        aria-disabled={disabled}
        className={`group relative flex min-h-[280px] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-3xl border-2 border-dashed px-6 py-14 text-center shadow-sm transition-all duration-300
  ${
    dragging
      ? "scale-[1.01] border-emerald-600 bg-emerald-50 shadow-lg"
      : "border-stone-200 bg-white hover:-translate-y-1 hover:border-emerald-400 hover:bg-emerald-50/30 hover:shadow-xl"
  }
  ${disabled ? "pointer-events-none opacity-50" : ""}`}
      >
        <svg
         className="mb-5 h-12 w-12 rounded-2xl bg-emerald-50 p-3 text-emerald-700 transition-transform duration-300 group-hover:scale-110"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 7.5L12 3m0 0L7.5 7.5M12 3v13.5"
          />
        </svg>
        <p className="text-lg font-semibold text-stone-900">
          Drop a selfie here, or click to browse
        </p>
        <p className="mt-2 max-w-md text-sm leading-6 text-stone-500">
          Front-facing, even lighting, no filters. JPEG, PNG or WebP up to 10MB.
        </p>

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          onChange={(e) => {
            accept(e.target.files?.[0]);
            // Reset so re-picking the same file still fires onChange.
            e.target.value = "";
          }}
        />
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <p className="mt-3 text-xs text-stone-500">
        Your photo is analysed to detect skin tone and is held in memory only —
        never written to disk — and discarded within 30 minutes.
      </p>
    </div>
  );
}
