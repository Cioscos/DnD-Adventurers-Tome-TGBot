"""Pydantic schemas for game sessions (invite-code based webapp feature)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from api.schemas.condition_effects import ConditionEffectRead, PendingSaveRead
from api.schemas.encounter import EncounterLive, PublicState
from api.schemas.item import ItemCreate
from core.game.actions import HIDE_MIN_TOTAL


class SessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    campaign_id: Optional[int] = None


class SessionJoinRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    character_id: int


class SessionMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    recipient_user_id: Optional[int] = None


class SessionMessageRead(BaseModel):
    id: int
    user_id: int
    role: str
    body: str
    sent_at: str
    recipient_user_id: Optional[int] = None
    sender_display_name: Optional[str] = None

    model_config = {"from_attributes": True}


class CharacterLiveSnapshot(BaseModel):
    """Lightweight character state shown in the live session view.

    Raw HP/AC/death_saves fields are nullable: they are populated for the GM
    and for the character's owner, but redacted to None for other players.
    hp_bucket / armor_category are always populated and carry the redacted
    summary.
    """

    id: int
    name: str
    race: Optional[str] = None
    class_summary: str = ""
    total_level: int = 0
    hit_points: Optional[int] = None
    current_hit_points: Optional[int] = None
    temp_hp: Optional[int] = None
    ac: Optional[int] = None
    conditions: Optional[dict[str, Any]] = None
    death_saves: Optional[dict[str, Any]] = None
    heroic_inspiration: bool = False
    last_roll: Optional[dict[str, Any]] = None
    hp_bucket: Optional[str] = None
    armor_category: Optional[str] = None
    condition_effects: list[ConditionEffectRead] = []
    has_pending_save: bool = False
    is_concentrating: bool = False
    # Stati con effetti su altri (Lupo, Orso, Attacco Irruento): li vedono tutti i partecipanti (R36)
    active_states: list[PublicState] = []


class SessionParticipantRead(BaseModel):
    user_id: int
    role: str
    character_id: Optional[int] = None
    display_name: Optional[str] = None
    character_name: Optional[str] = None
    joined_at: str

    model_config = {"from_attributes": True}


class GameSessionRead(BaseModel):
    id: int
    code: str
    gm_user_id: int
    gm_display_name: Optional[str] = None
    status: str
    title: Optional[str] = None
    created_at: str
    last_activity_at: str
    closed_at: Optional[str] = None
    participants: list[SessionParticipantRead] = []
    campaign_id: Optional[int] = None
    campaign_name: Optional[str] = None
    # Popolato solo da GET /sessions/me: stato dell'incontro non terminato, se esiste.
    encounter_status: Optional[Literal["setup", "active"]] = None

    model_config = {"from_attributes": True}


class GameSessionLiveRead(GameSessionRead):
    live_characters: list[CharacterLiveSnapshot] = []
    encounter: Optional[EncounterLive] = None


class IdentityView(BaseModel):
    """Public + optionally private identity fields for a session participant.

    Private fields (background, personality_traits, ideals, bonds, flaws)
    are populated only when the target has enabled `show_private_identity`
    or when the caller is the target themselves.
    """

    user_id: int
    character_id: int
    # public (always populated)
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    alignment: Optional[str] = None
    speed: Optional[int] = None
    languages: Optional[str] = None  # comma-joined for display
    general_proficiencies: Optional[str] = None  # comma-joined for display
    # private (null if target has show_private_identity = False)
    background: Optional[str] = None
    personality_traits: Optional[str] = None
    ideals: Optional[str] = None
    bonds: Optional[str] = None
    flaws: Optional[str] = None
    show_private: bool = False


class SessionFeedItem(BaseModel):
    """Single item in the mixed chat+history feed."""

    type: Literal["message", "event"]
    timestamp: str

    # message-only
    message_id: Optional[int] = None
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    body: Optional[str] = None
    recipient_user_id: Optional[int] = None

    # message-only — GM grant payload
    item_id: Optional[int] = None
    item_name: Optional[str] = None
    item_quantity: Optional[int] = None

    # message-only — PG-to-PG trade snapshot
    trade: Optional[dict] = None

    # event-only
    event_id: Optional[int] = None
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    owner_user_id: Optional[int] = None
    event_type: Optional[str] = None
    description: Optional[str] = None
    op: Optional[str] = None


class SessionFeedResponse(BaseModel):
    items: list[SessionFeedItem]
    has_more: bool = False


class GMGrantItemRequest(BaseModel):
    """GM action: grant an item to one or more session players."""

    recipient_user_ids: list[int] = Field(min_length=1)
    item: ItemCreate


class TradeRequest(BaseModel):
    """Player action: give an item (or loose coins) to another PG in the session."""

    from_character_id: int
    to_user_id: int
    item_id: Optional[int] = None
    quantity: Optional[int] = None
    coins: Optional[dict[str, int]] = None


class InspirationGiveRequest(BaseModel):
    """2024: chi ha già l'Ispirazione Eroica la cede a un personaggio del gruppo che ne è privo."""

    from_character_id: int
    to_user_id: int


