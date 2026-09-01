import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  detectionTypes,
  type BoundingBox,
  type DetectionType,
  type ReviewPlan,
  type ReviewRegion,
} from "../api-types";
import { isBoundingBoxWithinImage } from "../review-geometry";
import { detectionLabels, regionLabel } from "../review-labels";
import { ReviewCanvas } from "./ReviewCanvas";

interface CoordinateDraft {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface ReviewWorkspaceProps {
  imageUrl: string;
  plan: ReviewPlan;
  regions: ReviewRegion[];
  selectedRegionId: string | null;
  hasPendingChanges: boolean;
  hasOtherPageChanges: boolean;
  busyLabel: string | null;
  pageNumber: number;
  pageCount: number;
  onPageChange: (pageNumber: number) => void;
  onSelectRegion: (regionId: string | null) => void;
  onActionChange: (regionId: string, action: "retain" | "remove") => void;
  onRegionGeometryChange: (regionId: string, bbox: BoundingBox) => void;
  onManualRegion: (bbox: BoundingBox, detectionType: DetectionType | null) => void;
  onSave: () => void;
  onExport: () => void;
  onStartOver: () => void;
}

function confidenceLabel(confidence: number | null): string {
  return confidence === null ? "Manual" : `${Math.round(confidence * 100)}% confidence`;
}

export function ReviewWorkspace({
  imageUrl,
  plan,
  regions,
  selectedRegionId,
  hasPendingChanges,
  hasOtherPageChanges,
  busyLabel,
  pageNumber,
  pageCount,
  onPageChange,
  onSelectRegion,
  onActionChange,
  onRegionGeometryChange,
  onManualRegion,
  onSave,
  onExport,
  onStartOver,
}: ReviewWorkspaceProps) {
  const [drawingEnabled, setDrawingEnabled] = useState(false);
  const [manualType, setManualType] = useState<DetectionType | null>(null);
  const [canvasNotice, setCanvasNotice] = useState<string | null>(null);
  const [coordinateError, setCoordinateError] = useState<string | null>(null);
  const [coordinates, setCoordinates] = useState<CoordinateDraft>({
    x1: 0,
    y1: 0,
    x2: Math.min(100, plan.image_width),
    y2: Math.min(100, plan.image_height),
  });

  const selectedRegion =
    regions.find((region) => region.region_id === selectedRegionId) ?? null;
  const planRegionIds = useMemo(
    () => new Set(plan.regions.map((region) => region.region_id)),
    [plan.regions],
  );
  const automaticCount = regions.filter(
    (region) => region.provenance === "automatic",
  ).length;
  const manualCount = regions.filter(
    (region) => region.provenance === "manual" && region.action === "retain",
  ).length;
  const overrideCount = regions.filter(
    (region) =>
      region.provenance === "automatic" && region.action === "remove",
  ).length;
  const geometryOverrideCount = regions.filter(
    (region) => region.provenance === "automatic" && region.geometry_modified,
  ).length;
  const retainedCount = regions.filter((region) => region.action === "retain").length;

  function addManualBox(bbox: BoundingBox) {
    setCanvasNotice(null);
    onManualRegion(bbox, manualType);
  }

  function addCoordinates(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const bbox: BoundingBox = coordinates;
    if (!isBoundingBoxWithinImage(bbox, plan.image_width, plan.image_height)) {
      setCoordinateError(
        `Use whole-pixel coordinates inside ${plan.image_width} × ${plan.image_height}.`,
      );
      return;
    }

    setCoordinateError(null);
    onManualRegion(bbox, manualType);
  }

  useEffect(() => {
    setCoordinates({
      x1: 0,
      y1: 0,
      x2: Math.min(100, plan.image_width),
      y2: Math.min(100, plan.image_height),
    });
    setCanvasNotice(null);
    setCoordinateError(null);
    setDrawingEnabled(false);
  }, [plan.image_height, plan.image_width, plan.plan_id]);

  return (
    <main id="main" className="review-layout">
      <header className="workspace-heading">
        <div>
          <p className="eyebrow">Sensitive source preview</p>
          <h1>Review every proposed region</h1>
          <p>
            Boxes are only a visual plan. Pixels are permanently replaced during
            export, then the new image is scanned again.
          </p>
        </div>
        <div className="review-summary" aria-label="Review region summary">
          <span><b>{automaticCount}</b> automatic</span>
          <span><b>{manualCount}</b> manual</span>
          <span><b>{retainedCount}</b> to redact</span>
        </div>
      </header>

      {pageCount > 1 && (
        <nav className="page-navigation" aria-label="PDF page navigation">
          <button
            type="button"
            disabled={pageNumber <= 1 || busyLabel !== null}
            onClick={() => onPageChange(pageNumber - 1)}
          >
            Previous page
          </button>
          <label>
            PDF page
            <select
              value={pageNumber}
              disabled={busyLabel !== null}
              onChange={(event) => onPageChange(Number(event.currentTarget.value))}
            >
              {Array.from({ length: pageCount }, (_, index) => index + 1).map(
                (page) => <option key={page} value={page}>{page} / {pageCount}</option>,
              )}
            </select>
          </label>
          <button
            type="button"
            disabled={pageNumber >= pageCount || busyLabel !== null}
            onClick={() => onPageChange(pageNumber + 1)}
          >
            Next page
          </button>
        </nav>
      )}

      {(overrideCount > 0 || geometryOverrideCount > 0) && (
        <div className="override-warning" role="status">
          <span aria-hidden="true">!</span>
          <p>
            <strong>{overrideCount + geometryOverrideCount} human {
              overrideCount + geometryOverrideCount === 1 ? "override" : "overrides"
            }</strong>
            Moving or resizing an automatic region, or marking one “keep visible,” is
            recorded as a human override. The export cannot receive an ordinary passed
            status while these decisions remain.
          </p>
        </div>
      )}

      <section className="canvas-panel" aria-labelledby="canvas-heading">
        <div className="canvas-toolbar">
          <div>
            <span className="sensitive-badge">Sensitive original</span>
            <h2 id="canvas-heading">Review canvas</h2>
          </div>
          <div className="drawing-tools">
            <label>
              New box category
              <select
                value={manualType ?? ""}
                onChange={(event) =>
                  setManualType(
                    event.currentTarget.value === ""
                      ? null
                      : (event.currentTarget.value as DetectionType),
                  )
                }
              >
                <option value="">Privacy region</option>
                {detectionTypes.map((type) => (
                  <option key={type} value={type}>{detectionLabels[type]}</option>
                ))}
              </select>
            </label>
            <button
              className={drawingEnabled ? "tool-button is-active" : "tool-button"}
              type="button"
              aria-pressed={drawingEnabled}
              onClick={() => {
                setCanvasNotice(null);
                setDrawingEnabled((enabled) => !enabled);
              }}
            >
              <span aria-hidden="true">＋</span>
              {drawingEnabled ? "Finish drawing" : "Draw privacy box"}
            </button>
          </div>
        </div>

        {drawingEnabled && (
          <p className="drawing-instruction" role="status">
            Drag over the sensitive pixels. Coordinates remain in the original
            image’s {plan.image_width} × {plan.image_height} pixel space.
          </p>
        )}
        {canvasNotice !== null && (
          <p className="canvas-notice" role="status">{canvasNotice}</p>
        )}

        <ReviewCanvas
          imageUrl={imageUrl}
          imageWidth={plan.image_width}
          imageHeight={plan.image_height}
          regions={regions}
          selectedRegionId={selectedRegionId}
          drawingEnabled={drawingEnabled}
          onRegionSelect={(regionId) => onSelectRegion(regionId)}
          onRegionGeometryChange={onRegionGeometryChange}
          onManualRegion={addManualBox}
          onShortDrag={() =>
            setCanvasNotice("Draw a box at least 2 × 2 source pixels.")
          }
        />
      </section>

      <aside className="region-panel" aria-label="Review controls">
        <section className="region-inspector">
          <div className="panel-title-row">
            <div>
              <p className="step-label">Selected region</p>
              <h2>{selectedRegion === null ? "Choose a box" : regionLabel(selectedRegion)}</h2>
            </div>
            {selectedRegion !== null && (
              <span className={`provenance-chip is-${selectedRegion.provenance}`}>
                {selectedRegion.provenance}
              </span>
            )}
          </div>

          {selectedRegion === null ? (
            <p className="empty-inspector">
              Select a box on the canvas or in the list to inspect its source and
              decide whether its pixels should be removed.
            </p>
          ) : (
            <>
              <dl className="region-metadata">
                <div>
                  <dt>Coordinates</dt>
                  <dd>
                    {selectedRegion.bbox.x1}, {selectedRegion.bbox.y1} →{" "}
                    {selectedRegion.bbox.x2}, {selectedRegion.bbox.y2}
                  </dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{confidenceLabel(selectedRegion.confidence)}</dd>
                </div>
              </dl>

              {selectedRegion.action === "retain" && (
                <p className="edit-region-hint">
                  Drag the selected box to move it. Drag any corner handle to resize it.
                  Coordinates stay in source-page pixels.
                </p>
              )}

              {selectedRegion.provenance === "automatic" ? (
                <div className="decision-control" role="group" aria-label="Region decision">
                  <button
                    type="button"
                    className={selectedRegion.action === "retain" ? "is-selected" : ""}
                    onClick={() => onActionChange(selectedRegion.region_id, "retain")}
                  >
                    Redact pixels
                  </button>
                  <button
                    type="button"
                    className={selectedRegion.action === "remove" ? "is-selected is-risky" : ""}
                    onClick={() => onActionChange(selectedRegion.region_id, "remove")}
                  >
                    Keep visible · override
                  </button>
                </div>
              ) : (
                <button
                  className="remove-region-button"
                  type="button"
                  onClick={() =>
                    onActionChange(
                      selectedRegion.region_id,
                      selectedRegion.action === "retain" ? "remove" : "retain",
                    )
                  }
                >
                  {selectedRegion.action === "retain"
                    ? planRegionIds.has(selectedRegion.region_id)
                      ? "Exclude this manual region"
                      : "Delete this unsaved region"
                    : "Restore this manual region"}
                </button>
              )}
            </>
          )}
        </section>

        <section className="region-list-section">
          <div className="panel-title-row">
            <div>
              <p className="step-label">Review plan</p>
              <h2>{regions.length} regions</h2>
            </div>
            <span className="revision-chip">rev {plan.revision}</span>
          </div>
          {regions.length === 0 ? (
            <p className="empty-region-list">
              No automatic regions were found. Inspect the entire image and add
              any missed sensitive areas manually.
            </p>
          ) : (
            <ol className="region-list">
              {regions.map((region, index) => (
                <li key={region.region_id}>
                  <button
                    type="button"
                    className={`region-list-item${
                      selectedRegionId === region.region_id ? " is-selected" : ""
                    }${region.action === "remove" ? " is-removed" : ""}`}
                    onClick={() => onSelectRegion(region.region_id)}
                  >
                    <span className={`region-number is-${region.provenance}`}>
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span>
                      <strong>{regionLabel(region)}</strong>
                      <small>{confidenceLabel(region.confidence)}</small>
                    </span>
                    <em>{region.action === "retain" ? "Redact" : "Keep"}</em>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </section>

        <details className="coordinate-entry">
          <summary>Add a box with coordinates</summary>
          <form onSubmit={addCoordinates}>
            <div className="coordinate-grid">
              {(["x1", "y1", "x2", "y2"] as const).map((coordinate) => (
                <label key={coordinate}>
                  {coordinate.toUpperCase()}
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={coordinates[coordinate]}
                    onChange={(event) =>
                      setCoordinates((current) => ({
                        ...current,
                        [coordinate]: event.currentTarget.valueAsNumber || 0,
                      }))
                    }
                  />
                </label>
              ))}
            </div>
            {coordinateError !== null && <p role="alert">{coordinateError}</p>}
            <button type="submit">Add manual region</button>
          </form>
        </details>

        <section className="settings-receipt" aria-label="Applied export settings">
          <p className="step-label">Applied settings</p>
          <dl>
            <div><dt>Margin</dt><dd>{plan.settings.redaction_margin} px</dd></div>
            <div><dt>Max passes</dt><dd>{plan.settings.max_redaction_passes}</dd></div>
          </dl>
        </section>
      </aside>

      <footer className="review-actions">
        <button className="text-button" type="button" disabled={busyLabel !== null} onClick={onStartOver}>
          Discard session
        </button>
        <span className={hasPendingChanges ? "save-state is-pending" : "save-state"} role="status">
          {hasPendingChanges
            ? `Unsaved changes on page ${pageNumber}`
            : hasOtherPageChanges
            ? "Other PDF pages have unsaved changes"
            : `Page ${pageNumber} plan revision ${plan.revision} saved`}
        </span>
        <button
          className="secondary-button"
          type="button"
          disabled={!hasPendingChanges || busyLabel !== null}
          onClick={onSave}
        >
          Save review
        </button>
        <button
          className="primary-button"
          type="button"
          disabled={busyLabel !== null}
          onClick={onExport}
        >
          {busyLabel ?? ((hasPendingChanges || hasOtherPageChanges) ? "Save all & export" : "Export & verify")}
          <span aria-hidden="true">→</span>
        </button>
      </footer>
    </main>
  );
}
