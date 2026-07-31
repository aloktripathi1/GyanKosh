import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  LayoutGrid,
  AlertTriangle,
  FileDown,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Tag,
  BookOpen,
  CalendarDays,
  PenLine,
  Puzzle,
  ClipboardList,
} from "lucide-react";
import { getTkp, regenerateSection } from "../api.js";

const API_KEY = import.meta.env.VITE_API_KEY || "dev-local-key";

const TABS_STATIC = [
  { key: "overview", label: "Overview", icon: LayoutGrid },
  { key: "gaps", label: "Learning Gaps", icon: AlertTriangle },
];

export default function TKPReview() {
  const { tkpId } = useParams();
  const [tkp, setTkp] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("overview");
  const [regenerating, setRegenerating] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await getTkp(tkpId);
      setTkp(data);
      setError(null);
    } catch (err) {
      setError(err.detail || err.message || "Could not load this package");
    }
  }, [tkpId]);

  useEffect(() => {
    load();
  }, [load]);

  const regenerate = useCallback(
    async (section) => {
      setRegenerating(section);
      try {
        const updated = await regenerateSection(tkpId, section);
        setTkp(updated);
      } catch (err) {
        setError(err.detail || err.message || `Could not regenerate ${section}`);
      } finally {
        setRegenerating(null);
      }
    },
    [tkpId]
  );

  if (error && !tkp) {
    return (
      <div className="app-shell">
        <div className="error-banner">{error}</div>
      </div>
    );
  }
  if (!tkp) {
    return (
      <div className="app-shell stack">
        <div className="skeleton" style={{ height: 40, width: "50%" }} />
        <div className="skeleton" style={{ height: 200 }} />
      </div>
    );
  }

  const periods = tkp.teaching_plan?.periods ?? [];
  const tabs = [
    TABS_STATIC[0],
    ...periods.map((p) => ({ key: `period-${p.period_number}`, label: `Period ${p.period_number}` })),
    TABS_STATIC[1],
  ];

  return (
    <div className="app-shell fade-in">
      <div className="stack">
        <Header tkp={tkp} />
        {error && <div className="error-banner">{error}</div>}

        <div className="period-tabs">
          {tabs.map((t) => (
            <button
              key={t.key}
              className={`period-tab${tab === t.key ? " active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.icon && <t.icon size={13} style={{ marginRight: 4, verticalAlign: -2 }} />}
              {t.label}
            </button>
          ))}
        </div>

        {tab === "overview" && <Overview tkp={tkp} regenerate={regenerate} regenerating={regenerating} />}
        {tab === "gaps" && <GapsPanel tkp={tkp} regenerate={regenerate} regenerating={regenerating} />}
        {periods.map(
          (p) =>
            tab === `period-${p.period_number}` && (
              <PeriodPanel key={p.period_number} tkp={tkp} period={p} regenerate={regenerate} regenerating={regenerating} />
            )
        )}
      </div>
    </div>
  );
}

function Header({ tkp }) {
  const c = tkp.classification || {};
  return (
    <div className="card-bordered">
      <p className="eyebrow">Teacher Knowledge Package</p>
      <h1 style={{ marginTop: "var(--space-2)" }}>{c.topic || "Untitled"}</h1>
      <p className="subtitle">
        {c.subject} · Grade {c.grade} · {c.chapter}
      </p>
      <div className="row" style={{ marginTop: "var(--space-4)", flexWrap: "wrap" }}>
        <ValidationBadge report={tkp.validation_report} />
        {tkp.pdf_paths &&
          Object.entries(tkp.pdf_paths).map(([name, path]) => (
            <a
              key={name}
              className="badge badge-neutral"
              href={`/api/files/${path}?api_key=${encodeURIComponent(API_KEY)}`}
              target="_blank"
              rel="noreferrer"
            >
              <FileDown size={12} />
              {name.replaceAll("_", " ")} PDF
            </a>
          ))}
      </div>
    </div>
  );
}

function ValidationBadge({ report }) {
  if (!report) return <span className="badge badge-neutral">Not yet validated</span>;
  const checks = [report.schema_check, report.grounding_check, report.completeness_check, report.consistency_check];
  const passed = checks.every((c) => c?.passed);
  return passed ? (
    <span className="badge badge-success">
      <CheckCircle2 size={12} /> Validation passed
    </span>
  ) : (
    <span className="badge badge-error">
      <XCircle size={12} /> Validation issues found
    </span>
  );
}

function SectionHeader({ title, icon: Icon, section, regenerate, regenerating, scopeNote }) {
  return (
    <div className="section-header">
      <div>
        <h3 className="row" style={{ gap: 8 }}>
          {Icon && <Icon size={16} style={{ color: "var(--color-primary)" }} />}
          {title}
        </h3>
        {scopeNote && (
          <p className="muted" style={{ fontSize: "var(--text-xs)", marginTop: 2 }}>
            {scopeNote}
          </p>
        )}
      </div>
      {section && (
        <button className="regen-btn" disabled={regenerating === section} onClick={() => regenerate(section)}>
          <RefreshCw size={12} className={regenerating === section ? "spin" : undefined} />
          {regenerating === section ? "Regenerating…" : "Regenerate"}
        </button>
      )}
    </div>
  );
}

function Overview({ tkp, regenerate, regenerating }) {
  const ek = tkp.extracted_knowledge || {};
  return (
    <div className="card stack">
      <div className="section-block">
        <SectionHeader
          title="Classification"
          icon={Tag}
          section="classification"
          regenerate={regenerate}
          regenerating={regenerating}
        />
        <p>
          {tkp.classification?.subject} · Grade {tkp.classification?.grade} · {tkp.classification?.difficulty} ·{" "}
          {tkp.classification?.category}
        </p>
      </div>

      <div className="section-block">
        <SectionHeader
          title="Extracted Knowledge"
          icon={BookOpen}
          section="extracted_knowledge"
          regenerate={regenerate}
          regenerating={regenerating}
        />
        <KnowledgeList label="Objectives" items={ek.objectives} />
        <KnowledgeList label="Concepts" items={ek.concepts} render={(i) => `${i.name}: ${i.text}`} />
        <KnowledgeList label="Formulae" items={ek.formulae} render={(i) => `${i.name} — ${i.expression}`} />
        <KnowledgeList label="Misconceptions" items={ek.misconceptions} render={(i) => i.text} />
      </div>

      <div className="section-block">
        <SectionHeader
          title="Teaching Plan"
          icon={CalendarDays}
          section="teaching_plan"
          regenerate={regenerate}
          regenerating={regenerating}
          scopeNote="Regenerating the plan may make already-generated period content inconsistent — check the validation badge after."
        />
        <p>{tkp.teaching_plan?.planning_rationale}</p>
      </div>

      <ValidationDetail report={tkp.validation_report} />
    </div>
  );
}

function KnowledgeList({ label, items, render }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginTop: "var(--space-3)" }}>
      <p style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{label}</p>
      <ul>
        {items.map((item, i) => (
          <li key={i} style={{ fontSize: "var(--text-sm)" }}>
            {render ? render(item) : item.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ValidationDetail({ report }) {
  if (!report) return null;
  const rows = [
    ["Schema", report.schema_check],
    ["Grounding", report.grounding_check],
    ["Completeness", report.completeness_check],
    ["Consistency", report.consistency_check],
  ];
  return (
    <div className="section-block">
      <h3>Validation Report</h3>
      <div className="stack-sm" style={{ marginTop: "var(--space-2)" }}>
        {rows.map(([label, check]) => (
          <div key={label} className="row-between">
            <span style={{ fontSize: "var(--text-sm)" }}>{label}</span>
            <span className={`badge ${check?.passed ? "badge-success" : "badge-error"}`}>
              {check?.passed ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
              {check?.passed ? "Passed" : "Failed"}
            </span>
          </div>
        ))}
      </div>
      {rows
        .filter(([, check]) => check && !check.passed)
        .map(([label, check]) => (
          <div key={label} className="error-banner" style={{ marginTop: "var(--space-2)" }}>
            <strong>{label}:</strong> {(check.errors || check.violations || check.missing_items || check.conflicts || [])
              .map((v) => (typeof v === "string" ? v : v.claim || v.reason))
              .join("; ")}
          </div>
        ))}
    </div>
  );
}

function PeriodPanel({ tkp, period, regenerate, regenerating }) {
  const content = tkp.period_content?.periods?.find((p) => p.period_number === period.period_number);
  const activities = tkp.activities?.periods?.find((p) => p.period_number === period.period_number);
  const assessment = tkp.assessments?.periods?.find((p) => p.period_number === period.period_number);

  return (
    <div className="card stack">
      <div className="section-block">
        <h2>{period.title}</h2>
        <p className="muted" style={{ fontSize: "var(--text-sm)", marginTop: "var(--space-1)" }}>
          {period.sequencing_rationale}
        </p>
        <ul>
          {period.objectives?.map((o, i) => (
            <li key={i} style={{ fontSize: "var(--text-sm)" }}>
              {o}
            </li>
          ))}
        </ul>
      </div>

      <div className="section-block">
        <SectionHeader
          title="Lesson Content"
          icon={PenLine}
          section="period_content"
          regenerate={regenerate}
          regenerating={regenerating}
          scopeNote="Regenerates content for every period, not just this one."
        />
        {content ? (
          <div className="stack-sm">
            <Field label="Entry ticket" value={content.entry_ticket} />
            <Field label="Teacher script" value={content.teacher_script} />
            <Field label="Blackboard notes" value={content.blackboard_notes} />
            <Field label="Exit ticket" value={content.exit_ticket} />
            <Field label="Homework" value={content.homework} />
            <Field label="Mentor moment" value={content.mentor_moment} />
            {content.checkpoint_questions?.length > 0 && (
              <div>
                <p style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>Checkpoint questions</p>
                {content.checkpoint_questions.map((q, i) => (
                  <p key={i} style={{ fontSize: "var(--text-sm)" }}>
                    <strong>Q:</strong> {q.question} <strong>A:</strong> {q.expected_answer}
                  </p>
                ))}
              </div>
            )}
          </div>
        ) : (
          <EmptyNote label="content" />
        )}
      </div>

      <div className="section-block">
        <SectionHeader
          title="Activities"
          icon={Puzzle}
          section="activities"
          regenerate={regenerate}
          regenerating={regenerating}
          scopeNote="Regenerates activities for every period, not just this one."
        />
        {activities?.activities?.length > 0 ? (
          activities.activities.map((a, i) => (
            <div key={i} style={{ marginBottom: "var(--space-2)" }}>
              <p style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>
                {a.title} · {a.type} · {a.duration_minutes} min
              </p>
              <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                {a.instructions?.join(" → ")}
              </p>
            </div>
          ))
        ) : (
          <EmptyNote label="activities" />
        )}
      </div>

      <div className="section-block">
        <SectionHeader
          title="Assessment"
          icon={ClipboardList}
          section="assessments"
          regenerate={regenerate}
          regenerating={regenerating}
          scopeNote="Regenerates assessments for every period, not just this one."
        />
        {assessment ? (
          <div className="stack-sm">
            {assessment.mcqs?.map((q, i) => (
              <p key={`mcq-${i}`} style={{ fontSize: "var(--text-sm)" }}>
                <strong>MCQ:</strong> {q.question}
              </p>
            ))}
            {assessment.short_answer?.map((q, i) => (
              <p key={`sa-${i}`} style={{ fontSize: "var(--text-sm)" }}>
                <strong>Short answer:</strong> {q.question}
              </p>
            ))}
            {assessment.numerical?.map((q, i) => (
              <p key={`num-${i}`} style={{ fontSize: "var(--text-sm)" }}>
                <strong>Numerical:</strong> {q.question}
              </p>
            ))}
          </div>
        ) : (
          <EmptyNote label="assessment" />
        )}
      </div>
    </div>
  );
}

function GapsPanel({ tkp, regenerate, regenerating }) {
  const gaps = tkp.learning_gaps?.gaps || [];
  return (
    <div className="card stack">
      <SectionHeader
        title="Learning Gaps"
        icon={AlertTriangle}
        section="learning_gaps"
        regenerate={regenerate}
        regenerating={regenerating}
      />
      {gaps.length === 0 ? (
        <EmptyNote label="learning gaps" />
      ) : (
        gaps.map((g, i) => (
          <div key={i} className="section-block">
            <div className="row-between">
              <p style={{ fontWeight: 600 }}>{g.misconception}</p>
              <span className={`badge ${g.severity === "high" ? "badge-error" : g.severity === "medium" ? "badge-warning" : "badge-neutral"}`}>
                {g.severity}
              </span>
            </div>
            <p style={{ fontSize: "var(--text-sm)" }}>{g.remediation}</p>
          </div>
        ))
      )}
    </div>
  );
}

function Field({ label, value }) {
  if (!value) return null;
  return (
    <div>
      <p style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{label}</p>
      <p style={{ fontSize: "var(--text-sm)" }}>{value}</p>
    </div>
  );
}

function EmptyNote({ label }) {
  return <p className="muted">No {label} generated for this package.</p>;
}
