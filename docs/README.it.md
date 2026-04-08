# D&D 5e Telegram Bot (Wiki + Personaggi + Party)

Bot Telegram async per D&D 5e con tre macro-aree integrate:

1. Wiki D&D 5e via GraphQL (navigazione profonda dinamica)
2. Gestione personaggio completa con persistenza SQLite
3. Sessione Party di gruppo con aggiornamento live

## Panoramica funzionalita'

### 1) Wiki D&D 5e

- Endpoint GraphQL: `https://www.dnd5eapi.co/graphql/2014`
- Introspezione schema automatica all'avvio (tipi, root query, campi navigabili)
- 11 categorie: Spells, Monsters, Classes, Races, Equipment, Conditions, Magic Items, Feats, Rules, Backgrounds, Weapon Properties
- Navigazione N-livelli: categorie -> lista paginata -> dettaglio -> sotto-entita' navigabili
- Query GraphQL generate dinamicamente (nessuna query hardcoded)
- Supporto union types con `__typename` + inline fragments
- Gestione errori parziali: quando possibile mostra i dati disponibili anche con errori GraphQL

### 2) Gestione personaggio

- Creazione/selezione/cancellazione personaggi
- HP (max/correnti, danni, cure, riposo), AC (base/scudo/magia)
- Punteggi abilita' + modificatori
- Skill complete (18) con competenza e tiro `d20` + bonus
- Incantesimi: apprendimento, modifica campi, uso slot, concentrazione, ricerca fuzzy
- Slot incantesimo, inventario tipizzato, equip/unequip con sync AC
- Valute, abilita' speciali, mappe, note testuali e vocali
- Multiclasse con risorse di classe auto-generate e gestione livelli
- Condizioni D&D 5e (14 binarie + Exhaustion 0-6)
- Ispirazione eroica (toggle ottieni/usa)
- Storico modifiche personaggio (max 50 eventi)
- Persistenza stato conversazione e callback tramite `PicklePersistence`

### 3) Party di gruppo

- Comandi gruppo: `/party` e `/party_stop`
- Modalita' visualizzazione: pubblica nel gruppo o privata al master
- Messaggio party aggiornato in tempo reale su HP/AC/condizioni/tiri
- Countdown sessione (48 ore)
- Include HP bar, AC, condizioni attive e ultimo tiro per personaggio

## Comandi e scope chat

| Comando | Scope | Note |
|---|---|---|
| `/start` | Solo chat privata | Mostra menu principale con `Wiki D&D` e `Il mio personaggio`; in gruppo mostra avviso e termina |
| `/party` | Solo gruppi/supergruppi | Avvia selezione modalita' party |
| `/party_stop` | Solo gruppi/supergruppi | Termina sessione party attiva |
| `/stop` | Privata (fallback globale/conversation) | Annulla flusso in corso e pulisce i `*_pending` |

## Stack tecnico

- Python 3.10+
- `python-telegram-bot[callback-data] >= 22.0`
- `httpx >= 0.27.0`
- `sqlalchemy >= 2.0` + `aiosqlite >= 0.20`
- `python-dotenv >= 1.0.0`
- `rapidfuzz >= 3.0`
- `pyyaml >= 6.0`

## Installazione

### Windows (PowerShell)

```powershell
git clone https://github.com/Cioscos/dnd_bot_revamped.git
Set-Location dnd_bot_revamped
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configurazione

Crea un file `.env` nella root del progetto:

```env
BOT_TOKEN=your_bot_token_here
DEV_CHAT_ID=optional_telegram_chat_id
DB_PATH=data/dnd_bot.db
```

| Variabile | Obbligatoria | Descrizione |
|---|---|---|
| `BOT_TOKEN` | Si | Token bot Telegram |
| `DEV_CHAT_ID` | No | Chat ID developer per traceback errori non gestiti |
| `DB_PATH` | No | Path DB SQLite (default: `data/dnd_bot.db`) |

## Avvio

```powershell
python -m bot.main
```

## Architettura (sintesi)

```text
bot/
|- main.py                 # bootstrap app, persistence, handler registration, error handler
|- api/                    # client GraphQL, introspection, query builder dinamico
|- schema/                 # registry schema e campi navigabili
|- handlers/
|  |- start.py             # /start (private only)
|  |- navigation.py        # wiki callbacks
|  |- party.py             # /party, /party_stop, update live
|  '- character/           # conversation e feature personaggio
|- db/                     # engine async, modelli ORM, history helper
|- keyboards/              # tastiere inline wiki/personaggio/party
|- locales/                # i18n YAML (it/en)
'- utils/                  # formatter MarkdownV2, i18n, party formatting
```

## i18n e formattazione

- Lingua utente rilevata da `update.effective_user.language_code`
- Locali supportate: `it` (default) e `en`
- Stringhe utente in `bot/locales/it.yaml` e `bot/locales/en.yaml`
- Output messaggi in MarkdownV2 con escaping dedicato

## Persistenza

- Database personaggi: SQLite (`data/dnd_bot.db` di default)
- Stato bot: `data/persistence.pkl` (`user_data`, callback cache, stato conversation)
- Le callback dataclass (`NavAction`, `CharAction`, `PartyAction`) restano valide anche dopo riavvio

## Note operative

- Il bot usa solo inline keyboard per la navigazione
- Le sessioni DB sono gestite con context manager async
- Errori non gestiti: logging locale + inoltro traceback a `DEV_CHAT_ID` se configurato

## License

Progetto per uso educativo/personale. I contenuti D&D arrivano da [D&D 5e API](https://www.dnd5eapi.co/) sotto SRD.

