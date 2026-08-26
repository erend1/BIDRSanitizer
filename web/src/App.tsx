import { useEffect, useMemo, useState } from "react";

import {
  checkReviewApiHealth,
  readableClientError,
  ReviewApiClient,
  ReviewApiError,
} from "./api-client";
import type {
  BoundingBox,
  DetectionType,
  ImageSettings,
  ReviewAction,
  ReviewPlan,
  ReviewRegion,
  ReviewSession,
} from "./api-types";
import { ExportWorkspace } from "./components/ExportWorkspace";
import { ReviewWorkspace } from "./components/ReviewWorkspace";
import { UploadWorkspace } from "./components/UploadWorkspace";
import { readLaunchToken } from "./runtime";
import { useObjectUrl } from "./use-object-url";

type WorkflowStep = "upload" | "review" | "export";

const defaultSettings: ImageSettings = {
  redaction_margin: 5,
  max_redaction_passes: 3,
};

function initializeActions(plan: ReviewPlan): Record<string, ReviewAction> {
  return Object.fromEntries(
    plan.regions.map((region) => [region.region_id, region.action]),
  );
}

function createDraftRegion(
  bbox: BoundingBox,
  detectionType: DetectionType | null,
): ReviewRegion {
  return {
    region_id: `draft-${crypto.randomUUID()}`,
    bbox,
    provenance: "manual",
    action: "retain",
    detection_type: detectionType,
    confidence: null,
  };
}

function AppHeader({
  step,
  connected,
}: {
  step: WorkflowStep;
  connected: boolean;
}) {
  const stepNumber = step === "upload" ? 1 : step === "review" ? 2 : 3;

  return (
    <header className="topbar">
      <a className="brand" href="#main" aria-label="BIDR Sanitizer workspace">
        <span className="brand-mark" aria-hidden="true">B</span>
        <span>
          <strong>BIDR</strong>
          <small>Sanitizer</small>
        </span>
      </a>

      <nav className="workflow-nav" aria-label="Review workflow">
        {(["Upload", "Review", "Export"] as const).map((label, index) => (
          <span className="workflow-fragment" key={label}>
            {index > 0 && <span className="workflow-line" aria-hidden="true" />}
            <span
              className={`workflow-step${
                stepNumber === index + 1 ? " is-current" : ""
              }${stepNumber > index + 1 ? " is-complete" : ""}`}
              aria-current={stepNumber === index + 1 ? "step" : undefined}
            >
              <b>{String(index + 1).padStart(2, "0")}</b> {label}
            </span>
          </span>
        ))}
      </nav>

      <div className={`engine-status${connected ? " is-connected" : ""}`} role="status">
        <span aria-hidden="true" />
        {connected ? "Launch token in memory" : "Launch token required"}
      </div>
    </header>
  );
}

