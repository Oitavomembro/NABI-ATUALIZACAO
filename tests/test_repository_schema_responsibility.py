import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from repositories import ProdutoRepository


class RepositorySchemaResponsibilityTests(unittest.TestCase):
    def test_product_repository_constructor_does_not_alter_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "minimal.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE produtos(id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT)")
            conn.commit(); conn.close()
            db = DatabaseManager(path)
            before = [row["name"] for row in db.fetch_all("PRAGMA table_info(produtos)")]
            ProdutoRepository(db)
            after = [row["name"] for row in db.fetch_all("PRAGMA table_info(produtos)")]
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
