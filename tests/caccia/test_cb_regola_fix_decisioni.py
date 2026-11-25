"""Controlli delle decisioni dell'utente D-021…D-052 (tests/caccia/decisioni.md), scritti nel giro che le applica."""
import pytest

from tests.integration._encounter_helpers import PLAYER_ID, as_user


async def _pg(client, edizione: str, classe: str | None = None, livello: int = 1, sottoclasse: str | None = None, **punteggi) -> int:
    corpo = {"name": "Prova", "rules_edition": edizione}
    if classe:
        corpo["initial_class"] = {"class_name": classe, "level": livello, "subclass": sottoclasse}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _turno(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


@pytest.mark.caccia(id="CB-4601", fonte="decisione D-021 (tests/caccia/decisioni.md): nel 2024 «Termina» l'Ira è gratis; 2024 · Barbaro · Ira · pag. 51; 2014 · pag. 48",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "DELETE /characters/{char_id}/active-states/{key}"])
@pytest.mark.parametrize("edizione, speso", [("2014", True), ("2024", False)])
async def test_terminare_l_ira_a_mano_costa_l_azione_bonus_solo_nel_2014(client, edizione, speso):
    cid = await _pg(client, edizione, "barbarian", 15)  # Ira Persistente: resta accesa al turno dopo senza attacchi
    assert (await client.post(f"/characters/{cid}/features/barbarian.rage/use", json={})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
    assert (await _turno(client, cid))["bonus_used"] is speso


@pytest.mark.caccia(id="CB-4602", fonte="decisione D-022 (tests/caccia/decisioni.md): per edizione, nel 2024 il dado del Valore raddoppia sul critico e nel 2014 no; 2024 · Bardo · pag. 67; 2014 · pag. 55",
                    zona="regola:2024/bard", voce="regola",
                    copre=["carta:2024/classes/bard.md#Ispirazione in Combattimento / Combat Inspiration (Collegio del Valore 3, pag. 67)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("edizione, dadi_tirati", [("2014", 1), ("2024", 2)])
async def test_il_dado_del_valore_2024_raddoppia_sul_critico_di_un_arma(client, test_session_factory, edizione, dadi_tirati):
    from tests.integration.rules import test_2014_bard_inspiration as b14, test_2024_bard as b24
    modulo = b14 if edizione == "2014" else b24
    _sid, bard, hero = await modulo._table(client, test_session_factory, level=3, subclass=modulo.VALOR)
    assert (await b14._give(client, bard, hero)).status_code == 200
    as_user(PLAYER_ID)
    arma = await b14._sword(client, hero)
    colpo = (await client.post(f"/characters/{hero}/items/{arma}/attack", json={"die": 20, "defer_damage": True})).json()
    assert colpo["is_critical"], colpo
    r = await client.post(f"/characters/{hero}/attack/{colpo['attack_id']}/damage", json={"options": ["bardic_die:damage"]})
    assert r.status_code == 200 and len(r.json()["option_result"]["extra_rolls"]) == dadi_tirati, r.text


@pytest.mark.caccia(id="CB-4603", fonte="decisione D-028 (tests/caccia/decisioni.md): assegnare PE non abbassa mai il livello di classe; 2024 · Glossario · Punti Esperienza · pag. 366-367",
                    zona="regola:2024/generali", voce="interazione",
                    copre=["carta:2024/general.md#Experience Points (Punti Esperienza) (pag. 366-367)", "PATCH /characters/{char_id}/xp"])
async def test_un_set_di_punti_esperienza_verso_l_alto_non_toglie_livelli(client):
    cid = await _pg(client, "2024", "fighter", 5)  # 0 PE: il livello viene dalla classe
    livello = lambda r: r.json()["classes"][0]["level"]  # noqa: E731
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 300})
    assert r.status_code == 200 and livello(r) == 5
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 14000})
    assert livello(r) == 6
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 2700})  # correzione esplicita verso il basso
    assert livello(r) == 4


@pytest.mark.caccia(id="CB-4604", fonte="decisione D-034 (tests/caccia/decisioni.md): abilità doppie 2024 dopo la creazione rifiutate, come alla creazione e nel 2014",
                    zona="regola:2024/background", voce="interazione",
                    copre=["carta:2024/backgrounds.md#Nobile / Noble (pag. 183)", "POST /characters/{char_id}/classes",
                           "PUT /characters/{char_id}/feats/{ability_id}/options"])
async def test_abilita_gia_possedute_rifiutate_nel_2024_per_la_seconda_classe_e_abile(client):
    r = await client.post("/characters", json={"name": "Prova", "rules_edition": "2024", "skills": {"stealth": True, "religion": True},
                                               "initial_class": {"class_name": "fighter", "level": 4}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "rogue", "level": 1, "skill_choices": ["stealth"]})
    assert r.status_code == 422, r.status_code
    # il manuale 2024 non fa scegliere fuori dall'elenco della classe
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "rogue", "level": 1, "skill_choices": ["arcana"]})
    assert r.status_code == 422, r.status_code
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "rogue", "level": 1, "skill_choices": ["acrobatics"]})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/feats", json={"feat_key": "2024_skilled", "ability": None})
    assert r.status_code == 201, r.text
    riga = next(a["id"] for a in r.json()["abilities"] if a["feature_key"] == "feat.2024_skilled")
    for scelte, esito in ((["religion", "arcana", "history"], 422), (["tool:thieves_tools", "arcana", "history"], 422),
                          (["arcana", "history", "nature"], 200)):  # gli arnesi da scasso li dà già la multiclasse Ladro
        r = await client.put(f"/characters/{cid}/feats/{riga}/options", json={"options": {"picks": scelte}, "spells": []})
        assert r.status_code == esito, (scelte, r.status_code)


@pytest.mark.caccia(id="CB-4606", fonte="decisione D-026 (tests/caccia/decisioni.md): solo trucchetti conosciuti con Magia del Patto; 2024 · Warlock · Deflagrazione Agonizzante · pag. 155, Patto del Tomo · pag. 157",
                    zona="regola:2024/warlock", voce="regola",
                    copre=["carta:2024/classes/warlock.md#Deflagrazione Agonizzante / Agonizing Blast (Suppliche Occulte, livello 2+, trucchetto Warlock che infligge danno, pag. 155)",
                           "carta:2024/classes/warlock.md#Patto del Tomo / Pact of the Tome (Suppliche Occulte, pag. 157)"])
async def test_le_suppliche_dei_trucchetti_non_valgono_per_quelli_del_tomo_o_di_un_altra_classe(client):
    from tests.integration.rules.test_2024_warlock import TOME, _caster24, _choice, _full, _offered
    cid = await _caster24(client, 3, TOME, cantrips=("eldritch-blast",))
    tomo = _choice(await _full(client, cid), "tome_cantrips")["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Rintocco dei Morti", "srd_index": "toll-the-dead", "level": 0, "pick_id": tomo})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 1})
    assert r.status_code == 201
    mago = next(c["id"] for c in r.json()["classes"] if c["class_name"] == "wizard")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Tocco Gelido", "srd_index": "chill-touch", "level": 0, "class_id": mago})
    assert r.status_code == 201, r.text
    warlock = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"] == "warlock")
    await client.patch(f"/characters/{cid}", json={"settings": {"advancement": "milestone"}})
    r = await client.patch(f"/characters/{cid}/classes/distribute", json={"classes": [{"class_id": warlock, "level": 5}, {"class_id": mago, "level": 1}]})
    assert r.status_code == 200
    offerte = await _offered(client, cid)
    assert "eldritch_spear__eldritch_blast" in offerte  # Deflagrazione Agonizzante l'ha già scelta l'helper
    assert not {"agonizing_blast__toll_the_dead", "agonizing_blast__chill_touch"} & offerte