export function App() {
  const [launchToken, setLaunchToken] = useState(readLaunchToken);
  const [connecting, setConnecting] = useState(false);
  const [step, setStep] = useState<WorkflowStep>("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<ImageSettings>(defaultSettings);
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [sourceBlob, setSourceBlob] = useState<Blob | null>(null);
  const [exportBlob, setExportBlob] = useState<Blob | null>(null);
  const [actions, setActions] = useState<Record<string, ReviewAction>>({});
  const [manualDrafts, setManualDrafts] = useState<ReviewRegion[]>([]);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const client = useMemo(
    () => (launchToken.length > 0 ? new ReviewApiClient(launchToken) : null),
    [launchToken],
  );
  const sourceUrl = useObjectUrl(sourceBlob);
  const exportUrl = useObjectUrl(exportBlob);
  const plan = session?.plan ?? null;

  const effectiveRegions = useMemo(() => {
    if (plan === null) {
      return [];
    }

    const persisted = plan.regions.map((region) => ({
      ...region,
      action: actions[region.region_id] ?? region.action,
    }));
    return [...persisted, ...manualDrafts];
  }, [actions, manualDrafts, plan]);

  const hasPendingChanges = useMemo(() => {
    if (plan === null) {
      return false;
    }

    return (
      manualDrafts.length > 0 ||
      plan.regions.some(
        (region) => (actions[region.region_id] ?? region.action) !== region.action,
      )
    );
  }, [actions, manualDrafts, plan]);

  useEffect(() => {
    if (client === null || session === null) {
      return;
    }

    const sessionId = session.session_id;
    const handleBeforeUnload = () => {
      void client.deleteSession(sessionId, true).catch(() => undefined);
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [client, session]);

  function loadPlan(nextPlan: ReviewPlan) {
    setActions(initializeActions(nextPlan));
    setManualDrafts([]);
    setSelectedRegionId(nextPlan.regions[0]?.region_id ?? null);
  }

  function clearLocalSession() {
    setStep("upload");
    setSelectedFile(null);
    setSession(null);
    setSourceBlob(null);
    setExportBlob(null);
    setActions({});
    setManualDrafts([]);
    setSelectedRegionId(null);
    setSettings(defaultSettings);
  }

  async function recoverFromWorkflowError(error: unknown) {
    if (
      error instanceof ReviewApiError &&
      error.status === 409 &&
      client !== null &&
      session !== null
    ) {
      try {
        const latest = await client.getSession(session.session_id);
        setSession(latest);
        if (latest.plan !== null) {
          loadPlan(latest.plan);
        }
        setErrorMessage(
          "The plan changed before this operation completed. The latest revision has been reloaded.",
        );
        return;
      } catch (reloadError) {
        setErrorMessage(readableClientError(reloadError));
        return;
      }
    }

    setErrorMessage(readableClientError(error));
  }

  async function handleConnect(token: string) {
    setConnecting(true);
    setErrorMessage(null);
    try {
      const health = await checkReviewApiHealth();
      if (health.status !== "ok" || health.api_version !== "v1") {
        throw new Error("Unexpected local API response.");
      }
      new ReviewApiClient(token);
      setLaunchToken(token);
    } catch (error) {
      setErrorMessage(readableClientError(error));
    } finally {
      setConnecting(false);
    }
  }

  async function handleStartAnalysis() {
    if (client === null) {
      setErrorMessage("Connect the local review engine before analysis.");
      return;
    }

    setErrorMessage(null);
    let currentSession = session;
    try {
      if (currentSession === null) {
        if (selectedFile === null) {
          setErrorMessage("Select a PNG or JPEG image first.");
          return;
        }

        setBusyLabel("Creating private session…");
        currentSession = await client.createSession(selectedFile);
        setSession(currentSession);
        setSelectedFile(null);
      }

      if (sourceBlob === null) {
        setBusyLabel("Loading private preview…");
        setSourceBlob(await client.getSource(currentSession.session_id));
      }

      setBusyLabel("Analyzing locally…");
      const analyzed = await client.analyzeSession(
        currentSession.session_id,
        settings,
      );
      if (analyzed.plan === null) {
        throw new Error("The analysis response did not include a review plan.");
      }

      setSession(analyzed);
      loadPlan(analyzed.plan);
      setStep("review");
    } catch (error) {
      if (
        error instanceof ReviewApiError &&
        error.status === 401 &&
        session === null
      ) {
        setLaunchToken("");
      }
      await recoverFromWorkflowError(error);
    } finally {
      setBusyLabel(null);
    }
  }

  function handleActionChange(regionId: string, action: ReviewAction) {
    if (regionId.startsWith("draft-")) {
      if (action === "remove") {
        setManualDrafts((regions) =>
          regions.filter((region) => region.region_id !== regionId),
        );
        setSelectedRegionId(null);
      }
      return;
    }

    setActions((current) => ({ ...current, [regionId]: action }));
  }

  function handleManualRegion(
    bbox: BoundingBox,
    detectionType: DetectionType | null,
  ) {
    const region = createDraftRegion(bbox, detectionType);
    setManualDrafts((current) => [...current, region]);
    setSelectedRegionId(region.region_id);
    setExportBlob(null);
  }

  async function commitDraft(): Promise<ReviewSession> {
    if (client === null || session === null || plan === null) {
      throw new Error("A saved review plan is required.");
    }

    if (!hasPendingChanges) {
      return session;
    }

    const revised = await client.revisePlan(session.session_id, {
      expected_revision: plan.revision,
      decisions: plan.regions
        .filter(
          (region) =>
            (actions[region.region_id] ?? region.action) !== region.action,
        )
        .map((region) => ({
          region_id: region.region_id,
          action: actions[region.region_id] ?? region.action,
        })),
      manual_regions: manualDrafts.map((region) => ({
        bbox: region.bbox,
        detection_type: region.detection_type,
      })),
    });

    if (revised.plan === null) {
      throw new Error("The revised session did not include a review plan.");
    }

    setSession(revised);
    loadPlan(revised.plan);
    setExportBlob(null);
    return revised;
  }

  async function handleSave() {
    setErrorMessage(null);
    setBusyLabel("Saving review…");
    try {
      await commitDraft();
    } catch (error) {
      await recoverFromWorkflowError(error);
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleExport() {
    if (client === null || session === null) {
      setErrorMessage("The local review session is unavailable.");
      return;
    }

    setErrorMessage(null);
    setBusyLabel(hasPendingChanges ? "Saving review…" : "Preparing export…");
    try {
      const ready = await commitDraft();
      if (ready.plan === null) {
        throw new Error("A saved review plan is required for export.");
      }

      setBusyLabel("Redacting and verifying…");
      const completed = await client.exportSession(
        ready.session_id,
        ready.plan.revision,
      );
      if (completed.export === null) {
        throw new Error("The export response did not include verification state.");
      }

      setSession(completed);
      setStep("export");
      setBusyLabel("Loading reviewed output…");
      try {
        const downloaded = await client.getExport(completed.session_id);
        if (
          downloaded.status !== null &&
          downloaded.status !== completed.export.status
        ) {
          throw new Error("The export status header did not match the receipt.");
        }
        setExportBlob(downloaded.blob);
      } catch (downloadError) {
        setExportBlob(null);
        setErrorMessage(readableClientError(downloadError));
      }
    } catch (error) {
      await recoverFromWorkflowError(error);
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleDownload() {
    if (client === null || session === null || session.export === null) {
      return;
    }

    setBusyLabel("Preparing download…");
    setErrorMessage(null);
    try {
      const blob = exportBlob ?? (await client.getExport(session.session_id)).blob;
      if (exportBlob === null) {
        setExportBlob(blob);
      }

      const temporaryUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = temporaryUrl;
      anchor.download = `BIDR_REVIEW_RESULT.${
        session.media_type === "image/png" ? "png" : "jpg"
      }`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(temporaryUrl), 0);
    } catch (error) {
      setErrorMessage(readableClientError(error));
    } finally {
      setBusyLabel(null);
    }
  }

  async function deleteCurrentSession() {
    if (client === null || session === null) {
      clearLocalSession();
      return;
    }

    setBusyLabel("Removing private session…");
    setErrorMessage(null);
    try {
      await client.deleteSession(session.session_id);
      clearLocalSession();
    } catch (error) {
      if (error instanceof ReviewApiError && error.status === 404) {
        clearLocalSession();
      } else {
        setErrorMessage(
          `${readableClientError(error)} The session remains open so cleanup is not misrepresented.`,
        );
      }
    } finally {
      setBusyLabel(null);
    }
  }

  function handleAddRemaining() {
    if (session?.export === null || session?.export === undefined) {
      return;
    }

    const additions = session.export.remaining_detections.map((detection) =>
      createDraftRegion(detection.bbox, detection.detection_type),
    );
    setManualDrafts((current) => [...current, ...additions]);
    setSelectedRegionId(additions[0]?.region_id ?? null);
    setExportBlob(null);
    setStep("review");
  }

  const canShowReview = plan !== null && sourceUrl !== null;
  const canShowExport = session?.export !== null && session?.export !== undefined;
  const reviewPreviewPending =
    step === "review" && plan !== null && sourceBlob !== null && sourceUrl === null;

  return (
    <div className="app-shell" aria-busy={busyLabel !== null}>
      <AppHeader step={step} connected={client !== null} />

      {errorMessage !== null && (
        <div className="global-alert" role="alert">
          <span aria-hidden="true">!</span>
          <p>{errorMessage}</p>
          <button type="button" aria-label="Dismiss message" onClick={() => setErrorMessage(null)}>
            ×
          </button>
        </div>
      )}

      {step === "upload" && (
        <UploadWorkspace
          connected={client !== null}
          connecting={connecting}
          selectedFile={selectedFile}
          uploadedSession={session?.state === "uploaded"}
          busyLabel={busyLabel}
          settings={settings}
          onConnect={handleConnect}
          onFileSelected={(file) => {
            setErrorMessage(null);
            setSelectedFile(file);
          }}
          onInvalidFile={() =>
            setErrorMessage("Choose a PNG or JPEG image. Other formats are not accepted yet.")
          }
          onSettingsChange={setSettings}
          onStartAnalysis={() => void handleStartAnalysis()}
        />
      )}

      {step === "review" && canShowReview && (
        <ReviewWorkspace
          imageUrl={sourceUrl}
          plan={plan}
          regions={effectiveRegions}
          selectedRegionId={selectedRegionId}
          hasPendingChanges={hasPendingChanges}
          busyLabel={busyLabel}
          onSelectRegion={setSelectedRegionId}
          onActionChange={handleActionChange}
          onManualRegion={handleManualRegion}
          onSave={() => void handleSave()}
          onExport={() => void handleExport()}
          onStartOver={() => void deleteCurrentSession()}
        />
      )}

      {reviewPreviewPending && (
        <main id="main" className="recovery-panel" role="status">
          <h1>Preparing the private preview…</h1>
          <p>The source remains in memory while the authenticated blob view is created.</p>
        </main>
      )}

      {step === "export" && canShowExport && session !== null && session.export !== null && (
        <ExportWorkspace
          result={session.export}
          exportUrl={exportUrl}
          imageWidth={session.image_width}
          imageHeight={session.image_height}
          busyLabel={busyLabel}
          onDownload={() => void handleDownload()}
          onContinueReview={() => setStep("review")}
          onAddRemaining={handleAddRemaining}
          onStartNew={() => void deleteCurrentSession()}
        />
      )}

      {step !== "upload" &&
        ((step === "review" && !canShowReview && !reviewPreviewPending) ||
          (step === "export" && !canShowExport)) && (
          <main id="main" className="recovery-panel">
            <h1>The private preview is unavailable</h1>
            <p>Return to a new session rather than reviewing geometry without its source.</p>
            <button className="primary-button" type="button" onClick={() => void deleteCurrentSession()}>
              Start again
            </button>
          </main>
        )}

      <footer className="app-footer">
        <span>BIDR Sanitizer · pre-release</span>
        <span>Offline-first privacy tooling</span>
      </footer>
    </div>
  );
}
