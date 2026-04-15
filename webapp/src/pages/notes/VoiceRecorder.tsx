import { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'

interface VoiceRecorderProps {
  onRecordComplete: (blob: Blob, title: string) => void
  onCancel: () => void
  isPending: boolean
}

export default function VoiceRecorder({ onRecordComplete, onCancel, isPending }: VoiceRecorderProps) {
  const { t } = useTranslation()

  const [voiceTitle, setVoiceTitle] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [recordingDuration, setRecordingDuration] = useState(0)
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [micError, setMicError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

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

  const handleSave = () => {
    if (voiceTitle.trim() && recordedBlob) {
      onRecordComplete(recordedBlob, voiceTitle.trim())
    }
  }

  const handleCancel = () => {
    stopRecording()
    onCancel()
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
          {t('character.notes.title_label')}
        </p>
        <input
          type="text"
          value={voiceTitle}
          onChange={(e) => setVoiceTitle(e.target.value)}
          placeholder={t('character.notes.title_placeholder')}
          className="w-full bg-dnd-surface rounded-xl px-3 py-2 outline-none
                     border border-transparent focus:border-dnd-gold-dim
                     focus:shadow-[0_0_0_2px_var(--dnd-gold-glow)]"
        />
      </div>

      {micError && (
        <p className="text-sm text-[var(--dnd-danger)] bg-[var(--dnd-danger)]/10 rounded-xl px-3 py-2">
          {micError}
        </p>
      )}

      <Card className="text-center space-y-4">
        {/* Duration display */}
        <p className={`text-4xl font-mono font-bold ${isRecording ? 'text-[var(--dnd-danger)]' : ''}`}>
          {formatDuration(recordingDuration)}
        </p>

        {/* Recording indicator */}
        {isRecording && (
          <div className="flex items-center justify-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[var(--dnd-danger)] animate-pulse" />
            <span className="text-sm text-[var(--dnd-danger)]">{t('character.notes.recording')}</span>
          </div>
        )}

        {/* Record / Stop buttons */}
        <div className="flex justify-center gap-4">
          {!isRecording && !recordedBlob && (
            <button
              onClick={startRecording}
              className="w-16 h-16 rounded-full bg-[var(--dnd-danger)] flex items-center justify-center
                         active:opacity-70 transition-opacity"
            >
              <span className="text-2xl">🎤</span>
            </button>
          )}
          {isRecording && (
            <button
              onClick={stopRecording}
              className="w-16 h-16 rounded-full bg-[var(--dnd-danger)]/30 border-2 border-[var(--dnd-danger)]
                         flex items-center justify-center active:opacity-70"
            >
              <span className="w-6 h-6 rounded bg-[var(--dnd-danger)]" />
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
              className="text-xs text-dnd-text-secondary"
            >
              {t('character.notes.discard_recording')}
            </button>
          </div>
        )}
      </Card>

      <div className="flex gap-2">
        <DndButton
          onClick={handleSave}
          disabled={!voiceTitle.trim() || !recordedBlob || isPending}
          loading={isPending}
          className="flex-1"
        >
          {t('common.save')}
        </DndButton>
        <DndButton
          variant="secondary"
          onClick={handleCancel}
          className="flex-1"
        >
          {t('common.cancel')}
        </DndButton>
      </div>
    </div>
  )
}
