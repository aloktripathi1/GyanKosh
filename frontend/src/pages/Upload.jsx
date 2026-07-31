import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileText, Target, LayoutList, ShieldCheck } from "lucide-react";
import { uploadDocument } from "../api.js";

const ACCEPTED = ".pdf,.docx,.pptx,.txt";

const FEATURES = [
  { icon: Target, title: "Grounded, not hallucinated", desc: "Every generated claim traces back to a source span in your document." },
  { icon: LayoutList, title: "Full lesson package", desc: "Plans, activities, assessments, and a learning-gap analysis — generated together." },
  { icon: ShieldCheck, title: "Reviewed before you use it", desc: "Schema, grounding, and consistency checks run automatically, surfaced in the UI." },
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
        <div className="stack">
          <span className="eyebrow">A teaching co-pilot</span>
          <h1 style={{ maxWidth: "16ch" }}>
            Turn any document into a <span className="highlight-mark">ready-to-teach</span> package
          </h1>
          <p className="subtitle">
            Upload a PDF, DOCX, PPTX, or plain-text document. GyanKosh produces lesson plans, activities,
            assessments, and a learning-gap analysis — grounded in the source material, with progress you can
            watch happen.
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
          <span className="corner corner-tl" />
          <span className="corner corner-br" />
          <div className="stack-sm" style={{ alignItems: "center" }}>
            {status === "uploading" ? <FileText size={22} /> : <UploadCloud size={22} />}
            {status === "uploading" ? (
              <>
                <p style={{ fontWeight: 600, color: "var(--color-text)" }}>Uploading…</p>
                <div className="progress-track" style={{ maxWidth: 220 }}>
                  <div className="progress-fill" style={{ width: "100%" }} />
                </div>
              </>
            ) : (
              <>
                <p style={{ fontWeight: 650, color: "var(--color-text)", fontSize: "var(--text-base)" }}>
                  Drag a document here, or click to browse
                </p>
                <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                  PDF, DOCX, PPTX, or TXT · up to 25 MB
                </p>
              </>
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            style={{ display: "none" }}
            onChange={(e) => submit(e.target.files[0])}
          />
        </div>

        {status === "error" && <div className="error-banner">Upload failed: {error}</div>}

        <div className="stack" style={{ gap: "var(--space-4)", borderTop: "var(--rule)", paddingTop: "var(--space-5)" }}>
          {FEATURES.map((f) => (
            <div className="feature-row" key={f.title}>
              <f.icon size={16} className="feature-icon" />
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
