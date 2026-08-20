from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class FiscalProductProfile:
    """Valida a ficha fiscal de venda sem inferir tributação da empresa."""

    SIMPLE_CSOSN = {"102", "103", "201", "202", "203", "300", "400", "500"}
    NORMAL_ICMS_CST = {"00", "40", "41", "50", "60"}
    CONTRIBUTION_TAXED = {"01", "02"}
    CONTRIBUTION_UNTAXED = {"04", "05", "06", "07", "08", "09"}
    CONTRIBUTION_OTHER = {
        "49", "50", "51", "52", "53", "54", "55", "56", "60", "61", "62", "63",
        "64", "65", "66", "67", "70", "71", "72", "73", "74", "75", "98", "99",
    }
    IPI_TAXED = {"50", "99"}
    IPI_UNTAXED = {"51", "52", "53", "54", "55"}

    @staticmethod
    def digits(value: Any) -> str:
        return "".join(
            character for character in str("" if value is None else value) if character.isdigit()
        )

    @staticmethod
    def rate(value: Any, label: str) -> str:
        text = str(value or "0").strip().replace(",", ".") or "0"
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"{label} deve ser numérica.") from exc
        if number < 0 or number > 100:
            raise ValueError(f"{label} deve ficar entre 0 e 100%.")
        return format(number.normalize(), "f")

    @classmethod
    def normalize(cls, values: Mapping[str, Any]) -> dict[str, str]:
        result = {
            "ncm": cls.digits(values.get("ncm")),
            "cest": cls.digits(values.get("cest")),
            "cfop": cls.digits(values.get("cfop")),
            "fiscal_origin": cls.digits(values.get("fiscal_origin")),
            "fiscal_csosn": cls.digits(values.get("fiscal_csosn")),
            "fiscal_icms_cst": cls.digits(values.get("fiscal_icms_cst")),
            "fiscal_pis_cst": cls.digits(values.get("fiscal_pis_cst")),
            "fiscal_cofins_cst": cls.digits(values.get("fiscal_cofins_cst")),
            "fiscal_ipi_cst": cls.digits(values.get("fiscal_ipi_cst")),
            "fiscal_ipi_enq": cls.digits(values.get("fiscal_ipi_enq")),
            "fiscal_profile_source": str(values.get("fiscal_profile_source") or "").strip().upper(),
            "ibs_cbs_cst": cls.digits(values.get("ibs_cbs_cst")),
            "ibs_cbs_class": cls.digits(values.get("ibs_cbs_class")),
        }
        if result["ncm"] and (len(result["ncm"]) != 8 or result["ncm"] == "00000000"):
            raise ValueError("NCM deve possuir 8 dígitos e não pode ser genérico.")
        if result["cest"] and len(result["cest"]) != 7:
            raise ValueError("CEST deve possuir 7 dígitos.")
        if result["cfop"] and (len(result["cfop"]) != 4 or result["cfop"][0] not in "123567"):
            raise ValueError("CFOP deve possuir 4 dígitos válidos.")
        if result["fiscal_origin"] and result["fiscal_origin"] not in set("012345678"):
            raise ValueError("Origem da mercadoria deve ficar entre 0 e 8.")
        if result["fiscal_csosn"] and result["fiscal_csosn"] not in cls.SIMPLE_CSOSN:
            raise ValueError("CSOSN suportado deve ser 102, 103, 201, 202, 203, 300, 400 ou 500.")
        if result["fiscal_icms_cst"] and result["fiscal_icms_cst"] not in cls.NORMAL_ICMS_CST:
            raise ValueError("CST de ICMS suportado deve ser 00, 40, 41, 50 ou 60.")
        contribution_codes = cls.CONTRIBUTION_TAXED | cls.CONTRIBUTION_UNTAXED | cls.CONTRIBUTION_OTHER
        for field, label in (("fiscal_pis_cst", "CST PIS"), ("fiscal_cofins_cst", "CST COFINS")):
            if result[field] and result[field] not in contribution_codes:
                raise ValueError(f"{label} não é suportado pela ficha fiscal.")
        if result["fiscal_ipi_cst"] and result["fiscal_ipi_cst"] not in cls.IPI_TAXED | cls.IPI_UNTAXED:
            raise ValueError("CST IPI de saída deve ser 50, 51, 52, 53, 54, 55 ou 99.")
        if result["fiscal_ipi_cst"] and len(result["fiscal_ipi_enq"]) != 3:
            raise ValueError("IPI configurado exige código de enquadramento com 3 dígitos.")
        if result["ibs_cbs_cst"] and len(result["ibs_cbs_cst"]) != 3:
            raise ValueError("CST IBS/CBS deve possuir 3 dígitos.")
        if result["ibs_cbs_class"] and len(result["ibs_cbs_class"]) != 6:
            raise ValueError("Classificação IBS/CBS deve possuir 6 dígitos.")
        for field, label in (
            ("fiscal_icms_rate", "Alíquota de ICMS"),
            ("fiscal_pis_rate", "Alíquota de PIS"),
            ("fiscal_cofins_rate", "Alíquota de COFINS"),
            ("fiscal_ipi_rate", "Alíquota de IPI"),
            ("ibs_uf_rate", "Alíquota IBS estadual"),
            ("ibs_city_rate", "Alíquota IBS municipal"),
            ("cbs_rate", "Alíquota CBS"),
        ):
            result[field] = cls.rate(values.get(field), label)
        return result

    @classmethod
    def validate_for_regime(cls, values: Mapping[str, Any], *, crt: int, require_rtc: bool) -> dict[str, str]:
        profile = cls.normalize(values)
        required = [field for field in ("ncm", "cfop", "fiscal_origin", "fiscal_pis_cst", "fiscal_cofins_cst") if not profile[field]]
        if crt in {1, 2, 4} and not profile["fiscal_csosn"]:
            required.append("fiscal_csosn")
        if crt == 3 and not profile["fiscal_icms_cst"]:
            required.append("fiscal_icms_cst")
        if (
            profile["fiscal_csosn"] in {"201", "202", "203", "500"}
            or profile["fiscal_icms_cst"] == "60"
        ) and not profile["cest"]:
            required.append("cest")
        if require_rtc:
            if not profile["ibs_cbs_cst"]:
                required.append("ibs_cbs_cst")
            if not profile["ibs_cbs_class"]:
                required.append("ibs_cbs_class")
        if required:
            labels = {
                "ncm": "NCM", "cfop": "CFOP", "fiscal_origin": "origem",
                "fiscal_pis_cst": "CST PIS", "fiscal_cofins_cst": "CST COFINS",
                "fiscal_csosn": "CSOSN", "fiscal_icms_cst": "CST ICMS",
                "cest": "CEST para mercadoria com substituição tributária",
                "ibs_cbs_cst": "CST IBS/CBS", "ibs_cbs_class": "classificação IBS/CBS",
            }
            raise ValueError("ficha fiscal incompleta — " + ", ".join(labels[field] for field in required) + ".")
        return profile
