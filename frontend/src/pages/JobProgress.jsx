import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Check, X } from "lucide-react";
import { getJob, streamJobProgress } from "../api.js";

const STAGES = [
  ["document_intelligence", "Reading document"],
  ["classification", "Classifying content"],
  ["knowledge_extraction", "Extracting knowledge"],
  ["teaching_planner", "Planning periods"],
  ["content_generation", "Writing lesson content"],
  ["activity_generation", "Designing activities"],
  ["assessment_generation", "Building assessments"],
  ["gap_analysis", "Analyzing learning gaps"],
  ["validation", "Validating output"],
  ["publishing", "Publishing package"],
];

function useElapsed(startTime) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startTime) return;
    const start = new Date(startTime).getTime();
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startTime]);
  return elapsed;
}

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function JobProgress() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [connectionError, setConnectionError] = useState(null);
  const startedRef = useRef(false);
  const elapsed = useElapsed(job?.created_at);

  useEffect(() => {
    const controller = new AbortController();

    async function bootstrap() {
      try {
        const initial = await getJob(jobId);
        setJob(initial);
        if (initial.status === "completed" && initial.tkp_version_id) {
          navigate(`/tkp/${initial.tkp_version_id}`);
          return;
        }
        if (initial.status === "completed" || initial.status === "failed") return;

        await streamJobProgress(
          jobId,
          (event) => {
            setJob(event);
            if (event.status === "completed" && event.tkp_version_id) {
              navigate(`/tkp/${event.tkp_version_id}`);
            }
          },
          { signal: controller.signal }
        );
      } catch (err) {
        if (err.name !== "AbortError") {
          setConnectionError(err.detail || err.message || "Lost connection to the progress stream");
        }
      }
    }

    if (!startedRef.current) {
      startedRef.current = true;
      bootstrap();
    }
    return () => controller.abort();
  }, [jobId, navigate]);

  if (!job) {
    return (
      <div className="app-shell">
        {connectionError ? (
          <div className="error-banner">{connectionError}</div>
        ) : (
          <div className="stack">
            <div className="skeleton" style={{ height: 32, width: "60%" }} />
            <div className="skeleton" style={{ height: 120 }} />
          </div>
        )}
      </div>
    );
  }

  const currentIndex = STAGES.findIndex(([key]) => key === job.current_stage);

  return (
    <div className="app-shell fade-in">
      <div className="stack" style={{ gap: "var(--space-6)" }}>
        <div className="stack-sm">
          <span className="eyebrow">
            <span className="live-dot" /> Live pipeline run
          </span>
          <h1 style={{ fontSize: "var(--text-2xl)" }}>Generating your teaching package</h1>
          <p className="subtitle">Watching the 10-stage pipeline run, straight from the orchestrator.</p>
        </div>

        <div className="card-bordered stack" style={{ gap: "var(--space-5)" }}>
          <div className="row-between" style={{ flexWrap: "wrap", gap: "var(--space-4)" }}>
            <div className="row" style={{ gap: "var(--space-5)" }}>
              <div className="stat-tile">
                <div className="stat-value">{job.progress_pct}%</div>
                <div className="stat-label">Complete</div>
              </div>
              <div className="stat-tile">
                <div className="stat-value mono">{formatElapsed(elapsed)}</div>
                <div className="stat-label">Elapsed</div>
              </div>
            </div>
            <StatusBadge status={job.status} />
          </div>

          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${job.progress_pct}%` }} />
          </div>

          <div className="stepper">
            {STAGES.map(([key, label], i) => {
              const state =
                job.status === "failed" && key === job.current_stage
                  ? "failed"
                  : i < currentIndex || job.status === "completed"
                    ? "done"
                    : i === currentIndex
                      ? "active"
                      : "pending";
              return (
                <div key={key} className={`step ${state}`}>
                  <div className="step-line" />
                  <div className="step-marker">
                    {state === "done" ? (
                      <Check size={13} strokeWidth={3} />
                    ) : state === "failed" ? (
                      <X size={13} strokeWidth={3} />
                    ) : (
                      i + 1
                    )}
                  </div>
                  <div>
                    <div className="step-label">{label}</div>
                    {state === "active" && <div className="step-sub">In progress…</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {job.status === "failed" && (
          <div className="error-banner">
            Pipeline failed during <strong>{job.current_stage}</strong>: {job.error}
          </div>
        )}
        {connectionError && <div className="error-banner">{connectionError}</div>}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const variants = {
    pending: ["badge-neutral", "Queued"],
    running: ["badge-warning", "Running"],
    completed: ["badge-success", "Completed"],
    failed: ["badge-error", "Failed"],
  };
  const [cls, label] = variants[status] || variants.pending;
  return <span className={`badge ${cls}`}>{label}</span>;
}
