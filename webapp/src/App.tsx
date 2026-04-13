import { useEffect, useState } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import CharacterSelect from './pages/CharacterSelect'
import CharacterMain from './pages/CharacterMain'
import HP from './pages/HP'
import ArmorClass from './pages/ArmorClass'
import AbilityScores from './pages/AbilityScores'
import Skills from './pages/Skills'
import SavingThrows from './pages/SavingThrows'
import Spells from './pages/Spells'
import SpellSlots from './pages/SpellSlots'
import Inventory from './pages/Inventory'
import Currency from './pages/Currency'
import Abilities from './pages/Abilities'
import Multiclass from './pages/Multiclass'
import Experience from './pages/Experience'
import Conditions from './pages/Conditions'
import History from './pages/History'
import Notes from './pages/Notes'
import Maps from './pages/Maps'
import Dice from './pages/Dice'
import Identity from './pages/Identity'
import Settings from './pages/Settings'

/** Temporary diagnostic overlay — remove once keyboard-button 401 is resolved. */
function TelegramDebugOverlay() {
  const [info, setInfo] = useState<string | null>(null)

  useEffect(() => {
    const wa = window.Telegram?.WebApp
    if (wa?.initData) return  // auth works — hide overlay

    // Read snapshot captured in main.tsx BEFORE HashRouter mutated the hash.
    const dbg = (window as any).__tgDebug ?? {}
    const rawHash: string = dbg.hash ?? window.location.hash
    const hasTgData = rawHash.includes('tgWebAppData')
    const events: Array<{ type: string }> = dbg.nativeEvents ?? []

    const lines = [
      `initData: EMPTY`,
      `platform: ${wa?.platform ?? 'N/A'}  ver: ${wa?.version ?? 'N/A'}`,
      `TgProxy: ${dbg.hasTgProxy ? 'YES' : 'NO'}`,
      `tgWebAppData in hash: ${hasTgData ? 'YES' : 'NO'}`,
      `hash len: ${rawHash.length}  first 80:`,
      rawHash.slice(0, 80) || '(empty)',
      `nativeBridge events (${events.length}): ${events.map(e => e.type).join(', ') || 'none'}`,
      `initDataUnsafe.user: ${wa?.initDataUnsafe?.user?.id ?? 'missing'}`,
    ]
    setInfo(lines.join('\n'))
  }, [])

  if (!info) return null

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
      background: '#b00020', color: '#fff', padding: '8px 10px',
      fontSize: '11px', whiteSpace: 'pre-wrap', lineHeight: 1.5,
      fontFamily: 'monospace', wordBreak: 'break-all',
    }}>
      {info}
    </div>
  )
}

export default function App() {
  return (
    <>
    <TelegramDebugOverlay />
    <HashRouter>
      <Routes>
        <Route path="/" element={<CharacterSelect />} />
        <Route path="/char/:id" element={<CharacterMain />} />
        <Route path="/char/:id/hp" element={<HP />} />
        <Route path="/char/:id/ac" element={<ArmorClass />} />
        <Route path="/char/:id/stats" element={<AbilityScores />} />
        <Route path="/char/:id/skills" element={<Skills />} />
        <Route path="/char/:id/saves" element={<SavingThrows />} />
        <Route path="/char/:id/spells" element={<Spells />} />
        <Route path="/char/:id/slots" element={<SpellSlots />} />
        <Route path="/char/:id/inventory" element={<Inventory />} />
        <Route path="/char/:id/currency" element={<Currency />} />
        <Route path="/char/:id/abilities" element={<Abilities />} />
        <Route path="/char/:id/class" element={<Multiclass />} />
        <Route path="/char/:id/xp" element={<Experience />} />
        <Route path="/char/:id/conditions" element={<Conditions />} />
        <Route path="/char/:id/history" element={<History />} />
        <Route path="/char/:id/notes" element={<Notes />} />
        <Route path="/char/:id/maps" element={<Maps />} />
        <Route path="/char/:id/dice" element={<Dice />} />
        <Route path="/char/:id/identity" element={<Identity />} />
        <Route path="/char/:id/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
    </>
  )
}
