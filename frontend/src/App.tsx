import type { ReactNode } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import Layout from "@/components/Layout";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import TopicsPage from "@/pages/TopicsPage";
import ProjectsPage from "@/pages/ProjectsPage";
import ProjectDetailPage from "@/pages/ProjectDetailPage";
import PerformancePage from "@/pages/PerformancePage";
import { StyleLibraryPage } from "@/pages/StyleLibraryPage";
import AICallRecordsPage from "@/pages/AICallRecordsPage";
import AIModelSettingsPage from "@/pages/AIModelSettingsPage";
import LoginPage from "@/pages/LoginPage";
import UsersPage from "@/pages/UsersPage";

const queryClient = new QueryClient();

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        正在加载…
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter
          future={{
            v7_startTransition: true,
            v7_relativeSplatPath: true,
          }}
        >
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<Navigate to="/topics" replace />} />
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/topics" element={<TopicsPage />} />
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/projects/:id" element={<ProjectDetailPage />} />
              <Route
                path="/projects/:id/performance"
                element={<PerformancePage />}
              />
              <Route path="/style-library" element={<StyleLibraryPage />} />
              <Route path="/ai-model-settings" element={<AIModelSettingsPage />} />
              <Route path="/ai-calls" element={<AICallRecordsPage />} />
              <Route path="/users" element={<UsersPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      <Toaster position="top-center" richColors />
    </QueryClientProvider>
  );
}
