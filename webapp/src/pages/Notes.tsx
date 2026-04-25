import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Plus, Mic } from 'lucide-react'
import { GiQuillInk as NotebookPen } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
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
        <Button
          variant="primary"
          size="md"
          fullWidth
          onClick={() => {
            setEditNote(null)
            setMode('add')
          }}
          icon={<Plus size={16} />}
          haptic="medium"
        >
          {t('character.notes.new')}
        </Button>
        <Button
          variant="arcane"
          size="md"
          onClick={() => setMode('record')}
          icon={<Mic size={16} />}
          haptic="medium"
          aria-label={t('character.notes.record_voice')}
        />
      </div>

      {notes.length === 0 && (
        <Surface variant="flat" className="text-center py-8">
          <NotebookPen className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('common.none')}</p>
        </Surface>
      )}

      <ScrollArea>
        <div className="space-y-2">
          {textNotes.map((note, idx) => (
            <m.div
              key={note.title}
              initial={{ opacity: 0, rotate: idx % 2 === 0 ? -0.6 : 0.6, y: 8 }}
              animate={{ opacity: 1, rotate: idx % 2 === 0 ? -0.5 : 0.5, y: 0 }}
              transition={{ delay: idx * 0.03, duration: 0.25 }}
            >
              <NoteItem
                note={note}
                onEdit={startEdit}
                onDelete={(title) => setDeleteTarget(title)}
                voiceUrl={(filename) => api.notes.voiceUrl(charId, filename)}
              />
            </m.div>
          ))}

          {voiceNotes.map((note, idx) => (
            <m.div
              key={note.title}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: (textNotes.length + idx) * 0.03 }}
            >
              <NoteItem
                note={note}
                onDelete={(title) => setDeleteTarget(title)}
                voiceUrl={(filename) => api.notes.voiceUrl(charId, filename)}
              />
            </m.div>
          ))}
        </div>
      </ScrollArea>

      <Sheet
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        centered
        title={t('common.confirm')}
      >
        <div className="p-5 space-y-3">
          <p className="text-sm text-center text-dnd-text font-body">
            {deleteTarget && t('character.notes.delete_confirm', { title: deleteTarget })}
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              fullWidth
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
              loading={deleteMutation.isPending}
              haptic="error"
            >
              {t('common.delete')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setDeleteTarget(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}
