"""Controlli della zona regola:2014/talenti."""
import pytest

from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_2014_fighter import _fighter
from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _spell, _take


async def _incompleto(client, cid: int, key: str, ability: str | None = None) -> dict:
    r = await _take(client, cid, key, ability)
    assert r.status_code == 201, r.text
    return next(a for a in _feat_rows(r.json(), key) if a["feat_status"] == "incomplete")


async def _classe(client, cid: int) -> int:
    return (await _full(client, cid))["classes"][0]["id"]


async def _rituale(client, cid: int, nome: str, indice: str, class_id: int, **extra) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": nome, "level": 1, "srd_index": indice, "is_ritual": True, "casting_time": "1 azione", "class_id": class_id, **extra})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _incantatore_rituale(client, cid: int) -> None:
    """Incantatore Rituale con la lista del mago: Allarme e Identificare nel libro dei rituali."""
    row = await _incompleto(client, cid, "ritual_caster")
    libro = [{**_spell("Allarme", 1, "alarm"), "is_ritual": True}, {**_spell("Identificare", 1, "identify"), "is_ritual": True}]
    r = await _complete(client, cid, row["id"], {"list": "wizard"}, libro)
    assert r.status_code == 200, r.text


async def _scudo(client, cid: int) -> None:
    r = await client.post(f"/characters/{cid}/items", json={"name": "Scudo", "item_type": "shield", "item_metadata": {"ac_value": 2}})
    iid = next(i["id"] for i in r.json()["items"] if i["name"] == "Scudo")
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "off_hand"})
    assert r.status_code == 200, r.text


def _punteggio(body: dict, nome: str) -> int:
    return next(s["value"] for s in body["ability_scores"] if s["name"] == nome)


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3011", fonte="2014 · Talenti · Fortunato · pag. 167", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Fortunato / Lucky (pag. 167)", "POST /characters/{char_id}/last-roll/options",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
async def test_fortunato_lascia_scegliere_il_d20_da_tenere(client):
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    assert (await _take(client, cid, "lucky")).status_code == 201
    tiro = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 15})
    assert tiro.status_code == 200, tiro.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["feat.lucky"], "dice": [3]})
    assert r.status_code == 200, r.text
    # Il punto fortuna fa tirare un d20 in più e il giocatore sceglie quale usare: col 3 nuovo il 15 resta il suo tiro
    assert r.json()["die"] == 15 and r.json()["total"] == tiro.json()["total"]


