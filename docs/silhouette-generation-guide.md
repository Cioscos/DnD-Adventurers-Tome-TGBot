---
title: Silhouette Generation Guide
description: Guida per generare le PNG delle silhouette personaggio per la Mini App
audience: Future Claude session (and the user, when triggering generation)
---

# Silhouette Generation Guide

Guida operativa per generare le immagini PNG che la Mini App usa nel `PaperDoll`
dell'EquipmentScreen al posto del fallback SVG Vitruviano.

## TL;DR

1. Genera PNG con sfondo trasparente, ratio verticale ~5:9, ~600×1080 px.
2. Nome file: `{class}_{race}_{gender}.png` — tutto lowercase, snake_case sui multi-word.
3. Drop in `webapp/public/silhouettes/`.
4. Restart `npm run dev` (manifest si rigenera al `vite dev` start) o `npm run build:prod`.
5. Apri il PG canonico → la silhouette PNG sostituisce l'SVG.

## 1. Dove vive il sistema

| File / dir | Ruolo |
|---|---|
| `webapp/public/silhouettes/` | Cartella delle PNG. Solo `.png`. Trasparenti. |
| `webapp/scripts/generate-silhouette-manifest.mjs` | Build script che enumera la cartella in JSON. |
| `webapp/src/data/silhouette-manifest.json` | Manifest generato (gitignored). |
| `webapp/src/lib/silhouette.ts` | Resolver: `silhouetteUrl(char)` con fallback chain. |
| `webapp/src/components/character/PaperDoll.tsx` | Render `<img>` se URL disponibile, altrimenti SVG. |
| `webapp/vite.config.ts` | Plugin `silhouetteManifestPlugin` che rilancia lo script su `buildStart`. |
| `docs/superpowers/specs/2026-04-29-character-menu-fixes-design.md` | Spec originale (fonte di verità). |

## 2. Naming convention (rigida)

```
{class}_{race}_{gender}.png
```

Tutto **lowercase**, separator **underscore**, no spazi/accenti/caratteri speciali.

### Classi canonical (12 PHB 2014)
```
barbarian, bard, cleric, druid, fighter, monk,
paladin, ranger, rogue, sorcerer, warlock, wizard
```

### Race slug
```
human, elf, dwarf, halfling, half_elf, half_orc,
gnome, tiefling, dragonborn
```
Multi-word usa `_` (es. `half_elf`, **non** `halfelf` o `half-elf`).

### Gender slug
```
male, female
```
Non-binary / altro / vuoto → niente file gender-specific (resolver salta a `class_race`).

### Esempi validi
```
wizard.png                       — generico per la classe
wizard_male.png                  — wizard generico maschile
wizard_elf.png                   — wizard elfo neutro
wizard_elf_female.png            — wizard elfa specifica
half_orc.png                     — file race-only NON valido (manca class)
fighter_half_orc_male.png        — corretto
```

### Fallback chain (più specifico → meno specifico)
1. `{class}_{race}_{gender}.png`
2. `{class}_{race}.png`
3. `{class}_{gender}.png`
4. `{class}.png`
5. (nessuno) → SVG Vitruviano fallback

Il resolver pesca il primo match nel manifest.

### Cosa NON serve
- Race fuori dalle 9 PHB → resolver fallback su class-only, non serve generare file race-specifici per `Aasimar`/`Genasi`/etc.
- Subclass (es. `wizard_evocation_*`) → fuori scope, non riconosciuto dal resolver.
- Tutte custom class PG → SVG fallback hardcoded.

## 3. Specs immagini

| Proprietà | Valore consigliato |
|---|---|
| Formato | PNG-24 con alpha |
| Sfondo | Trasparente (alpha 0) |
| Ratio | ~5:9 verticale (compatibile con SVG `viewBox="0 0 200 360"`) |
| Risoluzione | 600×1080 px (retina) o minimo 400×720 px |
| Color profile | sRGB |
| Compressione | PNG ottimizzato (`pngquant -Q 80-95` o `oxipng -o 4`) |

### Render size nel componente
`PaperDoll` usa `<img className="max-h-[320px] w-auto object-contain" style={{ filter: 'drop-shadow(0 0 8px rgba(212,175,55,0.4))' }}>`.

⚠️ Il drop-shadow gold viene **applicato runtime via CSS**. Disegnare l'immagine **senza glow/aura interno** — altrimenti raddoppia.

