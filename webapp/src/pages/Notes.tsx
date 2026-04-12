import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

type Mode = 'list' | 'add' | 'edit'

export default function Notes() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [mode, setMode] = useState<Mode>('list')
  const [editTitle, setEditTitle] = useState('')
  const [editBody, setEditBody] = useState('')
  const [originalTitle, setOriginalTitle] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const { data: notes = [] } = useQuery({
    queryKey: ['notes', charId],
    queryFn: () => api.notes.list(charId),
  })

  const addMutation = useMutation({
    mutationFn: () => api.notes.add(charId, editTitle.trim(), editBody.trim()),
    onSuccess: (updated) => {
      qc.setQueryData(['notes', charId], updated)
      setMode('list')
      setEditTitle('')
      setEditBody('')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: () => api.notes.update(charId, originalTitle, editBody.trim()),
    onSuccess: (updated) => {
      qc.setQueryData(['notes', charId], updated)
      setMode('list')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const deleteMutation = useMutation({
    mutationFn: (title: string) => api.notes.remove(charId, title),
    onSuccess: (updated) => {
      qc.setQueryData(['notes', charId], updated)
      setDeleteTarget(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const startEdit = (title: string, body: string) => {
    setOriginalTitle(title)
    setEditTitle(title)
    setEditBody(body)
    setMode('edit')
  }

  const startAdd = () => {
    setEditTitle('')
    setEditBody('')
    setMode('add')
  }

  if (mode === 'add' || mode === 'edit') {
    const isEdit = mode === 'edit'
    const mutation = isEdit ? updateMutation : addMutation
    return (
      <Layout title={isEdit ? t('common.edit') : t('character.notes.new')} backTo={undefined}>
        <div className="space-y-3">
          {!isEdit && (
            <div>
              <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">{t('character.notes.title_label')}</p>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                placeholder={t('character.notes.title_placeholder')}
                className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none
                           focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
              />
            </div>
          )}
          <div>
            <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">{t('character.notes.body_label')}</p>
            <textarea
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
              placeholder={t('character.notes.body_placeholder')}
              rows={10}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none resize-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || (!isEdit && !editTitle.trim())}
              className="flex-1 py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
            >
              {mutation.isPending ? '...' : t('common.save')}
            </button>
            <button
              onClick={() => setMode('list')}
              className="flex-1 py-3 rounded-2xl bg-white/10 font-medium"
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout title={t('character.notes.title')} backTo={`/char/${charId}`}>
      <button
        onClick={startAdd}
        className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                   text-[var(--tg-theme-button-text-color)] font-semibold active:opacity-80"
      >
        + {t('character.notes.new')}
      </button>

      {notes.length === 0 && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      )}

      <div className="space-y-2">
        {notes.filter((n) => !n.is_voice).map((note) => (
          <Card key={note.title}>
            <div className="flex items-start justify-between gap-2 mb-1">
              <h3 className="font-semibold">{note.title}</h3>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => startEdit(note.title, note.body)}
                  className="text-xs text-[var(--tg-theme-link-color)]"
                >
                  {t('common.edit')}
                </button>
                <button
                  onClick={() => setDeleteTarget(note.title)}
                  className="text-xs text-red-400"
                >
                  {t('common.delete')}
                </button>
              </div>
            </div>
            <p className="text-sm text-[var(--tg-theme-hint-color)] whitespace-pre-wrap line-clamp-3">
              {note.body}
            </p>
          </Card>
        ))}

        {notes.filter((n) => n.is_voice).map((note) => (
          <Card key={note.title}>
            <div className="flex items-center gap-2">
              <span>🎤</span>
              <span className="text-sm text-[var(--tg-theme-hint-color)]">
                {t('character.notes.voice')}
              </span>
            </div>
          </Card>
        ))}
      </div>

      {deleteTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">Eliminare "{deleteTarget}"?</p>
            <div className="flex gap-2">
              <button
                onClick={() => deleteMutation.mutate(deleteTarget)}
                className="flex-1 py-2 rounded-xl bg-red-500/80 text-white font-medium"
              >
                {t('common.delete')}
              </button>
              <button
                onClick={() => setDeleteTarget(null)}
                className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
              >
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}
