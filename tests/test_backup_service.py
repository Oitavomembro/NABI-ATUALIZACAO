from __future__ import annotations

import sqlite3
import struct
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from services.backup_service import BackupService
from services.backup_envelope import MAGIC, MAX_HEADER_SIZE


class BackupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "app.db"
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("CREATE TABLE dados (id INTEGER PRIMARY KEY, nome TEXT NOT NULL)")
            conn.execute("INSERT INTO dados(nome) VALUES ('NabiCode')")
            conn.commit()
        finally:
            conn.close()
        self.config: dict[str, str] = {
            "pasta_backup_local": str(self.root / "local"),
            "pasta_backup_nuvem": str(self.root / "cloud"),
            "backup_diario_ativo": "1",
        }
        self.fiscal = self.root / "fiscal"
        (self.fiscal / "homologacao" / "55" / "chave").mkdir(parents=True)
        (self.fiscal / "homologacao" / "55" / "chave" / "processado.xml").write_bytes(
            b"<nfeProc/>"
        )
        (self.fiscal / "homologacao" / "55" / "chave" / "danfe.pdf").write_bytes(
            b"%PDF-1.4 teste"
        )
        (self.fiscal / "certificate").mkdir()
        (self.fiscal / "certificate" / "active.pfx").write_bytes(b"segredo")
        self.service = BackupService(
            database_path=self.db,
            default_directory=self.root / "default",
            get_config=self.config.get,
            set_config=lambda key, value: self.config.__setitem__(key, value),
            fiscal_directory=self.fiscal,
            now=lambda: datetime(2026, 8, 2, 20, 30, 0),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_all_gera_e_valida_todos_os_destinos(self) -> None:
        result = self.service.create_all("backup_manual")
        self.assertEqual(2, len(result.created))
        self.assertEqual(2, len(result.fiscal_archives))
        self.assertEqual((), result.errors)
        for path in result.created:
            conn = sqlite3.connect(path)
            try:
                self.assertEqual("NabiCode", conn.execute("SELECT nome FROM dados").fetchone()[0])
            finally:
                conn.close()
        for path in result.fiscal_archives:
            manifest = self.service._validate_fiscal_archive(Path(path))
            self.assertEqual(2, len(manifest["documents"]))
            self.assertEqual("2031-08-03", manifest["retain_until"])
            self.assertFalse(any("active.pfx" in item["path"] for item in manifest["documents"]))

    def test_restaura_documentos_fiscais_sem_sobrescrever_conflito(self) -> None:
        archive = self.service.create_all("restauracao").fiscal_archives[0]
        restored_dir = self.root / "fiscal_restaurado"
        restored = self.service.restore_fiscal_archive(archive, restored_dir)
        self.assertEqual(2, len(restored))
        xml = restored_dir / "homologacao" / "55" / "chave" / "processado.xml"
        self.assertEqual(b"<nfeProc/>", xml.read_bytes())
        xml.write_bytes(b"conteudo diferente")
        with self.assertRaisesRegex(FileExistsError, "documento fiscal diferente"):
            self.service.restore_fiscal_archive(archive, restored_dir)

    def test_run_daily_e_idempotente_por_dia(self) -> None:
        first = self.service.run_daily()
        second = self.service.run_daily()
        self.assertEqual(2, len(first.created))
        self.assertEqual("SUCESSO", first.status)
        self.assertTrue(second.skipped)
        self.assertEqual("JA_CONCLUIDO", second.status)
        self.assertEqual("2026-08-02", self.config["ultimo_backup_diario"])

    def test_run_daily_desativado_nao_cria_arquivo_nem_estado(self):
        self.config["backup_diario_ativo"] = "0"
        result = self.service.run_daily()
        self.assertTrue(result.skipped)
        self.assertEqual("DESATIVADO", result.status)
        self.assertEqual([], list((self.root / "local").glob("*.db")))
        self.assertNotIn("ultimo_backup_diario", self.config)

    def test_falha_secundaria_nao_esconde_parcial_e_retry_repete_so_destino_falho(self):
        original_create = self.service.create
        cloud = str((self.root / "cloud").resolve())
        failed = {"value": False}

        def create(directory, prefix="backup_diario"):
            if str(Path(directory).resolve()) == cloud and not failed["value"]:
                failed["value"] = True
                raise OSError("sincronização indisponível")
            return original_create(directory, prefix)

        self.service.create = create  # type: ignore[method-assign]
        first = self.service.run_daily()
        self.assertEqual("PARCIAL", first.status)
        self.assertEqual(1, len(first.created))
        self.assertEqual(1, len(first.errors))
        self.assertNotIn("ultimo_backup_diario", self.config)
        second = self.service.run_daily()
        self.assertEqual("SUCESSO", second.status)
        self.assertEqual(1, len(second.created))
        self.assertTrue(second.destinations[0].skipped)
        self.assertFalse(second.destinations[1].skipped)
        self.assertEqual(1, len(list((self.root / "local").glob("*.db"))))
        self.assertEqual(1, len(list((self.root / "cloud").glob("*.db"))))
        self.assertEqual("2026-08-02", self.config["ultimo_backup_diario"])

    def test_run_daily_concorrente_cria_apenas_um_conjunto(self) -> None:
        barrier = threading.Barrier(2)
        results = []

        def run():
            barrier.wait()
            results.append(self.service.run_daily())

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sum(len(result.created) for result in results), 2)
        self.assertEqual(sum(result.skipped for result in results), 1)
        self.assertEqual(len(list((self.root / "local").glob("*.db"))), 1)
        self.assertEqual(len(list((self.root / "cloud").glob("*.db"))), 1)

    def test_diretorios_duplicados_sao_eliminados(self) -> None:
        self.config["pasta_backup_nuvem"] = self.config["pasta_backup_local"]
        self.assertEqual(1, len(self.service.configured_directories()))

    def test_caminho_relativo_legado_e_resolvido_no_appdata(self) -> None:
        self.config["pasta_backup_local"] = "backups_moveis"
        self.config["pasta_backup_nuvem"] = ""
        self.assertEqual(
            [str((self.service.default_directory.parent / "backups_moveis").resolve())],
            self.service.configured_directories(),
        )

    def test_backup_corrompido_e_removido(self) -> None:
        original_validate = self.service._validate
        self.service._validate = lambda _path: (_ for _ in ()).throw(RuntimeError("falha simulada"))  # type: ignore[method-assign]
        try:
            with self.assertRaisesRegex(RuntimeError, "falha simulada"):
                self.service.create(self.root / "invalid", "teste")
        finally:
            self.service._validate = original_validate  # type: ignore[method-assign]
        self.assertEqual([], list((self.root / "invalid").glob("*.db")))

    def test_falha_parcial_remove_arquivo_incompleto(self) -> None:
        def fail_after_write(_source, destination):
            Path(destination).write_bytes(b"parcial")
            raise OSError("sem espaÃ§o")

        with patch("services.backup_service.backup_database", side_effect=fail_after_write):
            with self.assertRaisesRegex(OSError, "sem espaÃ§o"):
                self.service.create(self.root / "partial", "teste")
        self.assertEqual([], list((self.root / "partial").glob("*.db")))

    def test_backups_no_mesmo_segundo_tem_nomes_unicos(self) -> None:
        moments = iter(
            (
                datetime(2026, 8, 2, 20, 30, 0, 1),
                datetime(2026, 8, 2, 20, 30, 0, 2),
            )
        )
        self.service.now = lambda: next(moments)
        first = self.service.create(self.root / "unique", "manual")
        second = self.service.create(self.root / "unique", "manual")
        self.assertNotEqual(first, second)
        self.assertTrue(Path(first).is_file())
        self.assertTrue(Path(second).is_file())

    def test_backups_com_instante_identico_nao_sobrescrevem_anterior(self) -> None:
        fixed = datetime(2026, 8, 2, 20, 30, 0, 123456)
        self.service.now = lambda: fixed
        first = Path(self.service.create(self.root / "collision", "manual"))
        first_bytes = first.read_bytes()
        second = Path(self.service.create(self.root / "collision", "manual"))
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), first_bytes)
        self.assertTrue(second.is_file())
        self.assertEqual(len(list((self.root / "collision").glob("*.db"))), 2)

    def test_backups_concorrentes_com_instante_identico_reservam_nomes_unicos(self) -> None:
        self.service.now = lambda: datetime(2026, 8, 2, 20, 30, 0, 654321)
        barrier = threading.Barrier(2)
        created = []

        def run():
            barrier.wait()
            created.append(self.service.create(self.root / "concurrent", "manual"))

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(set(created)), 2)
        self.assertTrue(all(Path(path).is_file() for path in created))

    def test_arquivo_vazio_e_rejeitado(self) -> None:
        empty = self.root / "empty.db"
        empty.touch()
        with self.assertRaisesRegex(RuntimeError, "ausente ou vazio"):
            self.service._validate(empty)

    def test_verificacao_de_restauracao_usa_copia_temporaria_sem_tocar_ativo(self):
        backup = self.service.create(self.root / "restore", "teste_restore")
        connection = sqlite3.connect(self.db)
        connection.execute("UPDATE dados SET nome='ATIVO ALTERADO'")
        connection.commit(); connection.close()
        report = self.service.verify_restore_in_temporary(backup)
        self.assertEqual("ok", report.integrity)
        self.assertEqual((), report.foreign_key_errors)
        self.assertEqual(64, len(report.sha256))
        connection = sqlite3.connect(self.db)
        self.assertEqual("ATIVO ALTERADO", connection.execute("SELECT nome FROM dados").fetchone()[0])
        connection.close()

    def test_verificacao_rejeita_schema_incompativel_sem_tocar_ativo(self):
        incompatible = self.root / "incompatible.db"
        connection = sqlite3.connect(incompatible)
        connection.execute("CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT)")
        connection.execute("INSERT INTO configuracoes VALUES('db_schema_version','999')")
        connection.commit(); connection.close()
        with self.assertRaisesRegex(RuntimeError, "incompatível"):
            self.service.verify_restore_in_temporary(incompatible)
        connection = sqlite3.connect(self.db)
        self.assertEqual("NabiCode", connection.execute("SELECT nome FROM dados").fetchone()[0])
        connection.close()

    def test_backup_criptografado_roundtrip_e_formato_explicito(self):
        password = "senha forte de homologacao"
        backup = Path(self.service.create_encrypted(self.root / "secure", password))
        self.assertEqual(".nabibackup", backup.suffix)
        info = self.service.inspect_backup(backup)
        self.assertTrue(info.encrypted)
        self.assertEqual("NABICODE_ENCRYPTED_V1", info.format)
        report = self.service.verify_restore_in_temporary(backup, password)
        self.assertTrue(report.encrypted)
        self.assertEqual("NABICODE_ENCRYPTED_V1", report.backup_format)
        self.assertNotIn(password.encode(), backup.read_bytes())

    def test_backup_legado_permanece_detectavel_sem_conversao(self):
        legacy = Path(self.service.create(self.root / "legacy", "manual"))
        before = legacy.read_bytes()
        info = self.service.inspect_backup(legacy)
        report = self.service.verify_restore_in_temporary(legacy)
        self.assertFalse(info.encrypted)
        self.assertEqual("SQLITE_LEGACY_UNENCRYPTED", report.backup_format)
        self.assertEqual(before, legacy.read_bytes())

    def test_senha_errada_nao_toca_banco_ativo(self):
        backup = self.service.create_encrypted(
            self.root / "secure", "senha correta com doze"
        )
        with self.assertRaisesRegex(ValueError, "Senha incorreta|adulterado"):
            self.service.verify_restore_in_temporary(backup, "senha errada com doze")
        connection = sqlite3.connect(self.db)
        self.assertEqual("NabiCode", connection.execute("SELECT nome FROM dados").fetchone()[0])
        connection.close()

    def test_adulteracao_e_truncamento_sao_rejeitados(self):
        backup = Path(self.service.create_encrypted(
            self.root / "secure", "senha correta com doze"
        ))
        tampered = self.root / "tampered.nabibackup"
        content = bytearray(backup.read_bytes())
        content[-1] ^= 1
        tampered.write_bytes(content)
        with self.assertRaisesRegex(ValueError, "Senha incorreta|adulterado"):
            self.service.verify_restore_in_temporary(tampered, "senha correta com doze")
        truncated = self.root / "truncated.nabibackup"
        truncated.write_bytes(backup.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "Tamanho.*divergente"):
            self.service.verify_restore_in_temporary(truncated, "senha correta com doze")

    def test_cabecalho_malicioso_e_tamanho_gigante_sao_rejeitados(self):
        oversized = self.root / "oversized.nabibackup"
        oversized.write_bytes(MAGIC + struct.pack(">I", MAX_HEADER_SIZE + 1))
        with self.assertRaisesRegex(ValueError, "cabeçalho.*inválido"):
            self.service.inspect_backup(oversized)
        giant = self.root / "giant.nabibackup"
        header = (
            b'{"cipher":"AES-256-GCM","kdf":{"n":32768,"name":"scrypt",'
            b'"p":1,"r":8},"nonce":"AAAAAAAAAAAAAAAA","plaintext_size":'
            b'2147483649,"salt":"AAAAAAAAAAAAAAAAAAAAAA==","version":1}'
        )
        giant.write_bytes(MAGIC + struct.pack(">I", len(header)) + header)
        with self.assertRaisesRegex(ValueError, "Tamanho declarado"):
            self.service.inspect_backup(giant)

    def test_falha_na_validacao_remove_envelope_parcial(self):
        with patch.object(
            self.service, "_verify_encrypted_to_temporary",
            side_effect=RuntimeError("falha simulada"),
        ):
            with self.assertRaisesRegex(RuntimeError, "falha simulada"):
                self.service.create_encrypted(
                    self.root / "atomic", "senha correta com doze"
                )
        self.assertEqual([], list((self.root / "atomic").iterdir()))

    def test_backup_criptografado_com_instante_identico_nao_sobrescreve(self):
        password = "senha correta com doze"
        first = Path(self.service.create_encrypted(self.root / "collision", password))
        first_bytes = first.read_bytes()
        second = Path(self.service.create_encrypted(self.root / "collision", password))
        self.assertNotEqual(first, second)
        self.assertEqual(first_bytes, first.read_bytes())


if __name__ == "__main__":
    unittest.main()
