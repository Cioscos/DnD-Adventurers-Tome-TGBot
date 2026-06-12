import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
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
        <Input
          label={t('character.notes.title_label')}
          value={title}
          onChange={setTitle}
          placeholder={t('character.notes.title_placeholder')}
        />
      )}
      <Input
        variant="textarea"
        rows={10}
        label={t('character.notes.body_label')}
        value={body}
        onChange={setBody}
        placeholder={t('character.notes.body_placeholder')}
      />
      <ChipInput
        values={tags}
        onChange={setTags}
        suggestions={tagSuggestions}
        label={
          <span className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('character.notes.tags_label')}
          </span>
        }
        placeholder={t('character.notes.tags_placeholder')}
      />
      <div className="flex gap-2">
        <Button
          variant="secondary"
          onClick={onCancel}
          fullWidth
        >
          {t('common.cancel')}
        </Button>
        <Button
          onClick={handleSave}
          disabled={isPending || (!isEdit && !title.trim())}
          loading={isPending}
          fullWidth
        >
          {t('common.save')}
        </Button>
      </div>
    </div>
  )
}
