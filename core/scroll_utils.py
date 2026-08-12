class PercentScrollController:
    """Operações matemáticas de rolagem limitadas entre 0% e 100%."""

    @staticmethod
    def clamp(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        return max(0.0, min(1.0, value))

    @classmethod
    def advance(cls, current, delta_percent):
        return cls.clamp(float(current) + (float(delta_percent) / 100.0))

    @staticmethod
    def percent(first):
        return int(round(max(0.0, min(1.0, float(first))) * 100))

    @classmethod
    def viewport_percent(cls, first, last):
        """Converte a posição Tk ``(first, last)`` em percentual real 0..100.

        No Tk, ``first`` não chega a 1 quando existe uma parte visível do
        conteúdo. O limite inferior real é ``1 - (last - first)``.
        """
        first = cls.clamp(first)
        last = cls.clamp(last)
        visible = max(0.0, last - first)
        max_first = max(0.0, 1.0 - visible)
        if max_first <= 0.0:
            return 0
        return int(round(cls.clamp(first / max_first) * 100))

    @classmethod
    def moveto_for_percent(cls, percent, first, last):
        """Retorna o valor de ``moveto`` que representa 0..100% do percurso."""
        first = cls.clamp(first)
        last = cls.clamp(last)
        visible = max(0.0, last - first)
        max_first = max(0.0, 1.0 - visible)
        target = cls.clamp(float(percent) / 100.0)
        return target * max_first

    @staticmethod
    def wheel_direction(delta):
        """Normaliza deltas de roda/touchpad para -1, 0 ou 1."""
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            return 0
        if delta > 0:
            return -1
        if delta < 0:
            return 1
        return 0
