from __future__ import annotations

from dataclasses import dataclass
import logging
import sqlite3
from typing import Any, Callable

from helpers import cached_instance
from repositories import ClienteRepository, DashboardRepository
from services import (
    AdminAuditService,
    CashService,
    EmittedDocumentService,
    MovementService,
    PDFDocumentService,
    PrintingService,
    ReceiptService,
)


@dataclass(frozen=True)
class LegacyBackendContext:
    database_manager: Any
    connect: Callable[..., Any]
    get_config: Callable[[str], Any]
    pdf_dir: str
    product_application_service: Any
    report_service: Any


class LegacyBackendAdapterMixin:
    backend_context: LegacyBackendContext

    def _repositorio_dashboard(self):
        return cached_instance(
            self,
            "_dashboard_repository",
            lambda: DashboardRepository(self.backend_context.database_manager),
        )

    def _servico_caixa(self):
        # Operações do Caixa partem da thread de interface. Um lock externo não
        # pode congelar a janela por todo o timeout geral de 30 segundos.
        return cached_instance(
            self,
            "_cash_service",
            lambda: CashService(lambda: self.backend_context.connect(timeout=3)),
        )

    def _resumo_caixa_dia(self, data_br=None):
        return self._servico_caixa().daily_summary(data_br)

    def _servico_documentos_emitidos(self):
        return cached_instance(
            self,
            "_documentos_emitidos_service",
            lambda: EmittedDocumentService(
                self.backend_context.connect,
                logger=logging.getLogger("NabiCode.DocumentosEmitidos"),
            ),
        )

    def registrar_documento_emitido(self, movimentacao_id, categoria, caminho, numero=""):
        try:
            return self._servico_documentos_emitidos().register(
                movimentacao_id,
                categoria,
                caminho,
                numero,
            )
        except Exception as exc:
            logging.getLogger("NabiCode.DocumentosEmitidos").exception(
                "Não foi possível registrar o PDF emitido da movimentação %s",
                movimentacao_id,
            )
            self.mostrar_notificacao(
                "Documento não registrado",
                f"O PDF foi gerado, mas não pôde ser registrado no histórico: {exc}",
                nivel="warning",
            )
            return None

    def _servico_movimentacoes(self):
        return cached_instance(
            self,
            "_movement_service",
            lambda: MovementService(self.backend_context.connect),
        )

    def _categorias_ativas(self):
        return [
            (item.item_id, item.nome)
            for item in self.backend_context.product_application_service.listar_categorias()
        ]

    def _auxiliares_ativos(self, tipo):
        return [
            (item.item_id, item.nome)
            for item in self.backend_context.product_application_service.listar_auxiliares(tipo)
        ]

    @staticmethod
    def _normalizar_busca(texto):
        return ClienteRepository._normalize_search(texto)

    def _ordenar_clientes_busca(self, resultados, termo):
        return ClienteRepository.sort_sales_rows(resultados, termo)

    def _servico_impressao(self):
        return cached_instance(
            self,
            "_printing_service",
            lambda: PrintingService(get_config=self.backend_context.get_config),
        )

    def listar_impressoras_windows(self):
        return self._servico_impressao().list_printers()

    def impressora_disponivel(self, nome):
        return self._servico_impressao().is_available(nome)

    def imprimir_texto_windows(self, texto, impressora="Padrão do Sistema", titulo="NabiCode"):
        return self._servico_impressao().print_raw_text(texto, impressora, titulo)

    def imprimir_cupom_venda_80mm(
        self,
        cliente_id,
        itens,
        total,
        tipo,
        documento_id=None,
    ):
        categoria = "entrega" if str(tipo or "").strip().upper() == "ENTREGA" else "recibo"
        impressora = self.backend_context.get_config(
            "impressora_entrega" if categoria == "entrega" else "impressora_recibo"
        ) or "Padrão do Sistema"
        texto = self.texto_comprovante_venda(
            cliente_id,
            itens,
            total,
            tipo,
            documento_id,
        )
        return self._servico_impressao().print_text(
            texto,
            output_format=PrintingService.OFFICIAL_THERMAL_FORMAT,
            printer=impressora,
            title="Cupom de entrega" if categoria == "entrega" else "Comprovante de venda",
        )

    def _servico_comprovantes(self):
        return cached_instance(
            self,
            "_receipt_service",
            lambda: ReceiptService(
                self.backend_context.database_manager,
                config_getter=self.backend_context.get_config,
            ),
        )

    def texto_comprovante_venda(self, cliente_id, itens, total, tipo, documento_id=None):
        return self._servico_comprovantes().build_sale_text(
            cliente_id,
            itens,
            total,
            tipo,
            sale_id=documento_id,
        )

    def texto_recibo_pagamento_cliente(
        self,
        mov_id,
        alocacoes,
        saldo_anterior=None,
        novo_saldo=None,
    ):
        return self._servico_comprovantes().build_payment_text(
            mov_id,
            alocacoes,
            balance_before=saldo_anterior,
            balance_after=novo_saldo,
        )

    def formato_impressao(self, categoria):
        return self._servico_impressao().output_format(categoria)

    def imprimir_texto_a4_windows(self, texto, impressora="Padrão do Sistema", titulo="Documento"):
        return self._servico_impressao().print_a4_text(texto, impressora, titulo)

    def _servico_pdf_documentos(self):
        return cached_instance(
            self,
            "_pdf_document_service",
            lambda: PDFDocumentService(
                connection_factory=self.backend_context.connect,
                config_getter=self.backend_context.get_config,
                pdf_dir=self.backend_context.pdf_dir,
                document_registrar=self.registrar_documento_emitido,
                logger=logging.getLogger(__name__),
            ),
        )

    def _cfg_bool(self, chave, padrao=True):
        return self._servico_pdf_documentos().config_bool(chave, padrao)

    def _modelo_documento(self, categoria):
        return self._servico_pdf_documentos().document_model(categoria)

    def _dados_loja_impressao(self):
        return self._servico_pdf_documentos().store_data()

    def gerar_pdf_venda(self, cliente_id, itens, total, tipo, documento_id=None, destino=None):
        return self._servico_pdf_documentos().generate_sale(
            cliente_id,
            itens,
            total,
            tipo,
            document_id=documento_id,
            destination=destino,
        )

    def gerar_pdf_movimentacao(self, mov_id, destino=None):
        return self._servico_pdf_documentos().generate_movement(mov_id, destination=destino)

    def gerar_pdf_pagamento_cliente(
        self,
        mov_id,
        alocacoes,
        destino=None,
        saldo_anterior=None,
        novo_saldo=None,
    ):
        return self._servico_pdf_documentos().generate_customer_payment(
            mov_id,
            allocations=alocacoes,
            destination=destino,
            balance_before=saldo_anterior,
            balance_after=novo_saldo,
        )

    def gerar_pdf_fechamento(
        self,
        resumo,
        valor_contado=None,
        responsavel="",
        observacao="",
        destino=None,
    ):
        return self._servico_pdf_documentos().generate_closing(
            resumo,
            counted_value=valor_contado,
            responsible=responsavel,
            observation=observacao,
            destination=destino,
        )

    def _usuario_financeiro(self):
        session = getattr(self.security, "session", None)
        username = getattr(getattr(session, "user", None), "username", None) if session else None
        return str(username or "Sistema")

    @staticmethod
    def _modulo_do_relatorio(report_id):
        return {
            "vendas": "vendas",
            "produtos": "produtos",
            "clientes": "clientes",
            "financeiro": "financeiro",
            "compras": "compras",
            "nfe": "xml",
            "estoque": "estoque",
        }.get(str(report_id).strip().lower(), "relatorios")

    def _relatorios_permitidos(self):
        return {
            report_id: title
            for report_id, title in self.backend_context.report_service.available_reports().items()
            if self.security.require(self._modulo_do_relatorio(report_id), "view")
        }

    def _usuario_relatorios(self):
        session = getattr(getattr(self, "security", None), "session", None)
        return session.user.username if session else "Sistema"

    def _servico_auditoria_admin(self):
        return cached_instance(
            self,
            "_admin_audit_service",
            lambda: AdminAuditService(
                self.backend_context.connect,
                logging.getLogger("nabicode.security_audit"),
            ),
        )

    def _registrar_acesso_admin(self, sucesso, detalhes):
        try:
            self._servico_auditoria_admin().record_admin_access(bool(sucesso), detalhes)
        except (sqlite3.Error, ValueError) as exc:
            logging.getLogger("nabicode.security_audit").error(
                "Não foi possível registrar o acesso administrativo: %s",
                exc,
            )
