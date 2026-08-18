from __future__ import annotations

from typing import Any


# O catálogo separa a topologia nacional da implementação do emissor. Uma UF só
# recebe URLs quando elas foram conferidas e cobertas por testes; a ausência de
# URL é um bloqueio de segurança, nunca um convite para adivinhar o destino.
STATE_CODES = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15",
    "AP": "16", "TO": "17", "MA": "21", "PI": "22", "CE": "23",
    "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28",
    "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35",
    "PR": "41", "SC": "42", "RS": "43", "MS": "50", "MT": "51",
    "GO": "52", "DF": "53",
}

_SVRS_NFE = {
    "AC", "AL", "AP", "CE", "DF", "ES", "PA", "PB", "PI", "RJ",
    "RN", "RO", "RR", "SC", "SE", "TO",
}
_OWN_NFE = {"AM", "BA", "GO", "MG", "MS", "MT", "PE", "PR", "RS", "SP"}


def _authorizer(uf: str) -> str:
    if uf in _SVRS_NFE:
        return "SVRS"
    if uf == "MA":
        return "SVAN"
    if uf in _OWN_NFE:
        return uf
    raise ValueError(f"UF sem autorizador NF-e catalogado: {uf}")


BA_ENDPOINTS = {
    "55": {
        "HOMOLOGACAO": {
            "autorizacao": "https://hnfe.sefaz.ba.gov.br/webservices/NFeAutorizacao4/NFeAutorizacao4.asmx",
            "recibo": "https://hnfe.sefaz.ba.gov.br/webservices/NFeRetAutorizacao4/NFeRetAutorizacao4.asmx",
            "inutilizacao": "https://hnfe.sefaz.ba.gov.br/webservices/NFeInutilizacao4/NFeInutilizacao4.asmx",
            "status": "https://hnfe.sefaz.ba.gov.br/webservices/NFeStatusServico4/NFeStatusServico4.asmx",
            "evento": "https://hnfe.sefaz.ba.gov.br/webservices/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx",
            "consulta": "https://hnfe.sefaz.ba.gov.br/webservices/NFeConsultaProtocolo4/NFeConsultaProtocolo4.asmx",
            "cadastro": "https://hnfe.sefaz.ba.gov.br/webservices/CadConsultaCadastro4/CadConsultaCadastro4.asmx",
        },
        "PRODUCAO": {
            "autorizacao": "https://nfe.sefaz.ba.gov.br/webservices/NFeAutorizacao4/NFeAutorizacao4.asmx",
            "recibo": "https://nfe.sefaz.ba.gov.br/webservices/NFeRetAutorizacao4/NFeRetAutorizacao4.asmx",
            "inutilizacao": "https://nfe.sefaz.ba.gov.br/webservices/NFeInutilizacao4/NFeInutilizacao4.asmx",
            "status": "https://nfe.sefaz.ba.gov.br/webservices/NFeStatusServico4/NFeStatusServico4.asmx",
            "evento": "https://nfe.sefaz.ba.gov.br/webservices/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx",
            "consulta": "https://nfe.sefaz.ba.gov.br/webservices/NFeConsultaProtocolo4/NFeConsultaProtocolo4.asmx",
            "cadastro": "https://nfe.sefaz.ba.gov.br/webservices/CadConsultaCadastro4/CadConsultaCadastro4.asmx",
        },
    },
    "65": {
        "HOMOLOGACAO": {
            "autorizacao": "https://nfce-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
            "recibo": "https://nfce-homologacao.svrs.rs.gov.br/ws/NFeRetAutorizacao/NFeRetAutorizacao4.asmx",
            "inutilizacao": "https://nfce-homologacao.svrs.rs.gov.br/ws/nfeinutilizacao/nfeinutilizacao4.asmx",
            "status": "https://nfce-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
            "evento": "https://nfce-homologacao.svrs.rs.gov.br/ws/recepcaoevento/recepcaoevento4.asmx",
            "consulta": "https://nfce-homologacao.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx",
            "cadastro": "https://nfce-homologacao.svrs.rs.gov.br/ws/cadconsultacadastro/cadconsultacadastro2.asmx",
        },
        "PRODUCAO": {
            "autorizacao": "https://nfce.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
            "recibo": "https://nfce.svrs.rs.gov.br/ws/NFeRetAutorizacao/NFeRetAutorizacao4.asmx",
            "inutilizacao": "https://nfce.svrs.rs.gov.br/ws/nfeinutilizacao/nfeinutilizacao4.asmx",
            "status": "https://nfce.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
            "evento": "https://nfce.svrs.rs.gov.br/ws/recepcaoevento/recepcaoevento4.asmx",
            "consulta": "https://nfce.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx",
            "cadastro": "https://nfce.svrs.rs.gov.br/ws/cadconsultacadastro/cadconsultacadastro2.asmx",
        },
    },
}

BA_NFCE_URLS = {
    "HOMOLOGACAO": {
        "qr_code": "http://hnfe.sefaz.ba.gov.br/servicos/nfce/qrcode.aspx",
        "consulta_chave": "http://hinternet.sefaz.ba.gov.br/nfce/consulta",
    },
    "PRODUCAO": {
        "qr_code": "https://nfe.sefaz.ba.gov.br/servicos/nfce/qrcode.aspx",
        "consulta_chave": "https://www.sefaz.ba.gov.br/nfce/consulta",
    },
}


FISCAL_STATE_PROFILES: dict[str, dict[str, Any]] = {
    uf: {
        "uf": uf,
        "state_code": code,
        "nfe_authorizer": _authorizer(uf),
        "status": "VALIDADO" if uf == "BA" else "PENDENTE_HOMOLOGACAO",
        "endpoints": BA_ENDPOINTS if uf == "BA" else {},
        "nfce_urls": BA_NFCE_URLS if uf == "BA" else {},
    }
    for uf, code in STATE_CODES.items()
}


def state_profile(uf: str) -> dict[str, Any]:
    normalized = str(uf or "").strip().upper()
    profile = FISCAL_STATE_PROFILES.get(normalized)
    if profile is None:
        raise ValueError("UF fiscal inválida.")
    return profile
