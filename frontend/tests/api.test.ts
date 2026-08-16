import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  analyzeSelfie,
  awaitTryOn,
  fetchGarments,
  garmentPreviewUrl,
  startTryOn,
} from "@/lib/api";

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("garmentPreviewUrl", () => {
  it("encodes the '#' so it is not parsed as a fragment", () => {
    const url = garmentPreviewUrl("tshirt", "#0f7b6c");
    expect(url).toContain("color=%230f7b6c");
    expect(url).not.toContain("#0f7b6c");
  });
});

describe("error unwrapping", () => {
  it("surfaces a string `detail` from FastAPI", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "No face found in the uploaded image." }, 422),
      ),
    );

    await expect(analyzeSelfie(new File([""], "s.jpg"))).rejects.toThrow(
      "No face found in the uploaded image.",
    );
  });

  it("surfaces the first message from a 422 validation array", async () => {
    // Pydantic returns detail as an array of field errors, not a string.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { detail: [{ msg: "String should match pattern", loc: ["body"] }] },
          422,
        ),
      ),
    );

    await expect(startTryOn("img", "tshirt", "navy")).rejects.toThrow(
      "String should match pattern",
    );
  });

  it("falls back to the status code when the body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error("not json");
        },
      } as unknown as Response),
    );

    await expect(fetchGarments()).rejects.toThrow("Request failed (500)");
  });

  it("attaches the HTTP status to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "too big" }, 413)),
    );

    await expect(analyzeSelfie(new File([""], "s.jpg"))).rejects.toMatchObject({
      name: "ApiError",
      status: 413,
    });
  });
});

describe("analyzeSelfie", () => {
  it("posts the file as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ image_id: "abc", recommendations: [] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await analyzeSelfie(new File(["x"], "selfie.jpg", { type: "image/jpeg" }));

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    // Field name must be "file" to match the FastAPI parameter.
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });
});

describe("awaitTryOn", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("polls until the task succeeds and returns the url", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "running", result_url: null }))
      .mockResolvedValueOnce(jsonResponse({ status: "running", result_url: null }))
      .mockResolvedValueOnce(
        jsonResponse({ status: "success", result_url: "data:image/jpeg;base64,AAA" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const promise = awaitTryOn("task-1", { intervalMs: 10 });
    await vi.runAllTimersAsync();

    await expect(promise).resolves.toBe("data:image/jpeg;base64,AAA");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("rejects when the task reports an error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ status: "error", result_url: null })),
    );

    // Assert on the promise before advancing timers: attaching the rejection
    // handler first avoids an unhandled-rejection warning, which would
    // otherwise mask genuine ones.
    const assertion = expect(
      awaitTryOn("task-2", { intervalMs: 10 }),
    ).rejects.toThrow("could not be generated");
    await vi.runAllTimersAsync();
    await assertion;
  });

  it("gives up after the attempt budget instead of polling forever", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ status: "running", result_url: null }));
    vi.stubGlobal("fetch", fetchMock);

    const assertion = expect(
      awaitTryOn("task-3", { intervalMs: 10, attempts: 4 }),
    ).rejects.toThrow("longer than expected");
    await vi.runAllTimersAsync();
    await assertion;

    // Bounded: must not exceed the budget.
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not treat success without a url as done", async () => {
    // Guards the `result.result_url` half of the success condition.
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "success", result_url: null }))
      .mockResolvedValueOnce(
        jsonResponse({ status: "success", result_url: "data:image/jpeg;base64,BBB" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const promise = awaitTryOn("task-4", { intervalMs: 10 });
    await vi.runAllTimersAsync();

    await expect(promise).resolves.toBe("data:image/jpeg;base64,BBB");
  });
});

describe("ApiError", () => {
  it("is an Error subclass so instanceof checks work in components", () => {
    const err = new ApiError("nope", 400);
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
  });
});
