import { CheckCircle, ChevronDown, ChevronUp, Clock, Download, FileText, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import { createT } from "../../lib/i18n";

interface ExamFile {
  id: string;
  name: string;
  subject: string;
  status: string;
}

interface GeneratedExam {
  id: string;
  title: string;
  questions: Question[];
  duration: number;
  totalMarks: number;
  createdAt: string;
}

interface Question {
  id: string;
  type: "mcq" | "short" | "essay" | "truefalse";
  text: string;
  marks: number;
  options?: string[];
  answer?: string;
}

interface ExamGeneratorProps {
  availableFiles: ExamFile[];
  initialSelectedIds?: string[];
  disabled?: boolean;
  onExamGenerated: (exam: GeneratedExam) => void;
  onGenerate?: (params: {
    documentIds: string[];
    examTitle: string;
    duration: number;
    numMCQ: number;
    numShort: number;
    numEssay: number;
    marksMCQ: number;
    marksShort: number;
    marksEssay: number;
    difficulty: "easy" | "medium" | "hard";
    language: "en" | "fr";
  }) => Promise<GeneratedExam>;
  onDownload?: (examId: string, format: string) => void | Promise<void>;
  onViewExam?: (examId: string) => void;
}

const MAX_MATERIALS = 5;

const TYPE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  mcq: { label: "MCQ", color: "#0069e0", bg: "#cce7ff" },
  short: { label: "Short Answer", color: "#1aa06d", bg: "#d3f6e3" },
  essay: { label: "Essay", color: "#9552e0", bg: "#f1e6ff" },
  truefalse: { label: "True/False", color: "#e05a00", bg: "#ffd1b8" },
};

