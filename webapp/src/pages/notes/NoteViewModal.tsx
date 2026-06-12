import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { renderInlineMarkdown } from '@/lib/inlineMarkdown'
import type { Note } from '@/types'

interface Props {
  note: Note | null
  onClose: () => void
  onEdit: (title: string, body: string, tags: string[]) => void
  onDelete: (title: string) => void
}

export default function NoteViewModal({ note, onClose, onEdit, onDelete }: Props) {
  const { t } = useTranslation()
  const tags = note?.tags ?? []

  return (
    <Sheet open={note !== null} onClose={onClose} title={note?.title ?? ''}>
      <div className="p-5 space-y-4">
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
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

        <div className="text-sm text-dnd-text whitespace-pre-wrap leading-relaxed">
          {note ? renderInlineMarkdown(note.body) : null}
        </div>

        {/* Lo Sheet chiude già con X, ESC, backdrop e back: niente bottone
            Chiudi ridondante. Azione distruttiva a sinistra, principale a destra. */}
        <div className="flex gap-2 pt-1">
          <Button variant="danger" fullWidth onClick={() => note && onDelete(note.title)}>
            {t('common.delete')}
          </Button>
          <Button variant="secondary" fullWidth onClick={() => note && onEdit(note.title, note.body, tags)}>
            {t('common.edit')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}
