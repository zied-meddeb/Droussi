import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useUserData } from "../../hooks/useUserData";
import { OutputManager } from "../../components/droussi/OutputManager";
import { apiFetch } from "../../lib/api";
import { examToOutput } from "../../lib/droussiData";

export default function OutputsRoute() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { readyExams } = useUserData();

  if (!user) return null;

  const generatedExams = readyExams.map((e) => examToOutput(e));

  return (
    <OutputManager
      generatedExams={generatedExams}
      onDownload={async (examId, format) => {
        const { url } = await apiFetch<{ url: string }>(`/api/exams/${examId}/download?format=${format}`);
        window.open(url, "_blank");
      }}
      onPreview={(examId) => navigate(`/exams/${examId}`)}
    />
  );
}
