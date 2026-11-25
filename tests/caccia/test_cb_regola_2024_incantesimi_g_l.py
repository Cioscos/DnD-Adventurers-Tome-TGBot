"""Controlli della zona regola:2024/incantesimi-G-L (parte incantesimi-g-l)."""
import json
from pathlib import Path

import pytest

from core.rules.catalog.spells import SPELL_EFFECTS
from core.rules.condition_removal import spell_removal
from core.rules.spell_healing import healing_spec

_CATALOGO = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells-2024.json"
_SRD = {s["index"]: s for s in json.loads(_CATALOGO.read_text(encoding="utf-8"))["items"]}


def _dal_catalogo(indice: str) -> dict:
    """La riga del catalogo SRD 2024 come la scrive la webapp quando il giocatore la aggiunge (spellToForm, catalog.ts)."""
    e = _SRD[indice]
    materiale = (e.get("material") or {}).get("it") or ""
    componenti = ", ".join(e["components"]) + (f" ({materiale.rstrip('.')})" if materiale and "M" in e["components"] else "")
    corpo = {"name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
             "components": componenti, "is_concentration": e["concentration"], "is_ritual": e["ritual"],
             "damage_dice": e.get("damage_dice"), "damage_type": e.get("damage_type"), "attack_save": e.get("attack_type"),
             "school": e.get("school"), "srd_index": indice,
             "higher_levels_dice": e.get("higher_levels_dice") if e.get("damage_dice") else None,
             "is_prepared": e["level"] > 0}
    return {k: v for k, v in corpo.items() if v not in (None, "")}


async def _pg(client, classe, livello, sottoclasse=None, **punteggi) -> int:
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": "2024", "initial_class": {
        "class_name": classe, "level": livello, "subclass": sottoclasse}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _impara(client, cid, indice) -> int:
    r = await client.post(f"/characters/{cid}/spells", json=_dal_catalogo(indice))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _riga(client, cid, indice) -> dict | None:
    return next((s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == indice), None)


async def _due_concentrazioni(client, slot):
    """Un bardo 2024 concentrato su Immagine Silenziosa lancia Immagine Maggiore con uno slot ``slot``: (risposta, silenziosa, maggiore)."""
    cid = await _pg(client, "bard", 17)
    silenziosa = await _impara(client, cid, "silent-image")
    maggiore = await _impara(client, cid, "major-image")
    assert (await client.post(f"/characters/{cid}/spells/{silenziosa}/use", json={"slot_level": 1})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{maggiore}/use", json={"slot_level": slot, "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    return r.json(), silenziosa, maggiore


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3761", fonte="2024 · Incantesimi · Immagine Maggiore · pag. 295", zona="regola:2024/incantesimi-G-L", voce="limiti",
                    copre=["carta:2024/spells.md#Immagine Maggiore", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("slot", [4, 9])
async def test_immagine_maggiore_2024_dal_quarto_livello_non_toglie_la_concentrazione_in_corso(client, slot):
    esito, silenziosa, _ = await _due_concentrazioni(client, slot)
    # dal 4° dura finché non è dissolta, senza concentrazione: quella su Immagine Silenziosa resta
    assert esito["concentrating_spell_id"] == silenziosa


@pytest.mark.caccia(id="CB-3762", fonte="2024 · Incantesimi · Lama infuocata · pag. 275", zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Lama infuocata", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_il_danno_di_lama_infuocata_2024_somma_il_modificatore_da_incantatore(client, dadi):
    cid = await _pg(client, "druid", 3, wisdom=16)  # Saggezza +3
    sid = await _impara(client, cid, "flame-blade")
    dadi(2, 2, 2)
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": 2})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 6 + 3  # 3d6 più il modificatore da incantatore


@pytest.mark.caccia(id="CB-3763", fonte="2024 · Incantesimi · Guida · pag. 282; Glossario · Nascondersi · pag. 368", zona="regola:2024/incantesimi-G-L",
                    voce="interazione",
                    copre=["carta:2024/spells.md#Guida", "carta:2024/general.md#Hide [Action] (Nascondersi) (pag. 368)",
                           "POST /characters/{char_id}/spells", "POST /characters/{char_id}/hide", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3763: difforme dal manuale, confermato")
async def test_guida_presa_dal_catalogo_2024_ha_la_componente_verbale_e_fa_finire_il_nascondiglio(client):
    cid = await _pg(client, "cleric", 1)
    sid = await _impara(client, cid, "guidance")
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 20})).status_code == 200
    r = await client.post(f"/characters/{cid}/hide")
    assert r.status_code == 200, r.text
    assert r.json()["conditions"].get("invisible") is True
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"choices": {"skill": "athletics"}})
    assert r.status_code == 200, r.text
    # Guida ha V, S: un incantesimo con componente verbale fa finire l'Invisibilità del nascondiglio
    assert r.json()["conditions"].get("invisible") is not True