### Stile coerente
- Personaggio in posa **frontale neutra**, braccia leggermente staccate dal corpo (mostrare slot equipment senza occlusione).
- Stile coerente tra tutte le immagini: stesso lighting, stesso schema cromatico, stesso livello di dettaglio.
- Palette consigliata: tonalità terra/bronzo/oro per matchare tema D&D (vedi `webapp/src/index.css` variabili `--dnd-*` per riferimento colori).
- Eviare elementi che escono dal frame (capigliature lunghe orizzontali, mantelli larghi).

## 4. Pipeline ComfyUI consigliata

ComfyUI MCP server è disponibile in questo ambiente. Skill rilevanti:
- `comfy:z-image-txt2img` — fast, ottimo per character portrait stylizzato
- `comfy:flux-txt2img` — più realismo, fotografico
- `comfy:qwen-txt2img` — alternativa moderna
- `comfy:prompt-engineering` — guida prompt syntax
- `comfy:gen` — wrapper one-shot generation

### Modello consigliato per coerenza stilistica
**Flux.1 Dev (SRPO)** + LoRA character-art o **Z-Image** con LoRA fantasy-portrait.

Il critico è la **consistency**: stesso modello + stesso seed-base + stesso lighting per tutte le 200+ combinazioni. Variare solo classe/race/gender nel prompt.

### Prompt template

Base immutabile (per tutte le immagini):
```
{character description}, full body portrait, frontal pose, arms slightly
away from torso, neutral standing pose, transparent background, isolated
on transparent, soft rim light, fantasy character art, dnd 5e illustration,
detailed, painterly, high quality, centered composition, head to toe visible
```

Negative immutabile:
```
text, watermark, signature, frame, border, multiple characters, cropped,
out of frame, low quality, blurry, worst quality, glow effect, aura,
floating particles, dynamic pose, action pose, extreme angle
```

Per ogni combinazione, il `{character description}` è composto da:
```
{gender} {race} {class}, {class-specific equipment hints},
{race-specific features}
```

### Esempi di character description

```
wizard_elf_female:
"female elf wizard, slender frame, long pointed ears, holding a wooden
staff, wearing a hooded robe with arcane embroidery, leather satchel,
silver-blonde hair"

fighter_human_male:
"male human fighter, muscular build, plate armor with dnd-style fauld
and pauldrons, longsword sheathed at hip, weathered face, short brown hair"

barbarian_half_orc_male:
"male half-orc barbarian, towering muscular figure, green skin, lower
tusks, fur-lined leather armor, two-handed greataxe, scarred body,
mohawk braided hair"

cleric_dwarf_female:
"female dwarf cleric, stocky frame, intricate braided beard, chainmail
under tabard with holy symbol, ornate war-mace, healing herb pouch"

rogue_halfling_male:
"male halfling rogue, small stature, leather armor with hood up,
dual daggers crossed at back, mischievous expression, curly hair"
```

### Settings ComfyUI consigliati

**Z-Image Turbo (veloce, buona qualità)**:
- Steps: 8 (turbo LoRA)
- CFG: 1.0
- Sampler: `euler`, scheduler: `simple`
- Resolution: 512×896 (poi upscale a 600×1080)
- Seed-base: fisso (es. `42`), incrementare per variazioni

**Flux.1 Dev (qualità migliore, più lento)**:
- Steps: 20–28
- Guidance: 3.5
- Sampler: `euler`, scheduler: `beta` o `normal`
- Resolution: 768×1344 (poi downscale)

### Background removal

Modelli text-to-image generano **fondi soft**, non trasparenti. Strategie:

**Strategia A — In-pipeline (consigliata)**:
- Usa `RembgNode` (custom node `comfyui_rembg`) o `BiRefNetUltra` direttamente nel workflow ComfyUI.
- Modello: `birefnet_general` o `u2net_human_seg` per character isolation.
- Output diretto PNG con alpha.

**Strategia B — Post-processing**:
- Genera PNG opaco.
- Esegui rembg CLI: `rembg i input.png output.png` (modello `birefnet-general`).
- Verifica edge quality — applicare `--alpha-matting` se serve sharper edges.

**Strategia C — Manuale (per art curato)**:
- Generate a 1024×1792, refine in Photoshop/Krita, manuale alpha mask.
- Lento ma massima qualità.

### Batch generation