class StashPutRequest(BaseModel):
    from_character_id: int
    item_id: Optional[int] = None
    quantity: Optional[int] = None
    coins: Optional[dict[str, int]] = None


class StashTakeRequest(BaseModel):
    to_character_id: int
    item_id: Optional[int] = None
    quantity: Optional[int] = None
    coins: Optional[dict[str, int]] = None


class StashGMAddRequest(BaseModel):
    item: Optional[ItemCreate] = None
    coins: Optional[dict[str, int]] = None


class StashGMRemoveRequest(BaseModel):
    item_id: Optional[int] = None
    quantity: Optional[int] = None
    coins: Optional[dict[str, int]] = None


class GMGrantItemResult(BaseModel):
    user_id: int
    character_id: Optional[int] = None
    item_id: Optional[int] = None
    status: str  # "ok" | "not_a_player" | "no_character" | "character_not_found"


class GMGrantItemResponse(BaseModel):
    results: list[GMGrantItemResult]


class StartHealNotice(BaseModel):
    """Cura ricevuta all'inizio del turno da un privilegio (Sopravvissuto): quanto e perché."""
    feature_key: str
    name: dict[str, str]
    amount: int
    message: Optional[dict[str, str]] = None  # un avviso che non è una cura (Guerriero Eroico): sostituisce il testo di default


class TurnBlock(BaseModel):
    action_used: bool = False
    bonus_used: bool = False
    reaction_used: bool = False
    attacks_made: int = 0
    action_attacks: int = 0  # solo quelli dell'azione Attacco: gli attacchi con slot proprio non contano
    extra_actions: int = 0
    once_per_turn: list[str] = []
    spell_slot_cast: bool = False
    bonus_spell_cast: bool = False
    free_interaction_used: bool = False
    damaged: bool = False
    start_heal: list[StartHealNotice] = []  # le cure d'inizio turno di questo turno (avviso al giocatore)
    action_spell_level: Optional[int] = None  # livello dell'ultimo incantesimo lanciato con l'azione in questo turno (0: trucchetto)
    pending_attack: Optional[dict] = None
    beast: Optional[dict] = None  # gli ordini alla bestia del Signore delle Bestie in questo turno (attacchi che le restano)
    last_roll: Optional[dict] = None  # la domanda «Riuscito?» resta finché ``refundable`` non è vuoto


class TurnState(BaseModel):
    turn: TurnBlock = TurnBlock()
    attacks_allowed: int = 1
    attacks_allowed_pact: int = 1  # il limite con l'arma del patto (Lama Assetata)
    hide_min_total: int = HIDE_MIN_TOTAL  # Nascondersi 2024: il totale di Furtività che basta
    in_encounter: bool
    is_my_turn: bool
    round: Optional[int] = None
    session_id: Optional[int] = None
    pending_saves: list[PendingSaveRead] = []
    effects_sig: str = ""  # firma di stati attivi, condizioni, PF (attuali, massimi, temporanei) e usi delle abilità (CA ne deriva): se cambia (effetto di un alleato) la scheda va riletta
