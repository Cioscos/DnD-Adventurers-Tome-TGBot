"""Controlli delle decisioni dell'utente D-021…D-044 (tests/caccia/decisioni.md), scritti nel giro che le applica."""
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