@pytest.mark.caccia(id="CB-3764", fonte="2024 · Incantesimi · Glifo di interdizione · pag. 279", zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Glifo di interdizione", "POST /characters/{char_id}/spells",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(3, "5d8"), (5, "7d8")])
@pytest.mark.xfail(strict=True, reason="CB-3764: difforme dal manuale, confermato")
async def test_le_rune_esplosive_del_glifo_2024_tirano_5d8_del_tipo_scelto_piu_1d8_per_slot(client, slot, dadi_attesi):
    cid = await _pg(client, "cleric", 9)
    sid = await _impara(client, cid, "glyph-of-warding")
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={
        "slot_level": slot, "choices": {"glyph": "explosive", "damage_type": "fire"}, "confirm": ["material_consumed"]})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": slot})
    assert r.status_code == 200, r.text  # oggi 400: la riga del catalogo 2024 non ha dadi di danno
    assert (r.json()["scaled_dice"], r.json()["damage_type"]) == (dadi_attesi, "fire")


@pytest.mark.caccia(id="CB-3765", fonte="2024 · Incantesimi · Inviare · pag. 314; Stregone · Incantesimi Psionici · pag. 145",
                    zona="regola:2024/incantesimi-G-L", voce="edizioni",
                    copre=["carta:2024/spells.md#Inviare",
                           "carta:2024/classes/sorcerer.md#Incantesimi Psionici / Psionic Spells (Stregoneria Aberrante 3, pag. 145)",
                           "POST /characters"])
async def test_inviare_concesso_a_un_personaggio_2024_e_istantaneo(client):
    cid = await _pg(client, "sorcerer", 5, "Stregoneria Aberrante")
    riga = await _riga(client, cid, "sending")
    assert riga is not None
    assert riga["duration"] == "Istantanea"  # il 2024 non dura più 1 round


@pytest.mark.caccia(id="CB-3766", fonte="2024 · Incantesimi · Individuazione dei Pensieri · pag. 262; Stregone · Incantesimi Psionici · pag. 145",
                    zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Individuazione dei Pensieri",
                           "carta:2024/classes/sorcerer.md#Incantesimi Psionici / Psionic Spells (Stregoneria Aberrante 3, pag. 145)",
                           "POST /characters"])
async def test_individuazione_dei_pensieri_concessa_dichiara_il_tiro_salvezza(client):
    cid = await _pg(client, "sorcerer", 3, "Stregoneria Aberrante")
    riga = await _riga(client, cid, "detect-thoughts")
    assert riga is not None
    assert riga["attack_save"] == "SAVE"  # sondare più a fondo: TS Saggezza contro la CD di chi lancia


@pytest.mark.caccia(id="CB-3767", fonte="2024 · Incantesimi · Legame Telepatico di Rary · pag. 311; Stregone · Incantesimi Psionici · pag. 145",
                    zona="regola:2024/incantesimi-G-L", voce="interazione",
                    copre=["carta:2024/spells.md#Legame Telepatico di Rary",
                           "carta:2024/classes/sorcerer.md#Incantesimi Psionici / Psionic Spells (Stregoneria Aberrante 3, pag. 145)",
                           "POST /characters/{char_id}/spells", "POST /characters"])
@pytest.mark.xfail(strict=True, reason="CB-3767: difforme dal manuale, confermato")
async def test_legame_telepatico_concesso_non_duplica_quello_gia_preso_dal_catalogo(client):
    cid = await _pg(client, "sorcerer", 8, "Stregoneria Aberrante")
    await _impara(client, cid, "telepathic-bond")
    r = await client.patch(f"/characters/{cid}/classes/{(await _scheda(client, cid))['classes'][0]['id']}", json={"level": 9})
    assert r.status_code == 200, r.text
    righe = [s for s in (await client.get(f"/characters/{cid}/spells")).json() if "Rary" in s["name"]]
    # lo stesso incantesimo: la riga del catalogo diventa sempre preparata, senza una seconda copia
    assert len(righe) == 1, [(s["name"], s["srd_index"]) for s in righe]


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3768", fonte="2024 · Incantesimi · Infliggere ferite · pag. 288", zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Infliggere ferite", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(1, "2d10"), (3, "4d10"), (9, "10d10")])
async def test_infliggere_ferite_2024_tira_2d10_necrotici_piu_1d10_per_slot_e_dimezza_col_ts(client, slot, dadi_attesi):
    cid = await _pg(client, "cleric", 17)
    sid = await _impara(client, cid, "inflict-wounds")
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert (corpo["scaled_dice"], corpo["damage_type"], corpo["save_halves"]) == (dadi_attesi, "necrotic", True)


