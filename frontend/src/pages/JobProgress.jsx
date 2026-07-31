import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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

export default function JobProgress() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [connectionError, setConnectionError] = useState(null);
  const startedRef = useRef(false);

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
          <p className="muted">Loading job…</p>
        )}
      </div>
    );
  }

  const currentIndex = STAGES.findIndex(([key]) => key === job.current_stage);

  return (
    <div className="app-shell">
      <div className="stack">
        <div>
          <p className="eyebrow">Job {jobId.slice(0, 8)}</p>
          <h1>Generating your teaching package</h1>
          <p className="subtitle">This runs the 10-stage pipeline end to end — usually a few minutes.</p>
        </div>

        <div className="card stack">
          <div>
            <div className="row-between" style={{ marginBottom: "var(--space-2)" }}>
              <span className="mono muted" style={{ fontSize: "var(--text-sm)" }}>
                {job.progress_pct}%
              </span>
              <StatusBadge status={job.status} />
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${job.progress_pct}%` }} />
            </div>
          </div>

          <div className="stage-list">
            {STAGES.map(([key, label], i) => {
              const state = job.status === "failed" && key === job.current_stage
                ? "failed"
                : i < currentIndex || job.status === "completed"
                  ? "done"
                  : i === currentIndex
                    ? "active"
                    : "pending";
              return (
                <div key={key} className={`stage-item ${state}`}>
                  <span className="stage-dot" style={state === "failed" ? { background: "var(--color-error)" } : undefined} />
                  <span>{label}</span>
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
