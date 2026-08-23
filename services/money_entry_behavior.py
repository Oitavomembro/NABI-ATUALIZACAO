from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any

from ui.keyboard_navigation import bind_key_once


class MoneyEntryBehavior:
    """Mantém valor monetário canônico separado do texto brasileiro do campo."""

    MONEY = Decimal("0.01")
    _VALUE_ATTR = "_nabicode_money_value"

    @classmethod
    def parse(cls, value: Any) -> Decimal:
        text = str(value or "").strip().replace("R$", "").replace(" ", "")
        if not text:
            return Decimal("0.00")
        if not re.fullmatch(r"-?[0-9.,]+", text):
            raise ValueError("Preço inválido.")

        if "," in text:
            normalized = text.replace(".", "").replace(",", ".")
        elif "." in text:
            unsigned = text.lstrip("-")
            groups = unsigned.split(".")
            if len(groups) > 1 and 1 <= len(groups[0]) <= 3 and all(
                len(group) == 3 for group in groups[1:]
            ):
                normalized = text.replace(".", "")
            elif text.count(".") == 1:
                normalized = text
            else:
                raise ValueError("Preço inválido.")
        else:
            normalized = text

        try:
            result = Decimal(normalized).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Preço inválido.") from exc
        if not result.is_finite():
            raise ValueError("Preço inválido.")
        return result

    @classmethod
    def format(cls, value: Any) -> str:
        amount = cls.parse(value) if not isinstance(value, Decimal) else value.quantize(
            cls.MONEY, rounding=ROUND_HALF_UP
        )
        international = f"{amount:,.2f}"
        return international.translate(str.maketrans({",": ".", ".": ","}))

    @staticmethod
    def _position_after_digits(text: str, digit_count: int, *, stop: int) -> int:
        if digit_count <= 0:
            return 0
        seen = 0
        for index, char in enumerate(text[:stop]):
            if char.isdigit():
                seen += 1
                if seen == digit_count:
                    return index + 1
        return stop

    @classmethod
    def _cursor_after_format(cls, raw: str, raw_cursor: int, formatted: str) -> int:
        formatted_comma = formatted.rfind(",")
        raw_comma = raw.rfind(",")
        if raw_comma >= 0 and raw_cursor > raw_comma:
            decimal_digits = sum(char.isdigit() for char in raw[raw_comma + 1:raw_cursor])
            return min(len(formatted), formatted_comma + 1 + min(decimal_digits, 2))
        integer_digits = sum(char.isdigit() for char in raw[:raw_cursor])
        return cls._position_after_digits(
            formatted, integer_digits, stop=formatted_comma
        )

    @classmethod
    def format_after_edit(cls, entry: Any, _event: Any = None) -> None:
        raw = str(entry.get() or "")
        if not raw.strip():
            setattr(entry, cls._VALUE_ATTR, Decimal("0.00"))
            return
        try:
            raw_cursor = int(entry.index("insert"))
        except (AttributeError, TypeError, ValueError):
            raw_cursor = len(raw)
        amount = cls.parse(raw)
        formatted = cls.format(amount)
        cursor = cls._cursor_after_format(raw, raw_cursor, formatted)
        if raw != formatted:
            entry.delete(0, "end")
            entry.insert(0, formatted)
        try:
            entry.icursor(cursor)
        except (AttributeError, TypeError):
            pass
        setattr(entry, cls._VALUE_ATTR, amount)

    @classmethod
    def attach(cls, entry: Any) -> None:
        bind_key_once(
            entry,
            "<KeyRelease>",
            lambda event, target=entry: cls.format_after_edit(target, event),
            owner="money-entry:format",
        )
        setattr(entry, cls._VALUE_ATTR, cls.parse(entry.get()))

    @classmethod
    def set_value(cls, entry: Any, value: Any) -> None:
        amount = cls.parse(value)
        entry.delete(0, "end")
        entry.insert(0, cls.format(amount))
        setattr(entry, cls._VALUE_ATTR, amount)

    @classmethod
    def clear(cls, entry: Any) -> None:
        entry.delete(0, "end")
        setattr(entry, cls._VALUE_ATTR, Decimal("0.00"))

    @classmethod
    def value(cls, entry: Any) -> Decimal:
        amount = cls.parse(entry.get())
        setattr(entry, cls._VALUE_ATTR, amount)
        return amount
