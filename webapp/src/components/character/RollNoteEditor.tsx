import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Pencil } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import { saveSettingsPatch, rollNoteOf, ROLL_NOTE_MAX } from '@/lib/settings'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
  /** `save.<ability>` or `skill.<slug>` */
  noteKey: string
  label: string
}

/** Pencil button + sheet with one text field; an empty note removes the key. */
export default function RollNoteEditor({ char, noteKey, label }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')

  const mutation = useMutation({
    mutationFn: (text: string) => {
      const notes = { ...(char.settings?.roll_notes as Record<string, string> | undefined) }
      if (text) notes[noteKey] = text
      else delete notes[noteKey]
      return saveSettingsPatch(char, { roll_notes: notes })
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      setOpen(false)
    },
  })

  return (
    <>
      <Pressable
        onClick={() => {
          setDraft(rollNoteOf(char, noteKey))
          setOpen(true)
        }}
        aria-label={t('character.roll_notes.edit', { name: label })}
        className="w-11 max-xs:w-7 h-11 hit-44 flex items-center justify-center shrink-0 text-dnd-text-faint"
      >
        <Pencil size={14} />
      </Pressable>
      <Sheet open={open} onClose={() => setOpen(false)} title={t('character.roll_notes.title', { name: label })}>
        <div className="p-5 space-y-3">
          <input
            type="text"
            value={draft}
            maxLength={ROLL_NOTE_MAX}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t('character.roll_notes.placeholder')}
            aria-label={t('character.roll_notes.placeholder')}
            className="w-full min-h-[44px] px-3 rounded-xl bg-dnd-surface border border-dnd-border text-sm font-body text-dnd-text"
          />
          <Pressable
            onClick={() => mutation.mutate(draft.trim())}
            pending={mutation.isPending}
            className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright"
          >
            {t('common.save')}
          </Pressable>
        </div>
      </Sheet>
    </>
  )
}
