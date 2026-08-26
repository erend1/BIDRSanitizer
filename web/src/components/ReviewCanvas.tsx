import { useState, type PointerEvent as ReactPointerEvent } from "react";

import type { BoundingBox, ReviewRegion } from "../api-types";
import {
  clientPointToImage,
  isUsableBoundingBox,
  normalizeBoundingBox,
  type ImagePoint,
} from "../review-geometry";
import { regionLabel } from "../review-labels";

interface DragState {
  pointerId: number;
  start: ImagePoint;
  current: ImagePoint;
}

interface ReviewCanvasProps {
  imageUrl: string;
  imageWidth: number;
  imageHeight: number;
  regions: ReviewRegion[];
  selectedRegionId: string | null;
  drawingEnabled: boolean;
  onRegionSelect: (regionId: string) => void;
  onManualRegion: (bbox: BoundingBox) => void;
  onShortDrag: () => void;
}

function pointerToImage(
  event: ReactPointerEvent<SVGSVGElement>,
  imageWidth: number,
  imageHeight: number,
): ImagePoint {
  const bounds = event.currentTarget.getBoundingClientRect();
  return clientPointToImage(
    event.clientX,
    event.clientY,
    bounds,
    imageWidth,
    imageHeight,
  );
}

function regionClassName(region: ReviewRegion, selected: boolean): string {
  const classes = ["review-region", `is-${region.provenance}`];
  classes.push(region.action === "retain" ? "is-retained" : "is-removed");
  if (selected) {
    classes.push("is-selected");
  }
  return classes.join(" ");
}

export function ReviewCanvas({
  imageUrl,
  imageWidth,
  imageHeight,
  regions,
  selectedRegionId,
  drawingEnabled,
  onRegionSelect,
  onManualRegion,
  onShortDrag,
}: ReviewCanvasProps) {
  const [drag, setDrag] = useState<DragState | null>(null);

  const draftBox =
    drag === null
      ? null
      : normalizeBoundingBox(drag.start, drag.current, imageWidth, imageHeight);

  function handlePointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (!drawingEnabled || event.button !== 0) {
      return;
    }

    event.preventDefault();
    const point = pointerToImage(event, imageWidth, imageHeight);
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ pointerId: event.pointerId, start: point, current: point });
  }

  function handlePointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    if (drag === null || drag.pointerId !== event.pointerId) {
      return;
    }

    const current = pointerToImage(event, imageWidth, imageHeight);
    setDrag((previous) => (previous === null ? null : { ...previous, current }));
  }

  function finishPointer(event: ReactPointerEvent<SVGSVGElement>) {
    if (drag === null || drag.pointerId !== event.pointerId) {
      return;
    }

    const current = pointerToImage(event, imageWidth, imageHeight);
    const completed = normalizeBoundingBox(
      drag.start,
      current,
      imageWidth,
      imageHeight,
    );
    setDrag(null);

    if (isUsableBoundingBox(completed)) {
      onManualRegion(completed);
    } else {
      onShortDrag();
    }
  }

  return (
    <div className="review-canvas-frame">
      <svg
        className={`review-canvas${drawingEnabled ? " is-drawing" : ""}`}
        viewBox={`0 0 ${imageWidth} ${imageHeight}`}
        width={imageWidth}
        height={imageHeight}
        role="img"
        aria-label="Sensitive source preview with proposed privacy regions"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPointer}
        onPointerCancel={() => setDrag(null)}
      >
        <title>Sensitive source preview and review geometry</title>
        <image
          href={imageUrl}
          x="0"
          y="0"
          width={imageWidth}
          height={imageHeight}
          preserveAspectRatio="none"
        />

        {regions.map((region) => (
          <g
            key={region.region_id}
            className={regionClassName(
              region,
              selectedRegionId === region.region_id,
            )}
            onClick={(event) => {
              if (!drawingEnabled) {
                event.stopPropagation();
                onRegionSelect(region.region_id);
              }
            }}
          >
            <title>
              {regionLabel(region)} — {region.action === "retain" ? "redact" : "keep"}
            </title>
            <rect
              x={region.bbox.x1}
              y={region.bbox.y1}
              width={region.bbox.x2 - region.bbox.x1}
              height={region.bbox.y2 - region.bbox.y1}
              vectorEffect="non-scaling-stroke"
            />
          </g>
        ))}

        {draftBox !== null && (
          <rect
            className="drawing-region"
            x={draftBox.x1}
            y={draftBox.y1}
            width={draftBox.x2 - draftBox.x1}
            height={draftBox.y2 - draftBox.y1}
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>

      <div className="canvas-key" aria-hidden="true">
        <span><i className="key-auto" /> Automatic</span>
        <span><i className="key-manual" /> Manual</span>
        <span><i className="key-removed" /> Kept visible</span>
      </div>
    </div>
  );
}
