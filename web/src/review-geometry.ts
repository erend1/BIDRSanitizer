import type { BoundingBox } from "./api-types";

export interface ImagePoint {
  x: number;
  y: number;
}

export interface ClientBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

export type ResizeHandle = "nw" | "ne" | "se" | "sw";

export function translateBoundingBox(
  bbox: BoundingBox,
  deltaX: number,
  deltaY: number,
  imageWidth: number,
  imageHeight: number,
): BoundingBox {
  const width = bbox.x2 - bbox.x1;
  const height = bbox.y2 - bbox.y1;
  const x1 = clamp(Math.round(bbox.x1 + deltaX), 0, imageWidth - width);
  const y1 = clamp(Math.round(bbox.y1 + deltaY), 0, imageHeight - height);
  return { x1, y1, x2: x1 + width, y2: y1 + height };
}

export function resizeBoundingBox(
  bbox: BoundingBox,
  handle: ResizeHandle,
  point: ImagePoint,
  imageWidth: number,
  imageHeight: number,
  minimumSize = 2,
): BoundingBox {
  const x = clamp(Math.round(point.x), 0, imageWidth);
  const y = clamp(Math.round(point.y), 0, imageHeight);
  const leftHandle = handle === "nw" || handle === "sw";
  const topHandle = handle === "nw" || handle === "ne";

  return {
    x1: leftHandle ? clamp(x, 0, bbox.x2 - minimumSize) : bbox.x1,
    y1: topHandle ? clamp(y, 0, bbox.y2 - minimumSize) : bbox.y1,
    x2: leftHandle ? bbox.x2 : clamp(x, bbox.x1 + minimumSize, imageWidth),
    y2: topHandle ? bbox.y2 : clamp(y, bbox.y1 + minimumSize, imageHeight),
  };
}

export function clientPointToImage(
  clientX: number,
  clientY: number,
  bounds: ClientBounds,
  imageWidth: number,
  imageHeight: number,
): ImagePoint {
  if (bounds.width <= 0 || bounds.height <= 0) {
    throw new Error("The review canvas must have positive dimensions.");
  }

  return {
    x: clamp(((clientX - bounds.left) / bounds.width) * imageWidth, 0, imageWidth),
    y: clamp(
      ((clientY - bounds.top) / bounds.height) * imageHeight,
      0,
      imageHeight,
    ),
  };
}

export function normalizeBoundingBox(
  start: ImagePoint,
  end: ImagePoint,
  imageWidth: number,
  imageHeight: number,
): BoundingBox {
  const x1 = clamp(Math.floor(Math.min(start.x, end.x)), 0, imageWidth);
  const y1 = clamp(Math.floor(Math.min(start.y, end.y)), 0, imageHeight);
  const x2 = clamp(Math.ceil(Math.max(start.x, end.x)), 0, imageWidth);
  const y2 = clamp(Math.ceil(Math.max(start.y, end.y)), 0, imageHeight);

  return { x1, y1, x2, y2 };
}

export function isUsableBoundingBox(
  bbox: BoundingBox,
  minimumSize = 2,
): boolean {
  return bbox.x2 - bbox.x1 >= minimumSize && bbox.y2 - bbox.y1 >= minimumSize;
}

export function isBoundingBoxWithinImage(
  bbox: BoundingBox,
  imageWidth: number,
  imageHeight: number,
): boolean {
  return (
    Number.isInteger(bbox.x1) &&
    Number.isInteger(bbox.y1) &&
    Number.isInteger(bbox.x2) &&
    Number.isInteger(bbox.y2) &&
    bbox.x1 >= 0 &&
    bbox.y1 >= 0 &&
    bbox.x2 > bbox.x1 &&
    bbox.y2 > bbox.y1 &&
    bbox.x2 <= imageWidth &&
    bbox.y2 <= imageHeight
  );
}
