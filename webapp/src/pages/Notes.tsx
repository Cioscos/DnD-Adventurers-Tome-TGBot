import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

type Mode = 'list' | 'add' | 'edit' | 'record'

/** Extract filename from "[VOICE:data/voice_notes/123/abc.webm]" */
function extractVoiceFilename(body: string): string | null {
  const match = body.match(/^\[VOICE:(.+)\]$/)
  if (!match) return null
  const path = match[1]
  if (path === 'unavailable') return null
  const parts = path.split('/')
  return parts[parts.length - 1]
}

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

  // Voice recording state
  const [voiceTitle, setVoiceTitle] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [recordingDuration, setRecordingDuration] = useState(0)
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [micError, setMicError] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

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

  const voiceUploadMutation = useMutation({
    mutationFn: () => api.notes.uploadVoice(charId, voiceTitle.trim(), recordedBlob!),
    onSuccess: (updated) => {
      qc.setQueryData(['notes', charId], updated)
      setMode('list')
      setVoiceTitle('')
      setRecordedBlob(null)
      setRecordingDuration(0)
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

  const startRecord = () => {
    setVoiceTitle('')
    setRecordedBlob(null)
    setRecordingDuration(0)
    setMicError(null)
    setMode('record')
  }

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setRecordedBlob(blob)
        stream.getTracks().forEach((track) => track.stop())
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setIsRecording(true)
      setRecordingDuration(0)
      timerRef.current = setInterval(() => {
        setRecordingDuration((d) => d + 1)
      }, 1000)
    } catch {
      setMicError(t('character.notes.mic_denied'))
    }
  }, [t])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    setIsRecording(false)
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  // Voice recording mode
  if (mode === 'record') {
    return (
      <Layout title={t('character.notes.record_voice')} backTo={undefined}>
        <div className="space-y-3">
          <div>
            <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">{t('character.notes.title_label')}</p>
            <input
              type="text"
              value={voiceTitle}
              onChange={(e) => setVoiceTitle(e.target.value)}
              placeholder={t('character.notes.title_placeholder')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
          </div>

          {micError && (
            <p className="text-sm text-red-400 bg-red-500/10 rounded-xl px-3 py-2">{micError}</p>
          )}

          <Card className="text-center space-y-4">
            {/* Duration display */}
            <p className={`text-4xl font-mono font-bold ${isRecording ? 'text-red-400' : ''}`}>
              {formatDuration(recordingDuration)}
            </p>

            {/* Recording indicator */}
            {isRecording && (
              <div className="flex items-center justify-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
                <span className="text-sm text-red-400">{t('character.notes.recording')}</span>
              </div>
            )}

            {/* Record / Stop buttons */}
            <div className="flex justify-center gap-4">
              {!isRecording && !recordedBlob && (
                <button
                  onClick={startRecording}
                  className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center
                             active:opacity-70 transition-opacity"
                >
                  <span className="text-2xl">🎤</span>
                </button>
              )}
              {isRecording && (
                <button
                  onClick={stopRecording}
                  className="w-16 h-16 rounded-full bg-red-500/30 border-2 border-red-500
                             flex items-center justify-center active:opacity-70"
                >
                  <span className="w-6 h-6 rounded bg-red-500" />
                </button>
              )}
            </div>

            {/* Preview playback */}
            {recordedBlob && !isRecording && (
              <div className="space-y-2">
                <audio
                  controls
                  src={URL.createObjectURL(recordedBlob)}
                  className="w-full"
                />
                <button
                  onClick={() => {
                    setRecordedBlob(null)
                    setRecordingDuration(0)
                  }}
                  className="text-xs text-[var(--tg-theme-hint-color)]"
                >
                  {t('character.notes.discard_recording')}
                </button>
              </div>
            )}
          </Card>

          <div className="flex gap-2">
            <button
              onClick={() => voiceUploadMutation.mutate()}
              disabled={!voiceTitle.trim() || !recordedBlob || voiceUploadMutation.isPending}
              className="flex-1 py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
            >
              {voiceUploadMutation.isPending ? '...' : t('common.save')}
            </button>
            <button
              onClick={() => {
                stopRecording()
                setMode('list')
              }}
              className="flex-1 py-3 rounded-2xl bg-white/10 font-medium"
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      </Layout>
    )
  }

  // Add / Edit text note mode
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

  const textNotes = notes.filter((n) => !n.is_voice)
  const voiceNotes = notes.filter((n) => n.is_voice)

  return (
    <Layout title={t('character.notes.title')} backTo={`/char/${charId}`}>
      <div className="flex gap-2">
        <button
          onClick={startAdd}
          className="flex-1 py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                     text-[var(--tg-theme-button-text-color)] font-semibold active:opacity-80"
        >
          + {t('character.notes.new')}
        </button>
        <button
          onClick={startRecord}
          className="py-3 px-4 rounded-2xl bg-red-500/20 text-red-300 font-semibold active:opacity-80"
        >
          🎤
        </button>
      </div>

      {notes.length === 0 && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      )}

      <div className="space-y-2">
        {textNotes.map((note) => (
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

        {voiceNotes.map((note) => {
          const filename = extractVoiceFilename(note.body)
          return (
            <Card key={note.title}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="font-semibold">🎤 {note.title}</h3>
                <button
                  onClick={() => setDeleteTarget(note.title)}
                  className="text-xs text-red-400 shrink-0"
                >
                  {t('common.delete')}
                </button>
              </div>
              {filename ? (
                <audio
                  controls
                  src={api.notes.voiceUrl(charId, filename)}
                  className="w-full"
                />
              ) : (
                <p className="text-sm text-[var(--tg-theme-hint-color)]">
                  {t('character.notes.voice')}
                </p>
              )}
            </Card>
          )
        })}
      </div>

      {deleteTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.notes.delete_confirm', { title: deleteTarget })}
            </p>
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
