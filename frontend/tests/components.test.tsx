import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AnalysisCard from "@/components/AnalysisCard";
import ColorRecommendations from "@/components/ColorRecommendations";
import SelfieUploader from "@/components/SelfieUploader";
import TryOnResult from "@/components/TryOnResult";
import type { SkinAnalysis } from "@/lib/api";

const analysis: SkinAnalysis = {
  tone_depth: "medium",
  undertone: "warm",
  season: "autumn",
  skin_hex: "#c8a080",
  lightness: 58,
  contrast: 25,
  confidence: 0.9,
};

const recommendations = [
  { name: "Olive Green", hex: "#6b7042", rationale: "Shares your warm cast.", score: 96 },
  { name: "Rust", hex: "#a9542a", rationale: "Deepens your complexion.", score: 89 },
];

const avoid = [{ name: "Icy Blue", hex: "#bcd6e8", reason: "Too cool for you." }];

describe("SelfieUploader", () => {
  it("rejects a non-image file dropped onto the zone", async () => {
    const onSelect = vi.fn();
    render(<SelfieUploader onSelect={onSelect} />);

    // Tested via drop, not the file input: userEvent.upload honours the input's
    // `accept` attribute and would drop the file before the handler runs, while
    // a real drag-and-drop can deliver any type. The drop path is the one that
    // genuinely needs validating.
    const zone = screen.getByRole("button", { name: /upload a selfie/i });
    fireEvent.drop(zone, {
      dataTransfer: {
        files: [new File(["x"], "doc.pdf", { type: "application/pdf" })],
      },
    });

    expect(onSelect).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/JPEG, PNG or WebP/i);
  });

  it("rejects an oversized file dropped onto the zone", async () => {
    const onSelect = vi.fn();
    render(<SelfieUploader onSelect={onSelect} />);

    const oversized = new File(["x"], "big.jpg", { type: "image/jpeg" });
    // Size is read-only on File, so define it directly.
    Object.defineProperty(oversized, "size", { value: 11 * 1024 * 1024 });

    const zone = screen.getByRole("button", { name: /upload a selfie/i });
    fireEvent.drop(zone, { dataTransfer: { files: [oversized] } });

    expect(onSelect).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/over 10MB/i);
  });

  it("rejects a file over the 10MB limit from the picker", async () => {
    const onSelect = vi.fn();
    render(<SelfieUploader onSelect={onSelect} />);

    const oversized = new File(["x"], "big.jpg", { type: "image/jpeg" });
    Object.defineProperty(oversized, "size", { value: 11 * 1024 * 1024 });

    const input = document.querySelector("input[type=file]") as HTMLInputElement;
    await userEvent.upload(input, oversized);

    expect(onSelect).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/over 10MB/i);
  });

  it("accepts a valid jpeg and passes a preview url", async () => {
    const onSelect = vi.fn();
    render(<SelfieUploader onSelect={onSelect} />);

    const input = document.querySelector("input[type=file]") as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["x"], "selfie.jpg", { type: "image/jpeg" }),
    );

    expect(onSelect).toHaveBeenCalledOnce();
    const [file, url] = onSelect.mock.calls[0];
    expect(file.name).toBe("selfie.jpg");
    expect(url).toMatch(/^blob:/);
  });

  it("states the privacy handling of the photo", () => {
    render(<SelfieUploader onSelect={vi.fn()} />);
    // Biometric data: the user must be told what happens to their image.
    expect(screen.getByText(/held in memory only/i)).toBeInTheDocument();
  });

  it("is reachable by keyboard", () => {
    render(<SelfieUploader onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /upload a selfie/i })).toHaveAttribute(
      "tabIndex",
      "0",
    );
  });
});

