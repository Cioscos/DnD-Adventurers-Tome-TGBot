import React from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import { formatRelative, formatAbsolute } from '@/lib/relativeTime'
import { useCharacterStore } from '@/store/characterStore'
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
  onEdit?: (title: string, body: string, tags: string[]) => void
  onDelete: (title: string) => void
  voiceUrl?: (filename: string) => string
}

function NoteItemInner({ note, onEdit, onDelete, voiceUrl }: NoteItemProps) {
  const { t } = useTranslation()
  const locale = useCharacterStore((s) => s.locale)
  const stamp = note.updated_at ?? note.created_at ?? null
  const tags = note.tags ?? []
  const relLabel = stamp
    ? formatRelative(stamp, {
        locale: locale === 'en' ? 'en' : 'it',
        todayLabel: t('common.today', { defaultValue: locale === 'en' ? 'Today' : 'Oggi' }),
        yesterdayLabel: t('common.yesterday', { defaultValue: locale === 'en' ? 'Yesterday' : 'Ieri' }),
      })
    : null
  const absLabel = stamp ? formatAbsolute(stamp, locale === 'en' ? 'en' : 'it') : null
  const editedPrefix = note.updated_at
    ? t('character.notes.edited_prefix', { defaultValue: locale === 'en' ? 'edited' : 'modificata' })
    : t('character.notes.created_prefix', { defaultValue: locale === 'en' ? 'created' : 'creata' })

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
          <p className="text-sm text-dnd-text-muted">
            {t('character.notes.voice')}
          </p>
        )}
        {relLabel && (
          <p
            className="mt-2 text-[10px] text-dnd-text-faint italic"
            title={absLabel ?? undefined}
          >
            {editedPrefix} · {relLabel}
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
              onClick={() => onEdit(note.title, note.body, note.tags ?? [])}
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
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="text-[10px] font-cinzel uppercase tracking-wider px-1.5 py-px rounded-full bg-dnd-chip-bg text-dnd-gold-dim border border-dnd-border"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      <p className="text-sm text-dnd-text-muted whitespace-pre-wrap line-clamp-3">
        {note.body}
      </p>
      {relLabel && (
        <p
          className="mt-2 text-[10px] text-dnd-text-faint italic"
          title={absLabel ?? undefined}
        >
          {editedPrefix} · {relLabel}
        </p>
      )}
    </Card>
  )
}

const NoteItem = React.memo(NoteItemInner)
export default NoteItem
