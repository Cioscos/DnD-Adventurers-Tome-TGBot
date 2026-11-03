import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import ChipInput from '@/components/ui/ChipInput'
import Pressable from '@/components/ui/Pressable'
import type { NoteCampaign } from '@/types'

interface NoteEditorProps {
  initialNote?: { title: string; body: string; tags?: string[]; campaign_id?: number | null } | null
  campaigns?: NoteCampaign[]
  /** Campagna preselezionata per una voce nuova (quella attuale del PG). */
  defaultCampaignId?: number | null
  onSave: (title: string, body: string, tags: string[], campaignId: number | null) => void
  onCancel: () => void
  isPending: boolean
}

export default function NoteEditor({ initialNote, campaigns = [], defaultCampaignId = null, onSave, onCancel, isPending }: NoteEditorProps) {
  const { t } = useTranslation()
  const isEdit = !!initialNote

  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [campaignId, setCampaignId] = useState<number | null>(defaultCampaignId)

  useEffect(() => {
    if (initialNote) {
      setTitle(initialNote.title)
      setBody(initialNote.body)
      setTags(initialNote.tags ?? [])
      setCampaignId(initialNote.campaign_id ?? null)
    } else {
      setTitle('')
      setBody('')
      setTags([])
      setCampaignId(defaultCampaignId)
    }
  }, [initialNote, defaultCampaignId])

  const handleSave = () => {
    onSave(title.trim(), body.trim(), tags, campaignId)
  }

  const rawSuggestions = t('character.notes.tag_suggestions', { returnObjects: true })
  const tagSuggestions: string[] = Array.isArray(rawSuggestions) ? rawSuggestions : []
  const pending = tagSuggestions.filter((s) => !tags.some((x) => x.toLowerCase() === s.toLowerCase()))

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
        label={
          <span className="block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('character.notes.tags_label')}
          </span>
        }
        placeholder={t('character.notes.tags_placeholder')}
      />
      {pending.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {pending.map((s) => (
            <Pressable
              key={s}
              type="button"
              onClick={() => setTags((prev) => [...prev, s])}
              className="min-h-11 px-3 rounded-xl border border-dnd-border bg-dnd-surface-raised text-sm font-body text-dnd-text"
            >
              + {s}
            </Pressable>
          ))}
        </div>
      )}
      {campaigns.length > 0 && (
        <div>
          <span className="block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('character.notes.campaign_label')}
          </span>
          <div className="flex flex-wrap gap-2">
            {[{ id: null, name: t('character.notes.campaign_none') }, ...campaigns].map((c) => (
              <Pressable
                key={c.id ?? 'none'}
                type="button"
                aria-pressed={campaignId === c.id}
                onClick={() => setCampaignId(c.id)}
                className={`min-h-11 px-3 rounded-xl border text-sm font-body ${
                  campaignId === c.id
                    ? 'bg-dnd-gold/20 border-dnd-gold text-dnd-gold-bright'
                    : 'bg-dnd-surface-raised border-dnd-border text-dnd-text'
                }`}
              >
                {c.name}
              </Pressable>
            ))}
          </div>
        </div>
      )}
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
