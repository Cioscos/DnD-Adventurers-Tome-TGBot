import { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Mic, Square } from 'lucide-react'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Input from '@/components/ui/Input'

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
      <Input
        label={t('character.notes.title_label')}
        value={voiceTitle}
        onChange={setVoiceTitle}
        placeholder={t('character.notes.title_placeholder')}
      />

      {micError && (
        <p className="text-sm text-dnd-crimson-bright bg-dnd-crimson/10 rounded-xl px-3 py-2">
          {micError}
        </p>
      )}

      <Surface variant="flat" className="text-center space-y-4">
        {/* Duration display */}
        <p className={`text-4xl font-mono font-bold tabular-nums ${isRecording ? 'text-dnd-crimson-bright' : 'text-dnd-text'}`}>
          {formatDuration(recordingDuration)}
        </p>

        {/* Recording indicator */}
        {isRecording && (
          <div className="flex items-center justify-center gap-2">
            <span className="w-3 h-3 rounded-full bg-dnd-crimson animate-pulse" />
            <span className="text-sm text-dnd-crimson-bright">{t('character.notes.recording')}</span>
          </div>
        )}

        {/* Record / Stop buttons */}
        <div className="flex justify-center gap-4">
          {!isRecording && !recordedBlob && (
            <Pressable
              onClick={startRecording}
              aria-label={t('character.notes.record_voice')}
              className="w-16 h-16 rounded-full bg-dnd-crimson text-dnd-parchment flex items-center justify-center
                         active:opacity-70 transition-opacity"
            >
              <Mic size={28} />
            </Pressable>
          )}
          {isRecording && (
            <Pressable
              onClick={stopRecording}
              aria-label={t('character.notes.recording')}
              className="w-16 h-16 rounded-full bg-dnd-crimson/30 border-2 border-dnd-crimson text-dnd-crimson-bright
                         flex items-center justify-center active:opacity-70"
            >
              <Square size={22} fill="currentColor" />
            </Pressable>
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
            <Pressable
              onClick={() => {
                setRecordedBlob(null)
                setRecordingDuration(0)
              }}
              className="min-h-[44px] px-3 text-xs text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
            >
              {t('character.notes.discard_recording')}
            </Pressable>
          </div>
        )}
      </Surface>

      <div className="flex gap-2">
        <Button
          variant="secondary"
          onClick={handleCancel}
          fullWidth
        >
          {t('common.cancel')}
        </Button>
        <Button
          onClick={handleSave}
          disabled={!voiceTitle.trim() || !recordedBlob || isPending}
          loading={isPending}
          fullWidth
        >
          {t('common.save')}
        </Button>
      </div>
    </div>
  )
}