Per 12 classi × 9 races × 2 genders = 216 immagini totali (massimo).
Realisticamente: 12 classi × 5 races (human/elf/dwarf/halfling/half_orc) × 2 genders = **120 immagini** è target reasonable per coverage decente.

Workflow batch consigliato:
1. Compila CSV con tutte le combinazioni `class,race,gender,description`.
2. Usa skill `comfy:batch` con XY-plot wildcards o script Python con ComfyUI API.
3. Generate batch overnight.
4. Quality check manuale → scarta/regenera quelle scarse.
5. Background removal batch via rembg CLI.
6. PNG optimize: `oxipng -o 4 -r webapp/public/silhouettes/`.

## 5. Verifica e testing

### A. Verifica naming
```bash
ls webapp/public/silhouettes/ | grep -E '^[a-z_]+\.png$' | sort
```
Tutti i nomi devono matchare regex. Spazi, maiuscole, trattini = no.

### B. Verifica resolver locale
1. `cd webapp && npm run dev`
2. Apri `http://localhost:5173/`, naviga su `/char/<id>` con classe canonica.
3. Tab Equipment → silhouette PNG appare invece di SVG.
4. Cambia race/gender da Identity → silhouette aggiorna a render successivo.
5. Test fallback: PG con classe custom → SVG.

### C. Verifica manifest
```bash
cat webapp/src/data/silhouette-manifest.json
```
Deve elencare i PNG attuali (sorted, lowercase). Vuoto `[]` = directory vuota o script non eseguito.

### D. Quick smoke test single asset
Drop placeholder `wizard.png` (1×1 transparent OK):
```bash
# minimal transparent png
printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfa\xcf\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82' > webapp/public/silhouettes/wizard.png
```
Restart `npm run dev`, apri PG wizard → conferma `<img>` renderizza.

## 6. Deployment

1. Drop nuove PNG in `webapp/public/silhouettes/`.
2. `cd webapp && npm run build:prod` — rigenera manifest e bundle prod in `docs/app/`.
3. Restore `.env.local` a `127.0.0.1:8000` (quirk script build:prod).
4. Commit:
   ```bash
   git add webapp/public/silhouettes/ docs/app/
   git commit -m "feat(webapp): add silhouettes for {class/race/gender batch}"
   ```
5. Push branch → PR → merge → GitHub Pages serve via `/DnD-Adventurers-Tome-TGBot/app/silhouettes/...`.

## 7. Pitfalls noti

| Problema | Causa | Fix |
|---|---|---|
| PNG non appare nemmeno con file presente | Manifest stale (dev server non riavviato dopo drop) | Restart `npm run dev` |
| URL 404 in prod | `BASE_URL` mismatch | Rebuild via `npm run build:prod`, verifica path nel bundle |
| Silhouette tagliata in basso | Aspect ratio sbagliato | Generate a ratio ~5:9, max-h-320 con object-contain |
| Glow doppio | Drop-shadow CSS + glow nell'immagine | Generate senza glow, lascia drop-shadow CSS |
| Naming sbagliato → fallback su SVG | Typo case/separator | Verifica `ls` + test resolver console.log |
| Race italiana custom non matcha | Non in `RACE_SLUG_MAP` | Aggiungi alias in `webapp/src/lib/silhouette.ts` (richiede recompile) |

## 8. Estensione futura

### Aggiungere race custom (es. Aasimar)
1. Genera arte: `wizard_aasimar_female.png` etc.
2. In `webapp/src/lib/silhouette.ts` aggiungi al `RACE_SLUG_MAP`:
   ```ts
   aasimar: 'aasimar', aasimara: 'aasimar', // Italian aliases se servono
   ```
3. Drop PNG, rebuild.

### Subclass-specific (NON supportato attualmente)
Richiede modifica resolver per matchare `class_subclass_race_gender.png`. Out of scope plan corrente.

### Skin tone variants (NON supportato)
Richiede ulteriore dimensione nel naming. Considerare estensione con suffix `_v1/v2/v3` random pick lato resolver.

## 9. Riferimenti

- Spec design: `docs/superpowers/specs/2026-04-29-character-menu-fixes-design.md` § 5
- Plan implementazione: `docs/superpowers/plans/2026-04-29-character-menu-fixes.md` Phase 5 (Tasks 12–16)
- Resolver source: `webapp/src/lib/silhouette.ts`
- ComfyUI skills (Claude Code): `comfy:z-image-txt2img`, `comfy:flux-txt2img`, `comfy:prompt-engineering`, `comfy:batch`