@pytest.mark.caccia(id="CB-4607", fonte="decisione D-029 (tests/caccia/decisioni.md): la Vista Cieca di un privilegio 2024 toglie lo svantaggio di Accecato; 2024 · Glossario · Vista Cieca e Accecato · pag. 361",
                    zona="regola:2024/generali", voce="interazione",
                    copre=["carta:2024/general.md#Blindsight (Vista Cieca) (pag. 361)", "carta:2024/general.md#Blinded [Condition] (Accecato) (pag. 361)",
                           "carta:2024/feats.md#Combattere alla cieca / Blind Fighting (pag. 209)",
                           "carta:2024/feats.md#Furtivo / Skulker (pag. 208) - Generale (livello 4+, Destrezza 13+)",
                           "carta:2024/classes/ranger.md#Sensi Ferini / Feral Senses (Ranger 18, pag. 121)"])
async def test_la_vista_cieca_2024_toglie_lo_svantaggio_di_accecato(client):
    from tests.integration.rules.test_2014_ranger import _attack, _conditions, _sword
    from tests.integration.rules.test_2024_fighter import _styled
    chiave = "condition:blinded_blindsight"

    async def opzioni(cid):
        return [o["key"] for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()]

    stile = await _styled(client, "blind_fighting")
    assert chiave not in await opzioni(stile)  # non è Accecato
    ranger = await _pg(client, "2024", "ranger", 18)
    furtivo = await _pg(client, "2024", "rogue", 4, dexterity=16)
    r = await client.post(f"/characters/{furtivo}/feats", json={"feat_key": "2024_skulker", "ability": "dexterity"})
    assert r.status_code == 201, r.text
    for cid in (stile, ranger, furtivo):
        await _conditions(client, cid, blinded=True)
        assert chiave in await opzioni(cid)
    nessuno = await _pg(client, "2024", "fighter", 5)
    await _conditions(client, nessuno, blinded=True)
    assert chiave not in await opzioni(nessuno)
    spada = await _sword(client, stile, equip="main_hand")
    assert (await _attack(client, stile, spada, dice=[3, 17]))["mode_applied"] == "disadvantage"
    visto = await _attack(client, stile, spada, options=[chiave])
    assert visto["mode_applied"] == "normal" and "condition:blinded" not in visto["notes"]


@pytest.mark.caccia(id="CB-4608", fonte="decisione D-030 (tests/caccia/decisioni.md): nel 2014 il colpo senz'armi è un attacco con arma; 2014 · Favore Divino · pag. 235, Manto del Crociato · pag. 250 (Q-2014-incantesimi-d-f-2, Q-2014-incantesimi-m-r-2)",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Favore Divino", "carta:2014/spells.md#Manto del Crociato",
                           "POST /characters/{char_id}/attack/unarmed"])
@pytest.mark.parametrize("edizione, nome, indice, livello, vale", [
    ("2014", "Favore Divino", "divine-favor", 1, True), ("2024", "Favore Divino", "divine-favor", 1, False),
    ("2014", "Manto del Crociato", "crusaders-mantle", 3, True), ("2024", "Manto del Crociato", "crusaders-mantle", 3, True)])
async def test_favore_divino_e_manto_2014_valgono_col_colpo_senz_armi(client, edizione, nome, indice, livello, vale):
    cid = await _pg(client, edizione, "paladin", 9, charisma=16)
    r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "srd_index": indice, "level": livello, "is_concentration": True,
                                                             "duration": "1 minuto", "casting_time": "1 azione bonus"})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": livello})
    assert r.status_code == 200, r.text
    colpo = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 15})).json()
    assert ("radiant" in str(colpo.get("option_result"))) is vale, colpo.get("option_result")


@pytest.mark.caccia(id="CB-4609", fonte="decisione D-030 (tests/caccia/decisioni.md): nel 2014 il colpo senz'armi è un attacco con arma; 2014 · Paladino · Punizione Divina · pag. 98, Chierico · Colpo Divino · pag. 60-63",
                    zona="regola:2014/paladin", voce="regola",
                    copre=["carta:2014/classes/paladin.md#Punizione Divina / Divine Smite (Paladino 2, pag. 98)",
                           "carta:2014/classes/cleric.md#Colpo Divino / Divine Strike (Guerra 8, pag. 60)",
                           "GET /characters/{char_id}/roll-options"])
async def test_punizione_divina_e_colpo_divino_2014_valgono_col_colpo_senz_armi(client):
    for classe, sottoclasse, chiavi in (("paladin", "devotion", {"paladin.divine_smite", "paladin.divine_smite_fiend"}),
                                        ("cleric", "war", {"cleric.divine_strike_war"})):
        cid = await _pg(client, "2014", classe, 11, sottoclasse)
        offerte = {o["key"] for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()}
        assert chiavi <= offerte, offerte
    # nel 2024 i Colpi Benedetti restano agli attacchi con un'arma
    cid = await _pg(client, "2024", "cleric", 8, "war")
    scelta = next(c for c in (await _scheda(client, cid))["pending_choices"] if c.get("group") == "blessed_strikes")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": ["divine_strike"]})
    assert r.status_code == 200, r.text
    offerte = {o["key"] for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()}
    assert not any("divine_strike" in k for k in offerte), offerte


@pytest.mark.caccia(id="CB-4610", fonte="decisione D-031 (tests/caccia/decisioni.md): tipo scelto al lancio e ricordato per i tiri dei turni dopo; 2014 · Incantesimi · Guardiani Spirituali · pag. 240",
                    zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Guardiani Spirituali", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_guardiani_spirituali_2014_radiosi_o_necrotici_scelti_al_lancio(client):
    cid = await _pg(client, "2014", "cleric", 5, "war")  # la riga la concede il Dominio della Guerra
    spell = next(s["id"] for s in (await _scheda(client, cid))["spells"] if s["srd_index"] == "spirit-guardians")
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3, "choices": {"damage_type": "cold"}})
    assert r.status_code == 422, r.status_code
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3, "choices": {"damage_type": "necrotic"}})
    assert r.status_code == 200, r.text
    for _ in range(2):  # lo stesso tipo anche nel turno dopo
        r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"casting_level": 3})
        assert r.status_code == 200 and r.json()["damage_type"] == "necrotic", r.text
        assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200


