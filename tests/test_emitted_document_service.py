import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from services.emitted_document_service import EmittedDocumentService


class EmittedDocumentServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE documentos_emitidos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movimentacao_id INTEGER NOT NULL,
                categoria TEXT NOT NULL,
                caminho_pdf TEXT NOT NULL,
                numero_documento TEXT,
                data_emissao TEXT
            )
            """
        )
        conn.commit()
        conn.close()
        self.connections = []

        def factory():
            conn = sqlite3.connect(self.db_path)
            self.connections.append(conn)
            return conn

        self.service = EmittedDocumentService(
            factory,
            clock=lambda: datetime(2026, 8, 2, 20, 30, 0),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_register_and_latest(self):
        pdf = Path(self.temp_dir.name) / "document.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        document_id = self.service.register(7, "recibo", pdf, "R-7")
        latest = self.service.latest(7)
        self.assertEqual(document_id, latest.id)
        self.assertEqual("RECIBO", latest.category)
        self.assertEqual(str(pdf.resolve()), latest.pdf_path)
        self.assertEqual("R-7", latest.document_number)
        self.assertEqual("02/08/2026 20:30:00", latest.issued_at)

    def test_latest_existing_file_ignores_missing_file(self):
        missing = Path(self.temp_dir.name) / "missing.pdf"
        self.service.register(8, "movimento", missing)
        self.assertIsNone(self.service.latest_existing_file(8))

    def test_register_rolls_back_and_closes_on_error(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP TABLE documentos_emitidos")
        conn.commit()
        conn.close()
        with self.assertRaises(sqlite3.OperationalError):
            self.service.register(9, "movimento", Path(self.temp_dir.name) / "x.pdf")
        with self.assertRaises(sqlite3.ProgrammingError):
            self.connections[-1].execute("SELECT 1")

    def test_invalid_movement_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.latest(0)


if __name__ == "__main__":
    unittest.main()
