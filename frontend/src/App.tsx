import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { LanguageProvider } from "./contexts/LanguageContext";
import AppShell from "./layouts/AppShell";
import { ToastHost } from "./components/droussi/ToastHost";
import LandingRoute from "./pages/routes/LandingRoute";
import LoginRoute from "./pages/routes/LoginRoute";
import DashboardRoute from "./pages/routes/DashboardRoute";
import UploadRoute from "./pages/routes/UploadRoute";
import ExamRoute from "./pages/routes/ExamRoute";
import RepositoryRoute from "./pages/routes/RepositoryRoute";
import OutputsRoute from "./pages/routes/OutputsRoute";
import AdminRoute from "./pages/routes/AdminRoute";
import DocumentView from "./pages/DocumentView";
import ExamBuilder from "./pages/ExamBuilder";
import ExamView from "./pages/ExamView";

function Protected({ children }: { children: JSX.Element }) {
  const { session, loading } = useAuth();
  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#ebf5ff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#93979f",
          fontFamily: "'Geist','Inter',sans-serif",
        }}
      >
        Loading…
      </div>
    );
  }
  if (!session) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <LanguageProvider>
    <ToastHost />
    <Routes>
      <Route path="/" element={<LandingRoute />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        <Route path="/dashboard" element={<DashboardRoute />} />
        <Route path="/upload" element={<UploadRoute />} />
        <Route path="/exam" element={<ExamRoute />} />
        <Route path="/repository" element={<RepositoryRoute />} />
        <Route path="/outputs" element={<OutputsRoute />} />
        <Route path="/admin" element={<AdminRoute />} />
        <Route path="/documents/:id" element={<DocumentView />} />
        <Route path="/documents/:id/build" element={<ExamBuilder />} />
        <Route path="/exams/:id" element={<ExamView />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </LanguageProvider>
  );
}
