from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit

from commercial.domain.money import MoneyCodec, MoneyValueError


class MoneyEdit(QLineEdit):
    """Editor monetário Qt com valor Decimal separado da apresentação."""

    valueChanged = Signal(Decimal)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._value = MoneyCodec.ZERO
        self._integer_digits = ""
        self._fraction_digits = ""
        self._fraction_mode = False
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setText(MoneyCodec.format_br(self._value))
        self.setAccessibleName("Valor monetário")

    def value(self) -> Decimal:
        return self._value

    def set_value(self, value: Decimal | int | str) -> None:
        parsed = MoneyCodec.parse(value)
        canonical = MoneyCodec.canonical(parsed)
        integer, fraction = canonical.split(".")
        self._integer_digits = integer.lstrip("0") or "0"
        self._fraction_digits = fraction
        self._fraction_mode = False
        self._apply(parsed)

    def clear_value(self) -> None:
        self._integer_digits = ""
        self._fraction_digits = ""
        self._fraction_mode = False
        self._apply(MoneyCodec.ZERO)

    def _apply(self, value: Decimal) -> None:
        self._value = MoneyCodec.parse(value)
        self.setText(MoneyCodec.format_br(self._value))
        self.setCursorPosition(len(self.text()))
        self.valueChanged.emit(self._value)

    def _commit_buffer(self) -> None:
        integer = self._integer_digits or "0"
        fraction = (self._fraction_digits + "00")[:2]
        self._apply(Decimal(f"{integer}.{fraction}"))

    def _replace_selection_if_needed(self) -> None:
        if self.hasSelectedText():
            self._integer_digits = ""
            self._fraction_digits = ""
            self._fraction_mode = False

    def _paste(self) -> None:
        text = QApplication.clipboard().text().strip()
        try:
            self.set_value(MoneyCodec.parse(text))
        except MoneyValueError:
            QApplication.beep()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.SelectAll):
            super().keyPressEvent(event)
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            super().keyPressEvent(event)
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self._replace_selection_if_needed()
            self._paste()
            return

        text = event.text()
        if text and text.isdecimal() and text.isascii():
            self._replace_selection_if_needed()
            if self._fraction_mode:
                if len(self._fraction_digits) < 2:
                    self._fraction_digits += text
            else:
                self._integer_digits = (self._integer_digits.lstrip("0") + text) or "0"
            self._commit_buffer()
            return
        if text in {",", "."}:
            self._replace_selection_if_needed()
            self._fraction_mode = True
            self._fraction_digits = ""
            self._commit_buffer()
            return
        if event.key() == Qt.Key.Key_Backspace:
            self._replace_selection_if_needed()
            if self._fraction_mode and self._fraction_digits:
                self._fraction_digits = self._fraction_digits[:-1]
            elif self._fraction_mode:
                self._fraction_mode = False
            else:
                self._integer_digits = self._integer_digits[:-1]
            self._commit_buffer()
            return
        if event.key() == Qt.Key.Key_Delete:
            self.clear_value()
            return
        if event.key() in {
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End,
            Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Return, Qt.Key.Key_Enter,
        }:
            super().keyPressEvent(event)
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            super().keyPressEvent(event)
            return
        QApplication.beep()
