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

const POLL_INTERVAL_MS = 2000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Poll an exam row until generation finishes (ready/error) or the deadline. */
async function pollExamUntilDone(
  examId: string,
  timeoutMs: number
): Promise<ExamRow> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const exam = await apiFetch<ExamRow>(`/api/exams/${examId}`);
    if (exam.status === "ready" || exam.status === "error") return exam;
    await sleep(POLL_INTERVAL_MS);
  }
  throw new Error(
    "Exam generation is taking longer than expected. Check My Outputs shortly."
  );
}

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

    // Start generation in the background, then poll the exam's status. This
    // avoids holding a single HTTP request open for the full multi-minute LLM
    // call (which the platform may cut off).
    await apiFetch<ExamRow>(`/api/exams/${draft.id}/generate-async`, {
      method: "POST",
      body: JSON.stringify({
        document_id: primaryId,
        document_ids: params.documentIds,
        spec,
      }),
    });

    const exam = await pollExamUntilDone(draft.id, 190_000);

    await refresh();
    await reload();

    if (exam.status === "error") {
      throw new Error("Exam generation failed. Please try again.");
    }
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
