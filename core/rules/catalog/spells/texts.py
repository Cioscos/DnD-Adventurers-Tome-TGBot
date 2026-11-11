"""Incantesimi che l'app non modella in numeri (tabella D e righe rinviate): uno stato con nome e durata (se durano) e un testo it/en, nessun modificatore."""
from __future__ import annotations

from dataclasses import replace

from core.rules.catalog.spells.defenses import DAY, HOUR, MIN10, both, txt
from core.rules.spell_effects import SpellChoice, SpellEffect, SpellTarget, SpellVariant
from core.rules.types import Modifier

MIN1, HOUR8 = 10, 4800  # round (6 secondi)
_SELF, _ALLY = SpellTarget("self"), SpellTarget("ally")


def _text(it: str, en: str, rounds: int | None = None, *, concentration: bool = False, track: bool = True) -> SpellVariant:
    """``track=False``: istantaneo, solo il promemoria per il GM. Altrimenti lo stato resta visibile per tutta la durata."""
    return SpellVariant(track=track, rounds=rounds, concentration=concentration, text=txt(it, en))


def _instant(it: str, en: str) -> SpellVariant:
    return _text(it, en, track=False)


def _upcast_type(*types: str) -> SpellChoice:
    """Il tipo dei dadi in più dello slot più alto, scelto al lancio: il tiro di danno li dà a quel tipo (``upcast_type``)."""
    return SpellChoice("upcast_type", txt("Tipo dei dadi in più (slot più alto)", "Type of the extra dice (higher slot)"), lambda _ed: list(types))


_POLYMORPH = {
    "2014": _text("La creatura prende la forma di una bestia: usa i PF della forma e il danno in eccesso passa alla forma normale. Applica il profilo a mano.",
                  "The creature takes a beast's form: it uses the form's HP and excess damage carries over to its normal form. Apply the stat block by hand.", HOUR, concentration=True),
    "2024": _text("La creatura prende la forma di una bestia: ottiene PF temporanei pari ai PF della forma e usa il profilo della bestia. Applica il profilo a mano.",
                  "The creature takes a beast's form: it gains temporary HP equal to the form's HP and uses the beast's stat block. Apply the stat block by hand.", HOUR, concentration=True),
}
_MIRROR_2014 = _text("Tre duplicati illusori: quando vieni attaccato tira un d20 per vedere se il colpo va a un duplicato (6+ con 3 duplicati, 8+ con 2, 11+ con 1). Lo risolve il GM.",
                     "Three illusory duplicates: when you are attacked roll a d20 to see whether the attack targets a duplicate (6+ with 3, 8+ with 2, 11+ with 1). The GM resolves it.", MIN1)
_MIRROR_2024 = _text("Tre duplicati illusori: un attacco contro di te può colpire un duplicato (un d6 per duplicato: con 3 o più colpisce un duplicato, che viene distrutto). Lo risolve il GM.",
                     "Three illusory duplicates: an attack against you may hit a duplicate (a d6 per duplicate: 3 or higher hits a duplicate, which is destroyed). The GM resolves it.", MIN1)
