from typing import Any

from . import *
from .models import Currency


def verify_selected_map_callback_data(callback_data: Any) -> bool:
    return True if isinstance(callback_data, tuple) else False


def verify_selected_currency_callback_data(callback_data: Any) -> bool:
    """
    Verifies if the provided callback data is a tuple with two elements, where:
    - The first element is a string (currency type).
    - The second element is an instance of the Currency class.

    :param callback_data: The data to verify, expected to be a tuple (str, Currency).
    :return: True if the callback data is valid, otherwise False.
    """
    if not isinstance(callback_data, tuple) or len(callback_data) != 2:
        return False

    if not isinstance(callback_data[0], str) or not isinstance(callback_data[1], Currency):
        return False

    return True


def verify_character_currency_converter_callback_data(callback_data: Any) -> bool:
    if not isinstance(callback_data, tuple) or len(callback_data) > 3:
        return False

    action = callback_data[0]
    if action != SELECT_TARGET_CALLBACK_DATA and action != SELECT_SOURCE_CALLBACK_DATA and action != CONVERT_CURRENCY_CALLBACK_DATA:
        return False

    return True
