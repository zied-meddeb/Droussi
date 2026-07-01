import { supabase, DOCUMENTS_BUCKET } from "./supabase";
import { apiFetch } from "./api";
import type { DocumentRow, ExamContent, ExamRow, ExamSpec } from "../types";

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString();
}

export function fileExt(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? "file";
}

export async function uploadDocument(
  userId: string,
  file: File
): Promise<DocumentRow> {
  const ext = file.name.split(".").pop() ?? "bin";
  const path = `${userId}/${crypto.randomUUID()}.${ext}`;

  const { error: upErr } = await supabase.storage
    .from(DOCUMENTS_BUCKET)
    .upload(path, file, { contentType: file.type, upsert: false });
  if (upErr) throw upErr;

  return apiFetch<DocumentRow>("/api/documents/register", {
    method: "POST",
    body: JSON.stringify({
      filename: file.name,
      storage_path: path,
      mime_type: file.type,
      size_bytes: file.size,
    }),
  });
}

export function docToRepoFile(
  doc: DocumentRow,
  examCount: number,
  meta?: { subject: string; tags: string[] }
) {
  return {
    id: doc.id,
    name: doc.filename,
    subject: meta?.subject ?? "General",
    type: fileExt(doc.filename),
    uploadedAt: doc.created_at.slice(0, 10),
    tags: meta?.tags ?? [],
    examCount,
    size: formatBytes(doc.size_bytes),
  };
}

export function docToExamFile(
  doc: DocumentRow,
  meta?: { subject: string; tags: string[] }
) {
  return {
    id: doc.id,
    name: doc.filename,
    subject: meta?.subject ?? "General",
    status: "ready",
  };
}

export function examToOutput(exam: ExamRow, subject = "General") {
  const content = exam.content;
  return {
    id: exam.id,
    title: content?.title ?? exam.title ?? "Untitled exam",
    subject,
    createdAt: exam.created_at.slice(0, 10),
    duration: 60,
    questions: content?.exercises.length ?? 0,
    totalMarks: content?.total_points ?? exam.spec?.total_points ?? 0,
    // Both formats are always downloadable when we have the exam content to
    // render from; otherwise fall back to whatever was rendered at generation.
    formats: content ? ["pdf", "docx"] : exam.export_format ? [exam.export_format] : ["pdf"],
    status: exam.status === "ready" ? ("ready" as const) : ("processing" as const),
  };
}

export interface GeneratedQuestion {
  id: string;
  type: "mcq" | "short" | "essay" | "truefalse";
  text: string;
  marks: number;
  options?: string[];
  answer?: string;
}

export interface GeneratedExamView {
  id: string;
  title: string;
  questions: GeneratedQuestion[];
  duration: number;
  totalMarks: number;
  createdAt: string;
}

export function examContentToGenerated(
  examId: string,
  content: ExamContent,
  duration = 60
): GeneratedExamView {
  return {
    id: examId,
    title: content.title,
    duration,
    totalMarks: content.total_points,
    createdAt: new Date().toISOString().slice(0, 10),
    questions: content.exercises.map((ex, i) => ({
      id: String(i),
      type: ex.type === "mcq" ? "mcq" : "short",
      text: ex.question,
      marks: ex.points,
      options: ex.choices,
      answer: ex.answer,
    })),
  };
}

export function buildExamSpec(params: {
  difficulty: "easy" | "medium" | "hard";
  numMCQ: number;
  numShort: number;
  numEssay: number;
  marksMCQ?: number;
  marksShort?: number;
  marksEssay?: number;
  exportFormat?: "pdf" | "docx";
  extraInstructions?: string;
  language?: "en" | "fr";
}): ExamSpec {
  const num = Math.max(1, params.numMCQ + params.numShort + params.numEssay);
  const types: ExamSpec["question_types"] = [];
  if (params.numMCQ > 0) types.push("mcq");
  if (params.numShort + params.numEssay > 0) types.push("open");
  if (types.length === 0) types.push("mcq", "open");

  const mMCQ = Math.max(0, params.marksMCQ ?? 4);
  const mShort = Math.max(0, params.marksShort ?? 4);
  const mEssay = Math.max(0, params.marksEssay ?? 4);

  // Order must match the prompt: MCQ first, then open-ended (short, then essay).
  const perExercise = [
    ...Array(params.numMCQ).fill(mMCQ),
    ...Array(params.numShort).fill(mShort),
    ...Array(params.numEssay).fill(mEssay),
  ];
  // Fallback if counts were all zero (num was clamped to 1).
  if (perExercise.length === 0) perExercise.push(mMCQ || 4);

  const total = perExercise.reduce((a, b) => a + b, 0);

  return {
    difficulty: params.difficulty,
    question_types: types,
    num_exercises: num,
    total_points: total,
    per_exercise_points: perExercise,
    export_format: params.exportFormat ?? "pdf",
    language: params.language ?? "en",
    extra_instructions: params.extraInstructions,
  };
}

export type ActivityItem = {
  id: string;
  type: "upload" | "exam" | "download";
  title: string;
  time: string;
  color: string;
};

export function buildRecentActivity(
  docs: DocumentRow[],
  exams: ExamRow[]
): ActivityItem[] {
  const items: (ActivityItem & { sort: number })[] = [];

  for (const d of docs.slice(0, 10)) {
    items.push({
      id: `doc-${d.id}`,
      type: "upload",
      title: d.filename,
      time: formatRelativeTime(d.created_at),
      color: "#cce7ff",
      sort: new Date(d.created_at).getTime(),
    });
  }

  for (const e of exams.filter((x) => x.status === "ready").slice(0, 10)) {
    items.push({
      id: `exam-${e.id}`,
      type: "exam",
      title: e.content?.title ?? e.title ?? "Generated exam",
      time: formatRelativeTime(e.created_at),
      color: "#f1e6ff",
      sort: new Date(e.created_at).getTime(),
    });
  }

  return items
    .sort((a, b) => b.sort - a.sort)
    .slice(0, 5)
    .map(({ sort: _sort, ...rest }) => rest);
}
