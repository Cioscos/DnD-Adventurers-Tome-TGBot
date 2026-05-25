import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import ChipInput from '@/components/ui/ChipInput'

const TAG_SUGGESTIONS_IT = ['Lore', 'NPC', 'Quest', 'Loot', 'Trama', 'Segreto']
const TAG_SUGGESTIONS_EN = ['Lore', 'NPC', 'Quest', 'Loot', 'Plot', 'Secret']

interface NoteEditorProps {
  initialNote?: { title: string; body: string; tags?: string[] } | null
  onSave: (title: string, body: string, tags: string[]) => void
  onCancel: () => void
  isPending: boolean
}

export default function NoteEditor({ initialNote, onSave, onCancel, isPending }: NoteEditorProps) {
  const { t, i18n } = useTranslation()
  const isEdit = !!initialNote

  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [tags, setTags] = useState<string[]>([])

  useEffect(() => {
    if (initialNote) {
      setTitle(initialNote.title)
      setBody(initialNote.body)
      setTags(initialNote.tags ?? [])
    } else {
      setTitle('')
      setBody('')
      setTags([])
    }
  }, [initialNote])

  const handleSave = () => {
    onSave(title.trim(), body.trim(), tags)
  }

  const tagSuggestions = i18n.language === 'en' ? TAG_SUGGESTIONS_EN : TAG_SUGGESTIONS_IT

  return (
    <div className="space-y-3">
      {!isEdit && (
        <DndInput
          label={t('character.notes.title_label')}
          value={title}
          onChange={setTitle}
          placeholder={t('character.notes.title_placeholder')}
        />
      )}
      <div>
        <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
          {t('character.notes.body_label')}
        </label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={t('character.notes.body_placeholder')}
          rows={10}
          className="w-full bg-dnd-surface rounded-xl px-3 py-2 outline-none resize-none
                     border border-transparent focus:border-dnd-gold-dim
                     focus:shadow-[0_0_0_2px_var(--dnd-gold-glow)]
                     placeholder:text-dnd-text-muted/50"
        />
      </div>
      <ChipInput
        values={tags}
        onChange={setTags}
        suggestions={tagSuggestions}
        label={
          <span className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
            {t('character.notes.tags_label', { defaultValue: 'Tag' })}
          </span>
        }
        placeholder={t('character.notes.tags_placeholder', { defaultValue: 'NPC, Lore, Quest…' })}
      />
      <div className="flex gap-2">
        <DndButton
          onClick={handleSave}
          disabled={isPending || (!isEdit && !title.trim())}
          loading={isPending}
          className="flex-1"
        >
          {t('common.save')}
        </DndButton>
        <DndButton
          variant="secondary"
          onClick={onCancel}
          className="flex-1"
        >
          {t('common.cancel')}
        </DndButton>
      </div>
    </div>
  )
}
