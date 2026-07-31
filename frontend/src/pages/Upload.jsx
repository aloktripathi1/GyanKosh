import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileText, ClipboardCheck, Sparkles, Target } from "lucide-react";
import { uploadDocument } from "../api.js";

const ACCEPTED = ".pdf,.docx,.pptx,.txt";

const FEATURES = [
  { icon: Target, title: "Grounded, not hallucinated", desc: "Every generated claim traces back to a source span in your document." },
  { icon: Sparkles, title: "Full lesson package", desc: "Plans, activities, assessments, and a learning-gap analysis — generated together." },
  { icon: ClipboardCheck, title: "Reviewed before you use it", desc: "Schema, grounding, and consistency checks run automatically, surfaced in the UI." },
];

export default function Upload() {
  const [dragOver, setDragOver] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | uploading | error
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  const submit = useCallback(
    async (file) => {
      if (!file) return;
      setStatus("uploading");
      setError(null);
      try {
        const res = await uploadDocument(file);
        navigate(`/jobs/${res.job_id}`);
      } catch (err) {
        setStatus("error");
        setError(err.detail || err.message || "Upload failed");
      }
    },
    [navigate]
  );

  return (
    <div className="app-shell fade-in">
      <div className="stack" style={{ gap: "var(--space-7)" }}>
        <div className="stack" style={{ textAlign: "center", alignItems: "center" }}>
          <span className="eyebrow">
            <Sparkles size={12} /> AI teaching co-pilot
          </span>
          <h1 style={{ fontSize: "var(--text-3xl)", maxWidth: "18ch" }}>
            Turn any document into a <span className="gradient-text">ready-to-teach</span> package
          </h1>
          <p className="subtitle" style={{ textAlign: "center" }}>
            Upload a PDF, DOCX, PPTX, or plain-text document. GyanKosh produces lesson plans, activities,
            assessments, and a learning-gap analysis — grounded in the source material, with real-time progress.
          </p>
        </div>

        <div
          className={`dropzone${dragOver ? " dragover" : ""}`}
          onClick={() => status !== "uploading" && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            submit(e.dataTransfer.files[0]);
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            style={{ display: "none" }}
            onChange={(e) => submit(e.target.files[0])}
          />
          <div className="icon-badge">
            {status === "uploading" ? <FileText size={26} /> : <UploadCloud size={26} />}
          </div>
          {status === "uploading" ? (
            <div className="stack-sm" style={{ alignItems: "center" }}>
              <p style={{ fontWeight: 600, color: "var(--color-text)" }}>Uploading…</p>
              <div className="progress-track" style={{ maxWidth: 240 }}>
                <div className="progress-fill" style={{ width: "100%" }} />
              </div>
            </div>
          ) : (
            <div className="stack-sm">
              <p style={{ fontWeight: 650, color: "var(--color-text)", fontSize: "var(--text-lg)" }}>
                Drag a document here, or click to browse
              </p>
              <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                PDF, DOCX, PPTX, or TXT · up to 25 MB
              </p>
            </div>
          )}
        </div>

        {status === "error" && <div className="error-banner">Upload failed: {error}</div>}

        <div className="stack" style={{ gap: "var(--space-4)" }}>
          {FEATURES.map((f) => (
            <div className="feature-row" key={f.title}>
              <div className="icon-badge">
                <f.icon size={18} />
              </div>
              <div>
                <h4>{f.title}</h4>
                <p>{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