@pytest.mark.caccia(id="CB-4611", fonte="decisione D-032 (tests/caccia/decisioni.md): orologio e concentrazione si chiudono quando l'ultimo bersaglio perde lo stato; 2014 · Incantesimi · Invisibilità · pag. 246",
                    zona="regola:2014/incantesimi-G-L", voce="interazione",
                    copre=["carta:2014/spells.md#Invisibilità", "POST /characters/{char_id}/attack/unarmed",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("bersagli, agisce, resta", [
    (("lanciatore",), "attacco", False), (("lanciatore",), "lancio", False), (("eroe",), "attacco", False),
    (("lanciatore", "eroe"), "attacco", True)])
async def test_invisibilita_finita_per_l_ultimo_bersaglio_chiude_orologio_e_concentrazione(client, test_session_factory, bersagli, agisce, resta):
    from tests.integration._encounter_helpers import GM_ID
    from tests.integration.rules.test_spell_effects_defenses import _cast, _table
    eroe, lanciatore, spell = await _table(client, test_session_factory, "Invisibility", "invisibility", 3)
    as_user(GM_ID)
    r = await client.patch(f"/characters/{lanciatore}/spells/{spell}", json={"level": 2})
    assert r.status_code == 200, r.text
    ids = {"lanciatore": lanciatore, "eroe": eroe}
    await _cast(client, lanciatore, spell, [ids[b] for b in bersagli], level=3)
    if agisce == "lancio":
        altro = (await client.post(f"/characters/{lanciatore}/spells", json={"name": "Luce", "level": 0})).json()["id"]
        r = await client.post(f"/characters/{lanciatore}/spells/{altro}/use", json={"confirm": ["one_slot_per_turn"]})
    else:
        as_user(GM_ID if bersagli[0] == "lanciatore" else PLAYER_ID)
        r = await client.post(f"/characters/{ids[bersagli[0]]}/attack/unarmed", json={"die": 10})
    assert r.status_code == 200, r.text
    as_user(GM_ID)
    scheda = await _scheda(client, lanciatore)
    assert scheda["concentrating_spell_id"] == (spell if resta else None)
    chiavi = {s["key"] for s in scheda["active_states"] or []}
    assert ("spell_cast:invisibility" in chiavi) is resta and "spell:invisibility" not in chiavi
    if "eroe" in bersagli:
        as_user(PLAYER_ID)
        assert bool((await _scheda(client, eroe))["conditions"].get("invisible")) is resta


@pytest.mark.caccia(id="CB-4612", fonte="decisione D-032 (tests/caccia/decisioni.md); invariante: un nuovo lancio dello stesso incantesimo apre un nuovo orologio",
                    zona="regola:2014/incantesimi-G-L", voce="ripetizione",
                    copre=["carta:2014/spells.md#Invisibilità", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_invisibilita_rilanciata_da_invisibili_resta_attiva_con_la_concentrazione(client, test_session_factory):
    from tests.integration._encounter_helpers import GM_ID
    from tests.integration.rules.test_spell_effects_defenses import _cast, _table
    _eroe, lanciatore, spell = await _table(client, test_session_factory, "Invisibility", "invisibility", 2)
    for _ in range(2):
        await _cast(client, lanciatore, spell, [lanciatore], level=2, confirm=["one_slot_per_turn", "concentration"])
        as_user(GM_ID)
        await client.post(f"/characters/{lanciatore}/turn/new")
    scheda = await _scheda(client, lanciatore)
    assert scheda["concentrating_spell_id"] == spell and scheda["conditions"].get("invisible") is True
    assert {"spell:invisibility", "spell_cast:invisibility"} <= {s["key"] for s in scheda["active_states"]}


@pytest.mark.caccia(id="CB-4613", fonte="decisione D-036 (tests/caccia/decisioni.md): si riempiono solo i campi vuoti delle righe create dal sistema; 2024 · Incantesimi · Spiriti Guardiani · pag. 319, Tempesta di ghiaccio · pag. 287",
                    zona="regola:2024/incantesimi-S-Z", voce="persistenza",
                    copre=["carta:2024/spells.md#Spiriti Guardiani", "GET /characters/{char_id}"])
async def test_le_righe_concesse_gia_create_riempiono_solo_i_campi_vuoti(client, test_session_factory):
    from sqlalchemy import select

    from core.db.models import Character, Spell
    from core.rules.feature_sync import GRANTED_CREATED
    cid = await _pg(client, "2014", "cleric", 5, "war")

    async def riga(indice, **campi):
        async with test_session_factory() as s:
            spell = (await s.execute(select(Spell).where(Spell.character_id == cid, Spell.srd_index == indice))).scalar_one()
            for nome, valore in campi.items():
                setattr(spell, nome, valore)
            await s.commit()
            return spell.attack_save, spell.damage_dice, spell.damage_type, spell.higher_levels_dice

    async with test_session_factory() as s:
        assert {"spirit-guardians", "spiritual-weapon"} <= set((await s.get(Character, cid)).settings[GRANTED_CREATED])
    await riga("spirit-guardians", attack_save=None, damage_dice=None, higher_levels_dice=None)  # com'era prima della correzione
    await riga("spiritual-weapon", damage_dice="9d9", damage_type=None)  # i dadi scritti dall'utente restano
    assert (await client.patch(f"/characters/{cid}/xp", json={"set": 14000})).status_code == 200  # la salita di livello risincronizza
    assert await riga("spirit-guardians") == ("SAVE", "3d8", None, "1d8")
    assert (await riga("spiritual-weapon"))[:3] == ("ATK", "9d9", "force")


@pytest.mark.caccia(id="CB-4614", fonte="decisione D-039 (tests/caccia/decisioni.md): i PF temporanei impostati a mano sopravvivono alla fine degli effetti che ne danno; 2014 · pag. 198, 2024 · pag. 29",
                    zona="regola:2014/generali", voce="interazione",
                    copre=["carta:2014/general.md#Punti Ferita Temporanei / Temporary Hit Points (pag. 198)", "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("a_mano, dopo, resta", [(None, None, 0), (2, None, 2), (None, 2, 0)])
async def test_i_pf_temporanei_a_mano_sopravvivono_alla_fine_di_eroismo(client, test_session_factory, a_mano, dopo, resta):
    from tests.integration.rules.test_spell_effects_hp import _end_spell, _heroism_with_temp
    eroe, lanciatore = await _heroism_with_temp(client, test_session_factory)  # Eroismo 2014: 3 PF temporanei
    as_user(PLAYER_ID)
    if a_mano:
        assert (await client.patch(f"/characters/{eroe}/hp", json={"op": "set_temp", "value": a_mano})).status_code == 200
    if dopo:  # scesi per un danno, non a mano: svaniscono
        assert (await client.patch(f"/characters/{eroe}/hp", json={"op": "damage", "value": 3 - dopo})).status_code == 200
    await _end_spell(client, eroe, lanciatore, "heroism", "manual")
    as_user(PLAYER_ID)
    assert (await _scheda(client, eroe))["temp_hp"] == resta


@pytest.mark.caccia(id="CB-4615", fonte="decisione D-039 (tests/caccia/decisioni.md): i PF temporanei impostati a mano sopravvivono alla fine degli effetti che ne danno; 2024 · pag. 29",
                    zona="regola:2024/barbarian", voce="interazione",
                    copre=["carta:2024/general.md#Punti Ferita Temporanei / Temporary Hit Points (pag. 29)", "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("a_mano, annulla, resta", [(None, False, 0), (2, False, 2), (30, True, 0)])
async def test_i_pf_temporanei_a_mano_sopravvivono_alla_fine_dell_ira_di_un_compagno(client, test_session_factory, a_mano, annulla, resta):
    from tests.integration._encounter_helpers import GM_ID, seed_session
    from tests.integration.rules.test_2014_bard_inspiration import _seat
    from tests.integration.rules.test_task46_temp_hp_ally import LIFE, _life
    _sid, eroe = await seed_session(test_session_factory)
    as_user(GM_ID)
    barbaro = await _life(client)
    await _seat(test_session_factory, barbaro)
    as_user(GM_ID)
    r = await client.post(f"/characters/{barbaro}/features/{LIFE}/use", json={"params": {"target_character_ids": [eroe], "target_character_id": eroe}})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    assert (await _scheda(client, eroe))["temp_hp"] > 2
    if a_mano:
        r = await client.patch(f"/characters/{eroe}/hp", json={"op": "set_temp", "value": a_mano})
        assert r.status_code == 200
        if annulla:  # la correzione annullata non protegge più
            assert (await client.post(f"/characters/{eroe}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})).status_code == 200
    as_user(GM_ID)
    assert (await client.delete(f"/characters/{barbaro}/active-states/rage")).status_code == 200
    as_user(PLAYER_ID)
    assert (await _scheda(client, eroe))["temp_hp"] == resta


@pytest.mark.caccia(id="CB-4643", fonte="2024 · Chierico · Colpi Benedetti Migliorati, Incantesimi Potenti · pag. 71 (PF temporanei a sé o a un'altra creatura entro 18 m)",
                    zona="regola:2024/cleric", voce="regola",
                    copre=["carta:2024/classes/cleric.md#Colpi Benedetti Migliorati / Improved Blessed Strikes (Chierico 14, pag. 71)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_incantesimi_potenti_migliorati_possono_dare_i_pf_temporanei_a_se(client):
    from tests.integration.rules.test_task46_fix1 import POTENT, _cantrip, _potent
    cid = await _potent(client)
    trucchetto = await _cantrip(client, cid)
    url = f"/characters/{cid}/spells/{trucchetto}/roll_damage"
    r = await client.post(url, json={"main_rolls": [4, 3, 2], "options": [POTENT, f"{POTENT}_self"]})
    assert r.status_code == 409, r.status_code  # a sé o a un'altra creatura, non a entrambi
    r = await client.post(url, json={"main_rolls": [4, 3, 2], "options": [f"{POTENT}_self"]})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["temp_hp"] == 6  # 2 x Saggezza (+3)


@pytest.mark.caccia(id="CB-4644", fonte="2024 · Chierico · Lampo di Interdizione Migliorato · pag. 75 (PF temporanei al bersaglio dell'attacco, anche il chierico)",
                    zona="regola:2024/cleric", voce="regola",
                    copre=["carta:2024/classes/cleric.md#Lampo di Interdizione Migliorato / Improved Warding Flare (Luce 6, pag. 75)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_lampo_di_interdizione_migliorato_da_i_pf_temporanei_al_chierico_bersaglio(client, test_session_factory):
    from tests.integration._encounter_helpers import GM_ID, seed_session
    from tests.integration.rules.test_2014_bard_inspiration import _seat
    from tests.integration.rules.test_2024_cleric_domains import _dom
    lampo = "cleric.warding_flare"
    _sid, eroe = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _dom(client, 6, "light", wisdom=16)
    await _seat(test_session_factory, cid)
    riga = next(a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == lampo)
    assert [x["key"] for x in riga["use_toggles"]] == ["self"]
    # il bersaglio dell'attacco è uno solo: lui o un altro
    r = await client.post(f"/characters/{cid}/features/{lampo}/use", json={"params": {"self": True, "target_character_id": eroe}})
    assert r.status_code == 422, r.status_code
    r = await client.post(f"/characters/{cid}/features/{lampo}/use", json={"params": {"self": True}})
    assert r.status_code == 200 and r.json()["given"] is None, r.text
    assert 5 <= (await _scheda(client, cid))["temp_hp"] <= 15  # 2d6 + Saggezza (+3)


@pytest.mark.caccia(id="CB-4645", fonte="2024 · Incantesimi · Produrre Fiamma · pag. 308 (lancio con l'azione bonus, la fiamma si scaglia con un'azione Magia finché dura); 2014 · pag. 264",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2024/spells.md#Produrre Fiamma", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/attack"])
async def test_produrre_fiamma_2024_si_accende_col_lancio_e_si_scaglia_con_l_azione(client, test_session_factory):
    from tests.integration._encounter_helpers import GM_ID, seed_session
    from tests.integration.rules.test_2014_bard_inspiration import _seat
    sid, _eroe = await seed_session(test_session_factory)
    as_user(GM_ID)
    ids = {}
    for edizione, tempo in (("2024", "1 azione bonus"), ("2014", "1 azione")):
        cid = await _pg(client, edizione, "druid", 3, wisdom=16)
        r = await client.post(f"/characters/{cid}/spells", json={
            "name": "Produrre Fiamma", "srd_index": "produce-flame", "level": 0, "attack_save": "ATK", "casting_time": tempo,
            "duration": "10 minuti", "damage_dice": "1d8", "damage_type": "fire"})
        assert r.status_code == 201, r.text
        ids[edizione] = cid, r.json()["id"]
    cid, spell = ids["2024"]
    await _seat(test_session_factory, cid)
    url = f"/characters/{cid}/spells/{spell}"
    r = await client.post(f"{url}/attack", json={"die": 15})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "flame_not_lit", r.text[:200]
    assert (await client.post(f"{url}/use", json={})).status_code == 200
    turno = await _turno(client, cid)
    assert (turno["bonus_used"], turno["action_used"]) == (True, False)

    async def riga():
        return next(s for s in (await _scheda(client, cid))["spells"] if s["id"] == spell)

    assert ((await riga())["effect"]["lit"], (await riga())["effective_casting_time"]) == (True, "1 azione")
    assert (await client.post(f"{url}/attack", json={"die": 15})).status_code == 200
    assert (await _turno(client, cid))["action_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.post(f"{url}/attack", json={"die": 15})).status_code == 200  # ancora accesa: non serve un altro lancio
    turno = await _turno(client, cid)
    assert (turno["bonus_used"], turno["action_used"]) == (False, True)
    for _ in range(100):  # 10 minuti
        await client.post(f"/characters/{cid}/rounds/tick")
    assert (await riga())["effect"]["lit"] is False
    cid, spell = ids["2014"]  # nel 2014 il lancio e il tiro restano una cosa sola
    assert (await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 15})).status_code == 200


@pytest.mark.caccia(id="CB-4647", fonte="decisione D-020 (tests/caccia/decisioni.md): fuori dalla finestra del riposo lungo il cambio di preparati (e trucchetti 2024) va confermato; libero alla creazione e alla salita di livello",
                    zona="regola:2014/cleric", voce="regola",
                    copre=["carta:2014/classes/cleric.md#Incantesimi / Spellcasting (Chierico 1, pag. 58)",
                           "carta:2024/classes/cleric.md#Incantesimi / Spellcasting (Chierico 1, pag. 69)", "PATCH /characters/{char_id}/spells/{spell_id}",
                           "DELETE /characters/{char_id}/spells/{spell_id}"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_cambiare_i_preparati_lontano_dal_riposo_lungo_si_conferma(client, edizione):
    cid = await _pg(client, edizione, "cleric", 3, wisdom=16)
    ids = {}
    for nome, livello in (("Benedizione", 1), ("Cura", 1), ("Luce Prova", 0)):
        r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "level": livello})
        assert r.status_code == 201, r.text
        ids[nome] = r.json()["id"]
    url = f"/characters/{cid}/spells/{ids['Benedizione']}"

    async def prepara(valore, **q):
        return await client.patch(url, json={"is_prepared": valore}, params=q)

    async def spendi():
        slot = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["level"] == 1)
        r = await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": slot["used"] + 1})
        assert r.status_code == 200, r.text

    assert (await prepara(True)).status_code == 200  # creazione: libero
    await spendi()
    r = await prepara(False)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "change_after_long_rest", r.text
    assert (await prepara(False, confirm=True)).status_code == 200
    # i trucchetti solo nel 2024; un incantesimo non preparato si dimentica senza conferma
    r = await client.delete(f"/characters/{cid}/spells/{ids['Luce Prova']}")
    assert r.status_code == (409 if edizione == "2024" else 204), r.text
    assert (await client.delete(f"/characters/{cid}/spells/{ids['Cura']}")).status_code == 204
    cls = (await _scheda(client, cid))["classes"][0]  # salita di livello: libero, anche con slot spesi
    r = await client.patch(f"/characters/{cid}/classes/{cls['id']}", json={"level": 4})
    assert r.status_code == 200, r.text
    assert (await prepara(True)).status_code == 200
    await spendi()
    assert (await prepara(False)).status_code == 409
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.status_code == 200, r.text
    assert (await prepara(False)).status_code == 200


# ---------------------------------------------------------------------------
# D-037: Deflagrazione/Esplosione Occulta, un tiro per colpire e un danno per raggio
# ---------------------------------------------------------------------------

async def _deflagrazione(client, cid) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Deflagrazione Occulta", "level": 0, "srd_index": "eldritch-blast", "attack_save": "ATK",
                                                              "damage_dice": "1d10", "damage_type": "force", "casting_time": "1 azione"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _raggio(client, cid, sid, **corpo):
    return await client.post(f"/characters/{cid}/spells/{sid}/attack", json=corpo)


async def _danno(client, cid, sid, **corpo) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json=corpo)
    assert r.status_code == 200, r.text[:300]
    return r.json()


@pytest.mark.caccia(id="CB-4681", fonte="decisione D-037 (tests/caccia/decisioni.md): 1d10 e Carisma per raggio, col suo critico; 2014 · Deflagrazione Occulta · pag. 229, Deflagrazione Agonizzante · pag. 118; 2024 · pag. 267, 155",
                    zona="regola:2014/incantesimi-D-F", voce="interazione",
                    copre=["carta:2014/spells.md#Deflagrazione Occulta", "carta:2024/spells.md#Esplosione occulta",
                           "carta:2014/classes/warlock.md#Deflagrazione Agonizzante / Agonizing Blast (Suppliche Occulte, trucchetto deflagrazione occulta, pag. 118)",
                           "carta:2024/classes/warlock.md#Deflagrazione Agonizzante / Agonizing Blast (Suppliche Occulte, livello 2+, trucchetto Warlock che infligge danno, pag. 155)",
                           "POST /characters/{char_id}/spells/{spell_id}/attack", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_ogni_raggio_ha_il_suo_danno_il_suo_critico_e_il_carisma_di_agonizzante(client, edizione):
    cid = await _pg(client, edizione, "warlock", 11, charisma=18)  # tre raggi
    sid = await _deflagrazione(client, cid)
    scelta = next(c for c in (await _scheda(client, cid))["pending_choices"] if c.get("group") == "invocations")
    nota = "agonizing_blast" if edizione == "2014" else "agonizing_blast__eldritch_blast"
    altre = ["armor_of_shadows", "devils_sight", "misty_visions", "mask_of_many_faces", "fiendish_vigor", "otherworldly_leap", "ascendant_step"]
    altre = [k for k in altre if k in {o["key"] for o in scelta["options"]}]
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": [nota, *altre][:scelta["count"]]})
    assert r.status_code == 200, r.text[:300]
    danni = []
    for die, corpo in ((12, {}), (20, {"ray": True}), (12, {"ray": True})):
        r = await _raggio(client, cid, sid, die=die, **corpo)
        assert r.status_code == 200, r.text[:300]
        dadi = [7] * (2 if r.json()["is_critical"] else 1)
        danni.append((await _danno(client, cid, sid, main_rolls=dadi, is_critical=r.json()["is_critical"]))["total"])
    assert danni == [7 + 4, 14 + 4, 7 + 4]


@pytest.mark.caccia(id="CB-4682", fonte="decisione D-037 (tests/caccia/decisioni.md): Malocchio/Sortilegio per ogni raggio che colpisce; 2014 · Sortilegio · pag. 279; 2024 · Malocchio · pag. 285",
                    zona="regola:2014/incantesimi-S-Z", voce="interazione",
                    copre=["carta:2014/spells.md#Sortilegio", "carta:2024/spells.md#Malocchio", "POST /characters/{char_id}/spells/{spell_id}/attack",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_il_malocchio_vale_per_ogni_raggio_contro_il_bersaglio_maledetto(client, edizione):
    cid = await _pg(client, edizione, "warlock", 11)
    sid = await _deflagrazione(client, cid)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Hex", "level": 1, "srd_index": "hex", "is_concentration": True, "is_prepared": True})
    slot = next(s for s in (await _scheda(client, cid))["spell_slots"])
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_id": slot["id"], "slot_level": slot["level"], "choices": {"ability": "wisdom"}})
    assert r.status_code == 200, r.text[:300]
    dadi_hex = []
    for corpo in ({"options": ["spell:hex:damage"]}, {"ray": True, "options": ["spell:hex:damage"]}, {"ray": True}):  # il terzo su un altro bersaglio
        assert (await _raggio(client, cid, sid, die=15, **corpo)).status_code == 200
        danno = await _danno(client, cid, sid, main_rolls=[5])
        dadi_hex.append(len((danno.get("option_result") or {}).get("extra_rolls") or []))
    assert dadi_hex == [1, 1, 0]


@pytest.mark.caccia(id="CB-4683", fonte="decisione D-037 (tests/caccia/decisioni.md): i raggi sono dello stesso lancio; 2014 · Deflagrazione Occulta · pag. 229; 2024 · Esplosione occulta · pag. 267, Ispirazione Eroica · pag. 11",
                    zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Esplosione occulta", "carta:2014/spells.md#Deflagrazione Occulta", "POST /characters/{char_id}/spells/{spell_id}/attack"])
async def test_i_raggi_seguenti_non_sono_un_altro_lancio_e_il_rilancio_vale_per_uno(client):
    cid = await _pg(client, "2024", "warlock", 5)
    sid = await _deflagrazione(client, cid)
    senza_lancio = await _raggio(client, cid, sid, die=10, ray=True)
    assert (senza_lancio.status_code, senza_lancio.json()["detail"]["code"]) == (409, "no_ray_left")
    assert (await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})).status_code == 200
    assert (await _raggio(client, cid, sid, die=2)).json()["ray"] == 1
    rilancio = (await _raggio(client, cid, sid, die=17, with_inspiration=True)).json()
    assert (rilancio["to_hit_die"], rilancio["ray"], rilancio["rays"]) == (17, 1, 2)
    secondo = (await _raggio(client, cid, sid, die=9, ray=True)).json()
    assert (secondo["to_hit_die"], secondo["ray"]) == (9, 2)
    assert (await _raggio(client, cid, sid, die=10, ray=True)).status_code == 409
    assert (await _raggio(client, cid, sid, die=10)).json()["ray"] == 1  # un lancio nuovo
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _raggio(client, cid, sid, die=10, ray=True)).status_code == 409  # i raggi sono di quel turno
    dardo = (await client.post(f"/characters/{cid}/spells", json={"name": "Dardo di Fuoco", "level": 0, "srd_index": "fire-bolt", "attack_save": "ATK",
                                                                   "damage_dice": "1d10", "damage_type": "fire"})).json()["id"]
    altro = (await _raggio(client, cid, dardo, die=10)).json()
    assert "ray" not in altro and len((await _danno(client, cid, dardo))["main_rolls"]) == 2  # gli altri trucchetti non cambiano


# ---------------------------------------------------------------------------
# Opzioni dopo un colpo («after_hit») sugli attacchi con incantesimo: si confermano col danno (``hit_options``)
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-4684", fonte="2014 · Warlock · Deflagrazione Respingente · pag. 118; 2024 · pag. 157 (colpendo, per ogni raggio: decisione D-037, tests/caccia/decisioni.md)",
                    zona="regola:2024/warlock", voce="interazione",
                    copre=["carta:2014/classes/warlock.md#Deflagrazione Respingente / Repelling Blast (Suppliche Occulte, trucchetto deflagrazione occulta, pag. 118)",
                           "carta:2024/classes/warlock.md#Deflagrazione Respingente / Repelling Blast (Suppliche Occulte, livello 2+, trucchetto Warlock che infligge danno con un tiro per colpire, pag. 157)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_la_deflagrazione_respingente_spinge_per_ogni_raggio_a_segno(client, edizione):
    if edizione == "2014":
        from tests.integration.rules.test_2014_warlock_invocations import _caster
        cid, chiave = await _caster(client, 5, "repelling_blast", blast=True), "warlock.repelling_blast"
    else:
        from tests.integration.rules.test_2024_warlock import _caster24
        cid, chiave = await _caster24(client, 5, "repelling_blast__eldritch_blast", cantrips=("eldritch-blast",)), "warlock.repelling_blast__eldritch_blast"
    sid = next(s["id"] for s in (await _scheda(client, cid))["spells"] if s["srd_index"] == "eldritch-blast")
    assert (await _raggio(client, cid, sid, die=15)).status_code == 200
    danno = await _danno(client, cid, sid, hit_options=[chiave])
    assert danno["option_result"]["keys"] == [chiave] and danno["option_result"]["targets"] == [chiave]
    assert (await client.get(f"/characters/{cid}/target-effects/{chiave}")).json()["result"]["note"] == "repelling_blast"
    danni = f"/characters/{cid}/spells/{sid}/roll_damage"
    assert (await client.post(danni, json={"hit_options": [chiave]})).status_code == 409  # il danno di quel colpo è già tirato
    assert (await _raggio(client, cid, sid, die=1, ray=True)).status_code == 200
    assert (await client.post(danni, json={"hit_options": [chiave]})).status_code == 409  # un 1 naturale non spinge
    assert (await _raggio(client, cid, sid, die=15)).status_code == 200
    assert (await _danno(client, cid, sid, hit_options=[chiave]))["option_result"]["targets"] == [chiave]
    assert (await _raggio(client, cid, sid, die=12, ray=True)).status_code == 200
    assert (await _danno(client, cid, sid, hit_options=[chiave]))["option_result"]["targets"] == [chiave]  # e di nuovo col secondo raggio


@pytest.mark.caccia(id="CB-4685", fonte="2024 · Guerriero · Maestro di Battaglia, Attacco Minaccioso e Attacco Preciso · pag. 95 (se si colpisce; una manovra per attacco)",
                    zona="regola:2024/fighter", voce="interazione",
                    copre=["carta:2024/classes/fighter.md#Attacco Minaccioso / Menacing Attack (Manovra, Maestro di Battaglia 3, pag. 95)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage", "POST /characters/{char_id}/last-roll/options"])
async def test_una_manovra_dopo_il_colpo_di_un_incantesimo_spende_il_dado_e_lo_somma_al_danno(client):
    from tests.caccia.test_cb_regola_fix_classi_2024_b import _maestro_mago, _opzioni_attacco
    from tests.integration.rules.test_2014_bard import _ability
    minaccia, dadi = "fighter.maneuver_menacing", "fighter.superiority_dice"
    cid, dardo = await _maestro_mago(client, "precision", "menacing", "trip")
    assert "fighter.maneuver_trip" not in await _opzioni_attacco(client, cid, dardo)  # Sbilanciante nomina l'arma
    danni = f"/characters/{cid}/spells/{dardo}/roll_damage"
    assert (await client.post(danni, json={"hit_options": [minaccia]})).status_code == 409  # senza un colpo
    assert (await _raggio(client, cid, dardo, die=20)).status_code == 200
    danno = await _danno(client, cid, dardo, main_rolls=[4, 4], is_critical=True, hit_options=[minaccia])
    blocco = danno["option_result"]
    assert len(blocco["extra_rolls"]) == 2 and danno["total"] == 8 + sum(blocco["extra_rolls"])  # il critico raddoppia anche il dado
    assert blocco["targets"] == [minaccia] and [d[0] for d in danno["reroll_dice"]] == [10, 10, 8, 8]
    assert (await _ability(client, cid, dadi))["uses"] == 3
    assert (await _raggio(client, cid, dardo, die=8)).status_code == 200
    assert (await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["fighter.maneuver_precision"]})).status_code == 200
    assert (await client.post(danni, json={"hit_options": [minaccia]})).status_code == 409  # una sola manovra per attacco
    assert (await _ability(client, cid, dadi))["uses"] == 2


@pytest.mark.caccia(id="CB-4686", fonte="2024 · Talenti · Dono dell'Offensiva irresistibile, Colpo travolgente · pag. 211 (20 naturale sul d20 di un attacco)",
                    zona="regola:2024/talenti", voce="interazione",
                    copre=["carta:2024/feats.md#Dono dell'Offensiva irresistibile / Boon of Irresistible Offense (pag. 211) - Dono epico",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_il_colpo_travolgente_vale_anche_per_il_20_naturale_di_un_incantesimo(client):
    from tests.integration.rules.test_feats_2024_boons import _boon
    cid = (await _boon(client, "irresistible_offense", "strength", "warlock"))["id"]
    chiave = "feat.2024_boon_irresistible_offense_strike"
    forza = next(s["value"] for s in (await _scheda(client, cid))["ability_scores"] if s["name"] == "strength")
    sid = await _deflagrazione(client, cid)
    assert (await _raggio(client, cid, sid, die=20)).status_code == 200
    danno = await _danno(client, cid, sid, main_rolls=[3, 3], is_critical=True, hit_options=[chiave])
    assert danno["total"] == 6 + forza
    assert (await _raggio(client, cid, sid, die=19, ray=True)).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"hit_options": [chiave]})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "option_unavailable")
    # un ritiro che diventa 20 la apre: il d20 che conta è quello finale
    assert (await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})).status_code == 200
    assert (await _raggio(client, cid, sid, die=20, with_inspiration=True)).status_code == 200
    assert (await _danno(client, cid, sid, main_rolls=[3, 3], is_critical=True, hit_options=[chiave]))["total"] == 6 + forza


@pytest.mark.caccia(id="CB-4687", fonte="2014 · Incantesimi · Punizione Marchiante, Punizione Tonante · pag. 266, Colpo Intrappolante · pag. 222 (al prossimo colpo con un'arma)",
                    zona="regola:2014/incantesimi-M-R", voce="interazione",
                    copre=["carta:2014/spells.md#Punizione Marchiante", "carta:2014/spells.md#Punizione Tonante", "carta:2014/spells.md#Colpo Intrappolante",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("edizione, chiave, nome", [("2014", "branding-smite", "Branding Smite"), ("2014", "thunderous-smite", "Thunderous Smite"),
                                                    ("2014", "ensnaring-strike", "Ensnaring Strike")])
async def test_le_punizioni_gia_lanciate_non_si_offrono_su_un_attacco_con_incantesimo(client, edizione, chiave, nome):
    cid = await _pg(client, edizione, "paladin", 9)
    sid = await _deflagrazione(client, cid)
    livello = 2 if chiave == "branding-smite" else 1
    r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "level": livello, "srd_index": chiave, "is_concentration": True, "is_prepared": True})
    assert r.status_code == 201, r.text
    slot = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["level"] >= livello)
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_id": slot["id"], "slot_level": slot["level"]})
    assert r.status_code == 200, r.text[:300]
    opzione = f"spell:{chiave.replace('-', '_')}:hit"
    offerte = lambda q: client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", **q})  # noqa: E731
    assert opzione not in {o["key"] for o in (await offerte({"spell_id": sid})).json()}
    assert opzione in {o["key"] for o in (await offerte({})).json()}  # il colpo senz'armi 2014 è un attacco con arma (D-030)


@pytest.mark.caccia(id="CB-4688", fonte="2024 · Guerriero · Campione, Atleta Straordinario · pag. 96 (subito dopo un Colpo Critico, senza limite all'arma; Q-2024-fighter-2)",
                    zona="regola:2024/fighter", voce="interazione",
                    copre=["carta:2024/classes/fighter.md#Atleta Straordinario / Remarkable Athlete (Campione 3, pag. 96)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_atleta_straordinario_dopo_il_critico_di_un_incantesimo(client):
    cid = await _pg(client, "2024", "fighter", 3, "Campione")
    sid = await _deflagrazione(client, cid)
    chiave, danni = "fighter.remarkable_athlete_move", f"/characters/{cid}/spells/{sid}/roll_damage"
    assert (await _raggio(client, cid, sid, die=15)).status_code == 200
    assert (await client.post(danni, json={"hit_options": [chiave]})).status_code == 409
    assert (await _raggio(client, cid, sid, die=20)).status_code == 200
    assert "metà" in (await _danno(client, cid, sid, is_critical=True, hit_options=[chiave]))["option_result"]["effects"][0]["it"]


# ---------------------------------------------------------------------------
# D-045…D-052
# ---------------------------------------------------------------------------

async def _slot(client, cid, livello) -> dict:
    s = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["level"] == livello)
    return {"slot_id": s["id"], "slot_level": livello}


@pytest.mark.caccia(id="CB-4871", fonte="decisione D-045 (tests/caccia/decisioni.md): un tiro per colpire e 2d6 per raggio, +1 raggio per slot oltre il 2°; 2014 · Raggio Rovente · pag. 267; 2024 · pag. 313",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2014/spells.md#Raggio Rovente", "carta:2024/spells.md#Raggio Rovente", "POST /characters/{char_id}/spells/{spell_id}/attack",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
@pytest.mark.parametrize("indice", ["scorching-ray", None])
async def test_raggio_rovente_tira_per_colpire_e_fa_2d6_raggio_per_raggio(client, edizione, indice):
    cid = await _pg(client, edizione, "sorcerer", 9)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Raggio Rovente", "level": 2, "srd_index": indice, "attack_save": "ATK", "is_prepared": True,
                                                             "damage_dice": "2d6", "damage_type": "fire", "casting_time": "1 azione", "higher_levels_dice": "2d6"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert next(s for s in (await _scheda(client, cid))["spells"] if s["id"] == sid)["rays"] == 3
    slot = await _slot(client, cid, 4)
    disponibili = lambda scheda: next(s for s in scheda["spell_slots"] if s["id"] == slot["slot_id"])["available"]  # noqa: E731
    prima = disponibili(await _scheda(client, cid))
    r = await _raggio(client, cid, sid, die=20, **slot)
    assert r.status_code == 200 and (r.json()["ray"], r.json()["rays"]) == (1, 5), r.text
    # il critico è del solo primo raggio, e lo slot più alto dà raggi, non dadi
    assert len((await _danno(client, cid, sid, casting_level=4, is_critical=True))["main_rolls"]) == 4
    for n in range(2, 6):
        r = await _raggio(client, cid, sid, die=12, ray=True)
        assert r.status_code == 200 and r.json()["ray"] == n, r.text
        assert len((await _danno(client, cid, sid, casting_level=4))["main_rolls"]) == 2
    r = await _raggio(client, cid, sid, die=12, ray=True)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "no_ray_left")
    assert disponibili(await _scheda(client, cid)) == prima - 1  # un lancio solo
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _raggio(client, cid, sid, die=12, **await _slot(client, cid, 2))).json()["rays"] == 3


@pytest.mark.caccia(id="CB-4873", fonte="decisione D-046 (tests/caccia/decisioni.md): tipo scelto al lancio e ricordato per i tiri dei turni dopo, come la D-031; 2024 · Incantesimi · Spiriti Guardiani · pag. 319",
                    zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Spiriti Guardiani", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("tipo", ["radiant", "necrotic"])
async def test_spiriti_guardiani_2024_radiosi_o_necrotici_scelti_al_lancio(client, tipo):
    cid = await _pg(client, "2024", "cleric", 5, "war")  # la riga la concede il Dominio della Guerra
    spell = next(s["id"] for s in (await _scheda(client, cid))["spells"] if s["srd_index"] == "spirit-guardians")
    for choices in (None, {"damage_type": "cold"}):
        r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3, "choices": choices})
        assert r.status_code == 422, r.status_code
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3, "choices": {"damage_type": tipo}})
    assert r.status_code == 200, r.text
    for _ in range(2):  # lo stesso tipo anche nel turno dopo
        r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"casting_level": 3})
        assert r.status_code == 200 and r.json()["damage_type"] == tipo, r.text
        assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200


@pytest.mark.caccia(id="CB-4874", fonte="decisione D-047 (tests/caccia/decisioni.md): il lancio (azione bonus) crea la lama, ogni attacco è un'azione con il suo tiro; 2014 · Lama Infuocata · pag. 247; 2024 · Lama infuocata · pag. 275",
                    zona="regola:2014/incantesimi-G-L", voce="interazione",
                    copre=["carta:2014/spells.md#Lama Infuocata", "carta:2024/spells.md#Lama infuocata", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/attack"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_lama_infuocata_si_crea_col_lancio_e_attacca_con_l_azione_anche_nei_turni_dopo(client, test_session_factory, edizione):
    from tests.integration._encounter_helpers import GM_ID, seed_session
    from tests.integration.rules.test_2014_bard_inspiration import _seat
    await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _pg(client, edizione, "druid", 7, wisdom=16)
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Lama Infuocata", "srd_index": "flame-blade", "level": 2, "attack_save": "ATK", "casting_time": "1 azione bonus", "range_area": "Incantatore",
        "duration": "Concentrazione, fino a 10 minuti", "is_concentration": True, "is_prepared": True, "damage_dice": "3d6", "damage_type": "fire"})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    await _seat(test_session_factory, cid)
    url, slot = f"/characters/{cid}/spells/{spell}", await _slot(client, cid, 4)
    r = await client.post(f"{url}/attack", json={"die": 15, **slot})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "flame_not_lit", r.text[:200]
    assert (await client.post(f"{url}/use", json=slot)).status_code == 200
    turno = await _turno(client, cid)
    assert (turno["bonus_used"], turno["action_used"]) == (True, False)
    scheda = await _scheda(client, cid)
    riga = next(s for s in scheda["spells"] if s["id"] == spell)
    assert (riga["effect"]["lit"], riga["effective_casting_time"], scheda["settings"]["concentration_level"]) == (True, "1 azione", 4)
    libero = next(s for s in scheda["spell_slots"] if s["id"] == slot["slot_id"])["available"]
    for _ in range(2):  # lo stesso turno del lancio e quello dopo: un'azione, nessun altro slot
        assert (await client.post(f"{url}/attack", json={"die": 15})).status_code == 200
        assert (await _turno(client, cid))["action_used"] is True
        await client.post(f"/characters/{cid}/turn/new")
    scheda = await _scheda(client, cid)
    assert next(s for s in scheda["spell_slots"] if s["id"] == slot["slot_id"])["available"] == libero
    assert scheda["concentrating_spell_id"] == spell
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})  # senza concentrazione la lama svanisce
    assert (await client.post(f"{url}/attack", json={"die": 15})).status_code == 409


@pytest.mark.caccia(id="CB-4875", fonte="decisione D-047 (tests/caccia/decisioni.md): nel 2014 l'attacco con la lama è un'azione qualsiasi, nel 2024 è l'azione Magia; 2014 · Azione Impetuosa · pag. 83; 2024 · Azione Impetuosa · pag. 91",
                    zona="regola:2024/incantesimi-G-L", voce="edizioni",
                    copre=["carta:2024/spells.md#Lama infuocata", "POST /characters/{char_id}/spells/{spell_id}/attack"])
@pytest.mark.parametrize("edizione, esito", [("2014", 200), ("2024", 409)])
async def test_la_lama_infuocata_attacca_con_l_azione_in_piu_solo_nel_2014(client, edizione, esito):
    cid = await _pg(client, edizione, "fighter", 2)
    assert (await client.patch(f"/characters/{cid}", json={"settings": {"advancement": "milestone"}})).status_code == 200
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "druid", "level": 3})).status_code == 201
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Flame Blade", "srd_index": "flame-blade", "level": 2, "attack_save": "ATK", "casting_time": "1 bonus action",
        "duration": "Concentration, up to 10 minutes", "is_concentration": True, "is_prepared": True, "damage_dice": "3d6", "damage_type": "fire"})
    url = f"/characters/{cid}/spells/{r.json()['id']}"
    assert (await client.post(f"{url}/use", json=await _slot(client, cid, 2))).status_code == 200
    assert (await client.post(f"{url}/attack", json={"die": 15})).status_code == 200
    r = await client.post(f"/characters/{cid}/features/fighter.action_surge/use", json={})
    assert r.status_code == 200, r.text[:200]
    assert (await client.post(f"{url}/attack", json={"die": 15})).status_code == esito


