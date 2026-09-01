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
  ReviewPage,
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

interface PageDraft {
  actions: Record<string, ReviewAction>;
  geometries: Record<string, BoundingBox>;
  manualDrafts: ReviewRegion[];
  selectedRegionId: string | null;
}

const defaultSettings: ImageSettings = {
  redaction_margin: 5,
  max_redaction_passes: 3,
};

function createPageDraft(plan: ReviewPlan): PageDraft {
  return {
    actions: Object.fromEntries(
      plan.regions.map((region) => [region.region_id, region.action]),
    ),
    geometries: Object.fromEntries(
      plan.regions.map((region) => [region.region_id, region.bbox]),
    ),
    manualDrafts: [],
    selectedRegionId: plan.regions[0]?.region_id ?? null,
  };
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
    geometry_modified: false,
  };
}

function boxesEqual(first: BoundingBox, second: BoundingBox): boolean {
  return (
    first.x1 === second.x1 &&
    first.y1 === second.y1 &&
    first.x2 === second.x2 &&
    first.y2 === second.y2
  );
}

function pageHasPendingChanges(page: ReviewPage, draft: PageDraft): boolean {
  if (page.plan === null) {
    return false;
  }
  return (
    draft.manualDrafts.length > 0 ||
    page.plan.regions.some(
      (region) =>
        (draft.actions[region.region_id] ?? region.action) !== region.action ||
        !boxesEqual(
          draft.geometries[region.region_id] ?? region.bbox,
          region.bbox,
        ),
    )
  );
}

