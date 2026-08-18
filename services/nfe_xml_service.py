from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class NFeItem:
    codigo: str
    descricao: str
    quantidade: float
    unidade: str
    valor_unitario: float
    ncm: str = ""
    cfop: str = ""
    cest: str = ""
    codigo_barras: str = ""
    item_numero: int = 0
    valor_total: float = 0.0
    origem_mercadoria: str = ""
    cst_icms: str = ""
    csosn: str = ""
    cst_pis: str = ""
    cst_cofins: str = ""
    base_icms: float = 0.0
    aliquota_icms: float = 0.0
    valor_icms: float = 0.0
    base_pis: float = 0.0
    aliquota_pis: float = 0.0
    valor_pis: float = 0.0
    base_cofins: float = 0.0
    aliquota_cofins: float = 0.0
    valor_cofins: float = 0.0
    base_ipi: float = 0.0
    aliquota_ipi: float = 0.0
    valor_ipi: float = 0.0
    ibs_cbs_cst: str = ""
    ibs_cbs_class: str = ""
    ibs_cbs_base: float = 0.0
    ibs_uf_rate: float = 0.0
    ibs_city_rate: float = 0.0
    cbs_rate: float = 0.0

    def preco_por_margem(self, margem_percentual: float) -> float:
        margem = float(margem_percentual)
        if margem < 0:
            raise ValueError("A margem não pode ser negativa.")
        return round(self.valor_unitario * (1 + margem / 100), 2)


@dataclass(frozen=True)
class NFeDocument:
    chave: str
    numero: str
    fornecedor: str
    cnpj: str
    itens: tuple[NFeItem, ...]
    destinatario: str = ""
    destinatario_documento: str = ""
    data_emissao: str = ""
    serie: str = ""
    modelo: str = ""
    valor_total: float = 0.0


