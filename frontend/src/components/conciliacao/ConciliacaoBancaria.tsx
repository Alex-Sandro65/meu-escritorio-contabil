import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { conciliacaoAPI } from '../../services/api'
import toast from 'react-hot-toast'

interface Props {
  balanceteId: string
  contaId: string
  nomeConta?: string
}

export default function ConciliacaoBancaria({ balanceteId, contaId, nomeConta }: Props) {
  const [extrato, setExtrato] = useState<File | null>(null)
  const [resultado, setResultado] = useState<any>(null)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => files[0] && setExtrato(files[0]),
    accept: { 'text/plain': ['.ofx'], 'text/csv': ['.csv'], 'application/pdf': ['.pdf'] },
    maxFiles: 1,
  })

  const mutation = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('balancete_id', balanceteId)
      fd.append('conta_id', contaId)
      fd.append('extrato', extrato!)
      return conciliacaoAPI.bancaria(fd).then(r => r.data)
    },
    onSuccess: (data) => {
      setResultado(data)
      toast.success(`Conciliação concluída! Score: ${data.score_geral.toFixed(1)}%`)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Erro na conciliação'),
  })

  const fmt = (v: number) =>
    new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Conciliação Bancária</h2>
        {nomeConta && <p className="text-sm text-gray-500 mb-4">{nomeConta}</p>}

        {/* Upload Extrato */}
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer mb-4 ${
            isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
          }`}
        >
          <input {...getInputProps()} />
          {extrato ? (
            <div className="flex items-center justify-center gap-2">
              <span className="text-2xl">📑</span>
              <span className="font-medium">{extrato.name}</span>
              <button type="button" onClick={e => { e.stopPropagation(); setExtrato(null) }}
                className="text-red-500 ml-2">✕</button>
            </div>
          ) : (
            <div>
              <span className="text-3xl">🏦</span>
              <p className="mt-2 text-gray-600">Arraste o extrato bancário</p>
              <p className="text-xs text-gray-400">OFX · CSV · PDF</p>
            </div>
          )}
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={!extrato || mutation.isPending}
          className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? '⏳ Conciliando...' : '🔍 Iniciar Conciliação Automática'}
        </button>
      </div>

      {/* Resultado */}
      {resultado && (
        <div className="space-y-4">
          {/* Score Geral */}
          <div className="bg-white rounded-xl shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Resultado da Conciliação</h3>
              <ScoreGrande score={resultado.score_geral} />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatBox label="Pares Encontrados" value={resultado.total_pares} cor="blue" />
              <StatBox label="Automáticos" value={resultado.conciliados_automaticamente} cor="green" />
              <StatBox label="Revisão Manual" value={resultado.requerem_revisao_manual} cor="yellow" />
              <StatBox label="Não Conciliados" value={resultado.nao_conciliados_contabil} cor="red" />
            </div>
          </div>

          {/* Alertas IA */}
          {resultado.alertas?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <h4 className="font-semibold text-amber-800 mb-2">⚠️ Alertas da IA</h4>
              <ul className="space-y-1">
                {resultado.alertas.map((a: string, i: number) => (
                  <li key={i} className="text-sm text-amber-700">• {a}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Pares */}
          <div className="bg-white rounded-xl shadow overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
              <h4 className="font-semibold text-gray-700">Pares de Conciliação</h4>
              <span className="text-sm text-gray-500">{resultado.pares?.length} registros</span>
            </div>
            <table className="w-full text-xs">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2 text-gray-600">Data Contábil</th>
                  <th className="text-left px-3 py-2 text-gray-600">Histórico</th>
                  <th className="text-right px-3 py-2 text-gray-600">Valor</th>
                  <th className="text-left px-3 py-2 text-gray-600">Data Extrato</th>
                  <th className="text-left px-3 py-2 text-gray-600">Descrição Extrato</th>
                  <th className="text-center px-3 py-2 text-gray-600">Score</th>
                  <th className="text-center px-3 py-2 text-gray-600">Tipo</th>
                </tr>
              </thead>
              <tbody>
                {resultado.pares?.map((par: any, i: number) => (
                  <tr key={i} className={`border-b ${par.manual ? 'bg-yellow-50' : 'hover:bg-gray-50'}`}>
                    <td className="px-3 py-2 font-mono">{par.contabil.data}</td>
                    <td className="px-3 py-2 max-w-xs truncate">{par.contabil.descricao}</td>
                    <td className="px-3 py-2 text-right font-medium">{fmt(par.contabil.valor)}</td>
                    <td className="px-3 py-2 font-mono">{par.extrato.data}</td>
                    <td className="px-3 py-2 max-w-xs truncate text-gray-500">{par.extrato.descricao}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                        par.score >= 95 ? 'bg-green-100 text-green-700' :
                        par.score >= 70 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>{par.score.toFixed(0)}%</span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      {par.manual
                        ? <span className="bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded text-xs">Manual</span>
                        : <span className="bg-green-100 text-green-700 px-1.5 py-0.5 rounded text-xs">Auto</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreGrande({ score }: { score: number }) {
  const cor = score >= 90 ? '#16a34a' : score >= 70 ? '#f59e0b' : '#dc2626'
  return (
    <div className="text-center">
      <div className="text-3xl font-bold" style={{ color: cor }}>{score.toFixed(1)}%</div>
      <div className="text-xs text-gray-500">Score de Conciliação</div>
    </div>
  )
}

function StatBox({ label, value, cor }: any) {
  const cores: Record<string, string> = {
    blue: 'text-blue-700 bg-blue-50',
    green: 'text-green-700 bg-green-50',
    yellow: 'text-yellow-700 bg-yellow-50',
    red: 'text-red-700 bg-red-50',
  }
  return (
    <div className={`rounded-lg p-3 text-center ${cores[cor]}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs mt-0.5">{label}</div>
    </div>
  )
}
