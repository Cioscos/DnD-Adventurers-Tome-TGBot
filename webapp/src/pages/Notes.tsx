import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Plus, Mic, MicOff } from 'lucide-react'
import { GiQuillInk as NotebookPen } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import ScrollArea from '@/components/ScrollArea'
import EmptyState from '@/components/ui/EmptyState'
import { haptic } from '@/auth/telegram'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import VoiceRecorder from '@/pages/notes/VoiceRecorder'
import NoteEditor from '@/pages/notes/NoteEditor'
import NoteItem from '@/pages/notes/NoteItem'
import NotesSkeleton from '@/components/skeletons/NotesSkeleton'

// "denied" → mic API exists but user/browser blocked. "missing" → no MediaRecorder
// support at all (e.g. plain http on iOS). "ready" → we can attempt recording.
type MicStatus = 'unknown' | 'ready' | 'denied' | 'missing'

type Mode = 'list' | 'add' | 'edit' | 'record'

export default function Notes() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const reduceMotion = useReducedMotion()
  const [mode, setMode] = useState<Mode>('list')
  const [editNote, setEditNote] = useState<{ title: string; body: string; tags?: string[] } | null>(null)
  const [originalTitle, setOriginalTitle] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [micStatus, setMicStatus] = useState<MicStatus>('unknown')

  useEffect(() => {
    if (typeof window === 'undefined') return
    const hasApi = !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
    if (!hasApi) {
      setMicStatus('missing')
      return
    }
    // Probe permission non-invasively when supported. Falls back to 'ready' if
    // the Permissions API doesn't know about microphone (Safari, in-app browsers).
    const perms = navigator.permissions as Permissions | undefined
    if (perms?.query) {
      perms.query({ name: 'microphone' as PermissionName }).then(
        (res) => {
          setMicStatus(res.state === 'denied' ? 'denied' : 'ready')
          res.onchange = () => setMicStatus(res.state === 'denied' ? 'denied' : 'ready')
        },
        () => setMicStatus('ready'),
      )
    } else {
      setMicStatus('ready')
    }
  }, [])

  const { data: notes = [], isLoading } = useQuery({
    queryKey: ['notes', charId],
    queryFn: () => api.notes.list(charId),
  })

  const addMutation = useMutation({
    mutationFn: ({ title, body, tags }: { title: string; body: string; tags: string[] }) =>
      api.notes.add(charId, title, body, tags),
    onSuccess: (updated) => {
      qc.setQueryData(['notes', charId], updated)
      setMode('list')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ body, tags }: { body: string; tags: string[] }) =>
      api.notes.update(charId, originalTitle, body, tags),
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

  const startEdit = (title: string, body: string, tags: string[]) => {
    setOriginalTitle(title)
    setEditNote({ title, body, tags })
    setMode('edit')
  }

  const handleEditorSave = (title: string, body: string, tags: string[]) => {
    if (mode === 'edit') {
      updateMutation.mutate({ body, tags })
    } else {
      addMutation.mutate({ title, body, tags })
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

  const isEditorOpen = mode === 'add' || mode === 'edit'
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
          variant="secondary"
          size="md"
          onClick={() => setMode('record')}
          disabled={micStatus === 'denied' || micStatus === 'missing'}
          icon={micStatus === 'denied' || micStatus === 'missing' ? <MicOff size={16} /> : <Mic size={16} />}
          haptic="medium"
          aria-label={t('character.notes.record_voice')}
          title={
            micStatus === 'missing'
              ? t('character.notes.mic_missing', { defaultValue: 'Microfono non disponibile su questo browser' })
              : micStatus === 'denied'
                ? t('character.notes.mic_denied_tooltip', { defaultValue: 'Permesso microfono negato. Abilitalo nelle impostazioni del browser.' })
                : t('character.notes.record_voice')
          }
        />
      </div>

      {!isLoading && notes.length === 0 && (
        <EmptyState
          icon={<NotebookPen size={32} />}
          title={t('common.none')}
          hint={t('character.notes.empty_hint')}
          action={{
            label: t('character.notes.new'),
            onClick: () => {
              setEditNote(null)
              setMode('add')
            },
            icon: <Plus size={14} />,
          }}
        />
      )}

      {isLoading && <NotesSkeleton />}

      <ScrollArea>
        <div className="space-y-2">
          {textNotes.map((note, idx) => (
            <m.div
              key={note.title}
              initial={{
                opacity: 0,
                rotate: reduceMotion ? 0 : (idx % 2 === 0 ? -0.3 : 0.3),
                y: 8,
              }}
              animate={{
                opacity: 1,
                rotate: reduceMotion ? 0 : (idx % 2 === 0 ? -0.25 : 0.25),
                y: 0,
              }}
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

      <Sheet
        open={isEditorOpen}
        onClose={() => setMode('list')}
        title={mode === 'edit' ? t('common.edit') : t('character.notes.new')}
      >
        <div className="p-4">
          <NoteEditor
            initialNote={mode === 'edit' ? editNote : null}
            onSave={handleEditorSave}
            onCancel={() => setMode('list')}
            isPending={mode === 'edit' ? updateMutation.isPending : addMutation.isPending}
          />
        </div>
      </Sheet>
    </Layout>
  )
}