class NFeXMLService:
    """Lê NF-e com segurança e gera relatórios sem alterar o banco."""

    @staticmethod
    def _texto(elemento, caminho: str, padrao: str = "") -> str:
        encontrado = elemento.find(caminho) if elemento is not None else None
        return (encontrado.text or "").strip() if encontrado is not None else padrao

    def ler(self, caminho: str | Path) -> NFeDocument:
        arquivo = Path(caminho)
        if arquivo.suffix.lower() != ".xml":
            raise ValueError("Selecione um arquivo XML de NF-e.")
        try:
            raiz = ET.parse(arquivo).getroot()
        except (ET.ParseError, OSError) as exc:
            raise ValueError(f"Não foi possível ler o XML: {exc}") from exc

        for elemento in raiz.iter():
            if "}" in elemento.tag:
                elemento.tag = elemento.tag.split("}", 1)[1]

        inf_nfe = raiz.find(".//infNFe")
        if inf_nfe is None:
            raise ValueError("O arquivo não contém uma NF-e reconhecida (infNFe ausente).")

        emit = inf_nfe.find("emit")
        dest = inf_nfe.find("dest")
        ide = inf_nfe.find("ide")
        total = inf_nfe.find("total/ICMSTot")
        fornecedor = self._texto(emit, "xNome")
        cnpj = self._texto(emit, "CNPJ") or self._texto(emit, "CPF")
        destinatario = self._texto(dest, "xNome")
        destinatario_documento = self._texto(dest, "CNPJ") or self._texto(dest, "CPF")
        numero = self._texto(ide, "nNF")
        data_emissao = self._texto(ide, "dhEmi") or self._texto(ide, "dEmi")
        serie = self._texto(ide, "serie")
        modelo = self._texto(ide, "mod")
        chave = (inf_nfe.attrib.get("Id") or "").removeprefix("NFe")
        try:
            valor_total = float(self._texto(total, "vNF", "0").replace(",", "."))
        except ValueError:
            valor_total = 0.0

        itens: list[NFeItem] = []
        for indice, det in enumerate(inf_nfe.findall("det"), start=1):
            prod = det.find("prod")
            if prod is None:
                continue
            codigo = self._texto(prod, "cProd")
            descricao = self._texto(prod, "xProd")
            if not codigo and not descricao:
                continue
            try:
                quantidade = float(self._texto(prod, "qCom", "0").replace(",", "."))
                valor_unitario = float(self._texto(prod, "vUnCom", "0").replace(",", "."))
                valor_item = float(self._texto(prod, "vProd", "0").replace(",", "."))
            except ValueError as exc:
                raise ValueError("A NF-e contém quantidade ou valor unitário inválido.") from exc

            imposto = det.find("imposto")
            icms = imposto.find("ICMS") if imposto is not None else None
            icms_regra = next(iter(icms), None) if icms is not None else None
            pis = imposto.find("PIS") if imposto is not None else None
            pis_regra = next(iter(pis), None) if pis is not None else None
            cofins = imposto.find("COFINS") if imposto is not None else None
            cofins_regra = next(iter(cofins), None) if cofins is not None else None
            ibs_cbs = imposto.find("IBSCBS") if imposto is not None else None
            ibs_cbs_group = ibs_cbs.find("gIBSCBS") if ibs_cbs is not None else None
            try:
                item_numero = int(det.attrib.get("nItem") or indice)
            except (TypeError, ValueError):
                item_numero = indice
            itens.append(NFeItem(
                codigo=codigo,
                descricao=descricao,
                quantidade=quantidade,
                unidade=self._texto(prod, "uCom"),
                valor_unitario=valor_unitario,
                ncm=self._texto(prod, "NCM"),
                cfop=self._texto(prod, "CFOP"),
                cest=self._texto(prod, "CEST"),
                codigo_barras=self._texto(prod, "cEAN"),
                item_numero=item_numero,
                valor_total=valor_item,
                origem_mercadoria=self._texto(icms_regra, "orig"),
                cst_icms=self._texto(icms_regra, "CST"),
                csosn=self._texto(icms_regra, "CSOSN"),
                cst_pis=self._texto(pis_regra, "CST"),
                cst_cofins=self._texto(cofins_regra, "CST"),
                ibs_cbs_cst=self._texto(ibs_cbs, "CST"),
                ibs_cbs_class=self._texto(ibs_cbs, "cClassTrib"),
                ibs_cbs_base=float(self._texto(ibs_cbs_group, "vBC", "0").replace(",", ".")),
                ibs_uf_rate=float(self._texto(ibs_cbs_group, "gIBSUF/pIBSUF", "0").replace(",", ".")),
                ibs_city_rate=float(self._texto(ibs_cbs_group, "gIBSMun/pIBSMun", "0").replace(",", ".")),
                cbs_rate=float(self._texto(ibs_cbs_group, "gCBS/pCBS", "0").replace(",", ".")),
            ))

        if not itens:
            raise ValueError("Nenhum produto foi encontrado no XML.")
        return NFeDocument(
            chave=chave,
            numero=numero,
            fornecedor=fornecedor,
            cnpj=cnpj,
            itens=tuple(itens),
            destinatario=destinatario,
            destinatario_documento=destinatario_documento,
            data_emissao=data_emissao,
            serie=serie,
            modelo=modelo,
            valor_total=valor_total,
        )

    @staticmethod
    def salvar_relatorio(documento: NFeDocument, resultados: list[dict], pasta: str | Path) -> Path:
        destino = Path(pasta)
        destino.mkdir(parents=True, exist_ok=True)
        identificador = documento.numero or documento.chave[-12:] or datetime.now().strftime("%Y%m%d_%H%M%S")
        arquivo = destino / f"importacao_nfe_{identificador}_{datetime.now():%Y%m%d_%H%M%S}.json"
        temporario = arquivo.with_suffix(".tmp")
        conteudo = {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "nfe": {
                "chave": documento.chave,
                "numero": documento.numero,
                "fornecedor": documento.fornecedor,
                "cnpj": documento.cnpj,
                "destinatario": documento.destinatario,
                "destinatario_documento": documento.destinatario_documento,
                "data_emissao": documento.data_emissao,
                "serie": documento.serie,
                "modelo": documento.modelo,
                "valor_total": documento.valor_total,
            },
            "resultados": resultados,
        }
        temporario.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(arquivo)
        return arquivo