async def _ispirato(client, cid) -> None:
    assert (await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})).status_code == 200


@pytest.mark.caccia(id="CB-4877", fonte="decisione D-048 (tests/caccia/decisioni.md): il rilancio con Ispirazione tiene le opzioni confermate e i loro dadi; 2024 · Malocchio · pag. 285, Marchio del Cacciatore · pag. 285, Ispirazione Eroica · pag. 13",
                    zona="regola:2024/generali", voce="interazione",
                    copre=["carta:2024/spells.md#Malocchio", "POST /characters/{char_id}/spells/{spell_id}/attack",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_il_rilancio_di_un_raggio_tiene_i_dadi_del_malocchio(client):
    cid = await _pg(client, "2024", "warlock", 5)
    sid = await _deflagrazione(client, cid)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Hex", "level": 1, "srd_index": "hex", "is_concentration": True, "is_prepared": True})
    slot = next(s for s in (await _scheda(client, cid))["spell_slots"])
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_id": slot["id"], "slot_level": slot["level"], "choices": {"ability": "wisdom"}})
    assert r.status_code == 200, r.text[:300]
    for raggio in ({}, {"ray": True}) * 3:  # più giri: il d6 già tirato non cambia col d20
        await _ispirato(client, cid)
        primo = (await _raggio(client, cid, sid, die=3, options=["spell:hex:damage"], **raggio)).json()
        secondo = (await _raggio(client, cid, sid, die=12, with_inspiration=True)).json()
        assert secondo["to_hit_die"] == 12 and secondo["option_result"]["extra_rolls"] == primo["option_result"]["extra_rolls"]
        assert (await _danno(client, cid, sid, main_rolls=[5]))["total"] == 5 + sum(primo["option_result"]["extra_rolls"])
    # un critico nato dal rilancio raddoppia i dadi dell'opzione
    await client.post(f"/characters/{cid}/turn/new")
    await _ispirato(client, cid)
    await _raggio(client, cid, sid, die=3, options=["spell:hex:damage"])
    assert len((await _raggio(client, cid, sid, die=20, with_inspiration=True)).json()["option_result"]["extra_rolls"]) == 2


@pytest.mark.caccia(id="CB-4878", fonte="decisione D-048 (tests/caccia/decisioni.md): il rilancio con Ispirazione tiene le opzioni confermate senza ripagarle; 2024 · Guerriero · Maestro di Battaglia, Attacco Preciso · pag. 95 (una manovra per attacco)",
                    zona="regola:2024/fighter", voce="interazione",
                    copre=["carta:2024/classes/fighter.md#Attacco Preciso / Precision Attack (Manovra, Maestro di Battaglia 3, pag. 95)",
                           "POST /characters/{char_id}/spells/{spell_id}/attack", "POST /characters/{char_id}/last-roll/options"])
async def test_il_rilancio_di_un_attacco_con_incantesimo_tiene_la_manovra_usata_dopo_il_tiro(client):
    from tests.caccia.test_cb_regola_fix_classi_2024_b import _maestro_mago
    from tests.integration.rules.test_2014_bard import _ability
    preciso = "fighter.maneuver_precision"
    cid, dardo = await _maestro_mago(client, "precision", "menacing", "trip")
    await _ispirato(client, cid)
    primo = (await _raggio(client, cid, dardo, die=4)).json()
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [preciso]})
    assert r.status_code == 200, r.text[:300]
    dado = r.json()["total"] - primo["to_hit_total"]
    assert dado >= 1
    secondo = (await _raggio(client, cid, dardo, die=9, with_inspiration=True)).json()
    assert secondo["to_hit_total"] == 9 + primo["to_hit_bonus"] + dado, secondo
    assert (await _ability(client, cid, "fighter.superiority_dice"))["uses"] == 3
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [preciso]})
    assert r.status_code == 409  # già usata su questo tiro
    r = await client.post(f"/characters/{cid}/spells/{dardo}/roll_damage", json={"hit_options": ["fighter.maneuver_menacing"]})
    assert r.status_code == 409  # una sola manovra per attacco
    # l'attacco dopo è un altro tiro: nessun bonus
    assert (await _raggio(client, cid, dardo, die=9)).json()["to_hit_total"] == 9 + primo["to_hit_bonus"]
