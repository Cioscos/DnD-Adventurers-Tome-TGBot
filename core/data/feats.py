"""Talenti (feats) selezionabili al level-up: nome e riassunto meccanico breve scritti da noi.

Gli effetti stanno nel motore delle regole (``core/rules/catalog/feats.py``); qui restano scelta e prerequisiti."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ALL_ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


@dataclass(frozen=True)
class FeatSpec:
    key: str
    name: dict[str, str]
    summary: dict[str, str]
    # target e' lo slug del DSL senza prefisso "character." (es. "initiative").
    passive_modifiers: list[dict] = field(default_factory=list)
    ability_increase: Optional[list[str]] = None
    save_proficiency_from_increase: bool = False
    counter: Optional[dict] = None
    setting: Optional[str] = None
    # Talenti 2024 e Doni Epici (D3, core/data/feats_2024.py): solo scelta, prerequisiti e testo.
    edition: str = "2014"
    category: str = "general"  # general | epic_boon | origin | fighting_style
    min_level: int = 0  # livello totale del personaggio
    prereq_abilities: Optional[tuple[tuple[str, ...], int]] = None  # (una fra queste, minimo)
    needs_spellcasting: bool = False
    max_score: int = 20
    repeatable: bool = False  # si prende più volte (Abile, Iniziato alla magia): ogni riga è un'istanza
    prereq_armor: Optional[str] = None  # addestramento richiesto: light | medium | heavy | shields
    needs_fighting_style: bool = False  # Stile di Combattimento come talento: serve il privilegio Stile di Combattimento


def _f(key, it, en, sit, sen, **kw) -> FeatSpec:
    return FeatSpec(key=key, name={"it": it, "en": en}, summary={"it": sit, "en": sen}, **kw)


FEATS: dict[str, FeatSpec] = {f.key: f for f in [
    _f("grappler", "Lottatore", "Grappler",
       "Vantaggio ai tiri per colpire le creature che stai lottando; puoi tentare di immobilizzarle.",
       "Advantage on attacks against creatures you are grappling; you can try to pin them."),
    _f("alert", "Allerta", "Alert",
       "+5 all'iniziativa; non puoi essere sorpreso se sei cosciente.",
       "+5 to initiative; you cannot be surprised while conscious."),
    _f("tough", "Robusto", "Tough",
       "+2 punti ferita massimi per ogni livello.",
       "+2 maximum hit points per level."),
    _f("mobile", "Mobile", "Mobile",
       "+3 metri (+10 piedi) di velocita'; lo scatto non provoca attacchi di opportunita'.",
       "+10 feet speed; Dash does not provoke opportunity attacks."),
    _f("observant", "Osservatore", "Observant",
       "+1 Intelligenza o Saggezza; +5 a Percezione e Indagare passive.",
       "+1 Intelligence or Wisdom; +5 to passive Perception and Investigation.",
       ability_increase=["intelligence", "wisdom"]),
    _f("resilient", "Resiliente", "Resilient",
       "+1 a una caratteristica a scelta e competenza nei suoi tiri salvezza.",
       "+1 to one ability of your choice and proficiency in its saving throws.",
       ability_increase=list(ALL_ABILITIES), save_proficiency_from_increase=True),
    _f("war_caster", "Incantatore Bellico", "War Caster",
       "Vantaggio ai tiri salvezza su Costituzione per mantenere la concentrazione.",
       "Advantage on Constitution saves to maintain concentration."),
    _f("lucky", "Fortunato", "Lucky",
       "3 punti fortuna per riposo lungo per ritirare un d20.",
       "3 luck points per long rest to reroll a d20."),
]}
