import { useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { BoundingBox, ReviewRegion } from "../api-types";
import {
  clientPointToImage,
  isUsableBoundingBox,
  normalizeBoundingBox,
  resizeBoundingBox,
  translateBoundingBox,
  type ImagePoint,
  type ResizeHandle,
} from "../review-geometry";
import { regionLabel } from "../review-labels";

interface DrawState {
  mode: "draw";
  pointerId: number;
  start: ImagePoint;
  current: ImagePoint;
}

interface EditState {
  mode: "move" | "resize";
  pointerId: number;
  regionId: string;
  start: ImagePoint;
  initial: BoundingBox;
  current: BoundingBox;
  handle: ResizeHandle;
}

type InteractionState = DrawState | EditState;

interface ReviewCanvasProps {
  imageUrl: string;
  imageWidth: number;
  imageHeight: number;
  regions: ReviewRegion[];
  selectedRegionId: string | null;
  drawingEnabled: boolean;
  onRegionSelect: (regionId: string) => void;
  onRegionGeometryChange: (regionId: string, bbox: BoundingBox) => void;
  onManualRegion: (bbox: BoundingBox) => void;
  onShortDrag: () => void;
}

function pointFromClient(
  clientX: number,
  clientY: number,
  svg: SVGSVGElement,
  imageWidth: number,
  imageHeight: number,
): ImagePoint {
  return clientPointToImage(
    clientX,
    clientY,
    svg.getBoundingClientRect(),
    imageWidth,
    imageHeight,
  );
}

function regionClassName(region: ReviewRegion, selected: boolean): string {
  const classes = ["review-region", `is-${region.provenance}`];
  classes.push(region.action === "retain" ? "is-retained" : "is-removed");
  if (region.geometry_modified) classes.push("is-geometry-modified");
  if (selected) classes.push("is-selected");
  return classes.join(" ");
}

function boxForRegion(
  region: ReviewRegion,
  interaction: InteractionState | null,
): BoundingBox {
  return interaction !== null &&
    interaction.mode !== "draw" &&
    interaction.regionId === region.region_id
    ? interaction.current
    : region.bbox;
}

export function ReviewCanvas({
  imageUrl,
  imageWidth,
  imageHeight,
  regions,
  selectedRegionId,
  drawingEnabled,
  onRegionSelect,
  onRegionGeometryChange,
  onManualRegion,
  onShortDrag,
}: ReviewCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [interaction, setInteraction] = useState<InteractionState | null>(null);
  const selectedRegion = regions.find(
    (region) => region.region_id === selectedRegionId,
  ) ?? null;

  const draftBox = useMemo(() => {
    if (interaction === null) return null;
    if (interaction.mode === "draw") {
      return normalizeBoundingBox(
        interaction.start,
        interaction.current,
        imageWidth,
        imageHeight,
      );
    }
    return interaction.current;
  }, [imageHeight, imageWidth, interaction]);

  function beginDraw(event: ReactPointerEvent<SVGSVGElement>) {
    if (!drawingEnabled || event.button !== 0) return;
    event.preventDefault();
    const point = pointFromClient(
      event.clientX,
      event.clientY,
      event.currentTarget,
      imageWidth,
      imageHeight,
    );
    event.currentTarget.setPointerCapture(event.pointerId);
    setInteraction({
      mode: "draw",
      pointerId: event.pointerId,
      start: point,
      current: point,
    });
  }

  function beginEdit(
    event: ReactPointerEvent<SVGGElement | SVGCircleElement>,
    region: ReviewRegion,
    mode: "move" | "resize",
    handle?: ResizeHandle,
  ) {
    if (drawingEnabled || event.button !== 0 || region.action !== "retain") return;
    const svg = svgRef.current;
    if (svg === null) return;
    event.preventDefault();
    event.stopPropagation();
    onRegionSelect(region.region_id);
    const point = pointFromClient(
      event.clientX,
      event.clientY,
      svg,
      imageWidth,
      imageHeight,
    );
    svg.setPointerCapture(event.pointerId);
    setInteraction({
      mode,
      pointerId: event.pointerId,
      regionId: region.region_id,
      start: point,
      initial: region.bbox,
      current: region.bbox,
      handle: handle ?? "se",
    });
  }

  function handlePointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    if (interaction === null || interaction.pointerId !== event.pointerId) return;
    const point = pointFromClient(
      event.clientX,
      event.clientY,
      event.currentTarget,
      imageWidth,
      imageHeight,
    );
    setInteraction((previous) => {
      if (previous === null) return null;
      if (previous.mode === "draw") return { ...previous, current: point };
      if (previous.mode === "move") {
        return {
          ...previous,
          current: translateBoundingBox(
            previous.initial,
            point.x - previous.start.x,
            point.y - previous.start.y,
            imageWidth,
            imageHeight,
          ),
        };
      }
      return {
        ...previous,
        current: resizeBoundingBox(
          previous.initial,
          previous.handle ?? "se",
          point,
          imageWidth,
          imageHeight,
        ),
      };
    });
  }

  function finishPointer(event: ReactPointerEvent<SVGSVGElement>) {
    if (interaction === null || interaction.pointerId !== event.pointerId) return;
    const completed = interaction;
    setInteraction(null);
    if (completed.mode === "draw") {
      const point = pointFromClient(
        event.clientX,
        event.clientY,
        event.currentTarget,
        imageWidth,
        imageHeight,
      );
      const box = normalizeBoundingBox(
        completed.start,
        point,
        imageWidth,
        imageHeight,
      );
      if (isUsableBoundingBox(box)) onManualRegion(box);
      else onShortDrag();
      return;
    }
    if (isUsableBoundingBox(completed.current)) {
      onRegionGeometryChange(completed.regionId, completed.current);
    }
  }

  const selectedBox = selectedRegion === null
    ? null
    : boxForRegion(selectedRegion, interaction);
  const handleRadius = Math.max(5, Math.min(imageWidth, imageHeight) * 0.008);

  return (
    <div className="review-canvas-frame">
      <svg
        ref={svgRef}
        className={`review-canvas${drawingEnabled ? " is-drawing" : ""}`}
        viewBox={`0 0 ${imageWidth} ${imageHeight}`}
        width={imageWidth}
        height={imageHeight}
        role="img"
        aria-label="Sensitive source preview with editable privacy regions"
        onPointerDown={beginDraw}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPointer}
        onPointerCancel={() => setInteraction(null)}
      >
        <title>Sensitive source preview and editable review geometry</title>
        <image href={imageUrl} x="0" y="0" width={imageWidth} height={imageHeight} preserveAspectRatio="none" />

        {regions.map((region) => {
          const bbox = boxForRegion(region, interaction);
          return (
            <g
              key={region.region_id}
              className={regionClassName(region, selectedRegionId === region.region_id)}
              onPointerDown={(event) => beginEdit(event, region, "move")}
              onClick={(event) => {
                if (!drawingEnabled) {
                  event.stopPropagation();
                  onRegionSelect(region.region_id);
                }
              }}
            >
              <title>{regionLabel(region)} — drag to move</title>
              <rect
                x={bbox.x1}
                y={bbox.y1}
                width={bbox.x2 - bbox.x1}
                height={bbox.y2 - bbox.y1}
                vectorEffect="non-scaling-stroke"
              />
            </g>
          );
        })}

        {selectedRegion !== null && selectedBox !== null &&
          selectedRegion.action === "retain" && !drawingEnabled &&
          ([
            ["nw", selectedBox.x1, selectedBox.y1],
            ["ne", selectedBox.x2, selectedBox.y1],
            ["se", selectedBox.x2, selectedBox.y2],
            ["sw", selectedBox.x1, selectedBox.y2],
          ] as const).map(([handle, cx, cy]) => (
            <circle
              key={handle}
              className={`resize-handle is-${handle}`}
              cx={cx}
              cy={cy}
              r={handleRadius}
              vectorEffect="non-scaling-stroke"
              aria-label={`Resize selected region from ${handle} corner`}
              onPointerDown={(event) =>
                beginEdit(event, selectedRegion, "resize", handle)
              }
            />
          ))}

        {interaction?.mode === "draw" && draftBox !== null && (
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
        <span><i className="key-auto" /> Automatic / editable</span>
        <span><i className="key-manual" /> Manual / editable</span>
        <span><i className="key-removed" /> Kept visible</span>
      </div>
    </div>
  );
}
