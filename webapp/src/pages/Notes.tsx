import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import ScrollArea from '@/components/ScrollArea'
import { haptic } from '@/auth/telegram'
import VoiceRecorder from '@/pages/notes/VoiceRecorder'
import NoteEditor from '@/pages/notes/NoteEditor'
import NoteItem from '@/pages/notes/NoteItem'

type Mode = 'list' | 'add' | 'edit' | 'record'

export default function Notes() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [mode, setMode] = useState<Mode>('list')
  const [editNote, setEditNote] = useState<{ title: string; body: string } | null>(null)
  const [originalTitle, setOriginalTitle] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const { data: notes = [] } = useQuery({
    queryKey: ['notes', charId],
    queryFn: () => api.notes.list(charId),
  })

  const addMutation = useMutation({
    mutationFn: ({ title, body }: { title: string; body: string }) =>
      api.notes.add(charId, title, body),
    onSuccess: (updated) => {
      qc.setQueryData(['notes', charId], updated)
      setMode('list')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ body }: { body: string }) =>
      api.notes.update(charId, originalTitle, body),
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

  const voiceUploadMutation = useMutation({
    mutationFn: ({ blob, title }: { blob: Blob; title: string }) =>
      api.notes.uploadVoice(charId, title, blob),
    onSuccess: (updated) => {
      qc.setQueryData(['notes', charId], updated)
      setMode('list')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const startEdit = (title: string, body: string) => {
    setOriginalTitle(title)
    setEditNote({ title, body })
    setMode('edit')
  }

  const handleEditorSave = (title: string, body: string) => {
    if (mode === 'edit') {
      updateMutation.mutate({ body })
    } else {
      addMutation.mutate({ title, body })
    }
  }

  const handleVoiceComplete = (blob: Blob, title: string) => {
    voiceUploadMutation.mutate({ blob, title })
  }

  // Voice recording mode
  if (mode === 'record') {
    return (
      <Layout title={t('character.notes.record_voice')} backTo={undefined} group="tools" page="notes">
        <VoiceRecorder
          onRecordComplete={handleVoiceComplete}
          onCancel={() => setMode('list')}
          isPending={voiceUploadMutation.isPending}
        />
      </Layout>
    )
  }

  // Add / Edit text note mode
  if (mode === 'add' || mode === 'edit') {
    const isEdit = mode === 'edit'
    return (
      <Layout
        title={isEdit ? t('common.edit') : t('character.notes.new')}
        backTo={undefined}
        group="tools"
        page="notes"
      >
        <NoteEditor
          initialNote={isEdit ? editNote : null}
          onSave={handleEditorSave}
          onCancel={() => setMode('list')}
          isPending={isEdit ? updateMutation.isPending : addMutation.isPending}
        />
      </Layout>
    )
  }

  const textNotes = notes.filter((n) => !n.is_voice)
  const voiceNotes = notes.filter((n) => n.is_voice)

  return (
    <Layout title={t('character.notes.title')} backTo={`/char/${charId}`} group="tools" page="notes">
      <div className="flex gap-2">
        <DndButton
          onClick={() => {
            setEditNote(null)
            setMode('add')
          }}
          className="flex-1"
        >
          + {t('character.notes.new')}
        </DndButton>
        <DndButton
          variant="danger"
          onClick={() => setMode('record')}
          className="!px-4"
        >
          🎤
        </DndButton>
      </div>

      {notes.length === 0 && (
        <Card>
          <p className="text-center text-dnd-text-secondary">{t('common.none')}</p>
        </Card>
      )}

      <ScrollArea>
        <div className="space-y-2">
          {textNotes.map((note) => (
            <NoteItem
              key={note.title}
              note={note}
              onEdit={startEdit}
              onDelete={(title) => setDeleteTarget(title)}
              voiceUrl={(filename) => api.notes.voiceUrl(charId, filename)}
            />
          ))}

          {voiceNotes.map((note) => (
            <NoteItem
              key={note.title}
              note={note}
              onDelete={(title) => setDeleteTarget(title)}
              voiceUrl={(filename) => api.notes.voiceUrl(charId, filename)}
            />
          ))}
        </div>
      </ScrollArea>

      {deleteTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.notes.delete_confirm', { title: deleteTarget })}
            </p>
            <div className="flex gap-2">
              <DndButton
                variant="danger"
                onClick={() => deleteMutation.mutate(deleteTarget)}
                loading={deleteMutation.isPending}
                className="flex-1"
              >
                {t('common.delete')}
              </DndButton>
              <DndButton
                variant="secondary"
                onClick={() => setDeleteTarget(null)}
                className="flex-1"
              >
                {t('common.cancel')}
              </DndButton>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}
