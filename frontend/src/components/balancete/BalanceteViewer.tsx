import { useQuery } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import { balanceteAPI } from '../../services/api'

interface Props { balanceteId: string }

const STATUS_COR: Record<string, string> = {
  conciliado: 'bg-green-100 text-green-700',
  pendente: 'bg-yellow-100 text-yellow-700',
  divergente: 'bg-red-100 text-red-700',
  'em_analise': 'bg-blue-100 text-blue-700',
}

const STATUS_LABEL: Record<string, string> = {
  conciliado: '✅ Conciliado',
  pendente: '⏳ Pendente',
  divergente: '⚠️ Divergente',
  'em_analise': '🔍 Em Análise',
}

export default function BalanceteViewer({ balanceteId }: Props) {
  const [busca, setBusca] = useState('')
  const [filtroStatus, setFiltroStatus] = useState('todos')
  const [expandido, setExpandido] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['balancete', balanceteId],
    queryFn: () => balanceteAPI.get(balanceteId).then(r => r.data),
  })

  const itensFiltrados = useMemo(() => {
    if (!data?.itens) return []
    return data.itens.filter((item: any) => {
      const matchBusca =
        !busca ||
        item.codigo.includes(busca) ||
        item.descricao.toLowerCase().includes(busca.toLowerCase())
      const matchStatus =
        filtroStatus === 'todos' || item.status === filtroStatus
      return matchBusca && matchStatus
    })
  }, [data?.itens, busca, filtroStatus])

  if (isLoading) return <div className="p-6 animate-pulse text-gray-400">Carregando balancete...</div>

  const fmt = (v: number) =>
    new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

  const pct = data?.percentual_conciliado || 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-xl shadow p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">
            Balancete — {data?.competencia}
          </h2>
          <p className="text-sm text-gray-500">{data?.total_contas} contas · {pct.toFixed(1)}% conciliado</p>
        </div>
        <div className="w-48">
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="h-3 rounded-full"
              style={{
                width: `${Math.min(pct, 100)}%`,
                backgroundColor: pct >= 90 ? '#16a34a' : pct >= 70 ? '#f59e0b' : '#dc2626'
              }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-0.5 text-right">{pct.toFixed(2)}%</p>
        </div>
      </div>

      {/* Filtros */}
      <div className="bg-white rounded-xl shadow p-3 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Buscar por código ou descrição..."
          value={busca}
          onChange={e => setBusca(e.target.value)}
          className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none min-w-48"
        />
        <select
          value={filtroStatus}
          onChange={e => setFiltroStatus(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
        >
          <option value="todos">Todos os status</option>
          <option value="pendente">Pendentes</option>
          <option value="conciliado">Conciliados</option>
          <option value="divergente">Divergentes</option>
        </select>
        <span className="text-sm text-gray-500 self-center">
          {itensFiltrados.length} contas
        </span>
      </div>

      {/* Tabela */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-gray-600 w-32">Código</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Descrição</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Saldo Anterior</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Débitos</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Créditos</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Saldo Atual</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Diferença</th>
              <th className="text-center px-4 py-3 font-semibold text-gray-600">Score</th>
              <th className="text-center px-4 py-3 font-semibold text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody>
            {itensFiltrados.map((item: any) => (
              <>
                <tr
                  key={item.id}
                  className={`border-b hover:bg-gray-50 cursor-pointer ${
                    item.nivel <= 2 ? 'bg-gray-50 font-medium' : ''
                  }`}
                  onClick={() => setExpandido(expandido === item.id ? null : item.id)}
                >
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-600"
                    style={{ paddingLeft: `${(item.nivel - 1) * 16 + 16}px` }}>
                    {item.codigo}
                  </td>
                  <td className="px-4 py-2.5 text-gray-800">{item.descricao}</td>
                  <td className="px-4 py-2.5 text-right text-gray-600">{fmt(item.saldo_anterior)}</td>
                  <td className="px-4 py-2.5 text-right text-blue-600">{fmt(item.debitos)}</td>
                  <td className="px-4 py-2.5 text-right text-purple-600">{fmt(item.creditos)}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-gray-800">{fmt(item.saldo_atual)}</td>
                  <td className={`px-4 py-2.5 text-right font-medium ${
                    item.diferenca && item.diferenca !== 0 ? 'text-red-600' : 'text-gray-400'
                  }`}>
                    {item.diferenca != null ? fmt(item.diferenca) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {item.score != null ? (
                      <ScoreBadge score={item.score} />
                    ) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COR[item.status] || 'bg-gray-100 text-gray-600'}`}>
                      {STATUS_LABEL[item.status] || item.status}
                    </span>
                  </td>
                </tr>
                {expandido === item.id && item.alertas_ia?.length > 0 && (
                  <tr key={`${item.id}-alertas`}>
                    <td colSpan={9} className="px-4 py-3 bg-amber-50 border-b">
                      <div className="space-y-1">
                        {item.alertas_ia.map((alerta: string, i: number) => (
                          <p key={i} className="text-xs text-amber-700 flex items-start gap-1">
                            <span>⚠️</span> {alerta}
                          </p>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>

        {itensFiltrados.length === 0 && (
          <div className="py-12 text-center text-gray-400">
            Nenhuma conta encontrada com os filtros aplicados.
          </div>
        )}
      </div>
    </div>
  )
}

function ScoreBadge({ score }: { score: number }) {
  const cor =
    score >= 95 ? 'text-green-600 bg-green-50' :
    score >= 70 ? 'text-yellow-600 bg-yellow-50' :
    'text-red-600 bg-red-50'
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono font-bold ${cor}`}>
      {score.toFixed(0)}%
    </span>
  )
}
