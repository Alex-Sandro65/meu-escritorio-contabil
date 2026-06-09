import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { useAuthStore } from './store/authStore'
import LoginPage from './pages/LoginPage'
import DashboardPage from './components/dashboard/DashboardPage'

const qc = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

function ProtectedLayout() {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return (
    <div className="min-h-screen bg-gray-100 flex">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}

function Sidebar() {
  const { logout } = useAuthStore()
  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/balancetes', label: 'Balancetes', icon: '📋' },
    { path: '/conciliacoes', label: 'Conciliações', icon: '🔍' },
    { path: '/auditoria', label: 'Auditoria', icon: '📝' },
    { path: '/sped', label: 'SPED ECD/ECF', icon: '🗂️' },
    { path: '/relatorios', label: 'Relatórios', icon: '📑' },
    { path: '/empresas', label: 'Empresas', icon: '🏢' },
    { path: '/configuracoes', label: 'Configurações', icon: '⚙️' },
  ]

  return (
    <aside className="w-56 bg-blue-900 text-white flex flex-col min-h-screen">
      <div className="p-4 border-b border-blue-800">
        <div className="text-xl font-bold flex items-center gap-2">
          <span>📊</span> ContaMax
        </div>
        <div className="text-xs text-blue-300 mt-0.5">SaaS Contábil</div>
      </div>
      <nav className="flex-1 py-4">
        {navItems.map(item => (
          <a
            key={item.path}
            href={item.path}
            className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-blue-800 transition-colors"
          >
            <span>{item.icon}</span>
            {item.label}
          </a>
        ))}
      </nav>
      <div className="p-4 border-t border-blue-800">
        <button
          onClick={logout}
          className="w-full text-sm text-blue-300 hover:text-white transition-colors text-left"
        >
          🚪 Sair
        </button>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Toaster position="top-right" />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedLayout />}>
            <Route index element={<Navigate to="/dashboard" />} />
            <Route path="dashboard" element={<DashboardPage />} />
            {/* Rotas adicionais serão adicionadas aqui */}
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
