import { lazy, Suspense, useEffect } from 'react'
import { HashRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import ModalProvider from './components/ModalProvider'
import DiceAnimationProvider from './dice/DiceAnimationProvider'
import DiceOverlay from './components/DiceOverlay'
import Skeleton from './components/Skeleton'
import { getDevUserId } from './auth/devUser'
import { getStartParam } from './auth/telegram'
import { parseStartParam } from './lib/startParam'

// Lazy-loaded pages
const CharacterSelect = lazy(() => import('./pages/CharacterSelect'))
const CharacterMain = lazy(() => import('./pages/CharacterMain'))
const HP = lazy(() => import('./pages/HP'))
const ArmorClass = lazy(() => import('./pages/ArmorClass'))
const Actions = lazy(() => import('./pages/Actions'))
const AbilityScores = lazy(() => import('./pages/AbilityScores'))
const Skills = lazy(() => import('./pages/Skills'))
const SavingThrows = lazy(() => import('./pages/SavingThrows'))
const Spells = lazy(() => import('./pages/Spells'))
const SpellSlots = lazy(() => import('./pages/SpellSlots'))
const Inventory = lazy(() => import('./pages/Inventory'))
const Currency = lazy(() => import('./pages/Currency'))
const Abilities = lazy(() => import('./pages/Abilities'))
const Multiclass = lazy(() => import('./pages/Multiclass'))
const Experience = lazy(() => import('./pages/Experience'))
const Conditions = lazy(() => import('./pages/Conditions'))
const History = lazy(() => import('./pages/History'))
const Notes = lazy(() => import('./pages/Notes'))
const Maps = lazy(() => import('./pages/Maps'))
const Dice = lazy(() => import('./pages/Dice'))
const DiceStats = lazy(() => import('./pages/DiceStats'))
const Identity = lazy(() => import('./pages/Identity'))
const Settings = lazy(() => import('./pages/Settings'))
const Session = lazy(() => import('./pages/Session'))
const SessionJoin = lazy(() => import('./pages/SessionJoin'))
const SessionRoom = lazy(() => import('./pages/SessionRoom'))
const Homebrew = lazy(() => import('./pages/Homebrew'))
const RuleEditor = lazy(() => import('./pages/homebrew/RuleEditor'))
const Changelog = lazy(() => import('./pages/Changelog'))

/** Deep link esterni (t.me/<bot>?startapp=…): reindirizza una sola volta per
 *  APERTURA della Mini App, così il back non rimbalza sulla destinazione ma un
 *  nuovo avvio (nuovo invito) torna a funzionare.
 *
 *  Il guard è un flag a livello di MODULO, non `sessionStorage`: deduplica il
 *  doppio effect di React StrictMode e i re-mount entro lo stesso page-load, ma
 *  si resetta a ogni apertura fresca. Il vecchio guard in sessionStorage
 *  persisteva nel webview riusato da Telegram e bloccava per sempre il redirect
 *  alle aperture successive → si restava su CharacterSelect invece di entrare
 *  in sessione. */
let startParamRedirectDone = false
function StartParamRedirect() {
  const navigate = useNavigate()
  useEffect(() => {
    if (startParamRedirectDone) return
    const action = parseStartParam(getStartParam())
    if (!action) return
    startParamRedirectDone = true
    if (action.kind === 'join') {
      navigate(`/session/join?code=${action.code}`, { replace: true })
    }
  }, [navigate])
  return null
}

/** Chip fisso che identifica il tab quando si impersona un utente dev
 *  (?dev_user=<id>), per non confondere le finestre GM/giocatore. */
function DevUserBadge() {
  const devUserId = getDevUserId()
  if (!devUserId) return null
  return (
    <div className="fixed bottom-safe left-2 z-[70] pointer-events-none rounded-full bg-amber-500/90 px-2 py-0.5 text-[10px] font-bold text-dnd-ink">
      DEV #{devUserId}
    </div>
  )
}

function PageFallback() {
  return (
    <div className="min-h-screen p-4 space-y-3">
      <Skeleton.Line width="140px" height="24px" />
      <Skeleton.Rect height="160px" />
      <Skeleton.Rect height="80px" delay={100} />
      <Skeleton.Rect height="80px" delay={200} />
    </div>
  )
}

export default function App() {
  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ModalProvider>
        <DiceAnimationProvider>
          <StartParamRedirect />
          <Suspense fallback={<PageFallback />}>
            <Routes>
            <Route path="/" element={<CharacterSelect />} />
            <Route path="/char/:id" element={<CharacterMain />} />
            <Route path="/char/:id/hp" element={<HP />} />
            <Route path="/char/:id/ac" element={<ArmorClass />} />
            <Route path="/char/:id/actions" element={<Actions />} />
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
            <Route path="/char/:id/dice/stats" element={<DiceStats />} />
            <Route path="/char/:id/identity" element={<Identity />} />
            <Route path="/char/:id/settings" element={<Settings />} />
            <Route path="/char/:id/homebrew" element={<Homebrew />} />
            <Route path="/char/:id/homebrew/new" element={<RuleEditor />} />
            <Route path="/char/:id/homebrew/:ruleId" element={<RuleEditor />} />
            <Route path="/changelog" element={<Changelog />} />
            <Route path="/session" element={<Session />} />
            <Route path="/session/join" element={<SessionJoin />} />
            <Route path="/session/:id" element={<SessionRoom />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </Suspense>
          <DiceOverlay />
          <DevUserBadge />
        </DiceAnimationProvider>
      </ModalProvider>
    </HashRouter>
  )
}
