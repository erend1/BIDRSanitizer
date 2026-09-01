import {
  useId,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
} from "react";

import type { ImageSettings } from "../api-types";

const acceptedTypes = new Set(["image/png", "image/jpeg", "application/pdf"]);

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface UploadWorkspaceProps {
  connected: boolean;
  connecting: boolean;
  selectedFile: File | null;
  uploadedSession: boolean;
  busyLabel: string | null;
  settings: ImageSettings;
  onConnect: (token: string) => Promise<void>;
  onFileSelected: (file: File) => void;
  onInvalidFile: () => void;
  onSettingsChange: (settings: ImageSettings) => void;
  onStartAnalysis: () => void;
}

export function UploadWorkspace({
  connected,
  connecting,
  selectedFile,
  uploadedSession,
  busyLabel,
  settings,
  onConnect,
  onFileSelected,
  onInvalidFile,
  onSettingsChange,
  onStartAnalysis,
}: UploadWorkspaceProps) {
  const fileInputId = useId();
  const marginInputId = useId();
  const passesInputId = useId();
  const tokenInputId = useId();
  const [token, setToken] = useState("");
  const [dragActive, setDragActive] = useState(false);

  function acceptFile(file: File | undefined) {
    if (file === undefined) {
      return;
    }

    const isPdfByExtension =
      file.type === "" && file.name.toLowerCase().endsWith(".pdf");
    if (!acceptedTypes.has(file.type) && !isPdfByExtension) {
      onInvalidFile();
      return;
    }

    onFileSelected(file);
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    acceptFile(event.currentTarget.files?.[0]);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    acceptFile(event.dataTransfer.files[0]);
  }

  async function handleConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const suppliedToken = token.trim();
    if (suppliedToken.length === 0) {
      return;
    }

    await onConnect(suppliedToken);
    setToken("");
  }

  const fileDescription =
    selectedFile === null
      ? null
      : `${
          selectedFile.type === "image/png"
            ? "PNG"
            : selectedFile.type === "image/jpeg"
            ? "JPEG"
            : "PDF"
        } · ${formatBytes(selectedFile.size)}`;

  return (
    <main id="main" className="welcome-layout">
      <section className="welcome-copy" aria-labelledby="welcome-heading">
        <p className="eyebrow">Private review workspace</p>
        <h1 id="welcome-heading">
          Redact with confidence.
          <em> Keep control.</em>
        </h1>
        <p className="lede">
          Review every proposed privacy region before BIDR permanently removes
          the underlying pixels and verifies the exported image.
        </p>

        <div className="privacy-principles" aria-label="Privacy principles">
          <span>Runs on this device</span>
          <span>No cloud inference</span>
          <span>Destructive redaction</span>
        </div>
      </section>

      <section className="upload-card" aria-labelledby="upload-heading">
        <div className="card-heading">
          <div>
            <p className="step-label">Step 01</p>
            <h2 id="upload-heading">
              {uploadedSession ? "Document received" : "Choose a document"}
            </h2>
          </div>
          <span className="format-chip">PNG · JPEG · PDF</span>
        </div>

        {uploadedSession ? (
          <div className="uploaded-state">
            <span aria-hidden="true">✓</span>
            <strong>Private session created</strong>
            <p>The source is ready. Retry local analysis without uploading it again.</p>
          </div>
        ) : (
          <label
            className={`drop-zone${dragActive ? " is-dragging" : ""}`}
            htmlFor={fileInputId}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
          >
            <input
              id={fileInputId}
              type="file"
              accept="image/png,image/jpeg,application/pdf,.pdf"
              onChange={handleFileInput}
            />
            <span className="upload-symbol" aria-hidden="true">↑</span>
            <strong>{fileDescription ?? "Drop an image or PDF here"}</strong>
            <span>
              {fileDescription === null
                ? "or select one from this computer"
                : "Selected locally; its filename will not be uploaded"}
            </span>
            <span className="select-button">
              {fileDescription === null ? "Select document" : "Choose another"}
            </span>
          </label>
        )}

        <fieldset className="analysis-settings" disabled={busyLabel !== null}>
          <legend>Export safety settings</legend>
          <label htmlFor={marginInputId}>
            <span>
              Redaction margin
              <small>Extra pixels around each retained region</small>
            </span>
            <span className="number-control">
              <input
                id={marginInputId}
                type="number"
                min="0"
                step="1"
                inputMode="numeric"
                value={settings.redaction_margin}
                onChange={(event) =>
                  onSettingsChange({
                    ...settings,
                    redaction_margin: Math.max(0, event.currentTarget.valueAsNumber || 0),
                  })
                }
              />
              px
            </span>
          </label>
          <label htmlFor={passesInputId}>
            <span>
              Verification passes
              <small>Maximum redaction and re-scan attempts</small>
            </span>
            <span className="number-control">
              <input
                id={passesInputId}
                type="number"
                min="1"
                step="1"
                inputMode="numeric"
                value={settings.max_redaction_passes}
                onChange={(event) =>
                  onSettingsChange({
                    ...settings,
                    max_redaction_passes: Math.max(
                      1,
                      event.currentTarget.valueAsNumber || 1,
                    ),
                  })
                }
              />
            </span>
          </label>
        </fieldset>

        {!connected && (
          <form className="connection-panel" onSubmit={handleConnection}>
            <div>
              <span className="connection-icon" aria-hidden="true">⌁</span>
              <span>
                <strong>Load the local launch token</strong>
                <small>The launch token stays in memory and is never saved.</small>
              </span>
            </div>
            <label htmlFor={tokenInputId} className="sr-only">
              Per-launch API token
            </label>
            <input
              id={tokenInputId}
              type="password"
              value={token}
              minLength={32}
              autoComplete="off"
              spellCheck={false}
              placeholder="Per-launch token"
              onChange={(event) => setToken(event.currentTarget.value)}
            />
            <button type="submit" disabled={connecting || token.trim().length < 32}>
              {connecting ? "Checking…" : "Use token"}
            </button>
          </form>
        )}

        <div className="card-footer">
          <p>
            <span className="lock-dot" aria-hidden="true" />
            Your original is a sensitive preview. It is never the sanitized result.
          </p>
          <button
            className="primary-button"
            type="button"
            disabled={
              !connected ||
              (!uploadedSession && selectedFile === null) ||
              busyLabel !== null
            }
            onClick={onStartAnalysis}
          >
            {busyLabel ?? (uploadedSession ? "Retry analysis" : "Begin analysis")}
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </section>

      <aside className="assurance-card" aria-label="Verification scope">
        <span className="assurance-index">A / 01</span>
        <h2>Detection proposes. Deterministic code redacts.</h2>
        <p>
          Verification scans the newly exported pixels. A clear scan reports what
          the configured detectors found; it is not a legal guarantee.
        </p>
      </aside>
    </main>
  );
}
