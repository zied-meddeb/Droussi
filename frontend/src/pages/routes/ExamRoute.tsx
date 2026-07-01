import { useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useUserData } from "../../hooks/useUserData";
import { useUsage } from "../../hooks/useUsage";
import { ExamGenerator } from "../../components/droussi/ExamGenerator";
import { apiFetch } from "../../lib/api";
import {
  buildExamSpec,
  docToExamFile,
  examContentToGenerated,
  type GeneratedExamView,
} from "../../lib/droussiData";
import { getDocumentMetaOrDefault } from "../../lib/documentMeta";
import type { ExamRow } from "../../types";

export default function ExamRoute() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectDoc = searchParams.get("doc");
  const { docs, reload } = useUserData();
  const { atLimit, refresh } = useUsage();

  const availableFiles = useMemo(
    () => docs.map((d) => docToExamFile(d, getDocumentMetaOrDefault(d.id))),
    [docs]
  );

  useEffect(() => {
    if (preselectDoc && docs.some((d) => d.id === preselectDoc)) {
      // ExamGenerator reads initial selection from first file; preselect handled via key remount
    }
  }, [preselectDoc, docs]);

  if (!user) return null;

  async function handleGenerate(params: {
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
  }): Promise<GeneratedExamView> {
    if (atLimit) throw new Error("Daily exam limit reached. Try again after midnight UTC.");
    if (!params.documentIds.length) throw new Error("Select at least one source document.");

    const primaryId = params.documentIds[0];

    const draft = await apiFetch<{ id: string }>(
      `/api/exams/draft?document_id=${primaryId}`,
      { method: "POST" }
    );

    const spec = buildExamSpec({
      difficulty: params.difficulty,
      numMCQ: params.numMCQ,
      numShort: params.numShort,
      numEssay: params.numEssay,
      marksMCQ: params.marksMCQ,
      marksShort: params.marksShort,
      marksEssay: params.marksEssay,
      extraInstructions: params.examTitle,
      language: params.language,
    });

    const exam = await apiFetch<ExamRow>(`/api/exams/${draft.id}/generate`, {
      method: "POST",
      body: JSON.stringify({
        document_id: primaryId,
        document_ids: params.documentIds,
        spec,
      }),
      timeoutMs: 190_000,
    });

    await refresh();
    await reload();

    if (!exam.content) throw new Error("Exam generated but content is missing.");
    const view = examContentToGenerated(exam.id, exam.content, params.duration);
    view.title = params.examTitle || view.title;
    return view;
  }

  return (
    <ExamGenerator
      key={preselectDoc ?? "default"}
      availableFiles={availableFiles}
      initialSelectedIds={
        preselectDoc && docs.some((d) => d.id === preselectDoc)
          ? [preselectDoc]
          : undefined
      }
      disabled={atLimit}
      onExamGenerated={() => {}}
      onGenerate={handleGenerate}
      onDownload={async (examId, format) => {
        const { url } = await apiFetch<{ url: string }>(`/api/exams/${examId}/download?format=${format}`);
        window.open(url, "_blank");
      }}
      onViewExam={(examId) => navigate(`/exams/${examId}`)}
    />
  );
}
