from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class CompanyXMLParticipant:
    role: str
    legal_name: str
    trade_name: str = ""
    document: str = ""
    state_registration: str = ""
    street: str = ""
    number: str = ""
    complement: str = ""
    district: str = ""
    city_code: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    phone: str = ""
    email: str = ""


@dataclass(frozen=True)
class CompanyXMLReview:
    source_path: str
    model: str
    access_key: str
    authorization_status: str
    participants: tuple[CompanyXMLParticipant, ...]
    selected_role: str = ""

    @property
    def selected(self) -> CompanyXMLParticipant | None:
        return next((item for item in self.participants if item.role == self.selected_role), None)


class CompanyXMLImportService:
    """Lê XML fiscal local autorizado e produz evidência; nunca persiste ou transmite."""

    MAX_BYTES = 10 * 1024 * 1024
    SUPPORTED_MODELS = {"55", "65"}

    @staticmethod
    def _digits(value: str) -> str:
        return re.sub(r"\D", "", str(value or ""))

    @staticmethod
    def _text(parent, path: str) -> str:
        node = parent.find(path) if parent is not None else None
        return (node.text or "").strip() if node is not None else ""

    def inspect(self, path: str | Path, *, known_documents: tuple[str, ...] = ()) -> CompanyXMLReview:
        source = Path(path)
        if source.suffix.lower() != ".xml":
            raise ValueError("Selecione um arquivo XML fiscal.")
        try:
            raw = source.read_bytes()
        except OSError as exc:
            raise ValueError("Não foi possível ler o XML selecionado.") from exc
        if not raw or len(raw) > self.MAX_BYTES:
            raise ValueError("O XML está vazio ou excede o limite seguro de 10 MB.")
        lowered = raw.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError("XML com DTD ou entidades não é aceito.")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ValueError("XML inválido ou adulterado: estrutura não reconhecida.") from exc
        for node in root.iter():
            if "}" in node.tag:
                node.tag = node.tag.split("}", 1)[1]
        inf_nfe = root.find(".//infNFe")
        protocol = root.find(".//protNFe/infProt")
        if inf_nfe is None or protocol is None:
            raise ValueError("O arquivo não contém uma NF-e/NFC-e processada com protocolo.")
        model = self._text(inf_nfe.find("ide"), "mod")
        status = self._text(protocol, "cStat")
        key = self._text(protocol, "chNFe") or (inf_nfe.attrib.get("Id") or "").removeprefix("NFe")
        if model not in self.SUPPORTED_MODELS:
            raise ValueError(f"Modelo fiscal {model or 'ausente'} não é aceito para este cadastro.")
        if status != "100" or not re.fullmatch(r"\d{44}", key):
            raise ValueError("O XML não comprova autorização válida (cStat 100 e chave de 44 dígitos).")
        participants = tuple(filter(None, (
            self._participant(inf_nfe.find("emit"), "emitente", "enderEmit"),
            self._participant(inf_nfe.find("dest"), "destinatário", "enderDest"),
        )))
        if not participants:
            raise ValueError("O XML não possui emitente ou destinatário identificável.")
        known = {self._digits(item) for item in known_documents if self._digits(item)}
        matches = [item for item in participants if self._digits(item.document) in known]
        selected = matches[0].role if len(matches) == 1 else ""
        return CompanyXMLReview(str(source.resolve()), model, key, status, participants, selected)

    def select(
        self, review: CompanyXMLReview, role: str, *, known_documents: tuple[str, ...] = (),
    ) -> CompanyXMLReview:
        selected = next((item for item in review.participants if item.role == role), None)
        if selected is None:
            raise ValueError("Escolha o emitente ou o destinatário mostrado no XML.")
        known = {self._digits(item) for item in known_documents if self._digits(item)}
        if known and self._digits(selected.document) not in known:
            raise ValueError(
                "O CNPJ/CPF escolhido é incompatível com a empresa, licença ou certificado já configurado."
            )
        return CompanyXMLReview(
            review.source_path, review.model, review.access_key,
            review.authorization_status, review.participants, selected.role,
        )

    def _participant(self, node, role: str, address_tag: str) -> CompanyXMLParticipant | None:
        document = self._text(node, "CNPJ") or self._text(node, "CPF")
        name = self._text(node, "xNome")
        if not document and not name:
            return None
        address = node.find(address_tag) if node is not None else None
        return CompanyXMLParticipant(
            role=role, legal_name=name, trade_name=self._text(node, "xFant"),
            document=document, state_registration=self._text(node, "IE"),
            street=self._text(address, "xLgr"), number=self._text(address, "nro"),
            complement=self._text(address, "xCpl"), district=self._text(address, "xBairro"),
            city_code=self._text(address, "cMun"), city=self._text(address, "xMun"),
            state=self._text(address, "UF"), postal_code=self._text(address, "CEP"),
            phone=self._text(address, "fone"), email=self._text(node, "email"),
        )
