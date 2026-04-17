import { lazy, Suspense } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import ModalProvider from './components/ModalProvider'
import DiceAnimationProvider from './dice/DiceAnimationProvider'
import Skeleton from './components/Skeleton'

// Lazy-loaded pages
const CharacterSelect = lazy(() => import('./pages/CharacterSelect'))
const CharacterMain = lazy(() => import('./pages/CharacterMain'))
const HP = lazy(() => import('./pages/HP'))
const ArmorClass = lazy(() => import('./pages/ArmorClass'))
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
const Identity = lazy(() => import('./pages/Identity'))
const Settings = lazy(() => import('./pages/Settings'))

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
    <HashRouter>
      <ModalProvider>
        <DiceAnimationProvider>
          <Suspense fallback={<PageFallback />}>
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
          </Suspense>
        </DiceAnimationProvider>
      </ModalProvider>
    </HashRouter>
  )
}
