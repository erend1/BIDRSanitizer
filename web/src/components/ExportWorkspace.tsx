import type { ReviewedExport } from "../api-types";
import { detectionLabels, exportStatusPresentation } from "../review-labels";

interface ExportWorkspaceProps {
  result: ReviewedExport;
  exportUrl: string | null;
  imageWidth: number;
  imageHeight: number;
  busyLabel: string | null;
  onDownload: () => void;
  onContinueReview: () => void;
  onAddRemaining: () => void;
  onStartNew: () => void;
}

export function ExportWorkspace({
  result,
  exportUrl,
  imageWidth,
  imageHeight,
  busyLabel,
  onDownload,
  onContinueReview,
  onAddRemaining,
  onStartNew,
}: ExportWorkspaceProps) {
  const presentation = exportStatusPresentation(result.status);
  const remainingCount = result.remaining_detections.length;

  return (
    <main id="main" className={`export-layout tone-${presentation.tone}`}>
      <section className="export-result" aria-labelledby="export-heading">
        <span className="result-symbol" aria-hidden="true">
          {presentation.tone === "clear" ? "✓" : presentation.tone === "caution" ? "!" : "×"}
        </span>
        <p className="eyebrow">{presentation.eyebrow}</p>
        <h1 id="export-heading">{presentation.title}</h1>
        <p className="result-description">{presentation.description}</p>

        <div className="result-actions">
          <button
            className="primary-button"
            type="button"
            disabled={busyLabel !== null}
            onClick={onDownload}
          >
            {busyLabel ?? presentation.downloadLabel}
            <span aria-hidden="true">↓</span>
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={busyLabel !== null}
            onClick={onContinueReview}
          >
            Continue review
          </button>
        </div>

        <p className="legal-scope">
          Verification reports only what the currently configured detectors found
          in this output. Human review remains recommended for high-risk documents.
        </p>
      </section>

      <section className="export-preview" aria-labelledby="preview-heading">
        <div className="preview-heading-row">
          <div>
            <p className="step-label">Generated artifact</p>
            <h2 id="preview-heading">
              {result.status === "review_required" ? "Review artifact" : "Reviewed output"}
            </h2>
          </div>
          <span>{imageWidth} × {imageHeight} px</span>
        </div>
        <div className="export-image-frame">
          {exportUrl === null ? (
            <div className="preview-loading" role="status">
              Output preview unavailable. The artifact can still be fetched securely.
            </div>
          ) : (
            <img
              src={exportUrl}
              alt="Exported image after deterministic redaction"
              width={imageWidth}
              height={imageHeight}
            />
          )}
        </div>
      </section>

      <aside className="export-receipt" aria-label="Export verification receipt">
        <div className="panel-title-row">
          <div>
            <p className="step-label">Geometry-only receipt</p>
            <h2>Export summary</h2>
          </div>
          <span className="revision-chip">rev {result.plan_revision}</span>
        </div>

        <dl className="receipt-stats">
          <div><dt>Applied regions</dt><dd>{result.applied_region_count}</dd></div>
          <div><dt>Redaction passes</dt><dd>{result.redaction_passes}</dd></div>
          <div><dt>Manual additions</dt><dd>{result.manual_addition_count}</dd></div>
          <div><dt>Human overrides</dt><dd>{result.automatic_removal_count}</dd></div>
          <div><dt>Remediation detections</dt><dd>{result.remediation_detections.length}</dd></div>
          <div><dt>Remaining detections</dt><dd>{remainingCount}</dd></div>
        </dl>

        {remainingCount > 0 && (
          <section className="remaining-detections" aria-labelledby="remaining-heading">
            <h3 id="remaining-heading">Remaining geometry</h3>
            <ul>
              {result.remaining_detections.map((detection, index) => (
                <li key={`${detection.detection_type}-${detection.bbox.x1}-${detection.bbox.y1}-${index}`}>
                  <span>{detectionLabels[detection.detection_type]}</span>
                  <small>
                    {detection.bbox.x1}, {detection.bbox.y1} → {detection.bbox.x2},{" "}
                    {detection.bbox.y2}
                  </small>
                </li>
              ))}
            </ul>
            <button type="button" disabled={busyLabel !== null} onClick={onAddRemaining}>
              Add all as manual regions
            </button>
          </section>
        )}

        <button className="new-session-button" type="button" disabled={busyLabel !== null} onClick={onStartNew}>
          Start a new private session
        </button>
      </aside>
    </main>
  );
}
