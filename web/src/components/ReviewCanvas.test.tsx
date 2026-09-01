import { fireEvent, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReviewRegion } from "../api-types";
import { ReviewCanvas } from "./ReviewCanvas";

const automaticRegion: ReviewRegion = {
  region_id: "automatic-1",
  bbox: { x1: 10, y1: 10, x2: 30, y2: 30 },
  provenance: "automatic",
  action: "retain",
  detection_type: "face",
  confidence: 0.95,
  geometry_modified: false,
};

function renderCanvas(
  selectedRegionId: string | null,
  onRegionGeometryChange = vi.fn(),
) {
  const result = render(
    <ReviewCanvas
      imageUrl="blob:private-source"
      imageWidth={100}
      imageHeight={100}
      regions={[automaticRegion]}
      selectedRegionId={selectedRegionId}
      drawingEnabled={false}
      onRegionSelect={vi.fn()}
      onRegionGeometryChange={onRegionGeometryChange}
      onManualRegion={vi.fn()}
      onShortDrag={vi.fn()}
    />,
  );
  const svg = result.container.querySelector("svg.review-canvas") as SVGSVGElement;
  vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: 100,
    bottom: 100,
    width: 100,
    height: 100,
    toJSON: () => ({}),
  });
  Object.defineProperty(svg, "setPointerCapture", {
    configurable: true,
    value: vi.fn(),
  });
  return { ...result, svg };
}

describe("ReviewCanvas editing", () => {
  beforeEach(() => {
    if (!(globalThis as { PointerEvent?: typeof MouseEvent }).PointerEvent) {
      Object.defineProperty(globalThis, "PointerEvent", {
        configurable: true,
        value: MouseEvent,
      });
    }
  });

  it("moves a retained automatic region in source-page coordinates", () => {
    const onGeometryChange = vi.fn();
    const { container, svg } = renderCanvas(null, onGeometryChange);
    const region = container.querySelector(".review-region");
    expect(region).not.toBeNull();

    fireEvent.pointerDown(region!, {
      button: 0,
      pointerId: 1,
      clientX: 15,
      clientY: 15,
    });
    fireEvent.pointerMove(svg, { pointerId: 1, clientX: 25, clientY: 35 });
    fireEvent.pointerUp(svg, { pointerId: 1, clientX: 25, clientY: 35 });

    expect(onGeometryChange).toHaveBeenCalledWith("automatic-1", {
      x1: 20,
      y1: 30,
      x2: 40,
      y2: 50,
    });
  });

  it("resizes a selected region from its south-east corner", () => {
    const onGeometryChange = vi.fn();
    const { container, svg } = renderCanvas("automatic-1", onGeometryChange);
    const handle = container.querySelector(".resize-handle.is-se");
    expect(handle).not.toBeNull();

    fireEvent.pointerDown(handle!, {
      button: 0,
      pointerId: 2,
      clientX: 30,
      clientY: 30,
    });
    fireEvent.pointerMove(svg, { pointerId: 2, clientX: 50, clientY: 60 });
    fireEvent.pointerUp(svg, { pointerId: 2, clientX: 50, clientY: 60 });

    expect(onGeometryChange).toHaveBeenCalledWith("automatic-1", {
      x1: 10,
      y1: 10,
      x2: 50,
      y2: 60,
    });
  });
});
