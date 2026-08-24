from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree as ET

from repositories import NFeDevolucaoRepository
from .nfe_xml_service import NFeDocument, NFeXMLService
from .fiscal_service import FiscalService


@dataclass(frozen=True)
class DevolucaoItemDisponivel:
    item_origem_id: int
    codigo: str
    descricao: str
    unidade: str
    quantidade_original: float
    quantidade_devolvida: float
    quantidade_disponivel: float
    valor_unitario: float
    ncm: str
    cfop: str
    cest: str
    codigo_barras: str


class NFeDevolucaoService:
    """Monta, valida e exporta rascunhos de NF-e de devolução sem transmitir à SEFAZ."""

    XML_NAMESPACE = "urn:nabicode:nfe-devolucao:rascunho:v1"
    _RETURN_CFOP_BY_ORIGINAL = {
        "5101": "5201", "6101": "6201", "1101": "5201", "2101": "6201",
        "5102": "5202", "6102": "6202", "1102": "5202", "2102": "6202",
        "5401": "5410", "6401": "6410", "1401": "5410", "2401": "6410",
        "5402": "5410", "6402": "6410", "1402": "5410", "2402": "6410",
        "5403": "5411", "6403": "6411", "1403": "5411", "2403": "6411",
        "5404": "5411", "6404": "6411", "1404": "5411", "2404": "6411",
        "5405": "5411", "6405": "6411", "1405": "5411", "2405": "6411",
    }

    def __init__(self, repository: NFeDevolucaoRepository, xml_service: NFeXMLService | None = None) -> None:
        self.repository = repository
        self.xml_service = xml_service or NFeXMLService()

    @classmethod
    def sugerir_cfop_devolucao(
        cls, cfop_original: str, *, cst_icms: str = "", csosn: str = ""
    ) -> dict[str, Any]:
        """Analisa o CFOP importado e sugere opções; a confirmação continua humana."""
        original = "".join(ch for ch in str(cfop_original or "") if ch.isdigit())
        if len(original) != 4:
            return {"suggested": "", "candidates": [], "confidence": "BAIXA", "reason": "CFOP original ausente ou inválido."}
        relation_prefix = "6" if original[0] in {"2", "6"} else "5" if original[0] in {"1", "5"} else ""
        if not relation_prefix:
            return {"suggested": "", "candidates": [], "confidence": "BAIXA", "reason": "Operação exterior ou relação territorial não suportada automaticamente."}
        suggested = cls._RETURN_CFOP_BY_ORIGINAL.get(original, "")
        st = str(csosn or "").zfill(3) == "500" or str(cst_icms or "").zfill(2) in {"10", "30", "60", "70"} or original[1:2] == "4"
        if suggested:
            reason = "Mercadoria com substituição tributária identificada no XML." if st else "Natureza da venda original identificada pelo CFOP importado."
            confidence = "ALTA"
        else:
            suggested = f"{relation_prefix}411" if st else f"{relation_prefix}202"
            reason = "Sugestão conservadora baseada na tributação e na relação interna/interestadual; confirme a finalidade da compra."
            confidence = "MEDIA"
        candidates = [suggested]
        for suffix in (("410", "411") if st else ("201", "202", "553", "556")):
            option = f"{relation_prefix}{suffix}"
            if option not in candidates:
                candidates.append(option)
        return {"suggested": suggested, "candidates": candidates, "confidence": confidence, "reason": reason}

    def registrar_xml_origem(self, caminho: str | Path) -> int:
        documento = self.xml_service.ler(caminho)
        return self.registrar_documento(documento, arquivo_origem=str(caminho))

    def registrar_documento(self, documento: NFeDocument, *, arquivo_origem: str = "") -> int:
        return self.repository.salvar_nota_origem(
            chave=documento.chave,
            numero=documento.numero,
            emitente_nome=documento.fornecedor,
            emitente_documento=documento.cnpj,
            destinatario_nome=documento.destinatario,
            destinatario_documento=documento.destinatario_documento,
            data_emissao=documento.data_emissao,
            serie=documento.serie,
            modelo=documento.modelo,
            valor_total=documento.valor_total,
            arquivo_origem=arquivo_origem,
            itens=[{
                "item_numero": item.item_numero,
                "codigo": item.codigo,
                "descricao": item.descricao,
                "quantidade": item.quantidade,
                "unidade": item.unidade,
                "valor_unitario": item.valor_unitario,
                "valor_total": item.valor_total,
                "ncm": item.ncm,
                "cfop": item.cfop,
                "cest": item.cest,
                "codigo_barras": item.codigo_barras,
                "origem_mercadoria": item.origem_mercadoria,
                "cst_icms": item.cst_icms,
                "csosn": item.csosn,
                "cst_pis": item.cst_pis,
                "cst_cofins": item.cst_cofins,
                "base_icms": item.base_icms,
                "aliquota_icms": item.aliquota_icms,
                "valor_icms": item.valor_icms,
                "base_pis": item.base_pis,
                "aliquota_pis": item.aliquota_pis,
                "valor_pis": item.valor_pis,
                "base_cofins": item.base_cofins,
                "aliquota_cofins": item.aliquota_cofins,
                "valor_cofins": item.valor_cofins,
                "base_ipi": item.base_ipi,
                "aliquota_ipi": item.aliquota_ipi,
                "valor_ipi": item.valor_ipi,
            } for item in documento.itens],
        )

    def localizar_nota(self, referencia: str) -> tuple[dict, list[DevolucaoItemDisponivel]]:
        nota = self.repository.localizar_nota(referencia)
        if not nota:
            raise ValueError("Nota fiscal não localizada. Importe o XML original para continuar.")
        itens = []
        for item in self.repository.listar_itens(int(nota["id"])):
            original = float(item["quantidade"])
            devolvida = float(item["quantidade_devolvida"])
            disponivel = max(0.0, original - devolvida)
            itens.append(DevolucaoItemDisponivel(
                item_origem_id=int(item["id"]),
                codigo=str(item["codigo"] or ""),
                descricao=str(item["descricao"] or ""),
                unidade=str(item["unidade"] or "UN"),
                quantidade_original=original,
                quantidade_devolvida=devolvida,
                quantidade_disponivel=disponivel,
                valor_unitario=float(item["valor_unitario"]),
                ncm=str(item["ncm"] or ""),
                cfop=str(item["cfop"] or ""),
                cest=str(item["cest"] or ""),
                codigo_barras=str(item["codigo_barras"] or ""),
            ))
        return nota, itens

    def criar_rascunho(
        self,
        *,
        referencia_nota: str,
        tipo: str,
        selecoes: Iterable[tuple[int, float]] | None,
        motivo: str,
        observacoes: str = "",
    ) -> int:
        nota, itens_disponiveis = self.localizar_nota(referencia_nota)
        tipo_normalizado = str(tipo or "").strip().upper()
        mapa = {item.item_origem_id: item for item in itens_disponiveis}
        if tipo_normalizado == "INTEGRAL":
            escolhidos = [(item.item_origem_id, item.quantidade_disponivel) for item in itens_disponiveis if item.quantidade_disponivel > 0]
        elif tipo_normalizado == "PARCIAL":
            escolhidos = list(selecoes or [])
        else:
            raise ValueError("Escolha devolução integral ou parcial.")
        if not escolhidos:
            raise ValueError("Não há itens disponíveis para devolução.")

        itens_rascunho = []
        ids_usados: set[int] = set()
        for item_id, quantidade in escolhidos:
            item_id = int(item_id)
            if item_id in ids_usados:
                raise ValueError("O mesmo item foi selecionado mais de uma vez.")
            ids_usados.add(item_id)
            item = mapa.get(item_id)
            if item is None:
                raise ValueError("Um item selecionado não pertence à nota original.")
            quantidade_decimal = Decimal(str(quantidade))
            if quantidade_decimal <= 0:
                raise ValueError(f"A quantidade de '{item.descricao}' deve ser maior que zero.")
            disponivel_decimal = Decimal(str(item.quantidade_disponivel))
            if quantidade_decimal > disponivel_decimal:
                raise ValueError(
                    f"Quantidade inválida para '{item.descricao}'. Disponível: {item.quantidade_disponivel:g} {item.unidade}."
                )
            itens_rascunho.append({
                "item_origem_id": item_id,
                "quantidade": float(quantidade_decimal),
                "valor_unitario": item.valor_unitario,
            })
        return self.repository.criar_rascunho(
            documento_origem_id=int(nota["id"]),
            tipo=tipo_normalizado,
            motivo=str(motivo or "").strip() or "Devolução de mercadoria",
            observacoes=str(observacoes or "").strip(),
            itens=itens_rascunho,
        )

    def validar_rascunho(self, devolucao_id: int) -> list[str]:
        rascunho = self.repository.buscar_rascunho(devolucao_id)
        if not rascunho:
            raise ValueError("Rascunho de devolução não localizado.")
        pendencias: list[str] = []
        if str(rascunho.get("status") or "").upper() == "CANCELADA":
            pendencias.append("O rascunho está cancelado.")
        chave = str(rascunho.get("nota_chave") or "").strip()
        if not chave:
            pendencias.append("A nota original não possui chave de acesso.")
        elif len(chave) != 44 or not chave.isdigit():
            pendencias.append("A chave de acesso da nota original deve possuir 44 dígitos.")
        if not str(rascunho.get("destinatario_documento") or "").strip():
            pendencias.append("O destinatário da nota original não possui CPF/CNPJ.")
        for item in rascunho.get("itens", []):
            descricao = str(item.get("descricao") or "Produto sem descrição")
            if not str(item.get("ncm") or "").strip():
                pendencias.append(f"{descricao}: NCM não informado.")
            if not str(item.get("cfop") or "").strip():
                pendencias.append(f"{descricao}: CFOP original não informado.")
            if float(item.get("quantidade") or 0) <= 0:
                pendencias.append(f"{descricao}: quantidade inválida.")
        return pendencias

    def gerar_xml_rascunho(self, devolucao_id: int) -> bytes:
        pendencias = self.validar_rascunho(devolucao_id)
        if pendencias:
            raise ValueError("Rascunho possui pendências fiscais:\n- " + "\n- ".join(pendencias))
        rascunho = self.repository.buscar_rascunho(devolucao_id)
        if not rascunho:
            raise ValueError("Rascunho de devolução não localizado.")

        ET.register_namespace("", self.XML_NAMESPACE)
        tag = lambda nome: f"{{{self.XML_NAMESPACE}}}{nome}"
        raiz = ET.Element(tag("NFeDevolucaoRascunho"), {"versao": "1.0"})
        identificacao = ET.SubElement(raiz, tag("identificacao"))
        ET.SubElement(identificacao, tag("numeroInterno")).text = str(rascunho.get("numero_devolucao") or "")
        ET.SubElement(identificacao, tag("tipo")).text = str(rascunho["tipo"])
        ET.SubElement(identificacao, tag("motivo")).text = str(rascunho["motivo"])
        ET.SubElement(identificacao, tag("modelo")).text = "55"
        ET.SubElement(identificacao, tag("finalidade")).text = "4"

        referencia = ET.SubElement(raiz, tag("notaReferenciada"))
        ET.SubElement(referencia, tag("chave")).text = str(rascunho["nota_chave"])
        ET.SubElement(referencia, tag("numero")).text = str(rascunho["nota_numero"])
        ET.SubElement(referencia, tag("serie")).text = str(rascunho.get("serie") or "")
        ET.SubElement(referencia, tag("dataEmissao")).text = str(rascunho.get("data_emissao") or "")

        emitente = ET.SubElement(raiz, tag("emitenteOriginal"))
        ET.SubElement(emitente, tag("nome")).text = str(rascunho.get("emitente_nome") or "")
        ET.SubElement(emitente, tag("documento")).text = str(rascunho.get("emitente_documento") or "")
        destinatario = ET.SubElement(raiz, tag("destinatarioOriginal"))
        ET.SubElement(destinatario, tag("nome")).text = str(rascunho.get("destinatario_nome") or "")
        ET.SubElement(destinatario, tag("documento")).text = str(rascunho.get("destinatario_documento") or "")

        itens_xml = ET.SubElement(raiz, tag("itens"))
        for indice, item in enumerate(rascunho["itens"], start=1):
            item_xml = ET.SubElement(itens_xml, tag("item"), {"numero": str(indice)})
            for nome_xml, chave_item in (
                ("codigo", "codigo"), ("descricao", "descricao"), ("ean", "codigo_barras"),
                ("ncm", "ncm"), ("cest", "cest"), ("cfopOriginal", "cfop"),
                ("unidade", "unidade"), ("origemMercadoria", "origem_mercadoria"),
                ("cstIcms", "cst_icms"), ("csosn", "csosn"),
                ("cstPis", "cst_pis"), ("cstCofins", "cst_cofins"),
            ):
                ET.SubElement(item_xml, tag(nome_xml)).text = str(item.get(chave_item) or "")
            ET.SubElement(item_xml, tag("quantidade")).text = f"{Decimal(str(item['quantidade'])):.4f}"
            ET.SubElement(item_xml, tag("valorUnitario")).text = f"{Decimal(str(item['valor_unitario'])):.2f}"
            ET.SubElement(item_xml, tag("valorTotal")).text = f"{Decimal(str(item['valor_total'])):.2f}"

        totais = ET.SubElement(raiz, tag("totais"))
        ET.SubElement(totais, tag("valorProdutos")).text = f"{Decimal(str(rascunho['valor_total'])):.2f}"
        ET.SubElement(totais, tag("valorNota")).text = f"{Decimal(str(rascunho['valor_total'])):.2f}"
        adicionais = ET.SubElement(raiz, tag("informacoesAdicionais"))
        ET.SubElement(adicionais, tag("observacoes")).text = str(rascunho.get("observacoes") or "")
        ET.SubElement(adicionais, tag("aviso")).text = "Rascunho interno. Não transmitido e não válido como documento fiscal."

        ET.indent(raiz, space="  ")
        return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)

    def finalizar_rascunho(self, devolucao_id: int, pasta_saida: str | Path) -> Path:
        rascunho = self.repository.buscar_rascunho(devolucao_id)
        if not rascunho:
            raise ValueError("Rascunho de devolução não localizado.")
        status = str(rascunho.get("status") or "").upper()
        if status == "CANCELADA":
            raise ValueError("Rascunho cancelado não pode ser finalizado.")
        if status == "PRONTO" and str(rascunho.get("xml_rascunho") or "").strip():
            caminho_existente = Path(str(rascunho["xml_rascunho"]))
            if caminho_existente.exists():
                return caminho_existente

        numero = str(rascunho.get("numero_devolucao") or "").strip() or self.repository.proximo_numero_devolucao()
        self.repository.definir_numero(devolucao_id, numero)
        xml = self.gerar_xml_rascunho(devolucao_id)
        pasta = Path(pasta_saida)
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{numero}.xml"
        temporario = destino.with_suffix(destino.suffix + ".tmp")
        temporario.write_bytes(xml)
        temporario.replace(destino)
        hash_xml = sha256(xml).hexdigest()
        self.repository.finalizar_rascunho(devolucao_id, numero, str(destino.resolve()), hash_xml)
        return destino.resolve()



    def calcular_impostos_proporcionais(
        self, devolucao_id: int
    ) -> dict[str, Any]:
        """Calcula tributos da devolução na proporção da quantidade devolvida.

        O cálculo usa exclusivamente os valores existentes no XML original. Quando
        um tributo não foi informado na origem, o resultado permanece zero em vez
        de inventar alíquotas.
        """
        rascunho = self.repository.buscar_rascunho(devolucao_id)
        if not rascunho:
            raise ValueError("Rascunho de devolução não localizado.")
        itens_resultado: list[dict[str, Any]] = []
        totais = {
            "base_icms": Decimal("0"), "valor_icms": Decimal("0"),
            "base_pis": Decimal("0"), "valor_pis": Decimal("0"),
            "base_cofins": Decimal("0"), "valor_cofins": Decimal("0"),
            "base_ipi": Decimal("0"), "valor_ipi": Decimal("0"),
        }
        for item in rascunho.get("itens", []):
            quantidade_original = Decimal(str(item.get("quantidade_original") or 0))
            quantidade_devolvida = Decimal(str(item.get("quantidade") or 0))
            if quantidade_original <= 0:
                raise ValueError(f"{item.get('descricao') or 'Item'}: quantidade original inválida.")
            proporcao = quantidade_devolvida / quantidade_original
            calculado: dict[str, Any] = {
                "item_origem_id": int(item["item_origem_id"]),
                "descricao": str(item.get("descricao") or ""),
                "quantidade_original": float(quantidade_original),
                "quantidade_devolvida": float(quantidade_devolvida),
                "proporcao": float(proporcao),
                "aliquota_icms": float(item.get("aliquota_icms") or 0),
                "aliquota_pis": float(item.get("aliquota_pis") or 0),
                "aliquota_cofins": float(item.get("aliquota_cofins") or 0),
                "aliquota_ipi": float(item.get("aliquota_ipi") or 0),
            }
            for campo in totais:
                valor = (Decimal(str(item.get(campo) or 0)) * proporcao).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                calculado[campo] = float(valor)
                totais[campo] += valor
            itens_resultado.append(calculado)
        return {
            "devolucao_id": int(devolucao_id),
            "itens": itens_resultado,
            "totais": {campo: float(valor.quantize(Decimal("0.01"))) for campo, valor in totais.items()},
        }

    def preparar_documento_fiscal(
        self,
        devolucao_id: int,
        *,
        fiscal_service: FiscalService,
        issuer: Mapping[str, Any],
        document: Mapping[str, Any],
        item_overrides: Mapping[int, Mapping[str, Any]] | None = None,
    ) -> tuple[bytes, str]:
        """Gera a NF-e de devolução oficial em rascunho, sem transmitir.

        A emissão continua opcional. CFOP e tributação devem ser confirmados por item
        antes da geração; o método não inventa regras fiscais ausentes.
        """
        rascunho = self.repository.buscar_rascunho(devolucao_id)
        if not rascunho:
            raise ValueError("Rascunho de devolução não localizado.")
        pendencias = self.validar_rascunho(devolucao_id)
        if pendencias:
            raise ValueError("Rascunho possui pendências fiscais:\n- " + "\n- ".join(pendencias))
        issuer_document = ''.join(ch for ch in str(issuer.get("cnpj") or "") if ch.isdigit())
        original_recipient = ''.join(ch for ch in str(rascunho.get("destinatario_documento") or "") if ch.isdigit())
        if issuer_document and original_recipient and issuer_document != original_recipient:
            raise ValueError("O emitente da devolução deve corresponder ao destinatário da NF-e original.")
        overrides = {int(key): dict(value) for key, value in (item_overrides or {}).items()}
        impostos_por_item = {
            int(item["item_origem_id"]): item
            for item in self.calcular_impostos_proporcionais(devolucao_id)["itens"]
        }
        fiscal_items: list[dict[str, Any]] = []
        for item in rascunho["itens"]:
            item_id = int(item["item_origem_id"])
            override = overrides.get(item_id, {})
            cfop = ''.join(ch for ch in str(override.get("cfop") or "") if ch.isdigit())
            if len(cfop) != 4 or cfop[0] not in "567":
                raise ValueError(f"{item.get('descricao')}: informe um CFOP de devolução de saída válido.")
            impostos = impostos_por_item[item_id]
            fiscal_items.append({
                "code": item.get("codigo") or item_id,
                "description": str(item.get("descricao") or "").upper(),
                "ean": item.get("codigo_barras") or "",
                "ncm": item.get("ncm") or "",
                "cfop": cfop,
                "unit": item.get("unidade") or "UN",
                "quantity": item.get("quantidade") or 0,
                "unit_price": item.get("valor_unitario") or 0,
                "origin": override.get("origin", item.get("origem_mercadoria") or 0),
                "csosn": override.get("csosn", item.get("csosn") or "102"),
                "cst": override.get("cst", item.get("cst_icms") or "40"),
                "icms_rate": override.get("icms_rate", impostos.get("aliquota_icms", 0)),
                "icms_base": impostos.get("base_icms", 0),
                "icms_value": impostos.get("valor_icms", 0),
                "pis_cst": override.get("pis_cst", item.get("cst_pis") or "49"),
                "pis_rate": impostos.get("aliquota_pis", 0),
                "pis_base": impostos.get("base_pis", 0),
                "pis_value": impostos.get("valor_pis", 0),
                "cofins_cst": override.get("cofins_cst", item.get("cst_cofins") or "49"),
                "cofins_rate": impostos.get("aliquota_cofins", 0),
                "cofins_base": impostos.get("base_cofins", 0),
                "cofins_value": impostos.get("valor_cofins", 0),
                "ipi_return_value": impostos.get("valor_ipi", 0),
                "devolution_percent": float(impostos.get("proporcao", 0)) * 100.0,
            })
        fiscal_document = dict(document)
        fiscal_document.update({
            "model": "55",
            "purpose": 4,
            "operation_type": 1,
            "payment_code": "90",
            "strict_tax_profile": True,
            "nature": fiscal_document.get("nature") or "DEVOLUCAO DE MERCADORIA",
            "referenced_access_keys": [str(rascunho["nota_chave"])],
            "additional_info": fiscal_document.get("additional_info") or (
                f"Devolução referente à NF-e {rascunho['nota_chave']}. "
                f"Motivo: {rascunho.get('motivo') or ''}. {rascunho.get('observacoes') or ''}"
            ).strip(),
        })
        recipient = {
            "name": rascunho.get("emitente_nome") or "",
            "document": rascunho.get("emitente_documento") or "",
        }
        return fiscal_service.build_document_xml(
            issuer=issuer, recipient=recipient, items=fiscal_items, document=fiscal_document
        )


    def emitir_devolucao_oficial(
        self,
        devolucao_id: int,
        *,
        fiscal_service: FiscalService,
        issuer: Mapping[str, Any],
        document: Mapping[str, Any],
        item_overrides: Mapping[int, Mapping[str, Any]] | None,
        password: str,
        reservation_id: str = "",
    ) -> dict[str, Any]:
        """Gera, assina e transmite a NF-e de devolução, registrando seu ciclo fiscal."""
        current = self.repository.carregar_estado_fiscal(devolucao_id)
        current_status = str(current.get("status") or "").upper()
        if current_status in {"AUTORIZADA", "AUTORIZADA_PENDENTE_ESTOQUE"}:
            raise ValueError("A devolução já possui NF-e autorizada.")
        if current_status in {"CANCELADA", "CANCELADA_PENDENTE_ESTOQUE"}:
            raise ValueError("Devolução cancelada não pode ser autorizada novamente.")

        attempts = list(current.get("attempts") or [])
        xml, access_key = self.preparar_documento_fiscal(
            devolucao_id, fiscal_service=fiscal_service, issuer=issuer, document=document,
            item_overrides=item_overrides,
        )
        request_hash = sha256(xml).hexdigest()
        attempt = {
            "attempted_at": datetime.now().isoformat(timespec="seconds"),
            "actor": "",
            "access_key": access_key,
            "request_sha256": request_hash,
            "reservation_id": str(reservation_id or ""),
            "result": "ERRO",
            "status_code": "",
            "message": "",
            "protocol": "",
        }
        try:
            response, fiscal_record = fiscal_service.authorize_document(
                xml=xml, access_key=access_key, password=password, model="55",
                reservation_id=reservation_id,
            )
        except Exception as exc:
            attempt["message"] = str(exc)
            attempts.append(attempt)
            state = dict(current)
            state.update({
                "access_key": access_key,
                "attempts": attempts[-100:],
                "events": list(current.get("events") or []),
                "last_error": str(exc),
                "last_request_sha256": request_hash,
            })
            self.repository.salvar_estado_fiscal(devolucao_id, state, status="ERRO_FISCAL")
            raise

        status = "AUTORIZADA" if response.success else "REJEITADA"
        actor_name = str(fiscal_record.get("actor") or "").strip()
        attempt.update({
            "result": status,
            "status_code": str(response.status_code or ""),
            "message": str(response.message or ""),
            "protocol": str(response.protocol or ""),
            "actor": actor_name,
        })
        attempts.append(attempt)
        state = {
            "access_key": access_key,
            "protocol": response.protocol,
            "status_code": response.status_code,
            "message": response.message,
            "actor": actor_name,
            "fiscal_record": dict(fiscal_record),
            "events": list(current.get("events") or []),
            "attempts": attempts[-100:],
            "last_request_sha256": request_hash,
            "last_error": "",
        }
        if not response.success:
            return self.repository.salvar_estado_fiscal(devolucao_id, state, status=status)

        if not actor_name:
            state["last_error"] = (
                "NF-e autorizada, mas o registro fiscal não contém autoria "
                "técnica autenticada para baixar o estoque."
            )
            self.repository.salvar_estado_fiscal(
                devolucao_id, state, status="AUTORIZADA_PENDENTE_ESTOQUE"
            )
            raise RuntimeError(state["last_error"])

        # A autorização fiscal é externa; os efeitos locais ficam explicitamente
        # pendentes até que a baixa de estoque seja concluída com auditoria.
        self.repository.salvar_estado_fiscal(
            devolucao_id, state, status="AUTORIZADA_PENDENTE_ESTOQUE"
        )
        try:
            state["stock_effect"] = self.repository.aplicar_saida_estoque(
                devolucao_id, usuario=actor_name
            )
        except Exception as exc:
            state["last_error"] = f"NF-e autorizada, mas a baixa de estoque falhou: {exc}"
            self.repository.salvar_estado_fiscal(
                devolucao_id, state, status="AUTORIZADA_PENDENTE_ESTOQUE"
            )
            raise RuntimeError(state["last_error"]) from exc
        return self.repository.salvar_estado_fiscal(devolucao_id, state, status="AUTORIZADA")

    def gerar_espelho_fiscal_devolucao(
        self, devolucao_id: int, *, fiscal_service: FiscalService, output_path: str | Path
    ) -> Path:
        state = self.repository.carregar_estado_fiscal(devolucao_id)
        if str(state.get("status") or "").upper() not in {"AUTORIZADA", "AUTORIZADA_PENDENTE_ESTOQUE"}:
            raise ValueError("DANFE só pode ser gerado para devolução autorizada.")
        processed_path = str((state.get("fiscal_record") or {}).get("processed_path") or "").strip()
        if not processed_path or not Path(processed_path).is_file():
            raise ValueError("XML processado da devolução não foi localizado.")
        return fiscal_service.generate_official_danfe_pdf(
            authorized_xml=Path(processed_path).read_bytes(), output_path=output_path
        )

    def cancelar_devolucao_oficial(
        self, devolucao_id: int, *, fiscal_service: FiscalService, password: str,
        justification: str, sequence: int = 1
    ) -> dict[str, Any]:
        state = self.repository.carregar_estado_fiscal(devolucao_id)
        if str(state.get("status") or "").upper() not in {"AUTORIZADA", "AUTORIZADA_PENDENTE_ESTOQUE"}:
            raise ValueError("Somente devolução autorizada pode ser cancelada oficialmente.")
        response, event = fiscal_service.send_event(
            event_type="CANCELAMENTO", access_key=str(state.get("access_key") or ""),
            sequence=int(sequence), password=password,
            protocol=str(state.get("protocol") or ""), justification=justification,
        )
        events = list(state.get("events") or [])
        events.append(dict(event))
        state["events"] = events
        state["last_event_status_code"] = response.status_code
        state["last_event_message"] = response.message
        if not response.success:
            return self.repository.salvar_estado_fiscal(devolucao_id, state, status="AUTORIZADA")
        actor_name = str(event.get("actor") or "").strip()
        if not actor_name:
            state["last_error"] = (
                "Cancelamento fiscal aceito, mas o evento não contém autoria "
                "técnica autenticada para reverter o estoque."
            )
            self.repository.salvar_estado_fiscal(
                devolucao_id, state, status="CANCELADA_PENDENTE_ESTOQUE"
            )
            raise RuntimeError(state["last_error"])
        try:
            state["stock_reversal"] = self.repository.reverter_saida_estoque(
                devolucao_id, usuario=actor_name
            )
        except Exception as exc:
            state["last_error"] = f"Cancelamento fiscal aceito, mas a reversão de estoque falhou: {exc}"
            self.repository.salvar_estado_fiscal(
                devolucao_id, state, status="CANCELADA_PENDENTE_ESTOQUE"
            )
            raise RuntimeError(state["last_error"]) from exc
        return self.repository.salvar_estado_fiscal(devolucao_id, state, status="CANCELADA")

    def recuperar_efeito_estoque_pendente(
        self, devolucao_id: int, *, fiscal_service: FiscalService
    ) -> dict[str, Any]:
        """Conclui, de forma idempotente, o efeito local de uma operação fiscal já aceita."""
        actor_name = fiscal_service.require_authenticated_actor(
            "transmit", operation="recuperar o efeito de estoque de uma devolução fiscal"
        )
        return self._recuperar_efeito_estoque_pendente(
            int(devolucao_id), actor_name=actor_name
        )

    def _recuperar_efeito_estoque_pendente(
        self, devolucao_id: int, *, actor_name: str
    ) -> dict[str, Any]:
        estado = self.repository.carregar_estado_fiscal(int(devolucao_id))
        status = str(estado.get("status") or "").strip().upper()
        if status == "AUTORIZADA_PENDENTE_ESTOQUE":
            efeito = self.repository.aplicar_saida_estoque(int(devolucao_id), usuario=actor_name)
            estado["stock_effect"] = efeito
            estado["last_error"] = ""
            estado.setdefault("local_recovery", []).append({
                "action": "APLICAR_ESTOQUE",
                "actor": actor_name,
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "result": "OK",
            })
            return self.repository.salvar_estado_fiscal(
                int(devolucao_id), estado, status="AUTORIZADA"
            )
        if status == "CANCELADA_PENDENTE_ESTOQUE":
            efeito = self.repository.reverter_saida_estoque(int(devolucao_id), usuario=actor_name)
            estado["stock_reversal"] = efeito
            estado["last_error"] = ""
            estado.setdefault("local_recovery", []).append({
                "action": "REVERTER_ESTOQUE",
                "actor": actor_name,
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "result": "OK",
            })
            return self.repository.salvar_estado_fiscal(
                int(devolucao_id), estado, status="CANCELADA"
            )
        if status in {"AUTORIZADA", "CANCELADA"}:
            return estado
        raise ValueError("A devolução não possui efeito de estoque pendente para recuperação.")

    def recuperar_pendencias_estoque(
        self, *, fiscal_service: FiscalService, limite: int = 200
    ) -> dict[str, Any]:
        """Tenta concluir todas as pendências locais sem interromper o lote no primeiro erro."""
        actor_name = fiscal_service.require_authenticated_actor(
            "transmit", operation="recuperar efeitos de estoque de devoluções fiscais"
        )
        concluidas: list[int] = []
        falhas: list[dict[str, Any]] = []
        for item in self.repository.listar_pendencias_estoque(limite=limite):
            devolucao_id = int(item["id"])
            try:
                self._recuperar_efeito_estoque_pendente(
                    devolucao_id, actor_name=actor_name
                )
                concluidas.append(devolucao_id)
            except Exception as exc:
                estado = self.repository.carregar_estado_fiscal(devolucao_id)
                estado["last_error"] = str(exc)
                estado.setdefault("local_recovery", []).append({
                    "action": "RECUPERAR_ESTOQUE",
                    "actor": actor_name,
                    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "result": "ERRO",
                    "message": str(exc),
                })
                self.repository.salvar_estado_fiscal(
                    devolucao_id, estado, status=str(item.get("status") or "")
                )
                falhas.append({"devolucao_id": devolucao_id, "erro": str(exc)})
        return {"concluidas": concluidas, "falhas": falhas}

    def listar_historico(self, *, limite: int = 200) -> list[dict[str, Any]]:
        return self.repository.listar_devolucoes(limite=limite)

    def estado_fiscal(self, devolucao_id: int) -> dict[str, Any]:
        return self.repository.carregar_estado_fiscal(devolucao_id)

    def cancelar_rascunho(self, devolucao_id: int) -> bool:
        return self.repository.cancelar_rascunho(devolucao_id)
