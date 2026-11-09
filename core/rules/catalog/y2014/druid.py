"""Druido 2014 e i suoi circoli: Terra (con i territori) e Luna.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/druid.md``; i testi sono nostri, mai quelli del manuale.
La Forma Selvatica vive nei compagni (``kind="wild_shape"``): limiti, durata e PF della forma stanno in
``core/rules/forms.py`` e ``api/services/wild_shape.py``, qui ci sono gli usi e le righe del catalogo.
"""
from __future__ import annotations

from core.rules.catalog._common import feature
from core.rules.types import ChoiceSpec, FeatureSpec, Modifier, OnUse, RollOptionSpec, RuleContext, TargetEffect, Uses

ED, CK = "2014", "druid"
WILD_SHAPE = f"{CK}.wild_shape"

# (chiave, nome it, nome en)
TERRITORIES = (
    ("arctic", "Artico", "Arctic"), ("coast", "Costa", "Coast"), ("desert", "Deserto", "Desert"),
    ("forest", "Foresta", "Forest"), ("grassland", "Prateria", "Grassland"), ("mountain", "Montagna", "Mountain"),
    ("swamp", "Palude", "Swamp"), ("underdark", "Underdark", "Underdark"),
)

# territorio -> due incantesimi (``srd_index``) ai livelli di druido 3, 5, 7 e 9
TERRITORY_SPELLS: dict[str, tuple[tuple[str, str], ...]] = {
    "arctic": (("hold-person", "spike-growth"), ("slow", "sleet-storm"), ("freedom-of-movement", "ice-storm"),
               ("commune-with-nature", "cone-of-cold")),
    "coast": (("mirror-image", "misty-step"), ("water-walk", "water-breathing"), ("control-water", "freedom-of-movement"),
              ("conjure-elemental", "scrying")),
    "desert": (("blur", "silence"), ("create-food-and-water", "protection-from-energy"), ("blight", "hallucinatory-terrain"),
               ("wall-of-stone", "insect-plague")),
    "forest": (("spider-climb", "barkskin"), ("plant-growth", "call-lightning"), ("divination", "freedom-of-movement"),
               ("commune-with-nature", "tree-stride")),
    "grassland": (("invisibility", "pass-without-trace"), ("daylight", "haste"), ("divination", "freedom-of-movement"),
                  ("insect-plague", "dream")),
    "mountain": (("spike-growth", "spider-climb"), ("meld-into-stone", "lightning-bolt"), ("stoneskin", "stone-shape"),
                 ("wall-of-stone", "passwall")),
    "swamp": (("acid-arrow", "darkness"), ("water-walk", "stinking-cloud"), ("freedom-of-movement", "locate-creature"),
              ("insect-plague", "scrying")),
    "underdark": (("spider-climb", "web"), ("gaseous-form", "stinking-cloud"), ("greater-invisibility", "stone-shape"),
                  ("cloudkill", "insect-plague")),
}


