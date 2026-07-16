import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2, X, AlertTriangle } from 'lucide-react'
import Button from '@/components/ui/Button'
import IconButton from '@/components/ui/IconButton'
import Pressable from '@/components/ui/Pressable'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Input from '@/components/ui/Input'
import { resolveLabelI18n, type Locale } from '@/lib/homebrew/i18n-dsl'
import type { Property, Table } from '@/lib/homebrew/types'
import { computeTableWarnings, formatBin } from './tablesSection.utils'

export interface TablesSectionProps {
  tables: Table[]
  properties: Property[]
  onChange: (tables: Table[]) => void
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeEmptyTable(): Table {
  return {
    id: 'lookup_table',
    row_axis: '',
    col_axis: '',
    col_bins: [
      [1, 1],
      [2, 3],
      [4, 9],
    ],
    cells: {},
  }
}

/**
 * Given a row_axis key and the current properties list, return the enum
 * Property whose key matches — or null if the axis is unset or stale.
 */
function findEnumProperty(properties: Property[], rowAxis: string): Property | null {
  if (!rowAxis) return null
  const prop = properties.find((p) => p.key === rowAxis)
  if (!prop || prop.type !== 'enum') return null
  return prop
}

// ---------------------------------------------------------------------------
// Task 4.8 — TablesSection
//
// Renders a list of lookup tables. Each table is an inline editable card:
//   - id / row_axis (enum picker) / col_axis (free-form)
//   - HTML <table> grid: cols = col_bins, rows = enum values of row_axis
//   - Cells are comma-separated string[] of action codes
//
// Rows are derived from the picked enum property's values — the user cannot
// add/remove rows directly. Columns are user-managed [lo, hi] bins.
// ---------------------------------------------------------------------------

export default function TablesSection({
  tables,
  properties,
  onChange,
}: TablesSectionProps) {
  const { t } = useTranslation()

  const enumProperties = properties.filter((p) => p.type === 'enum')
  const hasEnumProps = enumProperties.length > 0

  const [confirmDeleteIndex, setConfirmDeleteIndex] = useState<number | null>(null)

  // -------------------------------------------------------------------------
  // Top-level table list mutations
  // -------------------------------------------------------------------------

  const updateTable = (index: number, patch: Partial<Table>) => {
    const copy = tables.slice()
    copy[index] = { ...copy[index], ...patch }
    onChange(copy)
  }

  const addTable = () => {
    onChange([...tables, makeEmptyTable()])
  }

  const deleteTable = () => {
    if (confirmDeleteIndex === null) return
    const copy = tables.slice()
    copy.splice(confirmDeleteIndex, 1)
    onChange(copy)
    setConfirmDeleteIndex(null)
  }

  // -------------------------------------------------------------------------
  // Per-table editors
  // -------------------------------------------------------------------------

  const handleRowAxisChange = (index: number, nextAxis: string) => {
    // Switching the row_axis invalidates the cells dict (stale keys), so
    // reset it. col_bins / col_axis are preserved as they're independent.
    updateTable(index, { row_axis: nextAxis, cells: {} })
  }

  const handleColBinChange = (
    tableIndex: number,
    binIndex: number,
    which: 'lo' | 'hi',
    raw: string,
  ) => {
    const tableSnapshot = tables[tableIndex]
    const num = Number(raw)
    if (raw === '' || Number.isNaN(num)) return
    const bins = tableSnapshot.col_bins.slice() as [number, number][]
    const current = bins[binIndex]
    let lo = which === 'lo' ? num : current[0]
    let hi = which === 'hi' ? num : current[1]
    // Auto-correct lo > hi by clamping the other side
    if (lo > hi) {
      if (which === 'lo') hi = lo
      else lo = hi
    }
    bins[binIndex] = [lo, hi]
    updateTable(tableIndex, { col_bins: bins })
  }

  const addColumn = (tableIndex: number) => {
    const tableSnapshot = tables[tableIndex]
    const lastHi = tableSnapshot.col_bins.length
      ? tableSnapshot.col_bins[tableSnapshot.col_bins.length - 1][1]
      : 0
    const nextStart = lastHi + 1
    const bins: [number, number][] = [...tableSnapshot.col_bins, [nextStart, nextStart]]
    // Append an empty slot to each existing row's cell array.
    const cells: Record<string, string[]> = {}
    for (const [k, v] of Object.entries(tableSnapshot.cells)) {
      cells[k] = [...v, '']
    }
    updateTable(tableIndex, { col_bins: bins, cells })
  }

  const removeColumn = (tableIndex: number, binIndex: number) => {
    const tableSnapshot = tables[tableIndex]
    const bins = tableSnapshot.col_bins.slice() as [number, number][]
    bins.splice(binIndex, 1)
    const cells: Record<string, string[]> = {}
    for (const [k, v] of Object.entries(tableSnapshot.cells)) {
      const next = v.slice()
      next.splice(binIndex, 1)
      cells[k] = next
    }
    updateTable(tableIndex, { col_bins: bins, cells })
  }

  /**
   * Commit a cell edit. The cell value displayed in the input is a comma-
   * separated list; we parse on commit to a `string[]` (trim + drop empties).
   * Ensures the row entry exists and is padded to col_bins.length.
   */
  const commitCell = (
    tableIndex: number,
    rowValue: string,
    binIndex: number,
    raw: string,
  ) => {
    const tableSnapshot = tables[tableIndex]
    const parsed = raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const cells: Record<string, string[]> = { ...tableSnapshot.cells }
    const row = (cells[rowValue] ?? []).slice()
    // Pad to col_bins.length so we don't end up with a sparse array.
    while (row.length < tableSnapshot.col_bins.length) row.push('')
    row[binIndex] = parsed.join(', ')
    cells[rowValue] = row
    updateTable(tableIndex, { cells })
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const deletingTable =
    confirmDeleteIndex !== null ? tables[confirmDeleteIndex] : null

  return (
    <div className="space-y-3">
      {!hasEnumProps && (
        <p className="px-2 py-3 text-[12px] font-body italic text-dnd-text-muted border border-dnd-border rounded-xl bg-dnd-surface/40">
          {t('homebrew.tables.need_enum')}
        </p>
      )}

      {tables.length === 0 ? (
        <p className="px-2 py-4 text-center text-sm font-body italic text-dnd-text-muted">
          {t('homebrew.tables.empty')}
        </p>
      ) : (
        <ul className="space-y-3">
          {tables.map((table, tableIndex) => (
            <TableCard
              key={tableIndex}
              table={table}
              enumProperties={enumProperties}
              onIdChange={(id) => updateTable(tableIndex, { id })}
              onRowAxisChange={(axis) => handleRowAxisChange(tableIndex, axis)}
              onColAxisChange={(axis) => updateTable(tableIndex, { col_axis: axis })}
              onColBinChange={(binIdx, which, raw) =>
                handleColBinChange(tableIndex, binIdx, which, raw)
              }
              onAddColumn={() => addColumn(tableIndex)}
              onRemoveColumn={(binIdx) => removeColumn(tableIndex, binIdx)}
              onCommitCell={(rowValue, binIdx, raw) =>
                commitCell(tableIndex, rowValue, binIdx, raw)
              }
              onRequestDelete={() => setConfirmDeleteIndex(tableIndex)}
            />
          ))}
        </ul>
      )}

      <Button
        variant="secondary"
        size="sm"
        icon={<Plus size={16} />}
        onClick={addTable}
        disabled={!hasEnumProps}
      >
        {t('homebrew.tables.add_button')}
      </Button>

      <ConfirmSheet
        open={confirmDeleteIndex !== null}
        onClose={() => setConfirmDeleteIndex(null)}
        onConfirm={deleteTable}
        title={t('common.delete')}
        body={
          deletingTable
            ? t('homebrew.tables.delete_confirm', { name: deletingTable.id })
            : ''
        }
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
      />
    </div>
  )
}

// ===========================================================================
// TableCard — one card per Table; renders id/axis inputs + the grid editor
// ===========================================================================

interface TableCardProps {
  table: Table
  enumProperties: Property[]
  onIdChange: (id: string) => void
  onRowAxisChange: (axis: string) => void
  onColAxisChange: (axis: string) => void
  onColBinChange: (binIndex: number, which: 'lo' | 'hi', raw: string) => void
  onAddColumn: () => void
  onRemoveColumn: (binIndex: number) => void
  onCommitCell: (rowValue: string, binIndex: number, raw: string) => void
  onRequestDelete: () => void
}

function TableCard({
  table,
  enumProperties,
  onIdChange,
  onRowAxisChange,
  onColAxisChange,
  onColBinChange,
  onAddColumn,
  onRemoveColumn,
  onCommitCell,
  onRequestDelete,
}: TableCardProps) {
  const { t, i18n } = useTranslation()
  const locale: Locale = i18n.language?.startsWith('en') ? 'en' : 'it'

  const axisProp = findEnumProperty(enumProperties, table.row_axis)
  const rowValues = axisProp?.values ?? []
  const warnings = computeTableWarnings(table)

  return (
    <li className="bg-dnd-surface-raised border border-dnd-border rounded-2xl p-3 space-y-3">
      {/* Card header: id input + delete button */}
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <Input
            label={t('homebrew.tables.id_label')}
            value={table.id}
            onChange={onIdChange}
            placeholder={t('homebrew.tables.id_placeholder')}
            className="font-mono"
          />
        </div>
        <IconButton
          icon={<Trash2 size={16} />}
          onClick={onRequestDelete}
          haptic="none"
          className="shrink-0 mt-6 p-1.5 rounded-lg text-dnd-crimson hover:text-dnd-crimson-bright hover:bg-dnd-crimson/10 min-w-[44px] min-h-[44px]"
          aria-label={t('common.delete')}
        />
      </div>

      {/* Axis pickers */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('homebrew.tables.row_axis_label')}
          </label>
          <select
            value={table.row_axis}
            onChange={(e) => onRowAxisChange(e.target.value)}
            disabled={enumProperties.length === 0}
            className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text border-b-2 border-dnd-border outline-none font-body disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <option value="">{t('homebrew.tables.row_axis_placeholder')}</option>
            {enumProperties.map((p) => (
              <option key={p.key} value={p.key}>
                {resolveLabelI18n(p.label_i18n, locale, p.key)} ({p.key})
              </option>
            ))}
          </select>
        </div>

        <Input
          label={t('homebrew.tables.col_axis_label')}
          value={table.col_axis}
          onChange={onColAxisChange}
          placeholder={t('homebrew.tables.col_axis_placeholder')}
          className="font-mono"
        />
      </div>

      {/* Grid editor */}
      {axisProp && rowValues.length > 0 ? (
        <div className="overflow-x-auto -mx-3 px-3">
          <table className="border-collapse w-full text-sm">
            <thead>
              <tr>
                {/* Top-left corner — empty */}
                <th className="bg-dnd-surface/40 border border-dnd-border p-1 text-[11px] font-cinzel uppercase tracking-wider text-dnd-gold-dim text-left min-w-[100px]">
                  {resolveLabelI18n(axisProp.label_i18n, locale, axisProp.key)}
                </th>
                {table.col_bins.map((bin, binIdx) => (
                  <th
                    key={binIdx}
                    className="bg-dnd-surface/40 border border-dnd-border p-1 align-top min-w-[110px]"
                  >
                    <ColBinHeader
                      bin={bin}
                      onChange={(which, raw) => onColBinChange(binIdx, which, raw)}
                      onRemove={
                        table.col_bins.length > 1
                          ? () => onRemoveColumn(binIdx)
                          : undefined
                      }
                    />
                  </th>
                ))}
                <th className="bg-dnd-surface/40 border border-dnd-border p-1 w-[44px]">
                  <IconButton
                    icon={<Plus size={16} />}
                    onClick={onAddColumn}
                    haptic="none"
                    className="w-full min-h-[36px] rounded-md text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface/60"
                    title={t('homebrew.tables.add_column')}
                    aria-label={t('homebrew.tables.add_column')}
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              {rowValues.map((rv) => {
                const label = resolveLabelI18n(axisProp.value_labels_i18n?.[rv], locale, rv)
                const rowCells = table.cells[rv] ?? []
                return (
                  <tr key={rv}>
                    <th className="bg-dnd-surface/30 border border-dnd-border p-1.5 text-left align-top">
                      <div className="text-[12px] font-display text-dnd-text">
                        {label}
                      </div>
                      <code className="text-[10px] font-mono text-dnd-text-muted block mt-0.5">
                        {rv}
                      </code>
                    </th>
                    {table.col_bins.map((_, binIdx) => (
                      <td
                        key={binIdx}
                        className="border border-dnd-border p-1 align-top"
                      >
                        <CellInput
                          initial={rowCells[binIdx] ?? ''}
                          placeholder={t('homebrew.tables.cell_placeholder')}
                          onCommit={(raw) => onCommitCell(rv, binIdx, raw)}
                        />
                      </td>
                    ))}
                    <td className="border border-dnd-border" />
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {warnings.length > 0 && (
        <ul className="space-y-1 pt-0.5">
          {warnings.map((w, i) => (
            <li
              key={i}
              className="flex items-start gap-1.5 text-[11px] font-body text-dnd-amber"
            >
              <AlertTriangle size={12} className="shrink-0 mt-0.5" />
              <span>{t(w.key, w.params)}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

// ===========================================================================
// ColBinHeader — editable [lo, hi] pair shown as the column header
// ===========================================================================

interface ColBinHeaderProps {
  bin: [number, number]
  onChange: (which: 'lo' | 'hi', raw: string) => void
  onRemove?: () => void
}

function ColBinHeader({ bin, onChange, onRemove }: ColBinHeaderProps) {
  const { t } = useTranslation()
  const [lo, setLo] = useState(String(bin[0]))
  const [hi, setHi] = useState(String(bin[1]))

  // Keep local state in sync if parent updates (e.g. auto-correct on lo>hi).
  // We don't useEffect here to avoid clobbering mid-edit — these are
  // uncontrolled-ish; reflect parent on blur via onCommit.
  // (If the parent rewrites, we rely on the next remount of the cell.)

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <input
          type="text"
          inputMode="numeric"
          value={lo}
          onChange={(e) => setLo(e.target.value)}
          onBlur={() => onChange('lo', lo)}
          aria-label={t('homebrew.tables.col_bin_lo')}
          className="w-12 px-1 py-1 min-h-[32px] rounded bg-dnd-surface text-dnd-text border border-dnd-border outline-none text-center font-mono text-[12px]"
        />
        <span className="text-dnd-text-muted text-[11px]">–</span>
        <input
          type="text"
          inputMode="numeric"
          value={hi}
          onChange={(e) => setHi(e.target.value)}
          onBlur={() => onChange('hi', hi)}
          aria-label={t('homebrew.tables.col_bin_hi')}
          className="w-12 px-1 py-1 min-h-[32px] rounded bg-dnd-surface text-dnd-text border border-dnd-border outline-none text-center font-mono text-[12px]"
        />
        {onRemove && (
          <Pressable
            onClick={onRemove}
            className="hit-44 ml-auto p-1 rounded text-dnd-crimson/70 hover:text-dnd-crimson-bright hover:bg-dnd-crimson/10 transition-colors min-w-[28px] min-h-[28px] flex items-center justify-center"
            aria-label={t('common.remove')}
          >
            <X size={12} />
          </Pressable>
        )}
      </div>
      <div className="text-[10px] text-dnd-text-muted font-mono text-center">
        {formatBin(bin)}
      </div>
    </div>
  )
}

// ===========================================================================
// CellInput — uncontrolled comma-separated input; parent commits on blur
// ===========================================================================

interface CellInputProps {
  initial: string
  placeholder?: string
  onCommit: (raw: string) => void
}

function CellInput({ initial, placeholder, onCommit }: CellInputProps) {
  const [value, setValue] = useState(initial)
  return (
    <textarea
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => onCommit(value)}
      placeholder={placeholder}
      rows={2}
      className="w-full px-1.5 py-1 min-h-[48px] rounded bg-dnd-surface text-dnd-text border border-dnd-border outline-none focus:border-dnd-gold font-mono text-[11px] resize-y"
    />
  )
}
