import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { balanceteAPI } from '../../services/api'
import toast from 'react-hot-toast'

interface Props {
  empresaId: string
  onSucesso?: (balanceteId: string) => void
}

export default function ImportarBalancete({ empresaId, onSucesso }: Props) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [competencia, setCompetencia] = useState('')
  const [dataInicial, setDataInicial] = useState('')
  const [dataFinal, setDataFinal] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('empresa_id', empresaId)
      fd.append('competencia', competencia)
      fd.append('data_inicial', dataInicial)
      fd.append('data_final', dataFinal)
      fd.append('arquivo', arquivo!)
      return balanceteAPI.importar(fd).then(r => r.data)
    },
    onSuccess: (data) => {
      toast.success(`Balancete importado! ${data.total_contas} contas processadas.`)
      qc.invalidateQueries({ queryKey: ['balancetes', empresaId] })
      onSucesso?.(data.balancete_id)
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail?.erros?.join(', ') || 'Erro ao importar balancete'
      toast.error(msg)
    },
  })

  const onDrop = useCallback((files: File[]) => {
    if (files[0]) setArquivo(files[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/csv': ['.csv'],
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt', '.sped'],
    },
    maxFiles: 1,
  })

  const handleCompetencia = (v: string) => {
    setCompetencia(v)
    if (v.length === 7) {
      const [y, m] = v.split('-')
      const ultimo = new Date(+y, +m, 0).getDate()
      setDataInicial(`${v}-01`)
      setDataFinal(`${v}-${String(ultimo).padStart(2, '0')}`)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow p-6 space-y-4">
      <h2 className="text-xl font-semibold text-gray-800">Importar Balancete</h2>

      {/* Competência */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Competência</label>
          <input
            type="month"
            value={competencia}
            onChange={e => handleCompetencia(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data Inicial</label>
          <input
            type="date"
            value={dataInicial}
            onChange={e => setDataInicial(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data Final</label>
          <input
            type="date"
            value={dataFinal}
            onChange={e => setDataFinal(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        }`}
      >
        <input {...getInputProps()} />
        {arquivo ? (
          <div className="flex items-center justify-center gap-3">
            <span className="text-3xl">📄</span>
            <div>
              <p className="font-medium text-gray-800">{arquivo.name}</p>
              <p className="text-sm text-gray-500">{(arquivo.size / 1024).toFixed(1)} KB</p>
            </div>
            <button
              type="button"
              onClick={e => { e.stopPropagation(); setArquivo(null) }}
              className="ml-4 text-red-500 hover:text-red-700 text-xl"
            >
              ✕
            </button>
          </div>
        ) : (
          <div>
            <span className="text-4xl">📂</span>
            <p className="mt-2 text-gray-600">
              {isDragActive ? 'Solte o arquivo aqui' : 'Arraste ou clique para selecionar'}
            </p>
            <p className="text-sm text-gray-400 mt-1">Excel · CSV · PDF · SPED ECD · TXT</p>
          </div>
        )}
      </div>

      {/* Formatos suportados */}
      <div className="flex flex-wrap gap-2 text-xs">
        {['SCI Único', 'SCI Visual Practice', 'Omie', 'Conta Azul', 'Excel Padrão', 'SPED ECD', 'PDF'].map(f => (
          <span key={f} className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{f}</span>
        ))}
      </div>

      <button
        onClick={() => mutation.mutate()}
        disabled={!arquivo || !competencia || mutation.isPending}
        className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {mutation.isPending ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin">⏳</span> Processando...
          </span>
        ) : (
          '🚀 Importar e Processar Balancete'
        )}
      </button>
    </div>
  )
}
