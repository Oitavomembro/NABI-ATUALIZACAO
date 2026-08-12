import unittest

from core.notifications import NotificationCenter


class NotificationCenterTests(unittest.TestCase):
    def test_duration_is_clamped(self):
        self.assertEqual(NotificationCenter.normalize_duration(1), 1200)
        self.assertEqual(NotificationCenter.normalize_duration(999999), 15000)

    def test_publish_adds_newest_first(self):
        center = NotificationCenter(max_history=3)
        center.publish("Primeira", "A")
        center.publish("Segunda", "B", level="success")
        history = center.history()
        self.assertEqual([item.title for item in history], ["Segunda", "Primeira"])
        self.assertEqual(history[0].level, "success")

    def test_history_respects_limit(self):
        center = NotificationCenter(max_history=2)
        center.publish("1", "A")
        center.publish("2", "B")
        center.publish("3", "C")
        self.assertEqual([item.title for item in center.history()], ["3", "2"])

    def test_invalid_level_falls_back_to_info(self):
        center = NotificationCenter()
        record = center.publish("Teste", "Mensagem", level="desconhecido")
        self.assertEqual(record.level, "info")

    def test_default_duration_can_be_updated_and_is_clamped(self):
        center = NotificationCenter()
        self.assertEqual(center.set_default_duration(900), 1200)
        self.assertEqual(center.publish("Teste", "Mensagem").duration_ms, 1200)
        self.assertEqual(center.set_default_duration(6000), 6000)

    def test_clear_removes_history(self):
        center = NotificationCenter()
        center.publish("Teste", "Mensagem")
        center.clear()
        self.assertEqual(center.history(), [])

    def test_history_is_deliberately_scoped_to_each_application_session(self):
        first_session = NotificationCenter()
        first_session.publish("Sessão anterior", "Não é um registro operacional persistente")

        restarted_session = NotificationCenter()

        self.assertEqual(restarted_session.history(), [])
        self.assertEqual(len(first_session.history()), 1)


if __name__ == "__main__":
    unittest.main()
