import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDocument } from "../api.js";

const ACCEPTED = ".pdf,.docx,.pptx,.txt";

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
    <div className="app-shell">
      <div className="stack">
        <div>
          <p className="eyebrow">GyanKosh</p>
          <h1>Turn a document into a teaching package</h1>
          <p className="subtitle">
            Upload a PDF, DOCX, PPTX, or plain-text document. GyanKosh will produce lesson plans, activities,
            assessments, and a learning-gap analysis — grounded in the source material.
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
          {status === "uploading" ? (
            <p>Uploading…</p>
          ) : (
            <div className="stack-sm">
              <p style={{ fontWeight: 600, color: "var(--color-text)" }}>
                Drag a document here, or click to browse
              </p>
              <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                PDF, DOCX, PPTX, or TXT · up to 25 MB
              </p>
            </div>
          )}
        </div>

        {status === "error" && <div className="error-banner">Upload failed: {error}</div>}
      </div>
    </div>
  );
}
