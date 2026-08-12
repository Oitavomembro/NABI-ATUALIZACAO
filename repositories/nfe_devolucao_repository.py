from __future__ import annotations

from datetime import datetime
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from database import DatabaseManager


class NFeDevolucaoRepository:
    """Persistência das notas de origem e dos rascunhos de devolução."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database


    FISCAL_STATE_PREFIX = "nfe_devolucao.fiscal."

    def salvar_estado_fiscal(self, devolucao_id: int, estado: dict[str, Any], *, status: str) -> dict[str, Any]:
        """Persiste o ciclo fiscal sem exigir alteração do schema legado."""
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chave = f"{self.FISCAL_STATE_PREFIX}{int(devolucao_id)}"
        payload = dict(estado)
        payload["devolucao_id"] = int(devolucao_id)
        payload["status"] = str(status or "").strip().upper()
        payload["atualizado_em"] = agora
        with self.database.session(write=True) as connection:
            row = connection.execute("SELECT id FROM nfe_devolucoes WHERE id=?", (int(devolucao_id),)).fetchone()
            if not row:
                raise ValueError("Devolução não localizada.")
            tabela = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'"
            ).fetchone()
            if not tabela:
                raise RuntimeError("Tabela configuracoes não disponível para o histórico fiscal da devolução.")
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                (chave, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
            connection.execute(
                "UPDATE nfe_devolucoes SET status=?, atualizado_em=? WHERE id=?",
                (payload["status"], agora, int(devolucao_id)),
            )
        return payload

    def carregar_estado_fiscal(self, devolucao_id: int) -> dict[str, Any]:
        chave = f"{self.FISCAL_STATE_PREFIX}{int(devolucao_id)}"
        try:
            row = self.database.fetch_one("SELECT valor FROM configuracoes WHERE chave=?", (chave,))
        except Exception:
            return {}
        if not row:
            return {}
        try:
            value = json.loads(str(row["valor"] or "{}"))
        except (TypeError, ValueError):
            return {}
        return dict(value) if isinstance(value, dict) else {}


    STOCK_EFFECT_PREFIX = "nfe_devolucao.estoque."

    def aplicar_saida_estoque(self, devolucao_id: int, *, usuario: str = "Sistema") -> dict[str, Any]:
        """Baixa do estoque os itens de uma devolução autorizada, de forma idempotente."""
        chave_config = f"{self.STOCK_EFFECT_PREFIX}{int(devolucao_id)}"
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            devolucao = connection.execute(
                "SELECT status FROM nfe_devolucoes WHERE id=?", (int(devolucao_id),)
            ).fetchone()
            if not devolucao:
                raise ValueError("Devolução não localizada.")
            if str(devolucao["status"] or "").upper() not in {"AUTORIZADA", "AUTORIZADA_PENDENTE_ESTOQUE"}:
                raise ValueError("A saída de estoque exige devolução autorizada.")
            existente = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (chave_config,)
            ).fetchone()
            if existente:
                payload = json.loads(str(existente["valor"] or "{}"))
                if payload.get("status") == "APLICADO":
                    return payload
                if payload.get("status") == "REVERTIDO":
                    raise ValueError("Os efeitos de estoque desta devolução já foram revertidos.")

            itens = connection.execute(
                """SELECT di.quantidade, oi.codigo, oi.codigo_barras, oi.descricao
                   FROM nfe_devolucao_itens di
                   JOIN nfe_documentos_origem_itens oi ON oi.id=di.item_origem_id
                   WHERE di.devolucao_id=? ORDER BY di.id""",
                (int(devolucao_id),),
            ).fetchall()
            if not itens:
                raise ValueError("A devolução não possui itens.")

            preparados = []
            for item in itens:
                codigo = str(item["codigo"] or "").strip()
                ean = str(item["codigo_barras"] or "").strip()
                candidatos = []
                if codigo:
                    candidatos = connection.execute(
                        "SELECT id,codigo,nome,estoque_atual,controla_estoque,permite_estoque_negativo "
                        "FROM produtos WHERE codigo=?", (codigo,)
                    ).fetchall()
                if not candidatos and ean:
                    candidatos = connection.execute(
                        "SELECT id,codigo,nome,estoque_atual,controla_estoque,permite_estoque_negativo "
                        "FROM produtos WHERE codigo_barras=?", (ean,)
                    ).fetchall()
                if len(candidatos) != 1:
                    raise ValueError(
                        f"{item['descricao']}: produto local não localizado de forma única por código/EAN."
                    )
                produto = candidatos[0]
                if not bool(produto["controla_estoque"]):
                    raise ValueError(f"{produto['nome']}: produto não controla estoque.")
                quantidade = Decimal(str(item["quantidade"] or 0)).quantize(Decimal("0.0001"))
                saldo_anterior = Decimal(str(produto["estoque_atual"] or 0)).quantize(Decimal("0.0001"))
                saldo_atual = (saldo_anterior - quantidade).quantize(Decimal("0.0001"))
                if saldo_atual < 0 and not bool(produto["permite_estoque_negativo"]):
                    raise ValueError(
                        f"{produto['nome']}: estoque insuficiente para a devolução. "
                        f"Disponível: {float(saldo_anterior):g}."
                    )
                preparados.append((produto, quantidade, saldo_anterior, saldo_atual))

            movimentos = []
            for produto, quantidade, saldo_anterior, saldo_atual in preparados:
                connection.execute(
                    "UPDATE produtos SET estoque_atual=?, atualizado_em=? WHERE id=?",
                    (float(saldo_atual), agora, int(produto["id"])),
                )
                cursor = connection.execute(
                    """INSERT INTO estoque_movimentacoes
                       (produto_id,tipo,quantidade,saldo_anterior,saldo_atual,origem,origem_id,motivo,usuario,data)
                       VALUES(?,?,?,?,?,'DEVOLUCAO_NFE',?,'Saída por NF-e de devolução',?,?)""",
                    (int(produto["id"]), "SAIDA", -float(quantidade), float(saldo_anterior),
                     float(saldo_atual), str(devolucao_id), str(usuario or "Sistema"), agora),
                )
                movimentos.append({
                    "movimentacao_id": int(cursor.lastrowid),
                    "produto_id": int(produto["id"]),
                    "quantidade": float(quantidade),
                    "saldo_anterior": float(saldo_anterior),
                    "saldo_atual": float(saldo_atual),
                })
            payload = {
                "devolucao_id": int(devolucao_id), "status": "APLICADO",
                "aplicado_em": agora, "usuario": str(usuario or "Sistema"),
                "movimentos": movimentos,
            }
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                (chave_config, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
            return payload

    def reverter_saida_estoque(self, devolucao_id: int, *, usuario: str = "Sistema") -> dict[str, Any]:
        """Restaura o estoque após cancelamento fiscal aceito, sem apagar a auditoria."""
        chave_config = f"{self.STOCK_EFFECT_PREFIX}{int(devolucao_id)}"
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (chave_config,)
            ).fetchone()
            if not row:
                return {"devolucao_id": int(devolucao_id), "status": "NAO_APLICADO", "reversoes": []}
            payload = json.loads(str(row["valor"] or "{}"))
            if payload.get("status") == "REVERTIDO":
                return payload
            if payload.get("status") != "APLICADO":
                raise ValueError("Estado de estoque da devolução inválido.")
            reversoes = []
            for movimento in payload.get("movimentos", []):
                produto = connection.execute(
                    "SELECT id,nome,estoque_atual FROM produtos WHERE id=?",
                    (int(movimento["produto_id"]),),
                ).fetchone()
                if not produto:
                    raise ValueError("Produto da devolução não foi localizado para reversão.")
                quantidade = Decimal(str(movimento["quantidade"])).quantize(Decimal("0.0001"))
                saldo_anterior = Decimal(str(produto["estoque_atual"] or 0)).quantize(Decimal("0.0001"))
                saldo_atual = (saldo_anterior + quantidade).quantize(Decimal("0.0001"))
                connection.execute(
                    "UPDATE produtos SET estoque_atual=?, atualizado_em=? WHERE id=?",
                    (float(saldo_atual), agora, int(produto["id"])),
                )
                cursor = connection.execute(
                    """INSERT INTO estoque_movimentacoes
                       (produto_id,tipo,quantidade,saldo_anterior,saldo_atual,origem,origem_id,motivo,usuario,data)
                       VALUES(?,?,?,?,?,'CANCELAMENTO_DEVOLUCAO_NFE',?,'Reversão de NF-e de devolução cancelada',?,?)""",
                    (int(produto["id"]), "ENTRADA", float(quantidade), float(saldo_anterior),
                     float(saldo_atual), str(devolucao_id), str(usuario or "Sistema"), agora),
                )
                reversoes.append({"movimentacao_id": int(cursor.lastrowid), "produto_id": int(produto["id"]),
                                  "quantidade": float(quantidade), "saldo_anterior": float(saldo_anterior),
                                  "saldo_atual": float(saldo_atual)})
            payload["status"] = "REVERTIDO"
            payload["revertido_em"] = agora
            payload["usuario_reversao"] = str(usuario or "Sistema")
            payload["reversoes"] = reversoes
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                (chave_config, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
            return payload

    def listar_pendencias_estoque(self, *, limite: int = 200) -> list[dict[str, Any]]:
        """Lista devoluções cujo efeito local de estoque precisa ser concluído."""
        limite = max(1, min(int(limite), 1000))
        rows = self.database.fetch_all(
            """SELECT d.id, d.status, d.atualizado_em, o.numero AS nota_numero, o.chave AS nota_chave
               FROM nfe_devolucoes d
               JOIN nfe_documentos_origem o ON o.id=d.documento_origem_id
               WHERE d.status IN ('AUTORIZADA_PENDENTE_ESTOQUE','CANCELADA_PENDENTE_ESTOQUE')
               ORDER BY d.id LIMIT ?""",
            (limite,),
        )
        return [dict(row) for row in rows]

    def listar_devolucoes(self, *, limite: int = 200) -> list[dict[str, Any]]:
        limite = max(1, min(int(limite), 1000))
        rows = self.database.fetch_all(
            """SELECT d.id, d.tipo, d.motivo, d.status, d.valor_total,
                      d.numero_devolucao, d.xml_rascunho, d.finalizado_em,
                      d.criado_em, d.atualizado_em,
                      o.numero AS nota_numero, o.chave AS nota_chave,
                      o.emitente_nome, o.destinatario_nome
               FROM nfe_devolucoes d
               JOIN nfe_documentos_origem o ON o.id=d.documento_origem_id
               ORDER BY d.id DESC LIMIT ?""",
            (limite,),
        )
        resultado: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            estado = self.carregar_estado_fiscal(int(item["id"]))
            item["access_key"] = str(estado.get("access_key") or "")
            item["protocol"] = str(estado.get("protocol") or "")
            item["fiscal_status"] = str(estado.get("status") or item.get("status") or "")
            item["fiscal_record"] = dict(estado.get("fiscal_record") or {})
            item["events"] = list(estado.get("events") or [])
            item["attempts"] = list(estado.get("attempts") or [])
            resultado.append(item)
        return resultado

    def estrutura_disponivel(self) -> bool:
        row = self.database.fetch_one(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='nfe_documentos_origem'"
        )
        return bool(row)

    def salvar_nota_origem(
        self,
        *,
        chave: str,
        numero: str,
        emitente_nome: str,
        emitente_documento: str,
        destinatario_nome: str,
        destinatario_documento: str,
        data_emissao: str,
        serie: str,
        modelo: str,
        valor_total: float,
        arquivo_origem: str,
        itens: Iterable[dict[str, Any]],
    ) -> int:
        chave = str(chave or "").strip()
        numero = str(numero or "").strip()
        if not chave and not numero:
            raise ValueError("A nota de origem precisa de chave ou número.")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            existente = None
            if chave:
                existente = connection.execute(
                    "SELECT id FROM nfe_documentos_origem WHERE chave=?", (chave,)
                ).fetchone()
            if existente is None and numero:
                existente = connection.execute(
                    "SELECT id FROM nfe_documentos_origem WHERE numero=? ORDER BY id DESC LIMIT 1", (numero,)
                ).fetchone()
            if existente:
                documento_id = int(existente["id"])
                possui_devolucao = connection.execute(
                    "SELECT 1 FROM nfe_devolucoes WHERE documento_origem_id=? LIMIT 1",
                    (documento_id,),
                ).fetchone()
                if possui_devolucao:
                    raise ValueError(
                        "A nota original já possui devoluções registradas e não pode ser sobrescrita."
                    )
                connection.execute(
                    """UPDATE nfe_documentos_origem
                       SET chave=CASE WHEN ?<>'' THEN ? ELSE chave END,
                           numero=?, emitente_nome=?, emitente_documento=?,
                           destinatario_nome=?, destinatario_documento=?, data_emissao=?,
                           serie=?, modelo=?, valor_total=?, arquivo_origem=?, atualizado_em=?
                       WHERE id=?""",
                    (
                        chave, chave, numero, emitente_nome, emitente_documento,
                        destinatario_nome, destinatario_documento, data_emissao,
                        serie, modelo, float(valor_total or 0), arquivo_origem, agora,
                        documento_id,
                    ),
                )
                connection.execute("DELETE FROM nfe_documentos_origem_itens WHERE documento_id=?", (documento_id,))
            else:
                cursor = connection.execute(
                    """INSERT INTO nfe_documentos_origem
                       (chave,numero,emitente_nome,emitente_documento,destinatario_nome,
                        destinatario_documento,data_emissao,serie,modelo,valor_total,
                        arquivo_origem,criado_em,atualizado_em)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        chave, numero, emitente_nome, emitente_documento,
                        destinatario_nome, destinatario_documento, data_emissao,
                        serie, modelo, float(valor_total or 0), arquivo_origem, agora, agora,
                    ),
                )
                documento_id = int(cursor.lastrowid)

            impostos_itens: dict[str, dict[str, float]] = {}
            for indice, item in enumerate(itens, start=1):
                item_numero = int(item.get("item_numero") or indice)
                impostos_itens[str(item_numero)] = {
                    campo: float(item.get(campo) or 0)
                    for campo in (
                        "base_icms", "aliquota_icms", "valor_icms",
                        "base_pis", "aliquota_pis", "valor_pis",
                        "base_cofins", "aliquota_cofins", "valor_cofins",
                        "base_ipi", "aliquota_ipi", "valor_ipi",
                    )
                }
                connection.execute(
                    """INSERT INTO nfe_documentos_origem_itens
                       (documento_id,item_numero,codigo,descricao,quantidade,unidade,
                        valor_unitario,valor_total,ncm,cfop,cest,codigo_barras,
                        origem_mercadoria,cst_icms,csosn,cst_pis,cst_cofins)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        documento_id,
                        item_numero,
                        str(item.get("codigo") or ""),
                        str(item.get("descricao") or ""),
                        float(item.get("quantidade") or 0),
                        str(item.get("unidade") or "UN"),
                        float(item.get("valor_unitario") or 0),
                        float(item.get("valor_total") or 0),
                        str(item.get("ncm") or ""),
                        str(item.get("cfop") or ""),
                        str(item.get("cest") or ""),
                        str(item.get("codigo_barras") or ""),
                        str(item.get("origem_mercadoria") or ""),
                        str(item.get("cst_icms") or ""),
                        str(item.get("csosn") or ""),
                        str(item.get("cst_pis") or ""),
                        str(item.get("cst_cofins") or ""),
                    ),
                )
            tabela_config = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'"
            ).fetchone()
            if tabela_config:
                connection.execute(
                    "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                    (
                        f"nfe_origem.impostos.{documento_id}",
                        json.dumps(impostos_itens, ensure_ascii=False, sort_keys=True),
                    ),
                )
        return documento_id

    def localizar_nota(self, referencia: str) -> dict[str, Any] | None:
        termo = str(referencia or "").strip()
        if not termo:
            return None
        row = self.database.fetch_one(
            """SELECT * FROM nfe_documentos_origem
               WHERE chave=? OR numero=?
               ORDER BY id DESC LIMIT 1""",
            (termo, termo),
        )
        return dict(row) if row else None

    def listar_itens(self, documento_id: int) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            """SELECT i.*,
                      COALESCE((SELECT SUM(di.quantidade)
                                FROM nfe_devolucao_itens di
                                JOIN nfe_devolucoes d ON d.id=di.devolucao_id
                                WHERE di.item_origem_id=i.id
                                  AND d.status NOT IN ('CANCELADA')), 0) AS quantidade_devolvida
               FROM nfe_documentos_origem_itens i
               WHERE i.documento_id=?
               ORDER BY i.item_numero, i.id""",
            (int(documento_id),),
        )
        itens = [dict(row) for row in rows]
        try:
            config = self.database.fetch_one(
                "SELECT valor FROM configuracoes WHERE chave=?",
                (f"nfe_origem.impostos.{int(documento_id)}",),
            )
            impostos = json.loads(str(config["valor"] or "{}")) if config else {}
        except (TypeError, ValueError, KeyError, Exception):
            impostos = {}
        for item in itens:
            item["quantidade_original"] = float(item.get("quantidade") or 0)
            perfil = impostos.get(str(item.get("item_numero")), {}) if isinstance(impostos, dict) else {}
            if isinstance(perfil, dict):
                item.update({campo: float(valor or 0) for campo, valor in perfil.items()})
        return itens

    def criar_rascunho(
        self,
        *,
        documento_origem_id: int,
        tipo: str,
        motivo: str,
        observacoes: str,
        itens: Iterable[dict[str, Any]],
    ) -> int:
        tipo = str(tipo or "").strip().upper()
        if tipo not in {"INTEGRAL", "PARCIAL"}:
            raise ValueError("Tipo de devolução inválido.")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        itens_lista = list(itens)
        if not itens_lista:
            raise ValueError("Selecione ao menos um item para devolução.")
        with self.database.session(write=True) as connection:
            # A validação do saldo precisa ocorrer dentro da mesma transação que
            # grava o rascunho. Validar apenas na camada de serviço permite que
            # duas janelas abertas com o mesmo saldo ultrapassem a quantidade
            # original.
            ids_usados: set[int] = set()
            itens_validados: list[tuple[int, Decimal, Decimal]] = []
            for item in itens_lista:
                item_origem_id = int(item["item_origem_id"])
                if item_origem_id in ids_usados:
                    raise ValueError("O mesmo item foi selecionado mais de uma vez.")
                ids_usados.add(item_origem_id)
                quantidade = Decimal(str(item["quantidade"]))
                if quantidade <= 0:
                    raise ValueError("A quantidade devolvida deve ser maior que zero.")
                origem = connection.execute(
                    """SELECT id, documento_id, descricao, quantidade, valor_unitario
                       FROM nfe_documentos_origem_itens WHERE id=?""",
                    (item_origem_id,),
                ).fetchone()
                if not origem or int(origem["documento_id"]) != int(documento_origem_id):
                    raise ValueError("Um item selecionado não pertence à nota original.")
                devolvida = connection.execute(
                    """SELECT COALESCE(SUM(di.quantidade), 0) AS total
                       FROM nfe_devolucao_itens di
                       JOIN nfe_devolucoes d ON d.id=di.devolucao_id
                       WHERE di.item_origem_id=? AND d.status<>'CANCELADA'""",
                    (item_origem_id,),
                ).fetchone()
                saldo = Decimal(str(origem["quantidade"] or 0)) - Decimal(str(devolvida["total"] or 0))
                if quantidade > saldo:
                    descricao = str(origem["descricao"] or "Produto")
                    raise ValueError(
                        f"Quantidade inválida para '{descricao}'. Disponível: {float(max(saldo, Decimal('0'))):g}."
                    )
                valor_unitario = Decimal(str(item.get("valor_unitario", origem["valor_unitario"] or 0)))
                itens_validados.append((item_origem_id, quantidade, valor_unitario))

            cursor = connection.execute(
                """INSERT INTO nfe_devolucoes
                   (documento_origem_id,tipo,motivo,observacoes,status,valor_total,criado_em,atualizado_em)
                   VALUES(?,?,?,?, 'RASCUNHO',0,?,?)""",
                (int(documento_origem_id), tipo, motivo, observacoes, agora, agora),
            )
            devolucao_id = int(cursor.lastrowid)
            valor_total = Decimal("0.00")
            for item_origem_id, quantidade, valor_unitario in itens_validados:
                total_item = (quantidade * valor_unitario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                valor_total += total_item
                connection.execute(
                    """INSERT INTO nfe_devolucao_itens
                       (devolucao_id,item_origem_id,quantidade,valor_unitario,valor_total)
                       VALUES(?,?,?,?,?)""",
                    (
                        devolucao_id,
                        item_origem_id,
                        float(quantidade),
                        float(valor_unitario),
                        float(total_item),
                    ),
                )
            connection.execute(
                "UPDATE nfe_devolucoes SET valor_total=? WHERE id=?",
                (float(valor_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), devolucao_id),
            )
        return devolucao_id

    def buscar_rascunho(self, devolucao_id: int) -> dict[str, Any] | None:
        row = self.database.fetch_one(
            """SELECT d.*, o.numero AS nota_numero, o.chave AS nota_chave,
                      o.emitente_nome, o.emitente_documento,
                      o.destinatario_nome, o.destinatario_documento,
                      o.data_emissao, o.serie, o.modelo, o.valor_total AS nota_valor_total
               FROM nfe_devolucoes d
               JOIN nfe_documentos_origem o ON o.id=d.documento_origem_id
               WHERE d.id=?""",
            (int(devolucao_id),),
        )
        if not row:
            return None
        resultado = dict(row)
        resultado["itens"] = [dict(item) for item in self.database.fetch_all(
            """SELECT di.*, oi.quantidade AS quantidade_original, oi.item_numero, oi.codigo, oi.descricao, oi.unidade, oi.ncm, oi.cfop, oi.cest, oi.codigo_barras,
                      oi.origem_mercadoria, oi.cst_icms, oi.csosn, oi.cst_pis, oi.cst_cofins
               FROM nfe_devolucao_itens di
               JOIN nfe_documentos_origem_itens oi ON oi.id=di.item_origem_id
               WHERE di.devolucao_id=? ORDER BY oi.item_numero""",
            (int(devolucao_id),),
        )]
        try:
            config = self.database.fetch_one(
                "SELECT valor FROM configuracoes WHERE chave=?",
                (f"nfe_origem.impostos.{int(resultado['documento_origem_id'])}",),
            )
            impostos = json.loads(str(config["valor"] or "{}")) if config else {}
        except Exception:
            impostos = {}
        for item in resultado["itens"]:
            perfil = impostos.get(str(item.get("item_numero")), {}) if isinstance(impostos, dict) else {}
            if isinstance(perfil, dict):
                item.update({campo: float(valor or 0) for campo, valor in perfil.items()})
        return resultado

    def proximo_numero_devolucao(self) -> str:
        ano = datetime.now().strftime("%Y")
        prefixo = f"DEV-{ano}-"
        row = self.database.fetch_one(
            "SELECT numero_devolucao FROM nfe_devolucoes WHERE numero_devolucao LIKE ? ORDER BY numero_devolucao DESC LIMIT 1",
            (prefixo + "%",),
        )
        sequencia = 1
        if row and str(row["numero_devolucao"] or "").startswith(prefixo):
            try:
                sequencia = int(str(row["numero_devolucao"])[len(prefixo):]) + 1
            except ValueError:
                sequencia = 1
        return f"{prefixo}{sequencia:06d}"

    def definir_numero(self, devolucao_id: int, numero: str) -> None:
        numero = str(numero or "").strip()
        if not numero:
            raise ValueError("Número interno da devolução não informado.")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            row = connection.execute(
                "SELECT status, numero_devolucao FROM nfe_devolucoes WHERE id=?",
                (int(devolucao_id),),
            ).fetchone()
            if not row:
                raise ValueError("Rascunho de devolução não localizado.")
            if str(row["status"] or "").upper() == "CANCELADA":
                raise ValueError("Rascunho cancelado não pode receber numeração.")
            existente = connection.execute(
                "SELECT id FROM nfe_devolucoes WHERE numero_devolucao=? AND id<>?",
                (numero, int(devolucao_id)),
            ).fetchone()
            if existente:
                raise ValueError("Número interno de devolução já utilizado.")
            connection.execute(
                "UPDATE nfe_devolucoes SET numero_devolucao=?, atualizado_em=? WHERE id=?",
                (numero, agora, int(devolucao_id)),
            )

    def finalizar_rascunho(self, devolucao_id: int, numero: str, xml_rascunho: str, hash_xml: str) -> None:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            row = connection.execute(
                "SELECT status FROM nfe_devolucoes WHERE id=?",
                (int(devolucao_id),),
            ).fetchone()
            if not row:
                raise ValueError("Rascunho de devolução não localizado.")
            status = str(row["status"] or "").upper()
            if status == "CANCELADA":
                raise ValueError("Rascunho cancelado não pode ser finalizado.")
            connection.execute(
                """UPDATE nfe_devolucoes
                   SET numero_devolucao=?, xml_rascunho=?, hash_xml=?, status='PRONTO',
                       finalizado_em=?, atualizado_em=?
                   WHERE id=?""",
                (str(numero), str(xml_rascunho), str(hash_xml), agora, agora, int(devolucao_id)),
            )

    def cancelar_rascunho(self, devolucao_id: int) -> bool:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            row = connection.execute(
                "SELECT status FROM nfe_devolucoes WHERE id=?",
                (int(devolucao_id),),
            ).fetchone()
            if not row:
                return False
            if str(row["status"]).upper() != "RASCUNHO":
                raise ValueError("Somente rascunhos podem ser cancelados.")
            connection.execute(
                "UPDATE nfe_devolucoes SET status='CANCELADA', atualizado_em=? WHERE id=?",
                (agora, int(devolucao_id)),
            )
        return True
