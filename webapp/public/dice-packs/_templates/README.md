# UV templates per ComfyUI

I PNG in questa cartella sono **template UV** generati una-tantum dallo script
`webapp/scripts/generate-uv-templates.mjs`. Ogni PNG mostra una griglia di celle
numerate (1..N) che corrisponde alla mappatura UV di un dado specifico.

## Workflow per creare un pack custom

1. Apri `<kind>.uv.png` come ControlNet input (Canny o Depth) in ComfyUI.
2. Prompt tematico, es. per "hell dice":
   ```
   molten lava texture, embers, hellish theme, glowing cracks,
   1024x1024, seamless cells, dark background between cells
   ```
3. Output: `<kind>.albedo.png` con stesso layout celle.
4. (Opzionale) Per **normal map**: usa nodo ComfyUI `Image to Normal` →
   `<kind>.normal.png`.
5. (Opzionale) Per **roughness**: desatura albedo + inverti, o nodo
   `Image to Roughness` → `<kind>.roughness.png`.
6. (Opzionale) Per **emissive** (zone "calde"): isola via mask le zone
   luminose dell'albedo, salva PNG con nero sui non-emissivi →
   `<kind>.emissive.png`.

## Installazione del pack

1. Crea cartella `webapp/public/dice-packs/<pack_id>/`.
2. Copia i PNG generati lì.
3. Crea `pack.json` (vedi schema in `webapp/src/dice/packs/manifest.ts`).
4. Aggiungi `<pack_id>` a `BUNDLED_PACKS` in `webapp/src/dice/packs/registry.ts`.
5. Esegui `npm run build:prod` per inserirli nel bundle prod.
6. In Settings → Dice pack, seleziona il nuovo pack.

## Rigenerare i template

I template **non vanno modificati a mano**. Per rigenerarli (ad es. dopo
cambio layout):

```bash
node webapp/scripts/generate-uv-templates.mjs
```

Il layout grid è definito in `webapp/src/dice/geometries/uvLayouts.ts` —
deve restare in sync con questo script.
