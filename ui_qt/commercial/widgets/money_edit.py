from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QTimer, Qt, Signal
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
        self._value = MoneyCodec.ZERO
        # Durante a edição, vazio precisa ser realmente vazio. Reformatar como
        # 0,00 no mesmo instante fazia Backspace/Delete parecerem inoperantes e
        # mantinha centavos antigos invisivelmente no buffer.
        self.clear()
        self.valueChanged.emit(self._value)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        # Campos monetários chegam normalmente preenchidos com uma sugestão.
        # Selecionar tudo permite que a primeira digitação substitua o valor,
        # em vez de inserir algarismos no meio da máscara formatada.
        QTimer.singleShot(0, self.selectAll)

    def _apply(self, value: Decimal, *, integer_cursor: int | None = None) -> None:
        self._value = MoneyCodec.parse(value)
        self.setText(MoneyCodec.format_br(self._value))
        if integer_cursor is None:
            self.setCursorPosition(len(self.text()))
        else:
            self.setCursorPosition(self._display_position_for_integer_index(integer_cursor))
        self.valueChanged.emit(self._value)

    def _commit_buffer(self, *, integer_cursor: int | None = None) -> None:
        integer = self._integer_digits or "0"
        fraction = (self._fraction_digits + "00")[:2]
        self._apply(Decimal(f"{integer}.{fraction}"), integer_cursor=integer_cursor)

    def _integer_index_at_display_position(self, position: int) -> int:
        integer_text = self.text().partition(",")[0]
        boundary = min(max(0, int(position)), len(integer_text))
        return sum(character.isdecimal() for character in integer_text[:boundary])

    def _display_position_for_integer_index(self, index: int) -> int:
        integer_text = self.text().partition(",")[0]
        wanted = max(0, min(int(index), len(self._integer_digits or "0")))
        if wanted == 0:
            return 0
        seen = 0
        for position, character in enumerate(integer_text):
            if character.isdecimal():
                seen += 1
                if seen == wanted:
                    return position + 1
        return len(integer_text)

    def _delete_selection(self) -> int | None:
        if not self.hasSelectedText():
            return None
        start = self.selectionStart()
        end = start + len(self.selectedText())
        if start == 0 and end == len(self.text()):
            self.clear_value()
            return 0

        integer_text = self.text().partition(",")[0]
        selected_indices = [
            index
            for index, position in enumerate(
                pos for pos, character in enumerate(integer_text) if character.isdecimal()
            )
            if start <= position < end
        ]
        if selected_indices:
            first = selected_indices[0]
            selected = set(selected_indices)
            self._integer_digits = "".join(
                digit for index, digit in enumerate(self._integer_digits) if index not in selected
            )
            self._commit_buffer(integer_cursor=first)
            return first
        return self._integer_index_at_display_position(start)

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
            event.accept()
            return

        text = event.text()
        if text and text.isdecimal() and text.isascii():
            selected = self.hasSelectedText()
            selection_start = self.selectionStart() if selected else self.cursorPosition()
            selection_index = self._delete_selection() if selected else None
            if self._fraction_mode:
                if len(self._fraction_digits) < 2:
                    self._fraction_digits += text
                self._commit_buffer()
            else:
                if selected:
                    index = selection_index or 0
                else:
                    index = self._integer_index_at_display_position(selection_start)
                    if selection_start >= len(self.text().partition(",")[0]):
                        index = len(self._integer_digits)
                digits = self._integer_digits.lstrip("0")
                index = min(index, len(digits))
                self._integer_digits = (digits[:index] + text + digits[index:]) or "0"
                self._commit_buffer(integer_cursor=None if selection_start >= len(self.text().partition(",")[0]) else index + 1)
            event.accept()
            return
        if text in {",", "."}:
            self._replace_selection_if_needed()
            self._fraction_mode = True
            self._fraction_digits = ""
            self._commit_buffer()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Backspace:
            if self.hasSelectedText():
                self._delete_selection()
                event.accept()
                return
            if self._fraction_mode and self._fraction_digits:
                self._fraction_digits = self._fraction_digits[:-1]
                self._commit_buffer()
            elif self._fraction_mode:
                self._fraction_mode = False
                self._commit_buffer()
            else:
                at_end = self.cursorPosition() >= len(self.text().partition(",")[0])
                index = self._integer_index_at_display_position(self.cursorPosition())
                if index > 0:
                    self._integer_digits = self._integer_digits[:index - 1] + self._integer_digits[index:]
                self._commit_buffer(integer_cursor=None if at_end else max(0, index - 1))
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete:
            if self.hasSelectedText():
                self._delete_selection()
                event.accept()
                return
            index = self._integer_index_at_display_position(self.cursorPosition())
            if index < len(self._integer_digits):
                self._integer_digits = self._integer_digits[:index] + self._integer_digits[index + 1:]
                self._commit_buffer(integer_cursor=index)
            event.accept()
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