_BLINK = {
    "2014": _text("A fine di ogni tuo turno tira un d20: con 11 o più sparisci nel Piano Etereo e torni all'inizio del turno dopo. Lo gestisce il GM.",
                  "At the end of each of your turns roll a d20: on 11 or higher you vanish to the Ethereal Plane and return at the start of your next turn. The GM handles it.", MIN1),
    "2024": _text("A fine di ogni tuo turno tira un d6: con 4-6 sparisci nel Piano Etereo e torni all'inizio del turno dopo. Lo gestisce il GM.",
                  "At the end of each of your turns roll a d6: on 4-6 you vanish to the Ethereal Plane and return at the start of your next turn. The GM handles it.", MIN1),
}
_WIND_WALK = {
    "2014": _text("Tu e fino a dieci alleati diventate nubi con volo 90 m e resistenza ai danni delle armi non magiche; cambiare forma richiede 1 minuto, durante il quale si è incapacitati e immobili.",
                  "You and up to ten allies become clouds with a 300 ft fly speed and resistance to nonmagical weapon damage; changing form takes 1 minute, during which you are incapacitated and unable to move.", HOUR8),
    "2024": _text("Tu e fino a dieci alleati diventate nubi con volo 90 m e immunità a Prono e resistenza ai danni contundenti, perforanti e taglienti; tornare normali richiede 1 minuto, durante il quale si è storditi.",
                  "You and up to ten allies become clouds with a 300 ft fly speed, immunity to Prone and resistance to bludgeoning, piercing and slashing damage; reverting takes 1 minute, during which you are stunned.", HOUR8),
}

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("shield", ("shield",), ("Scudo", "Shield"), _SELF, both(SpellVariant(
        modifiers=lambda d: (Modifier("ac", 5),), rounds=1,
        text=txt("+5 alla CA fino all'inizio del tuo prossimo turno, anche contro l'attacco che l'ha scatenato; niente Dardo Incantato.",
                 "+5 to AC until the start of your next turn, including against the triggering attack; no Magic Missile.")))),
    SpellEffect("enlarge_reduce", ("enlarge-reduce",), ("Ingrandire/Ridurre", "Enlarge/Reduce"), _ALLY, both(_text(
        "Cambia taglia: se ingrandito vantaggio a prove e TS di Forza e +1d4 ai danni con le armi; se ridotto svantaggio e -1d4. Applicalo a mano.",
        "Changes size: enlarged gives advantage on Strength checks and saves and +1d4 weapon damage; reduced gives disadvantage and -1d4. Apply it by hand.", MIN1, concentration=True))),
    SpellEffect("polymorph", ("polymorph",), ("Metamorfosi", "Polymorph"), _ALLY, _POLYMORPH),
    SpellEffect("animal_shapes", ("animal-shapes",), ("Forme Animali", "Animal Shapes"), SpellTarget("allies", lambda slot: 20), {  # «un numero qualsiasi»: 20 è più di ogni serata
        "2014": _text("Le creature consenzienti scelte diventano bestie: usano i PF della forma e il danno in eccesso passa alla forma normale. Applica i profili a mano.",
                      "The chosen willing creatures become beasts: they use the form's HP and excess damage carries over to the normal form. Apply the stat blocks by hand.", DAY, concentration=True),
        "2024": _text("Le creature consenzienti scelte diventano bestie e ottengono PF temporanei pari ai PF della forma; senza concentrazione. Applica i profili a mano.",
                      "The chosen willing creatures become beasts and gain temporary HP equal to the form's HP; no concentration. Apply the stat blocks by hand.", DAY)}),
    SpellEffect("shapechange", ("shapechange",), ("Trasformazione", "Metamorfosi Suprema", "Shapechange"), _SELF, {
        "2014": _text("Prendi la forma di una creatura vista e ne usi profilo, PF e Dadi Vita, tenendo allineamento e punteggi mentali; il danno in eccesso passa alla forma normale. Applica il profilo a mano.",
                      "You take the form of a creature you have seen and use its stat block, HP and Hit Dice, keeping alignment and mental scores; excess damage carries over to your normal form. Apply the stat block by hand.", HOUR, concentration=True),
        "2024": _text("Prendi la forma di una creatura già vista e ne usi il profilo, tenendo PF, Dadi Vita, punteggi mentali e Lancio di Incantesimi; ottieni PF temporanei pari ai PF della forma e finisce se si esauriscono. Applica il profilo a mano.",
                      "You take the form of a creature you have seen and use its stat block, keeping your HP, Hit Dice, mental scores and spellcasting; you gain temporary HP equal to the form's HP and it ends if they run out. Apply the stat block by hand.", HOUR, concentration=True)}),
    SpellEffect("true_polymorph", ("true-polymorph",), ("Metamorfosi Pura", "True Polymorph"), _ALLY, both(_text(
        "Trasforma una creatura in un'altra o in un oggetto; se la concentrazione dura un'ora la forma diventa permanente. Applica il profilo a mano.",
        "Transforms a creature into another or an object; if concentration lasts an hour the change becomes permanent. Apply the stat block by hand.", HOUR, concentration=True))),
    SpellEffect("alter_self", ("alter-self",), ("Alterare Se Stesso", "Alter Self"), _SELF, {
        "2014": _text("Scegli: respirare sott'acqua e nuotare, cambiare aspetto, oppure armi naturali (colpi senz'armi 1d6, competente, magici con +1 a colpire e ai danni). Il tipo di danno delle armi naturali lo decidi a mano.",
                      "Choose: breathe underwater and swim, change appearance, or natural weapons (unarmed strikes 1d6, proficient, magical with +1 to attack and damage). You choose the natural weapons' damage type by hand.", HOUR, concentration=True),
        "2024": _text("Scegli: respirare sott'acqua e nuotare, cambiare aspetto, oppure armi naturali (Colpo Senz'Armi 1d6, con il modificatore da incantatore per colpire e per i danni). Il tipo di danno delle armi naturali lo decidi a mano.",
                      "Choose: breathe underwater and swim, change appearance, or natural weapons (Unarmed Strike 1d6, using your spellcasting modifier for attack and damage). You choose the natural weapons' damage type by hand.", HOUR, concentration=True)}),
    SpellEffect("gaseous_form", ("gaseous-form",), ("Forma Gassosa", "Gaseous Form"), _ALLY, {
        "2014": _text("Nube con volo 3 m, resistenza ai danni non magici e vantaggio ai TS di Forza, Destrezza e Costituzione; non può attaccare né lanciare incantesimi.",
                      "A cloud with a 10 ft fly speed, resistance to nonmagical damage and advantage on Strength, Dexterity and Constitution saves; it cannot attack or cast spells.", HOUR, concentration=True),
        "2024": _text("Nube con volo 3 m, immunità a Prono, resistenza ai danni contundenti, perforanti e taglienti e vantaggio ai TS di Forza, Destrezza e Costituzione; non può attaccare né lanciare incantesimi.",
                      "A cloud with a 10 ft fly speed, immunity to Prone, resistance to bludgeoning, piercing and slashing damage and advantage on Strength, Dexterity and Constitution saves; it cannot attack or cast spells.", HOUR, concentration=True)}),
    SpellEffect("wind_walk", ("wind-walk",), ("Camminare nel Vento", "Wind Walk"), SpellTarget("allies", lambda slot: 11), _WIND_WALK),
    SpellEffect("mirror_image", ("mirror-image",), ("Immagine Speculare", "Mirror Image"), _SELF, {"2014": _MIRROR_2014, "2024": _MIRROR_2024}),
    SpellEffect("sanctuary", ("sanctuary",), ("Santuario", "Sanctuary"), _ALLY, {
        "2014": _text("Chi vuole attaccare il protetto o bersagliarlo con un incantesimo fa un TS Saggezza, altrimenti sceglie un altro bersaglio. Finisce se il protetto attacca o lancia un incantesimo su un nemico.",
                      "A creature that wants to attack the ward or target it with a spell makes a Wisdom save or picks another target. It ends if the ward attacks or casts a spell at an enemy.", MIN1),
        "2024": _text("Chi vuole attaccare il protetto o bersagliarlo con un incantesimo fa un TS Saggezza, altrimenti sceglie un altro bersaglio. Finisce se il protetto fa un tiro per colpire, lancia un incantesimo o infligge danni.",
                      "A creature that wants to attack the ward or target it with a spell makes a Wisdom save or picks another target. It ends if the ward makes an attack roll, casts a spell or deals damage.", MIN1)}),
    SpellEffect("blink", ("blink",), ("Intermittenza", "Blink"), _SELF, _BLINK),
    SpellEffect("glibness", ("glibness",), ("Loquacità", "Parlantina", "Glibness"), _SELF, both(_text(
        "Nelle prove di Carisma, se il dado dà meno di 15 conta 15.",
        "On Charisma checks, a die roll below 15 counts as 15.", HOUR))),
    SpellEffect("conjure_celestial", ("conjure-celestial",), ("Evoca Celestiale", "Conjure Celestial"), _SELF, {"2024": _text(
        "Un cilindro di luce (raggio 3 m, alto 12 m, lo muovi di 9 m): per ogni creatura a tua scelta al suo interno scegli Luce Curativa (4d12 + il tuo modificatore PF recuperati) oppure Luce Ardente (TS Destrezza, 6d12 radiante, metà se supera); +1d12 per slot oltre il 7°. Applicali a mano.",
        "A cylinder of light (10 ft radius, 40 ft high, you move it 30 ft): for each creature of your choice inside it, choose Healing Light (4d12 + your modifier HP regained) or Searing Light (Dexterity save, 6d12 radiant, half on a success); +1d12 per slot above 7th. Apply them by hand.", MIN10, concentration=True)}),
    SpellEffect("antilife_shell", ("antilife-shell",), ("Guscio Anti-Vita", "Antilife Shell"), _SELF, both(_text(
        "Barriera di 3 m intorno a te: le creature viventi non la attraversano. Zona, nessun effetto sulla scheda.",
        "A 10 ft barrier around you: living creatures cannot pass it. A zone, no effect on the sheet.", HOUR, concentration=True))),
    SpellEffect("antimagic_field", ("antimagic-field",), ("Campo Anti-Magia", "Antimagic Field"), _SELF, both(_text(
        "Sfera di 3 m: la magia al suo interno è soppressa. Zona: tienine conto a mano.",
        "A 10 ft sphere: magic inside is suppressed. A zone: account for it by hand.", HOUR, concentration=True))),
    SpellEffect("globe_of_invulnerability", ("globe-of-invulnerability",), ("Globo di Invulnerabilità", "Globe of Invulnerability"), _SELF, both(_text(
        "Sfera di 3 m: gli incantesimi di 5° livello o inferiore lanciati da fuori non la penetrano. Zona: tienine conto a mano.",
        "A 10 ft sphere: spells of 5th level or lower cast from outside do not enter. A zone: account for it by hand.", MIN1, concentration=True))),
    SpellEffect("magic_circle", ("magic-circle",), ("Cerchio Magico", "Magic Circle"), _SELF, both(_text(
        "Cilindro di 3 m: celestiali, elementali, folletti, immondi e non morti ne sono ostacolati. Zona: tienine conto a mano.",
        "A 10 ft cylinder: celestials, elementals, fey, fiends and undead are hindered by it. A zone: account for it by hand.", HOUR))),
    SpellEffect("leomunds_tiny_hut", ("leomunds-tiny-hut",), ("Capanna di Leomund", "Leomund's Tiny Hut"), _SELF, both(_text(
        "Cupola di 3 m che ripara dagli elementi e dalle creature esterne. Zona: nessun effetto sulla scheda.",
        "A 10 ft dome that shelters from the elements and outside creatures. A zone: no effect on the sheet.", HOUR8))),
    SpellEffect("hallow", ("hallow",), ("Santificare", "Hallow"), _SELF, both(_text(
        "Area di 18 m consacrata finché non è dissolta, con un effetto extra a scelta. Zona: tienine conto a mano.",
        "A 60 ft area consecrated until dispelled, with a chosen extra effect. A zone: account for it by hand."))),
    SpellEffect("destructive_wave", ("destructive-wave",), ("Onda Distruttiva", "Destructive Wave"), _SELF, both(_instant(
        "Onda di tuono in 9 m: 5d6 tuono più 5d6 radiante o necrotico e Prono, TS Costituzione: chi supera dimezza i danni e resta in piedi. Tira i danni a mano.",
        "A thunder wave in 30 ft: 5d6 thunder plus 5d6 radiant or necrotic and Prone, Constitution save: on a success half damage and not Prone. Roll the damage by hand."))),
    SpellEffect("flame_strike", ("flame-strike",), ("Colpo Infuocato", "Flame Strike"), _SELF, {"2014": replace(_instant(
        "Colonna di fuoco divino: 4d6 fuoco più 4d6 radiante, TS Destrezza. Con uno slot più alto, +1d6 per livello del tipo scelto al lancio (fuoco o radiante): li tira il tiro di danno.",
        "A column of divine fire: 4d6 fire plus 4d6 radiant, Dexterity save. At a higher slot, +1d6 per level of the type chosen at the cast (fire or radiant): the damage roll rolls them."),
        choices=(_upcast_type("fire", "radiant"),))}),
    SpellEffect("hunger_of_hadar", ("hunger-of-hadar",), ("Fame di Hadar", "Hunger of Hadar"), _SELF, {"2024": replace(_text(
        "Sfera di oscurità di 6 m che danneggia freddo e acido chi vi sta. Con uno slot più alto il danno cresce di 1d6 del tipo scelto al lancio (freddo o acido): applicalo a mano.",
        "A 20 ft sphere of darkness that deals cold and acid damage to those in it. At a higher slot the damage grows by 1d6 of the type chosen at the cast (cold or acid): apply it by hand.", MIN1, concentration=True),
        choices=(_upcast_type("cold", "acid"),))}),
    SpellEffect("conjure_barrage", ("conjure-barrage",), ("Evoca Raffica", "Conjure Barrage"), _SELF, {"2014": _instant(
        "Cono di 18 m: 3d8 danni del tipo dell'arma usata, TS Destrezza per metà. Tira i danni a mano.",
        "A 60 ft cone: 3d8 damage of the used weapon's type, Dexterity save for half. Roll the damage by hand.")}),
    SpellEffect("conjure_volley", ("conjure-volley",), ("Evoca Pioggia di Armi", "Conjure Volley"), _SELF, {"2014": _instant(
        "Cilindro di 12 m: 8d8 danni del tipo dell'arma usata, TS Destrezza per metà. Tira i danni a mano.",
        "A 40 ft radius cylinder: 8d8 damage of the used weapon's type, Dexterity save for half. Roll the damage by hand.")}),
    SpellEffect("wish", ("wish",), ("Desiderio", "Wish"), _SELF, both(_instant(
        "Duplica un incantesimo fino all'8° livello oppure realizza un desiderio a discrezione del GM. Nessun effetto automatico.",
        "Duplicates a spell of up to 8th level or grants a wish at the GM's discretion. No automatic effect."))),
)
