import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/useAuthStore'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

// Lazy load heavy pages
const KnowledgeList = React.lazy(() => import('./pages/knowledge/KnowledgeList'))
const KnowledgeDetail = React.lazy(() => import('./pages/knowledge/KnowledgeDetail'))
const RagChat = React.lazy(() => import('./pages/chat/RagChat'))
const SmartQuery = React.lazy(() => import('./pages/chat/SmartQuery'))
const DataSourceList = React.lazy(() => import('./pages/data/DataSourceList'))
const Terminology = React.lazy(() => import('./pages/data/Terminology'))
const SqlExamples = React.lazy(() => import('./pages/data/SqlExamples'))
const AuditLog = React.lazy(() => import('./pages/admin/AuditLog'))

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <MainLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="knowledge" element={<KnowledgeList />} />
          <Route path="knowledge/:id" element={<KnowledgeDetail />} />
          <Route path="chat/rag" element={<RagChat />} />
          <Route path="chat/query" element={<SmartQuery />} />
          <Route path="data/datasources" element={<DataSourceList />} />
          <Route path="data/terminology" element={<Terminology />} />
          <Route path="data/sql-examples" element={<SqlExamples />} />
          <Route path="admin/audit-logs" element={<AuditLog />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
