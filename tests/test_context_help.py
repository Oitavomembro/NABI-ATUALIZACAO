import unittest

from core.context_help import ContextHelpRegistry, HelpShortcut, HelpTopic


class ContextHelpRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ContextHelpRegistry()

    def test_alias_pdv_resolves_vendas(self):
        self.assertEqual(self.registry.get("pdv").context, "vendas")

    def test_unknown_context_falls_back_to_global(self):
        self.assertEqual(self.registry.get("nao_existe").context, "global")

    def test_xml_topic_contains_import_guidance(self):
        topic = self.registry.get("xml")
        self.assertEqual(topic.context, "xml_import")
        self.assertTrue(any("Concluir importação" in item.action for item in topic.shortcuts))

    def test_register_custom_topic(self):
        custom = HelpTopic(
            context="teste",
            title="Teste",
            description="Descrição",
            shortcuts=(HelpShortcut("F2", "Executar"),),
        )
        self.registry.register(custom)
        self.assertEqual(self.registry.get("teste"), custom)

    def test_context_list_is_sorted(self):
        contexts = self.registry.contexts()
        self.assertEqual(contexts, tuple(sorted(contexts)))

    def test_empty_context_is_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register(HelpTopic("", "Inválido", "", ()))


if __name__ == "__main__":
    unittest.main()
