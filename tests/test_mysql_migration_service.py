import tempfile
import unittest
from pathlib import Path

from services.mysql_migration_service import MySQLMigrationService


DUMP = """
CREATE TABLE `cliente` (
  `codigo` int,
  `ficha` int,
  `cpf` varchar(20),
  `nome` varchar(100),
  `rg` varchar(20),
  `nascimento` date,
  `endereco` varchar(100),
  `telefone` varchar(20)
) ENGINE=InnoDB;
INSERT INTO `cliente` VALUES
(1,10,'123.456.789-00','  João   Silva  ','123','1980-01-02',' Rua A ','11999999999'),
(2,11,'123.456.789-00','','456','1890-01-02','Rua B','123');
INSERT INTO `venda` VALUES (5,0,1,100.00,20.00,'2020-01-01');
INSERT INTO `recebimento` VALUES (7,1,30.00,'2020-01-02','Pagamento parcial');
"""


class MySQLMigrationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'dump.sql'
        self.path.write_text(DUMP, encoding='latin1')
        self.service = MySQLMigrationService()

    def tearDown(self):
        self.temp.cleanup()

    def test_analyze_dump_reports_quality_issues(self):
        result = self.service.analyze_dump(self.path)
        self.assertEqual(result['clientes'], 2)
        self.assertEqual(result['duplicados_cpf'], 1)
        self.assertEqual(result['sem_nome'], 1)
        self.assertEqual(result['datas_invalidas'], 1)
        self.assertEqual(result['telefones_invalidos'], 1)

    def test_prepare_summary_preserves_balance_and_recent_events(self):
        result = self.service.prepare_summary(self.path)
        self.assertEqual(result['clientes']['1']['nome'], 'João Silva')
        self.assertAlmostEqual(result['saldos']['1'], 50.0)
        self.assertEqual(len(result['eventos']['1']), 2)
        self.assertEqual(result['contagens']['venda'], 1)

    def test_parser_handles_null_and_escaped_values(self):
        rows = self.service.parse_mysql_values("(1,NULL,'a\\'b','linha\\n2')")
        self.assertEqual(rows, [['1', None, "a'b", 'linha\n2']])

    def test_malformed_values_are_rejected(self):
        with self.assertRaises(ValueError):
            self.service.parse_mysql_values("(1,'incompleto')(")


if __name__ == '__main__':
    unittest.main()
