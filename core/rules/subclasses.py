"""Catalogo delle sottoclassi per edizione e riconoscimento del testo scritto dall'utente."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from core.rules.edition import character_edition, class_key as row_class_key
from core.rules.types import Edition


@dataclass(frozen=True)
class SubclassSpec:
    key: str
    class_key: str
    edition: Edition
    name: dict[str, str]
    aliases: tuple[str, ...]
    choice_level: int


# (chiave, titolo it, titolo en) dalle schede in docs/superpowers/rules/<anno>/classes/.
_RAW: dict[str, dict[str, list[tuple[str, str, str]]]] = {
    "2014": {
        "barbarian": [("berserker", "Cammino del Berserker", "Path of the Berserker"),
                      ("totem_warrior", "Cammino del Combattente Totemico", "Path of the Totem Warrior")],
        "bard": [("lore", "Collegio della Sapienza", "College of Lore"),
                 ("valor", "Collegio del Valore", "College of Valor")],
        "cleric": [("knowledge", "Dominio della Conoscenza", "Knowledge Domain"),
                   ("war", "Dominio della Guerra", "War Domain"),
                   ("trickery", "Dominio dell'Inganno", "Trickery Domain"),
                   ("light", "Dominio della Luce", "Light Domain"),
                   ("nature", "Dominio della Natura", "Nature Domain"),
                   ("tempest", "Dominio della Tempesta", "Tempest Domain"),
                   ("life", "Dominio della Vita", "Life Domain")],
        "druid": [("land", "Circolo della Terra", "Circle of the Land"),
                  ("moon", "Circolo della Luna", "Circle of the Moon")],
        "fighter": [("champion", "Campione", "Champion"),
                    ("battle_master", "Maestro di Battaglia", "Battle Master"),
                    ("eldritch_knight", "Cavaliere Mistico", "Eldritch Knight")],
        "monk": [("open_hand", "Via della Mano Aperta", "Way of the Open Hand"),
                 ("shadow", "Via dell'Ombra", "Way of Shadow"),
                 ("four_elements", "Via dei Quattro Elementi", "Way of the Four Elements")],
        "paladin": [("devotion", "Giuramento di Devozione", "Oath of Devotion"),
                    ("ancients", "Giuramento degli Antichi", "Oath of the Ancients"),
                    ("vengeance", "Giuramento di Vendetta", "Oath of Vengeance")],
        "ranger": [("hunter", "Cacciatore", "Hunter"),
                   ("beast_master", "Signore delle Bestie", "Beast Master")],
        "rogue": [("thief", "Furfante", "Thief"), ("assassin", "Assassino", "Assassin"),
                  ("arcane_trickster", "Mistificatore Arcano", "Arcane Trickster")],
        "sorcerer": [("draconic", "Discendenza Draconica", "Draconic Bloodline"),
                     ("wild_magic", "Magia Selvaggia", "Wild Magic")],
        "warlock": [("archfey", "Il Signore Fatato", "The Archfey"),
                    ("fiend", "L'Immondo", "The Fiend"),
                    ("great_old_one", "Il Grande Antico", "The Great Old One")],
        "wizard": [("abjuration", "Scuola di Abiurazione", "School of Abjuration"),
                   ("enchantment", "Scuola di Ammaliamento", "School of Enchantment"),
                   ("divination", "Scuola di Divinazione", "School of Divination"),
                   ("conjuration", "Scuola di Evocazione", "School of Conjuration"),
                   ("illusion", "Scuola di Illusione", "School of Illusion"),
                   ("evocation", "Scuola di Invocazione", "School of Evocation"),
                   ("necromancy", "Scuola di Necromanzia", "School of Necromancy"),
                   ("transmutation", "Scuola di Trasmutazione", "School of Transmutation")],
    },
    "2024": {
        "barbarian": [("berserker", "Cammino del Berserker", "Path of the Berserker"),
                      ("wild_heart", "Cammino del Cuore Selvaggio", "Path of the Wild Heart"),
                      ("world_tree", "Cammino dell'Albero del Mondo", "Path of the World Tree"),
                      ("zealot", "Cammino dello Zelota", "Path of the Zealot")],
        "bard": [("dance", "Collegio della Danza", "College of Dance"),
                 ("glamour", "Collegio dell'Incanto", "College of Glamour"),
                 ("lore", "Collegio della Sapienza", "College of Lore"),
                 ("valor", "Collegio del Valore", "College of Valor")],
        "cleric": [("life", "Dominio della Vita", "Life Domain"),
                   ("light", "Dominio della Luce", "Light Domain"),
                   ("trickery", "Dominio dell'Inganno", "Trickery Domain"),
                   ("war", "Dominio della Guerra", "War Domain")],
        "druid": [("land", "Circolo della Terra", "Circle of the Land"),
                  ("moon", "Circolo della Luna", "Circle of the Moon"),
                  ("sea", "Circolo del Mare", "Circle of the Sea"),
                  ("stars", "Circolo delle Stelle", "Circle of the Stars")],
        "fighter": [("battle_master", "Maestro di Battaglia", "Battle Master"),
                    ("champion", "Campione", "Champion"),
                    ("eldritch_knight", "Cavaliere Mistico", "Eldritch Knight"),
                    ("psi_warrior", "Guerriero Psionico", "Psi Warrior")],
        "monk": [("mercy", "Guerriero della Misericordia", "Warrior of Mercy"),
                 ("shadow", "Guerriero dell'Ombra", "Warrior of Shadow"),
                 ("elements", "Guerriero degli Elementi", "Warrior of the Elements"),
                 ("open_hand", "Guerriero della Mano Aperta", "Warrior of the Open Hand")],
        "paladin": [("devotion", "Giuramento di Devozione", "Oath of Devotion"),
                    ("glory", "Giuramento della Gloria", "Oath of Glory"),
                    ("ancients", "Giuramento degli Antichi", "Oath of the Ancients"),
                    ("vengeance", "Giuramento di Vendetta", "Oath of Vengeance")],
        "ranger": [("beast_master", "Signore delle Bestie", "Beast Master"),
                   ("fey_wanderer", "Viandante Fatato", "Fey Wanderer"),
                   ("gloom_stalker", "Stalker delle Tenebre", "Gloom Stalker"),
                   ("hunter", "Cacciatore", "Hunter")],
        "rogue": [("arcane_trickster", "Mistificatore Arcano", "Arcane Trickster"),
                  ("assassin", "Assassino", "Assassin"),
                  ("soulknife", "Coltello dell'Anima", "Soulknife"),
                  ("thief", "Furfante", "Thief")],
        "sorcerer": [("aberrant", "Stregoneria Aberrante", "Aberrant Sorcery"),
                     ("clockwork", "Stregoneria Meccanica", "Clockwork Sorcery"),
                     ("draconic", "Stregoneria Draconica", "Draconic Sorcery"),
                     ("wild_magic", "Magia Selvaggia", "Wild Magic Sorcery")],
        "warlock": [("archfey", "Patrono Fatato", "Archfey Patron"),
                    ("celestial", "Patrono Celestiale", "Celestial Patron"),
                    ("fiend", "Patrono Immondo", "Fiend Patron"),
                    ("great_old_one", "Patrono Grande Antico", "Great Old One Patron")],
        "wizard": [("abjurer", "Abiuratore", "Abjurer"), ("diviner", "Divinatore", "Diviner"),
                   ("evoker", "Invocatore", "Evoker"), ("illusionist", "Illusionista", "Illusionist")],
    },
}
# Livello a cui si sceglie la sottoclasse (2014 varia per classe; 2024 sempre 3).
_CHOICE_2014 = {"cleric": 1, "sorcerer": 1, "warlock": 1, "druid": 2, "wizard": 2}


@lru_cache(maxsize=None)
def _catalog(edition: str) -> dict[str, tuple[SubclassSpec, ...]]:
    return {
        ck: tuple(
            SubclassSpec(key, ck, edition, {"it": it, "en": en}, (),
                         _CHOICE_2014.get(ck, 3) if edition == "2014" else 3)
            for key, it, en in rows
        )
        for ck, rows in _RAW[edition].items()
    }


def subclasses_for(edition: str, class_key: str) -> list[SubclassSpec]:
    return list(_catalog(edition if edition in _RAW else "2014").get(class_key, ()))


_LEAD = re.compile(
    r"^(?:cammino|circolo|giuramento|collegio|dominio|via|scuola|guerriero|stregoneria|patrono"
    r"|path|circle|oath|college|domain|way|school|warrior)\s+"
    r"(?:(?:del|dello|della|delle|dei|degli|di|of the|of)\s+|dell')?"
)
_ARTICLE = re.compile(r"^(?:il |lo |la |l'|the )")
_TAIL = re.compile(r"\s+(?:domain|patron|sorcery)$")


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().replace("’", "'")
    t = _LEAD.sub("", " ".join(t.split()), count=1)
    return _TAIL.sub("", _ARTICLE.sub("", t, count=1), count=1)


def match_subclass(text: str | None, class_key: str | None, edition: str) -> str | None:
    """Chiave della sottoclasse il cui nome o alias coincide esattamente (dopo normalizzazione), altrimenti None."""
    if not text or not class_key:
        return None
    wanted = _norm(text)
    for spec in subclasses_for(edition, class_key):
        if wanted in {_norm(n) for n in (*spec.name.values(), *spec.aliases)}:
            return spec.key
    return None


def sync_subclass_keys(char) -> None:
    """Ricalcola `subclass_key` di ogni classe del personaggio dal testo e dall'edizione; il testo non cambia."""
    ed = character_edition(char)
    for c in char.classes:
        c.subclass_key = match_subclass(c.subclass, row_class_key(c), ed)