def spell_dc(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return 8 + ctx.char.proficiency_bonus + effective_ability_mod(ctx.char, "wisdom")


def _no_options(_ctx: RuleContext) -> list[str]:
    return []


def _sanctuary_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    """Rifugio della Natura: la bestia o la pianta che attacca fa un TS Saggezza; se lo supera non subisce più l'effetto per
    24 ore (le «24 ore» sono fino al prossimo riposo lungo di chi lo usa). Se fallisce cambia bersaglio o manca da sola."""
    return TargetEffect(condition="custom:nature_ward", save_ability="wisdom", save_dc=spell_dc(ctx), rounds=1,
                        immune_on_success=True)


LANDS_STRIDE = RollOptionSpec(
    key=f"{CK}.lands_stride", phase="before", rolls=("save",), mode="advantage",
    label={"it": "Andatura sul Territorio: il TS è contro una pianta creata o manipolata con la magia per ostacolarti?",
           "en": "Land's Stride: is the save against a plant magically created or manipulated to impede movement?"})


def _territory_summary(key: str) -> tuple[str, str]:
    """Gli incantesimi del territorio per livello da druido, con i nomi del catalogo degli incantesimi concessi."""
    from core.rules.catalog.granted_spells import GRANTED_SPELLS
    tiers = list(zip((3, 5, 7, 9), TERRITORY_SPELLS[key]))
    lead = {"it": "Livello da druido ", "en": "Druid level "}
    return tuple(lead[lang] + "; ".join(f"{level}: " + ", ".join(GRANTED_SPELLS[s].name[lang] for s in spells)
                                        for level, spells in tiers) for lang in ("it", "en"))


def _territory_rows() -> list[FeatureSpec]:
    """Una riga per territorio (al 2° livello, quando si sceglie) e, senza riga propria, gli incantesimi ai livelli 3, 5, 7, 9."""
    rows: list[FeatureSpec] = []
    for key, it, en in TERRITORIES:
        title = f"{it} / {en} (Circolo della Terra 2, pag. 68)"
        rows.append(feature(
            f"territory_{key}", CK, ED, 2, title, (f"{it} (territorio)", f"{en} (land)"),
            _territory_summary(key), subclass="land", option_group="territory", option_key=key))
        for level, spells in zip((3, 5, 7, 9), TERRITORY_SPELLS[key]):
            rows.append(feature(
                f"territory_{key}_{level}", CK, ED, level, title, (f"{it} (territorio)", f"{en} (land)"),
                (f"Incantesimi del circolo del {level}° livello.", f"Circle spells gained at level {level}."),
                subclass="land", option_group="territory", option_key=key, granted_spells=spells, no_row=True,
                covered_by=f"{CK}.territory_{key} (stessa voce della mappatura) e test_each_territory_grants_its_spells_at_levels_3_5_7_and_9"))
    return rows


FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita e Competenze / Hit Points and Proficiencies (Druido 1, pag. 65)",
            ("Punti Ferita", "Hit Points"),
            ("Dado vita d8; al 1° livello 8 + Costituzione, poi d8 (o 5) + Costituzione.",
             "Hit die d8; level 1 gives 8 + Constitution, then d8 (or 5) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d8_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Punti Ferita e Competenze / Hit Points and Proficiencies (Druido 1, pag. 65)",
            ("Competenze", "Proficiencies"),
            ("Armature leggere e medie, scudi (non di metallo), dieci armi druidiche, borsa da erborista, TS Intelligenza e Saggezza, 2 abilità.",
             "Light and medium armor, shields (nonmetal), ten druidic weapons, herbalism kit, Intelligence and Wisdom saves, 2 skills."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies) e la scelta ClassSkillChoice; "
                                    "test_class_proficiencies_first_class_and_multiclass"),
    feature("equipment", CK, ED, 1, "Punti Ferita e Competenze / Hit Points and Proficiencies (Druido 1, pag. 65)",
            ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: scudo di legno o arma semplice, scimitarra o arma semplice da mischia, armatura di cuoio, dotazione da esploratore, focus druidico.",
             "Starting gear: a wooden shield or simple weapon, a scimitar or simple melee weapon, leather armor, explorer's pack, druidic focus."),
            no_row=True, covered_by="lavori-successivi"),
    feature("druidic", CK, ED, 1, "Druidico / Druidic (Druido 1, pag. 66)", ("Druidico", "Druidic"),
            ("Conosci il Druidico, il linguaggio segreto dei druidi.", "You know Druidic, the secret language of druids."),
            no_row=True, covered_by="core/rules/proficiencies.py (languages della classe); test_druidic_is_among_the_languages"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Druido 1, pag. 66)", ("Incantesimi", "Spellcasting"),
            ("Saggezza; CD 8 + competenza + Saggezza. Trucchetti 2/3/4, preparati Saggezza + livello, slot da tabella, rituali; focus druidico.",
             "Wisdom; DC 8 + proficiency + Wisdom. Cantrips 2/3/4, prepared Wisdom + level, slots by table, rituals; a druidic focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, prepared_limit, slots_for, caster_stats); "
                                    "test_cantrips_follow_the_class_table"),
    feature("wild_shape", CK, ED, 2, "Forma Selvatica / Wild Shape (Druido 2, pag. 66)", ("Forma Selvatica", "Wild Shape"),
            ("Assumi una bestia già vista (azione; bonus per la Luna) entro i limiti del livello. 2 usi per riposo breve o lungo, illimitati al 20°. Dura metà livello in ore.",
             "Take the shape of a beast you have seen (action; bonus for the Moon) within your level's limits. 2 uses per short or long rest, unlimited at 20th. Lasts half your level in hours."),
            "action", uses=Uses(table={2: 2}, unlimited_from=20), restoration="short_rest"),
    feature("beast_shapes", CK, ED, 2, "Forme Bestiali / Beast Shapes (Druido 2, pag. 66)", ("Forme Bestiali", "Beast Shapes"),
            ("GS massimo 1/4 senza nuotare né volare al 2°; 1/2 senza volare al 4°; 1 all'8°. Solo bestie. Le forme fuori limite chiedono conferma.",
             "Max CR 1/4 with no swim or fly at 2nd; 1/2 with no fly at 4th; 1 at 8th. Beasts only. Forms outside the limits ask for confirmation."),
            passive=True),
    feature("improved_wild_shape", CK, ED, 4, "Forma Selvatica Migliorata / Improved Wild Shape (Druido 4, pag. 65)",
            ("Forma Selvatica Migliorata", "Improved Wild Shape"),
            ("Dal 4° livello puoi assumere bestie di GS 1/2 che nuotano, ma che non volano.",
             "From 4th level you can take beasts of CR 1/2 that swim, but that do not fly."), passive=True),
    feature("improved_wild_shape_8", CK, ED, 8, "Forma Selvatica Migliorata / Improved Wild Shape (Druido 4, pag. 65)",
            ("Forma Selvatica Migliorata (8°)", "Improved Wild Shape (8th)"),
            ("Dall'8° livello puoi assumere bestie di GS 1, anche volanti.",
             "From 8th level you can take beasts of CR 1, flying ones included."), passive=True),
    feature("druid_circle", CK, ED, 2, "Circolo Druidico / Druid Circle (Druido 2, pag. 67)", ("Circolo Druidico", "Druid Circle"),
            ("Al 2° livello si sceglie il Circolo della Terra o il Circolo della Luna.",
             "At 2nd level you choose the Circle of the Land or the Circle of the Moon."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Druido 4, pag. 67)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level"),
    feature("timeless_body", CK, ED, 18, "Corpo Senza Tempo / Timeless Body (Druido 18, pag. 67)",
            ("Corpo Senza Tempo", "Timeless Body"),
            ("Invecchi di 1 anno ogni 10 che passano. Lo gestisce il GM.", "You age 1 year for every 10 that pass. The GM handles it."),
            passive=True),
    feature("beast_spells", CK, ED, 18, "Incantesimi Bestiali / Beast Spells (Druido 18, pag. 67)",
            ("Incantesimi Bestiali", "Beast Spells"),
            ("In forma bestiale lanci incantesimi da druido con componenti verbali e somatiche, ma non fornisci materiali.",
             "In beast shape you cast druid spells with verbal and somatic components, but you cannot provide materials."),
            cast_in_form=True),
    feature("archdruid", CK, ED, 20, "Arcidruido / Archdruid (Druido 20, pag. 67)", ("Arcidruido", "Archdruid"),
            ("Forma Selvatica illimitata. Ignori le componenti verbali, somatiche e materiali senza costo dei tuoi incantesimi da druido.",
             "Unlimited Wild Shape. You ignore the verbal, somatic and costless material components of your druid spells."),
            ignores_components=True),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Druido / Multiclassing: Druid (Regole opzionali, pag. 163)",
            ("Multiclasse: Druido", "Multiclassing: Druid"),
            ("Requisito Saggezza 13. Da multiclasse: armature leggere e medie e scudi; gli slot sommano i livelli interi.",
             "Requires Wisdom 13. As a multiclass: light and medium armor and shields; spell slots add up full levels."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),

    # Circolo della Terra
    feature("bonus_cantrip", CK, ED, 2, "Trucchetto Bonus / Bonus Cantrip (Circolo della Terra 2, pag. 68)",
            ("Trucchetto Bonus", "Bonus Cantrip"),
            ("Impari un trucchetto da druido in più, fuori dal limite dei trucchetti.",
             "You learn one extra druid cantrip, outside the cantrip limit."),
            subclass="land",
            choices=(ChoiceSpec(group="bonus_cantrip", levels={2: 1}, options=_no_options, spell_pick="extra", spell_level=0, spell_list="druid"),)),
    feature("natural_recovery", CK, ED, 2, "Recupero Naturale / Natural Recovery (Circolo della Terra 2, pag. 68)",
            ("Recupero Naturale", "Natural Recovery"),
            ("Durante un riposo breve recuperi slot spesi per un livello totale fino a metà del livello da druido (per eccesso), nessuno di 6° o più. Un uso per riposo lungo.",
             "During a short rest you regain spent slots totaling up to half your druid level (rounded up), none of 6th or higher. One use per long rest."),
            "special", subclass="land", uses=Uses(table={2: 1}), restoration="long_rest", passive=False),
    feature("circle_spells", CK, ED, 2, "Incantesimi del Circolo / Circle Spells (Circolo della Terra 2, pag. 68)",
            ("Incantesimi del Circolo", "Circle Spells"),
            ("Scegli un territorio: dal 3° livello ricevi i suoi incantesimi, sempre preparati e fuori dal limite.",
             "Choose a land: from 3rd level you gain its spells, always prepared and outside the limit."),
            subclass="land", no_row=True,
            choices=(ChoiceSpec(group="territory", levels={2: 1}, options=lambda _ctx: [k for k, _it, _en in TERRITORIES]),),
            covered_by="ChoiceSpec territory di questa riga e le righe dei territori; test_the_territory_is_a_choice_of_eight_made_at_the_circle"),
    *_territory_rows(),
    feature("lands_stride", CK, ED, 6, "Andatura sul Territorio / Land's Stride (Circolo della Terra 6, pag. 69)",
            ("Andatura sul Territorio", "Land's Stride"),
            ("Terreno difficile non magico e piante non magiche non ti rallentano né ti feriscono. Vantaggio ai TS contro piante magiche che ostacolano.",
             "Nonmagical difficult terrain and plants cost you nothing and never hurt you. Advantage on saves against magical plants that impede."),
            subclass="land", roll_options=(LANDS_STRIDE,)),
    feature("natures_ward", CK, ED, 10, "Interdizione della Natura / Nature's Ward (Circolo della Terra 10, pag. 69)",
            ("Interdizione della Natura", "Nature's Ward"),
            ("Immune a veleno (danni e condizione) e malattie. Elementali e folletti non possono affascinarti né spaventarti.",
             "Immune to poison (damage and condition) and disease. Elementals and fey cannot charm or frighten you."),
            subclass="land", condition_immunities=("poisoned",),
            modifiers=(Modifier("immunity:poison", 1, source=f"feature:{CK}.natures_ward"),)),
    feature("natures_sanctuary", CK, ED, 14, "Rifugio della Natura / Nature's Sanctuary (Circolo della Terra 14, pag. 69)",
            ("Rifugio della Natura", "Nature's Sanctuary"),
            ("Una bestia o una pianta che ti attacca fa un TS Saggezza (CD incantesimi): se fallisce cambia bersaglio o manca; chi lo supera è immune per 24 ore.",
             "A beast or plant that attacks you makes a Wisdom save (spell DC): on a failure it picks another target or misses; on a success it is immune for 24 hours."),
            subclass="land", on_use=OnUse(target_effect=_sanctuary_effect)),

    # Circolo della Luna
    feature("circle_forms", CK, ED, 2, "Forme del Circolo / Circle Forms (Circolo della Luna 2, pag. 69)",
            ("Forme del Circolo", "Circle Forms"),
            ("GS massimo 1 al 2°; dal 6° livello pari al livello da druido diviso 3 per difetto. Restano i limiti di volo e nuoto del livello.",
             "Max CR 1 at 2nd; from 6th, your druid level divided by 3 rounded down. The level's fly and swim limits still apply."),
            subclass="moon", passive=True),
    feature("combat_wild_shape", CK, ED, 2, "Forma Selvatica da Combattimento / Combat Wild Shape (Circolo della Luna 2, pag. 69)",
            ("Forma Selvatica da Combattimento", "Combat Wild Shape"),
            ("Forma Selvatica come azione bonus. In forma, azione bonus e uno slot: la forma recupera 1d8 PF per livello dello slot.",
             "Wild Shape as a bonus action. While shaped, a bonus action and a spell slot heal the form 1d8 per slot level."),
            "bonus_action", subclass="moon"),
    feature("primal_strike", CK, ED, 6, "Colpo Primordiale / Primal Strike (Circolo della Luna 6, pag. 69)",
            ("Colpo Primordiale", "Primal Strike"),
            ("I tuoi attacchi in forma bestiale contano come magici per superare resistenze e immunità ai danni non magici.",
             "Your attacks in beast form count as magical for overcoming resistance and immunity to nonmagical damage."),
            subclass="moon", passive=True),
    feature("elemental_wild_shape", CK, ED, 10, "Forma Selvatica Elementale / Elemental Wild Shape (Circolo della Luna 10, pag. 69)",
            ("Forma Selvatica Elementale", "Elemental Wild Shape"),
            ("Spendi due usi di Forma Selvatica e assumi un elementale d'acqua, aria, fuoco o terra, senza i limiti di GS della tabella.",
             "Spend two Wild Shape uses to become an air, earth, fire or water elemental, with none of the table's CR limits."),
            "bonus_action", subclass="moon"),
    feature("thousand_forms", CK, ED, 14, "Mille Forme / Thousand Forms (Circolo della Luna 14, pag. 69)",
            ("Mille Forme", "Thousand Forms"),
            ("Lanci alterare se stessi a volontà, senza slot; resta a concentrazione.",
             "You cast alter self at will, with no slot; it still needs concentration."),
            subclass="moon", granted_spells=("alter-self",), at_will_spells=("alter-self",)),
)
