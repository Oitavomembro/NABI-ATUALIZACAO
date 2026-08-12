import argparse
import sqlite3
from decimal import Decimal
from pathlib import Path


def d(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except Exception:
        return Decimal('0.00')


def main():
    p=argparse.ArgumentParser(description='Audita saldo consolidado, compras e parcelas de uma ficha NabiCode sem alterar o banco.')
    p.add_argument('--database', required=True, help='Caminho para uma COPIA do banco SQLite')
    p.add_argument('--ficha', required=True, help='Número da ficha do cliente')
    args=p.parse_args()
    db=Path(args.database)
    if not db.exists(): raise SystemExit(f'Banco não encontrado: {db}')
    conn=sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
    conn.row_factory=sqlite3.Row
    cliente=conn.execute("SELECT id,nome,numero_ficha,COALESCE(saldo_devedor,0) saldo FROM clientes WHERE CAST(numero_ficha AS TEXT)=?",(str(args.ficha),)).fetchone()
    if not cliente: raise SystemExit('Ficha não encontrada.')
    compras=conn.execute("SELECT id,COALESCE(valor,0) valor,COALESCE(valor_aberto,valor,0) aberto,COALESCE(status_pagamento,'') status,COALESCE(data,'') data FROM movimentacoes WHERE cliente_id=? AND tipo='COMPRA' AND UPPER(COALESCE(status_pagamento,''))<>'CANCELADO' ORDER BY id",(cliente['id'],)).fetchall()
    parcelas=conn.execute("SELECT p.id,p.movimentacao_id,p.numero_parcela,COALESCE(p.valor_parcela,0) valor,COALESCE(p.valor_pago,0) pago,COALESCE(p.status,'') status,COALESCE(p.vencimento,'') venc FROM parcelas p JOIN movimentacoes m ON m.id=p.movimentacao_id WHERE m.cliente_id=? AND m.tipo='COMPRA' ORDER BY p.movimentacao_id,p.numero_parcela,p.id",(cliente['id'],)).fetchall()
    saldo_cliente=d(cliente['saldo'])
    saldo_compras=sum((max(Decimal('0'),d(x['aberto'])) for x in compras),Decimal('0'))
    saldo_parcelas=sum((max(Decimal('0'),d(x['valor'])-d(x['pago'])) for x in parcelas),Decimal('0'))
    print(f"Ficha: {cliente['numero_ficha']} | Cliente: {cliente['nome']} | ID: {cliente['id']}")
    print(f"Saldo clientes:   R$ {saldo_cliente:.2f}")
    print(f"Saldo compras:    R$ {saldo_compras:.2f}")
    print(f"Saldo parcelas:   R$ {saldo_parcelas:.2f}")
    print(f"Residual cliente: R$ {max(Decimal('0'),saldo_cliente-saldo_compras):.2f}")
    print('\nCOMPRAS')
    for x in compras: print(dict(x))
    print('\nPARCELAS')
    for x in parcelas: print(dict(x))
    conn.close()

if __name__=='__main__': main()
