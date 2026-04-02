from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class Currency:
    gold: int = 0
    silver: int = 0
    bronze: int = 0
    electrum: int = 0
    platinum: int = 0

    _currency_fields = {
        'gold': 'gold',
        'silver': 'silver',
        'bronze': 'bronze',
        'electrum': 'electrum',
        'platinum': 'platinum'
    }

    _currency_emojis = {
        'gold': '🥇',
        'silver': '🥈',
        'bronze': '🥉',
        'electrum': '⚡',
        'platinum': '💎'
    }

    _currency_human_names = {
        'gold': 'oro',
        'silver': 'argento',
        'bronze': 'bronzo',
        'electrum': 'electrum',
        'platinum': 'platino'
    }

    _currency_to_cp = {
        'bronze': 1,
        'silver': 10,
        'electrum': 50,
        'gold': 100,
        'platinum': 1000
    }

    @property
    def currencies(self) -> Dict[str, Tuple[str, int]]:
        return {
            'gold': ('Oro', self.gold),
            'silver': ('Argento', self.silver),
            'bronze': ('Bronzo', self.bronze),
            'electrum': ('Electrum', self.electrum),
            'platinum': ('Platino', self.platinum)
        }

    @property
    def currency_human_names(self) -> Dict[str, str]:
        return self._currency_human_names

    @property
    def currency_to_cp(self) -> Dict[str, int]:
        return self._currency_to_cp

    def get_currency_value(self, currency_id: str) -> int:
        """
        Restituisce il valore della valuta corrispondente all'ID dato.
        :param currency_id: ID della valuta, ad esempio 'gold', 'silver', ecc.
        :return: Valore attuale della valuta.
        """
        attribute = self._currency_fields.get(currency_id)
        if attribute:
            return getattr(self, attribute)

    def set_currency_value(self, currency_id: str, value: int):
        """
        Imposta il valore della valuta corrispondente all'ID dato.
        :param currency_id: ID della valuta, ad esempio 'gold', 'silver', ecc.
        :param value: Nuovo valore da impostare per la valuta.
        """
        attribute = self._currency_fields.get(currency_id)
        if attribute:
            setattr(self, attribute, value)

    def get_currency_emoji(self, currency_id: str) -> str:
        """
        Restituisce l'emoji associata all'ID della valuta.
        :param currency_id: ID della valuta, ad esempio 'gold', 'silver', ecc.
        :return: Emoji della valuta.
        """
        emoji = self._currency_emojis.get(currency_id)
        if emoji:
            return emoji

    def get_currency_human_name(self, currency_id: str) -> str:
        """
        Restituisce il nome reale della valuta associata all'ID della valuta.
        :param currency_id: ID della valuta, ad esempio 'gold', 'silver', ecc.
        :return: Emoji della valuta.
        """
        human_name = self._currency_human_names.get(currency_id)
        if human_name:
            return human_name
