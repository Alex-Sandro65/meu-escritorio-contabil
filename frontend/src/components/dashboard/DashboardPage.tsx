import { useQuery } from '@tanstack/react-query'
import { dashboardAPI } from '../../services/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'

const CORES = ['#2563eb', '#16a34a', '#dc2626', '#f59e0b', '#7c3aed']

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-resumo'],
    queryFn: () => dashboardAPI.resumo().then(r => r.data),
    refetchInterval: 30_000,
  })

  if (isLoading) return <Skeleton />

  const d = data || {}

  const pieData = [
    { name: 'Aprovadas', value: d.conciliacoes?.aprovadas || 0 },
    { name: 'Concluídas', value: d.conciliacoes?.concluidas || 0 },
    { name: 'Com Divergência', value: d.conciliacoes?.com_divergencia || 0 },
    { name: 'Pendentes', value: d.conciliacoes?.pendentes || 0 },
  ]

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard Executivo</h1>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Empresas Ativas"
          value={d.total_empresas || 0}
          cor="blue"
          icone="🏢"
        />
        <KpiCard
          label="Score Médio Conciliação"
          value={`${(d.score_medio_conciliacao || 0).toFixed(1)}%`}
          cor={d.score_medio_conciliacao >= 90 ? 'green' : 'yellow'}
          icone="✅"
        />
        <KpiCard
          label="Diferenças Identificadas"
          value={formatCurrency(d.total_diferencas || 0)}
          cor="red"
          icone="⚠️"
        />
        <KpiCard
          label="Balancetes Concluídos"
          value={d.balancetes?.concluidos || 0}
          cor="green"
          icone="📊"
        />
      </div>

      {/* Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow p-4">
          <h2 className="text-lg font-semibold mb-4 text-gray-700">Status dos Balancetes</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={[
              { name: 'Concluídos', qtd: d.balancetes?.concluidos || 0 },
              { name: 'Em Andamento', qtd: d.balancetes?.em_andamento || 0 },
              { name: 'Com Erro', qtd: d.balancetes?.com_erro || 0 },
            ]}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="qtd" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl shadow p-4">
          <h2 className="text-lg font-semibold mb-4 text-gray-700">Conciliações por Status</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {pieData.map((_, i) => <Cell key={i} fill={CORES[i]} />)}
              </Pie>
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Score indicador */}
      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-lg font-semibold mb-2 text-gray-700">Nível de Conciliação Geral</h2>
        <div className="w-full bg-gray-200 rounded-full h-6">
          <div
            className="h-6 rounded-full transition-all duration-500 flex items-center justify-end pr-2"
            style={{
              width: `${Math.min(d.score_medio_conciliacao || 0, 100)}%`,
              backgroundColor: d.score_medio_conciliacao >= 90 ? '#16a34a' : d.score_medio_conciliacao >= 70 ? '#f59e0b' : '#dc2626'
            }}
          >
            <span className="text-white text-sm font-bold">
              {(d.score_medio_conciliacao || 0).toFixed(1)}%
            </span>
          </div>
        </div>
        <p className="text-sm text-gray-500 mt-1">
          Meta: 95% · Crítico: abaixo de 70%
        </p>
      </div>
    </div>
  )
}

function KpiCard({ label, value, cor, icone }: any) {
  const cores: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-200 text-blue-800',
    green: 'bg-green-50 border-green-200 text-green-800',
    red: 'bg-red-50 border-red-200 text-red-800',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  }
  return (
    <div className={`border rounded-xl p-4 ${cores[cor] || cores.blue}`}>
      <div className="text-2xl mb-1">{icone}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm mt-1 opacity-80">{label}</div>
    </div>
  )
}

function formatCurrency(v: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
}

function Skeleton() {
  return (
    <div className="p-6 grid grid-cols-4 gap-4">
      {[1, 2, 3, 4].map(i => (
        <div key={i} className="h-24 bg-gray-200 rounded-xl animate-pulse" />
      ))}
    </div>
  )
}
