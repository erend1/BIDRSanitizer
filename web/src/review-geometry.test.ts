import { describe, expect, it } from "vitest";

import {
  clientPointToImage,
  isBoundingBoxWithinImage,
  isUsableBoundingBox,
  normalizeBoundingBox,
  resizeBoundingBox,
  translateBoundingBox,
} from "./review-geometry";

describe("review geometry", () => {
  it("maps scaled client coordinates into original image pixels", () => {
    expect(
      clientPointToImage(
        250,
        150,
        { left: 50, top: 50, width: 400, height: 200 },
        1200,
        600,
      ),
    ).toEqual({ x: 600, y: 300 });
  });

  it("clamps client coordinates at the source boundaries", () => {
    expect(
      clientPointToImage(
        -100,
        900,
        { left: 20, top: 30, width: 200, height: 100 },
        1000,
        500,
      ),
    ).toEqual({ x: 0, y: 500 });
  });

  it("normalizes reverse drags with conservative outer rounding", () => {
    expect(
      normalizeBoundingBox(
        { x: 80.8, y: 60.2 },
        { x: 10.4, y: 20.7 },
        100,
        100,
      ),
    ).toEqual({ x1: 10, y1: 20, x2: 81, y2: 61 });
  });

  it("rejects tiny or out-of-image boxes", () => {
    expect(isUsableBoundingBox({ x1: 4, y1: 4, x2: 5, y2: 6 })).toBe(false);
    expect(
      isBoundingBoxWithinImage(
        { x1: 0, y1: 0, x2: 101, y2: 50 },
        100,
        100,
      ),
    ).toBe(false);
  });

  it("moves a box without changing its size and clamps it to the page", () => {
    expect(
      translateBoundingBox(
        { x1: 20, y1: 20, x2: 50, y2: 40 },
        80,
        -50,
        100,
        100,
      ),
    ).toEqual({ x1: 70, y1: 0, x2: 100, y2: 20 });
  });

  it("resizes from each corner while preserving a safe minimum size", () => {
    expect(
      resizeBoundingBox(
        { x1: 20, y1: 20, x2: 50, y2: 50 },
        "nw",
        { x: 48, y: 49 },
        100,
        100,
      ),
    ).toEqual({ x1: 48, y1: 48, x2: 50, y2: 50 });
    expect(
      resizeBoundingBox(
        { x1: 20, y1: 20, x2: 50, y2: 50 },
        "se",
        { x: 150, y: 90 },
        100,
        100,
      ),
    ).toEqual({ x1: 20, y1: 20, x2: 100, y2: 90 });
  });
});
