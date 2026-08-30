from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import json
from typing import Any, Callable

from repositories.decimal_storage import DecimalStorage, DecimalStorageError


@dataclass(frozen=True)
class VendaSuspensa:
    id: str
    criada_em: str
    cliente_id: int | None
    cliente_nome: str
    itens: tuple[dict[str, Any], ...]
    total: Decimal
    tipo: str = "SUSPENSA"
    metadata: dict[str, Any] | None = None


class PDVService:
    """Regras do PDV que independem da interface gráfica."""

    CONFIG_KEY = "pdv_vendas_suspensas"
    DOCUMENTS_KEY = "pdv_documentos_abertos"
    MODES = {"BALCAO", "TOUCH", "RAPIDO"}
    DOCUMENT_TYPES = {"ORCAMENTO", "PRE_VENDA"}
    PAYMENT_FORMS = {"DINHEIRO", "PIX", "DEBITO", "CREDITO", "CREDIARIO", "OUTROS"}
    PAYMENT_KEY_PREFIX = "pdv_pagamentos_venda_"

    def __init__(self, connection_factory: Callable[[], Any]):
        self.connection_factory = connection_factory

    MONEY = Decimal("0.01")
    RATE = Decimal("0.000001")

    @classmethod
    def _decimal(cls, value: Any, *, field: str) -> Decimal:
        try:
            return DecimalStorage.to_decimal(value, field=field)
        except DecimalStorageError as exc:
            raise ValueError(str(exc)) from exc

    @classmethod
    def _money(cls, value: Any, *, field: str) -> Decimal:
        return cls._decimal(value, field=field).quantize(cls.MONEY, rounding=ROUND_HALF_UP)

    @classmethod
    def totalizar(cls, itens: list[dict[str, Any]]) -> Decimal:
        total = Decimal("0")
        for item in itens:
            quantidade = cls._decimal(item.get("qtd", 0), field="quantidade")
            preco = cls._money(item.get("preco", 0), field="preço")
            if quantidade <= 0 or preco < 0:
                raise ValueError("Item da venda possui quantidade ou preço inválido.")
            total += quantidade * preco
        return total.quantize(cls.MONEY, rounding=ROUND_HALF_UP)

    @classmethod
    def aplicar_desconto(cls, item: dict[str, Any], percentual: Any) -> dict[str, Any]:
        percentual_decimal = cls._decimal(percentual, field="desconto").quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        if percentual_decimal < 0 or percentual_decimal > 100:
            raise ValueError("O desconto deve estar entre 0 e 100%.")
        quantidade = cls._decimal(item.get("qtd", 0), field="quantidade")
        preco_original = cls._money(item.get("preco_original", item.get("preco", 0)), field="preço original")
        if quantidade <= 0 or preco_original < 0:
            raise ValueError("Item da venda possui quantidade ou preço inválido.")
        atualizado = dict(item)
        preco = (preco_original * (Decimal("1") - percentual_decimal / Decimal("100"))).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        atualizado.update({
            "preco_original": preco_original,
            "desconto_percentual": percentual_decimal,
            "preco": preco,
            "subtotal": (quantidade * preco).quantize(cls.MONEY, rounding=ROUND_HALF_UP),
        })
        return atualizado

    @classmethod
    def atualizar_quantidade(cls, item: dict[str, Any], quantidade: Any) -> dict[str, Any]:
        quantidade_decimal = cls._decimal(quantidade, field="quantidade")
        if quantidade_decimal <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        preco = cls._money(item.get("preco", 0), field="preço")
        if preco < 0:
            raise ValueError("O preço do item não pode ser negativo.")
        atualizado = dict(item)
        atualizado["qtd"] = quantidade
        atualizado["subtotal"] = (quantidade_decimal * preco).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        return atualizado

    @classmethod
    def editar_item_venda(
        cls,
        item: dict[str, Any],
        *,
        quantidade: Any,
        preco_unitario: Any,
        desconto_percentual: Any = 0,
    ) -> dict[str, Any]:
        """Edita somente valores transacionais de uma linha do carrinho."""
        quantidade_decimal = cls._decimal(quantidade, field="quantidade")
        preco_base = cls._money(preco_unitario, field="preço unitário")
        desconto = cls._decimal(desconto_percentual, field="desconto").quantize(
            cls.MONEY, rounding=ROUND_HALF_UP
        )
        if quantidade_decimal <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        if preco_base < 0:
            raise ValueError("O preço unitário não pode ser negativo.")
        if desconto < 0 or desconto > 100:
            raise ValueError("O desconto deve estar entre 0 e 100%.")

        preco_final = (
            preco_base * (Decimal("1") - desconto / Decimal("100"))
        ).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        atualizado = dict(item)
        atualizado.update({
            "qtd": quantidade_decimal,
            "preco_original": preco_base,
            "desconto_percentual": desconto,
            "preco": preco_final,
            "subtotal": (quantidade_decimal * preco_final).quantize(
                cls.MONEY, rounding=ROUND_HALF_UP
            ),
        })
        return atualizado

    @classmethod
    def calcular_finalizacao(cls, total: Any, *, desconto: Any = 0, desconto_tipo: str = "VALOR",
                             acrescimo: Any = 0, acrescimo_tipo: str = "VALOR",
                             recebido: Any = 0, forma: str = "DINHEIRO") -> dict[str, Decimal]:
        total_decimal = cls._money(total, field="total da venda")
        if total_decimal <= 0:
            raise ValueError("O total da venda deve ser maior que zero.")
        desconto_decimal = max(Decimal("0"), cls._decimal(desconto, field="desconto"))
        acrescimo_decimal = max(Decimal("0"), cls._decimal(acrescimo, field="acréscimo"))
        desconto_tipo = str(desconto_tipo).upper()
        acrescimo_tipo = str(acrescimo_tipo).upper()
        if desconto_tipo == "PERCENTUAL" and desconto_decimal > 100:
            raise ValueError("O desconto percentual não pode ultrapassar 100%.")
        desconto_valor = (total_decimal * desconto_decimal / Decimal("100") if desconto_tipo == "PERCENTUAL" else desconto_decimal).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        if desconto_valor > total_decimal:
            raise ValueError("O desconto não pode ultrapassar o total da venda.")
        base = (total_decimal - desconto_valor).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        acrescimo_valor = (base * acrescimo_decimal / Decimal("100") if acrescimo_tipo == "PERCENTUAL" else acrescimo_decimal).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        total_final = (base + acrescimo_valor).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        if total_final <= 0:
            raise ValueError("O total final deve ser maior que zero.")
        forma = str(forma).strip().upper()
        recebido_decimal = total_final if forma == "CREDIARIO" else max(Decimal("0"), cls._money(recebido, field="valor recebido"))
        falta = max(Decimal("0"), total_final - recebido_decimal).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        troco = max(Decimal("0"), recebido_decimal - total_final).quantize(cls.MONEY, rounding=ROUND_HALF_UP) if forma == "DINHEIRO" else Decimal("0.00")
        return {"desconto_valor": desconto_valor, "acrescimo_valor": acrescimo_valor, "total_final": total_final, "recebido": recebido_decimal, "troco": troco, "falta": falta}

    @classmethod
    def ratear_total_itens(cls, itens: list[dict[str, Any]], total_final: Any) -> list[dict[str, Any]]:
        if not itens:
            raise ValueError("O carrinho de compras está vazio.")
        total_original = cls.totalizar(itens)
        total_final_decimal = cls._money(total_final, field="total final")
        if total_final_decimal <= 0:
            raise ValueError("O total final deve ser maior que zero.")
        fator = total_final_decimal / total_original
        ajustados: list[dict[str, Any]] = []
        acumulado = Decimal("0")
        for indice, item in enumerate(itens):
            novo = dict(item)
            qtd = cls._decimal(novo.get("qtd", 0), field="quantidade")
            if indice == len(itens) - 1:
                subtotal = (total_final_decimal - acumulado).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
            else:
                subtotal_original = cls._money(novo.get("subtotal", qtd * cls._money(novo.get("preco", 0), field="preço")), field="subtotal")
                subtotal = (subtotal_original * fator).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
                acumulado += subtotal
            novo["preco_original_venda"] = cls._money(novo.get("preco", 0), field="preço original")
            novo["subtotal_original_venda"] = cls._money(novo.get("subtotal", 0), field="subtotal original")
            novo["preco"] = (subtotal / qtd).quantize(cls.RATE, rounding=ROUND_HALF_UP)
            novo["subtotal"] = subtotal
            ajustados.append(novo)
        return ajustados

    @classmethod
    def validar_pagamentos(cls, total: Any, pagamentos: list[dict[str, Any]]) -> tuple[Decimal, Decimal]:
        total_decimal = cls._money(total, field="total da venda")
        if total_decimal <= 0:
            raise ValueError("O total da venda deve ser maior que zero.")
        if not pagamentos:
            raise ValueError("Informe ao menos uma forma de pagamento.")
        normalizados: list[tuple[str, Decimal]] = []
        for pagamento in pagamentos:
            forma = str(pagamento.get("forma", "")).strip().upper()
            try:
                valor = cls._money(pagamento.get("valor", 0), field="valor do pagamento")
            except ValueError as exc:
                raise ValueError("Valor de pagamento inválido.") from exc
            if forma not in cls.PAYMENT_FORMS:
                raise ValueError(f"Forma de pagamento inválida: {forma or '(vazia)' }.")
            if valor <= 0:
                raise ValueError("Cada pagamento deve ser maior que zero.")
            normalizados.append((forma, valor))
        crediarios = [valor for forma, valor in normalizados if forma == "CREDIARIO"]
        if crediarios:
            if len(crediarios) != 1:
                raise ValueError("Informe somente uma parte em crediário.")
            financiado = crediarios[0]
            entrada = sum((valor for forma, valor in normalizados if forma != "CREDIARIO"), Decimal("0"))
            if financiado + entrada != total_decimal:
                raise ValueError("A entrada somada ao valor financiado deve ser igual ao total da venda.")
            return total_decimal, Decimal("0.00")
        dinheiro = sum((valor for forma, valor in normalizados if forma == "DINHEIRO"), Decimal("0"))
        nao_monetario = sum((valor for forma, valor in normalizados if forma != "DINHEIRO"), Decimal("0"))
        recebido = (dinheiro + nao_monetario).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        if recebido < total_decimal:
            raise ValueError(f"Faltam R$ {total_decimal - recebido:.2f} para concluir a venda.")
        if nao_monetario > total_decimal:
            raise ValueError("Pagamentos sem dinheiro não podem gerar troco.")
        saldo_em_dinheiro = max(Decimal("0"), total_decimal - nao_monetario)
        troco = max(Decimal("0"), dinheiro - saldo_em_dinheiro).quantize(cls.MONEY, rounding=ROUND_HALF_UP)
        if recebido > total_decimal and troco <= 0:
            raise ValueError("Pagamento excedente só é permitido quando há dinheiro para o troco.")
        return recebido, troco

    @classmethod
    def registrar_pagamentos_transacao(cls, conn: Any, venda_id: int, pagamentos: list[dict[str, Any]],
                                       *, total: Any, recebido: Any, troco: Any) -> None:
        recebido_validado, troco_validado = cls.validar_pagamentos(total, pagamentos)
        total_decimal = cls._money(total, field="total da venda")
        payload = {
            "venda_id": int(venda_id),
            "total": DecimalStorage.canonical(total_decimal, field="total da venda"),
            "recebido": DecimalStorage.canonical(recebido_validado, field="valor recebido"),
            "troco": DecimalStorage.canonical(troco_validado, field="troco"),
            "pagamentos": [
                {
                    "forma": str(p["forma"]).strip().upper(),
                    "valor": DecimalStorage.canonical(cls._money(p["valor"], field="valor do pagamento")),
                    **({"card_integration": int(p.get("card_integration", 2))} if str(p.get("forma", "")).strip().upper() in {"DEBITO", "CREDITO"} else {}),
                    **({"card_authorization": str(p.get("card_authorization") or "").strip()[:20]} if str(p.get("card_authorization") or "").strip() else {}),
                }
                for p in pagamentos
            ],
            "registrado_em": datetime.now().isoformat(timespec="seconds"),
        }
        chave = f"{cls.PAYMENT_KEY_PREFIX}{int(venda_id)}"
        conn.execute("INSERT INTO configuracoes(chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, json.dumps(payload, ensure_ascii=False, sort_keys=True)))

    def obter_pagamentos_venda(self, venda_id: int) -> dict[str, Any] | None:
        conn = self.connection_factory()
        try:
            row = conn.execute(
                "SELECT valor FROM configuracoes WHERE chave = ?",
                (f"{self.PAYMENT_KEY_PREFIX}{int(venda_id)}",),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        try:
            dados = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(dados, dict):
            return None
        for campo in ("total", "recebido", "troco"):
            if campo in dados:
                dados[campo] = self._money(dados[campo], field=campo)
        for pagamento in dados.get("pagamentos", []):
            if isinstance(pagamento, dict) and "valor" in pagamento:
                pagamento["valor"] = self._money(pagamento["valor"], field="valor do pagamento")
        return dados

    @classmethod
    def normalizar_modo(cls, modo: str) -> str:
        normalizado = str(modo or "BALCAO").strip().upper()
        if normalizado not in cls.MODES:
            raise ValueError("Modo de PDV inválido.")
        return normalizado

    def listar_suspensas(self) -> list[VendaSuspensa]:
        return self._listar(self.CONFIG_KEY, "SUSPENSA")

    def listar_documentos(self, tipo: str | None = None) -> list[VendaSuspensa]:
        documentos = self._listar(self.DOCUMENTS_KEY, "DOCUMENTO")
        if tipo is None:
            return documentos
        tipo = str(tipo).strip().upper()
        return [documento for documento in documentos if documento.tipo == tipo]

    def suspender(self, itens: list[dict[str, Any]], *, cliente_id: int | None = None,
                  cliente_nome: str = "") -> VendaSuspensa:
        return self._registrar(self.CONFIG_KEY, "SUSPENSA", itens, cliente_id, cliente_nome)

    def salvar_documento(self, tipo: str, itens: list[dict[str, Any]], *, cliente_id: int | None = None,
                         cliente_nome: str = "", metadata: dict[str, Any] | None = None) -> VendaSuspensa:
        tipo = str(tipo).strip().upper()
        if tipo not in self.DOCUMENT_TYPES:
            raise ValueError("Tipo de documento do PDV inválido.")
        return self._registrar(
            self.DOCUMENTS_KEY, tipo, itens, cliente_id, cliente_nome,
            metadata=metadata,
        )

    def reabrir(self, venda_id: str) -> VendaSuspensa:
        return self._retirar(self.CONFIG_KEY, venda_id, "SUSPENSA")

    def consumir_documento(self, documento_id: str) -> VendaSuspensa:
        return self._retirar(self.DOCUMENTS_KEY, documento_id, "DOCUMENTO")

    def _listar(self, chave: str, tipo_padrao: str) -> list[VendaSuspensa]:
        dados = self._load(chave)
        vendas: list[VendaSuspensa] = []
        for registro in dados:
            try:
                itens = tuple(dict(item) for item in registro.get("itens", []))
                total = self.totalizar(list(itens))
                vendas.append(VendaSuspensa(
                    id=str(registro["id"]), criada_em=str(registro["criada_em"]),
                    cliente_id=int(registro["cliente_id"]) if registro.get("cliente_id") is not None else None,
                    cliente_nome=str(registro.get("cliente_nome", "")), itens=itens, total=total,
                    tipo=str(registro.get("tipo", tipo_padrao)).upper(),
                    metadata=dict(registro.get("metadata") or {}),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(vendas, key=lambda venda: venda.criada_em, reverse=True)

    def _registrar(self, chave: str, tipo: str, itens: list[dict[str, Any]],
                   cliente_id: int | None, cliente_nome: str,
                   metadata: dict[str, Any] | None = None) -> VendaSuspensa:
        if not itens:
            raise ValueError("Não há itens para preservar.")
        copia_itens = [dict(item) for item in itens]
        total = self.totalizar(copia_itens)
        criada_em = datetime.now().isoformat(timespec="seconds")
        identificador = datetime.now().strftime("%Y%m%d%H%M%S%f")
        registro = {
            "id": identificador, "tipo": tipo, "criada_em": criada_em,
            "cliente_id": int(cliente_id) if cliente_id is not None else None,
            "cliente_nome": str(cliente_nome or "").strip(), "itens": copia_itens,
            "metadata": dict(metadata or {}),
        }
        dados = self._load(chave)
        dados.append(registro)
        self._save(chave, dados)
        return VendaSuspensa(
            id=identificador, criada_em=criada_em, cliente_id=registro["cliente_id"],
            cliente_nome=registro["cliente_nome"], itens=tuple(copia_itens), total=total, tipo=tipo,
            metadata=dict(registro["metadata"]),
        )

    def _retirar(self, chave: str, identificador: str, tipo_padrao: str) -> VendaSuspensa:
        identificador = str(identificador)
        dados = self._load(chave)
        registro = next((item for item in dados if str(item.get("id")) == identificador), None)
        if registro is None:
            raise ValueError("Registro do PDV não encontrado.")
        self._save(chave, [item for item in dados if str(item.get("id")) != identificador])
        itens = tuple(dict(item) for item in registro.get("itens", []))
        return VendaSuspensa(
            id=identificador, criada_em=str(registro.get("criada_em", "")),
            cliente_id=int(registro["cliente_id"]) if registro.get("cliente_id") is not None else None,
            cliente_nome=str(registro.get("cliente_nome", "")), itens=itens,
            total=self.totalizar(list(itens)), tipo=str(registro.get("tipo", tipo_padrao)).upper(),
            metadata=dict(registro.get("metadata") or {}),
        )

    def _load(self, chave: str) -> list[dict[str, Any]]:
        conn = self.connection_factory()
        try:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave=?", (chave,)).fetchone()
            if not row or not row[0]:
                return []
            data = json.loads(row[0])
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
        finally:
            conn.close()

    @classmethod
    def _json_ready(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return DecimalStorage.canonical(value)
        if isinstance(value, dict):
            return {key: cls._json_ready(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_ready(item) for item in value]
        return value

    def _save(self, chave: str, dados: list[dict[str, Any]]) -> None:
        payload = json.dumps(self._json_ready(dados), ensure_ascii=False, separators=(",", ":"))
        conn = self.connection_factory()
        try:
            conn.execute(
                "INSERT INTO configuracoes(chave,valor) VALUES(?,?) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, payload),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
