import tempfile
import unittest
from pathlib import Path

from services.release_packaging_service import ReleasePackagingService


class ReleasePackagingServiceTests(unittest.TestCase):
    def test_clean_tree_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "main.py").write_text("print('ok')", encoding="utf-8")
            ReleasePackagingService.validate_tree(root)

    def test_database_and_backup_folder_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "backups_moveis"
            folder.mkdir()
            (folder / "clientes.db").write_bytes(b"SQLite format 3")
            with self.assertRaisesRegex(ValueError, "arquivos sensíveis"):
                ReleasePackagingService.validate_tree(root)

    def test_secret_extensions_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "certificado.pfx").write_bytes(b"secret")
            with self.assertRaisesRegex(ValueError, "certificado.pfx"):
                ReleasePackagingService.validate_tree(root)

    def test_certifi_public_trust_store_is_accepted_but_other_pem_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            certifi = root / "_internal" / "certifi"
            certifi.mkdir(parents=True)
            (certifi / "cacert.pem").write_text("PUBLIC CA BUNDLE", encoding="ascii")
            ReleasePackagingService.validate_tree(root)
            (certifi / "private.pem").write_text("PRIVATE KEY", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "private.pem"):
                ReleasePackagingService.validate_tree(root)


if __name__ == "__main__":
    unittest.main()
