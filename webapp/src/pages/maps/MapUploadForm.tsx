import { useRef, useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { UploadCloud, X, FileText } from 'lucide-react'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import FilterChip from '@/components/ui/FilterChip'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'

interface MapUploadFormProps {
  charId: number
  existingZones: string[]
  onUploadComplete: () => void
  onCancel: () => void
  initialZone?: string
}

const MAX_SIZE = 10 * 1024 * 1024
const ACCEPTED = /^(image\/|application\/pdf)/

function makePreviewUrl(file: File): string | null {
  if (!file.type.startsWith('image/')) return null
  return URL.createObjectURL(file)
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
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [activeProgress, setActiveProgress] = useState<number>(0)
  const [isDragOver, setIsDragOver] = useState(false)
  const [previews, setPreviews] = useState<Array<string | null>>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const next = selectedFiles.map(makePreviewUrl)
    setPreviews(next)
    return () => {
      for (const url of next) if (url) URL.revokeObjectURL(url)
    }
  }, [selectedFiles])

  const addFiles = (files: File[]) => {
    if (files.length === 0) return
    setUploadError(null)
    setSelectedFiles((prev) => [...prev, ...files])
  }

  const removeFile = (idx: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleUpload = async () => {
    if (!zoneName.trim() || selectedFiles.length === 0) return
    const tooLarge = selectedFiles.find((f) => f.size > MAX_SIZE)
    if (tooLarge) {
      setUploadError(t('character.maps.error_too_large', { name: tooLarge.name }))
      haptic.error()
      return
    }
    setIsUploading(true)
    setUploadError(null)
    try {
      for (let i = 0; i < selectedFiles.length; i++) {
        setActiveIndex(i)
        setActiveProgress(0)
        await api.maps.uploadWithProgress(charId, zoneName.trim(), selectedFiles[i], setActiveProgress)
      }
      haptic.success()
      onUploadComplete()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : t('character.maps.upload_error'))
      haptic.error()
    } finally {
      setIsUploading(false)
      setActiveIndex(null)
    }
  }

  const handleCancel = () => {
    setZoneName('')
    setSelectedFiles([])
    if (fileInputRef.current) fileInputRef.current.value = ''
    onCancel()
  }

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = Array.from(e.target.files ?? []).filter((f) => ACCEPTED.test(f.type) || /\.(heic|heif|pdf)$/i.test(f.name))
    addFiles(list)
    if (e.target) e.target.value = '' // allow re-picking the same file
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    const files = Array.from(e.dataTransfer.files).filter((f) => ACCEPTED.test(f.type) || /\.(heic|heif|pdf)$/i.test(f.name))
    addFiles(files)
  }

  return (
    <Surface variant="flat" className="space-y-3">
      <Input
        label={t('character.maps.zone_name')}
        value={zoneName}
        onChange={setZoneName}
        placeholder={t('character.maps.zone_name_placeholder')}
      />

      {existingZones.length > 0 && (
        <div className="flex gap-1.5 flex-wrap">
          {existingZones.map((z) => (
            <FilterChip
              key={z}
              label={z}
              selected={zoneName === z}
              onToggle={() => setZoneName(z)}
            />
          ))}
        </div>
      )}

      {/* Dropzone */}
      <div>
        <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
          {t('character.maps.select_files')}
        </label>
        <Pressable
          type="button"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true) }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          disabled={isUploading}
          className={`w-full flex flex-col items-center justify-center gap-2 py-6 rounded-xl
                      border-2 border-dashed transition-colors text-center
                      ${isDragOver
                        ? 'border-dnd-gold-bright bg-dnd-gold/10'
                        : 'border-dnd-border bg-dnd-surface/50 hover:border-dnd-gold/60'}
                      disabled:opacity-50`}
        >
          <UploadCloud size={28} className="text-dnd-gold-bright" />
          <span className="text-sm font-body text-dnd-text">
            {t('character.maps.dropzone_primary')}
          </span>
          <span className="text-[10px] font-mono text-dnd-text-faint">
            {t('character.maps.dropzone_accept')}
          </span>
        </Pressable>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf,.heic,.heif"
          onChange={handleFilePick}
          className="hidden"
        />
      </div>

      {/* Selected files list */}
      {selectedFiles.length > 0 && (
        <div className="space-y-1.5">
          {selectedFiles.map((file, idx) => {
            const isActive = activeIndex === idx
            const isDone = activeIndex !== null && idx < activeIndex
            const preview = previews[idx]
            return (
              <div
                key={`${file.name}-${idx}`}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-dnd-surface border border-dnd-border"
              >
                <div className="w-10 h-10 rounded-lg overflow-hidden bg-dnd-bg flex items-center justify-center shrink-0">
                  {preview ? (
                    <img src={preview} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <FileText size={18} className="text-dnd-gold-dim" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-body text-dnd-text truncate">{file.name}</p>
                  <p className="text-[10px] font-mono text-dnd-text-faint">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  {isUploading && isActive && (
                    <div className="h-1 mt-1 rounded-full bg-dnd-bg overflow-hidden border border-dnd-border">
                      <div
                        className="h-full bg-gradient-gold transition-[width] duration-200"
                        style={{ width: `${activeProgress}%` }}
                      />
                    </div>
                  )}
                  {isDone && (
                    <p className="text-[10px] font-mono text-dnd-gold-bright mt-0.5">
                      {t('character.maps.uploaded')}
                    </p>
                  )}
                </div>
                {!isUploading && (
                  <Pressable
                    type="button"
                    onClick={() => removeFile(idx)}
                    className="w-11 h-11 flex items-center justify-center shrink-0 rounded-lg
                               text-dnd-text-muted hover:text-dnd-crimson-bright transition-colors"
                    aria-label={`${t('common.remove')} ${file.name}`}
                  >
                    <X size={16} />
                  </Pressable>
                )}
              </div>
            )
          })}
          {isUploading && activeIndex !== null && selectedFiles.length > 1 && (
            <p className="text-[10px] font-mono text-dnd-text-faint text-center">
              {t('character.maps.upload_progress_count', {
                current: activeIndex + 1,
                total: selectedFiles.length,
                pct: activeProgress,
              })}
            </p>
          )}
        </div>
      )}

      {uploadError && (
        <p className="text-sm text-dnd-crimson-bright bg-dnd-crimson/10 rounded-xl px-3 py-2">
          {uploadError}
        </p>
      )}

      {/* Annulla a sinistra, conferma a destra (convenzione ConfirmSheet). */}
      <div className="flex gap-2">
        <Button
          variant="secondary"
          onClick={handleCancel}
          disabled={isUploading}
          fullWidth
        >
          {t('common.cancel')}
        </Button>
        <Button
          onClick={handleUpload}
          disabled={!zoneName.trim() || selectedFiles.length === 0 || isUploading}
          loading={isUploading}
          fullWidth
        >
          {t('character.maps.upload_btn')}
        </Button>
      </div>
    </Surface>
  )
}
