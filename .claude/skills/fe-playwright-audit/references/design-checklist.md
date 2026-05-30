# Design checklist — regole nominate → controlli visivi

Le 8 regole nominate di `DESIGN.md` (root del progetto) tradotte in controlli verificabili
da uno screenshot full-page. `DESIGN.md` resta la fonte di verità: in caso di dubbio leggilo.
Quando trovi una violazione, registrala come finding citando la regola **per nome**.

North Star: **"Illuminated Manuscript Noir"** — inchiostro marrone caldo + pergamena,
oro applicato con parsimonia. Mai `#000` né `#fff`. Priorità: epica > leggibile > calma >
tattile; quando confliggono, vince la leggibilità.

## Palette di riferimento (per riconoscere i colori negli screenshot)

- **Oro** `#d4a847` (bright `#f0c970`, dim `#8b7335`) — affordance primaria + ornamento + focus.
- **Superfici**: ink `#1a1512` → surface `#241d18` → raised `#2f261f` → lifted `#3b3026`.
  Bordi `#4a3d30` / `#6b5841`. Pergamena (light mode) `#f4e8c1`.
- **Semantici**: crimson `#b33a3a` (danno), emerald `#3fa66a` (cura), arcane `#9b59b6` (magia),
  cobalt `#3a7ca5` (info), amber `#e8a547` (highlight raro).

## Le 8 regole

### 1. Gold Leaf
L'oro è **solo** affordance primaria (bottone primario, sigillo pagina attiva, focus halo,
underline dell'header) e ornamento. Deve coprire **<10%** della schermata.
- ❌ Segnala: oro usato come decorazione diffusa, due+ elementi che competono per l'oro
  sulla stessa schermata, oro su superfici grandi, gradient oro su testo.

### 2. Two Inks
Superfici = famiglia marrone caldo; ornamento = oro. Mai mescolati sullo stesso elemento.
- ❌ Segnala: superfici tinte d'oro, oro "sporcato" di marrone, card con fill oro.

### 3. Semantic Triad
Crimson/Emerald/Arcane riservati al loro **significato** (danno/cura/magia). Mai decorativi.
- ❌ Segnala: crimson/emerald/arcane usati "per dare colore" dove non c'è quel significato.
  Per dare interesse visivo si usa elevazione o ornamento, non colore semantico preso in prestito.

### 4. Inscription
Cinzel per elementi **inscritti** (titoli, label, chip, testo dei bottoni). Fraunces per il
testo lungo (descrizioni, narrativa). JetBrains Mono per i numeri.
- ❌ Segnala: paragrafi in Cinzel, label in Fraunces, font di sistema sans evidente.

### 5. Tabular Numerics
Qualsiasi numero che si **confronta** con un altro (HP/maxHP, tiri di dado, componenti AC,
totali monete) è in JetBrains Mono con cifre tabulari allineate.
- ❌ Segnala: numeri proporzionali dentro una riga di confronto, cifre disallineate in colonna,
  HP/AC/tiri non monospaziati.

### 6. No Gradient Text
Testo con gradiente vietato, **tranne** un singolo glifo ornamentale per pagina (flourish
dell'header). Body, heading, label, bottoni, numeri = colore pieno.
- ❌ Segnala: heading/label/bottoni/numeri con `background-clip: text` o shimmer dorato.

### 7. Warm-Shadow
Le ombre sono tinte marrone caldo (`rgba(26,16,8, .25–.45)`), mai grigio neutro né nero puro.
- ❌ Segnala: drop-shadow grigio/nero (fa "screenshot di dialog box", non "pagina sollevata dal tomo").

### 8. Halo-as-Signal
Gli halos (glow gold/arcane/danger) significano "agisci ora": focus-visible, concentrazione
attiva, HP=0/death-save. Mai decorativi, mai solo-hover, **max 1 halo per schermata**.
- ❌ Segnala: halo decorativi, due halos contemporanei sulla stessa schermata.

## Controlli aggiuntivi dai Do/Don't (sempre da DESIGN.md §6)

- ❌ Bordi laterali colorati (`border-left/right` > 1px come accento) su card/list/alert — **banditi**.
- ❌ Glassmorphism (`backdrop-filter: blur`) decorativo — ammesso solo sul backdrop dei dialog.
- ❌ Easing elastico/bounce fuori dal dice-roller; nessun "outBack" sulle transizioni di layout.
- ❌ `#000`/`#fff` da nessuna parte.
- ❌ Ornamenti ripetuti (corner flourishes, ornament line) dentro le liste di contenuto.
- ❌ Em dash nei testi UI (usare virgole, due punti, punto e virgola, parentesi).
- ✅ Cliché da evitare attivamente: SaaS-cream (card neutre + accento blu + tutto rounded-2xl),
  D&D Beyond (rosso neon su nero puro), Roll20/"WordPress 2014", gacha mobile (particelle/coin),
  AI-slop (hero card tinta + heading gradient + griglie di card identiche + glassmorphism).
- ✅ Bottoni: shape `rounded-12px`, mai pill, mai spigoli vivi; min 40px (44px per azioni distruttive).
- ✅ Ogni stato semantico accoppia colore + icona + label (anche per daltonici).
- ✅ Light mode "pergamena invecchiata" trattata con lo stesso rigore del dark — non è un flip di contrasto.