describe("AnalysisCard", () => {
  it("shows depth, undertone and season", () => {
    render(<AnalysisCard analysis={analysis} summary="Rich and warm." />);
    expect(screen.getByText("medium")).toBeInTheDocument();
    expect(screen.getByText("warm")).toBeInTheDocument();
    expect(screen.getByText("autumn")).toBeInTheDocument();
    expect(screen.getByText("Rich and warm.")).toBeInTheDocument();
  });

  it("warns when confidence is low", () => {
    render(
      <AnalysisCard
        analysis={{ ...analysis, confidence: 0.4 }}
        summary="Rich and warm."
      />,
    );
    // Users must not read a shaky result as authoritative.
    expect(screen.getByText(/Confidence is low \(40%\)/i)).toBeInTheDocument();
  });

  it("stays quiet when confidence is high", () => {
    render(<AnalysisCard analysis={analysis} summary="Rich and warm." />);
    expect(screen.queryByText(/Confidence is low/i)).not.toBeInTheDocument();
  });
});

describe("ColorRecommendations", () => {
  it("renders each colour with its score and rationale", () => {
    render(
      <ColorRecommendations
        recommendations={recommendations}
        avoid={avoid}
        selectedHex={null}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Olive Green")).toBeInTheDocument();
    expect(screen.getByText("96")).toBeInTheDocument();
    // The explanation is the product's core claim, so it must be shown.
    expect(screen.getByText("Shares your warm cast.")).toBeInTheDocument();
  });

  it("marks the selected colour with aria-pressed", () => {
    render(
      <ColorRecommendations
        recommendations={recommendations}
        avoid={avoid}
        selectedHex="#a9542a"
        onSelect={vi.fn()}
      />,
    );

    const buttons = screen.getAllByRole("button");
    const pressed = buttons.filter((b) => b.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).toHaveTextContent("Rust");
  });

  it("passes the chosen colour to onSelect", async () => {
    const onSelect = vi.fn();
    render(
      <ColorRecommendations
        recommendations={recommendations}
        avoid={avoid}
        selectedHex={null}
        onSelect={onSelect}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /Olive Green/ }));
    expect(onSelect).toHaveBeenCalledWith(recommendations[0]);
  });

  it("lists colours to avoid with reasons", () => {
    render(
      <ColorRecommendations
        recommendations={recommendations}
        avoid={avoid}
        selectedHex={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText(/Too cool for you/)).toBeInTheDocument();
  });
});

describe("TryOnResult", () => {
  it("renders nothing before a try-on starts", () => {
    const { container } = render(
      <TryOnResult status="idle" resultUrl={null} error={null} colorName={null} isMock={false} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a progress message while loading", () => {
    render(
      <TryOnResult status="loading" resultUrl={null} error={null} colorName="Rust" isMock={false} />,
    );
    expect(screen.getByText(/Generating your try-on in Rust/i)).toBeInTheDocument();
  });

  it("shows the result and a download link when done", () => {
    render(
      <TryOnResult
        status="done"
        resultUrl="data:image/jpeg;base64,AAA"
        error={null}
        colorName="Rust"
        isMock={false}
      />,
    );

    expect(screen.getByRole("img", { name: /try-on result in Rust/i })).toHaveAttribute(
      "src",
      "data:image/jpeg;base64,AAA",
    );
    expect(screen.getByRole("link", { name: /download/i })).toHaveAttribute(
      "download",
      "skinstyle-tryon.jpg",
    );
  });

  it("discloses that a mock result is not real virtual try-on", () => {
    render(
      <TryOnResult
        status="done"
        resultUrl="data:image/jpeg;base64,AAA"
        error={null}
        colorName="Rust"
        isMock
      />,
    );
    // Honesty about placeholder output; must not be silently passed off as VTO.
    expect(screen.getByText(/Placeholder preview/i)).toBeInTheDocument();
  });

  it("omits the mock disclaimer in live mode", () => {
    render(
      <TryOnResult
        status="done"
        resultUrl="data:image/jpeg;base64,AAA"
        error={null}
        colorName="Rust"
        isMock={false}
      />,
    );
    expect(screen.queryByText(/Placeholder preview/i)).not.toBeInTheDocument();
  });

  it("surfaces an error message", () => {
    render(
      <TryOnResult
        status="error"
        resultUrl={null}
        error="The try-on service rejected this request."
        colorName="Rust"
        isMock={false}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/rejected this request/i);
  });
});