@pytest.mark.caccia(id="CB-3012", fonte="2014 · Talenti · Incantatore Rituale · pag. 168", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Incantatore Rituale / Ritual Caster (pag. 168)", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "PUT /characters/{char_id}/feats/{ability_id}/options"])
@pytest.mark.xfail(strict=True, reason="CB-3012: difforme dal manuale, confermato")
async def test_incantatore_rituale_non_rende_rituale_un_incantesimo_fuori_dal_libro(client):
    ch = await _char14(client, "sorcerer")  # Intelligenza 13: prerequisito del talento
    cid = ch["id"]
    sid = await _rituale(client, cid, "Individuazione del magico", "detect-magic", await _classe(client, cid))
    prima = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert prima.status_code == 400, prima.text  # lo stregone 2014 non celebra rituali
    await _incantatore_rituale(client, cid)
    dopo = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert dopo.status_code == 400, dopo.text


@pytest.mark.caccia(id="CB-3013", fonte="2014 · Talenti · Incantatore Rituale · pag. 168; Chierico · Incantesimi · pag. 58", zona="regola:2014/talenti",
                    voce="interazione",
                    copre=["carta:2014/feats.md#Incantatore Rituale / Ritual Caster (pag. 168)", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3013: difforme dal manuale, confermato")
async def test_incantatore_rituale_non_toglie_al_chierico_l_obbligo_di_preparare_i_suoi_rituali(client):
    ch = await _char14(client, "cleric")  # Saggezza 13: prerequisito del talento
    cid = ch["id"]
    sid = await _rituale(client, cid, "Purificare cibo e bevande", "purify-food-and-drink", await _classe(client, cid), is_prepared=False)
    prima = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert prima.status_code == 409 and prima.json()["detail"]["warnings"] == ["ritual_unprepared"], prima.text
    await _incantatore_rituale(client, cid)
    dopo = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert dopo.status_code == 409 and "ritual_unprepared" in dopo.json()["detail"]["warnings"], dopo.text


@pytest.mark.caccia(id="CB-3014", fonte="2014 · Talenti · Incantatore da Guerra · pag. 168; Guerriero · Cavaliere Mistico · pag. 75",
                    zona="regola:2014/talenti", voce="interazione",
                    copre=["carta:2014/feats.md#Incantatore da Guerra / War Caster (pag. 168)", "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3014: difforme dal manuale, confermato")
async def test_il_cavaliere_mistico_puo_prendere_incantatore_da_guerra(client):
    cid = await _fighter(client, 3, "eldritch_knight")
    r = await _take(client, cid, "war_caster")
    assert r.status_code == 201, r.text


@pytest.mark.caccia(id="CB-3015", fonte="2014 · Talenti · Incantatore da Guerra e Iniziato alla Magia · pag. 168", zona="regola:2014/talenti",
                    voce="interazione",
                    copre=["carta:2014/feats.md#Iniziato alla Magia / Magic Initiate (pag. 168)", "POST /characters/{char_id}/feats",
                           "PUT /characters/{char_id}/feats/{ability_id}/options"])
@pytest.mark.xfail(strict=True, reason="CB-3015: difforme dal manuale, confermato")
async def test_chi_lancia_incantesimi_da_un_talento_soddisfa_il_prerequisito(client):
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    row = await _incompleto(client, cid, "magic_initiate")
    magia = [_spell("Raggio di gelo", 0, "ray-of-frost"), _spell("Mano magica", 0, "mage-hand"), _spell("Dardo incantato", 1, "magic-missile")]
    assert (await _complete(client, cid, row["id"], {"list": "wizard"}, magia)).status_code == 200
    r = await _take(client, cid, "war_caster")
    assert r.status_code == 201, r.text


@pytest.mark.caccia(id="CB-3016", fonte="2014 · Talenti · Incantatore da Guerra · pag. 168; Paladino · Incantesimi dal 2º livello · pag. 97",
                    zona="regola:2014/talenti", voce="limiti",
                    copre=["carta:2014/feats.md#Incantatore da Guerra / War Caster (pag. 168)", "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3016: difforme dal manuale, confermato")
async def test_un_paladino_di_primo_livello_non_lancia_incantesimi(client):
    ch = await _char14(client, "paladin", level=1)
    r = await _take(client, ch["id"], "war_caster")
    assert r.status_code == 422 and "feat_prerequisite_spellcasting" in r.text, r.text


@pytest.mark.caccia(id="CB-3017", fonte="2014 · Talenti · Regole generali (massimo 20) · pag. 165", zona="regola:2014/talenti", voce="limiti",
                    copre=["carta:2014/feats.md#Regole generali (pag. 165)",
                           "carta:2014/feats.md#Maestro delle Armature Pesanti / Heavy Armor Master (pag. 169-170)",
                           "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3017: difforme dal manuale, confermato")
async def test_un_talento_con_piu_uno_si_prende_anche_con_la_caratteristica_a_20(client):
    ch = await _char14(client, "fighter", strength=20)
    r = await _take(client, ch["id"], "heavy_armor_master", "strength")
    assert r.status_code == 201, r.text
    assert _punteggio(r.json(), "strength") == 20 and _feat_rows(r.json(), "heavy_armor_master")


@pytest.mark.caccia(id="CB-3018", fonte="2014 · Talenti · Maestro d'Armi · pag. 168; Equipaggiamento · Armi · pag. 149", zona="regola:2014/talenti",
                    voce="edizioni",
                    copre=["carta:2014/feats.md#Maestro d'Armi / Weapon Master (pag. 168)", "PUT /characters/{char_id}/feats/{ability_id}/options"])
@pytest.mark.parametrize(("arma", "atteso"), [("net", 200), ("pistol", 422), ("musket", 422)])
@pytest.mark.xfail(strict=True, reason="CB-3018: difforme dal manuale, confermato")
async def test_maestro_d_armi_2014_sceglie_fra_le_armi_del_manuale_2014(client, arma, atteso):
    ch = await _char14(client, "wizard")
    row = await _incompleto(client, ch["id"], "weapon_master", "dexterity")
    r = await _complete(client, ch["id"], row["id"], {"weapons": [arma, "dagger", "club", "sling"]})
    assert r.status_code == atteso, r.text


@pytest.mark.caccia(id="CB-3019", fonte="2014 · Talenti · Maestro degli Scudi · pag. 169", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Maestro degli Scudi / Shield Master (pag. 169)", "GET /characters/{char_id}/roll-options",
                           "PATCH /characters/{char_id}/conditions"])
async def test_maestro_degli_scudi_incapacitato_non_somma_lo_scudo_ai_ts(client):
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    assert (await _take(client, cid, "shield_master")).status_code == 201
    await _scudo(client, cid)
    assert "feat.shield_master" in await _roll_keys(client, cid, "save", ability="dexterity")
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert r.status_code == 200, r.text
    assert "feat.shield_master" not in await _roll_keys(client, cid, "save", ability="dexterity")


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3020", fonte="2014 · Talenti · Robusto · pag. 170", zona="regola:2014/talenti", voce="interazione",
                    copre=["carta:2014/feats.md#Robusto / Tough (pag. 170)", "POST /characters/{char_id}/classes"])
async def test_robusto_conta_il_livello_del_personaggio_in_multiclasse(client):
    ch = await _char14(client, "fighter", level=3)
    cid = ch["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 2})
    assert r.status_code in (200, 201), r.text
    prima = (await _full(client, cid))["computed"]["hp_max_effective"]
    out = await _take(client, cid, "tough")
    assert out.status_code == 201, out.text
    assert out.json()["computed"]["hp_max_effective"] == prima + 2 * 5


@pytest.mark.caccia(id="CB-3021", fonte="2014 · Talenti · Osservatore · pag. 170", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Osservatore / Observant (pag. 170)", "POST /characters/{char_id}/feats"])
async def test_osservatore_somma_cinque_alle_passive_di_percezione_e_indagare(client):
    ch = await _char14(client, "rogue", intelligence=12)
    out = await _take(client, ch["id"], "observant", "intelligence")  # 12 -> 13: il modificatore resta +1
    assert out.status_code == 201, out.text
    for abilita in ("perception", "investigation"):
        assert out.json()["passives"][abilita] == ch["passives"][abilita] + 5
    assert out.json()["passives"]["insight"] == ch["passives"]["insight"]


@pytest.mark.caccia(id="CB-3022", fonte="2014 · Talenti · Adepto Elementale · pag. 165", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Adepto Elementale / Elemental Adept (pag. 165)", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_adepto_elementale_conta_gli_uno_come_due_solo_nel_tipo_scelto(client):
    ch = await _char14(client, "wizard")
    cid = ch["id"]
    row = await _incompleto(client, cid, "elemental_adept")
    assert (await _complete(client, cid, row["id"], {"damage_type": "fire"})).status_code == 200
    danni = {}
    for nome, tipo in (("Dardo di fuoco", "fire"), ("Raggio di gelo", "cold")):
        r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "level": 0, "damage_dice": "1d10", "damage_type": tipo,
                                                                 "attack_save": "ATK"})
        out = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/roll_damage", json={"main_rolls": [1]})
        assert out.status_code == 200, out.text
        danni[tipo] = out.json()["total"]
    assert danni == {"fire": 2, "cold": 1}


@pytest.mark.caccia(id="CB-3023", fonte="2014 · Talenti · Fortunato · pag. 167", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Fortunato / Lucky (pag. 167)", "POST /characters/{char_id}/rest"])
async def test_fortunato_tre_punti_che_tornano_solo_col_riposo_lungo(client, test_session_factory):
    from core.db.models import Ability
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    out = await _take(client, cid, "lucky")
    riga = _feat_rows(out.json(), "lucky")[0]
    assert (riga["max_uses"], riga["uses"]) == (3, 3)
    async with test_session_factory() as s:
        (await s.get(Ability, riga["id"])).uses = 0
        await s.commit()
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert _feat_rows(await _full(client, cid), "lucky")[0]["uses"] == 0
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert _feat_rows(await _full(client, cid), "lucky")[0]["uses"] == 3


@pytest.mark.caccia(id="CB-3024", fonte="2014 · Talenti · Resiliente · pag. 170", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Resiliente / Resilient (pag. 170)", "POST /characters/{char_id}/feats"])
async def test_resiliente_piu_uno_e_competenza_nel_tiro_salvezza(client):
    ch = await _char14(client, "fighter")
    out = await _take(client, ch["id"], "resilient", "wisdom")
    assert out.status_code == 201, out.text
    assert _punteggio(out.json(), "wisdom") == 14 and out.json()["saving_throws"]["wisdom"] is True


@pytest.mark.caccia(id="CB-3025", fonte="2014 · Talenti · Tenace · pag. 170", zona="regola:2014/talenti", voce="limiti",
                    copre=["carta:2014/feats.md#Tenace / Durable (pag. 170)", "POST /characters/{char_id}/hit_dice/spend"])
@pytest.mark.parametrize(("costituzione", "curati"), [(8, 2), (16, 6)])
async def test_tenace_cura_almeno_il_doppio_della_costituzione_minimo_due(client, costituzione, curati):
    ch = await _char14(client, "fighter", constitution=costituzione)
    cid = ch["id"]
    out = await _take(client, cid, "durable", "constitution")  # 8 -> 9 (-1), 16 -> 17 (+3)
    assert out.status_code == 201, out.text
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})
    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"count": 1, "rolls": [1], "class_id": out.json()["classes"][0]["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == curati


@pytest.mark.caccia(id="CB-3026", fonte="2014 · Talenti · Condottiero Ispiratore · pag. 167", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Condottiero Ispiratore / Inspiring Leader (pag. 167)", "POST /characters/{char_id}/rest"])
async def test_condottiero_ispiratore_livello_piu_carisma_non_si_somma(client):
    ch = await _char14(client, "bard", level=6, charisma=16)
    cid = ch["id"]
    assert (await _take(client, cid, "inspiring_leader")).status_code == 201
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 3})).status_code == 200
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == 6 + 3


@pytest.mark.caccia(id="CB-3028", fonte="2014 · Talenti · Linguista · pag. 168", zona="regola:2014/talenti", voce="ripetizione",
                    copre=["carta:2014/feats.md#Linguista / Linguist (pag. 168)", "PUT /characters/{char_id}/feats/{ability_id}/options"])
async def test_linguista_completato_due_volte_non_da_sei_linguaggi(client):
    ch = await _char14(client, "wizard")
    cid = ch["id"]
    row = await _incompleto(client, cid, "linguist", "intelligence")
    primo = await _complete(client, cid, row["id"], {"languages": ["Elfico", "Nanico", "Draconico"]})
    assert primo.status_code == 200, primo.text
    lingue = primo.json()["languages"]
    secondo = await _complete(client, cid, row["id"], {"languages": ["Gigante", "Orchesco", "Silvano"]})
    assert secondo.status_code == 409, secondo.text
    assert (await _full(client, cid))["languages"] == lingue
