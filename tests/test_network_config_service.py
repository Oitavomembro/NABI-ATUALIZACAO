import json
import tempfile
import unittest
from pathlib import Path
from services.network_config_service import NetworkConfigService, NetworkPaths


class NetworkConfigServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.paths = NetworkPaths(
            app_dir=root,
            config_file=root / "rede_local.json",
            installation_file=root / "instalacao.json",
            local_db=root / "local.db",
            server_dir=root / "server",
            server_db=root / "server" / "shared.db",
        )
        self.service = NetworkConfigService(self.paths)

    def tearDown(self):
        self.temp.cleanup()

    def test_invalid_json_falls_back_without_hiding_warning(self):
        self.paths.config_file.write_text("{inválido", encoding="utf-8")
        config = self.service.load()
        self.assertEqual(config["modo"], "local")
        self.assertTrue(self.service.last_warning)

    def test_save_and_load_are_consistent(self):
        self.service.save("rede", self.paths.server_db, "servidor")
        config = self.service.load()
        self.assertEqual(config["modo"], "rede")
        self.assertEqual(config["papel"], "servidor")
        self.assertEqual(config["db_path"], str(self.paths.server_db.resolve()))

    def test_prepare_server_marks_installation_and_checks_write(self):
        target = self.service.prepare_server()
        self.assertEqual(target, str(self.paths.server_db.resolve()))
        installation = json.loads(self.paths.installation_file.read_text(encoding="utf-8"))
        self.assertEqual(installation["papel"], "servidor")

    def test_client_paths_normalize_slashes(self):
        server, share, database = self.service.client_paths(r"\\SERVIDOR/")
        self.assertEqual(server, "SERVIDOR")
        self.assertEqual(share, r"\\SERVIDOR\BancoCompartilhado")
        self.assertTrue(database.endswith(r"\fichario_moveis_compartilhado.db"))

    def test_empty_server_is_rejected_before_network_access(self):
        with self.assertRaises(ValueError):
            self.service.test_client("")


if __name__ == "__main__":
    unittest.main()
