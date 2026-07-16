import React from 'react'
import { useTranslation } from 'react-i18next'
import { Mic, Pencil, Share2, Trash2 } from 'lucide-react'
import Surface from '@/components/ui/Surface'
import Pressable from '@/components/ui/Pressable'
import { renderInlineMarkdown } from '@/lib/inlineMarkdown'
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
  onView?: (note: Note) => void
  onShare?: (title: string) => void
  /** useShareMessage().isPending, already narrowed to this note by the caller
   *  (the mutation is shared across every note's share button). */
  sharePending?: boolean
  voiceUrl?: (filename: string) => string
}

function NoteItemInner({ note, onEdit, onDelete, onView, onShare, sharePending = false, voiceUrl }: NoteItemProps) {
  const { t } = useTranslation()
  const locale = useCharacterStore((s) => s.locale)
  const stamp = note.updated_at ?? note.created_at ?? null
  const tags = note.tags ?? []
  const relLabel = stamp
    ? formatRelative(stamp, {
        locale: locale === 'en' ? 'en' : 'it',
        todayLabel: t('common.date.today'),
        yesterdayLabel: t('common.date.yesterday'),
      })
    : null
  const absLabel = stamp ? formatAbsolute(stamp, locale === 'en' ? 'en' : 'it') : null
  const editedPrefix = note.updated_at
    ? t('character.notes.edited_prefix')
    : t('character.notes.created_prefix')

  if (note.is_voice) {
    const filename = extractVoiceFilename(note.body)
    return (
      <Surface variant="flat">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="font-semibold font-cinzel text-dnd-gold flex items-center gap-1.5 min-w-0">
            <Mic size={14} className="shrink-0 text-dnd-gold-dim" />
            <span className="truncate">{note.title}</span>
          </h3>
          <div className="flex shrink-0 -my-2.5 -mr-2 gap-0.5">
            {onShare && (
              <Pressable
                onClick={() => onShare(note.title)}
                pending={sharePending}
                className="w-11 h-11 flex items-center justify-center shrink-0 rounded-lg
                           text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
                aria-label={t('share.action')}
              >
                <Share2 size={16} />
              </Pressable>
            )}
            <Pressable
              onClick={() => onDelete(note.title)}
              className="w-11 h-11 flex items-center justify-center shrink-0 rounded-lg
                         text-dnd-text-muted hover:text-dnd-crimson-bright transition-colors"
              aria-label={t('common.delete')}
            >
              <Trash2 size={16} />
            </Pressable>
          </div>
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
      </Surface>
    )
  }

  return (
    <Surface
      variant="flat"
      onClick={onView ? () => onView(note) : undefined}
      className={onView ? 'cursor-pointer' : undefined}
    >
      <div className="flex items-start justify-between gap-1 mb-1">
        <h3 className="font-semibold font-cinzel text-dnd-gold min-w-0 break-words pt-2">{note.title}</h3>
        <div className="flex shrink-0 -my-2 -mr-2">
          {onShare && (
            <Pressable
              onClick={(e) => { e.stopPropagation(); onShare(note.title) }}
              pending={sharePending}
              className="w-11 h-11 flex items-center justify-center rounded-lg
                         text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
              aria-label={t('share.action')}
            >
              <Share2 size={16} />
            </Pressable>
          )}
          {onEdit && (
            <Pressable
              onClick={(e) => { e.stopPropagation(); onEdit(note.title, note.body, note.tags ?? []) }}
              className="w-11 h-11 flex items-center justify-center rounded-lg
                         text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
              aria-label={t('common.edit')}
            >
              <Pencil size={16} />
            </Pressable>
          )}
          <Pressable
            onClick={(e) => { e.stopPropagation(); onDelete(note.title) }}
            className="w-11 h-11 flex items-center justify-center rounded-lg
                       text-dnd-text-muted hover:text-dnd-crimson-bright transition-colors"
            aria-label={t('common.delete')}
          >
            <Trash2 size={16} />
          </Pressable>
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
        {renderInlineMarkdown(note.body)}
      </p>
      {relLabel && (
        <p
          className="mt-2 text-[10px] text-dnd-text-faint italic"
          title={absLabel ?? undefined}
        >
          {editedPrefix} · {relLabel}
        </p>
      )}
    </Surface>
  )
}

const NoteItem = React.memo(NoteItemInner)
export default NoteItem
