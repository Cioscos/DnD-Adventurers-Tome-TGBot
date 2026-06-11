# Ledger — impeccable pass per componenti

Coda di lavoro a batch di pagina. Stati: `☐` da fare · `◐` parziale · `✅` completato · `⛔` bloccato (motivo).
Questo ledger è stato seminato dall'audit FE del 2026-06-11 (`fe-playwright-audit/reports/2026-06-11_18-58-mobile/`): i findings citati (#n) vengono da quel `report.md`. Le run della skill risolvono comunque l'audit PIÙ RECENTE disponibile (vedi SKILL.md, Passo 0): se nel frattempo ne esiste uno più nuovo, integra qui i suoi findings prima di lavorare il batch.

> Baseline impeccable audit: **14/20** (2026-06-11, pre-B0). Score di fine giro: aggiornare qui.
> B0 (già consegnato in PR #166): label stats, pill On/Off, pb-24 swiper, side-stripe saves/combatant, backdrop warm, chip % HP, icona velocità.

## Batch trasversali (prima: sbloccano i batch di pagina)

- ☐ **B1 — Modali & overlay** · `ui/Sheet`, `ui/ConfirmSheet`, `ui/ResultDialog`, `ModalProvider`, `hp/HitDiceModal`, `notes` delete confirm, `maps/MapUploadForm`
  Findings: #4 ordine bottoni invertito (HitDiceModal, conferma nota, MapUploadForm → footer condiviso conferma-a-destra), #7 ESC non chiude ResultDialog, #12 back/history non chiude gli overlay (integrazione popstate/BackButton in ModalProvider).
  Verifica: hp→riposo breve, note→elimina, maps→form, skills→roll+ESC, back con sheet aperto.
- ☐ **B2 — Copy & i18n** · `locales/it.json`, `locales/en.json`, formatter numerici/orari
  Findings: #1 em dash (sweep U+2014 su entrambi i locale, incl. "Salta — compili dopo" e HandsConflictDialog), #8 "intelligence" grezzo nel modale save, #V4 separatore migliaia ("2,700"→"2.700" in it) e orario AM/PM nel feed sessione (→24h, coerente con Cronologia). Centralizzare `Intl.NumberFormat(locale)`/`hour12:false`.
  Verifica: wizard step 3, saves modal, xp hero, session feed, i18n it↔en.
- ☐ **B3 — Stati di errore & harden** · `AppErrorBoundary`, hook dati condiviso, `hp/DeathSaves`
  Findings: #10 id inesistente → main vuoto (EmptyState "Personaggio non trovato" + CTA lista nel Layout su 404), #5 indicatore "Stabilizzato · privo di sensi" (cobalt + icona) a 0 HP stabile. Passata empty/loading/error sulle pagine principali.
  Verifica: /char/9999/hp, death saves→3 successi, route abort.

## Batch di pagina

- ☐ **B4 — Hub personaggio** · `CharacterMain`, `character/HeroScreen`, `CharacterSwiper`, `SwiperDots`, `HeroStatsSection`, `QuickActions`, `SpellSlotsSummary`, `ProgressionPreview`, `ProgressionFullTableModal` (⛔ mai aperto: esercitalo), `ui/HPGauge`, `ui/HeroXPBar`, `ui/ConditionBadge`, `SearchOverlay` (#11: indicizzare risorse homebrew)
- ☐ **B5 — PaperDoll & equip** · `character/EquipmentScreen`, `PaperDoll`, `EquipmentSlotCell`, `SlotActionSheet`, `EquipItemPicker`, `EquipmentStatsFooter`, `HandsConflictDialog`, `ItemDetailsModal` (⛔ mai aperto), silhouette upload
- ☐ **B6 — Punti Ferita** · `pages/HP`, `hp/HpOperationForm`, `DeathSaves`, `DeathSaveResultDialog`, `InstantDeathDialog`, `DeadState`, `HitDiceResultDialog`, `ConcentrationSaveDialog`, `components/HPBar` (light mode con rigore pari al dark)
- ☐ **B7 — Tiri** · `pages/Skills`, `pages/SavingThrows`, `pages/Actions`, `RollResultModal`, `WeaponAttackModal`, `InspirationRerollButton`, long-press competenza (`useLongPress`)
- ☐ **B8 — Magia** · `pages/Spells`, `spells/SpellForm`, `SpellItem`, `SpellFilter`, `CastSpellModal`, `SpellDamageSheet` (⛔: serve spell con danno, creala), `pages/SpellSlots`, `character/AutoModeBanner`, banner concentrazione
- ☐ **B9 — Zaino** · `pages/Inventory`, `inventory/ItemForm`, `DamageDiceBuilder`, `InventoryItem`, `AbilityModifiersEditor` (⛔ visto ma non compilato), `EffectsEditor` (⛔), `pages/Currency`
- ☐ **B10 — Crescita** · `pages/Multiclass`, `multiclass/EditClassesModal`, `AddClassForm`, `LevelUpBanner`, `LevelUpModal` (⛔: esercitarlo con multiclasse), `pages/Experience`, `pages/Abilities`, `abilities/PassiveAbilityDetailModal` (⛔: serve una passiva, creala), `homebrew/CustomResourceCounter`
- ☐ **B11 — Stato & diario** · `pages/Conditions`, `conditions/ConditionDetailModal`, `pages/History`, `pages/Notes`, `notes/NoteEditor`, `NoteItem`, `NoteViewModal` (⛔), `VoiceRecorder` (⛔: serve permesso mic, prova su device), `pages/Maps`, `maps/MapUploadForm`, `MapZoneGroup`, `ZoomableImage`
- ☐ **B12 — Dadi** · `pages/Dice`, `pages/DiceStats`, `DiceOverlay` (FAB), `DicePoolResultModal`, `ui/DiceIcon`, `ui/PresetTextField`, pack texture (settings); unico posto con easing elastico ammesso
- ☐ **B13 — Identità, impostazioni & home** · `pages/Identity`, `pages/Settings` (tutte le sezioni), `pages/Changelog`, `pages/CharacterSelect`, `ui/SwitchToggle`, `ui/SelectSheet`, `ui/ChipInput` (⛔ campo Lingue mai esercitato), `ui/Flags`
- ☐ **B14 — Homebrew** · `pages/Homebrew` (hub/template), `homebrew/RuleEditor` + tutte le sections (`PropertyFormModal`, `PassiveModifierFormModal`, `EffectFormModal`, `EffectChainEditor` ⛔ mai aperti: crea una regola completa), `PropertyBadge`/`CustomConditionCard`/`HomebrewBreakdownRow`/`HomebrewNotification` (⛔: installare Sanguinamento e Qualità&Usura per vederli)
- ☐ **B15 — Sessione** · `pages/Session`, `SessionJoin`, `SessionRoom`, `session/SessionFeed`, `GrantItemModal`, `EncounterCreateSheet`, `CombatPanel`+`CombatantSheet`+`AddMonsterSheet`+`InitiativeCta`+`TurnBar`+`CombatantRow`+`RewardPopup`+`ParticipantIdentitySheet` (⛔: avviare un combattimento con 2 tab `?dev_user`), `ui/InSessionBanner`

## Chiusura giro

- ☐ **B16 — Re-audit** · ricalcola lo score impeccable (5 dimensioni), aggiorna la baseline qui sopra, riepilogo delta per l'utente. Se <17/20, apri il giro successivo con i residui.

## Fuori scope (bug funzionali trovati durante il pass — segnalare, non fixare qui)

- (vuoto)

## Diario

- 2026-06-11 · B0 consegnato in PR #166 (v2.14.2) · baseline 14/20
