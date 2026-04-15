import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'

interface MapUploadFormProps {
  charId: number
  existingZones: string[]
  onUploadComplete: () => void
  onCancel: () => void
  initialZone?: string
}

export default function MapUploadForm({
  charId,
  existingZones,
  onUploadComplete,
  onCancel,
  initialZone = '',
}: MapUploadFormProps) {
  const { t } = useTranslation()
  const [zoneName, setZoneName] = useState(initialZone)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleUpload = async () => {
    if (!zoneName.trim() || selectedFiles.length === 0) return
    setIsUploading(true)
    setUploadError(null)
    try {
      for (const file of selectedFiles) {
        await api.maps.upload(charId, zoneName.trim(), file)
      }
      haptic.success()
      onUploadComplete()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
      haptic.error()
    } finally {
      setIsUploading(false)
    }
  }

  const handleCancel = () => {
    setZoneName('')
    setSelectedFiles([])
    if (fileInputRef.current) fileInputRef.current.value = ''
    onCancel()
  }

  return (
    <Card className="space-y-3">
      <DndInput
        label={t('character.maps.zone_name')}
        value={zoneName}
        onChange={setZoneName}
        placeholder={t('character.maps.zone_name_placeholder')}
      />

      {existingZones.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {existingZones.map((z) => (
            <button
              key={z}
              onClick={() => setZoneName(z)}
              className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                zoneName === z
                  ? 'bg-dnd-gold text-dnd-bg'
                  : 'bg-dnd-surface'
              }`}
            >
              {z}
            </button>
          ))}
        </div>
      )}

      <div>
        <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
          {t('character.maps.select_files')}
        </label>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf,.heic,.heif"
          onChange={(e) => setSelectedFiles(Array.from(e.target.files ?? []))}
          className="w-full text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-lg
                     file:border-0 file:text-sm file:font-medium
                     file:bg-dnd-surface file:text-dnd-text"
        />
        {selectedFiles.length > 1 && (
          <p className="text-xs text-dnd-text-secondary mt-1">
            {t('character.maps.files_selected', { count: selectedFiles.length })}
          </p>
        )}
      </div>

      {uploadError && (
        <p className="text-sm text-[var(--dnd-danger)] bg-[var(--dnd-danger)]/10 rounded-xl px-3 py-2">
          {uploadError}
        </p>
      )}

      <div className="flex gap-2">
        <DndButton
          onClick={handleUpload}
          disabled={!zoneName.trim() || selectedFiles.length === 0 || isUploading}
          loading={isUploading}
          className="flex-1"
        >
          {t('character.maps.upload_btn')}
        </DndButton>
        <DndButton
          variant="secondary"
          onClick={handleCancel}
          className="flex-1"
        >
          {t('common.cancel')}
        </DndButton>
      </div>
    </Card>
  )
}
