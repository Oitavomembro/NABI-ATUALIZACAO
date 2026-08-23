from __future__ import annotations

import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Any

from repositories import NFeImportRepository
from validators import NFeImportValidator
from .nfe_matching_service import (
    NFeItemAnalysis,
    NFeMatchingService,
    NFeProductCandidate as NFeProductCandidate,
)
from .nfe_xml_service import NFeDocument


class NFeImportService:
    """Analisa duplicidades, vínculos e histórico antes da gravação da NF-e."""

    def __init__(self, repository: NFeImportRepository) -> None:
        self.repository = repository
        self.matching_service = NFeMatchingService(repository)

    def validar_nao_importada(self, documento: NFeDocument) -> None:
        if documento.chave and self.repository.buscar_importacao_por_chave(documento.chave):
            raise ValueError("Esta NF-e já foi importada anteriormente.")

    def analisar(self, documento: NFeDocument) -> list[NFeItemAnalysis]:
        return self.matching_service.analyze(documento)

    validar_decisao = staticmethod(NFeImportValidator.decision)


    def importar_atomicamente(
        self,
        documento: NFeDocument,
        *,
        arquivo_origem: str | Path,
        itens: list[dict[str, Any]],
        usuario: str = "Sistema",
        idempotency_key: str | None = None,
        operation_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        """Grava toda a importação em uma única transação SQLite.

        ``itens`` deve conter a decisão validada e os valores finais de cada item.
        Qualquer falha em produto, vínculo, estoque, financeiro ou histórico causa
        rollback integral, mantendo a NF-e disponível para nova tentativa.
        """
        NFeImportValidator.complete_items(len(itens), len(documento.itens))
        key = str(idempotency_key or "").strip()
        fingerprint = str(operation_fingerprint or "").strip()
        if bool(key) != bool(fingerprint):
            raise ValueError("Idempotência da importação exige chave e impressão digital.")
        if key and (len(key) > 128 or not re.fullmatch(r"[A-Za-z0-9:._-]+", key)):
            raise ValueError("Chave idempotente da importação é inválida.")
        if fingerprint and not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("Identificação idempotente da importação é inválida.")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        criados = vinculados = 0
        resultados: list[dict[str, Any]] = []

        with self.repository.database.session(write=True) as connection:
            if key:
                previous = connection.execute(
                    "SELECT fingerprint,status,result_json FROM assistant_operation_journal "
                    "WHERE idempotency_key=?",
                    (key,),
                ).fetchone()
                if previous:
                    if str(previous["fingerprint"]) != fingerprint:
                        raise ValueError("A chave idempotente já pertence a outra operação.")
                    if str(previous["status"]) == "COMMITTED":
                        return json.loads(str(previous["result_json"] or "{}"))
                    raise RuntimeError("A importação idempotente anterior não foi concluída.")
                connection.execute(
                    """INSERT INTO assistant_operation_journal
                       (idempotency_key,operation_kind,fingerprint,status,result_json,username,created_at)
                       VALUES(?, 'NFE_ENTRY_IMPORT', ?, 'PENDING', '', ?, ?)""",
                    (key, fingerprint, str(usuario or "Sistema"), agora),
                )
            if documento.chave:
                duplicada = connection.execute(
                    "SELECT id FROM nfe_importacoes WHERE chave=? LIMIT 1", (documento.chave,)
                ).fetchone()
                if duplicada:
                    raise ValueError("Esta NF-e já foi importada anteriormente.")

            fornecedor_id = self.repository.obter_ou_criar_fornecedor_transacao(
                connection, documento.cnpj, documento.fornecedor, agora
            )
            for indice, (item_xml, preparado) in enumerate(zip(documento.itens, itens)):
                acao = str(preparado.get("acao") or "").upper()
                produto_id = preparado.get("produto_id")
                acao = self.validar_decisao(acao, produto_id)
                unidade_estoque_id = self.repository.obter_ou_criar_unidade_transacao(
                    connection, preparado.get("unidade") or "UN", agora
                )
                unidade_compra_id = self.repository.obter_ou_criar_unidade_transacao(
                    connection, item_xml.unidade or "UN", agora
                )
                if acao == "CRIAR":
                    produto_id = self.repository.criar_produto_transacao(
                        connection, item=item_xml, preparado=preparado, fornecedor_id=fornecedor_id,
                        unidade_id=unidade_estoque_id, unidade_compra_id=unidade_compra_id, agora=agora,
                    )
                    criados += 1
                    status = "criado"
                else:
                    produto_id = int(produto_id)
                    produto = connection.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone()
                    if not produto:
                        raise ValueError(f"Produto selecionado não existe para o item {item_xml.descricao}.")
                    if acao == "ATUALIZAR":
                        self.repository.atualizar_produto_transacao(
                            connection, produto_id=produto_id, item=item_xml, preparado=preparado,
                            fornecedor_id=fornecedor_id, unidade_id=unidade_estoque_id,
                            unidade_compra_id=unidade_compra_id, agora=agora,
                        )
                        status = "atualizado"
                    else:
                        status = "vinculado"
                    vinculados += 1

                self.repository.vincular_produto_fornecedor_transacao(
                    connection, produto_id=produto_id, fornecedor_id=fornecedor_id,
                    codigo_fornecedor=item_xml.codigo, unidade_fornecedor=item_xml.unidade,
                    fator_conversao=preparado["fator"], ultimo_custo=preparado["custo"], agora=agora,
                )
                quantidade_estoque = float(preparado["quantidade"]) * float(preparado["fator"])
                origem_id = f"{documento.chave or documento.numero}:{indice}"
                self.repository.registrar_entrada_estoque_transacao(
                    connection, produto_id=produto_id, quantidade=quantidade_estoque,
                    origem_id=origem_id, motivo=f"Entrada pela NF-e {documento.numero or documento.chave}",
                    usuario=usuario, agora=agora,
                )
                resultados.append({
                    "codigo": item_xml.codigo, "descricao": item_xml.descricao, "status": status,
                    "produto_id": produto_id, "quantidade_xml": float(preparado["quantidade"]),
                    "fator_conversao": preparado["fator"], "quantidade_estoque": quantidade_estoque,
                    "custo_unitario_estoque": preparado["custo"],
                    "margem": preparado["margem"], "preco_venda": preparado["preco"],
                })

            importacao_id = self.repository.registrar_importacao_transacao(
                connection, documento=documento, arquivo_origem=str(arquivo_origem),
                itens_criados=criados, itens_vinculados=vinculados, agora=agora,
            )
            titulo_id = self.repository.registrar_financeiro_transacao(
                connection, documento=documento, importacao_id=importacao_id,
                fornecedor_id=fornecedor_id, agora=agora,
            )
            result = {
                "importacao_id": importacao_id, "titulo_id": titulo_id,
                "itens_criados": criados, "itens_vinculados": vinculados,
                "resultados": resultados,
            }
            if key:
                connection.execute(
                    """UPDATE assistant_operation_journal
                       SET status='COMMITTED',result_json=?,committed_at=?
                       WHERE idempotency_key=?""",
                    (json.dumps(result, ensure_ascii=False, sort_keys=True), agora, key),
                )

        return result

    def listar_importacoes(self, data_inicial: str = "", data_final: str = "") -> list[dict[str, Any]]:
        return self.repository.listar_importacoes(data_inicial, data_final)

    def analisar_exclusao(self, importacao_id: int) -> dict[str, Any]:
        return self.repository.analisar_exclusao(importacao_id)

    def excluir_importacao(self, importacao_id: int) -> dict[str, Any]:
        return self.repository.excluir_importacao(importacao_id)

    def estornar_importacao(self, importacao_id: int, *, usuario: str = "Sistema") -> dict[str, Any]:
        return self.repository.estornar_importacao(importacao_id, usuario=usuario)

    def produtos_vinculados_importacao(self, importacao_id: int) -> dict[int, int]:
        return self.repository.produtos_vinculados_importacao(importacao_id)

    def revisar_produtos_importados(
        self,
        importacao_id: int,
        documento: NFeDocument,
        *,
        itens: list[dict[str, Any]],
        usuario: str = "Sistema",
    ) -> dict[str, Any]:
        """Atualiza cadastros ligados à nota sem repetir estoque ou financeiro."""
        NFeImportValidator.complete_items(len(itens), len(documento.itens))
        vinculados = self.produtos_vinculados_importacao(importacao_id)
        if len(vinculados) != len(documento.itens):
            raise ValueError("Os vínculos originais da NF-e estão incompletos; estorne e importe novamente.")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        atualizados = 0
        with self.repository.database.session(write=True) as connection:
            nota = connection.execute(
                "SELECT status FROM nfe_importacoes WHERE id=?", (int(importacao_id),)
            ).fetchone()
            if not nota:
                raise ValueError("NF-e importada não localizada.")
            if str(nota["status"] or "").upper() == "ESTORNADA":
                raise ValueError("Lançamento estornado não pode ser revisado.")
            fornecedor_id = self.repository.obter_ou_criar_fornecedor_transacao(
                connection, documento.cnpj, documento.fornecedor, agora
            )
            for index, (item_xml, preparado) in enumerate(zip(documento.itens, itens)):
                produto_id = vinculados[index]
                if int(preparado.get("produto_id") or 0) != produto_id:
                    raise ValueError("A revisão não pode trocar o produto que recebeu o estoque original.")
                unidade_id = self.repository.obter_ou_criar_unidade_transacao(
                    connection, preparado.get("unidade") or "UN", agora
                )
                unidade_compra_id = self.repository.obter_ou_criar_unidade_transacao(
                    connection, item_xml.unidade or "UN", agora
                )
                self.repository.atualizar_produto_transacao(
                    connection, produto_id=produto_id, item=item_xml, preparado=preparado,
                    fornecedor_id=fornecedor_id, unidade_id=unidade_id,
                    unidade_compra_id=unidade_compra_id, agora=agora,
                )
                self.repository.vincular_produto_fornecedor_transacao(
                    connection, produto_id=produto_id, fornecedor_id=fornecedor_id,
                    codigo_fornecedor=item_xml.codigo, unidade_fornecedor=item_xml.unidade,
                    fator_conversao=preparado["fator"], ultimo_custo=preparado["custo"], agora=agora,
                )
                atualizados += 1
        return {
            "importacao_id": int(importacao_id),
            "produtos_atualizados": atualizados,
            "usuario": str(usuario or "Sistema"),
        }

    def fornecedor_existente(self, documento: NFeDocument) -> dict[str, Any] | None:
        return self.repository.localizar_fornecedor(documento.cnpj, documento.fornecedor)

    def unidade_existente(self, sigla: str) -> dict[str, Any] | None:
        return self.repository.localizar_unidade(sigla)

    def registrar_resultado(
        self,
        documento: NFeDocument,
        *,
        arquivo_origem: str | Path,
        itens_criados: int,
        itens_vinculados: int,
    ) -> int:
        importacao_id = self.repository.registrar_importacao(
            chave=documento.chave,
            numero=documento.numero,
            fornecedor_cnpj=documento.cnpj,
            fornecedor_nome=documento.fornecedor,
            arquivo_origem=str(arquivo_origem),
            itens_total=len(documento.itens),
            itens_criados=itens_criados,
            itens_vinculados=itens_vinculados,
            valor_total=documento.valor_total,
        )
        # A nota e seus itens ficam disponíveis para o Assistente de Devolução.
        # Bancos usados por testes ou integrações antigas podem ainda não ter o schema 9.
        from repositories import NFeDevolucaoRepository
        from .nfe_devolucao_service import NFeDevolucaoService

        devolucao_repository = NFeDevolucaoRepository(self.repository.database)
        if devolucao_repository.estrutura_disponivel():
            try:
                NFeDevolucaoService(devolucao_repository).registrar_documento(
                    documento,
                    arquivo_origem=str(arquivo_origem),
                )
            except ValueError:
                # Uma nota com devoluções existentes não pode ser sobrescrita.
                logging.getLogger(__name__).warning(
                    "O espelho da NF-e %s não foi atualizado porque já possui devoluções.",
                    documento.numero or documento.chave,
                )
        return importacao_id
