import React from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import type { Note } from '@/types'

/** Extract filename from "[VOICE:data/voice_notes/123/abc.webm]" */
function extractVoiceFilename(body: string): string | null {
  const match = body.match(/^\[VOICE:(.+)\]$/)
  if (!match) return null
  const path = match[1]
  if (path === 'unavailable') return null
  const parts = path.split('/')
  return parts[parts.length - 1]
}

interface NoteItemProps {
  note: Note
  onEdit?: (title: string, body: string) => void
  onDelete: (title: string) => void
  voiceUrl?: (filename: string) => string
}

function NoteItemInner({ note, onEdit, onDelete, voiceUrl }: NoteItemProps) {
  const { t } = useTranslation()

  if (note.is_voice) {
    const filename = extractVoiceFilename(note.body)
    return (
      <Card>
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="font-semibold font-cinzel text-dnd-gold">🎤 {note.title}</h3>
          <button
            onClick={() => onDelete(note.title)}
            className="text-xs text-[var(--dnd-danger)] shrink-0"
          >
            {t('common.delete')}
          </button>
        </div>
        {filename && voiceUrl ? (
          <audio
            controls
            src={voiceUrl(filename)}
            className="w-full"
          />
        ) : (
          <p className="text-sm text-dnd-text-secondary">
            {t('character.notes.voice')}
          </p>
        )}
      </Card>
    )
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className="font-semibold font-cinzel text-dnd-gold">{note.title}</h3>
        <div className="flex gap-2 shrink-0">
          {onEdit && (
            <button
              onClick={() => onEdit(note.title, note.body)}
              className="text-xs text-dnd-gold-dim"
            >
              {t('common.edit')}
            </button>
          )}
          <button
            onClick={() => onDelete(note.title)}
            className="text-xs text-[var(--dnd-danger)]"
          >
            {t('common.delete')}
          </button>
        </div>
      </div>
      <p className="text-sm text-dnd-text-secondary whitespace-pre-wrap line-clamp-3">
        {note.body}
      </p>
    </Card>
  )
}

const NoteItem = React.memo(NoteItemInner)
export default NoteItem