function AppHeader({ step, connected }: { step: WorkflowStep; connected: boolean }) {
  const stepNumber = step === "upload" ? 1 : step === "review" ? 2 : 3;
  return (
    <header className="topbar">
      <a className="brand" href="#main" aria-label="BIDR Sanitizer workspace">
        <span className="brand-mark" aria-hidden="true">B</span>
        <span><strong>BIDR</strong><small>Sanitizer</small></span>
      </a>
      <nav className="workflow-nav" aria-label="Review workflow">
        {(["Upload", "Review", "Export"] as const).map((label, index) => (
          <span className="workflow-fragment" key={label}>
            {index > 0 && <span className="workflow-line" aria-hidden="true" />}
            <span
              className={`workflow-step${stepNumber === index + 1 ? " is-current" : ""}${
                stepNumber > index + 1 ? " is-complete" : ""
              }`}
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
  const [activePageNumber, setActivePageNumber] = useState(1);
  const [pageDrafts, setPageDrafts] = useState<Record<number, PageDraft>>({});
  const [sourceBlob, setSourceBlob] = useState<Blob | null>(null);
  const [exportBlob, setExportBlob] = useState<Blob | null>(null);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const client = useMemo(
    () => (launchToken.length > 0 ? new ReviewApiClient(launchToken) : null),
    [launchToken],
  );
  const sourceUrl = useObjectUrl(sourceBlob);
  const exportUrl = useObjectUrl(exportBlob);
  const activePage = session?.pages.find(
    (page) => page.page_number === activePageNumber,
  ) ?? null;
  const plan = activePage?.plan ?? null;
  const pageDraft = activePage === null || plan === null
    ? null
    : pageDrafts[activePageNumber] ?? createPageDraft(plan);

  const effectiveRegions = useMemo(() => {
    if (plan === null || pageDraft === null) {
      return [];
    }
    const persisted = plan.regions.map((region) => {
      const bbox = pageDraft.geometries[region.region_id] ?? region.bbox;
      return {
        ...region,
        bbox,
        action: pageDraft.actions[region.region_id] ?? region.action,
        geometry_modified:
          region.geometry_modified ||
          (region.provenance === "automatic" && !boxesEqual(bbox, region.bbox)),
      };
    });
    return [...persisted, ...pageDraft.manualDrafts];
  }, [pageDraft, plan]);

  const hasPendingChanges =
    activePage !== null && pageDraft !== null
      ? pageHasPendingChanges(activePage, pageDraft)
      : false;
  const hasAnyPendingChanges = session?.pages.some((page) => {
    if (page.plan === null) return false;
    return pageHasPendingChanges(
      page,
      pageDrafts[page.page_number] ?? createPageDraft(page.plan),
    );
  }) ?? false;

  useEffect(() => {
    if (client === null || session === null) return;
    const sessionId = session.session_id;
    const handleBeforeUnload = () => {
      void client.deleteSession(sessionId, true).catch(() => undefined);
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [client, session]);

  function initializeDrafts(nextSession: ReviewSession): Record<number, PageDraft> {
    return Object.fromEntries(
      nextSession.pages
        .filter((page): page is ReviewPage & { plan: ReviewPlan } => page.plan !== null)
        .map((page) => [page.page_number, createPageDraft(page.plan)]),
    );
  }

  async function loadPagePreview(sessionId: string, pageNumber: number) {
    if (client === null) return;
    setSourceBlob(null);
    setBusyLabel(`Loading page ${pageNumber} preview…`);
    setSourceBlob(await client.getPageSource(sessionId, pageNumber));
  }

  function clearLocalSession() {
    setStep("upload");
    setSelectedFile(null);
    setSession(null);
    setActivePageNumber(1);
    setPageDrafts({});
    setSourceBlob(null);
    setExportBlob(null);
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
        setPageDrafts(initializeDrafts(latest));
        setErrorMessage(
          "The plan changed before this operation completed. All page revisions were reloaded.",
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
      const nextClient = new ReviewApiClient(token);
      await nextClient.checkAuthentication();
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
          setErrorMessage("Select a PNG, JPEG, or PDF document first.");
          return;
        }
        setBusyLabel("Creating private session…");
        currentSession = await client.createSession(selectedFile);
        setSession(currentSession);
        setSelectedFile(null);
      }

      setBusyLabel(
        currentSession.media_type === "application/pdf"
          ? `Analyzing ${currentSession.page_count} PDF pages locally…`
          : "Analyzing locally…",
      );
      const analyzed = await client.analyzeSession(currentSession.session_id, settings);
      if (analyzed.pages.some((page) => page.plan === null)) {
        throw new Error("The analysis response did not include every page plan.");
      }
      setSession(analyzed);
      setPageDrafts(initializeDrafts(analyzed));
      setActivePageNumber(1);
      await loadPagePreview(analyzed.session_id, 1);
      setStep("review");
    } catch (error) {
      if (error instanceof ReviewApiError && error.status === 401 && session === null) {
        setLaunchToken("");
      }
      await recoverFromWorkflowError(error);
    } finally {
      setBusyLabel(null);
    }
  }

  function updateActiveDraft(update: (draft: PageDraft) => PageDraft) {
    if (pageDraft === null) return;
    setPageDrafts((current) => ({
      ...current,
      [activePageNumber]: update(current[activePageNumber] ?? pageDraft),
    }));
    setExportBlob(null);
  }

  function handleActionChange(regionId: string, action: ReviewAction) {
    updateActiveDraft((draft) => {
      if (regionId.startsWith("draft-") && action === "remove") {
        return {
          ...draft,
          manualDrafts: draft.manualDrafts.filter(
            (region) => region.region_id !== regionId,
          ),
          selectedRegionId: null,
        };
      }
      return { ...draft, actions: { ...draft.actions, [regionId]: action } };
    });
  }

  function handleRegionGeometryChange(regionId: string, bbox: BoundingBox) {
    updateActiveDraft((draft) => {
      if (regionId.startsWith("draft-")) {
        return {
          ...draft,
          manualDrafts: draft.manualDrafts.map((region) =>
            region.region_id === regionId ? { ...region, bbox } : region,
          ),
        };
      }
      return {
        ...draft,
        geometries: { ...draft.geometries, [regionId]: bbox },
      };
    });
  }

  function handleManualRegion(bbox: BoundingBox, detectionType: DetectionType | null) {
    const region = createDraftRegion(bbox, detectionType);
    updateActiveDraft((draft) => ({
      ...draft,
      manualDrafts: [...draft.manualDrafts, region],
      selectedRegionId: region.region_id,
    }));
  }

  async function commitPages(pageNumbers: number[]): Promise<ReviewSession> {
    if (client === null || session === null) {
      throw new Error("A saved review session is required.");
    }
    let revisedSession = session;
    const committed = new Set<number>();
    for (const pageNumber of pageNumbers) {
      const page = revisedSession.pages.find((item) => item.page_number === pageNumber);
      if (page?.plan === null || page?.plan === undefined) {
        throw new Error("A saved page plan is required.");
      }
      const draft = pageDrafts[pageNumber] ?? createPageDraft(page.plan);
      if (!pageHasPendingChanges(page, draft)) continue;

      revisedSession = await client.revisePlan(revisedSession.session_id, {
        page_number: pageNumber,
        expected_revision: page.plan.revision,
        decisions: page.plan.regions
          .filter(
            (region) =>
              (draft.actions[region.region_id] ?? region.action) !== region.action,
          )
          .map((region) => ({
            region_id: region.region_id,
            action: draft.actions[region.region_id] ?? region.action,
          })),
        geometry_updates: page.plan.regions
          .filter(
            (region) =>
              !boxesEqual(
                draft.geometries[region.region_id] ?? region.bbox,
                region.bbox,
              ),
          )
          .map((region) => ({
            region_id: region.region_id,
            bbox: draft.geometries[region.region_id] ?? region.bbox,
          })),
        manual_regions: draft.manualDrafts.map((region) => ({
          bbox: region.bbox,
          detection_type: region.detection_type,
        })),
      });
      committed.add(pageNumber);
    }

    setSession(revisedSession);
    setPageDrafts((current) => {
      const next = { ...current };
      for (const pageNumber of committed) {
        const page = revisedSession.pages.find((item) => item.page_number === pageNumber);
        if (page?.plan !== null && page?.plan !== undefined) {
          next[pageNumber] = createPageDraft(page.plan);
        }
      }
      return next;
    });
    setExportBlob(null);
    return revisedSession;
  }

  async function handleSave() {
    setErrorMessage(null);
    setBusyLabel(`Saving page ${activePageNumber} review…`);
    try {
      await commitPages([activePageNumber]);
    } catch (error) {
      await recoverFromWorkflowError(error);
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleExport() {
    if (client === null || session === null) return;
    setErrorMessage(null);
    setBusyLabel(hasAnyPendingChanges ? "Saving all page reviews…" : "Preparing export…");
    try {
      const ready = await commitPages(session.pages.map((page) => page.page_number));
      const revisions = ready.pages.map((page) => {
        if (page.plan === null) throw new Error("Every page requires a saved plan.");
        return { page_number: page.page_number, revision: page.plan.revision };
      });
      setBusyLabel(
        ready.media_type === "application/pdf"
          ? "Redacting, verifying, and rebuilding PDF…"
          : "Redacting and verifying…",
      );
      const completed = await client.exportSession(ready.session_id, revisions);
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

  async function handlePageChange(pageNumber: number) {
    if (client === null || session === null || pageNumber === activePageNumber) return;
    setErrorMessage(null);
    setActivePageNumber(pageNumber);
    try {
      await loadPagePreview(session.session_id, pageNumber);
    } catch (error) {
      setErrorMessage(readableClientError(error));
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleDownload() {
    if (client === null || session?.export === null || session === null) return;
    setBusyLabel("Preparing download…");
    setErrorMessage(null);
    try {
      const blob = exportBlob ?? (await client.getExport(session.session_id)).blob;
      if (exportBlob === null) setExportBlob(blob);
      const temporaryUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = temporaryUrl;
      anchor.download = `BIDR_REVIEW_RESULT.${
        session.media_type === "image/png"
          ? "png"
          : session.media_type === "image/jpeg"
          ? "jpg"
          : "pdf"
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

  async function handleAddRemaining() {
    if (session?.export === null || session?.export === undefined) return;
    const firstPage = session.export.remaining_detections[0]?.page_number ?? 1;
    setPageDrafts((current) => {
      const next = { ...current };
      for (const detection of session.export!.remaining_detections) {
        const page = session.pages.find(
          (candidate) => candidate.page_number === detection.page_number,
        );
        if (page?.plan === null || page?.plan === undefined) continue;
        const draft = next[detection.page_number] ?? createPageDraft(page.plan);
        const addition = createDraftRegion(detection.bbox, detection.detection_type);
        next[detection.page_number] = {
          ...draft,
          manualDrafts: [...draft.manualDrafts, addition],
          selectedRegionId: addition.region_id,
        };
      }
      return next;
    });
    setExportBlob(null);
    setStep("review");
    await handlePageChange(firstPage);
  }

  const canShowReview = plan !== null && pageDraft !== null && sourceUrl !== null;
  const canShowExport = session?.export !== null && session?.export !== undefined;
  const reviewPreviewPending =
    step === "review" && plan !== null && sourceUrl === null;

  return (
    <div className="app-shell" aria-busy={busyLabel !== null}>
      <AppHeader step={step} connected={client !== null} />
      {errorMessage !== null && (
        <div className="global-alert" role="alert">
          <span aria-hidden="true">!</span><p>{errorMessage}</p>
          <button type="button" aria-label="Dismiss message" onClick={() => setErrorMessage(null)}>×</button>
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
          onFileSelected={(file) => { setErrorMessage(null); setSelectedFile(file); }}
          onInvalidFile={() =>
            setErrorMessage("Choose a PNG, JPEG, or PDF document.")
          }
          onSettingsChange={setSettings}
          onStartAnalysis={() => void handleStartAnalysis()}
        />
      )}

      {step === "review" && canShowReview && activePage !== null && pageDraft !== null && (
        <ReviewWorkspace
          imageUrl={sourceUrl}
          plan={plan}
          regions={effectiveRegions}
          selectedRegionId={pageDraft.selectedRegionId}
          hasPendingChanges={hasPendingChanges}
          hasOtherPageChanges={hasAnyPendingChanges && !hasPendingChanges}
          busyLabel={busyLabel}
          pageNumber={activePageNumber}
          pageCount={session?.page_count ?? 1}
          onPageChange={(pageNumber) => void handlePageChange(pageNumber)}
          onSelectRegion={(regionId) =>
            updateActiveDraft((draft) => ({ ...draft, selectedRegionId: regionId }))
          }
          onActionChange={handleActionChange}
          onRegionGeometryChange={handleRegionGeometryChange}
          onManualRegion={handleManualRegion}
          onSave={() => void handleSave()}
          onExport={() => void handleExport()}
          onStartOver={() => void deleteCurrentSession()}
        />
      )}

      {reviewPreviewPending && (
        <main id="main" className="recovery-panel" role="status">
          <h1>Preparing the private page preview…</h1>
          <p>The source remains in memory while the authenticated blob view is created.</p>
        </main>
      )}

      {step === "export" && canShowExport && session?.export !== null && session !== null && (
        <ExportWorkspace
          result={session.export}
          exportUrl={exportUrl}
          mediaType={session.media_type}
          imageWidth={session.image_width}
          imageHeight={session.image_height}
          pageCount={session.page_count}
          busyLabel={busyLabel}
          onDownload={() => void handleDownload()}
          onContinueReview={() => setStep("review")}
          onAddRemaining={() => void handleAddRemaining()}
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