function QuestionCard({ q, index }: { q: Question; index: number }) {
  const [expanded, setExpanded] = useState(true);
  const meta = TYPE_LABELS[q.type];

  return (
    <div style={{ backgroundColor: "#fafdff", borderRadius: 20, border: "1px solid rgba(83,88,98,0.12)", overflow: "hidden", marginBottom: 10 }}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded(!expanded);
          }
        }}
        style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 18px", cursor: "pointer" }}
      >
        <span style={{ width: 26, height: 26, borderRadius: 8, backgroundColor: "#f6f7f8", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: "#535862", flexShrink: 0 }}>
          {index + 1}
        </span>
        <p style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "#0a0d12", letterSpacing: "-0.01em" }}>{q.text}</p>
        <span style={{ padding: "3px 10px", borderRadius: 9999, backgroundColor: meta.bg, fontSize: 11, fontWeight: 600, color: meta.color, flexShrink: 0 }}>{meta.label}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#535862", flexShrink: 0 }}>{q.marks} pt{q.marks !== 1 ? "s" : ""}</span>
        {expanded ? <ChevronUp size={14} color="#93979f" /> : <ChevronDown size={14} color="#93979f" />}
      </div>
      {expanded && q.options && (
        <div style={{ padding: "0 18px 14px", display: "flex", flexDirection: "column", gap: 6 }}>
          {q.options.map((opt, oi) => (
            <div key={oi} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 18, height: 18, borderRadius: q.type === "truefalse" ? 4 : "50%", border: `1.5px solid ${opt === q.answer ? "#0069e0" : "rgba(83,88,98,0.25)"}`, backgroundColor: opt === q.answer ? "#cce7ff" : "transparent", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {opt === q.answer && <div style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: "#0069e0" }} />}
              </div>
              <span style={{ fontSize: 13, color: opt === q.answer ? "#0069e0" : "#535862", fontWeight: opt === q.answer ? 600 : 400 }}>{opt}</span>
              {opt === q.answer && <CheckCircle size={12} color="#0069e0" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ExamGenerator({
  availableFiles,
  initialSelectedIds,
  disabled,
  onExamGenerated,
  onGenerate,
  onDownload,
  onViewExam,
}: ExamGeneratorProps) {
  const { lang } = useLanguage();
  const t = createT(lang);

  const [selectedFiles, setSelectedFiles] = useState<string[]>(
    initialSelectedIds?.length
      ? initialSelectedIds
      : availableFiles[0]
        ? [availableFiles[0].id]
        : []
  );
  const [examTitle, setExamTitle] = useState("Chapter Exam");
  const [duration, setDuration] = useState(60);
  const [numMCQ, setNumMCQ] = useState(4);
  const [numShort, setNumShort] = useState(2);
  const [numEssay, setNumEssay] = useState(1);
  const [marksMCQ, setMarksMCQ] = useState(2);
  const [marksShort, setMarksShort] = useState(4);
  const [marksEssay, setMarksEssay] = useState(8);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [examLanguage, setExamLanguage] = useState<"en" | "fr">("en");
  const [generating, setGenerating] = useState(false);
  const [generatedExam, setGeneratedExam] = useState<GeneratedExam | null>(null);
  const [error, setError] = useState<string | null>(null);

  const atMax = selectedFiles.length >= MAX_MATERIALS;
  const totalMarks = numMCQ * marksMCQ + numShort * marksShort + numEssay * marksEssay;

  const toggleFile = (id: string) => {
    setSelectedFiles((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= MAX_MATERIALS) return prev;
      return [...prev, id];
    });
  };

  const handleGenerate = () => {
    if (!onGenerate) return;
    setGenerating(true);
    setError(null);
    void onGenerate({
      documentIds: selectedFiles,
      examTitle,
      duration,
      numMCQ,
      numShort,
      numEssay,
      marksMCQ,
      marksShort,
      marksEssay,
      difficulty,
      language: examLanguage,
    })
      .then((exam) => {
        setGeneratedExam(exam);
        onExamGenerated(exam);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setGenerating(false));
  };

  const difficultyKeys = [
    { val: "easy" as const, label: t("eg_easy") },
    { val: "medium" as const, label: t("eg_medium") },
    { val: "hard" as const, label: t("eg_hard") },
  ];

  return (
    <div style={{ backgroundColor: "#ebf5ff", minHeight: "calc(100vh - 64px)", fontFamily: "'Geist','Inter',sans-serif" }} className="px-4 py-10">
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        {/* Header */}
        <div className="mb-8">
          <h1 style={{ fontFamily: "'Inter',sans-serif", fontSize: 28, fontWeight: 700, color: "#0a0d12", letterSpacing: "-0.04em" }}>
            {t("eg_title")}
          </h1>
          <p style={{ fontSize: 14, color: "#93979f", marginTop: 6, letterSpacing: "-0.01em" }}>{t("eg_desc")}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
          {/* Config panel */}
          <div className="md:col-span-2 flex flex-col gap-4">
            {/* File selection */}
            <div style={{ backgroundColor: "#fafdff", borderRadius: 24, border: "1px solid rgba(83,88,98,0.12)", padding: 24 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "#0a0d12", letterSpacing: "-0.02em" }}>{t("eg_source")}</h3>
                <span style={{ fontSize: 11, color: selectedFiles.length === MAX_MATERIALS ? "#e05a00" : "#93979f", fontWeight: 500 }}>
                  {selectedFiles.length}/{MAX_MATERIALS}
                </span>
              </div>
              {availableFiles.length === 0 ? (
                <p style={{ fontSize: 13, color: "#93979f" }}>{t("eg_no_files")}</p>
              ) : (
                <>
                  <div className="flex flex-col gap-2">
                    {availableFiles.map((file) => {
                      const selected = selectedFiles.includes(file.id);
                      const blocked = !selected && atMax;
                      return (
                        <button
                          key={file.id}
                          onClick={() => toggleFile(file.id)}
                          disabled={blocked}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            padding: "10px 12px",
                            borderRadius: 12,
                            border: `1.5px solid ${selected ? "#0069e0" : "rgba(83,88,98,0.15)"}`,
                            backgroundColor: selected ? "#cce7ff" : blocked ? "#f6f7f8" : "#f6f7f8",
                            cursor: blocked ? "not-allowed" : "pointer",
                            opacity: blocked ? 0.5 : 1,
                            transition: "border-color 0.12s ease, background-color 0.12s ease",
                            textAlign: "left",
                          }}
                        >
                          <FileText size={14} color={selected ? "#0069e0" : "#93979f"} />
                          <span style={{ fontSize: 13, fontWeight: 500, color: "#0a0d12", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</span>
                          {selected && <CheckCircle size={14} color="#0069e0" />}
                        </button>
                      );
                    })}
                  </div>
                  {atMax && (
                    <p style={{ fontSize: 11, color: "#e05a00", marginTop: 8 }}>{t("eg_max_materials")}</p>
                  )}
                </>
              )}
            </div>

            {/* Settings */}
            <div style={{ backgroundColor: "#fafdff", borderRadius: 24, border: "1px solid rgba(83,88,98,0.12)", padding: 24 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "#0a0d12", letterSpacing: "-0.02em", marginBottom: 16 }}>{t("eg_settings")}</h3>
              <div className="flex flex-col gap-4">
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#535862", display: "block", marginBottom: 6 }}>{t("eg_exam_title")}</label>
                  <input
                    value={examTitle}
                    onChange={(e) => setExamTitle(e.target.value)}
                    style={{ width: "100%", padding: "9px 12px", borderRadius: 10, border: "1px solid rgba(83,88,98,0.2)", backgroundColor: "#f6f7f8", fontSize: 13, color: "#0a0d12", fontFamily: "'Geist','Inter',sans-serif", outline: "none", boxSizing: "border-box" }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#535862", display: "block", marginBottom: 6 }}>{t("eg_duration")}</label>
                  <input type="number" value={duration} min={15} max={180} step={5} onChange={(e) => setDuration(+e.target.value)}
                    style={{ width: "100%", padding: "9px 12px", borderRadius: 10, border: "1px solid rgba(83,88,98,0.2)", backgroundColor: "#f6f7f8", fontSize: 13, color: "#0a0d12", fontFamily: "'Geist','Inter',sans-serif", outline: "none", boxSizing: "border-box" }} />
                </div>

                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#535862", display: "block", marginBottom: 8 }}>{t("eg_difficulty")}</label>
                  <div style={{ display: "flex", gap: 6 }}>
                    {difficultyKeys.map(({ val, label }) => (
                      <button key={val} onClick={() => setDifficulty(val)}
                        style={{
                          flex: 1, padding: "7px 0", borderRadius: 9999, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600,
                          backgroundColor: difficulty === val ? "#181d27" : "#f6f7f8",
                          color: difficulty === val ? "#fff" : "#535862",
                          transition: "background-color 0.12s ease, color 0.12s ease",
                        }}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Exam language */}
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#535862", display: "block", marginBottom: 8 }}>{t("eg_language")}</label>
                  <div style={{ display: "flex", gap: 6 }}>
                    {([
                      { val: "en" as const, label: t("eg_lang_en") },
                      { val: "fr" as const, label: t("eg_lang_fr") },
                    ]).map(({ val, label }) => (
                      <button key={val} onClick={() => setExamLanguage(val)}
                        style={{
                          flex: 1, padding: "7px 0", borderRadius: 9999, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600,
                          backgroundColor: examLanguage === val ? "#0069e0" : "#f6f7f8",
                          color: examLanguage === val ? "#fff" : "#535862",
                          transition: "background-color 0.12s ease, color 0.12s ease",
                        }}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#535862", display: "block", marginBottom: 8 }}>{t("eg_count")}</label>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: t("eg_mcq"), value: numMCQ, set: setNumMCQ },
                      { label: t("eg_short"), value: numShort, set: setNumShort },
                      { label: t("eg_essay"), value: numEssay, set: setNumEssay },
                    ].map(({ label, value, set }) => (
                      <div key={label}>
                        <label style={{ fontSize: 11, fontWeight: 600, color: "#93979f", display: "block", marginBottom: 5, textAlign: "center" }}>{label}</label>
                        <input type="number" value={value} min={0} max={20} onChange={(e) => set(+e.target.value)}
                          style={{ width: "100%", padding: "7px 10px", borderRadius: 10, border: "1px solid rgba(83,88,98,0.2)", backgroundColor: "#f6f7f8", fontSize: 13, color: "#0a0d12", fontFamily: "'Geist','Inter',sans-serif", outline: "none", boxSizing: "border-box", textAlign: "center" }} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Grading */}
            <div style={{ backgroundColor: "#fafdff", borderRadius: 24, border: "1px solid rgba(83,88,98,0.12)", padding: 24 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "#0a0d12", letterSpacing: "-0.02em", marginBottom: 4 }}>{t("eg_grading")}</h3>
              <p style={{ fontSize: 12, color: "#93979f", marginBottom: 16 }}>{t("eg_grading_hint")}</p>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: t("eg_marks_per_mcq"), value: marksMCQ, set: setMarksMCQ },
                  { label: t("eg_marks_per_short"), value: marksShort, set: setMarksShort },
                  { label: t("eg_marks_per_essay"), value: marksEssay, set: setMarksEssay },
                ].map(({ label, value, set }) => (
                  <div key={label}>
                    <label style={{ fontSize: 11, fontWeight: 600, color: "#93979f", display: "block", marginBottom: 5, textAlign: "center" }}>{label}</label>
                    <input type="number" value={value} min={0} max={100} onChange={(e) => set(+e.target.value)}
                      style={{ width: "100%", padding: "7px 10px", borderRadius: 10, border: "1px solid rgba(83,88,98,0.2)", backgroundColor: "#f6f7f8", fontSize: 13, color: "#0a0d12", fontFamily: "'Geist','Inter',sans-serif", outline: "none", boxSizing: "border-box", textAlign: "center" }} />
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16, paddingTop: 14, borderTop: "1px solid rgba(83,88,98,0.1)" }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "#535862" }}>{t("eg_total_marks")}</span>
                <span style={{ fontSize: 18, fontWeight: 700, color: "#0a0d12", fontVariantNumeric: "tabular-nums" }}>{totalMarks}</span>
              </div>
            </div>

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={generating || selectedFiles.length === 0 || disabled}
              style={{
                backgroundColor: generating || selectedFiles.length === 0 || disabled ? "#93979f" : "#181d27",
                color: "#fff",
                borderRadius: 9999,
                padding: "14px 24px",
                fontSize: 14,
                fontWeight: 600,
                letterSpacing: "-0.01em",
                border: "none",
                cursor: generating || selectedFiles.length === 0 || disabled ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                transition: "background-color 0.15s ease",
              }}
              onMouseEnter={(e) => { if (!generating && selectedFiles.length > 0) e.currentTarget.style.backgroundColor = "#2d3444"; }}
              onMouseLeave={(e) => { if (!generating && selectedFiles.length > 0) e.currentTarget.style.backgroundColor = "#181d27"; }}
            >
              {generating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {generating ? t("eg_generating") : disabled ? t("eg_limit") : t("eg_generate")}
            </button>
            {error && <p style={{ fontSize: 13, color: "#e05a00", marginTop: 8, lineHeight: 1.4 }}>{error}</p>}
          </div>

          {/* Preview panel */}
          <div className="md:col-span-3">
            {generating && (
              <div style={{ backgroundColor: "#fafdff", borderRadius: 24, border: "1px solid rgba(83,88,98,0.12)", padding: 48, textAlign: "center" }}>
                <div style={{ width: 64, height: 64, borderRadius: 20, backgroundColor: "#9552e0", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
                  <Sparkles size={28} color="#fff" className="animate-pulse" />
                </div>
                <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 18, fontWeight: 600, color: "#0a0d12", letterSpacing: "-0.03em", marginBottom: 8 }}>{t("eg_ai_loading")}</p>
                <p style={{ fontSize: 13, color: "#93979f" }}>{t("eg_ai_subtext")}</p>
                <div style={{ marginTop: 24, height: 4, backgroundColor: "#f6f7f8", borderRadius: 9999, overflow: "hidden", maxWidth: 240, margin: "24px auto 0" }}>
                  <div style={{ height: "100%", backgroundColor: "#9552e0", borderRadius: 9999, animation: "pulse 1.5s ease-in-out infinite", width: "60%" }} />
                </div>
              </div>
            )}

            {!generating && !generatedExam && (
              <div style={{ backgroundColor: "#fafdff", borderRadius: 24, border: "1px solid rgba(83,88,98,0.12)", padding: 48, textAlign: "center" }}>
                <div style={{ width: 64, height: 64, borderRadius: 20, backgroundColor: "#f6f7f8", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
                  <FileText size={28} color="#93979f" />
                </div>
                <p style={{ fontSize: 16, fontWeight: 600, color: "#0a0d12", letterSpacing: "-0.02em", marginBottom: 6 }}>{t("eg_empty_title")}</p>
                <p style={{ fontSize: 13, color: "#93979f" }}>{t("eg_empty_hint")}</p>
              </div>
            )}

            {!generating && generatedExam && (
              <div className="mffb-enter" style={{ backgroundColor: "#fafdff", borderRadius: 24, border: "1px solid rgba(83,88,98,0.12)", overflow: "hidden" }}>
                {/* Exam header */}
                <div style={{ backgroundColor: "#9552e0", padding: "24px 24px" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                    <div>
                      <p style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.7)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 4 }}>{t("eg_generated_label")}</p>
                      <h2 style={{ fontFamily: "'Inter',sans-serif", fontSize: 18, fontWeight: 700, color: "#fff", letterSpacing: "-0.03em", lineHeight: 1.2 }}>{generatedExam.title}</h2>
                      <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
                        <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "rgba(255,255,255,0.8)", fontVariantNumeric: "tabular-nums" }}>
                          <Clock size={13} />{generatedExam.duration} {t("eg_min")}
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "rgba(255,255,255,0.8)", fontVariantNumeric: "tabular-nums" }}>
                          <FileText size={13} />{generatedExam.questions.length} {t("eg_questions")}
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "rgba(255,255,255,0.8)", fontVariantNumeric: "tabular-nums" }}>
                          <Sparkles size={13} />{generatedExam.totalMarks} {t("eg_marks")}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      {onViewExam && (
                        <button onClick={() => onViewExam(generatedExam.id)} style={{ display: "flex", alignItems: "center", gap: 6, backgroundColor: "rgba(255,255,255,0.25)", color: "#fff", borderRadius: 9999, padding: "7px 14px", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                          {t("eg_open_full")}
                        </button>
                      )}
                      <button onClick={() => void onDownload?.(generatedExam.id, "pdf")} style={{ display: "flex", alignItems: "center", gap: 6, backgroundColor: "rgba(255,255,255,0.15)", color: "#fff", borderRadius: 9999, padding: "7px 14px", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                        <Download size={13} /> PDF
                      </button>
                      <button onClick={() => void onDownload?.(generatedExam.id, "docx")} style={{ display: "flex", alignItems: "center", gap: 6, backgroundColor: "rgba(255,255,255,0.15)", color: "#fff", borderRadius: 9999, padding: "7px 14px", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                        <Download size={13} /> DOCX
                      </button>
                    </div>
                  </div>
                </div>

                {/* Questions */}
                <div style={{ padding: "20px" }}>
                  {generatedExam.questions.map((q, i) => (
                    <QuestionCard key={q.id} q={q} index={i} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
