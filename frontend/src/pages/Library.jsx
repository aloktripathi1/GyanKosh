import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, Library as LibraryIcon, Trash2 } from "lucide-react";
import { deleteJob, listJobs } from "../api.js";

const STATUS_VARIANTS = {
  pending: ["badge-neutral", "Queued"],
  running: ["badge-warning", "Running"],
  completed: ["badge-success", "Completed"],
  failed: ["badge-error", "Failed"],
};

function StatusBadge({ status }) {
  const [cls, label] = STATUS_VARIANTS[status] || STATUS_VARIANTS.pending;
  return <span className={`badge ${cls}`}>{label}</span>;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function rowHref(job) {
  if (job.tkp_version_id) return `/tkp/${job.tkp_version_id}`;
  return `/jobs/${job.id}`;
}

export default function Library() {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch((err) => setError(err.detail || err.message || "Could not load history"));
  }, []);

  async function handleDelete(e, jobId) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Remove this run from history? This can't be undone.")) return;
    setDeletingId(jobId);
    try {
      await deleteJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (err) {
      setError(err.detail || err.message || "Could not delete this run");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="app-shell fade-in">
      <div className="stack" style={{ gap: "var(--space-6)" }}>
        <div className="stack-sm">
          <span className="eyebrow">
            <LibraryIcon size={13} style={{ marginRight: 2, verticalAlign: -2 }} />
            Library
          </span>
          <h1 style={{ fontSize: "var(--text-2xl)" }}>Past runs</h1>
          <p className="subtitle">Every document you've generated a Teacher Knowledge Package from, newest first.</p>
        </div>

        {error && <div className="error-banner">{error}</div>}

        {jobs === null && !error && (
          <div className="stack">
            <div className="skeleton" style={{ height: 64 }} />
            <div className="skeleton" style={{ height: 64 }} />
            <div className="skeleton" style={{ height: 64 }} />
          </div>
        )}

        {jobs !== null && jobs.length === 0 && (
          <div className="card-bordered stack-sm" style={{ textAlign: "center", padding: "var(--space-8) var(--space-6)" }}>
            <FileText size={28} style={{ margin: "0 auto", opacity: 0.5 }} />
            <p className="muted">No runs yet. Upload a document to get started.</p>
            <Link to="/" className="btn btn-primary" style={{ alignSelf: "center", marginTop: "var(--space-2)" }}>
              Upload a document
            </Link>
          </div>
        )}

        {jobs !== null && jobs.length > 0 && (
          <div className="stack-sm">
            {jobs.map((job) => (
              <Link key={job.id} to={rowHref(job)} className="card row-between library-row">
                <div className="stack-sm" style={{ gap: 2 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <FileText size={15} style={{ opacity: 0.6 }} />
                    <span style={{ fontWeight: 600 }}>{job.document_filename}</span>
                  </div>
                  <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                    {job.subject || "Not yet classified"}
                    {job.topic ? ` · ${job.topic}` : ""} · {formatDate(job.created_at)}
                  </p>
                </div>
                <div className="row" style={{ gap: "var(--space-3)" }}>
                  <StatusBadge status={job.status} />
                  <button
                    type="button"
                    className="icon-btn"
                    title="Remove from history"
                    disabled={deletingId === job.id}
                    onClick={(e) => handleDelete(e, job.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