@pytest.mark.caccia(id="CB-3769", fonte="2024 · Incantesimi · Guida · pag. 282", zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Guida", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/last-roll/options"])
async def test_guida_2024_somma_1d4_a_ogni_prova_dell_abilita_scelta_e_solo_a_quella(client):
    cid = await _pg(client, "cleric", 1)
    sid = await _impara(client, cid, "guidance")
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"choices": {"skill": "athletics"}})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == sid
    for _ in range(2):  # non si spegne al primo d4: vale per tutta la durata
        prima = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10})
        assert prima.status_code == 200, prima.text
        r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["spell:guidance:add"]})
        assert r.status_code == 200, r.text
        assert 1 <= r.json()["total"] - prima.json()["total"] <= 4
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "stealth"})
    assert r.status_code == 200, r.text
    assert "spell:guidance:add" not in [o["key"] for o in r.json()]


@pytest.mark.caccia(id="CB-3770", fonte="2024 · Incantesimi · Invisibilità · pag. 289; Invisibilità superiore · pag. 281",
                    zona="regola:2024/incantesimi-G-L", voce="limiti",
                    copre=["carta:2024/spells.md#Invisibilità", "carta:2024/spells.md#Invisibilità superiore"])
def test_invisibilita_2024_una_creatura_in_piu_per_slot_e_la_superiore_non_finisce_attaccando():
    invisibilita, superiore = SPELL_EFFECTS["invisibility"], SPELL_EFFECTS["greater_invisibility"]
    assert [invisibilita.max_targets("2024", s) for s in (2, 3, 9)] == [1, 2, 8]
    assert [superiore.max_targets("2024", s) for s in (4, 9)] == [1, 1]
    v, sup = invisibilita.variants["2024"], superiore.variants["2024"]
    assert (v.condition, v.concentration, v.rounds, v.ends_on) == ("invisible", True, 600, ("attack", "cast", "manual"))  # 1 ora
    assert (sup.condition, sup.concentration, sup.rounds, sup.ends_on) == ("invisible", True, 10, ("manual",))  # 1 minuto


@pytest.mark.caccia(id="CB-3771", fonte="2024 · Incantesimi · Guarigione di Massa · pag. 296", zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Guarigione di Massa"])
def test_guarigione_di_massa_2024_ridà_700_pf_fissi_e_toglie_accecato_assordato_avvelenato():
    cura = healing_spec("mass-heal", "2024")
    assert (cura.dice, cura.fixed, cura.add_mod) == (None, 700, False)
    togli = spell_removal("2024", "mass-heal")
    assert set(togli.conditions) == {"blinded", "deafened", "poisoned"} and togli.count is None


@pytest.mark.caccia(id="CB-3772", fonte="2024 · Incantesimi · Grandine di spine · pag. 283", zona="regola:2024/incantesimi-G-L", voce="limiti",
                    copre=["carta:2024/spells.md#Grandine di spine", "GET /characters/{char_id}/roll-options"])
async def test_grandine_di_spine_2024_dopo_il_colpo_a_distanza_1d10_per_livello_di_slot_senza_tetto(client):
    cid = (await client.post("/characters", json={"name": "Arciere", "rules_edition": "2024"})).json()["id"]
    await _impara(client, cid, "hail-of-thorns")
    for livello in range(1, 8):
        assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": livello, "total": 1})).status_code in (200, 201)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Arco", "item_type": "weapon",
                                                            "item_metadata": {"damage_dice": "1d8", "weapon_type": "ranged", "properties": []}})
    assert r.status_code == 201, r.text
    arco = max(i["id"] for i in r.json()["items"])
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": arco})
    assert r.status_code == 200, r.text
    grandine = next(o for o in r.json() if o["key"] == "spell:hail_of_thorns:hit")
    assert {s["level"]: s["dice"] for s in grandine["input_options"]} == {n: f"{n}d10" for n in range(1, 8)}
    assert SPELL_EFFECTS["hail_of_thorns"].variants["2024"].concentration is False  # istantanea


@pytest.mark.caccia(id="CB-3773", fonte="2024 · Incantesimi · Immagine Maggiore · pag. 295", zona="regola:2024/incantesimi-G-L", voce="limiti",
                    copre=["carta:2024/spells.md#Immagine Maggiore", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_immagine_maggiore_2024_al_terzo_livello_richiede_ancora_concentrazione(client):
    esito, _, maggiore = await _due_concentrazioni(client, 3)
    assert esito["concentrating_spell_id"] == maggiore


@pytest.mark.caccia(id="CB-3774", fonte="2024 · Incantesimi · Libertà di movimento · pag. 277", zona="regola:2024/incantesimi-G-L", voce="limiti",
                    copre=["carta:2024/spells.md#Libertà di movimento"])
def test_liberta_di_movimento_2024_un_ora_senza_concentrazione_nuoto_e_un_bersaglio_in_piu_per_slot():
    liberta = SPELL_EFFECTS["freedom_of_movement"]
    assert [liberta.max_targets("2024", s) for s in (4, 5, 9)] == [1, 2, 6]
    v = liberta.variants["2024"]
    assert (v.concentration, v.rounds) == (False, 600)
    assert [m.target for m in v.modifiers({})] == ["swim_speed"]
