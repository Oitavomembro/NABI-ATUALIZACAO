from decimal import Decimal
import tempfile
from pathlib import Path
import unittest

from database import DatabaseManager, ProductDecimalMigration
from repositories.compra_repository import CompraRepository
from repositories.decimal_storage import DecimalStorage, DecimalStorageError


class DecimalPolicyAndPurchasePersistenceTests(unittest.TestCase):
    def test_read_falls_back_for_empty_or_invalid_canonical(self):
        self.assertEqual(DecimalStorage.read('', 12.5), Decimal('12.5'))
        self.assertEqual(DecimalStorage.read('abc', 9.75), Decimal('9.75'))

    def test_legacy_real_rejects_overflow(self):
        with self.assertRaises(DecimalStorageError):
            DecimalStorage.legacy_real(Decimal('1E+10000'), field='preço')

    def test_purchase_items_store_exact_decimal_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(str(Path(tmp) / 'db.sqlite'))
            with db.session(write=True) as c:
                c.executescript('''
                CREATE TABLE produtos(id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,ativo INTEGER,controla_estoque INTEGER,tipo_produto TEXT,preco_custo REAL,preco_custo_decimal TEXT,estoque_atual REAL,fator_conversao REAL,fator_conversao_decimal TEXT,fornecedor_id INTEGER,atualizado_em TEXT);
                CREATE TABLE fornecedores(id INTEGER PRIMARY KEY,nome_fantasia TEXT,razao_social TEXT,cnpj TEXT,ativo INTEGER);
                CREATE TABLE pedidos_compra(id INTEGER PRIMARY KEY AUTOINCREMENT,fornecedor_id INTEGER,status TEXT,observacao TEXT,usuario TEXT,criado_em TEXT,atualizado_em TEXT);
                CREATE TABLE pedido_compra_itens(id INTEGER PRIMARY KEY AUTOINCREMENT,pedido_id INTEGER,produto_id INTEGER,quantidade_pedida REAL,quantidade_recebida REAL,custo_unitario REAL,valor_total REAL,observacao TEXT);
                CREATE TABLE recebimentos_compra(id INTEGER PRIMARY KEY AUTOINCREMENT,pedido_id INTEGER,documento TEXT,observacao TEXT,usuario TEXT,data_recebimento TEXT);
                CREATE TABLE recebimento_compra_itens(id INTEGER PRIMARY KEY AUTOINCREMENT,recebimento_id INTEGER,pedido_item_id INTEGER,produto_id INTEGER,quantidade REAL,custo_unitario REAL,valor_total REAL);
                CREATE TABLE historico_precos_produtos(id INTEGER PRIMARY KEY,produto_id INTEGER,preco_anterior REAL,preco_novo REAL,custo REAL,margem_percentual REAL);
                CREATE TABLE produto_fornecedores(id INTEGER PRIMARY KEY,produto_id INTEGER,fornecedor_id INTEGER,fator_conversao REAL,ultimo_custo REAL);
                ''')
            ProductDecimalMigration(db).run()
            repo = CompraRepository(db)
            with db.session(write=True) as c:
                pedido_id = repo.criar_pedido(fornecedor_id=1, observacao='', usuario='u', itens=[{
                    'produto_id': 1, 'quantidade': 2, 'custo_unitario': Decimal('0.123456789'),
                    'valor_total': Decimal('0.246913578'), 'observacao': ''
                }], connection=c)
                row = c.execute('SELECT custo_unitario_decimal,valor_total_decimal,typeof(custo_unitario_decimal) t FROM pedido_compra_itens WHERE pedido_id=?',(pedido_id,)).fetchone()
                self.assertEqual(row['custo_unitario_decimal'], '0.123456789')
                self.assertEqual(row['valor_total_decimal'], '0.246913578')
                self.assertEqual(row['t'], 'text')

    def test_schema_initializer_uses_single_decimal_migration(self):
        root = Path(__file__).resolve().parents[1]
        schema = (root / 'database' / 'schema_initializer.py').read_text(encoding='utf-8')
        self.assertIn('ProductDecimalMigration.migrate_connection(conn)', schema)
        self.assertNotIn('preco_venda_decimal=COALESCE', schema)
        self.assertNotIn('ultimo_custo_decimal=COALESCE', schema)


if __name__ == '__main__':
    unittest.main()
