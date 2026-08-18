import os
import sqlite3
import urllib.request
import urllib.parse
import sys
import platform
import subprocess
import re
import threading
import socket
from pathlib import Path
from datetime import datetime, timedelta
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk, filedialog, simpledialog
import webbrowser
import logging
from time import perf_counter
from decimal import Decimal
from dataclasses import replace

from core import ConfigManager, EventBus, TaskManager, TaskStatus, GlobalShortcutManager, EnterField, install_enter_navigation, WindowActionController, UniversalTextInteractionManager, ContextHelpController, CommandDefinition, CommandPalette, GlobalSearchEngine, SearchResult, UniversalLayoutPolicy
from core.scroll_utils import PercentScrollController
from core.notifications import NotificationCenter
from core.app_version import load_app_version
from core.diagnostic_logging import configure_diagnostic_logging
from database.sqlite_connection import backup_database, open_connection
from database.runtime_adapter import SQLiteRuntimeAdapter
from database import DatabaseManager, DatabaseMaintenanceService
from repositories import CadastroAuxiliarRepository, CategoriaRepository, ProdutoRepository, NFeImportRepository, NFeDevolucaoRepository, EstoqueRepository, FinanceiroRepository, CompraRepository, ClienteRepository, ClientHistoryRepository, SystemRepository
from repositories.decimal_storage import DecimalStorage, DecimalStorageError
from services.financeiro_calculator import FinanceiroCalculator
from services import CobrancaService, NFeImportService, NFeXMLService, NFeDevolucaoService, ProdutoService, ProductApplicationError, ProductApplicationService, ProductAuxiliaryCreateCommand, ProductFormBinding, ProductFormControls, ProductPricingController, ProductPricingControls, SystemDiagnostics, UIPreferencesService, EstoqueService, XMLConferenceService, ActivityService, FactoryResetService, DeveloperToolsService, SecurityService, PDVService, FinanceiroService, FinanceiroViewData, CompraService, ReportService, FiscalService, NetworkConfigService, NetworkPaths, MySQLMigrationService, CustomerMaintenanceService, CustomerRegistrationService, AdminAuditService, PDVTransactionService, SearchEntryBehavior
from services.fiscal_sale_service import FiscalSaleService
from services.fiscal_catalog_readiness_service import FiscalCatalogReadinessService
from services.license_service import LicenseService
from services.legacy_runtime_facade import LegacyAuditFacade, LegacyInfrastructureFacade, LegacySystemFacade
from services.windows_pdf_printer import WindowsPDFPrinter, WindowsPDFPrintError
from services.windows_file_opener import WindowsFileOpener, WindowsFileOpenError
from services.nabimig_import_service import NabiMigImportService
from services.nabimig_ui_service import CATEGORY_LABELS, final_report_text, preview_text
from services.receipt_template_service import ReceiptTemplateService
from ui import (
    NabiTheme,
    BackgroundManager,
    BackgroundSettings,
    LayoutManager,
    prepare_hidden_toplevel,
    reveal_prepared_toplevel_when_idle,
    reveal_prepared_toplevel_smooth,
    configure_ctk,
    configure_ttk,
    apply_responsive_geometry,
)
from ui.keyboard_navigation import install_global_arrow_navigation
from managers import SystemInfrastructureManager, AdminOperationsManager
from helpers import cached_instance, parse_flexible_number, parse_system_date, migration_phase2_preview_text, migration_phase2_result_text, parse_profile_permissions
from helpers.legacy_reduction_helpers import parse_nonnegative_number, format_number_br, database_report_text, mysql_migration_report_text
from controllers.pdv_enter_controller import PDVEnterController
from controllers.financeiro_callback_controller import FinanceiroCallbackController
from controllers.legacy_backend_adapter import LegacyBackendAdapterMixin, LegacyBackendContext
from core.startup_metrics import mark_startup
from core.startup_window_coordinator import prepare_startup_modal, startup_modal_scope

# Configuração Inicial
UI_THEME = NabiTheme()
configure_ctk(appearance="Dark")
mark_startup("theme_manager_configured")

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_RESOURCE_DIR = getattr(sys, "_MEIPASS", SOURCE_DIR)
COMPILED_APP_VERSION = "2.5.1"

def _ler_versao_aplicacao():
    return load_app_version(
        COMPILED_APP_VERSION,
        source_file=__file__,
        executable=sys.executable,
        runtime_dir=RUNTIME_RESOURCE_DIR,
    )

APP_DIR = os.environ.get("NABICODE_APP_DIR") or os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NabiCode")
os.makedirs(APP_DIR, exist_ok=True)
REDE_CONFIG_FILE = os.path.join(APP_DIR, "rede_local.json")
INSTALACAO_CONFIG_FILE = os.path.join(APP_DIR, "instalacao_concluida.json")
LOCAL_DB_DEFAULT = os.path.join(APP_DIR, "fichario_moveis.db")
SERVIDOR_DIR_DEFAULT = os.path.join(os.environ.get("SystemDrive", "C:"), os.sep, "NabiCode", "BancoCompartilhado")
SERVIDOR_DB_DEFAULT = os.path.join(SERVIDOR_DIR_DEFAULT, "fichario_moveis_compartilhado.db")

_NETWORK_CONFIG_SERVICE = NetworkConfigService(
    NetworkPaths(
        app_dir=Path(APP_DIR),
        config_file=Path(REDE_CONFIG_FILE),
        installation_file=Path(INSTALACAO_CONFIG_FILE),
        local_db=Path(LOCAL_DB_DEFAULT),
        server_dir=Path(SERVIDOR_DIR_DEFAULT),
        server_db=Path(SERVIDOR_DB_DEFAULT),
    )
)

def _carregar_config_rede():
    return _NETWORK_CONFIG_SERVICE.load()

def _salvar_config_rede(modo, db_path, papel="local"):
    _NETWORK_CONFIG_SERVICE.save(modo, db_path, papel)

def _marcar_instalacao_concluida(papel):
    _NETWORK_CONFIG_SERVICE.mark_installation_complete(papel)

def _preparar_servidor(caminho_db=SERVIDOR_DB_DEFAULT):
    return _NETWORK_CONFIG_SERVICE.prepare_server(caminho_db)

def _reparar_configuracao_servidor():
    _NETWORK_CONFIG_SERVICE.repair_server_configuration()

def _caminho_cliente_rede(servidor):
    return _NETWORK_CONFIG_SERVICE.client_paths(servidor)

def _testar_cliente_rede(servidor, usuario="", senha="", persistente=True):
    return _NETWORK_CONFIG_SERVICE.test_client(servidor, usuario, senha, persistente)

def _janela_configurar_cliente(parent):
    resultado = {"concluido": False, "banco": ""}
    janela = tk.Toplevel(parent)
    janela.title("NabiCode — Configurar computador cliente")
    janela.geometry("610x485")
    janela.resizable(False, False)
    janela.configure(bg="#0d1117")
    prepare_startup_modal(janela, parent)

    frame = tk.Frame(janela, bg="#0d1117", padx=28, pady=22)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text="Conectar ao banco do servidor", bg="#0d1117", fg="#00FF88",
             font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tk.Label(frame, text="Informe os dados usados no teste pelo CMD.", bg="#0d1117", fg="#c9d1d9",
             font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 18))

    def campo(titulo, valor="", senha=False):
        tk.Label(frame, text=titulo, bg="#0d1117", fg="#ffffff",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 4))
        entrada = tk.Entry(frame, bg="#161b22", fg="#ffffff", insertbackground="#ffffff",
                           relief="flat", font=("Segoe UI", 11), show="●" if senha else "")
        entrada.pack(fill="x", ipady=8)
        if valor:
            entrada.insert(0, valor)
        return entrada

    servidor_entry = campo("Servidor (IP ou nome)", "192.168.1.5")
    usuario_entry = campo("Usuário do Windows", r"DESKTOP-BEHLR5Q\Pichau")
    senha_entry = campo("Senha do Windows", "", senha=True)

    persistente_var = tk.BooleanVar(value=True)
    tk.Checkbutton(frame, text="Manter a conexão após reiniciar o Windows", variable=persistente_var,
                   bg="#0d1117", fg="#c9d1d9", selectcolor="#161b22", activebackground="#0d1117",
                   activeforeground="#ffffff", font=("Segoe UI", 10)).pack(anchor="w", pady=(13, 5))

    caminho_label = tk.Label(frame, text="", bg="#0d1117", fg="#8b949e",
                             font=("Segoe UI", 9), wraplength=545, justify="left")
    caminho_label.pack(anchor="w", pady=(4, 8))
    status_label = tk.Label(frame, text="Ainda não testado.", bg="#0d1117", fg="#f0b429",
                            font=("Segoe UI", 10, "bold"))
    status_label.pack(anchor="w", pady=(3, 12))

    estado = {"banco_testado": ""}

    def atualizar_caminho(*_):
        try:
            _, _, banco = _caminho_cliente_rede(servidor_entry.get())
            caminho_label.configure(text=f"Banco esperado: {banco}")
        except Exception:
            caminho_label.configure(text="")

    servidor_entry.bind("<KeyRelease>", atualizar_caminho)
    atualizar_caminho()

    botoes = tk.Frame(frame, bg="#0d1117")
    botoes.pack(fill="x", pady=(5, 0))

    def testar(mostrar_sucesso=True):
        status_label.configure(text="Testando conexão...", fg="#f0b429")
        janela.update_idletasks()
        try:
            banco = _testar_cliente_rede(
                servidor_entry.get(), usuario_entry.get(), senha_entry.get(), persistente_var.get()
            )
            estado["banco_testado"] = banco
            status_label.configure(text="Conexão, banco e permissão de gravação confirmados.", fg="#00FF88")
            if mostrar_sucesso:
                messagebox.showinfo("NabiCode — Rede", "Conexão realizada com sucesso.", parent=janela)
            return banco
        except Exception as exc:
            estado["banco_testado"] = ""
            status_label.configure(text="Falha no teste de conexão.", fg="#ff6b6b")
            messagebox.showerror("NabiCode — Rede", str(exc), parent=janela)
            return ""

    def salvar():
        banco = testar(mostrar_sucesso=False)
        if not banco:
            return
        _salvar_config_rede("rede", banco, "cliente")
        _marcar_instalacao_concluida("cliente")
        resultado.update(concluido=True, banco=banco)
        messagebox.showinfo("NabiCode — Cliente configurado",
                            f"Configuração salva com sucesso.\n\nBanco:\n{banco}", parent=janela)
        janela.destroy()

    tk.Button(botoes, text="Testar conexão", command=testar, bg="#1f6feb", fg="#ffffff",
              activebackground="#1158c7", activeforeground="#ffffff", relief="flat",
              font=("Segoe UI", 10, "bold"), padx=14, pady=9).pack(side="left")
    tk.Button(botoes, text="Salvar e concluir", command=salvar, bg="#2ea043", fg="#ffffff",
              activebackground="#238636", activeforeground="#ffffff", relief="flat",
              font=("Segoe UI", 10, "bold"), padx=14, pady=9).pack(side="right")

    janela.protocol("WM_DELETE_WINDOW", janela.destroy)
    senha_entry.focus_set()
    parent.wait_window(janela)
    return resultado["concluido"]


def _assistente_primeira_instalacao():
    if os.path.exists(INSTALACAO_CONFIG_FILE) or os.path.exists(REDE_CONFIG_FILE):
        _reparar_configuracao_servidor()
        return True

    with startup_modal_scope():
        raiz = tk.Tk()
        raiz.withdraw()
        try:
            raiz.attributes("-topmost", True)
            escolha = messagebox.askyesnocancel(
                "Instalação do NabiCode",
                "Como este computador será usado?\n\n"
                "SIM = Computador principal / servidor\n"
                "NÃO = Computador cliente da rede\n"
                "CANCELAR = Usar somente neste computador",
                parent=raiz
            )
            if escolha is True:
                destino = _preparar_servidor()
                messagebox.showinfo(
                    "NabiCode — Servidor configurado",
                    "A pasta do servidor foi criada com sucesso em:\n\n"
                    f"{os.path.dirname(destino)}\n\n"
                    "O banco será criado automaticamente ao abrir o sistema.\n"
                    "Depois compartilhe essa pasta no Windows com permissão de leitura e gravação.",
                    parent=raiz
                )
            elif escolha is False:
                raiz.deiconify()
                raiz.geometry("1x1+0+0")
                raiz.overrideredirect(True)
                if not _janela_configurar_cliente(raiz):
                    return False
            else:
                _salvar_config_rede("local", LOCAL_DB_DEFAULT, "local")
                _marcar_instalacao_concluida("local")
            return True
        except Exception as exc:
            messagebox.showerror(
                "Instalação",
                f"Não foi possível concluir a configuração:\n{exc}",
                parent=raiz,
            )
            return False
        finally:
            try:
                raiz.attributes("-topmost", False)
            except tk.TclError:
                pass
            raiz.destroy()

if not _assistente_primeira_instalacao():
    sys.exit(0)
_REDE_CFG = _carregar_config_rede()
DB_NAME = os.path.abspath(_REDE_CFG.get("db_path") or LOCAL_DB_DEFAULT)
MODO_REDE = _REDE_CFG.get("modo") == "rede"
PAPEL_REDE = _REDE_CFG.get("papel", "local")
BACKUP_DIR = os.path.join(APP_DIR, "backups_moveis")
PDF_DIR = os.path.join(APP_DIR, "pdf_cupons_moveis")

APP_VERSION = _ler_versao_aplicacao()
APP_VERSION_LABEL = "Pesquisa global Ctrl+K"
DB_SCHEMA_VERSION = 17
ULTIMA_ATUALIZACAO_BANCO = {"executada": False, "de": 0, "para": DB_SCHEMA_VERSION, "backup": ""}

LOG_DIR = os.path.join(APP_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "nabicode.log")

logger = logging.getLogger("NabiCode")
if not logger.handlers:
    configure_diagnostic_logging(
        logger,
        LOG_FILE,
        app_version=APP_VERSION,
        runtime_profile=os.environ.get("NABICODE_PROFILE", "PRODUCAO"),
    )

CORE_CONFIG_FILE = os.path.join(APP_DIR, "config", "sistema.json")
CORE_CONFIG = ConfigManager(
    CORE_CONFIG_FILE,
    {
        "aplicacao": {"versao": APP_VERSION, "schema": DB_SCHEMA_VERSION},
        "backup": {"snapshots_maximos": 20},
        "eventos": {"habilitados": True},
        "interface": UIPreferencesService.DEFAULTS,
    },
)
CORE_CONFIG.set("aplicacao.versao", APP_VERSION)
CORE_CONFIG.set("aplicacao.schema", DB_SCHEMA_VERSION)
EVENT_BUS = EventBus(logger)
TASK_MANAGER = TaskManager(max_workers=2, event_bus=EVENT_BUS, logger=logger)
_RUNTIME_SHUTDOWN_DONE = False


def shutdown_runtime_resources() -> None:
    """Encerra tarefas cooperativamente antes da liberação do lock do banco."""

    global _RUNTIME_SHUTDOWN_DONE
    if _RUNTIME_SHUTDOWN_DONE:
        return
    _RUNTIME_SHUTDOWN_DONE = True
    TASK_MANAGER.shutdown(wait=True, cancel_pending=True)
COBRANCA_SERVICE = CobrancaService(DatabaseManager(DB_NAME, network_mode=MODO_REDE, logger=logger))
NFE_IMPORT_SERVICE = NFeImportService(NFeImportRepository(DatabaseManager(DB_NAME, network_mode=MODO_REDE, logger=logger)))
NFE_DEVOLUCAO_SERVICE = NFeDevolucaoService(NFeDevolucaoRepository(DatabaseManager(DB_NAME, network_mode=MODO_REDE, logger=logger)))
ESTOQUE_SERVICE = EstoqueService(EstoqueRepository(DatabaseManager(DB_NAME, network_mode=MODO_REDE, logger=logger)))


_DATABASE_RUNTIME = SQLiteRuntimeAdapter(DB_NAME, network_mode=MODO_REDE, logger=logger)
conectar_banco = _DATABASE_RUNTIME.connect
sessao_banco = _DATABASE_RUNTIME.session
_AUDIT_SERVICE = AdminAuditService(conectar_banco, logger=logger)
_AUDIT_FACADE = LegacyAuditFacade(
    _AUDIT_SERVICE,
    event_bus=EVENT_BUS,
    events_enabled=lambda: CORE_CONFIG.get("eventos.habilitados", True),
    database_path=DB_NAME,
)
registrar_auditoria = _AUDIT_FACADE.record

DATABASE_MANAGER = DatabaseManager(DB_NAME, network_mode=MODO_REDE, logger=logger)
CLIENT_HISTORY_REPOSITORY = ClientHistoryRepository(DATABASE_MANAGER)
PRODUTO_SERVICE = ProdutoService(
    ProdutoRepository(DATABASE_MANAGER),
    CategoriaRepository(DATABASE_MANAGER),
    CadastroAuxiliarRepository(DATABASE_MANAGER),
    auditoria=registrar_auditoria,
)
PRODUCT_APPLICATION_SERVICE = ProductApplicationService(PRODUTO_SERVICE, ESTOQUE_SERVICE)
DATABASE_MAINTENANCE = DatabaseMaintenanceService(
    DB_NAME,
    BACKUP_DIR,
    expected_schema_version=DB_SCHEMA_VERSION,
    required_tables=("configuracoes", "clientes", "produtos", "movimentacoes", "schema_migrations"),
)
FACTORY_RESET_SERVICE = FactoryResetService(DB_NAME, DATABASE_MAINTENANCE)
FINANCEIRO_SERVICE = FinanceiroService(FinanceiroRepository(DATABASE_MANAGER))
COMPRA_SERVICE = CompraService(CompraRepository(DATABASE_MANAGER), EstoqueRepository(DATABASE_MANAGER), FINANCEIRO_SERVICE)
CLIENTE_REPOSITORY = ClienteRepository(DATABASE_MANAGER)
CUSTOMER_MAINTENANCE_SERVICE = CustomerMaintenanceService(DATABASE_MANAGER)
REPORT_SERVICE = ReportService(conectar_banco, output_dir=Path(APP_DIR) / "relatorios", audit=registrar_auditoria)

tratar_numero = parse_flexible_number



# -----------------------------------------------------------------------------
# Infraestrutura segura: diagnóstico, snapshots, rollback e auditoria (v2.4.3)
# -----------------------------------------------------------------------------
RELEASE_DIR = os.path.join(APP_DIR, "releases")
ROLLBACK_DIR = os.path.join(APP_DIR, "rollback")
DIAGNOSTIC_DIR = os.path.join(APP_DIR, "diagnosticos")
UPDATE_STATE_FILE = os.path.join(APP_DIR, "estado_atualizacao.json")

_SYSTEM_INFRASTRUCTURE = SystemInfrastructureManager(
    database_manager=DATABASE_MANAGER,
    db_name=DB_NAME,
    backup_dir=BACKUP_DIR,
    pdf_dir=PDF_DIR,
    rollback_dir=ROLLBACK_DIR,
    diagnostic_dir=DIAGNOSTIC_DIR,
    update_state_file=UPDATE_STATE_FILE,
    app_dir=APP_DIR,
    source_dir=SOURCE_DIR,
    app_version=APP_VERSION,
    schema_version=DB_SCHEMA_VERSION,
    last_database_update=ULTIMA_ATUALIZACAO_BANCO,
    network_mode=MODO_REDE,
    network_role=PAPEL_REDE,
    connect=conectar_banco,
    logger=logger,
    get_config=lambda key: obter_config(key),
    set_config=lambda key, value: salvar_config(key, value),
    required_diagnostic_tables={"clientes", "movimentacoes", "configuracoes", "categorias_produtos", "produtos"},
)


_SYSTEM_REPOSITORY = SystemRepository(conectar_banco)
_SYSTEM_FACADE = LegacySystemFacade(_SYSTEM_REPOSITORY)
registrar_historico = _SYSTEM_FACADE.add_client_history
obter_config = _SYSTEM_FACADE.get_config
modo_fiscal_ativo = _SYSTEM_FACADE.fiscal_mode_enabled
salvar_config = _SYSTEM_FACADE.set_config

_INFRASTRUCTURE_FACADE = LegacyInfrastructureFacade(
    _SYSTEM_INFRASTRUCTURE,
    SystemDiagnostics.format_report,
)
inicializar_banco = _INFRASTRUCTURE_FACADE.initialize_database
_servico_snapshots = _INFRASTRUCTURE_FACADE.snapshot_service
criar_snapshot_sistema = _INFRASTRUCTURE_FACADE.create_snapshot
listar_snapshots_sistema = _INFRASTRUCTURE_FACADE.list_snapshots
restaurar_snapshot_sistema = _INFRASTRUCTURE_FACADE.restore_snapshot
_servico_backups = _INFRASTRUCTURE_FACADE.backup_service
_servico_diagnostico = _INFRASTRUCTURE_FACADE.diagnostics_service
_diretorio_instalacao = _INFRASTRUCTURE_FACADE.install_dir
_validar_atualizacao_apos_reinicio = _INFRASTRUCTURE_FACADE.validate_after_restart
executar_diagnostico_sistema = _INFRASTRUCTURE_FACADE.execute_diagnostics
formatar_diagnostico = _INFRASTRUCTURE_FACADE.format_diagnostics


_MYSQL_MIGRATION_SERVICE = MySQLMigrationService()

_ADMIN_OPERATIONS = AdminOperationsManager(
    get_config=obter_config,
    set_config=salvar_config,
    database_maintenance=DATABASE_MAINTENANCE,
    backup_dir=BACKUP_DIR,
    connect=conectar_banco,
    app_dir=APP_DIR,
    install_dir=_diretorio_instalacao,
    current_version=APP_VERSION,
)


CUSTOMER_REGISTRATION_SERVICE = CustomerRegistrationService(
    CLIENTE_REPOSITORY,
    get_config=obter_config,
    set_config=salvar_config,
    history_callback=registrar_historico,
)

def analisar_dump_mysql(caminho, progresso=None):
    return _MYSQL_MIGRATION_SERVICE.analyze_dump(caminho, progresso)


def preparar_migracao_resumida(caminho, progresso=None):
    return _MYSQL_MIGRATION_SERVICE.prepare_summary(caminho, progresso)

def executar_migracao_resumida(dados, remover_demos=True, progresso=None):
    """Importa o resumo MySQL pela camada de serviço transacional."""
    return _MYSQL_MIGRATION_SERVICE.execute_summary(
        dados,
        database_path=DB_NAME,
        backup_dir=BACKUP_DIR,
        connect=conectar_banco,
        backup_database=backup_database,
        network_mode=MODO_REDE,
        logger=logger,
        remove_demo_clients=remover_demos,
        progress=progresso,
    )

def _data_sql(valor):
    """Fachada compatível para conversão das datas usadas pelo sistema."""
    return parse_system_date(valor)


class BidirectionalScrollableFrame(ctk.CTkFrame):
    """Área rolável bidirecional com limites percentuais e rodapé externo.

    Roda do mouse: vertical em passos de 5%.
    Shift + roda: horizontal em passos de 5%.
    PageUp/PageDown: 20%; Home/End: 0%/100%.
    """

    def __init__(
        self, master, *, fg_color="#161b22", content_width=1000, content_height=1,
        expand_to_viewport=False, **kwargs
    ):
        super().__init__(master, fg_color=fg_color, **kwargs)
        self._minimum_content_width = int(content_width)
        self._expand_to_viewport = bool(expand_to_viewport)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._wheel_bound = False
        self._wheel_bindings = {}

        canvas_bg = self._resolve_canvas_background(master)
        self.canvas = tk.Canvas(
            self,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
            relief="flat",
            xscrollincrement=1,
            yscrollincrement=1,
        )
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self._on_xscroll, yscrollcommand=self._on_yscroll)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.status = ctk.CTkLabel(self, text="H 0% | V 0%", width=92, height=18, font=ctk.CTkFont(size=10))
        self.status.grid(row=1, column=1, sticky="nsew")

        self.content = ctk.CTkFrame(self.canvas, fg_color="transparent", width=content_width, height=content_height)
        self._window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._update_scrollregion, add="+")
        self.canvas.bind("<Configure>", self._update_scrollregion, add="+")

        # A roda é registrada uma única vez. O handler verifica se o evento
        # pertence a este frame. Isso evita perder a rolagem ao mover o cursor
        # entre o Canvas e widgets filhos, situação em que <Leave> era emitido
        # mesmo com o ponteiro visualmente dentro da área rolável.
        self._bind_wheel()
        for widget in (self, self.canvas, self.content):
            widget.bind("<Prior>", lambda _e: self.scroll_vertical(-20), add="+")
            widget.bind("<Next>", lambda _e: self.scroll_vertical(20), add="+")
            widget.bind("<Home>", lambda _e: self.move_vertical(0), add="+")
            widget.bind("<End>", lambda _e: self.move_vertical(100), add="+")
        self.canvas.configure(takefocus=True)

    def _resolve_canvas_background(self, master):
        """Resolve uma cor concreta para widgets Tk clássicos.

        CustomTkinter aceita ``fg_color="transparent"``, mas ``tk.Canvas``
        exige uma cor Tk válida. A resolução sobe pela hierarquia até achar
        uma cor concreta e usa uma cor segura como último recurso.
        """
        candidate = self.cget("fg_color")
        current = master
        visited = set()
        while candidate in (None, "", "transparent") and current is not None:
            marker = id(current)
            if marker in visited:
                break
            visited.add(marker)
            try:
                candidate = current.cget("fg_color")
            except (AttributeError, KeyError, tk.TclError):
                try:
                    candidate = current.cget("bg")
                except (AttributeError, KeyError, tk.TclError):
                    candidate = None
            current = getattr(current, "master", None)

        if candidate in (None, "", "transparent"):
            candidate = ("#f2f2f2", "#242424")
        try:
            return self._apply_appearance_mode(candidate)
        except (AttributeError, TypeError, tk.TclError):
            if isinstance(candidate, (tuple, list)):
                return str(candidate[-1])
            return str(candidate)

    def _update_scrollregion(self, _event=None):
        self.update_idletasks()
        if self._expand_to_viewport:
            viewport_width = max(1, self.canvas.winfo_width())
            target_width = max(self._minimum_content_width, viewport_width)
            try:
                self.canvas.itemconfigure(self._window_id, width=target_width)
            except tk.TclError:
                pass
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)
        self._update_scrollbar_visibility()
        self._update_status()

    def _update_scrollbar_visibility(self):
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        content_w = max(0, bbox[2] - bbox[0])
        content_h = max(0, bbox[3] - bbox[1])
        if content_h <= self.canvas.winfo_height() + 2:
            self.v_scroll.grid_remove()
            self.canvas.yview_moveto(0)
        else:
            self.v_scroll.grid()
        if content_w <= self.canvas.winfo_width() + 2:
            self.h_scroll.grid_remove()
            self.canvas.xview_moveto(0)
        else:
            self.h_scroll.grid()

    def _on_xscroll(self, first, last):
        self.h_scroll.set(first, last)
        self._update_status()

    def _on_yscroll(self, first, last):
        self.v_scroll.set(first, last)
        self._update_status()

    def _update_status(self):
        x_first, x_last = self.canvas.xview()
        y_first, y_last = self.canvas.yview()
        x_percent = PercentScrollController.viewport_percent(x_first, x_last)
        y_percent = PercentScrollController.viewport_percent(y_first, y_last)
        self.status.configure(text=f"H {x_percent}% | V {y_percent}%")

    def _bind_wheel(self, _event=None):
        if self._wheel_bound:
            return
        self._wheel_bound = True
        self._wheel_bindings = {
            "<MouseWheel>": tk.Misc.bind_all(self, "<MouseWheel>", self._on_mousewheel, add="+"),
            "<Shift-MouseWheel>": tk.Misc.bind_all(self, "<Shift-MouseWheel>", self._on_shift_mousewheel, add="+"),
            "<Button-4>": tk.Misc.bind_all(self, "<Button-4>", lambda e: self._scroll_button(e, -5, False), add="+"),
            "<Button-5>": tk.Misc.bind_all(self, "<Button-5>", lambda e: self._scroll_button(e, 5, False), add="+"),
            "<Shift-Button-4>": tk.Misc.bind_all(self, "<Shift-Button-4>", lambda e: self._scroll_button(e, -5, True), add="+"),
            "<Shift-Button-5>": tk.Misc.bind_all(self, "<Shift-Button-5>", lambda e: self._scroll_button(e, 5, True), add="+"),
        }

    def _scroll_button(self, event, delta_percent, horizontal=False):
        if not self._event_is_inside(event):
            return None
        if horizontal:
            self.scroll_horizontal(delta_percent)
        else:
            self.scroll_vertical(delta_percent)
        return "break"

    def _event_is_inside(self, event):
        widget = getattr(event, "widget", None)
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _unbind_wheel(self, _event=None):
        if not self._wheel_bound:
            return
        self._wheel_bound = False
        for sequence, func_id in self._wheel_bindings.items():
            if func_id:
                try:
                    self.unbind_class("all", sequence, func_id)
                except tk.TclError:
                    pass
        self._wheel_bindings.clear()

    def _on_mousewheel(self, event):
        if not self._event_is_inside(event):
            return None
        direction = PercentScrollController.wheel_direction(getattr(event, "delta", 0))
        if direction:
            self.scroll_vertical(direction * 5)
        return "break"

    def _on_shift_mousewheel(self, event):
        if not self._event_is_inside(event):
            return None
        direction = PercentScrollController.wheel_direction(getattr(event, "delta", 0))
        if direction:
            self.scroll_horizontal(direction * 5)
        return "break"

    def scroll_vertical(self, delta_percent):
        first, last = self.canvas.yview()
        current = PercentScrollController.viewport_percent(first, last)
        self.move_vertical(current + float(delta_percent))

    def scroll_horizontal(self, delta_percent):
        first, last = self.canvas.xview()
        current = PercentScrollController.viewport_percent(first, last)
        self.move_horizontal(current + float(delta_percent))

    def move_vertical(self, percent):
        first, last = self.canvas.yview()
        self.canvas.yview_moveto(PercentScrollController.moveto_for_percent(percent, first, last))
        self._update_status()

    def move_horizontal(self, percent):
        first, last = self.canvas.xview()
        self.canvas.xview_moveto(PercentScrollController.moveto_for_percent(percent, first, last))
        self._update_status()


class FicharioMoveisApp(LegacyBackendAdapterMixin, ctk.CTk):
    backend_context = LegacyBackendContext(
        database_manager=DATABASE_MANAGER,
        connect=conectar_banco,
        get_config=obter_config,
        pdf_dir=PDF_DIR,
        product_application_service=PRODUCT_APPLICATION_SERVICE,
        report_service=REPORT_SERVICE,
    )
    def __init__(self):
        super().__init__(fg_color="#0d1117")
        self._main_window_ready = False
        self._startup_reveal_complete = False
        self._license_dialog_active = False
        self._license_dialog_window = None
        self._license_exit_requested = False
        mark_startup("main_window_created")
        # Constrói toda a interface com a janela oculta. Isso evita a janela
        # branca e o redesenho completo visível durante a inicialização.
        self.withdraw()

        mark_startup("database_migrations_started")
        primeira_vez = inicializar_banco()
        mark_startup("database_migrations_ready", first_install=bool(primeira_vez))
        resultado_atualizacao = _validar_atualizacao_apos_reinicio()
        if resultado_atualizacao and not resultado_atualizacao.get("ok"):
            with startup_modal_scope():
                messagebox.showerror(
                    "Atualização revertida",
                    "A atualização falhou na validação e foi revertida.\n\n"
                    + resultado_atualizacao.get("error", "Falha desconhecida")
                    + "\n\nO NabiCode será reaberto na versão anterior.",
                    parent=self,
                )
            launcher = str(Path(sys.executable).resolve())
            comando = [launcher] if getattr(sys, "frozen", False) else [launcher, str(Path(SOURCE_DIR) / "main.py")]
            subprocess.Popen(comando, cwd=str(_diretorio_instalacao()))
            self.destroy()
            return
        registrar_auditoria("Sistema", "INICIALIZAR", APP_VERSION, APP_VERSION_LABEL, "SUCESSO")
        self.security = SecurityService(conectar_banco, inactivity_minutes=int(obter_config("bloqueio_inatividade_minutos") or 15))
        REPORT_SERVICE.authorize = lambda _actor, report_id: self.security.require(self._modulo_do_relatorio(report_id), "view")
        self.fiscal_service = FiscalService(conectar_banco, storage_dir=os.path.join(APP_DIR, "fiscal"))
        self.fiscal_sale_service = FiscalSaleService(self.fiscal_service)
        self.fiscal_catalog_readiness_service = FiscalCatalogReadinessService(conectar_banco)
        self.pdv_service = PDVService(conectar_banco)
        self.pdv_transaction_service = PDVTransactionService(
            conectar_banco, estoque_service=ESTOQUE_SERVICE,
            financeiro_service=FINANCEIRO_SERVICE, pdv_service=self.pdv_service
        )
        self.modo_pdv = self.pdv_service.normalizar_modo(obter_config("pdv_modo") or "BALCAO")
        self.security.bootstrap_admin(obter_config("admin_senha_hash"))
        # Migração corretiva 2.4.42: o login de abertura fica DESATIVADO em toda
        # instalação existente até que o proprietário marque e salve novamente a
        # opção na tela Segurança desta versão. Chaves antigas não autorizam mais
        # a abertura protegida, evitando que um valor legado reative o login.
        if str(obter_config("login_politica_v2442_inicializada") or "0").strip() != "1":
            salvar_config("login_usuarios_habilitado", "0")
            salvar_config("login_usuarios_configurado", "1")
            salvar_config("login_inicio_consentido_v2440", "0")
            salvar_config("login_inicio_ativado_pelo_usuario_v2442", "0")
            salvar_config("login_politica_v2442_inicializada", "1")
        if CORE_CONFIG.get("eventos.habilitados", True):
            EVENT_BUS.publish(
                "aplicacao.inicializada",
                versao=APP_VERSION, schema=DB_SCHEMA_VERSION, banco=DB_NAME, primeira_vez=primeira_vez,
            )

        self.preferencias_interface = UIPreferencesService.normalize(CORE_CONFIG.get("interface", {}))
        self.perfil_interface = UIPreferencesService.build_profile(self.preferencias_interface)
        self._usuario_preferencias_interface = None

        self._paletas = {
            "Verde Nabi": ("#00FF88", "#00cc6a"),
            "Azul": ("#388bfd", "#1f6feb"),
            "Roxo": ("#a371f7", "#8957e5"),
            "Laranja": ("#ff9f43", "#e67e22"),
            "Rosa": ("#ff6fae", "#d94f8a"),
        }
        self._labels_nome_loja = []
        self._widgets_acento = []
        self._grupos_botoes_topo = []
        self._botoes_favoritos = []
        self.notification_center = NotificationCenter(
            default_duration_ms=CORE_CONFIG.get("notificacoes.duracao_ms", 4200)
        )
        self._toast_windows = []
        aparencia = obter_config("aparencia_sistema") or "Dark"
        ctk.set_appearance_mode(aparencia if aparencia in ("Dark", "Light", "System") else "Dark")
        self.cor_acento, self.cor_acento_hover = self._paletas.get(obter_config("cor_destaque"), self._paletas["Verde Nabi"])
        
        # BLOQUEIO DEFINITIVO: Trava a execução caso a licença tenha expirado
        with startup_modal_scope():
            while self.verificar_bloqueio_expiracao():
                pass
        if self._license_exit_requested:
            self.destroy()
            raise SystemExit(0)

        self.title(obter_config("nome_loja") or "NabiCode — Gerenciador de Crediário Inteligente")
        apply_responsive_geometry(self, theme=UI_THEME)
        self.configure(fg_color=UI_THEME.background)

        # Estilo visual centralizado para tabelas; sem interferência nos dados.
        estilo = ttk.Style()
        configure_ttk(
            estilo,
            theme=UI_THEME,
            row_height=UIPreferencesService.row_height(self.perfil_interface.density),
            selected_color=self.cor_acento_hover,
        )

        if resultado_atualizacao and resultado_atualizacao.get("ok"):
            relatorio = resultado_atualizacao.get("report", {})
            with startup_modal_scope():
                messagebox.showinfo(
                    "Atualização concluída",
                    f"Atualização {APP_VERSION} concluída e validada.\n\n"
                    f"Arquivos validados: {relatorio.get('arquivos', 0)}\n"
                    f"Banco preservado: sim\n"
                    f"Relatório: {relatorio.get('diagnostico') or 'não informado'}",
                    parent=self,
                )
        if primeira_vez:
            with startup_modal_scope():
                messagebox.showinfo(
                    "Boas-vindas! 🦋",
                    "Primeira instalação realizada com sucesso para o NabiCode!\nSistema pronto para uso.",
                    parent=self,
                )
        elif ULTIMA_ATUALIZACAO_BANCO["executada"]:
            with startup_modal_scope():
                messagebox.showinfo(
                    "Atualização concluída",
                    "O banco de dados foi atualizado com segurança.\n\n"
                    f"Versão do banco: {ULTIMA_ATUALIZACAO_BANCO['de']} → {ULTIMA_ATUALIZACAO_BANCO['para']}\n"
                    f"Backup criado em:\n{ULTIMA_ATUALIZACAO_BANCO['backup']}\n\n"
                    "Seus cadastros e históricos foram preservados.",
                    parent=self,
                )

        # Pânico não pode compartilhar teclas de navegação. O atalho exige
        # combinação deliberada para nunca fechar o sistema ao navegar listas.
        self.bind("<Control-Shift-P>", self.ativar_modo_panico)
        
        self.bind("<F1>", lambda event: self.mostrar_tela("configs" if primeira_vez else "dashboard"))
        self.bind("<F2>", lambda event: self.abrir_pdv_independente())
        self.bind("<F3>", lambda event: self.mostrar_tela("clientes"))
        self.bind("<F4>", lambda event: self.mostrar_tela("produtos"))
        self.bind("<F5>", lambda event: self.mostrar_tela("configs"))
        for indice in range(1, 10):
            self.bind(f"<Alt-Key-{indice}>", lambda event, pos=indice: self._abrir_favorito_por_posicao(pos))
            self.bind(f"<Alt-KP_{indice}>", lambda event, pos=indice: self._abrir_favorito_por_posicao(pos))
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.carrinho_venda = []
        
        mark_startup("ui_build_started")
        self.criar_menu_lateral()
        self.criar_telas()
        mark_startup("ui_modules_created")
        self._aplicar_visibilidade_navegacao()
        
        if primeira_vez:
            self.mostrar_tela("configs")
        else:
            self.mostrar_tela("dashboard")
        mark_startup("dashboard_ready", first_install=bool(primeira_vez))

        self._instalar_interacoes_texto_globais()
        self._instalar_atalhos_globais()
        install_global_arrow_navigation(self)
        self.after(5000, self._executar_agendamentos_relatorios)
        self.bind("<<NabiCommandPalette>>", lambda _event: self.abrir_pesquisa_global(), add="+")

        # Redesenho com debounce ao restaurar/maximizar evita piscadas e artefatos visuais.
        self._redimensionamento_after = None
        self._redimensionamento_tamanho = None
        self.bind("<Configure>", self._agendar_redesenho_interface, add="+")
        self.bind("<Map>", self._agendar_redesenho_interface, add="+")
        self.after(900, self._executar_backup_diario_automatico)
        self._cash_startup_after_id = self.after(1800, self._agendar_pergunta_abertura_caixa)
        self._cash_startup_check_done = False
        self.after(5000, self._atualizacao_automatica_rede)
        self.after(1000, self._monitorar_licenca)
        self.bind_all("<Any-KeyPress>", lambda _event: self.security.touch(), add="+")
        self.bind_all("<Any-Button>", lambda _event: self.security.touch(), add="+")
        self.after(250, self._monitorar_inatividade)
        self.security.start_session_without_password("admin")
        self._janela_abertura_caixa = None
        self._janela_formulario_abertura_caixa = None
        # Confirma o primeiro frame válido sem revelar a raiz. O entrypoint
        # mantém a splash até receber esse readiness gate.
        self.after_idle(self._confirmar_main_window_ready)

    def _confirmar_main_window_ready(self):
        """Confirma layout mínimo calculado, mantendo a janela oculta."""
        try:
            self.update_idletasks()
            if self.winfo_reqwidth() <= 1 or self.winfo_reqheight() <= 1:
                self.after(16, self._confirmar_main_window_ready)
                return
            self._main_window_ready = True
            mark_startup("main_window_ready")
        except tk.TclError:
            logger.exception("Não foi possível confirmar o primeiro frame da janela principal.")

    def _marcar_startup_revelado(self):
        self._startup_reveal_complete = True

    def _garantir_janela_principal_visivel(self):
        """Exibe a janela principal uma única vez após o layout estar pronto."""
        try:
            if not self._startup_reveal_complete:
                return
            self.update_idletasks()
            if self.state() == "withdrawn":
                self.deiconify()
            self.lift()
            self.after(80, self.focus_force)
        except tk.TclError:
            logger.exception("Não foi possível exibir a janela principal.")

    def _login_usuarios_habilitado(self):
        # Login automático desativado: o NabiCode sempre inicia em sessão local.
        return False

    def _senha_administrativa_valida(self, senha):
        return self.security.confirm_manager_password(str(senha or ""))

    def _preparar_janela_modal(self, janela, parent=None):
        """Mantém diálogos críticos visíveis, centralizados e acima da janela chamadora."""
        parent = parent or self
        janela.transient(parent)
        janela.grab_set()
        janela.lift()
        try:
            janela.attributes("-topmost", True)
            janela.after(250, lambda: janela.attributes("-topmost", False))
        except Exception:
            pass
        janela.after(80, janela.focus_force)

    def _cliente_consumidor_final(self):
        """Retorna um cliente técnico para vendas simples sem exigir cadastro no caixa."""
        return CLIENTE_REPOSITORY.get_or_create_final_consumer()

    def _autorizar(self, modulo, acao="view", *, silencioso=False):
        if not self.security.session:
            self.security.start_session_without_password("admin")
        if self.security.require(modulo, acao):
            self.security.touch()
            return True
        if not silencioso:
            messagebox.showerror("Acesso negado", f"Seu perfil não possui permissão para {modulo}:{acao}.", parent=self)
        return False

    def abrir_login_usuario(self):
        return None

    def _monitorar_inatividade(self):
        try:
            if not self.security.session:
                self.security.start_session_without_password("admin")
        finally:
            self.after(30000, self._monitorar_inatividade)

    def confirmar_senha_gerente(self, titulo="Confirmação de gerente"):
        senha = simpledialog.askstring(titulo, "Digite a senha de um gerente ou administrador:", show="●", parent=self)
        return bool(senha and self.security.confirm_manager_password(senha))

    def mostrar_notificacao(self, titulo, mensagem, *, nivel="info", duracao_ms=None, parent=None):
        """Exibe toast não bloqueante e registra a mensagem no histórico."""
        registro = self.notification_center.publish(
            titulo, mensagem, level=nivel, duration_ms=duracao_ms
        )
        try:
            toast = ctk.CTkToplevel(parent or self)
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            cores = {
                "success": ("#1f6f43", "#2ea043"),
                "info": ("#153f73", "#1f6feb"),
                "warning": ("#6b4d00", "#bf8700"),
                "error": ("#6e1f22", "#da3633"),
            }
            fundo, destaque = cores.get(registro.level, cores["info"])
            toast.configure(fg_color=fundo)
            frame = ctk.CTkFrame(toast, fg_color=fundo, corner_radius=10, border_width=1, border_color=destaque)
            frame.pack(fill="both", expand=True)
            ctk.CTkLabel(frame, text=registro.title, font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkLabel(frame, text=registro.message, wraplength=390, justify="left", anchor="w").pack(fill="x", padx=14, pady=(0, 10))
            toast.update_idletasks()
            largura = max(330, min(430, toast.winfo_reqwidth()))
            altura = toast.winfo_reqheight()
            x = max(0, self.winfo_rootx() + self.winfo_width() - largura - 24)
            deslocamento = sum(j.winfo_height() + 8 for j in self._toast_windows if j.winfo_exists())
            y = max(0, self.winfo_rooty() + self.winfo_height() - altura - 24 - deslocamento)
            toast.geometry(f"{largura}x{altura}+{x}+{y}")
            self._toast_windows.append(toast)

            def fechar():
                if toast in self._toast_windows:
                    self._toast_windows.remove(toast)
                try:
                    toast.destroy()
                except tk.TclError:
                    pass

            toast.bind("<Button-1>", lambda _event: fechar())
            toast.after(registro.duration_ms, fechar)
        except Exception:
            logger.exception("Falha ao exibir notificação não bloqueante")
        return registro

    def abrir_historico_notificacoes(self):
        janela = ctk.CTkToplevel(self)
        prepare_hidden_toplevel(janela)
        janela.title("Histórico de notificações")
        janela.geometry("760x480")
        janela.minsize(620, 360)
        janela.transient(self)
        janela.configure(fg_color="#0d1117")
        cabecalho = ctk.CTkFrame(janela, fg_color="transparent")
        cabecalho.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(cabecalho, text="Histórico de notificações", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.cor_acento).pack(side="left")
        def limpar_historico():
            self.notification_center.clear()
            for item_id in tabela.get_children():
                tabela.delete(item_id)
        ctk.CTkButton(cabecalho, text="Limpar histórico", width=130, fg_color="#30363d", command=limpar_historico).pack(side="right")
        tabela = ttk.Treeview(janela, columns=("hora", "nivel", "titulo", "mensagem"), show="headings")
        for coluna, titulo, largura in (("hora", "Data/hora", 145), ("nivel", "Nível", 85), ("titulo", "Título", 150), ("mensagem", "Mensagem", 360)):
            tabela.heading(coluna, text=titulo)
            tabela.column(coluna, width=largura, anchor="w")
        barra = ttk.Scrollbar(janela, orient="vertical", command=tabela.yview)
        tabela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y", padx=(0, 12), pady=(0, 12))
        tabela.pack(fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        for indice, item in enumerate(self.notification_center.history()):
            tabela.insert("", "end", iid=str(indice), values=(
                item.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                item.level.upper(), item.title, item.message,
            ))
        reveal_prepared_toplevel_when_idle(janela)

    def _atualizacao_automatica_rede(self):
        try:
            if MODO_REDE:
                self.atualizar_resumo_lateral()
                if hasattr(self, "tabela_historico") and self.tabela_historico.winfo_exists():
                    self.carregar_historico_dia()
        except Exception:
            pass
        self.after(5000, self._atualizacao_automatica_rede)

    def abrir_configuracao_rede(self):
        janela = ctk.CTkToplevel(self)
        janela.title("NabiCode — Rede local")
        janela.geometry("720x520")
        janela.resizable(False, False)
        janela.transient(self); janela.grab_set(); janela.configure(fg_color="#0d1117")
        modo_txt = "REDE COMPARTILHADA" if MODO_REDE else "LOCAL"
        ctk.CTkLabel(janela, text="🖥️ Banco compartilhado da loja", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.cor_acento).pack(pady=(22,8))
        ctk.CTkLabel(janela, text=f"Modo atual: {modo_txt}", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=4)
        ctk.CTkLabel(janela, text=DB_NAME, wraplength=650, text_color="#8b949e").pack(padx=25,pady=(0,18))
        ctk.CTkLabel(janela, text="No computador principal, crie o banco numa pasta compartilhada.\nNos outros computadores, selecione exatamente o mesmo arquivo .db.", justify="left", wraplength=650).pack(padx=28,pady=8,anchor="w")
        def aviso():
            messagebox.showinfo("Rede local", "Configuração salva. Feche e abra o NabiCode novamente.", parent=janela)
        def criar():
            try:
                destino = _preparar_servidor()
                if os.path.abspath(DB_NAME) != os.path.abspath(destino) and os.path.exists(DB_NAME):
                    backup_database(DB_NAME, destino, timeout=30, network_mode=MODO_REDE, logger=logger)
                messagebox.showinfo("Rede local", f"Pasta criada e configuração salva em:\n\n{os.path.dirname(destino)}\n\nFeche e abra o NabiCode novamente.", parent=janela)
            except Exception as exc:
                messagebox.showerror("Rede local",f"Não foi possível criar o banco:\n{exc}",parent=janela)
        def conectar():
            if _janela_configurar_cliente(janela):
                aviso()
        def local():
            _salvar_config_rede("local",LOCAL_DB_DEFAULT,"local"); _marcar_instalacao_concluida("local"); aviso()
        ctk.CTkButton(janela,text="1️⃣ Criar banco compartilhado neste computador",height=44,fg_color="#2ea043",command=criar).pack(fill="x",padx=35,pady=(18,7))
        ctk.CTkButton(janela,text="2️⃣ Conectar a banco compartilhado existente",height=44,fg_color="#1f6feb",command=conectar).pack(fill="x",padx=35,pady=7)
        ctk.CTkButton(janela,text="Voltar ao banco local",height=40,fg_color="#8957e5",command=local).pack(fill="x",padx=35,pady=7)
        ctk.CTkLabel(janela,text="O computador principal e a pasta compartilhada precisam permanecer ligados e acessíveis.",wraplength=640,text_color="#f0b429").pack(padx=35,pady=(18,5),anchor="w")

    def _executar_backup_diario_automatico(self):
        resultado = _servico_backups().run_daily()
        if resultado.errors:
            logger.warning("Backup diário concluído com falhas: %s", " | ".join(resultado.errors))

    def _atualizar_identidade_visual(self):
        nome = obter_config("nome_loja") or "NabiCode — Gerenciador de Crediário"
        self.title(nome)
        for lbl in list(self._labels_nome_loja):
            try:
                if lbl.winfo_exists():
                    lbl.configure(text=nome.upper(), text_color=self.cor_acento)
            except Exception:
                pass
        for widget in list(self._widgets_acento):
            try:
                if widget.winfo_exists():
                    widget.configure(text_color=self.cor_acento)
            except Exception:
                pass
        try:
            self.lbl_logo_empresa.configure(text_color=self.cor_acento)
        except Exception:
            pass
        try:
            ttk.Style().map("Treeview", background=[("selected", self.cor_acento_hover)])
        except Exception:
            pass

    def _aplicar_personalizacao(self, aparencia, cor_nome):
        ctk.set_appearance_mode(aparencia)
        self.cor_acento, self.cor_acento_hover = self._paletas.get(cor_nome, self._paletas["Verde Nabi"])
        self._atualizar_identidade_visual()

    def _agendar_redesenho_interface(self, event=None):
        if event is not None and event.widget is not self:
            return
        size = (max(1, self.winfo_width()), max(1, self.winfo_height()))
        if not self._startup_reveal_complete:
            self._redimensionamento_tamanho = size
            return
        if size == self._redimensionamento_tamanho:
            return
        self._redimensionamento_tamanho = size
        if self._redimensionamento_after is not None:
            try:
                self.after_cancel(self._redimensionamento_after)
            except Exception:
                pass
        self._redimensionamento_after = self.after(120, self._redesenhar_interface)

    def _redesenhar_interface(self):
        self._redimensionamento_after = None
        try:
            self.update_idletasks()
            tela = getattr(self, "telas", {}).get(getattr(self, "tela_atual", ""))
            manager = getattr(self, "background_manager", None)
            if manager is not None and tela is not None:
                manager.refresh(tela, immediate=True)
            pending = [self]
            while pending:
                widget = pending.pop()
                if widget.winfo_exists() and widget.winfo_viewable():
                    widget.event_generate("<Expose>")
                    pending.extend(widget.winfo_children())
        except tk.TclError:
            logger.exception("Falha ao redesenhar a janela principal após redimensionamento.")

    def _criar_borboleta_fundo(self, parent):
        """Compatibilidade temporária: delega a marca d'água ao gerenciador único."""
        manager = getattr(self, "background_manager", None)
        if manager is None:
            return None
        return manager.attach(parent)

    def _instalar_interacoes_texto_globais(self):
        """Ativa copiar/colar, menu de contexto e seleção em campos e tabelas."""
        self.text_interactions = UniversalTextInteractionManager(self)
        self.text_interactions.install()


    def _instalar_atalhos_globais(self):
        """Ativa os atalhos comuns e define os fallbacks da janela principal."""
        self.nabi_help_context = "dashboard"
        if not hasattr(self, "tela_atual"):
            self.tela_atual = "dashboard"
        self.shortcut_manager = GlobalShortcutManager(self)
        self.shortcut_manager.install()
        self.window_actions = WindowActionController(self)
        self.context_help = ContextHelpController(self)

        self.bind("<<NabiClose>>", self._atalho_fechar_janela_principal, add="+")
        self.bind("<<NabiSearch>>", self._atalho_pesquisar_tela_atual, add="+")
        self.bind("<<NabiHelp>>", self._atalho_ajuda_global, add="+")
        self.bind("<<NabiDelete>>", self._atalho_excluir_tela_atual, add="+")
        self.bind("<<NabiSave>>", self._atalho_salvar_tela_atual, add="+")
        self.bind("<<NabiNew>>", self._atalho_novo_tela_atual, add="+")
        self.bind("<<NabiEdit>>", self._atalho_editar_tela_atual, add="+")

    def _atalho_salvar_tela_atual(self, _event=None):
        # Formulários independentes tratam Ctrl+S pelo WindowActionController.
        # Na janela principal não existe edição inline a ser salva.
        return "break"

    def _atalho_novo_tela_atual(self, _event=None):
        nome_tela = getattr(self, "tela_atual", "")
        if nome_tela == "produtos":
            self.abrir_cadastro_produto()
        elif nome_tela == "clientes":
            metodo = getattr(self, "abrir_cadastro_cliente", None)
            if callable(metodo):
                metodo()
        return "break"

    def _atalho_editar_tela_atual(self, _event=None):
        nome_tela = getattr(self, "tela_atual", "")
        if nome_tela == "produtos":
            self.editar_produto_selecionado()
        elif nome_tela == "clientes":
            metodo = getattr(self, "editar_cliente_selecionado", None)
            if callable(metodo):
                metodo()
        return "break"

    def _atalho_fechar_janela_principal(self, _event=None):
        if getattr(self, "pdv_window", None) is not None:
            try:
                if self.pdv_window.winfo_exists() and self.pdv_window.focus_displayof() is not None:
                    self._fechar_pdv()
                    return "break"
            except Exception:
                pass
        if messagebox.askyesno("Fechar NabiCode", "Deseja realmente fechar o sistema?", parent=self):
            self.destroy()
        return "break"

    def _atalho_pesquisar_tela_atual(self, _event=None):
        candidatos = {
            "produtos": "entry_busca_produto",
            "clientes": "entry_busca_cliente",
            "vendas": "entry_item_venda",
        }
        nome_tela = getattr(self, "tela_atual", "")
        widget = getattr(self, candidatos.get(nome_tela, ""), None)
        if widget is not None:
            try:
                widget.focus_set()
                widget.select_range(0, "end")
                return "break"
            except Exception:
                pass
        return "break"

    def _atalho_excluir_tela_atual(self, _event=None):
        nome_tela = getattr(self, "tela_atual", "")
        if nome_tela == "produtos":
            metodo = getattr(self, "excluir_produto_selecionado", None)
            if callable(metodo):
                metodo()
        elif nome_tela == "clientes":
            metodo = getattr(self, "excluir_cliente_selecionado", None)
            if callable(metodo):
                metodo()
        return "break"

    def _atalho_ajuda_global(self, _event=None):
        self.context_help.show()
        return "break"

    def _servico_licenca(self):
        return cached_instance(self, "_license_service", lambda: LicenseService(obter_config, salvar_config))

    def verificar_bloqueio_expiracao(self):
        status = self._servico_licenca().evaluate()
        if status.invalid_value:
            logger.warning("Configuração de licença inválida detectada: %s", status.reason)
        if status.blocked:
            return self.forcar_tela_bloqueio_inadimplencia()
        if status.days_remaining is not None and status.days_remaining <= 5 and not getattr(self, "_aviso_licenca_exibido", False):
            self._aviso_licenca_exibido = True
            messagebox.showwarning(
                "⚠️ Aviso de Vencimento",
                f"Sua assinatura vence em {status.days_remaining} dia(s)! Realize o pagamento para evitar o bloqueio.",
                parent=self,
            )
        return False

    def _monitorar_licenca(self):
        """Confere durante o uso todas as modalidades reais de bloqueio."""
        status = self._servico_licenca().evaluate()
        if status.invalid_value:
            logger.warning("Expiração exata inválida foi removida da configuração.")
        if status.blocked:
            with startup_modal_scope():
                self.forcar_tela_bloqueio_inadimplencia()
        try:
            window_exists = bool(self.winfo_exists())
        except tk.TclError:
            window_exists = False
        if window_exists:
            self.after(1000, self._monitorar_licenca)

    def forcar_tela_bloqueio_inadimplencia(self):
        """Bloqueia a mesma instância e restaura a raiz após liberação válida."""
        if self._license_dialog_active:
            try:
                if self._license_dialog_window.winfo_exists():
                    self._license_dialog_window.lift()
                    self._license_dialog_window.focus_force()
            except (AttributeError, tk.TclError):
                pass
            return True

        self._license_dialog_active = True
        parent_state = self.state()
        parent_was_withdrawn = parent_state == "withdrawn"
        if parent_was_withdrawn:
            try:
                self.attributes("-alpha", 0.0)
                self.deiconify()
                self.update_idletasks()
            except tk.TclError:
                pass

        bloqueio_win = ctk.CTkToplevel(self)
        self._license_dialog_window = bloqueio_win
        prepare_hidden_toplevel(bloqueio_win)
        bloqueio_win.title("NabiCode — Acesso Bloqueado por Inadimplência")
        bloqueio_win.geometry("450x320")
        bloqueio_win.configure(fg_color="#0d1117")
        bloqueio_win.transient(self)

        bloqueio_win.update_idletasks()
        largura = 450
        altura = 320
        x = (bloqueio_win.winfo_screenwidth() // 2) - (largura // 2)
        y = (bloqueio_win.winfo_screenheight() // 2) - (altura // 2)
        bloqueio_win.geometry(f"{largura}x{altura}+{x}+{y}")

        lbl_aviso = ctk.CTkLabel(bloqueio_win, text="🔒 SISTEMA BLOQUEADO", font=ctk.CTkFont(size=20, weight="bold"), text_color="#ff6b6b")
        lbl_aviso.pack(pady=(25, 10))

        lbl_desc = ctk.CTkLabel(bloqueio_win, text="O período da sua assinatura expirou.\nPara continuar usando o NabiCode, efetue o pagamento\nou digite a senha mestre para liberar o acesso.", font=ctk.CTkFont(size=13), justify="center", text_color="#c9d1d9")
        lbl_desc.pack(padx=20, pady=5)

        entry_senha_bloqueio = ctk.CTkEntry(bloqueio_win, placeholder_text="Digite a senha mestre do suporte...", show="*", height=38)
        entry_senha_bloqueio.pack(padx=30, pady=15, fill="x")
        entry_senha_bloqueio.focus()

        resultado = {"liberado": False, "fechar": False}

        def encerrar_modal():
            try:
                bloqueio_win.grab_release()
            except tk.TclError:
                pass
            try:
                bloqueio_win.destroy()
            except tk.TclError:
                pass

        def tentar_desbloquear():
            if self._servico_licenca().attempt_admin_unlock(
                entry_senha_bloqueio.get(),
                self.security.verify_master_password,
                days=30,
            ):
                resultado["liberado"] = True
                messagebox.showinfo(
                    "Sucesso",
                    "Assinatura renovada com sucesso por 30 dias!",
                    parent=bloqueio_win,
                )
                encerrar_modal()
            else:
                messagebox.showerror("Erro", "Senha incorreta!", parent=bloqueio_win)
                entry_senha_bloqueio.focus_set()

        btn_liberar = ctk.CTkButton(bloqueio_win, text="🔓 Desbloquear com Senha", fg_color="#2ea043", hover_color="#238636", height=40, font=ctk.CTkFont(weight="bold"), command=tentar_desbloquear)
        btn_liberar.pack(padx=30, pady=5, fill="x")

        def fechar_aplicacao_total():
            resultado["fechar"] = True
            encerrar_modal()

        bloqueio_win.protocol("WM_DELETE_WINDOW", fechar_aplicacao_total)
        try:
            bloqueio_win.attributes("-topmost", True)
            bloqueio_win.after(300, lambda: bloqueio_win.attributes("-topmost", False))
        except tk.TclError:
            pass
        reveal_prepared_toplevel_smooth(
            bloqueio_win,
            grab=True,
            focus_widget=entry_senha_bloqueio,
            duration_ms=300,
        )

        try:
            self.wait_window(bloqueio_win)
        finally:
            encerrar_modal()
            self._license_dialog_active = False
            self._license_dialog_window = None

        if resultado["fechar"]:
            self._license_exit_requested = True
            self.destroy()
            return False

        if resultado["liberado"]:
            if self._startup_reveal_complete:
                try:
                    self.deiconify()
                    self.attributes("-alpha", 1.0)
                    self.lift()
                    self.after(80, self.focus_force)
                except tk.TclError:
                    pass
            elif parent_was_withdrawn:
                try:
                    self.withdraw()
                except tk.TclError:
                    pass
            return False

        if parent_was_withdrawn and not self._startup_reveal_complete:
            try:
                self.withdraw()
            except tk.TclError:
                pass
        return True

    def ativar_modo_panico(self, event=None):
        self.destroy()
        return "break"

    def alternar_menu_lateral(self):
        if self.frame_menu.winfo_ismapped():
            self.frame_menu.grid_remove()
            if hasattr(self, 'btn_toggle_menu'):
                self.btn_toggle_menu.configure(text="📂 Menu ➔")
        else:
            self.frame_menu.grid(row=0, column=0, sticky="nsew")
            if hasattr(self, 'btn_toggle_menu'):
                self.btn_toggle_menu.configure(text="📁 Menu ✖")

    def criar_menu_lateral(self):
        self.frame_menu = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#161b22")
        self.frame_menu.grid(row=0, column=0, sticky="nsew")
        
        self.lbl_logo_empresa = ctk.CTkLabel(self.frame_menu, text="Nabi 🦋 Code", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.cor_acento)
        self.lbl_logo_empresa.pack(pady=(20, 25))
        self.lbl_logo_empresa.configure(cursor="hand2")
        self.clicks_dev = 0
        self._ultimo_clique_dev = 0.0
        self.lbl_logo_empresa.bind("<Button-1>", self.gatilho_menu_secreto)
        
        self.card_total = ctk.CTkLabel(self.frame_menu, text="📊 Fichas: 0", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#21262d", text_color="#ffffff", corner_radius=6, padx=8, pady=6, anchor="w")
        self.card_total.pack(pady=4, padx=12, fill="x")

        self.card_bons = ctk.CTkLabel(self.frame_menu, text="🟢 Em Dia: 0", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#1b4721", text_color="#00FF88", corner_radius=6, padx=8, pady=6, anchor="w")
        self.card_bons.pack(pady=4, padx=12, fill="x")

        self.card_devendo = ctk.CTkLabel(self.frame_menu, text="🟡 Devendo: 0 (R$ 0,00)", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#4d4113", text_color="#ffd700", corner_radius=6, padx=8, pady=6, anchor="w")
        self.card_devendo.pack(pady=4, padx=12, fill="x")

        self.card_alerta = ctk.CTkLabel(self.frame_menu, text="🔴 Alerta (>60d): 0 (R$ 0,00)", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#591d1d", text_color="#ff6b6b", corner_radius=6, padx=8, pady=6, anchor="w")
        self.card_alerta.pack(pady=4, padx=12, fill="x")
        
        frame_atalhos = ctk.CTkFrame(self.frame_menu, fg_color="#0d1117", corner_radius=8)
        frame_atalhos.pack(pady=10, padx=12, fill="x")
        
        lbl_atalhos_titulo = ctk.CTkLabel(frame_atalhos, text="⌨️ Atalhos Rápidos:", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffffff")
        lbl_atalhos_titulo.pack(anchor="w", padx=10, pady=(6, 2))
        
        txt_atalhos = (
            "[F1] ➔ Início\n"
            "[F2] ➔ Vendas\n"
            "[F3] ➔ Clientes\n"
            "[F4] ➔ Produtos\n"
            "[F5] ➔ Configs\n"
            "[Ctrl+Shift+P] ➔ Pânico"
        )
        lbl_atalhos_lista = ctk.CTkLabel(frame_atalhos, text=txt_atalhos, font=ctk.CTkFont(size=13, weight="bold"), text_color="#c9d1d9", justify="left")
        lbl_atalhos_lista.pack(anchor="w", padx=10, pady=(0, 6))

        self.frame_favoritos = ctk.CTkFrame(self.frame_menu, fg_color="#0d1117", corner_radius=8)
        self.frame_favoritos.pack(pady=(0, 10), padx=12, fill="x")
        self.lbl_favoritos_titulo = ctk.CTkLabel(
            self.frame_favoritos,
            text="⭐ Favoritos",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff",
        )
        self.lbl_favoritos_titulo.pack(anchor="w", padx=10, pady=(7, 3))
        self.frame_favoritos_itens = ctk.CTkFrame(self.frame_favoritos, fg_color="transparent")
        self.frame_favoritos_itens.pack(fill="x", padx=6, pady=(0, 7))
        self._reconstruir_menu_favoritos()

        btn_robo = ctk.CTkButton(self.frame_menu, text="🆘 Central de Ajuda", fg_color="#1f6feb", hover_color="#1158c7", height=32, font=ctk.CTkFont(size=12, weight="bold"), command=self.abrir_robo_ajuda)
        btn_robo.pack(pady=5, padx=12, fill="x")

        btn_suporte = ctk.CTkButton(self.frame_menu, text="📲 Suporte", fg_color="#2ea043", hover_color="#238636", height=32, font=ctk.CTkFont(size=12, weight="bold"), command=self.abrir_chamado_suporte)
        btn_suporte.pack(pady=(0, 5), padx=12, fill="x")

        btn_panico = ctk.CTkButton(
            self.frame_menu,
            text="⚠ Pânico  [Ctrl+Shift+P]",
            fg_color="#b62324",
            hover_color="#8f1d1e",
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.ativar_modo_panico,
        )
        btn_panico.pack(pady=(0, 5), padx=12, fill="x")

        lbl_rodape_dev = ctk.CTkLabel(self.frame_menu, text="Nabi 🦋 Code", font=ctk.CTkFont(size=10), text_color="#8b949e", cursor="hand2")
        lbl_rodape_dev.pack(side="bottom", pady=15)

    def criar_telas(self):
        self.container_telas = ctk.CTkFrame(self, fg_color="transparent")
        self.container_telas.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        LayoutManager.configure_root(self.container_telas)
        self.container_telas.grid_rowconfigure(0, weight=0)
        self.container_telas.grid_rowconfigure(1, weight=1)

        self.frame_navegacao_persistente = ctk.CTkFrame(self.container_telas, fg_color="transparent")
        self.frame_navegacao_persistente.grid(row=0, column=0, sticky="ew")
        self.criar_cabecalho_e_botoes(self.frame_navegacao_persistente)

        self.container_conteudo_telas = ctk.CTkFrame(self.container_telas, fg_color="transparent")
        self.container_conteudo_telas.grid(row=1, column=0, sticky="nsew")
        LayoutManager.configure_root(self.container_conteudo_telas)

        fundo = self.preferencias_interface
        self.background_manager = BackgroundManager(
            logo_path=obter_config("impressao_logo_path") or None,
            settings=BackgroundSettings(
                enabled=fundo["background_enabled"],
                opacity=fundo["background_opacity"],
                scale=fundo["background_scale"],
                position=fundo["background_position"],
            ),
        )

        # Construir todos os módulos aqui bloqueava a inicialização por vários
        # segundos e obrigava o Tk a renderizar telas que talvez nem fossem usadas.
        # O roteador mantém uma única instância de cada tela e a cria no primeiro
        # acesso. O dashboard continua imediato por ser o destino inicial habitual.
        self.telas = {}
        self._fabricas_telas = {
            "dashboard": self.tela_dashboard,
            "clientes": self.tela_clientes,
            "produtos": self.tela_produtos,
            "financeiro": self.tela_financeiro,
            "caixa": self.tela_caixa,
            "compras": self.tela_compras,
            "relatorios": self.tela_relatorios,
            "configs": self.tela_configs,
        }
        self._garantir_tela_criada("dashboard")

    def _garantir_tela_criada(self, nome):
        tela = self.telas.get(nome)
        if tela is not None:
            return tela
        fabrica = self._fabricas_telas.get(nome)
        if fabrica is None:
            raise KeyError(f"Tela desconhecida: {nome}")
        inicio = perf_counter()
        tela = fabrica(self.container_conteudo_telas)
        self.telas[nome] = tela
        self.background_manager.attach(tela)
        mark_startup(
            "ui_screen_created",
            screen=nome,
            duration_ms=round((perf_counter() - inicio) * 1000, 2),
        )
        return tela

    def mostrar_tela(self, nome):
        if not self._autorizar("financeiro" if nome == "caixa" else nome, "view"):
            return
        if nome == "vendas":
            self.abrir_pdv_independente()
            return
        self._garantir_tela_criada(nome)
        self._preparar_tela_para_exibicao(nome)
        for btn_nome, btn in self.botoes_topo.items():
            if btn_nome == nome:
                btn.configure(border_width=3, border_color="#ffffff")
            else:
                btn.configure(border_width=0)
                
        self._atualizar_identidade_visual()
                
        self.telas[nome].tkraise()
        self.tela_atual = nome

    def _preparar_tela_para_exibicao(self, nome):
        """Atualiza o destino mantendo a tela atual levantada."""
        self.atualizar_resumo_lateral()
        if nome == "dashboard":
            self.carregar_historico_dia()
        elif nome == "clientes":
            self.carregar_clientes()
        elif nome == "produtos":
            self.carregar_produtos()
        elif nome == "financeiro":
            self.carregar_financeiro()
        elif nome == "caixa":
            self._log_caixa_runtime("CASH_SCREEN_OPEN")
            self.atualizar_tela_caixa()
        elif nome == "compras":
            self.carregar_compras()
        elif nome == "relatorios":
            self.gerar_relatorio_ui()

    def _comandos_pesquisa_global(self):
        comandos = (
            CommandDefinition("dashboard", "Abrir Início", ("inicio", "painel", "dashboard")),
            CommandDefinition("vendas", "Abrir Vendas / PDV", ("venda", "caixa", "pdv")),
            CommandDefinition("clientes", "Abrir Clientes", ("cliente", "fichas", "crediario")),
            CommandDefinition("produtos", "Abrir Produtos", ("produto", "estoque", "cadastro")),
            CommandDefinition("financeiro", "Abrir Financeiro", ("financeiro", "caixa", "dre", "contas", "recorrencia")),
            CommandDefinition("caixa", "Abrir Caixa", ("caixa", "gaveta", "sangria", "suprimento", "fechamento")),
            CommandDefinition("relatorios", "Abrir Relatórios", ("relatorio", "dashboard", "grafico", "indicador", "exportar", "pdf", "excel")),
            CommandDefinition("fiscal_config", "Configurar Fiscal Oficial", ("fiscal", "nfe", "nfce", "sefaz", "certificado", "a1")),
            CommandDefinition("fiscal_documents", "Abrir Documentos Fiscais", ("documentos", "fiscal", "xml", "danfe", "contabilidade", "notas")),
            CommandDefinition("configs", "Abrir Configurações", ("configuracao", "preferencias", "sistema")),
            CommandDefinition("new_product", "Cadastrar novo produto", ("novo", "produto", "cadastro")),
            CommandDefinition("new_client", "Cadastrar novo cliente", ("novo", "cliente", "cadastro")),
            CommandDefinition("import_xml", "Importar XML de NF-e", ("xml", "nota", "nfe", "entrada")),
            CommandDefinition("nfe_history", "Abrir notas importadas", ("historico", "nfe", "nota", "excluir")),
            CommandDefinition("nfe_return", "Criar NF-e de devolução", ("devolucao", "nota", "nfe")),
            CommandDefinition("collections", "Abrir Central de Cobranças", ("cobranca", "promissoria", "inadimplencia")),
            CommandDefinition("product_aux", "Abrir marcas, fornecedores e unidades", ("marca", "fornecedor", "unidade")),
        )
        mapa = {"fiscal_config": "fiscal", "fiscal_documents": "fiscal", "new_product": "produtos", "new_client": "clientes", "import_xml": "produtos", "nfe_history": "produtos", "nfe_return": "produtos", "collections": "clientes", "product_aux": "produtos"}
        comandos_fiscais = {"fiscal_config", "fiscal_documents", "import_xml", "nfe_history", "nfe_return"}
        return tuple(
            cmd for cmd in comandos
            if (modo_fiscal_ativo() or cmd.action not in comandos_fiscais)
            and self.security.require(mapa.get(cmd.action, cmd.action), "view")
        )

    def abrir_pesquisa_global(self):
        try:
            janela_existente = getattr(self, "_janela_pesquisa_global", None)
            if janela_existente is not None and janela_existente.window.winfo_exists():
                janela_existente.window.lift()
                janela_existente.entry.focus_set()
                return
        except Exception:
            self._janela_pesquisa_global = None

        engine = GlobalSearchEngine(conectar_banco, self._comandos_pesquisa_global())
        self._janela_pesquisa_global = CommandPalette(
            self,
            engine,
            self._executar_resultado_pesquisa_global,
            accent_color=self.cor_acento,
        )

    def _executar_resultado_pesquisa_global(self, resultado: SearchResult):
        self._janela_pesquisa_global = None
        acao = resultado.action
        if acao in {"dashboard", "clientes", "produtos", "financeiro", "caixa", "compras", "relatorios", "configs"}:
            self.mostrar_tela(acao)
            return
        if acao == "vendas":
            self.abrir_pdv_independente()
            return
        if acao == "fiscal_config":
            if not modo_fiscal_ativo():
                messagebox.showinfo("Modo Comercial", "Ative o modo Fiscal nas configurações para acessar recursos fiscais.", parent=self)
                return
            self.abrir_configuracao_fiscal()
            return
        if acao == "fiscal_documents":
            self.abrir_central_fiscal()
            return
        if acao == "new_product":
            self.abrir_cadastro_produto()
            return
        if acao == "new_client":
            self.abrir_cadastro_cliente()
            return
        if acao == "import_xml":
            self.abrir_importacao_xml()
            return
        if acao == "nfe_history" or acao == "open_nfe_history":
            self.abrir_historico_nfe_importadas()
            return
        if acao == "nfe_return":
            self.abrir_assistente_devolucao()
            return
        if acao == "collections" or acao == "open_financial":
            self.abrir_central_cobrancas()
            return
        if acao == "product_aux" or acao == "open_supplier":
            self.abrir_cadastros_auxiliares()
            return
        if acao == "open_product":
            produto_id = int(resultado.payload.get("product_id", 0) or 0)
            if produto_id:
                self.abrir_cadastro_produto(produto_id)
            return
        if acao == "open_client":
            nome = str(resultado.payload.get("client_name", "") or resultado.title).strip()
            self.mostrar_tela("clientes")
            if hasattr(self, "entry_busca_cliente"):
                self.entry_busca_cliente.delete(0, "end")
                self.entry_busca_cliente.insert(0, nome)
                self.carregar_clientes(nome, manter_pagina=False)
            return

    def atualizar_resumo_lateral(self):
        """Atualiza os cartões laterais usando o repositório consolidado."""
        resumo = self._repositorio_dashboard().client_summary()
        self.card_total.configure(text=f"📊 Total de Fichas: {resumo.total_records}")
        self.card_bons.configure(text=f"🟢 Em Dia (Bons): {resumo.current_count}")
        self.card_devendo.configure(text=f"🟡 Devendo ({resumo.owing_count}): R$ {resumo.owing_value:.2f}")
        self.card_alerta.configure(text=f"🔴 Alerta >60d ({resumo.alert_count}): R$ {resumo.alert_value:.2f}")

    def criar_cabecalho_e_botoes(self, parent):
        frame_topo_barra = ctk.CTkFrame(parent, fg_color="transparent")
        frame_topo_barra.pack(fill="x", pady=(10, 10), padx=20)
        
        self.btn_toggle_menu = ctk.CTkButton(frame_topo_barra, text="📁 Menu ✖", width=110, height=35, fg_color="#161b22", hover_color="#30363d", command=self.alternar_menu_lateral)
        self.btn_toggle_menu.pack(side="left")
        
        nome_loja_atual = obter_config("nome_loja")
        self.lbl_nome_loja_topo = ctk.CTkLabel(frame_topo_barra, text=nome_loja_atual.upper(), font=ctk.CTkFont(size=22, weight="bold"), text_color=self.cor_acento)
        self.lbl_nome_loja_topo.pack(side="left", expand=True)
        self._labels_nome_loja.append(self.lbl_nome_loja_topo)
        ctk.CTkButton(
            frame_topo_barra, text="🔔 Histórico", width=105, height=35,
            fg_color="#161b22", hover_color="#30363d",
            command=self.abrir_historico_notificacoes,
        ).pack(side="right")

        frame_centralizador = ctk.CTkFrame(parent, fg_color="transparent")
        frame_centralizador.pack(fill="x", pady=10, padx=20)

        estilo_btn = {"height": 42, "corner_radius": 12, "font": ctk.CTkFont(size=13, weight="bold")}
        
        self.botoes_topo = {}
        
        btn_dash = ctk.CTkButton(frame_centralizador, text="📊 [F1] Início", fg_color="#1f6feb", hover_color="#1158c7", **estilo_btn)
        btn_dash.configure(command=lambda: self.mostrar_tela("dashboard"))
        self.botoes_topo["dashboard"] = btn_dash
        
        btn_vendas = ctk.CTkButton(frame_centralizador, text="🛒 [F2] Vendas", fg_color="#2ea043", hover_color="#238636", **estilo_btn)
        btn_vendas.configure(command=self.abrir_pdv_independente)
        self.botoes_topo["vendas"] = btn_vendas
        
        btn_clientes = ctk.CTkButton(frame_centralizador, text="👥 [F3] Clientes", fg_color="#8957e5", hover_color="#6e40c9", **estilo_btn)
        btn_clientes.configure(command=lambda: self.mostrar_tela("clientes"))
        self.botoes_topo["clientes"] = btn_clientes
        
        btn_produtos = ctk.CTkButton(frame_centralizador, text="📦 [F4] Produtos", fg_color="#bf8700", hover_color="#9e6a03", **estilo_btn)
        btn_produtos.configure(command=lambda: self.mostrar_tela("produtos"))
        self.botoes_topo["produtos"] = btn_produtos

        btn_financeiro = ctk.CTkButton(frame_centralizador, text="💰 Financeiro", fg_color="#0f766e", hover_color="#115e59", **estilo_btn)
        btn_financeiro.configure(command=lambda: self.mostrar_tela("financeiro"))
        self.botoes_topo["financeiro"] = btn_financeiro

        btn_caixa = ctk.CTkButton(frame_centralizador, text="💵 Caixa", fg_color="#a16207", hover_color="#854d0e", **estilo_btn)
        btn_caixa.configure(command=lambda: self.mostrar_tela("caixa"))
        self.botoes_topo["caixa"] = btn_caixa

        btn_compras = ctk.CTkButton(frame_centralizador, text="📥 Compras", fg_color="#7c3aed", hover_color="#6d28d9", **estilo_btn)
        btn_compras.configure(command=lambda: self.mostrar_tela("compras"))
        self.botoes_topo["compras"] = btn_compras

        btn_relatorios = ctk.CTkButton(frame_centralizador, text="📈 Relatórios", fg_color="#0369a1", hover_color="#075985", **estilo_btn)
        btn_relatorios.configure(command=lambda: self.mostrar_tela("relatorios"))
        self.botoes_topo["relatorios"] = btn_relatorios

        btn_configs = ctk.CTkButton(frame_centralizador, text="⚙️ [F5] Configs", fg_color="#da3633", hover_color="#b62324", **estilo_btn)
        btn_configs.configure(command=lambda: self.mostrar_tela("configs"))
        self.botoes_topo["configs"] = btn_configs
        for coluna in range(5):
            frame_centralizador.grid_columnconfigure(coluna, weight=1, uniform="navegacao_topo")
        for module_id, botao in self.botoes_topo.items():
            botao.bind("<Button-3>", lambda event, mid=module_id: self._abrir_menu_favorito_modulo(event, mid), add="+")
        self._grupos_botoes_topo.append(self.botoes_topo)

    def _chave_usuario_preferencias(self, username=None):
        if username is None:
            sessao = getattr(getattr(self, "security", None), "session", None)
            username = getattr(getattr(sessao, "user", None), "username", "")
        return UIPreferencesService.user_key(username)

    def _carregar_preferencias_usuario(self, username):
        chave = self._chave_usuario_preferencias(username)
        usuarios = CORE_CONFIG.get("interface_usuarios", {})
        if not isinstance(usuarios, dict):
            usuarios = {}
        dados = usuarios.get(chave)
        if not isinstance(dados, dict):
            base = UIPreferencesService.normalize(CORE_CONFIG.get("interface", {}))
            base["favorites"] = []
            dados = base
        self.preferencias_interface = UIPreferencesService.normalize(dados)
        self.perfil_interface = UIPreferencesService.build_profile(self.preferencias_interface)
        self._usuario_preferencias_interface = chave
        usuarios[chave] = self.preferencias_interface
        CORE_CONFIG.set("interface_usuarios", usuarios)

    def _aplicar_preferencias_usuario_autenticado(self, username):
        self._carregar_preferencias_usuario(username)
        self._aplicar_visibilidade_navegacao()
        self._reconstruir_menu_favoritos()
        self._sincronizar_controles_favoritos_config()

    def _persistir_preferencias_interface(self):
        self.preferencias_interface = UIPreferencesService.normalize(self.preferencias_interface)
        self.perfil_interface = UIPreferencesService.build_profile(self.preferencias_interface)
        chave = self._usuario_preferencias_interface
        if chave is None:
            try:
                chave = self._chave_usuario_preferencias()
            except ValueError:
                return
        usuarios = CORE_CONFIG.get("interface_usuarios", {})
        if not isinstance(usuarios, dict):
            usuarios = {}
        usuarios[chave] = self.preferencias_interface
        CORE_CONFIG.set("interface_usuarios", usuarios)

    def _abrir_modulo_favorito(self, module_id):
        if module_id == "vendas":
            self.abrir_pdv_independente()
            return
        if module_id in getattr(self, "telas", {}):
            self.mostrar_tela(module_id)

    def _abrir_menu_favorito_modulo(self, event, module_id):
        favoritos = set(UIPreferencesService.favorites(self.preferencias_interface))
        menu = tk.Menu(self, tearoff=0)
        texto = "Remover dos favoritos" if module_id in favoritos else "Adicionar aos favoritos"
        menu.add_command(label=texto, command=lambda: self._alternar_favorito_modulo(module_id))
        menu.tk_popup(event.x_root, event.y_root)

    def _alternar_favorito_modulo(self, module_id):
        self.preferencias_interface = UIPreferencesService.toggle_favorite(self.preferencias_interface, module_id)
        self._persistir_preferencias_interface()
        self._reconstruir_menu_favoritos()
        self._sincronizar_controles_favoritos_config()

    def _mover_favorito_modulo(self, module_id, offset):
        self.preferencias_interface = UIPreferencesService.move_favorite(self.preferencias_interface, module_id, offset)
        self._persistir_preferencias_interface()
        self._reconstruir_menu_favoritos()
        self._sincronizar_controles_favoritos_config(module_id)

    def _abrir_favorito_por_posicao(self, posicao):
        favoritos = UIPreferencesService.favorites(self.preferencias_interface)
        indice = int(posicao) - 1
        if 0 <= indice < len(favoritos):
            self._abrir_modulo_favorito(favoritos[indice])
            return "break"
        return None

    def _reconstruir_menu_favoritos(self):
        frame = getattr(self, "frame_favoritos_itens", None)
        if frame is None:
            return
        for widget in frame.winfo_children():
            widget.destroy()
        self._botoes_favoritos = []
        favoritos = UIPreferencesService.favorites(self.preferencias_interface)
        if not favoritos:
            ctk.CTkLabel(frame, text="Nenhum módulo favoritado", text_color="#8b949e", anchor="w").pack(fill="x", padx=4, pady=3)
            return
        for indice, module_id in enumerate(favoritos[:9], start=1):
            titulo = UIPreferencesService.MODULE_LABELS[module_id]
            botao = ctk.CTkButton(
                frame,
                text=f"Alt+{indice}  {titulo}",
                height=30,
                anchor="w",
                fg_color="#21262d",
                hover_color="#30363d",
                command=lambda mid=module_id: self._abrir_modulo_favorito(mid),
            )
            botao.pack(fill="x", pady=2)
            botao.bind("<Button-3>", lambda event, mid=module_id: self._abrir_menu_favorito_modulo(event, mid), add="+")
            self._botoes_favoritos.append(botao)

    def _sincronizar_controles_favoritos_config(self, selecionado=None):
        combo = getattr(self, "combo_favoritos_config", None)
        if combo is None:
            return
        favoritos = UIPreferencesService.favorites(self.preferencias_interface)
        valores = [f"{indice}. {UIPreferencesService.MODULE_LABELS[module_id]}" for indice, module_id in enumerate(favoritos, 1)]
        combo.configure(values=valores or ["Nenhum favorito"])
        if selecionado in favoritos:
            combo.set(valores[favoritos.index(selecionado)])
        else:
            combo.set(valores[0] if valores else "Nenhum favorito")

    def _modulo_favorito_selecionado_config(self):
        combo = getattr(self, "combo_favoritos_config", None)
        if combo is None:
            return None
        valor = combo.get().strip()
        if not valor or valor == "Nenhum favorito":
            return None
        try:
            indice = int(valor.split(".", 1)[0]) - 1
        except (ValueError, IndexError):
            return None
        favoritos = UIPreferencesService.favorites(self.preferencias_interface)
        return favoritos[indice] if 0 <= indice < len(favoritos) else None

    def _mover_favorito_config(self, offset):
        module_id = self._modulo_favorito_selecionado_config()
        if module_id:
            self._mover_favorito_modulo(module_id, offset)

    def _remover_favorito_config(self):
        module_id = self._modulo_favorito_selecionado_config()
        if module_id:
            self._alternar_favorito_modulo(module_id)

    def _aplicar_visibilidade_navegacao(self):
        """Mostra somente os módulos permitidos pelo modo e espaço de trabalho."""
        for grupo in self._grupos_botoes_topo:
            for botao in grupo.values():
                botao.grid_forget()
            for nome, linha, coluna in UIPreferencesService.navigation_positions(
                self.perfil_interface.visible_modules,
                columns=5,
            ):
                botao = grupo.get(nome)
                if botao is not None:
                    botao.grid(
                        row=linha,
                        column=coluna,
                        padx=4,
                        pady=4,
                        sticky="ew",
                    )

    def _salvar_preferencias_interface(self):
        dados = UIPreferencesService.normalize({
            "mode": self.combo_modo_interface.get(),
            "workspace": self.combo_espaco_interface.get(),
            "density": self.combo_densidade_interface.get(),
            "theme": self.combo_tema_oficial.get(),
            "adaptive_menu": bool(self.var_menu_adaptativo.get()),
            "custom_navigation": bool(self.var_navegacao_personalizada.get()) if hasattr(self, "var_navegacao_personalizada") else self.preferencias_interface.get("custom_navigation", False),
            "navigation_modules": [
                module_id for module_id, var in self.vars_modulos_navegacao.items() if bool(var.get())
            ] if hasattr(self, "vars_modulos_navegacao") else self.preferencias_interface.get("navigation_modules", list(UIPreferencesService.MODULE_ORDER)),
            "dashboard_widgets": [
                widget_id for widget_id, var in self.vars_dashboard_widgets.items() if bool(var.get())
            ] if hasattr(self, "vars_dashboard_widgets") else self.preferencias_interface.get("dashboard_widgets", []),
            "favorites": self.preferencias_interface.get("favorites", []),
            "background_enabled": bool(self.var_background_enabled.get()) if hasattr(self, "var_background_enabled") else self.preferencias_interface.get("background_enabled", True),
            "background_opacity": float(self.slider_background_opacity.get()) if hasattr(self, "slider_background_opacity") else self.preferencias_interface.get("background_opacity", 0.10),
            "background_scale": self.combo_background_scale.get() if hasattr(self, "combo_background_scale") else self.preferencias_interface.get("background_scale", "automática"),
            "background_position": self.combo_background_position.get() if hasattr(self, "combo_background_position") else self.preferencias_interface.get("background_position", "centro"),
        })
        self.preferencias_interface = dados
        self.perfil_interface = UIPreferencesService.build_profile(dados)
        self._persistir_preferencias_interface()
        manager = getattr(self, "background_manager", None)
        if manager is not None:
            manager.set_enabled(dados["background_enabled"])
            manager.set_opacity(dados["background_opacity"])
            manager.set_scale(dados["background_scale"])
            manager.set_position(dados["background_position"])
            manager.set_logo_path(obter_config("impressao_logo_path") or None)

    def adicionar_rodape_status(self, parent):
        frame_rodape = ctk.CTkFrame(parent, fg_color="transparent")
        frame_rodape.pack(side="bottom", fill="x", pady=(5, 5), padx=20)
        
        card_info = ctk.CTkLabel(frame_rodape, text="⚡ Sistema Operacional Estável & Seguro  |  💾 Backup diário configurável", font=ctk.CTkFont(size=11), fg_color="#161b22", text_color=self.cor_acento, corner_radius=6, padx=10, pady=4)
        card_info.pack(fill="x")
        self._widgets_acento.append(card_info)

    def tela_dashboard(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")

        self.adicionar_rodape_status(frame)

        scroll_dashboard = BidirectionalScrollableFrame(frame, fg_color="#161b22", corner_radius=12, content_width=1180)
        scroll_dashboard.pack(fill="both", expand=True, padx=20, pady=5)
        conteudo_frame = scroll_dashboard.content

        widgets = UIPreferencesService.dashboard_widgets(self.preferencias_interface)

        if "resumo" in widgets:
            frame_totais_dia = ctk.CTkFrame(conteudo_frame, fg_color="#0d1117", corner_radius=10)
            frame_totais_dia.pack(fill="x", padx=15, pady=(15, 8), ipadx=10, ipady=8)
            self.lbl_vendas_dia = ctk.CTkLabel(frame_totais_dia, text="🛒 Vendas Hoje: R$ 0.00", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00FF88")
            self.lbl_vendas_dia.pack(side="left", expand=True, padx=10)
            self.lbl_recebidos_dia = ctk.CTkLabel(frame_totais_dia, text="💰 Recebido Hoje: R$ 0.00", font=ctk.CTkFont(size=14, weight="bold"), text_color="#388bfd")
            self.lbl_recebidos_dia.pack(side="left", expand=True, padx=10)
            self.lbl_mov_total_dia = ctk.CTkLabel(frame_totais_dia, text="📊 Movimento Total: R$ 0.00", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffd700")
            self.lbl_mov_total_dia.pack(side="left", expand=True, padx=10)

        indicadores = ctk.CTkFrame(conteudo_frame, fg_color="transparent")
        mostrar_indicadores = False
        if "cobrancas" in widgets:
            mostrar_indicadores = True
            card = ctk.CTkFrame(indicadores, fg_color="#0d1117", corner_radius=10)
            card.pack(side="left", fill="x", expand=True, padx=(0, 4))
            ctk.CTkLabel(card, text="Cobranças", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f2cc60").pack(anchor="w", padx=12, pady=(10, 2))
            self.lbl_dashboard_cobrancas = ctk.CTkLabel(card, text="Carregando...", font=ctk.CTkFont(size=16, weight="bold"))
            self.lbl_dashboard_cobrancas.pack(anchor="w", padx=12, pady=(0, 10))
        if "produtos" in widgets:
            mostrar_indicadores = True
            card = ctk.CTkFrame(indicadores, fg_color="#0d1117", corner_radius=10)
            card.pack(side="left", fill="x", expand=True, padx=(4, 0))
            ctk.CTkLabel(card, text="Produtos", font=ctk.CTkFont(size=13, weight="bold"), text_color="#58a6ff").pack(anchor="w", padx=12, pady=(10, 2))
            self.lbl_dashboard_produtos = ctk.CTkLabel(card, text="Carregando...", font=ctk.CTkFont(size=16, weight="bold"))
            self.lbl_dashboard_produtos.pack(anchor="w", padx=12, pady=(0, 10))
        if mostrar_indicadores:
            indicadores.pack(fill="x", padx=15, pady=4)

        if "historico" in widgets:
            frame_topo_tabela_dash = ctk.CTkFrame(conteudo_frame, fg_color="transparent")
            frame_topo_tabela_dash.pack(fill="x", padx=15, pady=(10, 2))
            ctk.CTkLabel(frame_topo_tabela_dash, text="📊 Histórico de Movimentações do Dia", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffffff").pack(side="left")
            ctk.CTkButton(frame_topo_tabela_dash, text="✏️ Editar", fg_color="#1f6feb", hover_color="#1158c7", height=30, width=85, font=ctk.CTkFont(size=12, weight="bold"), command=self.disparar_edicao_dash).pack(side="right")

            tabela_dash_frame = ctk.CTkFrame(conteudo_frame, fg_color="transparent")
            tabela_dash_frame.pack(fill="both", expand=True, padx=15, pady=5)
            self.tabela_dash = ttk.Treeview(tabela_dash_frame, columns=("ID", "Hora", "Cliente", "Tipo", "Descrição", "Valor"), show="headings", height=12)
            for coluna, titulo in (("ID", "ID"), ("Hora", "Horário"), ("Cliente", "Cliente"), ("Tipo", "Tipo"), ("Descrição", "Descrição / Produto"), ("Valor", "Valor")):
                self.tabela_dash.heading(coluna, text=titulo)
            self.tabela_dash.column("ID", width=45, anchor="center")
            self.tabela_dash.column("Hora", width=80, anchor="center")
            self.tabela_dash.column("Cliente", width=185, minwidth=130, anchor="w", stretch=True)
            self.tabela_dash.column("Tipo", width=90, minwidth=75, anchor="center", stretch=False)
            self.tabela_dash.column("Descrição", width=320, minwidth=220, anchor="w", stretch=True)
            self.tabela_dash.column("Valor", width=105, minwidth=90, anchor="e", stretch=False)
            self.tabela_dash.pack(fill="both", expand=True, pady=(0, 10))
            self.tabela_dash.bind("<Double-1>", self.editar_movimentacao_dash)
            self.tabela_dash.bind("<Button-3>", self.abrir_menu_contexto_historico)

        return frame

    def carregar_painel_atividades(self):
        if not hasattr(self, "tabela_atividades"):
            return
        periodo_texto = self.combo_atividade_periodo.get() if hasattr(self, "combo_atividade_periodo") else "30 dias"
        dias = {"7 dias": 7, "30 dias": 30, "90 dias": 90, "Todos": 0}.get(periodo_texto, 30)
        modulo = self.combo_atividade_modulo.get() if hasattr(self, "combo_atividade_modulo") else "Todos"
        modulo = "" if modulo == "Todos" else modulo
        usuario = self.combo_atividade_usuario.get() if hasattr(self, "combo_atividade_usuario") else "Todos"
        usuario = "" if usuario == "Todos" else usuario
        service = ActivityService(
            conectar_banco,
            backup_directory=obter_config("pasta_backup_local") or BACKUP_DIR,
            log_directory=LOG_DIR,
        )
        atividades = service.list_activities(
            days=dias, module=modulo, user=usuario,
            allowed_modules=self._modulos_atividade_permitidos(), limit=150,
        )
        self._atividades_dashboard = {}
        for item in self.tabela_atividades.get_children():
            self.tabela_atividades.delete(item)
        for indice, atividade in enumerate(atividades):
            iid = f"atividade_{indice}"
            self._atividades_dashboard[iid] = atividade
            data = atividade.occurred_at.replace("T", " ")[:19] if atividade.occurred_at else "Sem data"
            self.tabela_atividades.insert("", "end", iid=iid, values=(data, atividade.module, atividade.kind, atividade.description, atividade.user))

    def _modulos_atividade_permitidos(self):
        permissoes = {
            "Vendas": ("vendas", "view"),
            "Clientes": ("clientes", "view"),
            "Produtos": ("produtos", "view"),
            "Estoque": ("produtos", "view"),
            "XML": ("produtos", "view"),
            "Financeiro": ("financeiro", "view"),
            "Backup": ("technical", "view"),
            "Sistema": ("technical", "view"),
        }
        return {nome for nome, (modulo, acao) in permissoes.items() if self.security.require(modulo, acao)}

    def _agendar_atualizacao_painel_atividades(self):
        anterior = getattr(self, "_atividade_after_id", None)
        if anterior:
            try:
                self.after_cancel(anterior)
            except Exception:
                pass
        self._atividade_after_id = self.after(60000, self._atualizar_painel_atividades_automaticamente)

    def _atualizar_painel_atividades_automaticamente(self):
        self._atividade_after_id = None
        try:
            if self.security.session and hasattr(self, "tabela_atividades") and self.tabela_atividades.winfo_exists():
                self.carregar_painel_atividades()
        finally:
            self._agendar_atualizacao_painel_atividades()

    def abrir_atividade_selecionada(self, _event=None):
        if not hasattr(self, "tabela_atividades"):
            return
        selecionados = self.tabela_atividades.selection()
        if not selecionados:
            return
        atividade = getattr(self, "_atividades_dashboard", {}).get(selecionados[0])
        if atividade is None:
            return
        permissoes = {
            "open_product": ("produtos", "view"),
            "open_client": ("clientes", "view"),
            "open_nfe_history": ("produtos", "view"),
            "open_movement": ("vendas", "view"),
            "open_finance": ("financeiro", "view"),
        }
        modulo_acao = permissoes.get(atividade.action)
        if modulo_acao and not self._autorizar(*modulo_acao):
            return
        try:
            if atividade.action == "open_product" and atividade.record_id:
                self.abrir_cadastro_produto(int(atividade.record_id))
            elif atividade.action == "open_client" and atividade.record_id:
                self.abrir_historico_cliente(int(atividade.record_id))
            elif atividade.action == "open_nfe_history":
                self.abrir_historico_nfe_importadas()
            elif atividade.action == "open_movement" and atividade.record_id:
                self.abrir_janela_edicao_movimento(int(atividade.record_id))
            elif atividade.action == "open_finance":
                self.mostrar_tela("financeiro")
        except (TypeError, ValueError):
            return

    def _atualizar_indicadores_dashboard(self):
        indicadores = self._repositorio_dashboard().indicators()
        if hasattr(self, "lbl_dashboard_cobrancas"):
            self.lbl_dashboard_cobrancas.configure(
                text=f"{indicadores.overdue_count} vencidas • R$ {indicadores.overdue_value:.2f}"
            )
        if hasattr(self, "lbl_dashboard_produtos"):
            if indicadores.active_products is None:
                self.lbl_dashboard_produtos.configure(text="Cadastro ainda não disponível")
            else:
                self.lbl_dashboard_produtos.configure(text=f"{indicadores.active_products} produtos ativos")

    def carregar_historico_dia(self):
        self._atualizar_indicadores_dashboard()
        self.carregar_painel_atividades()
        if not hasattr(self, 'tabela_dash'):
            return
        for row in self.tabela_dash.get_children():
            self.tabela_dash.delete(row)

        historico = self._repositorio_dashboard().day_history()
        for movimento in historico.movements:
            hora = movimento.timestamp.split(" ")[1] if " " in movimento.timestamp else movimento.timestamp
            self.tabela_dash.insert(
                "", "end", iid=str(movimento.movement_id),
                values=(
                    movimento.movement_id,
                    hora,
                    movimento.customer_name,
                    movimento.movement_type,
                    movimento.description,
                    f"R$ {movimento.value:.2f}",
                ),
            )

        if hasattr(self, 'lbl_vendas_dia'):
            self.lbl_vendas_dia.configure(text=f"🛒 Vendas Hoje: R$ {historico.sales_total:.2f}")
            self.lbl_recebidos_dia.configure(text=f"💰 Recebido Hoje: R$ {historico.received_total:.2f}")
            self.lbl_mov_total_dia.configure(text=f"📊 Movimento Total: R$ {historico.movement_total:.2f}")

    def _agendar_pergunta_abertura_caixa(self):
        """Abre a pergunta de caixa somente depois que a janela raiz estiver visível."""
        self._cash_startup_after_id = None
        if self._cash_startup_check_done:
            return
        if not self._startup_reveal_complete:
            self._cash_startup_after_id = self.after(250, self._agendar_pergunta_abertura_caixa)
            return
        self._cash_startup_check_done = True
        self._log_caixa_runtime("CASH_STARTUP_CHECK")
        try:
            self._garantir_janela_principal_visivel()
            self.perguntar_abertura_caixa()
        except Exception:
            logger.exception("Falha ao abrir a pergunta de abertura do caixa.")
            self._garantir_janela_principal_visivel()

    @staticmethod
    def _terminal_caixa():
        return socket.gethostname().strip().upper() or "TERMINAL_LOCAL"

    def _usuario_caixa(self):
        sessao = getattr(getattr(self, "security", None), "session", None)
        return getattr(getattr(sessao, "user", None), "username", "") or "Sistema"

    @staticmethod
    def _log_caixa_runtime(evento, **detalhes):
        payload = " ".join(f"{chave}={valor}" for chave, valor in detalhes.items())
        logger.info("%s%s", evento, f" {payload}" if payload else "")

    def _fechar_modal_caixa(self, win, evento="CASH_MODAL_CLOSE"):
        modal_type = str(getattr(win, "_cash_modal_type", "CAIXA"))
        try:
            if win.grab_current() == win:
                win.grab_release()
        except tk.TclError:
            pass
        try:
            win.unbind("<Escape>")
        except tk.TclError:
            pass
        refs = getattr(self, "_cash_modal_refs", {})
        if refs.get(modal_type) is win:
            refs.pop(modal_type, None)
        try:
            if win.winfo_exists():
                win.destroy()
        except tk.TclError:
            pass
        self._log_caixa_runtime(evento)
        try:
            self.lift(); self.focus_set()
        except tk.TclError:
            pass

    def _criar_modal_nabicode(self, modal_type, title, width, height):
        refs = getattr(self, "_cash_modal_refs", None)
        if refs is None:
            refs = self._cash_modal_refs = {}
        existing = refs.get(modal_type)
        try:
            if existing is not None and existing.winfo_exists():
                existing.lift()
                return existing, False
        except tk.TclError:
            refs.pop(modal_type, None)
        self._log_caixa_runtime("CASH_MODAL_CREATE_START", tipo=modal_type)
        try:
            win = ctk.CTkToplevel(self)
            win._cash_modal_type = modal_type
            win.title(title)
            win.configure(fg_color="#0d1117")
            win.transient(self)
            x = max(0, self.winfo_rootx() + (max(self.winfo_width(), width) - width) // 2)
            y = max(0, self.winfo_rooty() + (max(self.winfo_height(), height) - height) // 2)
            win.geometry(f"{width}x{height}+{x}+{y}")
            win.resizable(False, False)
            refs[modal_type] = win
            self._log_caixa_runtime("CASH_MODAL_CREATED", tipo=modal_type, geometry=win.geometry())
            return win, True
        except Exception:
            logger.exception("CASH_MODAL_EXCEPTION tipo=%s", modal_type)
            raise

    def _mostrar_modal_nabicode(self, win, focus_widget=None):
        modal_type = str(getattr(win, "_cash_modal_type", "CAIXA"))
        try:
            self._log_caixa_runtime("CASH_MODAL_WIDGETS_READY", tipo=modal_type)
            win.update_idletasks()
            self._log_caixa_runtime("CASH_MODAL_GEOMETRY_READY", tipo=modal_type, geometry=win.geometry())
            win.lift()
            self._log_caixa_runtime("CASH_MODAL_VISIBLE", tipo=modal_type, viewable=bool(win.winfo_viewable()), state=win.state())
            if focus_widget is not None:
                focus_widget.focus_set()
            self._log_caixa_runtime("CASH_MODAL_FOCUS", tipo=modal_type)
        except Exception:
            logger.exception("CASH_MODAL_EXCEPTION tipo=%s", modal_type)
            self._fechar_modal_caixa(win)
            raise

    def _solicitar_criacao_sessao_caixa(self, *, source, opening_balance):
        allowed = {
            "OPEN_WITH_VALUE": "VALOR_INFORMADO",
            "OPEN_WITHOUT_VALUE": "SEM_VALOR_INFORMADO",
        }
        self._log_caixa_runtime("CASH_SESSION_CREATE_REQUEST", source=source, user_action=True)
        if source not in allowed:
            logger.error("CASH_SESSION_CREATE_REJECTED source=%s", source)
            raise ValueError("Origem de abertura do caixa não autorizada.")
        return self._servico_caixa().open_session(
            self._terminal_caixa(), self._usuario_caixa(), opening_balance, allowed[source]
        )

    def _abrir_teste_modal_caixa(self):
        """Probe visual mínimo, sem banco/modalidade; mantido sem botão de produção."""
        win, created = self._criar_modal_nabicode("TESTE_MODAL", "TESTE MODAL", 360, 180)
        if not created: return
        ctk.CTkLabel(win, text="TESTE MODAL", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(35, 18))
        close = lambda: self._fechar_modal_caixa(win)
        ctk.CTkButton(win, text="Fechar", command=close).pack()
        win.protocol("WM_DELETE_WINDOW", close)
        self._mostrar_modal_nabicode(win)

    def tela_caixa(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent", corner_radius=0)
        scroll.pack(fill="both", expand=True)
        cab = ctk.CTkFrame(scroll, fg_color="#161b22", corner_radius=14, border_width=1, border_color="#30363d")
        cab.pack(fill="x", padx=24, pady=(20, 12))
        top = ctk.CTkFrame(cab, fg_color="transparent"); top.pack(fill="x", padx=20, pady=(16, 4))
        self.lbl_caixa_estado = ctk.CTkLabel(top, text="CAIXA", font=ctk.CTkFont(size=25, weight="bold"), text_color=self.cor_acento)
        self.lbl_caixa_estado.pack(side="left")
        ctk.CTkButton(top, text="← Voltar ao Início", width=145, fg_color="#30363d", hover_color="#484f58", command=lambda: self.mostrar_tela("dashboard")).pack(side="right")
        self.lbl_caixa_identificacao = ctk.CTkLabel(cab, text="", justify="left", anchor="w", text_color="#c9d1d9")
        self.lbl_caixa_identificacao.pack(fill="x", padx=20, pady=(2, 16))
        cards = ctk.CTkFrame(scroll, fg_color="transparent"); cards.pack(fill="x", padx=20, pady=2)
        for col in range(4): cards.grid_columnconfigure(col, weight=1, uniform="cash_cards")
        self.caixa_cards = {}
        definitions = (("expected_cash","DINHEIRO NA GAVETA","#00FF88"),("movement_total","MOVIMENTO TOTAL","#388bfd"),("pix","PIX","#a371f7"),("cartao","CARTÃO","#f0b429"),("recebimentos","RECEBIMENTOS","#58a6ff"),("sangrias","SANGRIAS","#ff6b6b"),("suprimentos","SUPRIMENTOS","#3fb950"),("saldo_inicial","SALDO INICIAL","#c9d1d9"))
        for index, (key, title, color) in enumerate(definitions):
            card = ctk.CTkFrame(cards, fg_color="#161b22", corner_radius=12, border_width=1, border_color="#30363d"); card.grid(row=index // 4, column=index % 4, sticky="nsew", padx=5, pady=5)
            title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="#8b949e"); title_label.pack(anchor="w", padx=14, pady=(12, 2))
            label = ctk.CTkLabel(card, text="R$ 0,00", font=ctk.CTkFont(size=21, weight="bold"), text_color=color); label.pack(anchor="w", padx=14, pady=(0, 12)); self.caixa_cards[key] = label
            for clickable in (card, title_label, label):
                clickable.bind("<Button-1>", lambda _event, item_key=key, item_title=title: self._abrir_detalhe_cartao_caixa(item_key, item_title))
        self.frame_caixa_abertura = ctk.CTkFrame(scroll, fg_color="#161b22", corner_radius=12)
        self.frame_caixa_acoes = ctk.CTkFrame(scroll, fg_color="#161b22", corner_radius=12)
        for action_frame in (self.frame_caixa_abertura, self.frame_caixa_acoes): action_frame.pack(fill="x", padx=24, pady=10)
        ctk.CTkLabel(self.frame_caixa_abertura, text="ABRIR CAIXA", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.cor_acento).pack(side="left", padx=16, pady=14)
        self.btn_caixa_abrir = ctk.CTkButton(self.frame_caixa_abertura, text="Informar saldo inicial", command=self.abrir_formulario_abertura_caixa); self.btn_caixa_abrir.pack(side="left", padx=6, pady=12)
        self.btn_caixa_sem_valor = ctk.CTkButton(self.frame_caixa_abertura, text="Abrir sem informar", fg_color="#1f6feb", command=self._abrir_caixa_sem_valor_pela_aba); self.btn_caixa_sem_valor.pack(side="left", padx=6, pady=12)
        ctk.CTkLabel(self.frame_caixa_acoes, text="AÇÕES", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.cor_acento).pack(side="left", padx=16, pady=14)
        self.btn_caixa_sangria = ctk.CTkButton(self.frame_caixa_acoes, text="Registrar Sangria", fg_color="#b62324", command=lambda: self._abrir_movimento_sessao("SANGRIA")); self.btn_caixa_sangria.pack(side="left", padx=6, pady=12)
        self.btn_caixa_suprimento = ctk.CTkButton(self.frame_caixa_acoes, text="Registrar Suprimento", fg_color="#2ea043", command=lambda: self._abrir_movimento_sessao("SUPRIMENTO")); self.btn_caixa_suprimento.pack(side="left", padx=6, pady=12)
        self.btn_caixa_fechar = ctk.CTkButton(self.frame_caixa_acoes, text="Fechar Caixa", fg_color="#1f6feb", command=self._abrir_fechamento_sessao); self.btn_caixa_fechar.pack(side="left", padx=6, pady=12)
        self.caixa_consultas = ctk.CTkFrame(scroll, fg_color="transparent"); self.caixa_consultas.pack(fill="x", padx=24, pady=(8, 24))
        ctk.CTkButton(self.caixa_consultas, text="Ver movimentações atuais", fg_color="#30363d", command=lambda: self._abrir_detalhe_cartao_caixa("todos", "MOVIMENTAÇÕES ATUAIS")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.caixa_consultas, text="Histórico por dia", fg_color="#1f6feb", command=self._abrir_historico_caixa_por_dia).pack(side="left")
        self._cash_current_summary = None
        return frame

    def _abrir_caixa_sem_valor_pela_aba(self):
        try:
            self._solicitar_criacao_sessao_caixa(source="OPEN_WITHOUT_VALUE", opening_balance=0)
            self.atualizar_tela_caixa()
        except Exception as exc:
            messagebox.showerror("Caixa", str(exc), parent=self)

    def atualizar_tela_caixa(self):
        if not hasattr(self, "lbl_caixa_estado"):
            return
        service, terminal = self._servico_caixa(), self._terminal_caixa()
        session = service.get_open_session(terminal)
        aberto = session is not None
        self.lbl_caixa_estado.configure(text="CAIXA ABERTO" if aberto else "CAIXA FECHADO")
        if aberto:
            self.frame_caixa_abertura.pack_forget()
            if not self.frame_caixa_acoes.winfo_manager(): self.frame_caixa_acoes.pack(fill="x", padx=24, pady=10, before=self.caixa_consultas)
        else:
            self.frame_caixa_acoes.pack_forget()
            if not self.frame_caixa_abertura.winfo_manager(): self.frame_caixa_abertura.pack(fill="x", padx=24, pady=10, before=self.caixa_consultas)
        values = {key: Decimal("0") for key in self.caixa_cards}
        self._cash_current_summary = None
        if session:
            resumo = service.session_summary(session.id)
            self._cash_current_summary = resumo
            self.lbl_caixa_identificacao.configure(text=f"Sessão #{session.id}  •  Terminal: {terminal}  •  Aberto por: {session.opened_by}\nAbertura: {session.opened_at}  •  Saldo inicial: R$ {session.opening_balance:.2f}  •  Modo: {session.opening_mode}")
            values.update(expected_cash=resumo["expected_cash"], movement_total=resumo["movement_total"], pix=resumo["pix"], cartao=resumo["cartao"], recebimentos=resumo["recebimentos_dinheiro"] + resumo["recebimentos_eletronicos"], sangrias=resumo["sangrias"], suprimentos=resumo["suprimentos"], saldo_inicial=session.opening_balance)
        else:
            self.lbl_caixa_identificacao.configure(text=f"Terminal {terminal}  •  Nenhuma sessão aberta\nEscolha uma opção abaixo para iniciar o caixa.")
        for key, label in self.caixa_cards.items(): label.configure(text=f"R$ {values[key]:.2f}")

    def _abrir_detalhe_cartao_caixa(self, key, title):
        resumo = getattr(self, "_cash_current_summary", None)
        if resumo is None:
            messagebox.showinfo("Caixa", "Não existe uma sessão aberta para consultar.", parent=self)
            return
        movements = list(resumo["movements"])
        filters = {
            "movement_total": lambda item: str(item["tipo"]).startswith("VENDA "),
            "pix": lambda item: str(item["tipo"]).endswith(" PIX"),
            "cartao": lambda item: str(item["tipo"]).endswith(" CARTAO"),
            "recebimentos": lambda item: str(item["tipo"]).startswith("RECEBIMENTO "),
            "sangrias": lambda item: item["tipo"] == "SANGRIA",
            "suprimentos": lambda item: item["tipo"] == "SUPRIMENTO",
            "expected_cash": lambda item: item["tipo"] in {"VENDA DINHEIRO", "RECEBIMENTO DINHEIRO", "SANGRIA", "SUPRIMENTO"},
            "saldo_inicial": lambda _item: False,
            "todos": lambda _item: True,
        }
        selected = [item for item in movements if filters.get(key, filters["todos"])(item)]
        win, created = self._criar_modal_nabicode("DETALHE_CARTAO_CAIXA", title.title(), 760, 520)
        if not created: return
        shell = ctk.CTkScrollableFrame(win, fg_color="#0d1117", corner_radius=0); shell.pack(fill="both", expand=True)
        ctk.CTkLabel(shell, text=title, font=ctk.CTkFont(size=21, weight="bold"), text_color=self.cor_acento).pack(anchor="w", padx=28, pady=(24, 12))
        if key == "saldo_inicial":
            ctk.CTkLabel(shell, text=f"Valor informado na abertura: R$ {resumo['session'].opening_balance:.2f}", anchor="w").pack(fill="x", padx=28, pady=8)
        elif selected:
            for movement in selected:
                sign = "-" if movement.get("sinal", 1) < 0 else "+"
                text = f"{movement['data']}  •  {movement['tipo']}  •  {sign}R$ {movement['valor']:.2f}\n{movement['usuario']}  •  {movement['observacao']}"
                ctk.CTkLabel(shell, text=text, justify="left", anchor="w", fg_color="#161b22", corner_radius=9).pack(fill="x", padx=28, pady=4, ipady=7)
        else:
            ctk.CTkLabel(shell, text="Nenhuma movimentação compõe este valor.", text_color="#8b949e").pack(anchor="w", padx=28, pady=8)
        close = lambda _event=None: self._fechar_modal_caixa(win)
        ctk.CTkButton(shell, text="Voltar", fg_color="#30363d", command=close).pack(anchor="e", padx=28, pady=24)
        win.bind("<Escape>", close); win.protocol("WM_DELETE_WINDOW", close)
        self._mostrar_modal_nabicode(win)

    def _abrir_historico_caixa_por_dia(self):
        win, created = self._criar_modal_nabicode("LISTA_HISTORICO_CAIXA", "Histórico do Caixa", 980, 560)
        if not created: return
        shell = ctk.CTkFrame(win, fg_color="#0d1117", corner_radius=0); shell.pack(fill="both", expand=True)
        header = ctk.CTkFrame(shell, fg_color="transparent"); header.pack(fill="x", padx=24, pady=(22, 12))
        ctk.CTkLabel(header, text="HISTÓRICO POR DIA", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.cor_acento).pack(side="left")
        date_entry = ctk.CTkEntry(header, width=135, placeholder_text="DD/MM/AAAA"); date_entry.pack(side="right", padx=(8, 0)); date_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
        table = ttk.Treeview(shell, columns=("id","abertura","usuario","fechamento","esperado","contado","diferenca","status"), show="headings", height=13)
        for col, label, width in (("id","Sessão",65),("abertura","Abertura",145),("usuario","Aberto por",105),("fechamento","Fechamento",145),("esperado","Esperado",105),("contado","Contado",105),("diferenca","Diferença",105),("status","Status",80)):
            table.heading(col, text=label); table.column(col, width=width, minwidth=60, anchor="center")
        table.pack(fill="both", expand=True, padx=24, pady=8)
        status = ctk.CTkLabel(shell, text="", text_color="#8b949e"); status.pack(anchor="w", padx=24)
        def load(_event=None):
            try:
                sessions = self._servico_caixa().history(self._terminal_caixa(), opened_date=date_entry.get())
            except ValueError as exc:
                status.configure(text=str(exc), text_color="#ff6b6b"); date_entry.focus_set(); return
            for item in table.get_children(): table.delete(item)
            money = lambda value: "" if value is None else f"R$ {value:.2f}"
            for item in sessions:
                table.insert("", "end", iid=str(item.id), values=(item.id,item.opened_at,item.opened_by,item.closed_at,money(item.expected_cash),money(item.counted_cash),money(item.difference),item.status))
            status.configure(text=f"{len(sessions)} sessão(ões). Dê dois cliques para ver os detalhes.", text_color="#8b949e")
        ctk.CTkButton(header, text="Buscar", width=80, fg_color="#1f6feb", command=load).pack(side="right")
        close = lambda _event=None: self._fechar_modal_caixa(win)
        ctk.CTkButton(shell, text="Voltar", fg_color="#30363d", command=close).pack(anchor="e", padx=24, pady=(8, 20))
        table.bind("<Double-1>", self._detalhar_caixa_historico)
        date_entry.bind("<Return>", load); win.bind("<Escape>", close); win.protocol("WM_DELETE_WINDOW", close)
        self._mostrar_modal_nabicode(win, date_entry)
        load()

    def _abrir_movimento_sessao(self, kind):
        self._log_caixa_runtime("CASH_MODAL_OPEN", tipo=kind)
        win, created = self._criar_modal_nabicode(kind, f"Registrar {kind.title()}", 520, 445)
        if not created: return
        shell = ctk.CTkFrame(win, fg_color="#0d1117", corner_radius=0); shell.pack(fill="both", expand=True)
        color = "#b62324" if kind == "SANGRIA" else "#2ea043"
        ctk.CTkLabel(shell, text=f"REGISTRAR {kind}", font=ctk.CTkFont(size=22, weight="bold"), text_color=color).pack(anchor="w", padx=30, pady=(28, 18))
        ctk.CTkLabel(shell, text="Valor", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30)
        value = ctk.CTkEntry(shell, placeholder_text="R$ 0,00", height=44); value.pack(fill="x", padx=30, pady=(5, 14))
        ctk.CTkLabel(shell, text="Motivo / observação", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=30)
        note = ctk.CTkTextbox(shell, height=100); note.pack(fill="x", padx=30, pady=(5, 8))
        error = ctk.CTkLabel(shell, text="", text_color="#ff6b6b"); error.pack(anchor="w", padx=30)
        buttons = ctk.CTkFrame(shell, fg_color="transparent"); buttons.pack(fill="x", padx=25, pady=18)
        def close(_event=None): self._fechar_modal_caixa(win)
        def confirm(_event=None):
            try:
                self._servico_caixa().register_session_movement(self._terminal_caixa(), kind, tratar_numero(value.get()), self._usuario_caixa(), note.get("1.0", "end").strip())
            except Exception as exc:
                error.configure(text=str(exc)); value.focus_set(); return
            close(); self.atualizar_tela_caixa()
        ctk.CTkButton(buttons, text=f"Confirmar {kind.title()}", fg_color=color, command=confirm).pack(side="right", padx=5)
        ctk.CTkButton(buttons, text="Voltar", fg_color="#30363d", command=close).pack(side="right", padx=5)
        win.bind("<Return>", confirm); win.bind("<Escape>", close); win.protocol("WM_DELETE_WINDOW", close)
        self._mostrar_modal_nabicode(win, value)

    def _abrir_fechamento_sessao(self):
        close_started = perf_counter()
        self._log_caixa_runtime("CASH_CLOSE_CLICK")
        self._log_caixa_runtime("CASH_CLOSE_MODAL_CREATE")
        win, created = self._criar_modal_nabicode("FECHAMENTO", "Fechar Caixa", 680, 680)
        if not created: return
        self._log_caixa_runtime("CASH_CLOSE_MODAL_OPEN")
        shell = ctk.CTkScrollableFrame(win, fg_color="#0d1117", corner_radius=0); shell.pack(fill="both", expand=True)
        loading = ctk.CTkLabel(shell, text="Carregando fechamento...", font=ctk.CTkFont(size=18, weight="bold"), text_color="#8b949e")
        loading.pack(expand=True, pady=80)
        closing = {"done": False, "submitting": False}
        def close(_event=None, *, confirmed=False):
            if closing["done"]: return
            closing["done"] = True
            self._log_caixa_runtime("CASH_CLOSE_CONFIRM" if confirmed else "CASH_CLOSE_CANCEL")
            try:
                if win.grab_current() == win:
                    win.grab_release(); self._log_caixa_runtime("CASH_CLOSE_GRAB_RELEASE")
            except tk.TclError:
                logger.exception("CASH_CLOSE_EXCEPTION ao liberar grab")
            self._fechar_modal_caixa(win, "CASH_CLOSE_DESTROY")
            self._log_caixa_runtime("CASH_CLOSE_MODAL_CLOSE")
        win.bind("<Escape>", close); win.protocol("WM_DELETE_WINDOW", close)
        self._mostrar_modal_nabicode(win)
        self._log_caixa_runtime("CASH_CLOSE_MODAL_VISIBLE", elapsed_ms=round((perf_counter() - close_started) * 1000, 2))
        self._log_caixa_runtime("CASH_CLOSE_READY", estado="carregando")

        def carregar_fechamento():
            data_started = perf_counter()
            self._log_caixa_runtime("CASH_CLOSE_DATA_START")
            try:
                service = self._servico_caixa()
                session = service.get_open_session(self._terminal_caixa())
                if not session:
                    close()
                    self.atualizar_tela_caixa()
                    return
                resumo = service.session_summary(session.id)
            except Exception as exc:
                logger.exception("CASH_CLOSE_EXCEPTION ao carregar fechamento")
                loading.configure(text=f"Não foi possível carregar o fechamento:\n{exc}", text_color="#ff6b6b")
                return
            self._log_caixa_runtime("CASH_CLOSE_DATA_END", elapsed_ms=round((perf_counter() - data_started) * 1000, 2))
            if closing["done"]:
                return
            loading.destroy()
            ctk.CTkLabel(shell, text="FECHAMENTO DE CAIXA", font=ctk.CTkFont(size=22, weight="bold"), text_color="#388bfd").pack(anchor="w", padx=32, pady=(26, 12))
            def metric_card(parent, row, column, title, amount, color="#f0f6fc"):
                card = ctk.CTkFrame(parent, fg_color="#161b22", corner_radius=11, border_width=1, border_color="#30363d")
                card.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
                ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="#8b949e").pack(anchor="w", padx=12, pady=(10, 1))
                ctk.CTkLabel(card, text=f"R$ {amount:.2f}", font=ctk.CTkFont(size=18, weight="bold"), text_color=color).pack(anchor="w", padx=12, pady=(0, 10))
            ctk.CTkLabel(shell, text="DINHEIRO FÍSICO", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8b949e").pack(anchor="w", padx=32, pady=(2, 3))
            cash_cards = ctk.CTkFrame(shell, fg_color="transparent"); cash_cards.pack(fill="x", padx=28)
            for column in range(3): cash_cards.grid_columnconfigure(column, weight=1, uniform="closing_cash")
            cash_metrics = (
                ("SALDO INICIAL", session.opening_balance, "#c9d1d9"),
                ("VENDAS", resumo["dinheiro"], "#58a6ff"),
                ("RECEBIMENTOS", resumo["recebimentos_dinheiro"], "#58a6ff"),
                ("SUPRIMENTOS", resumo["suprimentos"], "#3fb950"),
                ("SANGRIAS", -resumo["sangrias"], "#ff6b6b"),
                ("DINHEIRO ESPERADO", resumo["expected_cash"], "#00FF88"),
            )
            for index, (title, amount, color) in enumerate(cash_metrics):
                metric_card(cash_cards, index // 3, index % 3, title, amount, color)
            ctk.CTkLabel(shell, text="ELETRÔNICOS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8b949e").pack(anchor="w", padx=32, pady=(10, 3))
            electronic_cards = ctk.CTkFrame(shell, fg_color="transparent"); electronic_cards.pack(fill="x", padx=28)
            for column in range(3): electronic_cards.grid_columnconfigure(column, weight=1, uniform="closing_electronic")
            electronic_metrics = (
                ("PIX", resumo["pix"], "#a371f7"),
                ("CARTÃO", resumo["cartao"], "#f0b429"),
                ("OUTROS", resumo["outros"] + resumo["recebimentos_eletronicos"], "#79c0ff"),
            )
            for column, (title, amount, color) in enumerate(electronic_metrics):
                metric_card(electronic_cards, 0, column, title, amount, color)
            ctk.CTkLabel(shell, text="VALOR CONTADO", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=32, pady=(12, 3))
            counted = ctk.CTkEntry(shell, placeholder_text="R$ 0,00", height=44); counted.pack(fill="x", padx=32)
            result = ctk.CTkLabel(shell, text="Informe o valor contado", font=ctk.CTkFont(size=18, weight="bold"), text_color="#8b949e"); result.pack(anchor="w", padx=32, pady=12)
            ctk.CTkLabel(shell, text="Observação do fechamento", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=32)
            note = ctk.CTkTextbox(shell, height=85); note.pack(fill="x", padx=32, pady=(4, 6))
            error = ctk.CTkLabel(shell, text="", text_color="#ff6b6b"); error.pack(anchor="w", padx=32)
            def calculate(_event=None):
                try: diff = Decimal(str(tratar_numero(counted.get()))) - resumo["expected_cash"]
                except ValueError: result.configure(text="Informe um valor contado válido", text_color="#f0b429"); return None
                if diff == 0: result.configure(text="CAIXA CONFERE", text_color="#00FF88")
                elif diff > 0: result.configure(text=f"SOBRA R$ {diff:.2f}", text_color="#f0b429")
                else: result.configure(text=f"FALTA R$ {abs(diff):.2f}", text_color="#ff6b6b")
                return diff
            counted.bind("<KeyRelease>", calculate)
            def confirm():
                if closing["done"] or closing["submitting"] or calculate() is None:
                    return
                closing["submitting"] = True
                confirm_button.configure(state="disabled", text="Fechando...")
                try:
                    closed_session = service.close_session(self._terminal_caixa(), tratar_numero(counted.get()), self._usuario_caixa(), note.get("1.0", "end").strip())
                except Exception as exc:
                    logger.exception("CASH_CLOSE_EXCEPTION ao confirmar fechamento")
                    closing["submitting"] = False
                    confirm_button.configure(state="normal", text="Confirmar Fechamento")
                    error.configure(text=str(exc)); return
                close(confirmed=True)
                self.atualizar_tela_caixa()
                self._abrir_acoes_fechamento_caixa(closed_session, resumo)
            buttons = ctk.CTkFrame(shell, fg_color="transparent"); buttons.pack(fill="x", padx=27, pady=18)
            confirm_button = ctk.CTkButton(buttons, text="Confirmar Fechamento", fg_color="#1f6feb", command=confirm)
            confirm_button.pack(side="right", padx=5)
            ctk.CTkButton(buttons, text="Voltar", fg_color="#30363d", command=close).pack(side="right", padx=5)
            counted.focus_set()
            self._log_caixa_runtime("CASH_CLOSE_BUILD_END")
            self._log_caixa_runtime("CASH_CLOSE_READY", estado="pronto")

        self.after(1, carregar_fechamento)

    def _abrir_acoes_fechamento_caixa(self, session, resumo):
        win, created = self._criar_modal_nabicode("FECHAMENTO_CONCLUIDO", f"Caixa #{session.id} fechado", 560, 300)
        if not created: return
        shell = ctk.CTkFrame(win, fg_color="#0d1117", corner_radius=0); shell.pack(fill="both", expand=True)
        ctk.CTkLabel(shell, text="CAIXA FECHADO", font=ctk.CTkFont(size=22, weight="bold"), text_color="#00FF88").pack(anchor="w", padx=30, pady=(28, 8))
        ctk.CTkLabel(shell, text=f"Sessão #{session.id} concluída. A impressão é opcional e não altera o fechamento.", justify="left", anchor="w", wraplength=490).pack(fill="x", padx=30, pady=(0, 20))
        status = ctk.CTkLabel(shell, text="", text_color="#f0b429"); status.pack(anchor="w", padx=30)
        buttons = ctk.CTkFrame(shell, fg_color="transparent"); buttons.pack(fill="x", padx=25, pady=24)
        def close(_event=None): self._fechar_modal_caixa(win)
        def print_closing():
            self._abrir_preview_fechamento_caixa(session, resumo)
            status.configure(text="Pré-visualização aberta. Nada foi impresso automaticamente.", text_color="#58a6ff")
        print_button = ctk.CTkButton(buttons, text="Visualizar / Imprimir", fg_color="#1f6feb", command=print_closing); print_button.pack(side="right", padx=5)
        ctk.CTkButton(buttons, text="Voltar", fg_color="#30363d", command=close).pack(side="right", padx=5)
        win.bind("<Escape>", close); win.protocol("WM_DELETE_WINDOW", close)
        self._mostrar_modal_nabicode(win, print_button)

    @staticmethod
    def _texto_comprovante_fechamento_caixa(session, resumo):
        return "".join((
            "NABICODE\n",
            "FECHAMENTO DE CAIXA\n",
            "=" * 32, "\n",
            f"Sessão: {session.id}\nTerminal: {session.terminal}\n"
            f"Aberto por: {session.opened_by}\nAbertura: {session.opened_at}\n"
            f"Fechado por: {session.closed_by}\nFechamento: {session.closed_at}\n",
            "-" * 32, "\n",
            f"Saldo inicial: R$ {session.opening_balance:.2f}\n"
            f"Vendas dinheiro: R$ {resumo['dinheiro']:.2f}\n"
            f"Recebimentos dinheiro: R$ {resumo['recebimentos_dinheiro']:.2f}\n"
            f"Suprimentos: R$ {resumo['suprimentos']:.2f}\n"
            f"Sangrias: R$ {resumo['sangrias']:.2f}\n"
            f"Outras saídas: R$ 0.00\n"
            f"Dinheiro esperado: R$ {session.expected_cash:.2f}\n",
            "-" * 32, "\n",
            f"PIX: R$ {resumo['pix']:.2f}\nCartão: R$ {resumo['cartao']:.2f}\n"
            f"Outros eletrônicos: R$ {resumo['outros'] + resumo['recebimentos_eletronicos']:.2f}\n"
            f"Valor contado: R$ {session.counted_cash:.2f}\nDiferença: R$ {session.difference:.2f}\n"
            f"Observação: {session.closing_note or '-'}\n",
        ))

    def _abrir_preview_fechamento_caixa(self, session, resumo):
        texto = self._texto_comprovante_fechamento_caixa(session, resumo)
        return self.janela_preview_documento(
            texto,
            categoria="fechamento",
            titulo=f"Fechamento de caixa #{session.id}",
            subtitulo="Pré-visualização do fechamento",
        )

    def _detalhar_caixa_historico(self, _event=None):
        table = getattr(_event, "widget", None)
        if table is None or not hasattr(table, "selection"):
            return
        selected = table.selection()
        if not selected: return
        resumo = self._servico_caixa().session_summary(int(selected[0]))
        sessao = resumo["session"]
        win, created = self._criar_modal_nabicode("HISTORICO", f"Detalhes da sessão #{sessao.id}", 800, 620)
        if not created: return
        self._log_caixa_runtime("CASH_MODAL_OPEN", tipo="HISTORICO")
        shell = ctk.CTkScrollableFrame(win, fg_color="#0d1117", corner_radius=0); shell.pack(fill="both", expand=True)
        ctk.CTkLabel(shell, text=f"SESSÃO #{sessao.id} — {sessao.status}", font=ctk.CTkFont(size=21, weight="bold"), text_color=self.cor_acento).pack(anchor="w", padx=28, pady=(24, 12))
        counted_text = "—" if sessao.counted_cash is None else f"R$ {sessao.counted_cash:.2f}"
        difference_text = "—" if sessao.difference is None else f"R$ {sessao.difference:.2f}"
        text = f"Abertura: {sessao.opened_at} por {sessao.opened_by}\nFechamento: {sessao.closed_at or '—'} por {sessao.closed_by or '—'}\nSaldo inicial: R$ {sessao.opening_balance:.2f}\nDinheiro: R$ {resumo['dinheiro']:.2f}   PIX: R$ {resumo['pix']:.2f}   Cartão: R$ {resumo['cartao']:.2f}\nRecebimentos em dinheiro: R$ {resumo['recebimentos_dinheiro']:.2f}\nSangrias: R$ {resumo['sangrias']:.2f}   Suprimentos: R$ {resumo['suprimentos']:.2f}\nEsperado: R$ {resumo['expected_cash']:.2f}\nContado: {counted_text}   Diferença: {difference_text}\nObservação: {sessao.closing_note or '—'}"
        ctk.CTkLabel(shell, text=text, justify="left", anchor="w", fg_color="#161b22", corner_radius=12).pack(fill="x", padx=28, pady=8, ipady=12)
        ctk.CTkLabel(shell, text="MOVIMENTAÇÕES", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=28, pady=(14, 6))
        if resumo["movements"]:
            for movement in resumo["movements"]:
                sign = "-" if movement.get("sinal", 1) < 0 else "+"
                ctk.CTkLabel(shell, text=f"{movement['data']}  •  {movement['tipo']}  •  {sign}R$ {movement['valor']:.2f}  •  {movement['usuario']}  •  {movement['observacao']}", anchor="w").pack(fill="x", padx=32, pady=2)
        else:
            ctk.CTkLabel(shell, text="Nenhuma movimentação nesta sessão.", text_color="#8b949e").pack(anchor="w", padx=32)
        close = lambda _event=None: self._fechar_modal_caixa(win)
        ctk.CTkButton(shell, text="Voltar", fg_color="#30363d", command=close).pack(anchor="e", padx=28, pady=24)
        win.bind("<Escape>", close); win.protocol("WM_DELETE_WINDOW", close)
        self._mostrar_modal_nabicode(win)

    def perguntar_abertura_caixa(self):
        if not self._startup_reveal_complete:
            return
        self._garantir_janela_principal_visivel()
        self._log_caixa_runtime("CASH_CHECK", terminal=self._terminal_caixa())
        if self._servico_caixa().get_open_session(self._terminal_caixa()):
            return
        win, created = self._criar_modal_nabicode("ABERTURA_ESCOLHA", "Abertura de caixa", 500, 250)
        if not created: return
        self._log_caixa_runtime("CASH_DIALOG_CREATE")
        self._janela_abertura_caixa = win
        self._log_caixa_runtime("CASH_MODAL_OPEN", tipo="ABERTURA")

        def fechar_apos_abertura():
            self._janela_abertura_caixa = None
            self._fechar_modal_caixa(win)
            self._garantir_janela_principal_visivel()

        def fechar_pergunta():
            self._janela_abertura_caixa = None
            self._fechar_modal_caixa(win)
            self._garantir_janela_principal_visivel()

        def informar_agora():
            fechar_apos_abertura()
            self.abrir_formulario_abertura_caixa()

        def abrir_sem_informar():
            try:
                self._solicitar_criacao_sessao_caixa(source="OPEN_WITHOUT_VALUE", opening_balance=0)
            except Exception as exc:
                messagebox.showerror("Abertura de caixa", str(exc), parent=win)
                return
            fechar_apos_abertura()
            self.atualizar_tela_caixa()

        win.protocol("WM_DELETE_WINDOW", fechar_pergunta)
        ctk.CTkLabel(win, text="💵 Abertura de caixa", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.cor_acento).pack(pady=(25,8))
        ctk.CTkLabel(win, text="Escolha como abrir o caixa deste terminal.", justify="center").pack(pady=8)
        frame=ctk.CTkFrame(win, fg_color="transparent"); frame.pack(fill="x", padx=30, pady=15)
        ctk.CTkButton(frame, text="INFORMAR SALDO INICIAL", fg_color="#2ea043", command=informar_agora).pack(side="left", expand=True, fill="x", padx=5)
        ctk.CTkButton(frame, text="ABRIR SEM INFORMAR", fg_color="#1f6feb", command=abrir_sem_informar).pack(side="left", expand=True, fill="x", padx=5)
        self._mostrar_modal_nabicode(win)
        self._log_caixa_runtime("CASH_DIALOG_VISIBLE", viewable=bool(win.winfo_viewable()))

    def abrir_formulario_abertura_caixa(self):
        """Abre o formulário de caixa sem ocultar ou bloquear a janela principal."""
        self._garantir_janela_principal_visivel()

        win, created = self._criar_modal_nabicode("ABERTURA_VALOR", "Informar abertura de caixa", 480, 410)
        if not created: return
        self._janela_formulario_abertura_caixa = win
        self._log_caixa_runtime("CASH_MODAL_OPEN", tipo="SALDO_INICIAL")

        ctk.CTkLabel(
            win,
            text="Informar saldo inicial",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=self.cor_acento,
        ).pack(pady=(20, 10))

        valor = ctk.CTkEntry(
            win,
            placeholder_text="Valor inicial em dinheiro (R$)",
            height=40,
        )
        valor.pack(fill="x", padx=30, pady=7)
        erro = ctk.CTkLabel(win, text="", text_color="#ff6b6b")
        erro.pack(anchor="w", padx=30)

        def fechar_formulario():
            self._janela_formulario_abertura_caixa = None
            self._fechar_modal_caixa(win)
            self._garantir_janela_principal_visivel()

        def salvar():
            if not valor.get().strip():
                erro.configure(text="Informe o saldo inicial. R$ 0,00 é aceito.")
                return
            try:
                valor_inicial = tratar_numero(valor.get())
            except ValueError:
                erro.configure(text="Valor inicial inválido.")
                return

            try:
                self._solicitar_criacao_sessao_caixa(source="OPEN_WITH_VALUE", opening_balance=valor_inicial)
            except Exception as exc:
                logger.exception("Falha ao registrar abertura de caixa.")
                erro.configure(text=f"Não foi possível abrir o caixa: {exc}")
                return

            fechar_formulario()
            self.atualizar_tela_caixa()

        win.protocol("WM_DELETE_WINDOW", fechar_formulario)
        win.bind("<Escape>", lambda _event: fechar_formulario())
        win.bind("<Return>", lambda _event: salvar())
        ctk.CTkButton(
            win,
            text="CONFIRMAR ABERTURA",
            fg_color="#2ea043",
            height=42,
            command=salvar,
        ).pack(fill="x", padx=30, pady=(15, 6))
        ctk.CTkButton(win, text="VOLTAR", fg_color="#30363d", command=fechar_formulario).pack(fill="x", padx=30, pady=5)
        self._mostrar_modal_nabicode(win, valor)

    def abrir_movimentacao_caixa(self):
        win=ctk.CTkToplevel(self); win.title("Movimentação de Caixa"); win.geometry("500x500"); win.transient(self); win.grab_set()
        ctk.CTkLabel(win,text="💰 Movimentação de Caixa",font=ctk.CTkFont(size=20,weight="bold"),text_color=self.cor_acento).pack(pady=(20,10))
        tipo=ctk.CTkComboBox(win,values=["RETIRADA","SUPRIMENTO","PAGAMENTO DE CONTA"],height=40); tipo.set("RETIRADA"); tipo.pack(fill="x",padx=30,pady=7)
        valor=ctk.CTkEntry(win,placeholder_text="Valor (R$)",height=40); valor.pack(fill="x",padx=30,pady=7)
        forma=ctk.CTkComboBox(win,values=["Dinheiro","PIX","Transferência","Cartão","Outro"],height=40); forma.set("Dinheiro"); forma.pack(fill="x",padx=30,pady=7)
        motivo=ctk.CTkEntry(win,placeholder_text="Motivo ou descrição (opcional)",height=40); motivo.pack(fill="x",padx=30,pady=7)
        resp=ctk.CTkEntry(win,placeholder_text="Responsável (opcional)",height=40); resp.pack(fill="x",padx=30,pady=7); resp.insert(0,obter_config("caixa_responsavel_padrao") or "")
        def confirmar():
            try: v=tratar_numero(valor.get())
            except ValueError: messagebox.showerror("Erro","Digite um valor válido.",parent=win); return
            if v<=0: messagebox.showwarning("Valor","O valor deve ser maior que zero.",parent=win); return
            t = tipo.get()
            desc = motivo.get().strip() or t.title()
            self._servico_caixa().register_movement(
                t, v, forma.get(), desc, resp.get().strip(),
                datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            )
            win.destroy(); self.carregar_historico_dia(); messagebox.showinfo("Caixa",f"{t.title()} de R$ {v:.2f} registrada com sucesso.")
        ctk.CTkButton(win,text="Confirmar movimentação",fg_color="#2ea043",height=42,command=confirmar).pack(fill="x",padx=30,pady=(18,7))
        ctk.CTkButton(win,text="Cancelar",fg_color="#30363d",command=win.destroy).pack(fill="x",padx=30,pady=5)

    def abrir_fechamento_caixa(self):
        r=self._resumo_caixa_dia(); win=ctk.CTkToplevel(self); win.title("Finalizar / Fechar dia"); win.geometry("610x650"); win.transient(self); win.grab_set()
        ctk.CTkLabel(win,text=f"📊 Resumo do dia — {r['data']}",font=ctk.CTkFont(size=20,weight="bold"),text_color=self.cor_acento).pack(pady=(18,8))
        texto=(f"Abertura informada: R$ {r['abertura']:.2f}\nVendas registradas: R$ {r['vendas']:.2f}\nRecebimentos: R$ {r['recebimentos']:.2f}\nSuprimentos: R$ {r['suprimentos']:.2f}\nRetiradas: R$ {r['retiradas']:.2f}\nPagamentos de conta: R$ {r['contas']:.2f}\n\nEntradas de caixa: R$ {r['entradas']:.2f}\nSaídas de caixa: R$ {r['saidas']:.2f}\nSALDO ESPERADO: R$ {r['saldo_esperado']:.2f}")
        ctk.CTkLabel(win,text=texto,justify="left",anchor="w",font=ctk.CTkFont(size=14)).pack(fill="x",padx=35,pady=10)
        contado=ctk.CTkEntry(win,placeholder_text="Valor contado no caixa (opcional)",height=40); contado.pack(fill="x",padx=35,pady=6)
        resp=ctk.CTkEntry(win,placeholder_text="Responsável (opcional)",height=40); resp.pack(fill="x",padx=35,pady=6); resp.insert(0,obter_config("caixa_responsavel_padrao") or "")
        obs=ctk.CTkEntry(win,placeholder_text="Observação / diferença (opcional)",height=40); obs.pack(fill="x",padx=35,pady=6)
        def ler_valor_contado():
            if not contado.get().strip():
                return None
            try:
                return tratar_numero(contado.get())
            except ValueError:
                messagebox.showerror("Erro", "Valor contado inválido.", parent=win)
                raise

        def salvar_fechamento(caminho_pdf=""):
            try:
                vc = ler_valor_contado()
            except ValueError:
                return False
            data_sql = datetime.now().strftime("%Y-%m-%d")
            existente = self._servico_caixa().existing_closing_id(data_sql)
            substituir = False
            if existente:
                substituir = messagebox.askyesno(
                    "Caixa já fechado",
                    "Já existe um fechamento salvo para hoje. Deseja atualizar esse fechamento?",
                    parent=win,
                )
                if not substituir:
                    return False
            self._servico_caixa().save_closing(
                data_sql, r["saldo_esperado"], vc, resp.get().strip(),
                obs.get().strip(), caminho_pdf, replace_existing=substituir,
            )
            return True

        def fechar_e_salvar():
            if salvar_fechamento(""):
                messagebox.showinfo("Caixa fechado", "O fechamento do dia foi salvo com sucesso.", parent=win)
                win.destroy()

        def gerar_pdf_imprimir():
            try:
                vc = ler_valor_contado()
            except ValueError:
                return
            caminho = self.gerar_pdf_fechamento(r,vc,resp.get().strip(),obs.get().strip())
            if salvar_fechamento(caminho):
                self.janela_acoes_pdf(caminho,"fechamento","Fechamento de caixa")

        ctk.CTkButton(win,text="✅ Fechar caixa e salvar",fg_color="#1f6feb",hover_color="#1158c7",height=42,command=fechar_e_salvar).pack(fill="x",padx=35,pady=(18,7))
        ctk.CTkButton(win,text="🧾 Salvar, gerar PDF e imprimir",fg_color="#2ea043",height=42,command=gerar_pdf_imprimir).pack(fill="x",padx=35,pady=7)
        ctk.CTkButton(win,text="Cancelar sem fechar",fg_color="#30363d",command=win.destroy).pack(fill="x",padx=35,pady=5)

    def abrir_menu_contexto_historico(self, event):
        item=self.tabela_dash.identify_row(event.y)
        if not item: return
        self.tabela_dash.selection_set(item)
        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label="Visualizar / editar detalhes",command=lambda:self.abrir_janela_edicao_movimento(item))
        tipo = self._servico_caixa().movement_type(int(item))
        if tipo=="COMPRA":
            menu.add_command(label="Reimprimir comprovante de venda",command=lambda:self.reimprimir_movimentacao(item,"recibo"))
            menu.add_command(label="Gerar comprovante de entrega",command=lambda:self.reimprimir_movimentacao(item,"entrega"))
        elif tipo in ("PAGAMENTO","ABATIMENTO"):
            menu.add_command(label="Reimprimir comprovante",command=lambda:self.reimprimir_movimentacao(item,"movimento"))
        elif tipo in ("RETIRADA_CAIXA","SUPRIMENTO_CAIXA","PAGAMENTO_CONTA"):
            menu.add_command(label="Imprimir comprovante da movimentação",command=lambda:self.reimprimir_movimentacao(item,"movimento"))
        menu.add_separator(); menu.add_command(label="Abrir último PDF gerado",command=lambda:self.abrir_ultimo_pdf_movimentacao(item))
        menu.tk_popup(event.x_root,event.y_root)

    def abrir_ultimo_pdf_movimentacao(self, mov_id):
        documento = self._servico_documentos_emitidos().latest_existing_file(mov_id)
        if documento is not None:
            self._abrir_arquivo_sistema(documento.pdf_path)
            return
        messagebox.showinfo(
            "PDF",
            "Nenhum PDF anterior foi encontrado. Use a opção de reimpressão para gerar uma nova via.",
        )

    def reimprimir_movimentacao(self, mov_id, categoria):
        movimento = self._servico_movimentacoes().get(int(mov_id))
        if movimento is None:
            return
        cid = movimento.customer_id
        tipo = movimento.movement_type
        desc = movimento.description
        valor = movimento.value
        data = movimento.occurred_at
        forma = movimento.payment_method
        nome = movimento.customer_name
        try:
            if tipo=="COMPRA" and cid:
                itens=[]
                for parte in (desc or "").split(" | "):
                    m=re.match(r"([\d.,]+)x\s+(.*?)\s+\(R\$\s*([\d.,]+)\)",parte)
                    if m:
                        qtd=tratar_numero(m.group(1)); subtotal=tratar_numero(m.group(3)); itens.append({"qtd":qtd,"item":m.group(2),"preco":subtotal/qtd if qtd else subtotal,"subtotal":subtotal})
                if not itens: itens=[{"qtd":1,"item":desc or "Venda","preco":float(valor or 0),"subtotal":float(valor or 0)}]
                tipo_doc = "ENTREGA" if categoria=="entrega" else "RECIBO"
                texto = self.texto_comprovante_venda(cid, itens, float(valor or 0), tipo_doc, mov_id)
                self.janela_preview_documento(
                    texto,
                    categoria="entrega" if categoria=="entrega" else "recibo",
                    titulo="Segunda via",
                    subtitulo="Pré-visualização do cupom",
                    pdf_callback=lambda destino: self.gerar_pdf_venda(
                        cid, itens, float(valor or 0), tipo_doc, mov_id, destino=destino
                    ),
                )
            elif tipo == "PAGAMENTO":
                self.janela_recibo_pagamento_cliente(int(mov_id), [])
            else:
                texto = (
                    "NabiCode\nCOMPROVANTE DE MOVIMENTAÇÃO\n"
                    + "=" * 42 + "\n"
                    + f"Movimento: {mov_id}\n"
                    + f"Data: {data or '-'}\n"
                    + f"Cliente: {nome or 'CONSUMIDOR FINAL'}\n"
                    + f"Tipo: {tipo or '-'}\n"
                    + f"Forma: {forma or '-'}\n"
                    + f"Valor: R$ {DecimalStorage.to_decimal(valor or 0, field='valor'):.2f}\n"
                    + f"Descrição: {desc or '-'}\n"
                )
                self.janela_preview_documento(
                    texto,
                    categoria="recibo",
                    titulo="Comprovante",
                    subtitulo="Pré-visualização do cupom",
                    pdf_callback=lambda destino: self.gerar_pdf_movimentacao(mov_id, destino=destino),
                )
        except Exception as exc: messagebox.showerror("Reimpressão",str(exc))

    def disparar_edicao_dash(self):
        selecionado = self.tabela_dash.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione uma linha na tabela acima para editar!")
            return
        self.abrir_janela_edicao_movimento(selecionado[0])

    def editar_movimentacao_dash(self, event):
        selecionado = self.tabela_dash.selection()
        if not selecionado:
            return
        self.abrir_janela_edicao_movimento(selecionado[0])

    def abrir_janela_edicao_movimento(self, mov_id):
        movimento = self._servico_movimentacoes().get(int(mov_id))
        if movimento is None:
            return

        cli_id = movimento.customer_id
        tipo_antigo = movimento.movement_type
        desc_antiga = movimento.description
        valor_antigo = movimento.value

        janela_ed = ctk.CTkToplevel(self)
        janela_ed.title(f"Editar Lançamento / Venda #{mov_id}")
        janela_ed.geometry("420x400")
        janela_ed.configure(fg_color="#0d1117")
        janela_ed.grab_set()

        lbl = ctk.CTkLabel(janela_ed, text=f"✏️ Editar Lançamento #{mov_id}", font=ctk.CTkFont(size=18, weight="bold"), text_color="#00FF88")
        lbl.pack(pady=15)

        e_desc = ctk.CTkEntry(janela_ed, placeholder_text="Descrição do Produto / Serviço", height=38, fg_color="#161b22", text_color="#ffffff")
        e_desc.pack(padx=25, pady=8, fill="x")
        e_desc.insert(0, desc_antiga or "")

        e_val = ctk.CTkEntry(janela_ed, placeholder_text="Valor (R$)", height=38, fg_color="#161b22", text_color="#ffffff")
        e_val.pack(padx=25, pady=8, fill="x")
        e_val.insert(0, str(valor_antigo or 0.0))

        lbl_info_tipo = ctk.CTkLabel(janela_ed, text=f"Tipo de Lançamento: {tipo_antigo}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffd700")
        lbl_info_tipo.pack(pady=5)

        def salvar_alteracao_mov():
            try:
                novo_valor = tratar_numero(e_val.get())
            except ValueError:
                messagebox.showerror("Erro", "Valor inválido!")
                return
            nova_desc = e_desc.get().strip()

            try:
                self._servico_movimentacoes().update(int(mov_id), nova_desc, novo_valor)
            except Exception as exc:
                logging.getLogger("NabiCode.Movimentacoes").exception(
                    "Falha ao editar a movimentação %s", mov_id
                )
                messagebox.showerror("Erro", str(exc), parent=janela_ed)
                return

            messagebox.showinfo("Sucesso", "Lançamento atualizado com sucesso!", parent=janela_ed)
            janela_ed.destroy()
            self.carregar_historico_dia()
            self.atualizar_resumo_lateral()

        btn_salvar_ed = ctk.CTkButton(janela_ed, text="Salvar Alterações", fg_color="#2ea043", hover_color="#238636", height=42, font=ctk.CTkFont(weight="bold"), command=salvar_alteracao_mov)
        btn_salvar_ed.pack(padx=25, pady=15, fill="x")

    def tela_produtos(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        self.adicionar_rodape_status(frame)

        conteudo = ctk.CTkFrame(frame, fg_color="transparent")
        conteudo.pack(fill="both", expand=True, padx=20, pady=5)

        topo = ctk.CTkFrame(conteudo, fg_color="transparent")
        topo.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(topo, text="Cadastro de Produtos", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        ctk.CTkButton(topo, text="Cadastros auxiliares", width=165, fg_color="#8957e5",
                      hover_color="#6e40c9", command=self.abrir_cadastros_auxiliares).pack(side="right", padx=(6, 0))
        ctk.CTkButton(topo, text="＋ Nova categoria", width=145, fg_color="#8957e5",
                      hover_color="#6e40c9", command=self.abrir_cadastro_categoria).pack(side="right", padx=(6, 0))
        ctk.CTkButton(topo, text="＋ Novo produto", width=140, fg_color="#2ea043",
                      hover_color="#238636", command=self.abrir_cadastro_produto).pack(side="right")
        if modo_fiscal_ativo():
            ctk.CTkButton(topo, text="📄 Importar XML", width=140, fg_color="#1f6feb",
                          hover_color="#1158c7", command=self.abrir_importacao_xml).pack(side="right", padx=(0, 8))
            ctk.CTkButton(topo, text="🗑 Notas importadas", width=155, fg_color="#da3633",
                          hover_color="#b62324", command=self.abrir_historico_nfe_importadas).pack(side="right", padx=(0, 8))
            ctk.CTkButton(topo, text="↩ NF-e Devolução", width=150, fg_color="#d29922",
                          hover_color="#9e6a03", command=self.abrir_assistente_devolucao).pack(side="right", padx=(0, 8))

        busca_frame = ctk.CTkFrame(conteudo, fg_color="#161b22", corner_radius=10)
        busca_frame.pack(fill="x", pady=(0, 8))
        self.entry_busca_produto = ctk.CTkEntry(busca_frame, placeholder_text="Buscar por nome, código, EAN, marca ou fornecedor...",
                                                height=36, fg_color="#0d1117")
        self.entry_busca_produto.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        SearchEntryBehavior.attach(
            self.entry_busca_produto, on_enter=self.carregar_produtos
        )
        self.entry_busca_produto.bind("<KeyRelease>", lambda event: self.carregar_produtos())
        self.filtro_tipo_produto = ctk.CTkComboBox(busca_frame, values=["TODOS", "MERCADORIA", "SERVIÇO"],
                                                   width=145, command=lambda _v: self.carregar_produtos())
        self.filtro_tipo_produto.set("TODOS")
        self.filtro_tipo_produto.pack(side="left", padx=(0, 10), pady=10)

        tabela_frame = ctk.CTkFrame(conteudo, fg_color="#161b22", corner_radius=10)
        tabela_frame.pack(fill="both", expand=True)
        colunas = ("Codigo", "Nome", "Preco", "Estoque", "Categoria", "Marca", "Unidade", "Tipo")
        self.tabela_produtos = ttk.Treeview(tabela_frame, columns=colunas, show="headings")
        titulos = {"Codigo":"Código", "Nome":"Nome", "Preco":"Preço de Venda", "Estoque":"Estoque", "Categoria":"Categoria", "Marca":"Marca", "Unidade":"Un.", "Tipo":"Tipo do Produto"}
        larguras = {"Codigo":100, "Nome":230, "Preco":115, "Estoque":90, "Categoria":135, "Marca":120, "Unidade":65, "Tipo":120}
        for coluna in colunas:
            self.tabela_produtos.heading(coluna, text=titulos[coluna])
            self.tabela_produtos.column(coluna, width=larguras[coluna], anchor="w" if coluna in ("Nome","Categoria","Marca") else "center")
        self.tabela_produtos.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabela_produtos.bind("<Double-1>", lambda event: self.editar_produto_selecionado())

        acoes = ctk.CTkFrame(conteudo, fg_color="transparent")
        acoes.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(acoes, text="Editar selecionado", width=150, command=self.editar_produto_selecionado).pack(side="left")
        ctk.CTkButton(acoes, text="Duplicar", width=110, fg_color="#8957e5", hover_color="#6e40c9",
                      command=self.duplicar_produto_selecionado).pack(side="left", padx=(6, 0))
        ctk.CTkButton(acoes, text="Histórico", width=110, fg_color="#1f6feb", hover_color="#1158c7",
                      command=self.abrir_historico_produto_selecionado).pack(side="left", padx=(6, 0))
        ctk.CTkButton(acoes, text="Ativar/Desativar", width=145, fg_color="#bf8700", hover_color="#9e6a03",
                      command=self.alternar_status_produto).pack(side="left", padx=6)
        self.lbl_total_produtos = ctk.CTkLabel(acoes, text="0 produto(s)", text_color="#8b949e")
        self.lbl_total_produtos.pack(side="right")
        return frame

    def carregar_produtos(self):
        if not hasattr(self, "tabela_produtos"):
            return
        termo = self.entry_busca_produto.get().strip() if hasattr(self, "entry_busca_produto") else ""
        tipo = self.filtro_tipo_produto.get() if hasattr(self, "filtro_tipo_produto") else "TODOS"
        resultado = PRODUCT_APPLICATION_SERVICE.listar_tabela(termo, tipo)
        for item in self.tabela_produtos.get_children():
            self.tabela_produtos.delete(item)
        for linha in resultado.rows:
            self.tabela_produtos.insert(
                "", "end", iid=str(linha.produto_id), values=linha.values
            )
        self.lbl_total_produtos.configure(text=resultado.total_texto)

    def abrir_cadastros_auxiliares(self, tipo_inicial="marca", ao_fechar=None):
        tipo_inicial = str(tipo_inicial or "marca").strip().lower()
        if tipo_inicial not in {"marca", "fornecedor", "unidade"}:
            tipo_inicial = "marca"
        win = ctk.CTkToplevel(self)
        win.title("Cadastros auxiliares de produtos")
        metricas = UniversalLayoutPolicy.metrics(
            win.winfo_screenwidth(), win.winfo_screenheight(),
            preferred_width=760, preferred_height=620,
        )
        win.geometry(UniversalLayoutPolicy.geometry(metricas))
        win.minsize(*UniversalLayoutPolicy.safe_minsize(metricas))
        win.configure(fg_color="#0d1117")
        win.transient(self)

        cabecalho = ctk.CTkFrame(win, fg_color="#0d1117")
        cabecalho.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(cabecalho, text="Cadastros auxiliares", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.cor_acento).pack(anchor="w")
        ctk.CTkLabel(cabecalho, text="Marcas, fornecedores e unidades usadas nos produtos", text_color="#8b949e").pack(anchor="w", pady=(2, 0))

        scroll = BidirectionalScrollableFrame(win, fg_color="#161b22", corner_radius=10, content_width=700)
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        corpo = scroll.content
        corpo.grid_columnconfigure(0, weight=1)

        tipo_var = tk.StringVar(value=tipo_inicial)
        ctk.CTkLabel(corpo, text="Tipo de cadastro", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        ctk.CTkSegmentedButton(corpo, values=["marca", "fornecedor", "unidade"], variable=tipo_var).grid(row=1, column=0, sticky="ew", padx=12)
        ctk.CTkLabel(corpo, text="Nome ou sigla *", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="ew", padx=12, pady=(14, 4))
        entrada = ctk.CTkEntry(corpo, height=UniversalLayoutPolicy.metrics(1024, 768).row_height)
        entrada.grid(row=3, column=0, sticky="ew", padx=12)
        ctk.CTkLabel(corpo, text="Descrição / razão social", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=4, column=0, sticky="ew", padx=12, pady=(12, 4))
        descricao = ctk.CTkEntry(corpo, height=38)
        descricao.grid(row=5, column=0, sticky="ew", padx=12)
        ctk.CTkLabel(corpo, text="Registros cadastrados", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=6, column=0, sticky="ew", padx=12, pady=(12, 4))
        lista = tk.Listbox(corpo, height=12, bg="#161b22", fg="#f0f6fc", selectbackground="#1f6feb", relief="flat")
        lista.grid(row=7, column=0, sticky="nsew", padx=12, pady=(0, 12))
        corpo.grid_rowconfigure(7, weight=1)

        def carregar(*_):
            lista.delete(0, "end")
            for item in PRODUCT_APPLICATION_SERVICE.listar_auxiliares(tipo_var.get()):
                lista.insert("end", item.nome)
            entrada.delete(0, "end")
            descricao.delete(0, "end")
            entrada.focus_set()

        def salvar():
            tipo = tipo_var.get()
            try:
                PRODUCT_APPLICATION_SERVICE.criar_auxiliar_comando(
                    ProductAuxiliaryCreateCommand(
                        tipo=tipo, nome=entrada.get(), descricao=descricao.get()
                    )
                )
            except ProductApplicationError as exc:
                messagebox.showerror("Cadastro", str(exc), parent=win)
                return False
            except Exception as exc:
                messagebox.showerror("Cadastro", str(exc), parent=win)
                return False
            carregar()
            return True

        callback_executado = False

        def fechar():
            nonlocal callback_executado
            win.destroy()
            if not callback_executado and callable(ao_fechar):
                callback_executado = True
                ao_fechar()

        rodape = ctk.CTkFrame(win, fg_color="#0d1117")
        rodape.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkButton(rodape, text="Voltar", width=120, height=42, fg_color="#30363d", command=fechar).pack(side="left")
        ctk.CTkButton(rodape, text="Salvar", width=150, height=42, fg_color="#2ea043", command=salvar).pack(side="right")
        tipo_var.trace_add("write", carregar)
        win.bind("<Control-s>", lambda _event: salvar(), add="+")
        win.bind("<Escape>", lambda _event: fechar(), add="+")
        win.protocol("WM_DELETE_WINDOW", fechar)
        win._enter_navigator = install_enter_navigation([entrada, descricao], on_finish=salvar)
        carregar()

    def abrir_cadastro_categoria(self):
        win = ctk.CTkToplevel(self)
        win.title("Nova categoria")
        metricas = UniversalLayoutPolicy.metrics(
            win.winfo_screenwidth(), win.winfo_screenheight(),
            preferred_width=620, preferred_height=430,
        )
        win.geometry(UniversalLayoutPolicy.geometry(metricas))
        win.minsize(*UniversalLayoutPolicy.safe_minsize(metricas))
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()

        cabecalho = ctk.CTkFrame(win, fg_color="#0d1117")
        cabecalho.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(cabecalho, text="Cadastrar categoria", font=ctk.CTkFont(size=19, weight="bold"), text_color="#00FF88").pack(anchor="w")
        ctk.CTkLabel(cabecalho, text="Organize os produtos em uma categoria identificável", text_color="#8b949e").pack(anchor="w", pady=(2, 0))

        scroll = BidirectionalScrollableFrame(win, fg_color="#161b22", corner_radius=10, content_width=560)
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        corpo = scroll.content
        corpo.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(corpo, text="Nome da categoria *", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(18, 4))
        entrada = ctk.CTkEntry(corpo, height=38)
        entrada.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 18))

        def salvar():
            try:
                PRODUCT_APPLICATION_SERVICE.criar_categoria(entrada.get())
            except ValueError as exc:
                messagebox.showwarning("Categoria", str(exc), parent=win)
                return False
            except ProductApplicationError as exc:
                messagebox.showerror("Categoria", str(exc), parent=win)
                return False
            except Exception as exc:
                logger.exception("Falha ao cadastrar categoria")
                messagebox.showerror("Categoria", f"Não foi possível salvar a categoria.\n\n{exc}", parent=win)
                return False
            win.destroy()
            self.carregar_produtos()
            return True

        rodape = ctk.CTkFrame(win, fg_color="#0d1117")
        rodape.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkButton(rodape, text="Cancelar", width=120, height=42, fg_color="#30363d", command=win.destroy).pack(side="left")
        ctk.CTkButton(rodape, text="Salvar categoria", width=170, height=42, fg_color="#2ea043", command=salvar).pack(side="right")
        win.bind("<Control-s>", lambda _event: salvar(), add="+")
        win.bind("<Escape>", lambda _event: win.destroy(), add="+")
        entrada.bind("<Return>", lambda _event: salvar(), add="+")
        entrada.focus_set()

    def abrir_cadastro_produto(
        self, produto_id=None, dados_precarregados=None, *, aba_inicial=None, ao_salvar=None
    ):
        catalogo = PRODUCT_APPLICATION_SERVICE.carregar_catalogo_auxiliar()
        categorias = [(item.item_id, item.nome) for item in catalogo.categorias]
        mapa = catalogo.mapa_categorias
        marcas = [(item.item_id, item.nome) for item in catalogo.marcas]
        mapa_marcas = catalogo.mapa_marcas
        fornecedores = [(item.item_id, item.nome) for item in catalogo.fornecedores]
        mapa_fornecedores = catalogo.mapa_fornecedores
        unidades = [(item.item_id, item.nome) for item in catalogo.unidades]
        mapa_unidades = catalogo.mapa_unidades

        try:
            preparacao_cadastro = PRODUCT_APPLICATION_SERVICE.preparar_cadastro(
                produto_id, dados_precarregados,
                categorias=mapa, marcas=mapa_marcas, fornecedores=mapa_fornecedores,
                unidades=mapa_unidades, unidade_padrao=("UN" if "UN" in mapa_unidades else next(iter(mapa_unidades), "UN")),
            )
        except (TypeError, ValueError) as exc:
            messagebox.showwarning("Produtos", str(exc), parent=self)
            return

        produto_id = preparacao_cadastro.produto_id
        win = ctk.CTkToplevel(self)
        win.nabi_help_context = "produto_form"
        win.title(preparacao_cadastro.window_title)
        metricas_layout = UniversalLayoutPolicy.metrics(
            win.winfo_screenwidth(), win.winfo_screenheight(), preferred_width=1080, preferred_height=720
        )
        win.geometry(UniversalLayoutPolicy.geometry(metricas_layout))
        win.minsize(*UniversalLayoutPolicy.safe_minsize(metricas_layout))
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()

        titulo = ctk.CTkLabel(
            win,
            text=preparacao_cadastro.heading,
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color="#00FF88",
        )
        titulo.pack(fill="x", padx=18, pady=(14, 6))

        abas_produto = ctk.CTkTabview(win, fg_color="#161b22")
        abas_produto.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        aba_geral = abas_produto.add("Geral")
        aba_precos = abas_produto.add("Preços")
        aba_estoque = abas_produto.add("Estoque")
        aba_fiscal = abas_produto.add("Fiscal")
        if aba_inicial in {"Geral", "Preços", "Estoque", "Fiscal"}:
            abas_produto.set(aba_inicial)

        formularios = {}
        for nome, aba in (("geral", aba_geral), ("precos", aba_precos), ("estoque", aba_estoque), ("fiscal", aba_fiscal)):
            scroll_aba = BidirectionalScrollableFrame(aba, fg_color="#161b22", content_width=1040)
            scroll_aba.pack(fill="both", expand=True, padx=4, pady=4)
            formularios[nome] = scroll_aba.content
            formularios[nome].grid_columnconfigure((0, 1, 2), weight=1, uniform=f"produto_{nome}")

        def campo(parent, titulo_campo, linha, coluna, *, placeholder="", colspan=1):
            bloco = ctk.CTkFrame(parent, fg_color="transparent")
            bloco.grid(row=linha, column=coluna, columnspan=colspan, sticky="ew", padx=8, pady=6)
            ctk.CTkLabel(bloco, text=titulo_campo, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 3))
            entrada = ctk.CTkEntry(bloco, placeholder_text=placeholder, height=38)
            entrada.pack(fill="x")
            return entrada

        def combo(parent, titulo_campo, linha, coluna, values, valor_inicial, *, colspan=1):
            bloco = ctk.CTkFrame(parent, fg_color="transparent")
            bloco.grid(row=linha, column=coluna, columnspan=colspan, sticky="ew", padx=8, pady=6)
            ctk.CTkLabel(bloco, text=titulo_campo, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 3))
            widget = ctk.CTkComboBox(bloco, values=values, height=38)
            widget.set(valor_inicial)
            widget.pack(fill="x")
            return widget

        geral = formularios["geral"]
        precos = formularios["precos"]
        estoque = formularios["estoque"]
        fiscal = formularios["fiscal"]
        e_codigo = campo(geral, "Código automático", 0, 0)
        e_nome = campo(geral, "Nome do produto", 0, 1, colspan=2)
        combo_cat = combo(geral, "Categoria", 1, 0, ["Sem categoria"] + list(mapa), "Sem categoria")
        combo_marca = combo(geral, "Marca", 1, 1, ["Sem marca"] + list(mapa_marcas), "Sem marca")
        combo_fornecedor = combo(geral, "Fornecedor principal", 1, 2, ["Sem fornecedor"] + list(mapa_fornecedores), "Sem fornecedor")
        combo_tipo = combo(geral, "Tipo do produto", 2, 0, ["MERCADORIA", "SERVIÇO"], "MERCADORIA")

        e_custo = campo(precos, "Preço de custo (R$)", 0, 0)
        e_despesas = campo(precos, "Despesas adicionais (%)", 0, 1)
        e_margem = campo(precos, "Margem sobre o custo total (%)", 0, 2)
        e_preco = campo(precos, "Preço de venda (R$)", 1, 0)

        valores_unidades = list(mapa_unidades) or ["UN"]
        unidade_padrao = "UN" if "UN" in mapa_unidades else next(iter(mapa_unidades), "UN")
        e_estoque = campo(estoque, "Estoque atual / inicial", 0, 0)
        e_estoque_minimo = campo(estoque, "Estoque mínimo", 0, 1)
        combo_unidade = combo(estoque, "Unidade de estoque/venda", 1, 0, valores_unidades, unidade_padrao)
        combo_unidade_compra = combo(estoque, "Unidade de compra", 1, 1, valores_unidades, unidade_padrao)
        e_fator = campo(estoque, "Fator de conversão compra → estoque", 1, 2, placeholder="Ex.: 12 para 1 CX = 12 UN")

        e_ean = campo(fiscal, "Código de barras / EAN", 0, 0)
        e_ncm = campo(fiscal, "NCM (8 dígitos)", 0, 1)
        e_cest = campo(fiscal, "CEST (quando aplicável)", 0, 2)
        e_cfop = campo(fiscal, "CFOP de referência", 1, 0)
        e_origem = campo(fiscal, "Origem da mercadoria (0 a 8)", 1, 1)
        e_csosn = campo(fiscal, "CSOSN — Simples Nacional", 2, 0)
        e_icms_cst = campo(fiscal, "CST ICMS — regime normal", 2, 1)
        e_icms_rate = campo(fiscal, "Alíquota ICMS (%)", 2, 2)
        e_pis_cst = campo(fiscal, "CST PIS", 3, 0)
        e_pis_rate = campo(fiscal, "Alíquota PIS (%)", 3, 1)
        e_cofins_cst = campo(fiscal, "CST COFINS", 3, 2)
        e_cofins_rate = campo(fiscal, "Alíquota COFINS (%)", 4, 0)
        e_ibs_cst = campo(fiscal, "CST IBS/CBS", 4, 1)
        e_ibs_class = campo(fiscal, "Classificação IBS/CBS", 4, 2)
        e_ibs_uf_rate = campo(fiscal, "IBS estadual (%)", 5, 0)
        e_ibs_city_rate = campo(fiscal, "IBS municipal (%)", 5, 1)
        e_cbs_rate = campo(fiscal, "CBS (%)", 5, 2)
        ctk.CTkLabel(
            fiscal,
            text=("A NF-e de compra atualiza NCM, CEST, origem e IBS/CBS quando presentes. "
                  "CSOSN/CST de venda devem refletir a tributação da sua empresa e não são copiados cegamente do fornecedor."),
            anchor="w", justify="left", text_color="#8b949e", wraplength=780,
        ).grid(row=6, column=0, columnspan=3, sticky="ew", padx=8, pady=12)

        opcoes = ctk.CTkFrame(estoque, fg_color="transparent")
        opcoes.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(opcoes, text="Controle de estoque", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 7))
        permite_negativo_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opcoes, text="Permitir estoque negativo", variable=permite_negativo_var).pack(anchor="w")


        controlador_preco = ProductPricingController(ProductPricingControls(
            custo=e_custo, despesas_percentual=e_despesas,
            margem_lucro=e_margem, preco_venda=e_preco,
        ))

        def aplicar_preco_sugerido():
            try:
                controlador_preco.apply_suggested_price()
            except ValueError as exc:
                messagebox.showwarning("Formação de preço", str(exc), parent=win)

        for campo_origem in (e_custo, e_despesas, e_margem):
            campo_origem.bind("<KeyRelease>", controlador_preco.on_cost_or_margin_changed, add="+")
            campo_origem.bind("<FocusOut>", controlador_preco.on_cost_or_margin_changed, add="+")
        e_preco.bind("<KeyRelease>", controlador_preco.on_sale_price_changed, add="+")
        e_preco.bind("<FocusOut>", controlador_preco.on_sale_price_changed, add="+")

        formulario_produto = ProductFormBinding(ProductFormControls(
            codigo=e_codigo, nome=e_nome, preco_venda=e_preco, categoria=combo_cat,
            tipo_produto=combo_tipo, marca=combo_marca, fornecedor=combo_fornecedor,
            unidade=combo_unidade, unidade_compra=combo_unidade_compra,
            fator_conversao=e_fator, preco_custo=e_custo, despesas_percentual=e_despesas,
            margem_lucro=e_margem, codigo_barras=e_ean, estoque_atual=e_estoque,
            estoque_minimo=e_estoque_minimo, permite_estoque_negativo=permite_negativo_var,
        ))
        formulario_produto.apply(preparacao_cadastro.state, codigo_editavel=bool(produto_id))
        perfil_fiscal = PRODUTO_SERVICE.buscar(int(produto_id)) if produto_id else {}
        for widget, value in (
            (e_ncm, perfil_fiscal.get("ncm", "")), (e_cest, perfil_fiscal.get("cest", "")),
            (e_cfop, perfil_fiscal.get("cfop", "")), (e_origem, perfil_fiscal.get("fiscal_origin", "")),
            (e_csosn, perfil_fiscal.get("fiscal_csosn", "")),
            (e_icms_cst, perfil_fiscal.get("fiscal_icms_cst", "")),
            (e_icms_rate, perfil_fiscal.get("fiscal_icms_rate", "0")),
            (e_pis_cst, perfil_fiscal.get("fiscal_pis_cst", "")),
            (e_pis_rate, perfil_fiscal.get("fiscal_pis_rate", "0")),
            (e_cofins_cst, perfil_fiscal.get("fiscal_cofins_cst", "")),
            (e_cofins_rate, perfil_fiscal.get("fiscal_cofins_rate", "0")),
            (e_ibs_cst, perfil_fiscal.get("ibs_cbs_cst", "")),
            (e_ibs_class, perfil_fiscal.get("ibs_cbs_class", "")),
            (e_ibs_uf_rate, perfil_fiscal.get("ibs_uf_rate", "0")),
            (e_ibs_city_rate, perfil_fiscal.get("ibs_city_rate", "0")),
            (e_cbs_rate, perfil_fiscal.get("cbs_rate", "0")),
        ):
            widget.insert(0, str(value or ""))

        def salvar():
            try:
                duplicidade = PRODUCT_APPLICATION_SERVICE.avaliar_duplicidade(
                    e_nome.get(), codigo_barras=e_ean.get(), produto_id=produto_id
                )
                if duplicidade.possui_similares and not messagebox.askyesno(
                    "Possível produto duplicado",
                    "Foram encontrados produtos semelhantes:\n\n" + duplicidade.resumo() +
                    "\n\nDeseja salvar mesmo assim?",
                    parent=win,
                ):
                    return False
                estado_atual = formulario_produto.capture()
                dados_formulario = PRODUCT_APPLICATION_SERVICE.criar_dados_formulario(
                    estado_atual, categorias=mapa, marcas=mapa_marcas,
                    fornecedores=mapa_fornecedores, unidades=mapa_unidades,
                    produto_id=produto_id, usuario="Sistema",
                )
                dados_formulario = replace(
                    dados_formulario,
                    ncm=e_ncm.get(), cest=e_cest.get(), cfop=e_cfop.get(),
                    fiscal_origin=e_origem.get(), fiscal_csosn=e_csosn.get(),
                    fiscal_icms_cst=e_icms_cst.get(), fiscal_icms_rate=e_icms_rate.get(),
                    fiscal_pis_cst=e_pis_cst.get(), fiscal_pis_rate=e_pis_rate.get(),
                    fiscal_cofins_cst=e_cofins_cst.get(), fiscal_cofins_rate=e_cofins_rate.get(),
                    fiscal_profile_source="MANUAL", ibs_cbs_cst=e_ibs_cst.get(),
                    ibs_cbs_class=e_ibs_class.get(), ibs_uf_rate=e_ibs_uf_rate.get(),
                    ibs_city_rate=e_ibs_city_rate.get(), cbs_rate=e_cbs_rate.get(),
                )
                comando = PRODUCT_APPLICATION_SERVICE.criar_comando(dados_formulario)
                resultado_salvamento = PRODUCT_APPLICATION_SERVICE.salvar(comando)
            except ValueError as exc:
                messagebox.showwarning("Produto", str(exc), parent=win)
                return False
            except sqlite3.IntegrityError as exc:
                messagebox.showerror(
                    "Produto",
                    PRODUCT_APPLICATION_SERVICE.mensagem_integridade(exc),
                    parent=win,
                )
                return False
            except Exception as exc:
                logger.exception("Falha ao salvar produto")
                messagebox.showerror("Produto", f"Não foi possível salvar o produto.\n\n{exc}", parent=win)
                return False
            self.mostrar_notificacao(
                "Produto salvo",
                f"{e_nome.get().strip().upper()} foi salvo com sucesso.",
                nivel="success", parent=win,
            )
            if resultado_salvamento.estoque_foi_ajustado:
                self.mostrar_notificacao(
                    "Estoque atualizado",
                    (
                        f"Saldo ajustado de {resultado_salvamento.estoque_anterior:.3f} "
                        f"para {resultado_salvamento.estoque_atual:.3f}."
                    ),
                    nivel="success", parent=win,
                )
            win.destroy()
            self.carregar_produtos()
            if callable(ao_salvar):
                ao_salvar()
            return True

        rodape = ctk.CTkFrame(win, fg_color="#0d1117")
        rodape.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkButton(rodape, text="Cancelar", width=120, height=42, fg_color="#30363d", command=win.destroy).pack(side="left")
        ctk.CTkButton(rodape, text="Calcular preço sugerido", width=210, height=42, fg_color="#1f6feb", command=aplicar_preco_sugerido).pack(side="right", padx=(8, 0))
        ctk.CTkButton(rodape, text="Salvar produto", width=170, height=42, fg_color="#2ea043", command=salvar).pack(side="right")

        def validar_nome_produto():
            try:
                PRODUCT_APPLICATION_SERVICE.validar_nome_formulario(e_nome.get())
                return True
            except ValueError as exc:
                messagebox.showwarning("Produto", str(exc), parent=win)
                return False

        def validar_numero_produto(widget, rotulo, *, maior_zero=False):
            def _validar():
                try:
                    PRODUCT_APPLICATION_SERVICE.validar_numero_formulario(
                        widget.get() or "0", rotulo, maior_zero=maior_zero
                    )
                    return True
                except ValueError as exc:
                    messagebox.showwarning("Produto", str(exc), parent=win)
                    return False
            return _validar

        win._enter_navigator = install_enter_navigation(
            [
                e_codigo,
                EnterField(e_nome, validar_nome_produto),
                EnterField(e_custo, validar_numero_produto(e_custo, "Preço de custo")),
                EnterField(e_despesas, validar_numero_produto(e_despesas, "Despesas adicionais")),
                EnterField(e_margem, validar_numero_produto(e_margem, "Margem")),
                EnterField(e_preco, validar_numero_produto(e_preco, "Preço de venda")),
                EnterField(e_estoque, validar_numero_produto(e_estoque, "Estoque")),
                EnterField(e_estoque_minimo, validar_numero_produto(e_estoque_minimo, "Estoque mínimo")),
                e_ean,
                combo_cat,
                combo_marca,
                combo_fornecedor,
                combo_unidade,
                combo_unidade_compra,
                EnterField(e_fator, validar_numero_produto(e_fator, "Fator de conversão", maior_zero=True)),
                combo_tipo,
            ],
            on_finish=salvar,
        )
        def estado_produto():
            return (
                e_codigo.get(), e_nome.get(), e_custo.get(), e_despesas.get(), e_margem.get(),
                e_preco.get(), e_estoque.get(), e_estoque_minimo.get(), e_ean.get(), combo_cat.get(),
                combo_marca.get(), combo_fornecedor.get(), combo_unidade.get(),
                combo_unidade_compra.get(), e_fator.get(), combo_tipo.get(),
                bool(permite_negativo_var.get()),
                e_ncm.get(), e_cest.get(), e_cfop.get(), e_origem.get(), e_csosn.get(),
                e_icms_cst.get(), e_icms_rate.get(), e_pis_cst.get(), e_pis_rate.get(),
                e_cofins_cst.get(), e_cofins_rate.get(), e_ibs_cst.get(), e_ibs_class.get(),
                e_ibs_uf_rate.get(), e_ibs_city_rate.get(), e_cbs_rate.get(),
            )

        estado_inicial_produto = estado_produto()
        self.window_actions.register(
            win,
            save=salvar,
            close=win.destroy,
            is_dirty=lambda: estado_produto() != estado_inicial_produto,
            title="Produto",
        )
        win.bind("<Control-s>", lambda _event: self.window_actions.save(win))
        win.bind("<Escape>", lambda _event: self.window_actions.close(win))
        e_codigo.focus_set()

    def editar_produto_selecionado(self):
        if not hasattr(self, "tabela_produtos"):
            return
        try:
            produto_id = PRODUCT_APPLICATION_SERVICE.obter_produto_id_selecionado(
                self.tabela_produtos.selection()
            )
        except ValueError as exc:
            messagebox.showwarning("Produtos", str(exc))
            return
        self.abrir_cadastro_produto(produto_id)

    def duplicar_produto_selecionado(self):
        try:
            dados = PRODUCT_APPLICATION_SERVICE.preparar_duplicacao(
                self.tabela_produtos.selection() if hasattr(self, "tabela_produtos") else ()
            )
        except ValueError as exc:
            messagebox.showwarning("Produtos", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Produtos", str(exc))
            return
        self.abrir_cadastro_produto(dados_precarregados=dados)

    def abrir_historico_produto_selecionado(self):
        try:
            historico = PRODUCT_APPLICATION_SERVICE.obter_historico(
                self.tabela_produtos.selection() if hasattr(self, "tabela_produtos") else ()
            )
        except ValueError as exc:
            messagebox.showwarning("Produtos", str(exc))
            return
        except Exception as exc:
            logger.exception("Falha ao carregar histórico do produto")
            messagebox.showerror("Produtos", f"Não foi possível carregar o histórico.\n\n{exc}")
            return
        win = ctk.CTkToplevel(self)
        win.title(historico.titulo)
        win.geometry("900x480")
        win.configure(fg_color="#0d1117")
        colunas = ("Data", "Motivo", "PrecoAnterior", "PrecoNovo", "Custo", "Margem")
        tabela = ttk.Treeview(win, columns=colunas, show="headings")
        titulos = {"Data":"Data", "Motivo":"Motivo", "PrecoAnterior":"Preço anterior", "PrecoNovo":"Preço novo", "Custo":"Custo", "Margem":"Margem %"}
        for coluna in colunas:
            tabela.heading(coluna, text=titulos[coluna])
            tabela.column(coluna, width=145, anchor="center")
        tabela.pack(fill="both", expand=True, padx=16, pady=16)
        for item in historico.rows:
            tabela.insert("", "end", values=item.values)

    def alternar_status_produto(self):
        try:
            PRODUCT_APPLICATION_SERVICE.alternar_status(
                self.tabela_produtos.selection() if hasattr(self, "tabela_produtos") else ()
            )
        except ValueError as exc:
            messagebox.showwarning("Produtos", str(exc))
            return
        except Exception as exc:
            logger.exception("Falha ao alterar status do produto")
            messagebox.showerror("Produtos", f"Não foi possível alterar o status.\n\n{exc}")
            return
        self.carregar_produtos()

    def abrir_assistente_devolucao(self):
        win = ctk.CTkToplevel(self)
        win.nabi_help_context = "nfe_devolucao"
        win.title("Assistente de NF-e de Devolução")
        win.geometry("1120x760")
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="Assistente de NF-e de Devolução",
                     font=ctk.CTkFont(size=21, weight="bold"),
                     text_color=self.cor_acento).pack(pady=(16, 4))
        ctk.CTkLabel(win, text="Localize a nota original, escolha devolução integral ou parcial e gere um rascunho para conferência fiscal.",
                     text_color="#8b949e").pack(pady=(0, 12))

        busca = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=10)
        busca.pack(fill="x", padx=18, pady=6)
        referencia = ctk.CTkEntry(busca, placeholder_text="Número ou chave de acesso da nota original", height=38)
        referencia.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        info = ctk.CTkLabel(win, text="Nenhuma nota selecionada.", text_color="#c9d1d9")
        info.pack(anchor="w", padx=20, pady=(4, 2))

        tipo_var = tk.StringVar(value="PARCIAL")
        opcoes = ctk.CTkFrame(win, fg_color="transparent")
        opcoes.pack(fill="x", padx=18, pady=(4, 4))
        ctk.CTkRadioButton(opcoes, text="Devolução parcial", variable=tipo_var, value="PARCIAL").pack(side="left", padx=6)
        ctk.CTkRadioButton(opcoes, text="Devolução integral", variable=tipo_var, value="INTEGRAL").pack(side="left", padx=18)

        tabela_frame = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=10)
        tabela_frame.pack(fill="both", expand=True, padx=18, pady=6)
        colunas = ("Codigo", "Descricao", "Original", "Devolvida", "Disponivel", "Quantidade", "Unidade", "Valor")
        tabela = ttk.Treeview(tabela_frame, columns=colunas, show="headings", selectmode="extended")
        titulos = {"Codigo":"Código", "Descricao":"Produto", "Original":"Qtd. original", "Devolvida":"Já devolvida",
                   "Disponivel":"Disponível", "Quantidade":"Qtd. a devolver", "Unidade":"Un.", "Valor":"Valor unitário"}
        larguras = {"Codigo":95, "Descricao":280, "Original":95, "Devolvida":95, "Disponivel":90, "Quantidade":110, "Unidade":60, "Valor":100}
        for coluna in colunas:
            tabela.heading(coluna, text=titulos[coluna])
            tabela.column(coluna, width=larguras[coluna], anchor="w" if coluna=="Descricao" else "center")
        tabela.pack(fill="both", expand=True, padx=10, pady=10)

        estado = {"nota": None, "itens": {}}

        def importar_xml_origem():
            caminho = filedialog.askopenfilename(title="Selecionar XML da nota original", filetypes=[("XML de NF-e", "*.xml")], parent=win)
            if not caminho:
                return
            try:
                NFE_DEVOLUCAO_SERVICE.registrar_xml_origem(caminho)
                documento = NFeXMLService().ler(caminho)
                referencia.delete(0, "end")
                referencia.insert(0, documento.chave or documento.numero)
                localizar()
            except Exception as exc:
                messagebox.showerror("NF-e de Devolução", str(exc), parent=win)

        def localizar():
            try:
                nota, itens = NFE_DEVOLUCAO_SERVICE.localizar_nota(referencia.get())
            except Exception as exc:
                messagebox.showwarning("NF-e de Devolução", str(exc), parent=win)
                return
            estado["nota"] = nota
            estado["itens"] = {item.item_origem_id: item for item in itens}
            for iid in tabela.get_children():
                tabela.delete(iid)
            for item in itens:
                tabela.insert("", "end", iid=str(item.item_origem_id), values=(
                    item.codigo, item.descricao, f"{item.quantidade_original:g}", f"{item.quantidade_devolvida:g}",
                    f"{item.quantidade_disponivel:g}", f"{item.quantidade_disponivel:g}", item.unidade, f"R$ {item.valor_unitario:.2f}"
                ))
            participante = nota.get("destinatario_nome") or nota.get("emitente_nome") or "-"
            info.configure(
                text=(
                    f"NF-e {nota.get('numero') or '-'} | Série {nota.get('serie') or '-'} | "
                    f"Participante: {participante} | Chave: {nota.get('chave') or '-'}"
                )
            )
            tabela.selection_set([str(item.item_origem_id) for item in itens if item.quantidade_disponivel > 0])

        ctk.CTkButton(busca, text="Localizar", width=110, command=localizar, fg_color="#1f6feb").pack(side="left", padx=(0, 6), pady=10)
        ctk.CTkButton(busca, text="Importar XML original", width=165, command=importar_xml_origem, fg_color="#8957e5").pack(side="left", padx=(0, 10), pady=10)

        formulario = ctk.CTkFrame(win, fg_color="transparent")
        formulario.pack(fill="x", padx=18, pady=(4, 4))
        motivo = ctk.CTkComboBox(formulario, values=["Troca", "Defeito", "Quantidade incorreta", "Desistência", "Outro"], width=220)
        motivo.set("Troca")
        motivo.pack(side="left", padx=(0, 8))
        observacoes = ctk.CTkEntry(formulario, placeholder_text="Observações da devolução", height=36)
        observacoes.pack(side="left", fill="x", expand=True)

        def editar_quantidade(_event=None):
            selecionado = tabela.selection()
            if len(selecionado) != 1:
                return
            iid = selecionado[0]
            item = estado["itens"].get(int(iid))
            if not item:
                return
            valor = simpledialog.askfloat(
                "Quantidade a devolver",
                f"{item.descricao}\nDisponível: {item.quantidade_disponivel:g} {item.unidade}",
                minvalue=0.000001, maxvalue=item.quantidade_disponivel, parent=win
            )
            if valor is None:
                return
            valores = list(tabela.item(iid, "values"))
            valores[5] = f"{valor:g}"
            tabela.item(iid, values=valores)

        tabela.bind("<Double-1>", editar_quantidade)

        def gerar_rascunho():
            if not estado["nota"]:
                messagebox.showwarning("NF-e de Devolução", "Localize a nota original.", parent=win)
                return
            selecoes = []
            if tipo_var.get() == "PARCIAL":
                for iid in tabela.selection():
                    valores = tabela.item(iid, "values")
                    try:
                        quantidade = float(str(valores[5]).replace(",", "."))
                    except (ValueError, IndexError):
                        quantidade = 0
                    selecoes.append((int(iid), quantidade))
            try:
                rascunho_id = NFE_DEVOLUCAO_SERVICE.criar_rascunho(
                    referencia_nota=referencia.get(), tipo=tipo_var.get(), selecoes=selecoes,
                    motivo=motivo.get(), observacoes=observacoes.get(),
                )
                rascunho = NFE_DEVOLUCAO_SERVICE.repository.buscar_rascunho(rascunho_id)
                pendencias = NFE_DEVOLUCAO_SERVICE.validar_rascunho(rascunho_id)
                xml_gerado = ""
                if not pendencias:
                    pasta_saida = Path(APP_DIR) / "relatorios" / "nfe_devolucoes"
                    xml_gerado = str(NFE_DEVOLUCAO_SERVICE.finalizar_rascunho(rascunho_id, pasta_saida))
                    rascunho = NFE_DEVOLUCAO_SERVICE.repository.buscar_rascunho(rascunho_id)
            except Exception as exc:
                messagebox.showerror("NF-e de Devolução", str(exc), parent=win)
                return
            registrar_auditoria("Fiscal", "Criar rascunho de devolução", str(rascunho_id),
                               f"Nota {rascunho.get('nota_numero')} | Total R$ {rascunho.get('valor_total', 0):.2f}")
            resumo_pendencias = ""
            if pendencias:
                resumo_pendencias = "\n\nPendências fiscais:\n- " + "\n- ".join(pendencias[:8])
                if len(pendencias) > 8:
                    resumo_pendencias += f"\n- ... e mais {len(pendencias) - 8} pendência(s)."
            mensagem = (
                f"Rascunho #{rascunho_id} criado com sucesso.\n\n"
                f"Nota original: {rascunho.get('nota_numero') or '-'}\n"
                f"Cliente/destinatário: {rascunho.get('destinatario_nome') or '-'}\n"
                f"Itens: {len(rascunho.get('itens', []))}\n"
                f"Total: R$ {float(rascunho.get('valor_total') or 0):.2f}"
                f"{resumo_pendencias}\n\n"
                + (f"XML de rascunho gerado em:\n{xml_gerado}\n\n" if xml_gerado else "")
                + "Use o Histórico para validar, transmitir e acompanhar o ciclo fiscal da devolução."
            )
            if pendencias:
                messagebox.showwarning("NF-e de Devolução", mensagem, parent=win)
            else:
                messagebox.showinfo("NF-e de Devolução", mensagem, parent=win)
            win.destroy()

        rodape = ctk.CTkFrame(win, fg_color="transparent")
        rodape.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkLabel(rodape, text="Duplo clique no item altera a quantidade da devolução parcial.", text_color="#8b949e").pack(side="left")
        ctk.CTkButton(rodape, text="Gerar rascunho", width=160, height=40, fg_color="#2ea043", command=gerar_rascunho).pack(side="right")
        ctk.CTkButton(rodape, text="Histórico", width=110, height=40, fg_color="#8957e5", command=self.abrir_historico_devolucoes).pack(side="right", padx=8)
        ctk.CTkButton(rodape, text="Fechar", width=100, height=40, fg_color="#30363d", command=win.destroy).pack(side="right")

    def abrir_historico_devolucoes(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Histórico de devoluções")
        janela.geometry("1120x680")
        janela.minsize(900, 560)
        janela.transient(self)
        janela.grab_set()

        ctk.CTkLabel(janela, text="Histórico de devoluções",
                     font=ctk.CTkFont(size=21, weight="bold"),
                     text_color=self.cor_acento).pack(pady=(16, 8))
        quadro = ctk.CTkFrame(janela, fg_color="#161b22", corner_radius=10)
        quadro.pack(fill="both", expand=True, padx=18, pady=8)
        colunas = ("Id", "Nota", "Tipo", "Status", "Total", "Chave", "Protocolo", "Atualizado")
        tabela = ttk.Treeview(quadro, columns=colunas, show="headings", selectmode="browse")
        larguras = {"Id":60, "Nota":90, "Tipo":90, "Status":110, "Total":100, "Chave":300, "Protocolo":130, "Atualizado":145}
        for coluna in colunas:
            tabela.heading(coluna, text=coluna)
            tabela.column(coluna, width=larguras[coluna], anchor="center")
        ybar = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
        xbar = ttk.Scrollbar(quadro, orient="horizontal", command=tabela.xview)
        tabela.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tabela.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
        ybar.grid(row=0, column=1, sticky="ns", pady=(10, 0))
        xbar.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))
        quadro.grid_rowconfigure(0, weight=1)
        quadro.grid_columnconfigure(0, weight=1)
        registros = {}

        def carregar():
            registros.clear()
            for iid in tabela.get_children():
                tabela.delete(iid)
            try:
                itens = NFE_DEVOLUCAO_SERVICE.listar_historico()
            except Exception as exc:
                messagebox.showerror("Devoluções", str(exc), parent=janela)
                return
            for item in itens:
                devolucao_id = int(item["id"])
                registros[devolucao_id] = item
                tabela.insert("", "end", iid=str(devolucao_id), values=(
                    devolucao_id, item.get("nota_numero") or "-", item.get("tipo") or "-",
                    item.get("fiscal_status") or item.get("status") or "-",
                    f"R$ {float(item.get('valor_total') or 0):.2f}",
                    item.get("access_key") or "-", item.get("protocol") or "-",
                    item.get("atualizado_em") or item.get("criado_em") or "-",
                ))

        def selecionado():
            ids = tabela.selection()
            if not ids:
                messagebox.showwarning("Devoluções", "Selecione uma devolução.", parent=janela)
                return None
            return registros.get(int(ids[0]))

        def abrir_arquivo():
            item = selecionado()
            if not item:
                return
            estado = NFE_DEVOLUCAO_SERVICE.estado_fiscal(int(item["id"]))
            fiscal_record = dict(estado.get("fiscal_record") or {})
            candidatos = [
                fiscal_record.get("processed_path"), fiscal_record.get("request_path"),
                fiscal_record.get("response_path"), item.get("xml_rascunho"),
            ]
            caminho = next((str(v) for v in candidatos if v and Path(str(v)).is_file()), "")
            if not caminho:
                messagebox.showwarning("Devoluções", "Nenhum arquivo fiscal disponível para esta devolução.", parent=janela)
                return
            try:
                self._abrir_arquivo_sistema(caminho)
            except Exception as exc:
                messagebox.showerror("Devoluções", str(exc), parent=janela)

        def gerar_danfe():
            item = selecionado()
            if not item:
                return
            destino = filedialog.asksaveasfilename(parent=janela, title="Salvar DANFE da devolução",
                defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
            if not destino:
                return
            try:
                NFE_DEVOLUCAO_SERVICE.gerar_danfe_devolucao(
                    int(item["id"]), fiscal_service=self.fiscal_service, output_path=destino
                )
                self.mostrar_notificacao("DANFE gerado", destino, nivel="success")
            except Exception as exc:
                messagebox.showerror("Devoluções", str(exc), parent=janela)

        def _dados_emissao_oficial(item):
            config = self.fiscal_service.load_config()
            problemas = self.fiscal_service.validate_ready(operation="autorizacao", model="55")
            issuer_cfg = dict(config.get("issuer") or {})
            obrigatorios = {
                "Razão social": issuer_cfg.get("name"),
                "Inscrição estadual": issuer_cfg.get("state_registration"),
                "Código IBGE do município": issuer_cfg.get("city_code"),
                "Município": issuer_cfg.get("city"),
                "Logradouro": issuer_cfg.get("street"),
                "Número": issuer_cfg.get("number"),
                "Bairro": issuer_cfg.get("district"),
                "CEP": issuer_cfg.get("zip_code"),
            }
            problemas.extend(f"{nome} do emitente não configurado." for nome, valor in obrigatorios.items() if not str(valor or "").strip())
            if problemas:
                raise ValueError("Configuração fiscal incompleta:\n- " + "\n- ".join(problemas))
            rascunho = NFE_DEVOLUCAO_SERVICE.repository.buscar_rascunho(int(item["id"]))
            if not rascunho:
                raise ValueError("Rascunho de devolução não localizado.")
            overrides = {}
            for produto in rascunho.get("itens", []):
                analysis = NFE_DEVOLUCAO_SERVICE.sugerir_cfop_devolucao(
                    str(produto.get("cfop") or ""),
                    cst_icms=str(produto.get("cst_icms") or ""),
                    csosn=str(produto.get("csosn") or ""),
                )
                cfop = str(analysis.get("suggested") or "")
                if not cfop:
                    raise ValueError(
                        f"Não foi possível determinar o CFOP de devolução para "
                        f"'{produto.get('descricao') or 'Produto'}'. Revise o XML original."
                    )
                overrides[int(produto["item_origem_id"])] = {
                    "cfop": cfop, "cfop_analysis": analysis,
                }
            actor = self._usuario_financeiro()
            series = int(issuer_cfg.get("return_series") or 1)
            reservation = self.fiscal_service.reserve_number(
                model="55", series=series, actor=actor, environment=config.get("environment")
            )
            issuer = {
                "cnpj": config.get("cnpj"), "name": issuer_cfg.get("name"),
                "state_registration": issuer_cfg.get("state_registration"),
                "city_code": issuer_cfg.get("city_code"), "city": issuer_cfg.get("city"),
                "street": issuer_cfg.get("street"), "number": issuer_cfg.get("number"),
                "district": issuer_cfg.get("district"), "zip_code": issuer_cfg.get("zip_code"),
                "state": config.get("state"),
                "tax_regime": config.get("tax_regime"),
                "tax_regime_code": self.fiscal_service.TAX_REGIME_CODES.get(str(config.get("tax_regime") or "").upper(), 1),
            }
            document = {
                "environment": config.get("environment"),
                "state_code": self.fiscal_service.STATE_CODES.get(str(config.get("state") or "").upper()),
                "series": series,
                "number": int(reservation["number"]),
                "numeric_code": f"{int(reservation['number']):08d}"[-8:],
                "issued_at": datetime.now().astimezone(),
                "final_consumer": 0,
                "presence": 9,
                "payment_code": "90",
            }
            return issuer, document, overrides, reservation, actor

        def emitir_oficial():
            item = selecionado()
            if not item:
                return
            status = str(item.get("fiscal_status") or item.get("status") or "").upper()
            if status in {"AUTORIZADA", "AUTORIZADA_PENDENTE_ESTOQUE", "CANCELADA", "CANCELADA_PENDENTE_ESTOQUE"}:
                messagebox.showwarning("Devoluções", "A devolução já possui ciclo fiscal definitivo.", parent=janela)
                return
            senha = self._obter_senha_certificado(parent=janela)
            if senha is None:
                return
            reservation = None
            try:
                issuer, document, overrides, reservation, actor = _dados_emissao_oficial(item)
                rascunho = NFE_DEVOLUCAO_SERVICE.repository.buscar_rascunho(int(item["id"])) or {}
                analyses = [dict(value.get("cfop_analysis") or {}) for value in overrides.values()]
                cfops = sorted({str(value.get("cfop") or "") for value in overrides.values()})
                medium = sum(1 for value in analyses if value.get("confidence") != "ALTA")
                if not messagebox.askyesno(
                    "Transmitir devolução",
                    f"Transmitir a NF-e de devolução #{item['id']} para a SEFAZ?\n\n"
                    f"Ambiente: {self.fiscal_service.load_config().get('environment')}\n"
                    f"Série: {document['series']} | Número: {document['number']}\n"
                    f"Itens selecionados: {len(rascunho.get('itens', []))}\n"
                    f"CFOP analisado automaticamente: {', '.join(cfops)}"
                    + (f"\nAtenção: {medium} item(ns) exigem conferência contábil posterior." if medium else ""),
                    parent=janela,
                ):
                    self.fiscal_service.release_number(reservation["reservation_id"], actor=actor, reason="Emissão cancelada antes da transmissão")
                    return
                estado = NFE_DEVOLUCAO_SERVICE.emitir_devolucao_oficial(
                    int(item["id"]), fiscal_service=self.fiscal_service, issuer=issuer,
                    document=document, item_overrides=overrides, password=senha,
                    actor=actor, reservation_id=reservation["reservation_id"],
                )
                registrar_auditoria("Fiscal", "Emitir NF-e de devolução", str(item["id"]),
                                   f"Status {estado.get('status')} | Chave {estado.get('access_key') or '-'}")
                carregar()
                if estado.get("status") == "AUTORIZADA":
                    self.mostrar_notificacao("Devolução autorizada", f"Protocolo {estado.get('protocol')}", nivel="success")
                else:
                    messagebox.showwarning("Devoluções", estado.get("message") or "Documento rejeitado pela SEFAZ.", parent=janela)
            except RuntimeError as exc:
                if str(exc) != "Emissão cancelada pelo usuário.":
                    messagebox.showerror("Devoluções", str(exc), parent=janela)
            except Exception as exc:
                if reservation:
                    try:
                        self.fiscal_service.release_number(
                            reservation["reservation_id"], actor=self._usuario_financeiro(),
                            reason=f"Falha antes da autorização: {exc}",
                        )
                    except Exception:
                        pass
                messagebox.showerror("Devoluções", str(exc), parent=janela)

        def cancelar_oficial():
            item = selecionado()
            if not item:
                return
            estado = NFE_DEVOLUCAO_SERVICE.estado_fiscal(int(item["id"]))
            if str(estado.get("status") or "").upper() not in {"AUTORIZADA", "AUTORIZADA_PENDENTE_ESTOQUE"}:
                messagebox.showwarning("Devoluções", "Somente devolução autorizada pode ser cancelada oficialmente.", parent=janela)
                return
            justificativa = simpledialog.askstring(
                "Cancelamento fiscal", "Justificativa do cancelamento (mínimo 15 caracteres):", parent=janela
            )
            if justificativa is None:
                return
            senha = self._obter_senha_certificado(parent=janela)
            if senha is None:
                return
            if not messagebox.askyesno("Confirmar cancelamento", "Transmitir o evento oficial de cancelamento?", parent=janela):
                return
            try:
                novo_estado = NFE_DEVOLUCAO_SERVICE.cancelar_devolucao_oficial(
                    int(item["id"]), fiscal_service=self.fiscal_service, password=senha,
                    actor=self._usuario_financeiro(), justification=justificativa,
                )
                registrar_auditoria("Fiscal", "Cancelar NF-e de devolução", str(item["id"]),
                                   f"Status {novo_estado.get('status')}")
                carregar()
                if novo_estado.get("status") == "CANCELADA":
                    self.mostrar_notificacao("Devolução cancelada", "Evento aceito pela SEFAZ.", nivel="success")
                else:
                    messagebox.showwarning("Devoluções", novo_estado.get("last_event_message") or "Evento rejeitado.", parent=janela)
            except Exception as exc:
                messagebox.showerror("Devoluções", str(exc), parent=janela)

        def recuperar_estoque_pendente():
            item = selecionado()
            if not item:
                return
            status = str(item.get("fiscal_status") or item.get("status") or "").upper()
            if status not in {"AUTORIZADA_PENDENTE_ESTOQUE", "CANCELADA_PENDENTE_ESTOQUE"}:
                messagebox.showinfo(
                    "Devoluções", "A devolução selecionada não possui efeito de estoque pendente.", parent=janela
                )
                return
            if not messagebox.askyesno(
                "Recuperar efeito local",
                "Tentar concluir agora o efeito de estoque pendente desta devolução?",
                parent=janela,
            ):
                return
            try:
                estado = NFE_DEVOLUCAO_SERVICE.recuperar_efeito_estoque_pendente(
                    int(item["id"]), actor=self._usuario_financeiro()
                )
                registrar_auditoria(
                    "Fiscal", "Recuperar estoque de devolução", str(item["id"]),
                    f"Status {estado.get('status')}", usuario=self._usuario_financeiro(),
                )
                carregar()
                self.mostrar_notificacao(
                    "Efeito de estoque concluído",
                    f"Devolução #{item['id']} atualizada para {estado.get('status')}.",
                    nivel="success",
                )
            except Exception as exc:
                messagebox.showerror("Devoluções", str(exc), parent=janela)

        def recuperar_todas_pendencias():
            if not messagebox.askyesno(
                "Recuperar pendências",
                "Tentar concluir todos os efeitos de estoque pendentes?",
                parent=janela,
            ):
                return
            resultado = NFE_DEVOLUCAO_SERVICE.recuperar_pendencias_estoque(
                actor=self._usuario_financeiro()
            )
            carregar()
            if resultado["falhas"]:
                detalhes = "\n".join(
                    f"#{item['devolucao_id']}: {item['erro']}" for item in resultado["falhas"][:10]
                )
                messagebox.showwarning(
                    "Devoluções",
                    f"Concluídas: {len(resultado['concluidas'])}\nFalhas: {len(resultado['falhas'])}\n\n{detalhes}",
                    parent=janela,
                )
            else:
                self.mostrar_notificacao(
                    "Pendências processadas",
                    f"{len(resultado['concluidas'])} devolução(ões) regularizada(s).",
                    nivel="success",
                )

        def cancelar_rascunho():
            item = selecionado()
            if not item:
                return
            status = str(item.get("fiscal_status") or item.get("status") or "").upper()
            if status in {"AUTORIZADA", "AUTORIZADA_PENDENTE_ESTOQUE", "CANCELADA", "CANCELADA_PENDENTE_ESTOQUE"}:
                messagebox.showwarning("Devoluções", "Documento fiscal autorizado deve ser cancelado pelo evento oficial.", parent=janela)
                return
            if not messagebox.askyesno("Devoluções", "Cancelar este rascunho de devolução?", parent=janela):
                return
            try:
                if not NFE_DEVOLUCAO_SERVICE.cancelar_rascunho(int(item["id"])):
                    raise ValueError("O rascunho não pode ser cancelado no estado atual.")
                registrar_auditoria("Fiscal", "Cancelar rascunho de devolução", str(item["id"]), usuario=self._usuario_financeiro())
                carregar()
            except Exception as exc:
                messagebox.showerror("Devoluções", str(exc), parent=janela)

        barra = ctk.CTkFrame(janela, fg_color="transparent")
        barra.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(barra, text="Atualizar", command=carregar, fg_color="#1f6feb").pack(side="left")
        ctk.CTkButton(barra, text="Abrir XML", command=abrir_arquivo, fg_color="#30363d").pack(side="left", padx=8)
        ctk.CTkButton(barra, text="Gerar DANFE", command=gerar_danfe, fg_color="#8957e5").pack(side="left")
        ctk.CTkButton(barra, text="Emitir oficial", command=emitir_oficial, fg_color="#2ea043").pack(side="left", padx=8)
        ctk.CTkButton(barra, text="Cancelar oficial", command=cancelar_oficial, fg_color="#b62324").pack(side="left")
        ctk.CTkButton(barra, text="Recuperar estoque", command=recuperar_estoque_pendente, fg_color="#bf8700").pack(side="left", padx=8)
        ctk.CTkButton(barra, text="Recuperar todas", command=recuperar_todas_pendencias, fg_color="#9a6700").pack(side="left")
        ctk.CTkButton(barra, text="Cancelar rascunho", command=cancelar_rascunho, fg_color="#da3633").pack(side="right")
        ctk.CTkButton(barra, text="Fechar", command=janela.destroy, fg_color="#30363d").pack(side="right", padx=8)
        tabela.bind("<Double-1>", lambda _event: abrir_arquivo())
        carregar()

    def abrir_historico_nfe_importadas(self):
        """Lista e exclui NF-e de teste com backup e reversão transacional do estoque."""
        win = ctk.CTkToplevel(self)
        win.title("NF-e importadas — excluir notas de teste")
        largura = max(980, int(win.winfo_screenwidth() * 0.88))
        altura = max(620, int(win.winfo_screenheight() * 0.82))
        win.geometry(f"{largura}x{altura}")
        win.minsize(900, 560)
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(
            win,
            text="NF-e importadas",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color="#ffffff",
        ).pack(anchor="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(
            win,
            text="Exclusão destinada a testes. O sistema cria snapshot, reverte as entradas de estoque e libera a chave para nova importação.",
            text_color="#c9d1d9",
            wraplength=largura - 60,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 12))

        filtros = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=10)
        filtros.pack(fill="x", padx=18, pady=(0, 10))
        hoje = datetime.now()
        inicio_padrao = (hoje - timedelta(days=30)).strftime("%Y-%m-%d")
        fim_padrao = hoje.strftime("%Y-%m-%d")

        ctk.CTkLabel(filtros, text="Data inicial (AAAA-MM-DD)", text_color="#ffffff").grid(row=0, column=0, padx=(12, 6), pady=(9, 2), sticky="w")
        ctk.CTkLabel(filtros, text="Data final (AAAA-MM-DD)", text_color="#ffffff").grid(row=0, column=1, padx=6, pady=(9, 2), sticky="w")
        entrada_inicio = ctk.CTkEntry(filtros, width=180)
        entrada_inicio.grid(row=1, column=0, padx=(12, 6), pady=(0, 10), sticky="w")
        entrada_inicio.insert(0, inicio_padrao)
        entrada_fim = ctk.CTkEntry(filtros, width=180)
        entrada_fim.grid(row=1, column=1, padx=6, pady=(0, 10), sticky="w")
        entrada_fim.insert(0, fim_padrao)
        lbl_total = ctk.CTkLabel(filtros, text="0 nota(s)", text_color="#8b949e")
        lbl_total.grid(row=1, column=3, padx=12, pady=(0, 10), sticky="e")
        filtros.grid_columnconfigure(2, weight=1)

        tabela_frame = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=10)
        tabela_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        colunas = ("id", "data", "numero", "fornecedor", "cnpj", "itens", "status", "chave")
        tabela = ttk.Treeview(tabela_frame, columns=colunas, show="headings", selectmode="extended")
        titulos = {
            "id": "ID", "data": "Importada em", "numero": "NF-e", "fornecedor": "Fornecedor",
            "cnpj": "CNPJ", "itens": "Itens", "status": "Status", "chave": "Chave de acesso",
        }
        larguras = {"id": 55, "data": 145, "numero": 90, "fornecedor": 240, "cnpj": 135, "itens": 60, "status": 95, "chave": 330}
        for coluna in colunas:
            tabela.heading(coluna, text=titulos[coluna])
            tabela.column(coluna, width=larguras[coluna], minwidth=50, anchor="w" if coluna not in {"id", "itens"} else "center")
        scroll_y = ttk.Scrollbar(tabela_frame, orient="vertical", command=tabela.yview)
        scroll_x = ttk.Scrollbar(tabela_frame, orient="horizontal", command=tabela.xview)
        tabela.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tabela.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0))
        scroll_y.grid(row=0, column=1, sticky="ns", pady=(8, 0), padx=(0, 8))
        scroll_x.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 8))
        tabela_frame.grid_rowconfigure(0, weight=1)
        tabela_frame.grid_columnconfigure(0, weight=1)

        detalhes = ctk.CTkTextbox(win, height=125, fg_color="#0d1117", text_color="#c9d1d9")
        detalhes.pack(fill="x", padx=18, pady=(0, 10))
        notas_cache = {}

        def validar_data(valor, nome):
            valor = str(valor or "").strip()
            if not valor:
                return ""
            try:
                datetime.strptime(valor, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"{nome} deve estar no formato AAAA-MM-DD.") from exc
            return valor

        def carregar():
            try:
                inicial = validar_data(entrada_inicio.get(), "Data inicial")
                final = validar_data(entrada_fim.get(), "Data final")
                if inicial and final and inicial > final:
                    raise ValueError("A data inicial não pode ser maior que a data final.")
                notas = NFE_IMPORT_SERVICE.listar_importacoes(inicial, final)
            except Exception as exc:
                messagebox.showerror("NF-e importadas", str(exc), parent=win)
                return
            tabela.delete(*tabela.get_children())
            notas_cache.clear()
            for nota in notas:
                nota_id = int(nota["id"])
                notas_cache[nota_id] = nota
                tabela.insert("", "end", iid=str(nota_id), values=(
                    nota_id,
                    nota.get("data_importacao") or "",
                    nota.get("numero") or "-",
                    nota.get("fornecedor_nome") or "-",
                    nota.get("fornecedor_cnpj") or "-",
                    nota.get("itens_total") or 0,
                    nota.get("status") or "-",
                    nota.get("chave") or "-",
                ))
            lbl_total.configure(text=f"{len(notas)} nota(s)")
            detalhes.delete("1.0", "end")
            detalhes.insert("end", "Selecione uma nota para visualizar o impacto da exclusão.")

        def atualizar_impacto(_event=None):
            selecionados = tabela.selection()
            detalhes.delete("1.0", "end")
            if len(selecionados) != 1:
                detalhes.insert("end", "Selecione exatamente uma nota para visualizar os produtos e saldos que serão revertidos.")
                return
            try:
                impacto = NFE_IMPORT_SERVICE.analisar_exclusao(int(selecionados[0]))
                nota = impacto["nota"]
                linhas = [
                    f"NF-e {nota.get('numero') or '-'} | {nota.get('fornecedor_nome') or '-'}",
                    f"Chave: {nota.get('chave') or '-'}",
                    f"Entradas de estoque encontradas: {len(impacto['movimentos'])}",
                ]
                for item in impacto["movimentos"]:
                    linhas.append(
                        f"• {item.get('codigo') or ''} - {item.get('nome') or ''}: "
                        f"reverter {item.get('quantidade_reverter', 0):g}; "
                        f"saldo {item.get('estoque_atual', 0):g} → {item.get('estoque_apos_reversao', 0):g}"
                    )
                if impacto["bloqueios"]:
                    linhas.append("\nBLOQUEIOS:")
                    linhas.extend(f"• {texto}" for texto in impacto["bloqueios"])
                else:
                    linhas.append("\nSituação: pronta para exclusão segura.")
                detalhes.insert("end", "\n".join(linhas))
            except Exception as exc:
                detalhes.insert("end", f"Falha ao analisar: {exc}")

        def excluir_selecionadas():
            ids = [int(item) for item in tabela.selection()]
            if not ids:
                messagebox.showwarning("Excluir NF-e", "Selecione ao menos uma nota.", parent=win)
                return
            impactos = []
            bloqueios = []
            try:
                for nota_id in ids:
                    impacto = NFE_IMPORT_SERVICE.analisar_exclusao(nota_id)
                    impactos.append(impacto)
                    bloqueios.extend(impacto["bloqueios"])
            except Exception as exc:
                messagebox.showerror("Excluir NF-e", str(exc), parent=win)
                return
            if bloqueios:
                messagebox.showerror(
                    "Exclusão bloqueada",
                    "Não é possível apagar as notas selecionadas:\n\n- " + "\n- ".join(bloqueios),
                    parent=win,
                )
                return
            senha = simpledialog.askstring(
                "Confirmação administrativa",
                "Informe a senha administrativa para excluir as notas selecionadas:",
                show="●",
                parent=win,
            )
            if senha is None:
                return
            if not self._senha_administrativa_valida(senha):
                self._registrar_acesso_admin(False, "Tentativa de exclusão de NF-e com senha incorreta.")
                messagebox.showerror("Acesso negado", "Senha administrativa incorreta.", parent=win)
                return
            numeros = ", ".join(str(item["nota"].get("numero") or item["nota"].get("id")) for item in impactos)
            movimentos = sum(len(item["movimentos"]) for item in impactos)
            if not messagebox.askyesno(
                "Confirmar exclusão",
                f"Excluir {len(ids)} NF-e(s) de teste?\n\nNotas: {numeros}\nEntradas de estoque a reverter: {movimentos}\n\nUm snapshot será criado antes da operação.",
                parent=win,
            ):
                return
            try:
                snapshot = criar_snapshot_sistema("antes_excluir_nfe_teste")
                resultados = []
                for nota_id in ids:
                    resultados.append(NFE_IMPORT_SERVICE.excluir_importacao(nota_id))
                total_revertido = sum(item["movimentos_revertidos"] for item in resultados)
                registrar_auditoria(
                    "XML",
                    "EXCLUIR_NFE_TESTE",
                    objeto=numeros,
                    detalhes=f"Notas={len(resultados)}; movimentos revertidos={total_revertido}; snapshot={snapshot.get('id')}",
                    usuario="Administrador",
                )
                self._registrar_acesso_admin(True, f"Exclusão de {len(resultados)} NF-e(s) de teste.")
                messagebox.showinfo(
                    "NF-e excluídas",
                    f"{len(resultados)} nota(s) excluída(s).\n{total_revertido} entrada(s) de estoque revertida(s).\n\nSnapshot: {snapshot.get('id')}",
                    parent=win,
                )
                carregar()
                try:
                    self.carregar_produtos()
                except Exception:
                    logger.exception("Falha ao atualizar a grade de produtos após excluir NF-e")
            except Exception as exc:
                registrar_auditoria("XML", "EXCLUIR_NFE_TESTE", objeto=numeros, detalhes=str(exc), resultado="ERRO", usuario="Administrador")
                messagebox.showerror("Excluir NF-e", f"A operação foi revertida.\n\n{exc}", parent=win)

        tabela.bind("<<TreeviewSelect>>", atualizar_impacto)
        botoes = ctk.CTkFrame(win, fg_color="#0d1117")
        botoes.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkButton(botoes, text="Atualizar lista", command=carregar, fg_color="#30363d").pack(side="left")
        ctk.CTkButton(botoes, text="Excluir selecionadas", command=excluir_selecionadas, fg_color="#da3633", hover_color="#b62324").pack(side="right")
        ctk.CTkButton(botoes, text="Fechar", command=win.destroy, fg_color="#30363d").pack(side="right", padx=8)
        ctk.CTkButton(filtros, text="Filtrar", command=carregar, width=105, fg_color="#1f6feb").grid(row=1, column=2, padx=8, pady=(0, 10), sticky="w")
        win.bind("<Escape>", lambda _event: win.destroy())
        carregar()

    def abrir_importacao_xml(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar XML de NF-e",
            filetypes=[("XML de NF-e", "*.xml"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return

        xml_service = NFeXMLService()
        try:
            documento = xml_service.ler(caminho)
            NFE_IMPORT_SERVICE.validar_nao_importada(documento)
            analises = NFE_IMPORT_SERVICE.analisar(documento)
        except Exception as exc:
            messagebox.showerror("Importar XML", str(exc))
            return
        if not analises:
            messagebox.showerror("Importar XML", "O XML não possui produtos válidos para importação.")
            return

        fornecedor_encontrado = NFE_IMPORT_SERVICE.fornecedor_existente(documento)
        unidades_ativas = self._auxiliares_ativos("unidade")
        nomes_unidades = [nome for _uid, nome in unidades_ativas] or ["UN"]

        win = ctk.CTkToplevel(self)
        win.nabi_help_context = "xml_import"
        win.title("Assistente XML — Conferência obrigatória")
        metricas_layout = UniversalLayoutPolicy.metrics(
            win.winfo_screenwidth(), win.winfo_screenheight(), preferred_width=1280, preferred_height=780
        )
        win.geometry(UniversalLayoutPolicy.geometry(metricas_layout))
        win.minsize(*UniversalLayoutPolicy.safe_minsize(metricas_layout))
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()

        cabecalho = ctk.CTkFrame(win, fg_color="#0d1117")
        cabecalho.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            cabecalho,
            text="Conferência obrigatória dos produtos da NF-e",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.cor_acento,
        ).pack(anchor="w")
        situacao_fornecedor = "cadastrado" if fornecedor_encontrado else "será cadastrado"
        ctk.CTkLabel(
            cabecalho,
            text=(f"NF-e {documento.numero or '-'} | Fornecedor: {documento.fornecedor or '-'} | "
                  f"CNPJ: {documento.cnpj or '-'} ({situacao_fornecedor})"),
            text_color="#c9d1d9",
        ).pack(anchor="w", pady=(2, 0))

        resumo_frame = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=10)
        resumo_frame.pack(fill="x", padx=14, pady=(2, 6))
        lbl_resumo = ctk.CTkLabel(resumo_frame, text="", justify="left", anchor="w")
        lbl_resumo.pack(side="left", fill="x", expand=True, padx=12, pady=8)
        lbl_progresso = ctk.CTkLabel(resumo_frame, text="0%", text_color="#58a6ff", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_progresso.pack(side="right", padx=12)

        principal = ctk.CTkFrame(win, fg_color="transparent")
        principal.pack(fill="both", expand=True, padx=14, pady=4)
        principal.grid_rowconfigure(0, weight=1)
        principal.grid_columnconfigure(0, weight=5)
        principal.grid_columnconfigure(1, weight=2)

        tabela_frame = ctk.CTkFrame(principal, fg_color="#161b22", corner_radius=10)
        tabela_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tabela_frame.grid_rowconfigure(0, weight=1)
        tabela_frame.grid_columnconfigure(0, weight=1)

        colunas = (
            "Codigo", "Descricao", "QtdXML", "Fator", "Entrada", "UnEstoque",
            "Custo", "Margem", "Venda", "Lucro", "Status",
        )
        tabela = ttk.Treeview(tabela_frame, columns=colunas, show="headings", selectmode="browse")
        definicoes = (
            ("Codigo", "Código", 95), ("Descricao", "Descrição", 250),
            ("QtdXML", "Qtd. recebida", 95), ("Fator", "Fator", 65),
            ("Entrada", "Entrada estoque", 100), ("UnEstoque", "Un.", 60),
            ("Custo", "Custo", 82), ("Margem", "Margem %", 78),
            ("Venda", "Preço venda", 88), ("Lucro", "Lucro", 78),
            ("Status", "Ação automática", 120),
        )
        for coluna, titulo, largura_coluna in definicoes:
            tabela.heading(coluna, text=titulo)
            tabela.column(coluna, width=largura_coluna, minwidth=55, anchor="w" if coluna == "Descricao" else "center")
        tabela.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0))
        scroll_y = ttk.Scrollbar(tabela_frame, orient="vertical", command=tabela.yview)
        scroll_x = ttk.Scrollbar(tabela_frame, orient="horizontal", command=tabela.xview)
        tabela.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.grid(row=0, column=1, sticky="ns", pady=(8, 0), padx=(0, 8))
        scroll_x.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 8))

        editor = ctk.CTkFrame(principal, fg_color="#161b22", corner_radius=10)
        editor.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        editor_scroll = BidirectionalScrollableFrame(editor, fg_color="#161b22", content_width=390)
        editor_scroll.pack(fill="both", expand=True, padx=6, pady=6)
        editor_body = editor_scroll.content
        editor_body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(editor_body, text="Editar item", font=ctk.CTkFont(size=16, weight="bold"), text_color="#58a6ff").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 8))
        lbl_item = ctk.CTkLabel(editor_body, text="Selecione um produto.", wraplength=350, justify="left")
        lbl_item.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        def campo_editor(titulo, linha, valor=""):
            bloco = ctk.CTkFrame(editor_body, fg_color="transparent")
            bloco.grid(row=linha, column=0, sticky="ew", padx=10, pady=4)
            ctk.CTkLabel(bloco, text=titulo, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
            var = tk.StringVar(value=valor)
            entrada = ctk.CTkEntry(bloco, textvariable=var, height=34)
            entrada.pack(fill="x")
            return var, entrada

        qtd_var, qtd_entry = campo_editor("Quantidade recebida", 2)
        fator_var, fator_entry = campo_editor("Fator (1 compra = X estoque)", 3, "1")
        custo_var, custo_entry = campo_editor("Custo por unidade de estoque", 4)
        margem_var, margem_entry = campo_editor("Margem sobre custo (%)", 5, "30")
        preco_var, preco_entry = campo_editor("Preço de venda", 6)

        bloco_unidade = ctk.CTkFrame(editor_body, fg_color="transparent")
        bloco_unidade.grid(row=7, column=0, sticky="ew", padx=10, pady=4)
        ctk.CTkLabel(bloco_unidade, text="Unidade de estoque/venda", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        unidade_var = tk.StringVar(value=nomes_unidades[0])
        unidade_combo = ctk.CTkComboBox(bloco_unidade, values=nomes_unidades, variable=unidade_var, height=34)
        unidade_combo.pack(fill="x")

        bloco_decisao = ctk.CTkFrame(editor_body, fg_color="transparent")
        bloco_decisao.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        ctk.CTkLabel(bloco_decisao, text="Decisão do item", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        acao_var = tk.StringVar(value="")
        acao_combo = ctk.CTkComboBox(bloco_decisao, values=["VINCULAR", "ATUALIZAR", "CRIAR"], variable=acao_var, height=34)
        acao_combo.pack(fill="x")

        bloco_candidato = ctk.CTkFrame(editor_body, fg_color="transparent")
        bloco_candidato.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        ctk.CTkLabel(bloco_candidato, text="Produto cadastrado / similaridade", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        candidato_var = tk.StringVar(value="")
        candidato_combo = ctk.CTkComboBox(bloco_candidato, values=["Nenhum produto"], variable=candidato_var, height=34)
        candidato_combo.pack(fill="x")

        qtd_entry.master.grid_configure(row=4)
        fator_entry.master.grid_configure(row=5)
        custo_entry.master.grid_configure(row=6)
        margem_entry.master.grid_configure(row=7)
        preco_entry.master.grid_configure(row=8)
        bloco_unidade.grid_configure(row=9)

        lbl_calculo = ctk.CTkLabel(editor_body, text="", text_color="#2ea043", font=ctk.CTkFont(size=13, weight="bold"), justify="left")
        lbl_calculo.grid(row=10, column=0, sticky="w", padx=10, pady=(8, 4))
        lbl_pendencia = ctk.CTkLabel(editor_body, text="", text_color="#f85149", wraplength=350, justify="left")
        lbl_pendencia.grid(row=11, column=0, sticky="ew", padx=10, pady=(2, 4))

        configuracoes: dict[int, dict] = {}
        analises_por_indice = {analise.index: analise for analise in analises}
        for analise in analises:
            item = analise.item
            produto = PRODUTO_SERVICE.buscar(analise.produto_id) if analise.produto_id else None
            fator_padrao = float(produto.get("fator_conversao", 1) or 1) if produto else 1.0
            if fator_padrao <= 0:
                fator_padrao = 1.0
            unidade_padrao = item.unidade if item.unidade in nomes_unidades else nomes_unidades[0]
            custo_estoque = float(item.valor_unitario) / fator_padrao
            if produto and float(produto.get("preco_venda", 0) or 0) > 0:
                resultado_preco = XMLConferenceService.por_preco(custo_estoque, produto["preco_venda"])
            else:
                resultado_preco = XMLConferenceService.por_margem(custo_estoque, 30)
            configuracoes[analise.index] = {
                "quantidade": float(item.quantidade),
                "fator": fator_padrao,
                "unidade": unidade_padrao,
                "custo": float(resultado_preco.custo),
                "margem": float(resultado_preco.margem_percentual),
                "preco": float(resultado_preco.preco_venda),
                "acao": "CRIAR" if analise.status == "NOVO" else ("ATUALIZAR" if analise.status == "VINCULAR" else ""),
                "produto_id": analise.produto_id if analise.status != "NOVO" else None,
            }

        estado = {"indice": None, "carregando": False, "sincronizando": False}

        def calcular_resumo():
            pendencias = XMLConferenceService.validar_todos(configuracoes, exigir_preco=True)
            for indice, cfg in configuracoes.items():
                try:
                    NFE_IMPORT_SERVICE.validar_decisao(cfg.get("acao", ""), cfg.get("produto_id"))
                except ValueError as exc:
                    pendencias.setdefault(indice, []).append(str(exc))
            total = len(configuracoes)
            conferidos = total - len(pendencias)
            percentual = int(round((conferidos / total) * 100)) if total else 0
            novos = sum(1 for a in analises if a.status == "NOVO")
            existentes = total - novos
            entrada = sum(float(c["quantidade"]) * float(c["fator"]) for c in configuracoes.values())
            lbl_resumo.configure(text=(
                f"Produtos: {total} | Existentes: {existentes} | Novos: {novos} | "
                f"Pendentes: {len(pendencias)} | Entrada calculada: {format_number_br(entrada)}"
            ))
            lbl_progresso.configure(text=f"{percentual}%", text_color="#2ea043" if not pendencias else "#f0b429")
            return pendencias

        def atualizar_calculo(origem=""):
            if estado["carregando"] or estado["sincronizando"]:
                return
            try:
                quantidade = parse_nonnegative_number(qtd_var.get(), "Quantidade", greater_than_zero=True)
                fator = parse_nonnegative_number(fator_var.get(), "Fator", greater_than_zero=True)
                custo = parse_nonnegative_number(custo_var.get(), "Custo")
                estado["sincronizando"] = True
                if origem == "preco":
                    resultado = XMLConferenceService.por_preco(custo, preco_var.get())
                    margem_var.set(format_number_br(resultado.margem_percentual, 2))
                else:
                    resultado = XMLConferenceService.por_margem(custo, margem_var.get())
                    preco_var.set(format_number_br(resultado.preco_venda, 2))
                entrada = quantidade * fator
                lbl_calculo.configure(
                    text=(f"Entrada: {format_number_br(entrada)} {unidade_var.get()}\n"
                          f"Lucro unitário: R$ {float(resultado.lucro_unitario):.2f} | "
                          f"Markup: {float(resultado.markup_percentual):.2f}%"),
                    text_color="#f85149" if resultado.lucro_unitario < 0 else "#2ea043",
                )
                lbl_pendencia.configure(text="Preço abaixo do custo." if resultado.lucro_unitario < 0 else "")
            except ValueError as exc:
                lbl_calculo.configure(text="Dados inválidos", text_color="#f85149")
                lbl_pendencia.configure(text=str(exc))
            finally:
                estado["sincronizando"] = False

        qtd_var.trace_add("write", lambda *_: atualizar_calculo("margem"))
        fator_var.trace_add("write", lambda *_: atualizar_calculo("margem"))
        custo_var.trace_add("write", lambda *_: atualizar_calculo("margem"))
        margem_var.trace_add("write", lambda *_: atualizar_calculo("margem"))
        preco_var.trace_add("write", lambda *_: atualizar_calculo("preco"))
        unidade_var.trace_add("write", lambda *_: atualizar_calculo("margem"))

        def salvar_item_atual(*, silencioso=False):
            indice = estado["indice"]
            if indice is None:
                return True
            try:
                quantidade = parse_nonnegative_number(qtd_var.get(), "Quantidade recebida", greater_than_zero=True)
                fator = parse_nonnegative_number(fator_var.get(), "Fator de conversão", greater_than_zero=True)
                custo = parse_nonnegative_number(custo_var.get(), "Custo unitário")
                preco = parse_nonnegative_number(preco_var.get(), "Preço de venda", greater_than_zero=True)
                resultado = XMLConferenceService.por_preco(custo, preco)
                unidade = unidade_var.get().strip().upper() or "UN"
                acao = acao_var.get().strip().upper()
                rotulo_candidato = candidato_var.get().strip()
                produto_id = None
                if acao in {"VINCULAR", "ATUALIZAR"}:
                    produto_id = candidatos_rotulo_id.get(indice, {}).get(rotulo_candidato)
                NFE_IMPORT_SERVICE.validar_decisao(acao, produto_id)
            except ValueError as exc:
                if not silencioso:
                    messagebox.showwarning("Conferência XML", str(exc), parent=win)
                return False
            configuracoes[indice].update({
                "quantidade": quantidade,
                "fator": fator,
                "unidade": unidade,
                "custo": custo,
                "margem": float(resultado.margem_percentual),
                "preco": preco,
                "acao": acao,
                "produto_id": produto_id,
            })
            atualizar_linha(indice)
            calcular_resumo()
            return True

        candidatos_rotulo_id: dict[int, dict[str, int]] = {}
        for analise in analises:
            mapa = {}
            for candidato in analise.candidatos:
                rotulo = f"{candidato.codigo} — {candidato.nome} ({candidato.similaridade:.1f}% / {candidato.criterio})"
                mapa[rotulo] = candidato.produto_id
            candidatos_rotulo_id[analise.index] = mapa

        def carregar_item(indice):
            if estado["indice"] is not None:
                salvar_item_atual(silencioso=True)
            estado["carregando"] = True
            estado["indice"] = indice
            analise = analises_por_indice[indice]
            cfg = configuracoes[indice]
            lbl_item.configure(
                text=(f"XML: {analise.item.codigo} — {analise.item.descricao.upper()}\n"
                      f"Melhor correspondência: {analise.similaridade:.1f}% ({analise.criterio})")
            )
            opcoes = list(candidatos_rotulo_id.get(indice, {})) or ["Nenhum produto"]
            candidato_combo.configure(values=opcoes)
            selecionado = next((rotulo for rotulo, pid in candidatos_rotulo_id.get(indice, {}).items() if pid == cfg.get("produto_id")), opcoes[0])
            candidato_var.set(selecionado)
            acao_var.set(cfg.get("acao") or "")
            qtd_var.set(format_number_br(cfg["quantidade"]))
            fator_var.set(format_number_br(cfg["fator"]))
            custo_var.set(format_number_br(cfg["custo"], 2))
            margem_var.set(format_number_br(cfg["margem"], 2))
            preco_var.set(format_number_br(cfg["preco"], 2))
            unidade_var.set(cfg["unidade"])
            estado["carregando"] = False
            atualizar_calculo("preco")

        def atualizar_linha(indice):
            analise = analises_por_indice[indice]
            item = analise.item
            cfg = configuracoes[indice]
            entrada = cfg["quantidade"] * cfg["fator"]
            resultado = XMLConferenceService.por_preco(cfg["custo"], cfg["preco"])
            erros = XMLConferenceService.validar_item(cfg, exigir_preco=True)
            try:
                NFE_IMPORT_SERVICE.validar_decisao(cfg.get("acao", ""), cfg.get("produto_id"))
            except ValueError as exc:
                erros.append(str(exc))
            status = "PENDENTE" if erros else cfg.get("acao", "")
            valores = (
                item.codigo, item.descricao.upper(), format_number_br(cfg["quantidade"]),
                format_number_br(cfg["fator"]), format_number_br(entrada), cfg["unidade"],
                f"R$ {cfg['custo']:.2f}", f"{float(resultado.margem_percentual):.2f}%",
                f"R$ {cfg['preco']:.2f}", f"R$ {float(resultado.lucro_unitario):.2f}", status,
            )
            if tabela.exists(str(indice)):
                tabela.item(str(indice), values=valores, tags=("pendente",) if erros else ())
            else:
                tabela.insert("", "end", iid=str(indice), values=valores, tags=("pendente",) if erros else ())
        tabela.tag_configure("pendente", background="#5a1e1e", foreground="#ffffff")

        for analise in analises:
            atualizar_linha(analise.index)

        def ao_selecionar(_event=None):
            selecao = tabela.selection()
            if selecao:
                carregar_item(int(selecao[0]))
        tabela.bind("<<TreeviewSelect>>", ao_selecionar)

        ctk.CTkButton(editor_body, text="Aplicar alterações ao item", height=38, fg_color="#1f6feb", command=salvar_item_atual).grid(row=14, column=0, sticky="ew", padx=10, pady=(8, 4))

        lote_frame = ctk.CTkFrame(editor_body, fg_color="transparent")
        lote_frame.grid(row=13, column=0, sticky="ew", padx=10, pady=(4, 12))
        margem_lote_var = tk.StringVar(value="30")
        ctk.CTkEntry(lote_frame, textvariable=margem_lote_var, width=85).pack(side="left", padx=(0, 5))
        def aplicar_margem_todos():
            try:
                margem = parse_nonnegative_number(margem_lote_var.get(), "Margem em lote")
                for indice, cfg in configuracoes.items():
                    resultado = XMLConferenceService.por_margem(cfg["custo"], margem)
                    cfg["margem"] = float(resultado.margem_percentual)
                    cfg["preco"] = float(resultado.preco_venda)
                    atualizar_linha(indice)
                if estado["indice"] is not None:
                    carregar_item(estado["indice"])
                calcular_resumo()
            except ValueError as exc:
                messagebox.showwarning("Margem em lote", str(exc), parent=win)
        ctk.CTkButton(lote_frame, text="Aplicar margem a todos", command=aplicar_margem_todos, fg_color="#8957e5").pack(side="left", fill="x", expand=True)

        def colar_valores_excel():
            try:
                texto = win.clipboard_get()
                linhas = XMLConferenceService.parse_clipboard_rows(texto)
            except tk.TclError:
                messagebox.showwarning("Colar do Excel", "A área de transferência está vazia ou indisponível.", parent=win)
                return
            except ValueError as exc:
                messagebox.showwarning("Colar do Excel", str(exc), parent=win)
                return
            indices = sorted(configuracoes)
            inicio = 0
            selecao = tabela.selection()
            if selecao:
                try:
                    inicio = indices.index(int(selecao[0]))
                except (ValueError, TypeError):
                    inicio = 0
            disponiveis = len(indices) - inicio
            if len(linhas) > disponiveis:
                messagebox.showwarning(
                    "Colar do Excel",
                    f"Foram copiadas {len(linhas)} linhas, mas existem apenas {disponiveis} itens a partir da seleção.",
                    parent=win,
                )
                return
            for deslocamento, valores in enumerate(linhas):
                indice = indices[inicio + deslocamento]
                configuracoes[indice].update(valores)
                atualizar_linha(indice)
            primeiro = indices[inicio]
            tabela.selection_set(str(primeiro))
            tabela.focus(str(primeiro))
            tabela.see(str(primeiro))
            carregar_item(primeiro)
            calcular_resumo()
            self.mostrar_notificacao(
                f"{len(linhas)} item(ns) atualizado(s) com valores copiados do Excel.",
                titulo="Conferência XML",
            )

        ctk.CTkButton(
            editor_body,
            text="Colar valores do Excel",
            height=36,
            command=colar_valores_excel,
            fg_color="#238636",
        ).grid(row=12, column=0, sticky="ew", padx=10, pady=(0, 12))

        def resolver_primeira_pendencia():
            salvar_item_atual(silencioso=True)
            pendencias = calcular_resumo()
            if not pendencias:
                messagebox.showinfo("Conferência XML", "Todos os produtos estão prontos para importação.", parent=win)
                return
            indice = sorted(pendencias)[0]
            tabela.selection_set(str(indice))
            tabela.see(str(indice))
            carregar_item(indice)
            lbl_pendencia.configure(text="; ".join(pendencias[indice]))

        def confirmar_item_e_avancar():
            if not salvar_item_atual():
                return
            filhos = list(tabela.get_children())
            if not filhos or estado["indice"] is None:
                return
            atual = str(estado["indice"])
            try:
                posicao = filhos.index(atual)
            except ValueError:
                posicao = -1
            if 0 <= posicao < len(filhos) - 1:
                proximo = filhos[posicao + 1]
                tabela.selection_set(proximo)
                tabela.focus(proximo)
                tabela.see(proximo)
                carregar_item(int(proximo))
                qtd_entry.focus_set()
                qtd_entry.select_range(0, "end")
                return
            pendencias = calcular_resumo()
            if pendencias:
                resolver_primeira_pendencia()
                return
            processar_todos()

        win._enter_navigator_xml = install_enter_navigation(
            [acao_combo, candidato_combo, qtd_entry, fator_entry, custo_entry, margem_entry, preco_entry, unidade_combo],
            on_finish=confirmar_item_e_avancar,
        )

        def processar_todos():
            if not salvar_item_atual():
                return
            pendencias = calcular_resumo()
            if pendencias:
                resolver_primeira_pendencia()
                messagebox.showwarning(
                    "Importação bloqueada",
                    f"Existem {len(pendencias)} produto(s) com dados obrigatórios pendentes.\n\nA NF-e não foi cadastrada.",
                    parent=win,
                )
                return
            if not messagebox.askyesno(
                "Concluir importação",
                f"Processar obrigatoriamente os {len(analises)} produto(s)?\n\n"
                "Produtos existentes serão atualizados; produtos novos serão cadastrados; estoque e histórico serão gravados.",
                parent=win,
            ):
                return

            itens_preparados = []
            for analise in analises:
                cfg = dict(configuracoes[analise.index])
                cfg["indice"] = analise.index
                itens_preparados.append(cfg)
            try:
                resultado_importacao = NFE_IMPORT_SERVICE.importar_atomicamente(
                    documento,
                    arquivo_origem=caminho,
                    itens=itens_preparados,
                    usuario=getattr(getattr(self, "security_session", None), "username", "Sistema") or "Sistema",
                )
                resultados = resultado_importacao["resultados"]
                criados = int(resultado_importacao["itens_criados"])
                vinculados = int(resultado_importacao["itens_vinculados"])
                lbl_progresso.configure(text="100%")
                win.update_idletasks()
            except Exception as exc:
                logger.exception("Falha na importação atômica da NF-e")
                messagebox.showerror(
                    "Importação revertida",
                    f"Nenhuma parte da NF-e foi mantida. A transação SQLite foi revertida.\n\n{exc}",
                    parent=win,
                )
                return

            relatorio = ""
            try:
                relatorio = xml_service.salvar_relatorio(documento, resultados, os.path.join(APP_DIR, "relatorios", "importacoes_xml"))
            except Exception:
                logger.exception("Falha ao gravar relatório da importação XML")
            self.carregar_produtos()
            mensagem = (
                f"NF-e importada com sucesso.\n\n{criados} produto(s) criado(s).\n"
                f"{vinculados} produto(s) atualizado(s).\n{len(analises)} entrada(s) de estoque processada(s)."
            )
            if relatorio:
                mensagem += f"\n\nRelatório:\n{relatorio}"
            self.mostrar_notificacao("XML importado", mensagem, nivel="success", parent=win, duracao_ms=7000)
            win.destroy()

        rodape = ctk.CTkFrame(win, fg_color="#0d1117")
        rodape.pack(fill="x", padx=14, pady=(4, 12))
        ctk.CTkButton(rodape, text="Resolver pendências", command=resolver_primeira_pendencia, fg_color="#9e6a03").pack(side="left")
        ctk.CTkButton(rodape, text="Concluir importação", height=42, fg_color="#2ea043", command=processar_todos).pack(side="right")
        ctk.CTkButton(rodape, text="Cancelar", height=42, fg_color="#30363d", command=win.destroy).pack(side="right", padx=8)
        self.window_actions.register(
            win,
            save=processar_todos,
            close=win.destroy,
            is_dirty=lambda: True,
            title="Importação XML",
        )
        win.bind("<Control-s>", lambda _event: self.window_actions.save(win))
        win.bind("<Escape>", lambda _event: self.window_actions.close(win))
        calcular_resumo()
        if analises:
            tabela.selection_set(str(analises[0].index))
            carregar_item(analises[0].index)

    def abrir_pdv_independente(self):
        """Abre o PDV em uma janela própria, limpa e focada na operação de venda."""
        janela_atual = getattr(self, "pdv_window", None)
        if janela_atual is not None:
            try:
                if janela_atual.winfo_exists():
                    janela_atual.deiconify()
                    janela_atual.lift()
                    janela_atual.focus_force()
                    if hasattr(self, "entry_item_venda"):
                        self.entry_item_venda.focus_set()
                    return
            except tk.TclError:
                pass

        win = ctk.CTkToplevel(self)
        # Mantém a janela oculta durante a montagem. Sem isso, o Windows exibe
        # um quadro branco antes de os widgets do PDV serem desenhados.
        prepare_hidden_toplevel(win)
        # O PDV é uma janela operacional independente. Não o marque como
        # transient: no Windows isso pode retirar o botão nativo de minimizar.
        win.nabi_help_context = "vendas"
        self.pdv_window = win
        self.pdv_fullscreen = False
        win.title(f"NabiCode {APP_VERSION} — Vendas")
        win.configure(fg_color="#0d1117")
        win.minsize(1024, 650)
        win.grid_rowconfigure(1, weight=1)
        win.grid_columnconfigure(0, weight=1)

        cabecalho = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=0, height=64)
        cabecalho.grid(row=0, column=0, sticky="ew")
        cabecalho.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            cabecalho, text="🛒 NABI VENDAS",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=self.cor_acento
        ).grid(row=0, column=0, padx=22, pady=14, sticky="w")
        modo_operacao = (obter_config("modo_operacao") or "COMERCIAL").strip().upper()
        if modo_operacao not in {"COMERCIAL", "FISCAL"}:
            modo_operacao = "COMERCIAL"
        self.modo_operacao = modo_operacao
        rotulo_operacao = "SEM FISCAL" if modo_operacao == "COMERCIAL" else "COM FISCAL"
        self.lbl_pdv_status = ctk.CTkLabel(
            cabecalho,
            text=f"Caixa ativo  •  {rotulo_operacao}  •  {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#c9d1d9"
        )
        self.lbl_pdv_status.grid(row=0, column=1, padx=18, pady=14, sticky="e")
        ctk.CTkButton(
            cabecalho, text="Minimizar", width=110, height=36,
            fg_color="#30363d", hover_color="#484f58", command=self._minimizar_pdv
        ).grid(row=0, column=2, padx=(0, 8), pady=14)
        ctk.CTkButton(
            cabecalho, text="Fechar  [Esc]", width=120, height=36,
            fg_color="#da3633", hover_color="#b62324", command=self._fechar_pdv
        ).grid(row=0, column=3, padx=(0, 18), pady=14)

        corpo = ctk.CTkFrame(win, fg_color="#0d1117", corner_radius=0)
        corpo.grid(row=1, column=0, sticky="nsew", padx=14, pady=12)
        corpo.grid_rowconfigure(2, weight=1)
        corpo.grid_columnconfigure(0, weight=4)
        corpo.grid_columnconfigure(1, weight=1, minsize=270)

        menu_pdv = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=10)
        menu_pdv.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for coluna in range(7):
            menu_pdv.grid_columnconfigure(coluna, weight=1, uniform="menu_pdv")
        comandos_menu_pdv = (
            ("Cliente [F3]", "#8957e5", lambda: self.entry_cliente_venda.focus_set()),
            ("Cliente rápido", "#6e40c9", self.abrir_cliente_rapido_pdv),
            ("Reabrir [F7]", "#1f6feb", self.abrir_vendas_suspensas),
            ("Orçamento [F5]", "#6e7681", lambda: self.salvar_documento_pdv("ORCAMENTO")),
            ("Pré-venda [F8]", "#8957e5", lambda: self.salvar_documento_pdv("PRE_VENDA")),
            ("Documentos", "#1f6feb", self.abrir_documentos_pdv),
            ("Cancelar", "#da3633", self.cancelar_venda_pdv),
        )
        for coluna, (texto, cor, comando) in enumerate(comandos_menu_pdv):
            ctk.CTkButton(
                menu_pdv, text=texto, height=34, fg_color=cor, command=comando
            ).grid(row=0, column=coluna, sticky="ew", padx=3, pady=7)

        busca = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=12)
        busca.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        busca.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(busca, text="Produto / código de barras", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=(16, 8), pady=12)
        self.entry_item_venda = ctk.CTkEntry(
            busca, placeholder_text="Digite o nome, código interno ou código de barras...",
            height=42, fg_color="#0d1117", text_color="#ffffff", placeholder_text_color="#8b949e", font=ctk.CTkFont(size=15)
        )
        self.entry_item_venda.grid(row=0, column=1, sticky="ew", padx=(6, 2), pady=12)
        self.btn_lista_produtos_venda = ctk.CTkButton(
            busca,
            text="▼",
            width=42,
            height=42,
            fg_color="#30363d",
            hover_color="#484f58",
            command=self.mostrar_lista_produtos_venda,
        )
        self.btn_lista_produtos_venda.grid(row=0, column=2, padx=(2, 6), pady=12)
        SearchEntryBehavior.attach_focus(self.entry_item_venda)
        self.entry_item_venda.bind("<KeyRelease>", self.filtrar_produtos_venda)
        self.entry_item_venda.bind("<Down>", self.navegar_sugestoes_produto)
        self.entry_item_venda.bind("<Up>", self.navegar_sugestoes_produto)
        self.entry_item_venda.bind("<Escape>", lambda event: self.fechar_sugestoes_produto())
        self.entry_item_venda.bind("<FocusOut>", self.agendar_fechamento_sugestoes_produto)

        self.entry_qtd_venda = ctk.CTkEntry(busca, placeholder_text="Qtd", width=78, height=42, fg_color="#0d1117", text_color="#ffffff", justify="center")
        self.entry_qtd_venda.grid(row=0, column=3, padx=6, pady=12)
        self.entry_qtd_venda.insert(0, "1")

        self.entry_valor_venda = ctk.CTkEntry(busca, placeholder_text="Preço", width=118, height=42, fg_color="#0d1117", text_color="#ffffff", justify="center")
        self.entry_valor_venda.grid(row=0, column=4, padx=6, pady=12)

        def validar_quantidade_pdv():
            try:
                return tratar_numero(self.entry_qtd_venda.get()) > 0
            except (TypeError, ValueError):
                return False

        def validar_preco_pdv():
            try:
                return tratar_numero(self.entry_valor_venda.get()) >= 0
            except (TypeError, ValueError):
                return False

        ctk.CTkButton(busca, text="Adicionar  [Enter]", height=42, width=150, fg_color="#1f6feb", hover_color="#1158c7", command=self.adicionar_item_carrinho).grid(row=0, column=5, padx=(6, 14), pady=12)

        self.var_item_avulso_pdv = tk.BooleanVar(value=False)
        self.check_item_avulso_pdv = ctk.CTkCheckBox(
            busca,
            text="Produto avulso — não cadastra e não movimenta estoque",
            variable=self.var_item_avulso_pdv,
            command=self.alternar_item_avulso_pdv,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.check_item_avulso_pdv.grid(row=1, column=1, columnspan=4, sticky="w", padx=6, pady=(0, 12))
        if modo_operacao == "FISCAL":
            self.check_item_avulso_pdv.configure(state="disabled")
            texto_avulso = "Modo fiscal: use somente produtos cadastrados com dados fiscais."
            cor_avulso = "#d29922"
        else:
            texto_avulso = "Marque para vender uma descrição livre sem baixar estoque."
            cor_avulso = "#8b949e"
        self.lbl_item_avulso_pdv = ctk.CTkLabel(busca, text=texto_avulso, text_color=cor_avulso)
        self.lbl_item_avulso_pdv.grid(row=1, column=4, sticky="e", padx=(6, 14), pady=(0, 12))

        self._registrar_contexto_item_venda(
            entry_item_venda=self.entry_item_venda,
            entry_qtd_venda=self.entry_qtd_venda,
            entry_valor_venda=self.entry_valor_venda,
            var_item_avulso_pdv=self.var_item_avulso_pdv,
        )

        area_itens = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=12)
        area_itens.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        area_itens.grid_rowconfigure(1, weight=1)
        area_itens.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(area_itens, text="ITENS DA VENDA", font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffffff").grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))

        tabela_frame = ctk.CTkFrame(area_itens, fg_color="transparent")
        tabela_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tabela_frame.grid_rowconfigure(0, weight=1)
        tabela_frame.grid_columnconfigure(0, weight=1)
        self.tabela_carrinho = ttk.Treeview(tabela_frame, columns=("Item", "Qtd", "Preço", "Subtotal"), show="headings", selectmode="browse")
        for coluna, titulo in (("Item", "Produto / Serviço"), ("Qtd", "Qtd."), ("Preço", "Unitário"), ("Subtotal", "Total")):
            self.tabela_carrinho.heading(coluna, text=titulo)
        self.tabela_carrinho.column("Item", width=480, minwidth=260, anchor="w")
        self.tabela_carrinho.column("Qtd", width=85, minwidth=70, anchor="center")
        self.tabela_carrinho.column("Preço", width=120, minwidth=95, anchor="e")
        self.tabela_carrinho.column("Subtotal", width=130, minwidth=105, anchor="e")
        scroll_y = ttk.Scrollbar(tabela_frame, orient="vertical", command=self.tabela_carrinho.yview)
        scroll_x = ttk.Scrollbar(tabela_frame, orient="horizontal", command=self.tabela_carrinho.xview)
        self.tabela_carrinho.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tabela_carrinho.grid(row=0, column=0, sticky="nsew")
        self.tabela_carrinho.bind(
            "<Double-Button-1>",
            self.abrir_editor_item_carrinho,
        )
        self.tabela_carrinho.bind("<Button-3>", self.abrir_menu_item_carrinho)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        resumo = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=12)
        resumo.grid(row=2, column=1, sticky="nsew")
        resumo.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(resumo, text="RESUMO DA VENDA", font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffffff").grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        ctk.CTkLabel(resumo, text="Cliente", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8b949e").grid(row=1, column=0, sticky="w", padx=16, pady=(8, 3))
        self.entry_cliente_venda = ctk.CTkEntry(resumo, placeholder_text="CONSUMIDOR / CLIENTE", height=40, fg_color="#0d1117", text_color="#ffffff", placeholder_text_color="#8b949e")
        self.entry_cliente_venda.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
        SearchEntryBehavior.attach(
            self.entry_cliente_venda, on_enter=self.confirmar_sugestao_cliente
        )
        self.entry_cliente_venda.bind("<KeyRelease>", self.filtrar_clientes_venda)
        self.entry_cliente_venda.bind("<Down>", self.navegar_sugestoes_cliente)
        self.entry_cliente_venda.bind("<Up>", self.navegar_sugestoes_cliente)
        self.entry_cliente_venda.bind("<Escape>", lambda event: self.fechar_sugestoes_cliente())
        self.entry_cliente_venda.bind("<FocusOut>", lambda event: self.after(150, self.fechar_sugestoes_cliente))

        self.cliente_venda_selecionado_id = None
        self.dict_clientes_venda = {}
        self.popup_clientes_venda = None
        self.lista_clientes_venda = None
        self.combo_cliente_venda = ctk.CTkComboBox(resumo, values=[], height=1, width=1, command=self.ao_selecionar_combo_cliente)
        self.combo_cliente_venda.set("")
        self.produto_venda_selecionado_id = None
        self.dict_produtos_venda = {}
        self.popup_produtos_venda = None
        self.lista_produtos_venda = None

        ctk.CTkFrame(resumo, height=2, fg_color="#30363d").grid(row=3, column=0, sticky="ew", padx=16, pady=12)
        self.lbl_total_carrinho = ctk.CTkLabel(resumo, text="TOTAL: R$ 0,00", font=ctk.CTkFont(size=28, weight="bold"), text_color="#00FF88")
        self.lbl_total_carrinho.grid(row=4, column=0, sticky="ew", padx=16, pady=(16, 22))
        ctk.CTkLabel(
            resumo,
            text="Duplo clique: editar item da venda  •  Clique direito: remover item",
            text_color="#8b949e",
            font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 3))
        self.combo_modo_pdv = ctk.CTkComboBox(
            resumo, values=["BALCAO", "TOUCH", "RAPIDO"], command=self.aplicar_modo_pdv
        )
        self.combo_modo_pdv.set(getattr(self, "modo_pdv", "BALCAO"))
        self.combo_modo_pdv.grid(row=6, column=0, sticky="ew", padx=16, pady=5)
        ctk.CTkButton(
            resumo,
            text="FINALIZAR VENDA  [F9]",
            height=58,
            fg_color="#2ea043",
            hover_color="#238636",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self.finalizar_venda("COMPROVANTE"),
        ).grid(row=7, column=0, sticky="ew", padx=16, pady=(5, 12))

        rodape = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=0)
        rodape.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(
            rodape,
            text=("Enter seleciona/avança • pesquisa vazia + Enter → carrinho • Enter no carrinho → finalizar   "
                  "F2 Produto   F3 Cliente   F9 Finalizar   Esc Fechar"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#c9d1d9",
        ).pack(pady=10)

        for item in self.carrinho_venda:
            nome_item = f"AVULSO • {item['item']}" if item.get("item_avulso") else item["item"]
            self.tabela_carrinho.insert("", "end", values=(nome_item, item["qtd"], f"R$ {item['preco']:.2f}", f"R$ {item['subtotal']:.2f}"))
        self.atualizar_total_carrinho()
        self.atualizar_combo_clientes_venda()

        self.window_actions.register(
            win,
            delete=self.remover_item_carrinho_selecionado,
            close=self._fechar_pdv,
            is_dirty=lambda: bool(self.carrinho_venda),
            delete_description=lambda: "o item selecionado do carrinho",
            confirm_delete=True,
            confirm_close=False,
            title="Vendas",
        )
        win.bind("<Delete>", lambda _event: self.window_actions.delete(win))
        win.bind("<Escape>", lambda _event: self.window_actions.close(win))
        win.bind("<F2>", lambda _event: self.entry_item_venda.focus_set())
        win.bind("<F3>", lambda _event: self.entry_cliente_venda.focus_set())
        win.bind("<Shift-F3>", lambda _event: self.abrir_cliente_rapido_pdv())
        win.bind("<F4>", lambda _event: self.alterar_quantidade_item_pdv())
        win.bind("<F5>", lambda _event: self.salvar_documento_pdv("ORCAMENTO"))
        win.bind("<F6>", lambda _event: self.suspender_venda_atual())
        win.bind("<F7>", lambda _event: self.abrir_vendas_suspensas())
        win.bind("<F8>", lambda _event: self.salvar_documento_pdv("PRE_VENDA"))
        win.bind("<F9>", lambda _event: self.finalizar_venda("COMPROVANTE"))
        win.bind("<F10>", lambda _event: self.aplicar_desconto_item_pdv())
        win.bind("<F11>", lambda _event: self._alternar_tela_cheia_pdv())
        self._pdv_enter_controller = PDVEnterController(
            product_entry=self.entry_item_venda,
            quantity_entry=self.entry_qtd_venda,
            price_entry=self.entry_valor_venda,
            cart=self.tabela_carrinho,
            popup_getter=lambda: getattr(self, "popup_produtos_venda", None),
            confirm_suggestion=self.confirmar_sugestao_produto,
            select_by_barcode=self._selecionar_produto_por_codigo_barras,
            add_item=self.adicionar_item_carrinho,
            finalize_sale=lambda: self.finalizar_venda("COMPROVANTE"),
            validate_quantity=validar_quantidade_pdv,
            validate_price=validar_preco_pdv,
        ).install()
        # Esc e o botão X são tratados pelo controlador universal de janelas.
        def revelar_pdv_pronto():
            try:
                reveal_prepared_toplevel_when_idle(
                    win,
                    maximize=True,
                    focus_widget=self.entry_item_venda,
                )
            except tk.TclError:
                logger.exception("Não foi possível revelar a janela de vendas.")

        revelar_pdv_pronto()


    def _enter_contexto_pdv(self, event=None):
        controller = getattr(self, "_pdv_enter_controller", None)
        if controller is None:
            return None
        return controller.dispatch_legacy_event(event)



    def abrir_cliente_rapido_pdv(self):
        def selecionar_cliente(cliente_id, nome):
            self.cliente_venda_selecionado_id = int(cliente_id)
            self.entry_cliente_venda.delete(0, "end")
            self.entry_cliente_venda.insert(0, str(nome))
            self.entry_item_venda.focus_set()

        self.abrir_cadastro_cliente(on_saved=selecionar_cliente)

    def _minimizar_pdv(self):
        """Minimiza somente o PDV e devolve acesso à janela principal."""
        win = getattr(self, "pdv_window", None)
        if win is None or not win.winfo_exists():
            return
        if bool(getattr(self, "pdv_fullscreen", False)):
            win.attributes("-fullscreen", False)
            self.pdv_fullscreen = False
        win.iconify()
        self.deiconify()
        self.lift()
        self.focus_force()

    @staticmethod
    def _nome_item_tabela_pdv(item):
        nome = str(item.get("item", ""))
        return f"AVULSO • {nome}" if item.get("item_avulso") else nome

    def _atualizar_linha_item_carrinho(self, item_id, item):
        self.tabela_carrinho.item(item_id, values=(
            self._nome_item_tabela_pdv(item),
            item.get("qtd", 0),
            f"R$ {float(item.get('preco', 0)):.2f}",
            f"R$ {float(item.get('subtotal', 0)):.2f}",
        ))

    def abrir_editor_item_carrinho(self, event=None):
        """Edita a linha da venda sem alterar o cadastro permanente do produto."""
        tabela = getattr(self, "tabela_carrinho", None)
        if tabela is None or not tabela.winfo_exists():
            return "break"
        if event is not None:
            item_apontado = tabela.identify_row(event.y)
            if item_apontado:
                tabela.selection_set(item_apontado)
                tabela.focus(item_apontado)
        selecionados = tabela.selection()
        if not selecionados:
            return "break"
        item_id = selecionados[0]
        indice = tabela.index(item_id)
        if indice < 0 or indice >= len(self.carrinho_venda):
            return "break"
        item = self.carrinho_venda[indice]
        parent = getattr(self, "pdv_window", self)

        editor = ctk.CTkToplevel(parent)
        prepare_hidden_toplevel(editor)
        editor.title("Editar item da venda")
        editor.geometry("470x390")
        editor.resizable(False, False)
        editor.transient(parent)
        editor.configure(fg_color="#0d1117")

        ctk.CTkLabel(
            editor,
            text="EDITAR ITEM DA VENDA",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.cor_acento,
        ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            editor,
            text=self._nome_item_tabela_pdv(item),
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 4))
        ctk.CTkLabel(
            editor,
            text="As alterações valem somente para esta venda e não modificam o cadastro do produto.",
            text_color="#8b949e",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 14))

        campos = ctk.CTkFrame(editor, fg_color="#161b22")
        campos.pack(fill="x", padx=22, pady=4)
        campos.grid_columnconfigure(1, weight=1)

        def criar_campo(linha, rotulo, valor):
            ctk.CTkLabel(campos, text=rotulo, anchor="w").grid(
                row=linha, column=0, sticky="w", padx=12, pady=9
            )
            entrada = ctk.CTkEntry(
                campos, fg_color="#0d1117", text_color="#ffffff", justify="right"
            )
            entrada.grid(row=linha, column=1, sticky="ew", padx=12, pady=9)
            entrada.insert(0, str(valor).replace(".", ","))
            return entrada

        entrada_qtd = criar_campo(0, "Quantidade", item.get("qtd", 1))
        entrada_preco = criar_campo(
            1, "Preço unitário base", item.get("preco_original", item.get("preco", 0))
        )
        entrada_desconto = criar_campo(
            2, "Desconto (%)", item.get("desconto_percentual", 0)
        )

        botoes = ctk.CTkFrame(editor, fg_color="transparent")
        botoes.pack(fill="x", padx=22, pady=18)

        def aplicar_edicao():
            try:
                quantidade = tratar_numero(entrada_qtd.get())
                preco = tratar_numero(entrada_preco.get())
                desconto = tratar_numero(entrada_desconto.get())
                produto_id = item.get("produto_id")
                if produto_id and not self._confirmar_estoque_pdv_para_quantidade(
                    produto_id,
                    quantidade,
                    ignorar_indice=indice,
                    override_atual=bool(item.get("estoque_override", False)),
                ):
                    self._produto_venda_override_estoque = False
                    return
                atualizado = self.pdv_service.editar_item_venda(
                    item,
                    quantidade=quantidade,
                    preco_unitario=preco,
                    desconto_percentual=desconto,
                )
                if produto_id:
                    atualizado["estoque_override"] = bool(
                        item.get("estoque_override", False)
                        or getattr(self, "_produto_venda_override_estoque", False)
                    )
            except (TypeError, ValueError) as exc:
                messagebox.showerror("Editar item da venda", str(exc), parent=editor)
                return
            finally:
                self._produto_venda_override_estoque = False

            self.carrinho_venda[indice] = atualizado
            self._atualizar_linha_item_carrinho(item_id, atualizado)
            self.atualizar_total_carrinho()
            tabela.selection_set(item_id)
            tabela.focus(item_id)
            try:
                editor.grab_release()
            except tk.TclError:
                pass
            editor.destroy()
            tabela.focus_set()

        ctk.CTkButton(
            botoes, text="Cancelar", fg_color="#30363d", command=editor.destroy
        ).pack(side="left", padx=(0, 8), expand=True, fill="x")
        ctk.CTkButton(
            botoes, text="Aplicar ao item da venda", fg_color="#1f6feb", command=aplicar_edicao
        ).pack(side="left", expand=True, fill="x")
        editor.bind("<Escape>", lambda _event: editor.destroy())
        editor.bind("<Return>", lambda _event: aplicar_edicao())
        reveal_prepared_toplevel_smooth(editor, grab=True, focus_widget=entrada_qtd)
        return "break"

    def abrir_menu_item_carrinho(self, event):
        tabela = getattr(self, "tabela_carrinho", None)
        if tabela is None or not tabela.winfo_exists():
            return "break"
        item_id = tabela.identify_row(event.y)
        if not item_id:
            return "break"
        tabela.selection_set(item_id)
        tabela.focus(item_id)
        indice = tabela.index(item_id)
        if indice < 0 or indice >= len(self.carrinho_venda):
            return "break"
        item = self.carrinho_venda[indice]

        def confirmar_remocao():
            if messagebox.askyesno(
                "Remover item da venda",
                f"Remover '{item.get('item', '')}' do carrinho?",
                parent=getattr(self, "pdv_window", self),
            ):
                self.remover_item_carrinho_selecionado()

        menu = tk.Menu(tabela, tearoff=0)
        menu.add_command(label="Editar item da venda", command=self.abrir_editor_item_carrinho)
        menu.add_separator()
        menu.add_command(label="Remover item", command=confirmar_remocao)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
        return "break"

    def aplicar_desconto_item_pdv(self):
        tabela = getattr(self, "tabela_carrinho", None)
        if tabela is None or not tabela.winfo_exists():
            return
        selecionados = tabela.selection()
        if not selecionados:
            messagebox.showwarning("Desconto", "Selecione um item do carrinho.", parent=getattr(self, "pdv_window", self))
            return
        indice = tabela.index(selecionados[0])
        if indice < 0 or indice >= len(self.carrinho_venda):
            return
        item = self.carrinho_venda[indice]
        atual = float(item.get("desconto_percentual", 0.0))
        percentual = simpledialog.askfloat(
            "Desconto do item", "Percentual de desconto (0 a 100):",
            initialvalue=atual, minvalue=0.0, maxvalue=100.0,
            parent=getattr(self, "pdv_window", self),
        )
        if percentual is None:
            return
        try:
            item_atualizado = self.pdv_service.aplicar_desconto(item, percentual)
        except ValueError as exc:
            messagebox.showerror("Desconto", str(exc), parent=getattr(self, "pdv_window", self))
            return
        self.carrinho_venda[indice] = item_atualizado
        item = item_atualizado
        self._atualizar_linha_item_carrinho(selecionados[0], item)
        self.atualizar_total_carrinho()
        self.entry_item_venda.focus_set()


    def suspender_venda_atual(self):
        if not self.carrinho_venda:
            messagebox.showwarning("Venda suspensa", "Não há itens no carrinho.", parent=getattr(self, "pdv_window", self))
            return
        try:
            venda = self.pdv_service.suspender(
                self.carrinho_venda,
                cliente_id=getattr(self, "cliente_venda_selecionado_id", None),
                cliente_nome=self.entry_cliente_venda.get().strip() if hasattr(self, "entry_cliente_venda") else "",
            )
        except ValueError as exc:
            messagebox.showerror("Venda suspensa", str(exc), parent=getattr(self, "pdv_window", self))
            return
        self.carrinho_venda.clear()
        if hasattr(self, "tabela_carrinho"):
            for row in self.tabela_carrinho.get_children():
                self.tabela_carrinho.delete(row)
        self.atualizar_total_carrinho()
        if hasattr(self, "entry_cliente_venda"):
            self.entry_cliente_venda.delete(0, "end")
        self.cliente_venda_selecionado_id = None
        self.mostrar_notificacao("Venda suspensa", f"Venda {venda.id} preservada com total de R$ {venda.total:.2f}.", nivel="success")

    def abrir_vendas_suspensas(self):
        vendas = self.pdv_service.listar_suspensas()
        if not vendas:
            messagebox.showinfo("Vendas suspensas", "Não existem vendas suspensas.", parent=getattr(self, "pdv_window", self))
            return
        opcoes = "\n".join(
            f"{indice + 1} - {venda.criada_em.replace('T', ' ')} - {venda.cliente_nome or 'Sem cliente'} - R$ {venda.total:.2f}"
            for indice, venda in enumerate(vendas)
        )
        escolha = simpledialog.askinteger(
            "Reabrir venda", f"Informe o número da venda:\n\n{opcoes}",
            minvalue=1, maxvalue=len(vendas), parent=getattr(self, "pdv_window", self),
        )
        if escolha is None:
            return
        if self.carrinho_venda and not messagebox.askyesno(
            "Substituir carrinho", "O carrinho atual será substituído pela venda suspensa. Continuar?",
            parent=getattr(self, "pdv_window", self),
        ):
            return
        venda = self.pdv_service.reabrir(vendas[escolha - 1].id)
        self.carrinho_venda = [dict(item) for item in venda.itens]
        if hasattr(self, "tabela_carrinho"):
            for row in self.tabela_carrinho.get_children():
                self.tabela_carrinho.delete(row)
            for item in self.carrinho_venda:
                self.tabela_carrinho.insert("", "end", values=(
                    item.get("item", ""), item.get("qtd", 0),
                    f"R$ {float(item.get('preco', 0)):.2f}", f"R$ {float(item.get('subtotal', 0)):.2f}",
                ))
        self.cliente_venda_selecionado_id = venda.cliente_id
        if hasattr(self, "entry_cliente_venda"):
            self.entry_cliente_venda.delete(0, "end")
            self.entry_cliente_venda.insert(0, venda.cliente_nome)
        self.atualizar_total_carrinho()

    def alterar_quantidade_item_pdv(self):
        tabela = getattr(self, "tabela_carrinho", None)
        if tabela is None or not tabela.winfo_exists():
            return
        selecionados = tabela.selection()
        if not selecionados:
            self.entry_qtd_venda.focus_set()
            self.entry_qtd_venda.select_range(0, "end")
            return
        item_id = selecionados[0]
        indice = tabela.index(item_id)
        if indice < 0 or indice >= len(self.carrinho_venda):
            return
        item = self.carrinho_venda[indice]
        quantidade = simpledialog.askfloat(
            "Quantidade do item", "Nova quantidade:",
            initialvalue=float(item.get("qtd", 1)), minvalue=0.001,
            parent=getattr(self, "pdv_window", self),
        )
        if quantidade is None:
            return
        try:
            atualizado = self.pdv_service.atualizar_quantidade(item, quantidade)
        except ValueError as exc:
            messagebox.showerror("Quantidade", str(exc), parent=getattr(self, "pdv_window", self))
            return
        self.carrinho_venda[indice] = atualizado
        self._atualizar_linha_item_carrinho(item_id, atualizado)
        self.atualizar_total_carrinho()
        tabela.selection_set(item_id)
        tabela.focus(item_id)

    def remover_item_carrinho_selecionado(self):
        tabela = getattr(self, "tabela_carrinho", None)
        if tabela is None or not tabela.winfo_exists():
            return
        selecionados = tabela.selection()
        if not selecionados:
            return
        item_id = selecionados[0]
        indice = tabela.index(item_id)
        if indice < 0 or indice >= len(self.carrinho_venda):
            return
        self.carrinho_venda.pop(indice)
        tabela.delete(item_id)
        self.atualizar_total_carrinho()
        if tabela.get_children():
            proximo = tabela.get_children()[min(indice, len(tabela.get_children()) - 1)]
            tabela.selection_set(proximo)
            tabela.focus(proximo)

    def _alternar_tela_cheia_pdv(self):
        win = getattr(self, "pdv_window", None)
        if win is None or not win.winfo_exists():
            return
        self.pdv_fullscreen = not bool(getattr(self, "pdv_fullscreen", False))
        win.attributes("-fullscreen", self.pdv_fullscreen)

    def _fechar_pdv(self):
        win = getattr(self, "pdv_window", None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                self.pdv_window = None
                return
        except tk.TclError:
            self.pdv_window = None
            return
        if self.carrinho_venda:
            fechar = messagebox.askyesno(
                "Fechar Vendas",
                "Existe uma venda em andamento. Ela será preservada para quando o PDV for aberto novamente.\n\nDeseja fechar a janela?",
                parent=win,
            )
            if not fechar:
                return
        self.fechar_sugestoes_cliente()
        self.fechar_sugestoes_produto()
        try:
            win.grab_release()
        except tk.TclError:
            pass
        win.destroy()
        self.pdv_window = None
        self.after_idle(self._garantir_janela_principal_visivel)

    def tela_vendas(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        
        self.adicionar_rodape_status(frame)
        
        scroll_vendas = BidirectionalScrollableFrame(frame, fg_color="transparent", content_width=1120)
        scroll_vendas.pack(fill="both", expand=True, padx=20, pady=5)
        conteudo_venda_frame = scroll_vendas.content
        conteudo_venda_frame.configure(fg_color="transparent")
        
        lbl = ctk.CTkLabel(conteudo_venda_frame, text="Módulo de Vendas & Carrinho", font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffffff")
        lbl.pack(anchor="w", pady=(0, 6))
        
        form_venda = ctk.CTkFrame(conteudo_venda_frame, fg_color="#161b22", corner_radius=12)
        form_venda.pack(fill="x", pady=4, ipadx=10, ipady=6)
        
        lbl_cli = ctk.CTkLabel(form_venda, text="Cliente Vinculado à Ficha:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_cli.pack(anchor="w", padx=12, pady=(4, 2))
        
        self.entry_cliente_venda = ctk.CTkEntry(form_venda, placeholder_text="Digite o nome do cliente...", height=35, fg_color="#0d1117", text_color="#ffffff", placeholder_text_color="#8b949e")
        self.entry_cliente_venda.pack(fill="x", padx=12, pady=(0, 6))
        SearchEntryBehavior.attach(
            self.entry_cliente_venda, on_enter=self.confirmar_sugestao_cliente
        )
        self.entry_cliente_venda.bind("<KeyRelease>", self.filtrar_clientes_venda)
        self.entry_cliente_venda.bind("<Down>", self.navegar_sugestoes_cliente)
        self.entry_cliente_venda.bind("<Up>", self.navegar_sugestoes_cliente)
        self.entry_cliente_venda.bind("<Escape>", lambda event: self.fechar_sugestoes_cliente())
        self.entry_cliente_venda.bind("<FocusOut>", lambda event: self.after(150, self.fechar_sugestoes_cliente))

        self.cliente_venda_selecionado_id = None
        self.dict_clientes_venda = {}
        self.popup_clientes_venda = None
        self.lista_clientes_venda = None

        # Mantido apenas por compatibilidade interna; a seleção visível agora é uma lista suspensa real.
        self.combo_cliente_venda = ctk.CTkComboBox(form_venda, values=[], height=1, width=1, command=self.ao_selecionar_combo_cliente)
        self.combo_cliente_venda.set("")
        
        frame_inputs = ctk.CTkFrame(form_venda, fg_color="transparent")
        frame_inputs.pack(fill="x", padx=12, pady=4)
        
        self.entry_item_venda = ctk.CTkEntry(frame_inputs, placeholder_text="Descrição do Produto / Serviço", height=32, fg_color="#0d1117", text_color="#ffffff")
        self.entry_item_venda.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_lista_produtos_venda = ctk.CTkButton(
            frame_inputs,
            text="▼",
            width=38,
            height=32,
            fg_color="#30363d",
            hover_color="#484f58",
            command=self.mostrar_lista_produtos_venda,
        )
        self.btn_lista_produtos_venda.pack(side="left", padx=(0, 6))
        SearchEntryBehavior.attach(
            self.entry_item_venda, on_enter=self.confirmar_sugestao_produto
        )
        self.entry_item_venda.bind("<KeyRelease>", self.filtrar_produtos_venda)
        self.entry_item_venda.bind("<Down>", self.navegar_sugestoes_produto)
        self.entry_item_venda.bind("<Up>", self.navegar_sugestoes_produto)
        self.entry_item_venda.bind("<Escape>", lambda event: self.fechar_sugestoes_produto())
        self.entry_item_venda.bind("<FocusOut>", self.agendar_fechamento_sugestoes_produto)
        self.produto_venda_selecionado_id = None
        self.dict_produtos_venda = {}
        self.popup_produtos_venda = None
        self.lista_produtos_venda = None
        
        self.entry_qtd_venda = ctk.CTkEntry(frame_inputs, placeholder_text="Qtd", width=65, height=32, fg_color="#0d1117", text_color="#ffffff")
        self.entry_qtd_venda.pack(side="left", padx=(0, 6))
        self.entry_qtd_venda.insert(0, "1")
        
        self.entry_valor_venda = ctk.CTkEntry(frame_inputs, placeholder_text="Preço Unit. (R$)", width=110, height=32, fg_color="#0d1117", text_color="#ffffff")
        self.entry_valor_venda.pack(side="left", padx=(0, 6))
        self.entry_valor_venda.bind("<Return>", lambda event: self.adicionar_item_carrinho())
        
        btn_add_item = ctk.CTkButton(frame_inputs, text="➕ Adicionar", fg_color="#1f6feb", hover_color="#1158c7", height=32, command=self.adicionar_item_carrinho)
        btn_add_item.pack(side="left")

        self.var_item_avulso_aba_vendas = tk.BooleanVar(value=False)
        self._registrar_contexto_item_venda(
            entry_item_venda=self.entry_item_venda,
            entry_qtd_venda=self.entry_qtd_venda,
            entry_valor_venda=self.entry_valor_venda,
            var_item_avulso_pdv=self.var_item_avulso_aba_vendas,
        )

        tabela_carrinho_frame = ctk.CTkFrame(conteudo_venda_frame, fg_color="#161b22", corner_radius=12)
        tabela_carrinho_frame.pack(fill="both", expand=True, pady=4)

        self.tabela_carrinho = ttk.Treeview(tabela_carrinho_frame, columns=("Item", "Qtd", "Preço", "Subtotal"), show="headings")
        self.tabela_carrinho.heading("Item", text="Item / Serviço")
        self.tabela_carrinho.heading("Qtd", text="Qtd")
        self.tabela_carrinho.heading("Preço", text="Preço Unit.")
        self.tabela_carrinho.heading("Subtotal", text="Subtotal")
        
        self.tabela_carrinho.column("Item", width=340, anchor="w")
        self.tabela_carrinho.column("Qtd", width=65, anchor="center")
        self.tabela_carrinho.column("Preço", width=110, anchor="center")
        self.tabela_carrinho.column("Subtotal", width=110, anchor="center")
        
        carrinho_scroll_y = ttk.Scrollbar(tabela_carrinho_frame, orient="vertical", command=self.tabela_carrinho.yview)
        carrinho_scroll_x = ttk.Scrollbar(tabela_carrinho_frame, orient="horizontal", command=self.tabela_carrinho.xview)
        self.tabela_carrinho.configure(yscrollcommand=carrinho_scroll_y.set, xscrollcommand=carrinho_scroll_x.set)
        carrinho_scroll_y.pack(side="right", fill="y", pady=6)
        carrinho_scroll_x.pack(side="bottom", fill="x", padx=10)
        self.tabela_carrinho.pack(fill="both", expand=True, padx=10, pady=6)

        frame_fechar = ctk.CTkFrame(conteudo_venda_frame, fg_color="#161b22", corner_radius=10)
        frame_fechar.pack(fill="x", pady=4, padx=0, ipadx=10, ipady=6)
        
        self.lbl_total_carrinho = ctk.CTkLabel(frame_fechar, text="TOTAL: R$ 0.00", font=ctk.CTkFont(size=16, weight="bold"), text_color="#00FF88")
        self.lbl_total_carrinho.pack(side="left", padx=10)
        
        btn_finalizar_venda = ctk.CTkButton(
            frame_fechar, text="FINALIZAR VENDA  [F9]", fg_color="#2ea043",
            hover_color="#238636", height=44, width=250,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self.finalizar_venda("COMPROVANTE"),
        )
        btn_finalizar_venda.pack(side="right", padx=10, pady=4)
        self.btn_finalizar_venda = btn_finalizar_venda
        parent.bind("<F9>", lambda _event: self.finalizar_venda("COMPROVANTE"), add="+")
        
        return frame

    def _confirmar_pesquisa_produtos(self):
        self.carregar_produtos()
        return SearchEntryBehavior.consume_enter()

    def _confirmar_pesquisa_clientes(self):
        self.filtrar_tabela_clientes()
        return SearchEntryBehavior.consume_enter()

    def preparar_campo_pesquisa(self, event):
        """Seleciona o valor anterior; placeholder nativo nunca é tratado como conteúdo."""
        return SearchEntryBehavior.select_existing_text(event.widget)

    def filtrar_clientes_venda(self, event=None):
        if event and event.keysym in {"Down", "Up", "Return", "Escape", "Left", "Right", "Tab", "Shift_L", "Shift_R"}:
            return

        digitado = self.entry_cliente_venda.get().strip()
        self.cliente_venda_selecionado_id = None

        if not digitado:
            self.fechar_sugestoes_cliente()
            return

        resultados = CLIENTE_REPOSITORY.search_sales_suggestions(digitado, limit=30)

        self.dict_clientes_venda = {}
        sugestoes = []
        for cliente in resultados:
            prefixo = f"Ficha {cliente.numero_ficha} | " if cliente.numero_ficha is not None else ""
            texto = f"{prefixo}{cliente.codigo} - {cliente.nome}".strip(" -")
            sugestoes.append(texto)
            self.dict_clientes_venda[texto] = cliente.id

        self.exibir_sugestoes_cliente(sugestoes)

    def exibir_sugestoes_cliente(self, sugestoes):
        self.fechar_sugestoes_cliente()
        if not sugestoes or not self.entry_cliente_venda.winfo_ismapped():
            return

        self.entry_cliente_venda.update_idletasks()
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#30363d")

        largura = max(self.entry_cliente_venda.winfo_width(), 420)
        altura = min(240, 28 * len(sugestoes) + 4)
        x = self.entry_cliente_venda.winfo_rootx()
        y = self.entry_cliente_venda.winfo_rooty() + self.entry_cliente_venda.winfo_height()
        popup.geometry(f"{largura}x{altura}+{x}+{y}")

        lista = tk.Listbox(
            popup, bg="#161b22", fg="#ffffff", selectbackground="#1f6feb",
            selectforeground="#ffffff", borderwidth=1, relief="solid",
            highlightthickness=0, font=("Arial", 11), activestyle="none"
        )
        lista.pack(fill="both", expand=True, padx=1, pady=1)
        for texto in sugestoes:
            lista.insert("end", texto)
        lista.selection_set(0)
        lista.activate(0)
        lista.bind("<ButtonRelease-1>", self.confirmar_sugestao_cliente)
        lista.bind("<Double-1>", self.confirmar_sugestao_cliente)
        lista.bind("<Return>", self.confirmar_sugestao_cliente)
        lista.bind("<Escape>", lambda event: self.fechar_sugestoes_cliente())

        self.popup_clientes_venda = popup
        self.lista_clientes_venda = lista

    def navegar_sugestoes_cliente(self, event):
        lista = getattr(self, "lista_clientes_venda", None)
        if not lista or not lista.winfo_exists() or lista.size() == 0:
            self.filtrar_clientes_venda()
            return "break"

        atual = lista.curselection()
        indice = atual[0] if atual else 0
        indice += 1 if event.keysym == "Down" else -1
        indice = max(0, min(lista.size() - 1, indice))
        lista.selection_clear(0, "end")
        lista.selection_set(indice)
        lista.activate(indice)
        lista.see(indice)
        return "break"

    def confirmar_sugestao_cliente(self, event=None):
        lista = getattr(self, "lista_clientes_venda", None)
        if not lista or not lista.winfo_exists() or lista.size() == 0:
            self.fechar_sugestoes_cliente()
            return SearchEntryBehavior.consume_enter()
        selecionado = lista.curselection()
        indice = selecionado[0] if selecionado else 0
        escolha = lista.get(indice)
        self.ao_selecionar_combo_cliente(escolha)
        self.fechar_sugestoes_cliente()
        self.entry_item_venda.focus_set()
        return "break"

    def fechar_sugestoes_cliente(self):
        popup = getattr(self, "popup_clientes_venda", None)
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass
        self.popup_clientes_venda = None
        self.lista_clientes_venda = None

    def ao_selecionar_combo_cliente(self, escolha):
        cliente_id = getattr(self, "dict_clientes_venda", {}).get(escolha)
        if not cliente_id:
            self.cliente_venda_selecionado_id = None
            return

        self.cliente_venda_selecionado_id = cliente_id
        self.entry_cliente_venda.delete(0, "end")
        self.entry_cliente_venda.insert(0, escolha)
        self.combo_cliente_venda.set(escolha)

    def atualizar_combo_clientes_venda(self):
        if not hasattr(self, "entry_cliente_venda"):
            return
        self.dict_clientes_venda = {}
        self.combo_cliente_venda.configure(values=[])
        self.combo_cliente_venda.set("")
        self.cliente_venda_selecionado_id = None
        self.fechar_sugestoes_cliente()
        self.fechar_sugestoes_produto()

    # ------------------------------------------------------------------
    # Contexto dos campos de venda
    #
    # A aba "Vendas" e a janela do PDV criam campos com os mesmos nomes de
    # atributo. Sem registro explícito, o último criado sobrescrevia o outro e
    # a lista de produtos passava a consultar um campo invisível — por isso ela
    # não abria nem ao digitar nem com a seta para baixo.
    # ------------------------------------------------------------------
    @staticmethod
    def _widget_vivo(widget):
        try:
            return widget is not None and bool(widget.winfo_exists())
        except Exception:
            return False

    @staticmethod
    def _widget_visivel(widget):
        try:
            return bool(widget.winfo_ismapped())
        except Exception:
            return False

    def _registrar_contexto_item_venda(self, **widgets):
        contextos = [
            ctx for ctx in getattr(self, "_contextos_item_venda", [])
            if self._widget_vivo(ctx.get("entry_item_venda"))
        ]
        contextos.append(widgets)
        self._contextos_item_venda = contextos
        for nome, widget in widgets.items():
            setattr(self, nome, widget)

    def _sincronizar_contexto_item_venda(self):
        contextos = [
            ctx for ctx in getattr(self, "_contextos_item_venda", [])
            if self._widget_vivo(ctx.get("entry_item_venda"))
        ]
        self._contextos_item_venda = contextos
        if not contextos:
            return getattr(self, "entry_item_venda", None)

        escolhido = None
        try:
            foco = self.focus_get()
        except Exception:
            foco = None
        if foco is not None:
            for ctx in contextos:
                alvo = ctx.get("entry_item_venda")
                widget = foco
                while widget is not None:
                    if widget is alvo or widget is getattr(alvo, "_entry", None):
                        escolhido = ctx
                        break
                    widget = getattr(widget, "master", None)
                if escolhido is not None:
                    break
        if escolhido is None:
            visiveis = [c for c in contextos if self._widget_visivel(c.get("entry_item_venda"))]
            escolhido = visiveis[-1] if visiveis else contextos[-1]

        for nome, widget in escolhido.items():
            setattr(self, nome, widget)
        return escolhido.get("entry_item_venda")

    def _produtos_ativos_para_venda(self, termo=""):
        try:
            produtos = PRODUTO_SERVICE.listar(termo, "TODOS")
            return [
                produto
                for produto in produtos
                if int(produto.get("ativo") or 0) == 1
            ][:100]
        except Exception as exc:
            logger.exception("Falha ao carregar produtos para venda", exc_info=exc)
            messagebox.showerror(
                "Produtos",
                f"Não foi possível carregar a lista de produtos:\n{exc}",
                parent=getattr(self, "pdv_window", self),
            )
            return []

    def mostrar_lista_produtos_venda(self):
        entry = self._sincronizar_contexto_item_venda()
        if entry is None:
            return
        if getattr(getattr(self, "var_item_avulso_pdv", None), "get", lambda: False)():
            return
        termo = self.entry_item_venda.get().strip()
        resultados = self._produtos_ativos_para_venda(termo)
        self._preencher_sugestoes_produto(resultados, termo=termo, permitir_avulso=True)
        self.entry_item_venda.focus_set()

    def filtrar_produtos_venda(self, event=None):
        if self._sincronizar_contexto_item_venda() is None:
            return
        if getattr(getattr(self, "var_item_avulso_pdv", None), "get", lambda: False)():
            self.produto_venda_selecionado_id = None
            self.fechar_sugestoes_produto()
            return
        if event and event.keysym in {
            "Down", "Up", "Return", "Escape", "Left", "Right",
            "Tab", "Shift_L", "Shift_R"
        }:
            return
        termo = self.entry_item_venda.get().strip()
        self.produto_venda_selecionado_id = None
        if not termo:
            self.fechar_sugestoes_produto()
            return
        resultados = self._produtos_ativos_para_venda(termo)
        self._preencher_sugestoes_produto(
            resultados,
            termo=termo,
            permitir_avulso=True,
        )

    def _preencher_sugestoes_produto(self, resultados, termo="", permitir_avulso=False):
        self.dict_produtos_venda = {}
        sugestoes = []
        for produto in resultados:
            try:
                preco = DecimalStorage.to_decimal(produto["preco_venda"], field="preço do produto")
            except (DecimalStorageError, KeyError, TypeError):
                # Um preço inválido no cadastro não pode derrubar a lista inteira.
                preco = Decimal("0")
            texto = (
                f"{produto['codigo']} - {produto['nome']} | "
                f"R$ {preco:.2f}"
            )
            sugestoes.append(texto)
            self.dict_produtos_venda[texto] = produto


        termo_limpo = str(termo or "").strip()
        if not sugestoes and permitir_avulso:
            if termo_limpo:
                texto_avulso = f"➕ USAR COMO PRODUTO AVULSO: {termo_limpo}"
                sugestoes.append(texto_avulso)
                self.dict_produtos_venda[texto_avulso] = {
                    "_avulso": True,
                    "nome": termo_limpo,
                }
            else:
                texto_aviso = "Nenhum produto ativo cadastrado — use Produto avulso"
                sugestoes.append(texto_aviso)
                self.dict_produtos_venda[texto_aviso] = {
                    "_avulso": True,
                    "nome": "",
                }

        self.exibir_sugestoes_produto(sugestoes)

    def exibir_sugestoes_produto(self, sugestoes):
        """Exibe produtos em tabela nativa com colunas e fonte do sistema."""
        self.fechar_sugestoes_produto()
        entry = getattr(self, "entry_item_venda", None)
        if not sugestoes or not self._widget_vivo(entry):
            return

        popup = None
        try:
            entry.update_idletasks()
            parent = entry.winfo_toplevel()
            popup = tk.Toplevel(parent)
            popup.withdraw()
            popup.overrideredirect(True)
            popup.configure(bg="#30363d")

            linhas_visiveis = max(1, min(10, len(sugestoes)))
            largura = max(700, min(980, entry.winfo_width() + 300))
            altura = 32 * linhas_visiveis + 34
            x = entry.winfo_rootx()
            y = entry.winfo_rooty() + entry.winfo_height()
            limite_x = parent.winfo_rootx() + max(0, parent.winfo_width() - largura - 12)
            if limite_x > parent.winfo_rootx():
                x = min(x, limite_x)
            popup.geometry(f"{largura}x{altura}+{x}+{y}")
            try:
                popup.attributes("-topmost", True)
            except tk.TclError:
                pass

            style = ttk.Style(popup)
            style.configure(
                "PDVProdutos.Treeview",
                background="#161b22",
                fieldbackground="#161b22",
                foreground="#ffffff",
                rowheight=30,
                font=("Segoe UI", 11),
                borderwidth=0,
            )
            style.configure(
                "PDVProdutos.Treeview.Heading",
                background="#21262d",
                foreground="#ffffff",
                font=("Segoe UI", 11, "bold"),
                relief="flat",
            )
            style.map(
                "PDVProdutos.Treeview",
                background=[("selected", "#8957e5")],
                foreground=[("selected", "#ffffff")],
            )

            quadro = tk.Frame(popup, bg="#30363d", bd=1, relief="solid")
            quadro.pack(fill="both", expand=True)
            colunas = ("codigo", "produto", "preco", "estoque")
            tabela = ttk.Treeview(
                quadro,
                columns=colunas,
                show="headings",
                height=linhas_visiveis,
                style="PDVProdutos.Treeview",
                selectmode="browse",
            )
            tabela.heading("codigo", text="Código")
            tabela.heading("produto", text="Produto / Serviço")
            tabela.heading("preco", text="Preço")
            tabela.heading("estoque", text="Estoque")
            tabela.column("codigo", width=105, minwidth=80, stretch=False, anchor="w")
            tabela.column("produto", width=430, minwidth=260, stretch=True, anchor="w")
            tabela.column("preco", width=120, minwidth=100, stretch=False, anchor="e")
            tabela.column("estoque", width=100, minwidth=85, stretch=False, anchor="center")
            scroll = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
            tabela.configure(yscrollcommand=scroll.set)
            tabela.pack(side="left", fill="both", expand=True)
            if len(sugestoes) > linhas_visiveis:
                scroll.pack(side="right", fill="y")

            self._produto_sugestao_por_indice = []
            for indice, texto in enumerate(sugestoes):
                produto = self.dict_produtos_venda.get(texto) or {}
                if produto.get("_avulso"):
                    valores = (
                        "+",
                        produto.get("nome") or "Produto avulso",
                        "Informar",
                        "—",
                    )
                else:
                    preco = DecimalStorage.to_decimal(
                        produto.get("preco_venda") or 0,
                        field="preço do produto",
                    )
                    estoque = produto.get("estoque_atual")
                    valores = (
                        str(produto.get("codigo") or "-"),
                        str(produto.get("nome") or texto),
                        f"R$ {preco:.2f}",
                        "—" if estoque in (None, "") else str(estoque),
                    )
                tabela.insert("", "end", iid=str(indice), values=valores)
                self._produto_sugestao_por_indice.append(produto)

            if tabela.get_children():
                primeiro = tabela.get_children()[0]
                tabela.selection_set(primeiro)
                tabela.focus(primeiro)
            tabela.bind("<ButtonPress-1>", lambda _event: self._cancelar_fechamento_sugestoes_produto())
            tabela.bind("<ButtonRelease-1>", self.confirmar_sugestao_produto)
            tabela.bind("<Double-1>", self.confirmar_sugestao_produto)
            tabela.bind("<Return>", self.confirmar_sugestao_produto)
            tabela.bind("<KP_Enter>", self.confirmar_sugestao_produto)
            tabela.bind("<Escape>", lambda _event: self.fechar_sugestoes_produto())
            popup.bind("<FocusOut>", self.agendar_fechamento_sugestoes_produto)

            popup.deiconify()
            popup.lift()
            popup.update_idletasks()
        except (tk.TclError, DecimalStorageError, ValueError) as exc:
            logger.exception("Falha ao exibir a lista de produtos", exc_info=exc)
            if popup is not None:
                try:
                    popup.destroy()
                except Exception:
                    pass
            return

        self.popup_produtos_venda = popup
        self.lista_produtos_venda = tabela

    def _cancelar_fechamento_sugestoes_produto(self):
        after_id = getattr(self, "_fechar_sugestoes_produto_after", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self._fechar_sugestoes_produto_after = None

    def agendar_fechamento_sugestoes_produto(self, _event=None):
        self._cancelar_fechamento_sugestoes_produto()
        self._fechar_sugestoes_produto_after = self.after(
            350, self._fechar_sugestoes_produto_se_fora
        )

    def _fechar_sugestoes_produto_se_fora(self):
        self._fechar_sugestoes_produto_after = None
        popup = getattr(self, "popup_produtos_venda", None)
        try:
            foco = self.focus_get()
            if popup is not None and popup.winfo_exists():
                if foco is popup or getattr(foco, "master", None) is popup:
                    return
        except tk.TclError:
            pass
        self.fechar_sugestoes_produto()

    def navegar_sugestoes_produto(self, event):
        self._sincronizar_contexto_item_venda()
        tabela = getattr(self, "lista_produtos_venda", None)
        if not tabela or not tabela.winfo_exists() or not tabela.get_children():
            self.mostrar_lista_produtos_venda()
            return "break"
        itens = list(tabela.get_children())
        atual = tabela.focus() or (tabela.selection()[0] if tabela.selection() else itens[0])
        try:
            indice = itens.index(atual)
        except ValueError:
            indice = 0
        indice += 1 if event.keysym == "Down" else -1
        indice = max(0, min(len(itens) - 1, indice))
        iid = itens[indice]
        tabela.selection_set(iid)
        tabela.focus(iid)
        tabela.see(iid)
        return "break"

    def confirmar_sugestao_produto(self, event=None):
        self._cancelar_fechamento_sugestoes_produto()
        tabela = getattr(self, "lista_produtos_venda", None)
        if not tabela or not tabela.winfo_exists() or not tabela.get_children():
            self.fechar_sugestoes_produto()
            return SearchEntryBehavior.consume_enter()

        iid = ""
        if (
            event is not None
            and getattr(event, "widget", None) is tabela
            and getattr(event, "y", None) is not None
        ):
            if tabela.identify_region(event.x, event.y) not in {"cell", "tree"}:
                return "break"
            iid = tabela.identify_row(event.y)
            if iid:
                tabela.selection_set(iid)
                tabela.focus(iid)
        iid = iid or tabela.focus() or (tabela.selection()[0] if tabela.selection() else "")
        try:
            indice = int(iid)
        except (TypeError, ValueError):
            indice = -1
        produtos = getattr(self, "_produto_sugestao_por_indice", [])
        produto = produtos[indice] if 0 <= indice < len(produtos) else None
        if not produto:
            self.fechar_sugestoes_produto()
            return SearchEntryBehavior.consume_enter()

        if produto.get("_avulso"):
            nome_avulso = str(produto.get("nome") or self.entry_item_venda.get()).strip()
            if hasattr(self, "var_item_avulso_pdv"):
                self.var_item_avulso_pdv.set(True)
            self.produto_venda_selecionado_id = None
            self.entry_item_venda.delete(0, "end")
            self.entry_item_venda.insert(0, nome_avulso)
            self.fechar_sugestoes_produto()
            self.entry_valor_venda.focus_set()
            self.entry_valor_venda.select_range(0, "end")
            return "break"

        self.produto_venda_selecionado_id = produto["id"]
        self._produto_venda_override_estoque = False
        if hasattr(self, "var_item_avulso_pdv"):
            self.var_item_avulso_pdv.set(False)
        self.entry_item_venda.delete(0, "end")
        self.entry_item_venda.insert(0, produto["nome"])
        self.entry_valor_venda.delete(0, "end")
        preco = DecimalStorage.to_decimal(
            produto.get("preco_venda") or 0, field="preço do produto"
        )
        self.entry_valor_venda.insert(0, f"{preco:.2f}".replace(".", ","))
        self.fechar_sugestoes_produto()
        if not self._confirmar_estoque_pdv_ao_selecionar(int(produto["id"])):
            return "break"
        self.entry_qtd_venda.focus_set()
        self.entry_qtd_venda.select_range(0, "end")
        return "break"

    def fechar_sugestoes_produto(self):
        self._cancelar_fechamento_sugestoes_produto()
        popup = getattr(self, "popup_produtos_venda", None)
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass
        self.popup_produtos_venda = None
        self.lista_produtos_venda = None
        self._produto_sugestao_por_indice = []


    def alternar_item_avulso_pdv(self):
        """Alterna entre produto cadastrado e item livre sem controle de estoque."""
        ativo = bool(getattr(getattr(self, "var_item_avulso_pdv", None), "get", lambda: False)())
        if ativo and (obter_config("modo_operacao") or "COMERCIAL").strip().upper() == "FISCAL":
            self.var_item_avulso_pdv.set(False)
            messagebox.showwarning(
                "Item avulso",
                "No modo fiscal, a venda exige um produto cadastrado com os dados fiscais necessários.",
                parent=getattr(self, "pdv_window", self),
            )
            return
        self.produto_venda_selecionado_id = None
        self.fechar_sugestoes_produto()
        if hasattr(self, "entry_item_venda"):
            self.entry_item_venda.configure(
                placeholder_text=(
                    "Digite a descrição do item avulso..." if ativo
                    else "Digite o nome, código interno ou código de barras..."
                )
            )
            self.entry_item_venda.focus_set()
        if hasattr(self, "lbl_item_avulso_pdv"):
            self.lbl_item_avulso_pdv.configure(
                text=(
                    "ITEM AVULSO ATIVO: não será cadastrado nem baixará estoque."
                    if ativo else "Marque para vender uma descrição livre sem baixar estoque."
                ),
                text_color="#3fb950" if ativo else "#8b949e",
            )

    def _selecionar_produto_por_codigo_barras(self, termo):
        """Seleciona produto por código interno ou código de barras exato."""
        chave = str(termo or "").strip()
        if not chave:
            return False
        for produto in self._produtos_ativos_para_venda(chave):
            codigo = str(produto.get("codigo") or "").strip()
            barras = str(produto.get("codigo_barras") or "").strip()
            if chave not in {codigo, barras}:
                continue
            self.produto_venda_selecionado_id = int(produto["id"])
            self._produto_venda_override_estoque = False
            if hasattr(self, "var_item_avulso_pdv"):
                self.var_item_avulso_pdv.set(False)
            self.entry_item_venda.delete(0, "end")
            self.entry_item_venda.insert(0, str(produto.get("nome") or chave))
            preco = DecimalStorage.to_decimal(
                produto.get("preco_venda") or 0, field="preço do produto"
            )
            self.entry_valor_venda.delete(0, "end")
            self.entry_valor_venda.insert(0, f"{preco:.2f}".replace(".", ","))
            self.fechar_sugestoes_produto()
            if not self._confirmar_estoque_pdv_ao_selecionar(int(produto["id"])):
                return False
            return True
        return False

    def _confirmar_estoque_pdv_ao_selecionar(self, produto_id):
        """Bloqueia produto zerado no momento da seleção, salvo autorização explícita."""
        try:
            produto = ESTOQUE_SERVICE.repository.buscar_produto(int(produto_id))
        except Exception as exc:
            logger.exception("Falha ao consultar estoque do produto %s", produto_id, exc_info=exc)
            messagebox.showerror(
                "Estoque",
                "Não foi possível consultar o estoque deste produto.",
                parent=getattr(self, "pdv_window", self),
            )
            return False
        if not produto or not bool(produto.get("controla_estoque", 1)) or str(produto.get("tipo_produto", "")).upper() == "SERVICO":
            return True
        saldo = float(produto.get("estoque_atual", 0) or 0)
        if bool(produto.get("permite_estoque_negativo", 0)) or saldo > 0:
            return True
        continuar = messagebox.askyesno(
            "Produto sem estoque",
            f"{produto.get('codigo', '')} - {produto.get('nome', '')} está sem estoque.\n\n"
            "Deseja vender mesmo assim? O estoque ficará negativo para esta venda.",
            parent=getattr(self, "pdv_window", self),
        )
        if continuar:
            self._produto_venda_override_estoque = True
            return True
        self.produto_venda_selecionado_id = None
        self._produto_venda_override_estoque = False
        self.entry_item_venda.delete(0, "end")
        self.entry_valor_venda.delete(0, "end")
        self.entry_item_venda.focus_set()
        return False

    def _confirmar_estoque_pdv_para_quantidade(
        self, produto_id, quantidade, *, ignorar_indice=None, override_atual=False
    ):
        """Confere a quantidade total no carrinho antes de permitir saldo negativo."""
        produto = ESTOQUE_SERVICE.repository.buscar_produto(int(produto_id))
        if not produto or not bool(produto.get("controla_estoque", 1)) or str(produto.get("tipo_produto", "")).upper() == "SERVICO":
            return True
        if bool(produto.get("permite_estoque_negativo", 0)):
            return True
        saldo = float(produto.get("estoque_atual", 0) or 0)
        quantidade_no_carrinho = sum(
            float(item.get("qtd", 0) or 0)
            for indice, item in enumerate(self.carrinho_venda)
            if indice != ignorar_indice and item.get("produto_id") == int(produto_id)
        )
        solicitado = quantidade_no_carrinho + float(quantidade)
        if solicitado <= saldo + 1e-9:
            return True
        if override_atual or bool(getattr(self, "_produto_venda_override_estoque", False)):
            return True
        continuar = messagebox.askyesno(
            "Estoque insuficiente",
            f"{produto.get('codigo', '')} - {produto.get('nome', '')}\n\n"
            f"Disponível: {saldo:g}\nSolicitado no carrinho: {solicitado:g}\n\n"
            "Deseja vender mesmo assim? O estoque ficará negativo para esta venda.",
            parent=getattr(self, "pdv_window", self),
        )
        self._produto_venda_override_estoque = bool(continuar)
        return bool(continuar)

    def adicionar_item_carrinho(self):
        item = self.entry_item_venda.get().strip()
        qtd_str = self.entry_qtd_venda.get().strip()
        valor_str = self.entry_valor_venda.get().strip()

        if not item:
            messagebox.showwarning("Aviso", "Digite a descrição do produto ou serviço!")
            return

        try:
            qtd = float(tratar_numero(qtd_str))
            if qtd <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Quantidade inválida!")
            return

        try:
            preco = tratar_numero(valor_str)
            if preco < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Preço unitário inválido!")
            return

        modo_operacao = (obter_config("modo_operacao") or "COMERCIAL").strip().upper()
        item_avulso = bool(getattr(getattr(self, "var_item_avulso_pdv", None), "get", lambda: False)())
        produto_id = getattr(self, "produto_venda_selecionado_id", None)
        if item_avulso and modo_operacao == "FISCAL":
            messagebox.showwarning(
                "Item avulso",
                "O modo fiscal não permite item avulso. Cadastre e selecione o produto.",
                parent=getattr(self, "pdv_window", self),
            )
            return
        if not item_avulso and not produto_id:
            if not self._selecionar_produto_por_codigo_barras(item):
                mensagem = (
                    "Selecione um produto cadastrado. Para uma venda sem estoque, marque 'Produto avulso'."
                    if modo_operacao != "FISCAL"
                    else "No modo fiscal, selecione um produto cadastrado com dados fiscais."
                )
                messagebox.showwarning("Produto não selecionado", mensagem, parent=getattr(self, "pdv_window", self))
                return
            produto_id = getattr(self, "produto_venda_selecionado_id", None)
            item = self.entry_item_venda.get().strip()
            valor_str = self.entry_valor_venda.get().strip()
            preco = tratar_numero(valor_str)

        if not item_avulso and produto_id and not self._confirmar_estoque_pdv_para_quantidade(produto_id, qtd):
            return

        subtotal = qtd * preco
        registro = {
            "produto_id": None if item_avulso else produto_id,
            "item": item,
            "qtd": qtd,
            "preco": preco,
            "subtotal": subtotal,
            "item_avulso": item_avulso,
            "controla_estoque": not item_avulso,
            "estoque_override": bool(getattr(self, "_produto_venda_override_estoque", False)),
        }
        self.carrinho_venda.append(registro)

        nome_tabela = f"AVULSO • {item}" if item_avulso else item
        novo_iid = self.tabela_carrinho.insert("", "end", values=(nome_tabela, qtd, f"R$ {preco:.2f}", f"R$ {subtotal:.2f}"))
        self.tabela_carrinho.see(novo_iid)

        self.entry_item_venda.delete(0, "end")
        self.produto_venda_selecionado_id = None
        self._produto_venda_override_estoque = False
        self.fechar_sugestoes_produto()
        self.entry_qtd_venda.delete(0, "end")
        self.entry_qtd_venda.insert(0, "1")
        self.entry_valor_venda.delete(0, "end")
        if hasattr(self, "var_item_avulso_pdv"):
            self.var_item_avulso_pdv.set(False)
            self.alternar_item_avulso_pdv()
        self.entry_item_venda.focus()

        self.atualizar_total_carrinho()

    def atualizar_total_carrinho(self):
        total = sum(i["subtotal"] for i in self.carrinho_venda)
        if hasattr(self, 'lbl_total_carrinho'):
            self.lbl_total_carrinho.configure(text=f"TOTAL: R$ {total:.2f}")


    def aplicar_modo_pdv(self, modo):
        try:
            self.modo_pdv = self.pdv_service.normalizar_modo(modo)
        except ValueError as exc:
            messagebox.showerror("Modo do PDV", str(exc), parent=getattr(self, "pdv_window", self))
            return
        salvar_config("pdv_modo", self.modo_pdv)
        touch = self.modo_pdv == "TOUCH"
        rapido = self.modo_pdv == "RAPIDO"
        if hasattr(self, "entry_qtd_venda"):
            self.entry_qtd_venda.configure(width=105 if touch else 78)
        if hasattr(self, "entry_item_venda"):
            self.entry_item_venda.configure(font=ctk.CTkFont(size=18 if touch else 15))
            self.entry_item_venda.focus_set()
        if rapido:
            self.entry_qtd_venda.delete(0, "end"); self.entry_qtd_venda.insert(0, "1")

    def salvar_documento_pdv(self, tipo):
        if not self.carrinho_venda:
            messagebox.showwarning("PDV", "O carrinho está vazio.", parent=getattr(self, "pdv_window", self)); return
        documento = self.pdv_service.salvar_documento(
            tipo, self.carrinho_venda,
            cliente_id=getattr(self, "cliente_venda_selecionado_id", None),
            cliente_nome=self.entry_cliente_venda.get().strip() if hasattr(self, "entry_cliente_venda") else "",
        )
        self.mostrar_notificacao(tipo.replace("_", " ").title(), f"Documento {documento.id} salvo. Total R$ {documento.total:.2f}.", nivel="success")

    def abrir_documentos_pdv(self):
        documentos = self.pdv_service.listar_documentos()
        if not documentos:
            messagebox.showinfo("Documentos do PDV", "Não existem orçamentos ou pré-vendas abertos.", parent=getattr(self, "pdv_window", self)); return
        opcoes = "\n".join(f"{i+1} - {d.tipo} - {d.cliente_nome or 'Sem cliente'} - R$ {d.total:.2f}" for i,d in enumerate(documentos))
        escolha = simpledialog.askinteger("Documentos do PDV", f"Informe o número para carregar:\n\n{opcoes}", minvalue=1, maxvalue=len(documentos), parent=getattr(self, "pdv_window", self))
        if escolha is None: return
        if self.carrinho_venda and not messagebox.askyesno("Substituir carrinho", "Substituir o carrinho atual?", parent=getattr(self, "pdv_window", self)): return
        documento = self.pdv_service.consumir_documento(documentos[escolha-1].id)
        self.carrinho_venda = [dict(item) for item in documento.itens]
        for row in self.tabela_carrinho.get_children(): self.tabela_carrinho.delete(row)
        for item in self.carrinho_venda:
            nome_item = f"AVULSO • {item.get('item', '')}" if item.get("item_avulso") else item.get("item", "")
            self.tabela_carrinho.insert("", "end", values=(nome_item, item.get("qtd", 0), f"R$ {float(item.get('preco',0)):.2f}", f"R$ {float(item.get('subtotal',0)):.2f}"))
        self.cliente_venda_selecionado_id = documento.cliente_id
        self.entry_cliente_venda.delete(0, "end"); self.entry_cliente_venda.insert(0, documento.cliente_nome)
        self.atualizar_total_carrinho()

    def solicitar_condicoes_crediario(self, total_final):
        """Assistente simples para fiado, parcelado ou entrada + parcelas."""
        parent = getattr(self, "pdv_window", self)
        win = ctk.CTkToplevel(parent)
        win.title("Condições do crediário")
        win.geometry("720x650")
        win.minsize(680, 590)
        win.configure(fg_color="#0d1117")
        self._preparar_janela_modal(win, parent)
        resultado = {"valor": None}
        modo_var = tk.StringVar(value="PARCELADO")
        entrada_var = tk.StringVar(value="0,00")
        forma_entrada_var = tk.StringVar(value="DINHEIRO")
        parcelas_var = tk.StringVar(value="2")
        primeiro_vencimento_var = tk.StringVar(value=(datetime.now()+timedelta(days=30)).strftime("%d/%m/%Y"))
        ctk.CTkLabel(win,text="COMO O CLIENTE VAI PAGAR?",font=ctk.CTkFont(size=23,weight="bold"),text_color=self.cor_acento).pack(pady=(20,5))
        ctk.CTkLabel(win,text=f"Valor da venda: R$ {float(total_final):.2f}",font=ctk.CTkFont(size=18,weight="bold")).pack(pady=(0,14))
        modos=ctk.CTkFrame(win,fg_color="#161b22",corner_radius=12); modos.pack(fill="x",padx=22,pady=6)
        ctk.CTkLabel(modos,text="Escolha uma opção",font=ctk.CTkFont(size=15,weight="bold")).pack(anchor="w",padx=16,pady=(14,7))
        for texto,valor in [("Fiado — paga tudo em uma única data","FIADO"),("Parcelado — divide todo o valor","PARCELADO"),("Entrada + parcelas — paga uma parte agora","ENTRADA")]:
            ctk.CTkRadioButton(modos,text=texto,variable=modo_var,value=valor).pack(anchor="w",padx=18,pady=6)
        detalhes=ctk.CTkFrame(win,fg_color="#161b22",corner_radius=12); detalhes.pack(fill="both",expand=True,padx=22,pady=8)
        entrada_frame=ctk.CTkFrame(detalhes,fg_color="transparent")
        ctk.CTkLabel(entrada_frame,text="Valor da entrada (pago agora)").grid(row=0,column=0,sticky="w",padx=12,pady=(10,3))
        entrada_entry=ctk.CTkEntry(entrada_frame,textvariable=entrada_var,height=38); entrada_entry.grid(row=1,column=0,sticky="ew",padx=12,pady=(0,8))
        ctk.CTkLabel(entrada_frame,text="Forma da entrada").grid(row=0,column=1,sticky="w",padx=12,pady=(10,3))
        ctk.CTkComboBox(entrada_frame,values=["DINHEIRO","PIX","DEBITO","CREDITO","OUTROS"],variable=forma_entrada_var,state="readonly",height=38).grid(row=1,column=1,sticky="ew",padx=12,pady=(0,8)); entrada_frame.grid_columnconfigure((0,1),weight=1)
        parcelas_frame=ctk.CTkFrame(detalhes,fg_color="transparent")
        ctk.CTkLabel(parcelas_frame,text="Quantidade de parcelas").grid(row=0,column=0,sticky="w",padx=12,pady=(10,3))
        ctk.CTkComboBox(parcelas_frame,values=[str(i) for i in range(1,25)],variable=parcelas_var,state="readonly",height=38).grid(row=1,column=0,sticky="ew",padx=12,pady=(0,8))
        ctk.CTkLabel(parcelas_frame,text="Primeiro vencimento").grid(row=0,column=1,sticky="w",padx=12,pady=(10,3))
        ctk.CTkEntry(parcelas_frame,textvariable=primeiro_vencimento_var,height=38).grid(row=1,column=1,sticky="ew",padx=12,pady=(0,8)); parcelas_frame.grid_columnconfigure((0,1),weight=1)
        resumo=ctk.CTkLabel(detalhes,text="",justify="left",anchor="w",font=ctk.CTkFont(size=14),text_color="#c9d1d9"); resumo.pack(fill="x",padx=14,pady=12)
        erro=ctk.CTkLabel(detalhes,text="",text_color="#ff6b6b",justify="left",wraplength=620); erro.pack(fill="x",padx=14,pady=(0,8))
        def numero(texto):
            texto=str(texto or "").strip().replace("R$","").replace(" ","")
            if not texto: return 0.0
            if "," in texto: texto=texto.replace(".","").replace(",",".")
            return round(float(texto),2)
        def atualizar(*_):
            modo=modo_var.get(); entrada_frame.pack_forget(); parcelas_frame.pack_forget()
            if modo=="FIADO": parcelas_var.set("1"); parcelas_frame.pack(fill="x")
            elif modo=="PARCELADO": parcelas_frame.pack(fill="x")
            else: entrada_frame.pack(fill="x"); parcelas_frame.pack(fill="x")
            try:
                entrada=numero(entrada_var.get()) if modo=="ENTRADA" else 0.0; financiado=round(float(total_final)-entrada,2); qtd=max(1,int(parcelas_var.get())); parcela=round(financiado/qtd,2)
                resumo.configure(text=f"Entrada agora: R$ {entrada:.2f}\nValor que ficará no crediário: R$ {financiado:.2f}\n{qtd} parcela(s) de aproximadamente R$ {parcela:.2f}\nPrimeiro vencimento: {primeiro_vencimento_var.get()}")
            except Exception: resumo.configure(text="Confira os valores informados.")
        def confirmar():
            erro.configure(text="")
            try:
                modo=modo_var.get(); entrada=numero(entrada_var.get()) if modo=="ENTRADA" else 0.0
                if entrada<0 or entrada>=float(total_final): raise ValueError("A entrada deve ser menor que o total da venda.")
                qtd=1 if modo=="FIADO" else int(parcelas_var.get())
                venc=datetime.strptime(primeiro_vencimento_var.get().strip(),"%d/%m/%Y").strftime("%Y-%m-%d")
                financiado=round(float(total_final)-entrada,2); pagamentos=[]
                if entrada>0: pagamentos.append({"forma":forma_entrada_var.get(),"valor":entrada,"entrada":True})
                pagamentos.append({"forma":"CREDIARIO","valor":financiado,"parcelas":qtd,"primeiro_vencimento":venc,"modo_crediario":modo,"entrada":entrada})
                resultado["valor"]=pagamentos; win.destroy()
            except (TypeError,ValueError) as exc: erro.configure(text=str(exc))
        for var in (modo_var,entrada_var,parcelas_var,primeiro_vencimento_var): var.trace_add("write",atualizar)
        botoes=ctk.CTkFrame(win,fg_color="transparent"); botoes.pack(fill="x",padx=22,pady=(5,18))
        ctk.CTkButton(botoes,text="Voltar",fg_color="#30363d",command=win.destroy).pack(side="left",expand=True,fill="x",padx=(0,6))
        ctk.CTkButton(botoes,text="Confirmar condições",fg_color="#2ea043",command=confirmar).pack(side="left",expand=True,fill="x",padx=(6,0))
        atualizar(); win.wait_window(); return resultado["valor"]

    def solicitar_pagamentos_pdv(self, total):
        """Finalização horizontal, recalculada em tempo real e operável por teclado."""
        parent = getattr(self, "pdv_window", self)
        janela = ctk.CTkToplevel(parent)
        janela.title("Finalizar venda")
        janela.geometry("980x500")
        janela.minsize(900, 460)
        janela.configure(fg_color="#0d1117")
        self._preparar_janela_modal(janela, parent)

        resultado = {"valor": None}
        forma_var = tk.StringVar(value="DINHEIRO")
        desconto_tipo = tk.StringVar(value="VALOR")
        acrescimo_tipo = tk.StringVar(value="VALOR")
        recebido_var = tk.StringVar(value="")
        autorizacao_cartao_var = tk.StringVar(value="")
        desconto_var = tk.StringVar(value="0,00")
        acrescimo_var = tk.StringVar(value="0,00")
        estado = {"total_final": round(float(total), 2), "recebido": 0.0, "troco": 0.0, "falta": round(float(total), 2)}
        parcelas_var = tk.StringVar(value="1")
        primeiro_vencimento_var = tk.StringVar(
            value=(datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
        )

        cab = ctk.CTkFrame(janela, fg_color="transparent")
        cab.pack(fill="x", padx=22, pady=(18, 8))
        ctk.CTkLabel(cab, text="FINALIZAR VENDA", font=ctk.CTkFont(size=24, weight="bold"), text_color=self.cor_acento).pack(side="left")
        ctk.CTkLabel(cab, text=f"Total da venda: R$ {float(total):.2f}", font=ctk.CTkFont(size=20, weight="bold")).pack(side="right")

        corpo = ctk.CTkFrame(janela, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=22, pady=8)
        corpo.grid_columnconfigure((0,1,2), weight=1, uniform="pagamento")
        corpo.grid_rowconfigure(0, weight=1)
        col_pag = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=12)
        col_ajustes = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=12)
        col_resumo = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=12)
        col_pag.grid(row=0,column=0,sticky="nsew",padx=(0,7))
        col_ajustes.grid(row=0,column=1,sticky="nsew",padx=7)
        col_resumo.grid(row=0,column=2,sticky="nsew",padx=(7,0))

        ctk.CTkLabel(col_pag,text="Forma de pagamento",font=ctk.CTkFont(size=15,weight="bold")).pack(anchor="w",padx=16,pady=(16,8))
        formas=[("Dinheiro","DINHEIRO"),("PIX","PIX"),("Débito","DEBITO"),("Crédito","CREDITO"),("Crediário","CREDIARIO"),("Outros","OUTROS")]
        radios=[]
        for texto,codigo in formas:
            r=ctk.CTkRadioButton(col_pag,text=texto,variable=forma_var,value=codigo)
            r.pack(anchor="w",padx=18,pady=5); radios.append(r)
        ctk.CTkLabel(col_pag,text="Valor recebido",font=ctk.CTkFont(size=14,weight="bold")).pack(anchor="w",padx=16,pady=(14,5))
        recebido_entry=ctk.CTkEntry(col_pag,textvariable=recebido_var,height=42,placeholder_text="0,00")
        recebido_entry.pack(fill="x",padx=16,pady=(0,16))
        cartao_frame = ctk.CTkFrame(col_pag, fg_color="#0d1117", corner_radius=8)
        ctk.CTkLabel(cartao_frame, text="Autorização da maquininha (opcional)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(8, 3))
        autorizacao_cartao_entry = ctk.CTkEntry(cartao_frame, textvariable=autorizacao_cartao_var, height=34, placeholder_text="NSU / código do comprovante")
        autorizacao_cartao_entry.pack(fill="x", padx=10, pady=(0, 8))

        def bloco(parent,titulo,tipo_var,valor_var):
            ctk.CTkLabel(parent,text=titulo,font=ctk.CTkFont(size=15,weight="bold")).pack(anchor="w",padx=16,pady=(16,7))
            combo=ctk.CTkComboBox(parent,values=["Valor","%"],state="readonly",height=38)
            combo.set("Valor"); combo.pack(fill="x",padx=16,pady=(0,7))
            entrada=ctk.CTkEntry(parent,textvariable=valor_var,height=42)
            entrada.pack(fill="x",padx=16,pady=(0,10))
            combo.configure(command=lambda v: (tipo_var.set("PERCENTUAL" if v=="%" else "VALOR"), recalcular()))
            return combo,entrada
        desconto_combo,desconto_entry=bloco(col_ajustes,"Desconto",desconto_tipo,desconto_var)
        acrescimo_combo,acrescimo_entry=bloco(col_ajustes,"Acréscimo",acrescimo_tipo,acrescimo_var)

        crediario_frame = ctk.CTkFrame(col_ajustes, fg_color="#0d1117", corner_radius=8)
        ctk.CTkLabel(
            crediario_frame,
            text="Condições do crediário",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#d2a8ff",
        ).pack(anchor="w", padx=12, pady=(10, 5))
        ctk.CTkLabel(crediario_frame, text="Quantidade de parcelas").pack(anchor="w", padx=12)
        parcelas_combo = ctk.CTkComboBox(
            crediario_frame,
            values=[str(i) for i in range(1, 25)],
            variable=parcelas_var,
            state="readonly",
            height=34,
        )
        parcelas_combo.pack(fill="x", padx=12, pady=(3, 8))
        ctk.CTkLabel(crediario_frame, text="Primeiro vencimento (DD/MM/AAAA)").pack(anchor="w", padx=12)
        primeiro_vencimento_entry = ctk.CTkEntry(
            crediario_frame,
            textvariable=primeiro_vencimento_var,
            height=34,
        )
        primeiro_vencimento_entry.pack(fill="x", padx=12, pady=(3, 10))

        total_final_label=ctk.CTkLabel(col_resumo,text="Total Final\nR$ 0,00",font=ctk.CTkFont(size=24,weight="bold"),justify="left")
        total_final_label.pack(anchor="w",padx=18,pady=(24,12))
        saldo_label=ctk.CTkLabel(col_resumo,text="Troco\nR$ 0,00",font=ctk.CTkFont(size=20,weight="bold"),justify="left")
        saldo_label.pack(anchor="w",padx=18,pady=12)
        erro_label=ctk.CTkLabel(col_resumo,text="",text_color="#ff6b6b",wraplength=260,justify="left",font=ctk.CTkFont(size=12,weight="bold"))
        erro_label.pack(anchor="w",padx=18,pady=8)

        def numero(texto):
            texto=str(texto or "").strip().replace("R$","").replace(" ","")
            if not texto:return 0.0
            if "," in texto:texto=texto.replace(".","").replace(",",".")
            return max(0.0,float(texto))
        def recalcular(*_):
            try:
                calculo=self.pdv_service.calcular_finalizacao(float(total),desconto=numero(desconto_var.get()),desconto_tipo=desconto_tipo.get(),acrescimo=numero(acrescimo_var.get()),acrescimo_tipo=acrescimo_tipo.get(),recebido=numero(recebido_var.get()),forma=forma_var.get())
                estado.update(calculo)
                total_final_label.configure(text=f"Total Final\nR$ {calculo['total_final']:.2f}")
                if calculo['falta']>0.009: saldo_label.configure(text=f"Falta receber\nR$ {calculo['falta']:.2f}",text_color="#ff6b6b")
                else: saldo_label.configure(text=f"Troco\nR$ {calculo['troco']:.2f}",text_color="#3fb950")
                erro_label.configure(text="")
            except (ValueError,TypeError) as exc: erro_label.configure(text=str(exc))
        def forma_alterada(*_):
            crediario_frame.pack_forget()
            cartao_frame.pack_forget()
            if forma_var.get()=="CREDIARIO": recebido_var.set(f"{estado['total_final']:.2f}".replace(".",","))
            if forma_var.get() in {"DEBITO", "CREDITO"}:
                cartao_frame.pack(fill="x", padx=12, pady=(0, 10))
            recalcular()
        forma_var.trace_add("write",forma_alterada); recebido_var.trace_add("write",recalcular); desconto_var.trace_add("write",recalcular); acrescimo_var.trace_add("write",recalcular)
        def cancelar(_event=None): resultado["valor"]=None; janela.destroy(); return "break"
        def concluir(_event=None):
            recalcular()
            if estado['falta']>0.009:
                erro_label.configure(text=f"Faltam R$ {estado['falta']:.2f} para concluir a venda.")
                recebido_entry.focus_set(); janela.lift(); return "break"
            if forma_var.get()=="CREDIARIO":
                pagamentos=self.solicitar_condicoes_crediario(estado["total_final"])
                if not pagamentos: janela.lift(); return "break"
            else:
                pagamentos=[{"forma":forma_var.get(),"valor":estado["recebido"]}]
                if forma_var.get() in {"DEBITO", "CREDITO"}:
                    pagamentos[0].update({
                        "card_integration": 2,
                        "card_authorization": autorizacao_cartao_var.get().strip()[:20],
                    })
            try:
                recebido,troco=self.pdv_service.validar_pagamentos(estado['total_final'],pagamentos)
                itens=self.pdv_service.ratear_total_itens(self.carrinho_venda,estado['total_final'])
            except ValueError as exc:
                erro_label.configure(text=str(exc)); janela.lift(); return "break"
            resultado["valor"]=(pagamentos,recebido,troco,itens)
            janela.destroy(); return "break"
        btns=ctk.CTkFrame(col_resumo,fg_color="transparent")
        btns.pack(side="bottom",fill="x",padx=16,pady=16)
        ctk.CTkButton(btns,text="Cancelar",fg_color="#30363d",command=cancelar).pack(fill="x",pady=(0,7))
        finalizar_btn=ctk.CTkButton(btns,text="Finalizar venda",height=46,fg_color="#2ea043",command=concluir)
        finalizar_btn.pack(fill="x")
        fluxo=radios+[recebido_entry,autorizacao_cartao_entry,desconto_combo,desconto_entry,acrescimo_combo,acrescimo_entry,parcelas_combo,primeiro_vencimento_entry,finalizar_btn]
        def avancar(event=None):
            atual=janela.focus_get()
            if atual in fluxo:
                i=fluxo.index(atual)
                if i<len(fluxo)-1: fluxo[i+1].focus_set(); return "break"
            return concluir(event)
        def voltar(event=None):
            atual=janela.focus_get()
            if atual in fluxo and fluxo.index(atual)>0: fluxo[fluxo.index(atual)-1].focus_set()
            return "break"
        janela.bind("<Escape>",cancelar); janela.bind("<Return>",avancar); janela.bind("<Shift-Return>",voltar); janela.protocol("WM_DELETE_WINDOW",cancelar)
        janela.after(100,radios[0].focus_set); recalcular(); janela.wait_window(); return resultado['valor']

    def janela_pos_venda_comprovante(self, caminho_pdf, cliente_id, itens, total, tipo, documento_id=None):
        """Abre o PDF no visualizador do sistema sem criar janela intermediária.

        As janelas CTk/Tk usadas nas versões 2.4.73 e 2.4.74 podiam aparecer
        completamente brancas em alguns Windows. O visualizador padrão do sistema
        já é o destino correto do comprovante, portanto o modal foi removido.
        """
        parent = getattr(self, "pdv_window", self)
        caminho_pdf = os.path.abspath(os.fspath(caminho_pdf))
        if not os.path.isfile(caminho_pdf) or os.path.getsize(caminho_pdf) <= 0:
            raise FileNotFoundError(f"O comprovante não foi gerado corretamente: {caminho_pdf}")
        try:
            self._abrir_arquivo_sistema(caminho_pdf)
        except Exception as exc:
            logger.exception("Falha ao abrir o comprovante no visualizador do sistema", exc_info=exc)
            messagebox.showinfo(
                "Comprovante gerado",
                f"A venda foi concluída e o PDF foi salvo em:\n\n{caminho_pdf}",
                parent=parent,
            )
        return caminho_pdf

    def cancelar_venda_pdv(self):
        rows = self.pdv_transaction_service.list_cancellable_sales(limit=20)
        if not rows:
            messagebox.showinfo("Cancelar venda", "Nenhuma venda disponível.", parent=getattr(self, "pdv_window", self))
            return
        opcoes = "\n".join(
            f"{indice + 1} - #{venda['id']} - {venda['data']} - R$ {venda['valor']:.2f}"
            for indice, venda in enumerate(rows)
        )
        escolha = simpledialog.askinteger(
            "Cancelar venda", f"Informe a venda:\n\n{opcoes}", minvalue=1, maxvalue=len(rows),
            parent=getattr(self, "pdv_window", self),
        )
        if escolha is None:
            return
        venda = rows[escolha - 1]
        if not messagebox.askyesno(
            "Confirmar cancelamento",
            f"Cancelar a venda #{venda['id']} e reverter estoque e financeiro?",
            parent=getattr(self, "pdv_window", self),
        ):
            return
        actor = getattr(getattr(self, "security", None), "current_username", "Sistema")
        try:
            self.pdv_transaction_service.cancel_sale(
                venda["id"],
                user=actor,
                before_cancel_commit=self.fiscal_sale_service.prepare_local_cancellation,
            )
            self.fiscal_sale_service.finalize_local_cancellation(
                sale_id=int(venda["id"]), actor=actor
            )
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("Cancelar venda", str(exc), parent=getattr(self, "pdv_window", self))
            return
        self.mostrar_notificacao(
            "Venda cancelada",
            f"Venda #{venda['id']} cancelada e estoque revertido.",
            nivel="success",
        )

    def finalizar_venda(self, tipo_comprovante):
        if not self.carrinho_venda:
            messagebox.showwarning("Aviso", "O carrinho de compras está vazio!")
            return

        cli_selecionado = self.entry_cliente_venda.get().strip()
        cliente_id = getattr(self, "cliente_venda_selecionado_id", None)
        if not cliente_id:
            escolha_combo = self.combo_cliente_venda.get().strip() if hasattr(self, "combo_cliente_venda") else ""
            cliente_id = getattr(self, "dict_clientes_venda", {}).get(escolha_combo)
        if not cliente_id and cli_selecionado:
            codigo_ou_nome = cli_selecionado.split(" - ")[0] if " - " in cli_selecionado else cli_selecionado
            conn = conectar_banco()
            try:
                res = conn.execute(
                    "SELECT id FROM clientes WHERE codigo = ? OR nome = ?",
                    (codigo_ou_nome, cli_selecionado),
                ).fetchone()
            finally:
                conn.close()
            if res:
                cliente_id = res[0]
        if not cliente_id:
            cliente_id = self._cliente_consumidor_final()
            cli_selecionado = "CONSUMIDOR FINAL"

        total_venda = self.pdv_service.totalizar(self.carrinho_venda)
        pagamento = self.solicitar_pagamentos_pdv(total_venda)
        if pagamento is None:
            return
        pagamentos, recebido, troco, itens_finalizados = pagamento
        usuario_venda = getattr(getattr(self, "security", None), "current_username", "Sistema")
        rascunho_fiscal = None
        if self.fiscal_service.is_enabled():
            try:
                config_fiscal = self.fiscal_service.load_config()
                destinatario_fiscal, destino_fiscal = self.fiscal_sale_service.recipient_for_customer(
                    int(cliente_id), model=str(config_fiscal.get("default_model") or "65")
                )
                rascunho_fiscal = self.fiscal_sale_service.prepare(
                    items=[dict(item) for item in itens_finalizados],
                    payments=pagamentos,
                    actor=usuario_venda,
                    recipient=destinatario_fiscal,
                    destination=destino_fiscal,
                )
            except (ValueError, RuntimeError) as exc:
                messagebox.showerror(
                    "Venda fiscal não concluída",
                    "A venda não foi gravada porque o documento fiscal precisa ser corrigido:\n\n" + str(exc),
                    parent=getattr(self, "pdv_window", self),
                )
                return
        try:
            resultado = self.pdv_transaction_service.finalize_sale(
                customer_id=int(cliente_id),
                customer_name=cli_selecionado,
                items=[dict(item) for item in itens_finalizados],
                payments=pagamentos,
                received=recebido,
                change=troco,
                user=usuario_venda,
                after_sale_in_transaction=(
                    (lambda connection, sale_id: self.fiscal_sale_service.persist_draft(
                        connection, sale_id, rascunho_fiscal
                    )) if rascunho_fiscal is not None else None
                ),
            )
        except (ValueError, RuntimeError) as exc:
            if rascunho_fiscal is not None:
                try:
                    self.fiscal_service.release_number(
                        rascunho_fiscal.reservation_id, actor=usuario_venda,
                        reason="A transação comercial da venda foi revertida.",
                    )
                except Exception:
                    logger.exception("Falha ao liberar numeração fiscal de venda revertida")
            messagebox.showerror("Venda", str(exc), parent=getattr(self, "pdv_window", self))
            return

        aviso_fiscal = ""
        if rascunho_fiscal is not None:
            try:
                self.fiscal_sale_service.enqueue_pending(
                    sale_id=resultado.sale_id, actor=usuario_venda
                )
                aviso_fiscal = " Documento fiscal colocado na fila segura de transmissão."
            except Exception as exc:
                logger.exception("Venda salva com documento fiscal pendente", exc_info=exc)
                aviso_fiscal = (
                    " Documento fiscal preservado como pendente e será reenviado pela Central Fiscal."
                )

        registrar_historico(
            int(cliente_id),
            "COMPRA",
            f"Compra de R$ {resultado.total:.2f}: " + " | ".join(
                f"{item['qtd']}x {item['item']} (R$ {item['subtotal']:.2f})" for item in itens_finalizados
            ),
        )
        itens_impressao = [dict(item) for item in itens_finalizados]
        aviso_impressao = ""
        try:
            resultado_emissao = self.janela_venda_finalizada(
                int(cliente_id), itens_impressao, resultado.total, tipo_comprovante, resultado.sale_id
            )
            if resultado_emissao:
                aviso_impressao = f" {resultado_emissao}."
        except Exception as exc:
            logger.exception("Venda salva, mas a escolha do comprovante falhou", exc_info=exc)
            messagebox.showerror(
                "Comprovante",
                "A venda foi salva, mas não foi possível concluir a escolha do comprovante:\n" + str(exc),
                parent=getattr(self, "pdv_window", self),
            )

        self.mostrar_notificacao(
            "Venda concluída",
            f"Venda de R$ {resultado.total:.2f} registrada com sucesso. "
            f"Pagamento: {resultado.payment_description}. Troco: R$ {resultado.change:.2f}."
            f"{aviso_fiscal}{aviso_impressao}",
            nivel="success", duracao_ms=7000,
        )
        self.carrinho_venda.clear()
        for row in self.tabela_carrinho.get_children():
            self.tabela_carrinho.delete(row)
        self.atualizar_total_carrinho()
        self.entry_cliente_venda.delete(0, "end")
        self.combo_cliente_venda.set("")
        self.cliente_venda_selecionado_id = None
        pdv = getattr(self, "pdv_window", None)
        try:
            pdv_aberto = pdv is not None and pdv.winfo_exists()
        except tk.TclError:
            pdv_aberto = False
        if pdv_aberto:
            self.entry_item_venda.focus_set()
        else:
            self.mostrar_tela("dashboard")

    def tela_clientes(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        
        LayoutManager.configure_vertical_shell(frame, expandable_row=1)

        conteudo_cli = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=12)
        # O conteúdo principal e o rodapé compartilham ``pack``; o grid fica
        # restrito aos widgets internos deste container.
        conteudo_cli.pack(fill="both", expand=True, padx=20, pady=5)
        LayoutManager.configure_vertical_shell(conteudo_cli, expandable_row=2)
        self.background_manager.attach(conteudo_cli)
        
        frame_topo_cli = ctk.CTkFrame(conteudo_cli, fg_color="transparent")
        frame_topo_cli.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        lbl = ctk.CTkLabel(frame_topo_cli, text="👥 Gerenciamento de Clientes & Fichas", font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffffff")
        lbl.pack(side="left")

        # CAMPO DE BUSCA DINÂMICA DE CLIENTE (AO DIGITAR JÁ BUSCA)
        frame_busca_cli = ctk.CTkFrame(conteudo_cli, fg_color="transparent")
        frame_busca_cli.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 5))

        self.var_somente_favoritos = ctk.BooleanVar(value=False)
        chk_favoritos = ctk.CTkCheckBox(frame_busca_cli, text="Somente favoritos", variable=self.var_somente_favoritos, command=self.filtrar_tabela_clientes, text_color="#ffffff")
        chk_favoritos.pack(side="right", padx=(12, 0))

        self.entry_busca_cliente = ctk.CTkEntry(frame_busca_cli, placeholder_text="🔍 Buscar por ficha, código, nome, CPF, RG, telefone ou endereço...", height=35, fg_color="#0d1117", text_color="#ffffff", placeholder_text_color="#8b949e")
        self.entry_busca_cliente.pack(side="left", fill="x", expand=True)
        SearchEntryBehavior.attach(
            self.entry_busca_cliente, on_enter=self.filtrar_tabela_clientes
        )
        self.entry_busca_cliente.bind("<KeyRelease>", self.filtrar_tabela_clientes)

        # Paginação evita congelamento ao carregar milhares de clientes de uma vez.
        self.clientes_por_pagina = 250
        self.pagina_clientes = 0
        self._filtro_clientes_after = None
        self.lbl_pagina_clientes = ctk.CTkLabel(frame_busca_cli, text="", width=165, text_color="#c9d1d9")
        self.lbl_pagina_clientes.pack(side="right", padx=(8, 0))
        self.btn_proxima_pagina_clientes = ctk.CTkButton(frame_busca_cli, text="▶", width=38, height=32, command=lambda: self.mudar_pagina_clientes(1))
        self.btn_proxima_pagina_clientes.pack(side="right", padx=(4, 0))
        self.btn_anterior_pagina_clientes = ctk.CTkButton(frame_busca_cli, text="◀", width=38, height=32, command=lambda: self.mudar_pagina_clientes(-1))
        self.btn_anterior_pagina_clientes.pack(side="right", padx=(8, 0))

        tabela_cli_frame = ctk.CTkFrame(conteudo_cli, fg_color="transparent")
        tabela_cli_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=5)
        LayoutManager.configure_root(tabela_cli_frame)

        # A tela de clientes prioriza a leitura operacional: FICHA → NOME → SALDO.
        estilo_clientes = ttk.Style()
        estilo_clientes.configure(
            "Clientes.Treeview",
            background="#161b22",
            foreground="#ffffff",
            fieldbackground="#161b22",
            rowheight=32,
            font=("Arial", 12)
        )
        estilo_clientes.configure(
            "Clientes.Treeview.Heading",
            background="#21262d",
            foreground="#ffffff",
            font=("Arial", 11, "bold")
        )
        estilo_clientes.map("Clientes.Treeview", background=[("selected", self.cor_acento_hover)])

        self.tabela_cli = ttk.Treeview(
            tabela_cli_frame,
            columns=("Ficha", "Nome", "Saldo", "Limite", "Telefone", "CPF", "Fav"),
            show="headings",
            style="Clientes.Treeview"
        )
        self.tabela_cli.heading("Ficha", text="FICHA")
        self.tabela_cli.heading("Nome", text="NOME DO CLIENTE")
        self.tabela_cli.heading("Saldo", text="SALDO DEVEDOR")
        self.tabela_cli.heading("Limite", text="LIMITE")
        self.tabela_cli.heading("Telefone", text="TELEFONE")
        self.tabela_cli.heading("CPF", text="CPF")
        self.tabela_cli.heading("Fav", text="★")

        self.tabela_cli.column("Ficha", width=105, minwidth=90, anchor="center", stretch=False)
        self.tabela_cli.column("Nome", width=290, minwidth=210, anchor="w")
        self.tabela_cli.column("Saldo", width=150, minwidth=135, anchor="e", stretch=False)
        self.tabela_cli.column("Limite", width=120, minwidth=105, anchor="e", stretch=False)
        self.tabela_cli.column("Telefone", width=135, minwidth=115, anchor="center")
        self.tabela_cli.column("CPF", width=135, minwidth=120, anchor="center")
        self.tabela_cli.column("Fav", width=46, anchor="center", stretch=False)

        acoes_clientes = ctk.CTkFrame(conteudo_cli, fg_color="transparent")
        acoes_clientes.grid(row=3, column=0, sticky="ew", padx=15, pady=(6, 6))
        for texto, cor, comando in (
            ("➕ Novo Cliente", "#2ea043", self.abrir_cadastro_cliente),
            ("✏️ Editar", "#8957e5", self.editar_cliente_selecionado),
            ("⭐ Favoritar", "#9e6a03", self.alternar_favorito_cliente),
            ("🔔 Lembrete", "#1f6feb", self.configurar_lembrete_cliente_selecionado),
            ("📣 Cobranças", "#d29922", self.abrir_central_cobrancas),
            ("💰 Receber", "#2ea043", self.receber_pagamento_cliente_selecionado),
            ("📜 Histórico", "#1f6feb", self.abrir_historico_cliente_selecionado),
        ):
            ctk.CTkButton(
                acoes_clientes,
                text=texto,
                fg_color=cor,
                height=36,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=comando,
            ).pack(side="left", expand=True, fill="x", padx=2)

        # O ttk.Treeview aplica cor e fonte por linha. As faixas abaixo tornam
        # dívidas visíveis imediatamente sem alterar os dados do cliente.
        self.tabela_cli.tag_configure("saldo_ok", foreground="#ffffff")
        self.tabela_cli.tag_configure("saldo_atencao", foreground="#ffd33d")
        self.tabela_cli.tag_configure("saldo_critico", foreground="#ff7b72")
        
        scrollbar_cli = ttk.Scrollbar(tabela_cli_frame, orient="vertical", command=self.tabela_cli.yview)
        self.tabela_cli.configure(yscrollcommand=scrollbar_cli.set)
        self.tabela_cli.grid(row=0, column=0, sticky="nsew")
        scrollbar_cli.grid(row=0, column=1, sticky="ns")

        self._clientes_layout_after = None

        def ajustar_colunas_clientes(event):
            if self._clientes_layout_after is not None:
                try:
                    tabela_cli_frame.after_cancel(self._clientes_layout_after)
                except Exception:
                    pass
            def aplicar():
                self._clientes_layout_after = None
                largura = max(1, int(tabela_cli_frame.winfo_width()) - 18)
                LayoutManager.apply_client_treeview(self.tabela_cli, largura)
            self._clientes_layout_after = tabela_cli_frame.after(80, aplicar)

        tabela_cli_frame.bind("<Configure>", ajustar_colunas_clientes, add="+")
        self.adicionar_rodape_status(frame)
        self.tabela_cli.bind("<Double-1>", lambda event: self.editar_cliente_selecionado())
        self.tabela_cli.bind("<Double-3>", lambda event: self.abrir_historico_cliente_selecionado())
        
        return frame

    def carregar_clientes(self, termo="", manter_pagina=True):
        """Carrega clientes fora da thread gráfica para impedir travamentos."""
        if not hasattr(self, 'tabela_cli'):
            return
        if not manter_pagina:
            self.pagina_clientes = 0

        somente_favoritos = bool(
            hasattr(self, "var_somente_favoritos") and self.var_somente_favoritos.get()
        )
        pagina_solicitada = max(0, getattr(self, "pagina_clientes", 0))
        por_pagina = getattr(self, "clientes_por_pagina", 250)

        # Cada chamada recebe um número; resultados antigos são descartados.
        self._carga_clientes_id = getattr(self, "_carga_clientes_id", 0) + 1
        carga_id = self._carga_clientes_id
        if hasattr(self, "lbl_pagina_clientes"):
            self.lbl_pagina_clientes.configure(text="Carregando...")
            self.btn_anterior_pagina_clientes.configure(state="disabled")
            self.btn_proxima_pagina_clientes.configure(state="disabled")

        def consultar():
            try:
                resultado = CLIENTE_REPOSITORY.list_page(
                    termo,
                    favorites_only=somente_favoritos,
                    page=pagina_solicitada,
                    per_page=por_pagina,
                )
                self.after(0, lambda: self._aplicar_clientes_carregados(
                    carga_id,
                    resultado.rows,
                    resultado.total,
                    resultado.total_pages,
                    resultado.page,
                    resultado.offset,
                ))
            except Exception as exc:
                logger.exception("Falha ao consultar clientes paginados.")
                self.after(0, lambda erro=str(exc): self._erro_carregar_clientes(carga_id, erro))

        threading.Thread(target=consultar, daemon=True).start()

    def _aplicar_clientes_carregados(self, carga_id, clientes, total, total_paginas, pagina, offset):
        if carga_id != getattr(self, "_carga_clientes_id", None) or not hasattr(self, "tabela_cli"):
            return
        self.pagina_clientes = pagina
        self.tabela_cli.delete(*self.tabela_cli.get_children())
        for c in clientes:
            c_id, ficha, nome, saldo, lim, telefone, cpf, favorito = c
            saldo_valor = float(saldo or 0.0)
            estrela = "★" if favorito else ""
            if saldo_valor > 500.0:
                tag_saldo = "saldo_critico"
            elif saldo_valor > 0.005:
                tag_saldo = "saldo_atencao"
            else:
                tag_saldo = "saldo_ok"
            self.tabela_cli.insert("", "end", iid=str(c_id), values=(
                ficha or "", nome or "", f"R$ {saldo_valor:.2f}",
                f"R$ {(lim or 0.0):.2f}", telefone or "", cpf or "", estrela
            ), tags=(tag_saldo,))

        inicio = offset + 1 if total else 0
        fim = min(offset + len(clientes), total)
        self.lbl_pagina_clientes.configure(
            text=f"{inicio}-{fim} de {total}  |  pág. {pagina + 1}/{total_paginas}"
        )
        self.btn_anterior_pagina_clientes.configure(state="normal" if pagina > 0 else "disabled")
        self.btn_proxima_pagina_clientes.configure(state="normal" if pagina < total_paginas - 1 else "disabled")

    def _erro_carregar_clientes(self, carga_id, erro):
        if carga_id != getattr(self, "_carga_clientes_id", None):
            return
        if hasattr(self, "lbl_pagina_clientes"):
            self.lbl_pagina_clientes.configure(text="Erro ao carregar")
        messagebox.showerror("Clientes", f"Não foi possível carregar os clientes:\n{erro}")

    def mudar_pagina_clientes(self, direcao):
        self.pagina_clientes = max(0, getattr(self, "pagina_clientes", 0) + direcao)
        termo = self.entry_busca_cliente.get().strip() if hasattr(self, "entry_busca_cliente") else ""
        self.carregar_clientes(termo, manter_pagina=True)

    def filtrar_tabela_clientes(self, event=None):
        # Debounce: não executa uma consulta pesada a cada tecla pressionada.
        if getattr(self, "_filtro_clientes_after", None):
            try:
                self.after_cancel(self._filtro_clientes_after)
            except Exception:
                pass
        self._filtro_clientes_after = self.after(250, self._executar_filtro_clientes)

    def _executar_filtro_clientes(self):
        self._filtro_clientes_after = None
        termo = self.entry_busca_cliente.get().strip() if hasattr(self, "entry_busca_cliente") else ""
        self.carregar_clientes(termo, manter_pagina=False)

    def alternar_favorito_cliente(self):
        selecionado = self.tabela_cli.selection() if hasattr(self, "tabela_cli") else ()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um cliente para favoritar ou desfavoritar.")
            return

        cliente_id = selecionado[0]
        try:
            novo_valor = CLIENTE_REPOSITORY.toggle_favorite(int(cliente_id))
        except (TypeError, ValueError) as exc:
            logger.warning("Não foi possível alternar favorito do cliente %s: %s", cliente_id, exc)
            messagebox.showerror("Erro", str(exc))
            return
        except Exception as exc:
            logger.exception("Falha ao alternar favorito do cliente %s", cliente_id)
            messagebox.showerror("Erro", f"Não foi possível atualizar o favorito:\n{exc}")
            return

        self.filtrar_tabela_clientes()
        mensagem = "Cliente adicionado aos favoritos." if novo_valor else "Cliente removido dos favoritos."
        messagebox.showinfo("Favoritos", mensagem)

    def abrir_cadastro_cliente(self, on_saved=None):
        janela_cad = ctk.CTkToplevel(self)
        janela_cad.nabi_help_context = "clientes"
        janela_cad.title("Cadastrar Novo Cliente")
        metricas = UniversalLayoutPolicy.metrics(
            janela_cad.winfo_screenwidth(), janela_cad.winfo_screenheight(),
            preferred_width=900, preferred_height=680,
        )
        janela_cad.geometry(UniversalLayoutPolicy.geometry(metricas))
        janela_cad.minsize(UniversalLayoutPolicy.MIN_WIDTH, UniversalLayoutPolicy.MIN_HEIGHT)
        janela_cad.configure(fg_color="#0d1117")
        janela_cad.transient(self)
        janela_cad.grab_set()

        cabecalho = ctk.CTkFrame(janela_cad, fg_color="#0d1117")
        cabecalho.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(cabecalho, text="Novo Cliente", font=ctk.CTkFont(size=19, weight="bold"), text_color="#00FF88").pack(anchor="w")
        ctk.CTkLabel(cabecalho, text="Dados cadastrais e limite de crédito", text_color="#8b949e").pack(anchor="w", pady=(2, 0))

        scroll = BidirectionalScrollableFrame(janela_cad, fg_color="#161b22", corner_radius=10, content_width=850)
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        form = scroll.content
        form.grid_columnconfigure((0, 1), weight=1, uniform="cliente")

        def campo(rotulo, linha, coluna, *, valor="", colspan=1):
            bloco = ctk.CTkFrame(form, fg_color="transparent")
            bloco.grid(row=linha, column=coluna, columnspan=colspan, sticky="ew", padx=8, pady=6)
            ctk.CTkLabel(bloco, text=rotulo, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 3))
            entrada = ctk.CTkEntry(bloco, height=38, fg_color="#0d1117", text_color="#ffffff")
            entrada.pack(fill="x")
            if valor != "":
                entrada.insert(0, str(valor))
            return entrada

        proxima = int(obter_config("proxima_ficha") or 5500)
        e_ficha = campo("Número da ficha", 0, 0, valor=proxima)
        e_cod = campo("Código (opcional)", 0, 1)
        e_nome = campo("Nome completo *", 1, 0, colspan=2)
        e_cpf = campo("CPF", 2, 0)
        e_rg = campo("RG", 2, 1)
        e_tel = campo("Telefone", 3, 0)
        e_lim = campo("Limite de crédito (R$)", 3, 1, valor="500.00")
        e_end = campo("Endereço", 4, 0, colspan=2)
        e_email = campo("E-mail fiscal (opcional)", 5, 0, colspan=2)
        ctk.CTkLabel(form, text="Dados fiscais — necessários para NF-e", font=ctk.CTkFont(size=14, weight="bold"), text_color="#58a6ff").grid(row=6, column=0, columnspan=2, sticky="w", padx=8, pady=(12, 2))
        e_fiscal_logradouro = campo("Logradouro", 7, 0)
        e_fiscal_numero = campo("Número", 7, 1)
        e_fiscal_bairro = campo("Bairro", 8, 0)
        e_fiscal_municipio = campo("Município", 8, 1)
        e_fiscal_codigo = campo("Código IBGE do município", 9, 0)
        e_fiscal_uf = campo("UF", 9, 1)
        e_fiscal_cep = campo("CEP", 10, 0)
        e_ie = campo("Inscrição estadual", 10, 1)
        contribuinte_var = tk.IntVar(value=0)
        ctk.CTkCheckBox(form, text="Cliente contribuinte de ICMS", variable=contribuinte_var).grid(row=11, column=0, columnspan=2, sticky="w", padx=16, pady=8)
        e_obs = campo("Observações", 12, 0, colspan=2)

        def salvar_novo_cliente():
            nome = e_nome.get().strip()
            try:
                cliente_id = CUSTOMER_REGISTRATION_SERVICE.criar(
                    nome=nome,
                    codigo=e_cod.get(),
                    numero_ficha=e_ficha.get(),
                    cpf=e_cpf.get(),
                    rg=e_rg.get(),
                    telefone=e_tel.get(),
                    endereco=e_end.get(),
                    observacoes=e_obs.get(),
                    limite=e_lim.get(),
                    email=e_email.get(),
                    inscricao_estadual=e_ie.get(),
                    contribuinte_icms=bool(contribuinte_var.get()),
                    fiscal_logradouro=e_fiscal_logradouro.get() or e_end.get(),
                    fiscal_numero=e_fiscal_numero.get(),
                    fiscal_bairro=e_fiscal_bairro.get(),
                    fiscal_codigo_municipio=e_fiscal_codigo.get(),
                    fiscal_municipio=e_fiscal_municipio.get(),
                    fiscal_uf=e_fiscal_uf.get(),
                    fiscal_cep=e_fiscal_cep.get(),
                )
                janela_cad.destroy(); self.carregar_clientes(); self.atualizar_resumo_lateral()
                if callable(on_saved):
                    on_saved(cliente_id, nome)
                return True
            except (ValueError, sqlite3.IntegrityError) as exc:
                mensagem = str(exc) if isinstance(exc, ValueError) else "Já existe um cliente cadastrado com este código!"
                messagebox.showerror("Erro", mensagem, parent=janela_cad)
                return False

        rodape = ctk.CTkFrame(janela_cad, fg_color="#0d1117")
        rodape.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkButton(rodape, text="Cancelar", width=120, height=42, fg_color="#30363d", command=janela_cad.destroy).pack(side="left")
        ctk.CTkButton(rodape, text="Salvar cliente", width=170, height=42, fg_color="#2ea043", command=salvar_novo_cliente).pack(side="right")
        janela_cad.bind("<Control-s>", lambda _e: salvar_novo_cliente(), add="+")
        janela_cad.bind("<Escape>", lambda _e: janela_cad.destroy(), add="+")
        janela_cad._enter_navigator = install_enter_navigation(
            [e_ficha, e_cod, e_nome, e_cpf, e_rg, e_tel, e_lim, e_end, e_email,
             e_fiscal_logradouro, e_fiscal_numero, e_fiscal_bairro, e_fiscal_municipio,
             e_fiscal_codigo, e_fiscal_uf, e_fiscal_cep, e_ie, e_obs],
            on_finish=salvar_novo_cliente,
        )

    def _cliente_selecionado_id(self):
        selecionado = self.tabela_cli.selection() if hasattr(self, "tabela_cli") else ()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um cliente na tabela.")
            return None
        return int(selecionado[0])

    def editar_cliente_selecionado(self):
        cliente_id = self._cliente_selecionado_id()
        if not cliente_id:
            return
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("SELECT numero_ficha,codigo,nome,cpf,rg,telefone,endereco,limite,observacoes FROM clientes WHERE id=?", (cliente_id,))
        dados = cur.fetchone(); conn.close()
        if not dados:
            return
        win = ctk.CTkToplevel(self); win.title("Editar Cliente"); win.geometry("500x760"); win.configure(fg_color="#0d1117"); win.grab_set()
        ctk.CTkLabel(win, text="✏️ Editar Cliente", font=ctk.CTkFont(size=18, weight="bold"), text_color="#00FF88").pack(pady=12)
        nomes = ["Número da ficha", "Código", "Nome", "CPF", "RG", "Telefone", "Endereço", "Limite", "Observações"]
        entradas=[]
        for rotulo, valor in zip(nomes, dados):
            ctk.CTkLabel(win, text=rotulo, anchor="w").pack(fill="x", padx=25)
            e=ctk.CTkEntry(win, height=34, fg_color="#161b22", text_color="#ffffff"); e.pack(fill="x", padx=25, pady=(1,6)); e.insert(0, "" if valor is None else str(valor)); entradas.append(e)
        def salvar():
            try:
                ficha = int(entradas[0].get()) if entradas[0].get().strip() else None
                limite = tratar_numero(entradas[7].get())
            except ValueError:
                messagebox.showerror("Erro", "Ficha ou limite inválido."); return
            conn=conectar_banco(); cur=conn.cursor()
            cur.execute("SELECT limite, observacoes FROM clientes WHERE id=?", (cliente_id,)); antigo=cur.fetchone()
            try:
                cur.execute("""UPDATE clientes SET numero_ficha=?,codigo=?,nome=?,cpf=?,rg=?,telefone=?,endereco=?,limite=?,observacoes=? WHERE id=?""",
                    (ficha, entradas[1].get().strip(), entradas[2].get().strip(), entradas[3].get().strip(), entradas[4].get().strip(), entradas[5].get().strip(), entradas[6].get().strip(), limite, entradas[8].get().strip(), cliente_id))
                conn.commit(); conn.close()
            except sqlite3.IntegrityError:
                conn.close(); messagebox.showerror("Erro", "Código já utilizado por outro cliente."); return
            registrar_historico(cliente_id, "EDIÇÃO", "Dados cadastrais atualizados.")
            if antigo and float(antigo[0] or 0) != limite:
                registrar_historico(cliente_id, "LIMITE", f"Limite alterado de R$ {float(antigo[0] or 0):.2f} para R$ {limite:.2f}.")
            if antigo and (antigo[1] or "") != entradas[8].get().strip():
                registrar_historico(cliente_id, "OBSERVAÇÃO", "Observações do cliente atualizadas.")
            win.destroy(); self.filtrar_tabela_clientes(); self.atualizar_resumo_lateral(); messagebox.showinfo("Sucesso", "Cliente atualizado.")
        botoes = ctk.CTkFrame(win, fg_color="transparent")
        botoes.pack(fill="x", padx=25, pady=12)
        ctk.CTkButton(botoes, text="💬 Cobrar Cliente", fg_color="#25D366", hover_color="#1da851", height=40, command=self.cobrar_cliente_selecionado).pack(side="left", expand=True, fill="x", padx=(0,5))
        ctk.CTkButton(botoes, text="💾 Salvar Alterações", fg_color="#2ea043", hover_color="#238636", height=40, command=salvar).pack(side="left", expand=True, fill="x", padx=(5,0))
        ctk.CTkButton(win, text="🧾 Dados fiscais do cliente", fg_color="#1f6feb", height=38, command=lambda: self.editar_perfil_fiscal_cliente(cliente_id)).pack(fill="x", padx=25, pady=(0, 12))

    def editar_perfil_fiscal_cliente(self, cliente_id):
        conn = conectar_banco()
        try:
            row = conn.execute(
                """SELECT email,inscricao_estadual,contribuinte_icms,fiscal_logradouro,
                          fiscal_numero,fiscal_bairro,fiscal_codigo_municipio,
                          fiscal_municipio,fiscal_uf,fiscal_cep
                     FROM clientes WHERE id=?""", (int(cliente_id),)
            ).fetchone()
        finally:
            conn.close()
        if not row:
            messagebox.showerror("Dados fiscais", "Cliente não encontrado.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Dados fiscais do cliente")
        win.geometry("620x720")
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text="Dados fiscais do cliente", font=ctk.CTkFont(size=19, weight="bold"), text_color="#00FF88").pack(pady=(16, 4))
        ctk.CTkLabel(win, text="Preencha uma vez; o NabiCode reutiliza automaticamente nas próximas NF-e.", text_color="#8b949e").pack(pady=(0, 10))
        frame = ctk.CTkScrollableFrame(win, fg_color="#161b22")
        frame.pack(fill="both", expand=True, padx=18, pady=8)
        labels = ("E-mail", "Inscrição estadual", "Logradouro", "Número", "Bairro", "Código IBGE do município", "Município", "UF", "CEP")
        indexes = (0, 1, 3, 4, 5, 6, 7, 8, 9)
        entries = []
        for label, index in zip(labels, indexes):
            ctk.CTkLabel(frame, text=label, anchor="w").pack(fill="x", padx=8)
            entry = ctk.CTkEntry(frame, height=34)
            entry.pack(fill="x", padx=8, pady=(2, 7))
            entry.insert(0, str(row[index] or ""))
            entries.append(entry)
        contribuinte = tk.IntVar(value=int(row[2] or 0))
        ctk.CTkCheckBox(frame, text="Contribuinte de ICMS", variable=contribuinte).pack(anchor="w", padx=8, pady=8)

        def salvar_fiscal():
            try:
                CUSTOMER_REGISTRATION_SERVICE.atualizar_perfil_fiscal(
                    int(cliente_id), email=entries[0].get(), inscricao_estadual=entries[1].get(),
                    contribuinte_icms=bool(contribuinte.get()), fiscal_logradouro=entries[2].get(),
                    fiscal_numero=entries[3].get(), fiscal_bairro=entries[4].get(),
                    fiscal_codigo_municipio=entries[5].get(), fiscal_municipio=entries[6].get(),
                    fiscal_uf=entries[7].get(), fiscal_cep=entries[8].get(),
                )
            except ValueError as exc:
                messagebox.showerror("Dados fiscais", str(exc), parent=win)
                return
            registrar_historico(int(cliente_id), "FISCAL", "Perfil fiscal do cliente atualizado.")
            win.destroy()
            messagebox.showinfo("Dados fiscais", "Perfil fiscal atualizado com sucesso.")

        ctk.CTkButton(win, text="Salvar dados fiscais", height=42, fg_color="#2ea043", command=salvar_fiscal).pack(fill="x", padx=18, pady=(0, 16))

    def cobrar_cliente_selecionado(self):
        cliente_id = self._cliente_selecionado_id()
        if not cliente_id:
            return

        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("SELECT nome, telefone, saldo_devedor FROM clientes WHERE id=?", (cliente_id,))
        cliente = cur.fetchone()
        conn.close()

        if not cliente:
            messagebox.showerror("Erro", "Cliente não encontrado.")
            return

        nome, telefone, saldo = cliente
        saldo = float(saldo or 0.0)

        if not telefone:
            messagebox.showwarning("Cobrança", "Este cliente não possui telefone cadastrado.")
            return

        if saldo <= 0:
            messagebox.showinfo("Cobrança", "Este cliente não possui saldo devedor.")
            return

        loja = obter_config("nome_loja") or "Nossa loja"
        numero = "".join(ch for ch in str(telefone) if ch.isdigit())

        mensagem = (
            f"Olá {nome}, tudo bem?\n\n"
            f"Aqui é da {loja}.\n"
            f"Estamos entrando em contato sobre sua pendência no valor de "
            f"R$ {saldo:,.2f}.\n\n"
            "Podemos combinar o pagamento?"
        )

        url = "https://wa.me/" + numero + "?text=" + urllib.parse.quote(mensagem)
        webbrowser.open(url)

    def _abrir_whatsapp(self, telefone, mensagem):
        numero = "".join(ch for ch in str(telefone or "") if ch.isdigit())
        if not numero:
            messagebox.showwarning("WhatsApp", "O cliente não possui telefone cadastrado.")
            return False
        if len(numero) in (10, 11):
            numero = "55" + numero
        webbrowser.open("https://wa.me/" + numero + "?text=" + urllib.parse.quote(mensagem))
        return True

    def abrir_central_cobrancas(self):
        win = ctk.CTkToplevel(self)
        win.title("Cobranças e Lembretes")
        win.geometry("1180x720")
        win.minsize(980, 620)
        win.configure(fg_color="#0d1117")
        win.grab_set()

        ctk.CTkLabel(win, text="📣 Cobranças e Lembretes de Promissórias",
                     font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffffff").pack(pady=(14, 8))
        abas = ctk.CTkTabview(win, fg_color="#161b22")
        abas.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        aba_atrasadas = abas.add("Promissórias atrasadas")
        aba_lembretes = abas.add("Lembretes antes do vencimento")
        aba_retornos = abas.add("Retornos agendados")

        frame_acoes = ctk.CTkFrame(aba_atrasadas, fg_color="transparent")
        frame_acoes.pack(fill="x", padx=8, pady=8)
        self.lbl_resumo_cobrancas = ctk.CTkLabel(frame_acoes, text="Carregando...", text_color="#ffd33d")
        self.lbl_resumo_cobrancas.pack(side="left")
        self.combo_filtro_cobrancas = ctk.CTkComboBox(frame_acoes, values=list(COBRANCA_SERVICE.FILTROS), width=150, command=lambda _=None: self.carregar_cobrancas_atrasadas())
        self.combo_filtro_cobrancas.set("Todas")
        self.combo_filtro_cobrancas.pack(side="left", padx=(16, 4))
        ctk.CTkButton(frame_acoes, text="Atualizar", width=90, command=self.carregar_cobrancas_atrasadas).pack(side="right", padx=4)
        ctk.CTkButton(frame_acoes, text="Registrar contato", width=140, fg_color="#8957e5", command=self.registrar_contato_cobranca_selecionado).pack(side="right", padx=4)
        ctk.CTkButton(frame_acoes, text="Cobrar pelo WhatsApp", width=170, fg_color="#25D366", hover_color="#1da851", command=self.cobrar_promissoria_selecionada).pack(side="right", padx=4)

        cols=("Cliente","Telefone","Parcela","Valor","Vencimento","Dias","Último contato","Situação")
        self.tabela_cobrancas = ttk.Treeview(aba_atrasadas, columns=cols, show="headings")
        for c in cols: self.tabela_cobrancas.heading(c, text=c)
        widths={"Cliente":230,"Telefone":125,"Parcela":75,"Valor":100,"Vencimento":105,"Dias":70,"Último contato":145,"Situação":150}
        for c in cols: self.tabela_cobrancas.column(c,width=widths[c],anchor="w" if c in ("Cliente","Situação") else "center")
        self.tabela_cobrancas.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.tabela_cobrancas.bind("<Double-1>", lambda e: self.cobrar_promissoria_selecionada())

        frame_lemb = ctk.CTkFrame(aba_lembretes, fg_color="transparent")
        frame_lemb.pack(fill="x", padx=8, pady=8)
        self.lbl_resumo_lembretes = ctk.CTkLabel(frame_lemb, text="", text_color="#58a6ff")
        self.lbl_resumo_lembretes.pack(side="left")
        ctk.CTkButton(frame_lemb, text="Atualizar", width=90, command=self.carregar_lembretes_cobranca).pack(side="right", padx=4)
        ctk.CTkButton(frame_lemb, text="Avisar pelo WhatsApp", width=175, fg_color="#25D366", hover_color="#1da851", command=self.avisar_lembrete_selecionado).pack(side="right", padx=4)

        cols2=("Cliente","Telefone","Parcela","Valor","Vencimento","Avisar em","Observação")
        self.tabela_lembretes = ttk.Treeview(aba_lembretes, columns=cols2, show="headings")
        for c in cols2: self.tabela_lembretes.heading(c, text=c)
        widths2={"Cliente":220,"Telefone":125,"Parcela":75,"Valor":100,"Vencimento":105,"Avisar em":105,"Observação":300}
        for c in cols2: self.tabela_lembretes.column(c,width=widths2[c],anchor="w" if c in ("Cliente","Observação") else "center")
        self.tabela_lembretes.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.tabela_lembretes.bind("<Double-1>", lambda e: self.avisar_lembrete_selecionado())

        frame_ret = ctk.CTkFrame(aba_retornos, fg_color="transparent")
        frame_ret.pack(fill="x", padx=8, pady=8)
        self.lbl_resumo_retornos = ctk.CTkLabel(frame_ret, text="", text_color="#f0b429")
        self.lbl_resumo_retornos.pack(side="left")
        ctk.CTkButton(frame_ret, text="Atualizar", width=90, command=self.carregar_retornos_cobranca).pack(side="right", padx=4)
        ctk.CTkButton(frame_ret, text="Cobrar pelo WhatsApp", width=170, fg_color="#25D366", hover_color="#1da851", command=self.cobrar_retorno_selecionado).pack(side="right", padx=4)
        ctk.CTkButton(frame_ret, text="Registrar novo retorno", width=165, fg_color="#8957e5", command=self.registrar_retorno_selecionado).pack(side="right", padx=4)

        cols3=("Cliente","Telefone","Parcela","Valor","Vencimento","Retornar em","Resultado","Observação")
        self.tabela_retornos = ttk.Treeview(aba_retornos, columns=cols3, show="headings")
        for c in cols3: self.tabela_retornos.heading(c, text=c)
        widths3={"Cliente":200,"Telefone":120,"Parcela":70,"Valor":95,"Vencimento":100,"Retornar em":105,"Resultado":130,"Observação":280}
        for c in cols3: self.tabela_retornos.column(c,width=widths3[c],anchor="w" if c in ("Cliente","Resultado","Observação") else "center")
        self.tabela_retornos.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.tabela_retornos.bind("<Double-1>", lambda e: self.cobrar_retorno_selecionado())

        self.carregar_cobrancas_atrasadas()
        self.carregar_lembretes_cobranca()
        self.carregar_retornos_cobranca()

    def carregar_cobrancas_atrasadas(self):
        if not hasattr(self, "tabela_cobrancas"):
            return
        for item in self.tabela_cobrancas.get_children():
            self.tabela_cobrancas.delete(item)
        filtro = self.combo_filtro_cobrancas.get() if hasattr(self, "combo_filtro_cobrancas") else "Todas"
        rows = COBRANCA_SERVICE.listar_atrasadas(filtro)
        hoje = datetime.now().date()
        for row in rows:
            dt = _data_sql(row.get("vencimento"))
            dias = (hoje-dt.date()).days if dt else 0
            situacao = row.get("situacao") or "Pendente"
            proximo = row.get("proximo_contato") or ""
            if proximo:
                situacao = f"{situacao} · retorno {proximo}"
            self.tabela_cobrancas.insert("","end",iid=str(row["parcela_id"]),values=(
                row["nome"],row.get("telefone") or "—",row.get("numero_parcela") or 1,
                f"R$ {float(row.get('valor_aberto') or 0):.2f}",row.get("vencimento") or "—",dias,
                row.get("ultimo_contato") or "Nunca",situacao),tags=(str(row["cliente_id"]),))
        resumo = COBRANCA_SERVICE.resumo(rows)
        self.lbl_resumo_cobrancas.configure(text=f"{resumo.quantidade} parcela(s) — Total: R$ {resumo.total:.2f}")

    def _dados_parcela_cobranca(self, parcela_id):
        return COBRANCA_SERVICE.dados_parcela(parcela_id)

    def cobrar_promissoria_selecionada(self):
        sel=self.tabela_cobrancas.selection() if hasattr(self,"tabela_cobrancas") else ()
        if not sel: messagebox.showwarning("Cobrança","Selecione uma promissória."); return
        parcela_id=int(sel[0]); dados=self._dados_parcela_cobranca(parcela_id)
        if not dados: return
        cliente_id=dados["cliente_id"]; nome=dados["nome"]; tel=dados.get("telefone")
        num=dados.get("numero_parcela"); valor=dados.get("valor_aberto"); venc=dados.get("vencimento")
        loja=obter_config("nome_loja") or "Nossa loja"
        mensagem=COBRANCA_SERVICE.mensagem_cobranca(nome=nome,loja=loja,parcela=num or 1,valor=float(valor or 0),vencimento=venc)
        if self._abrir_whatsapp(tel,mensagem):
            COBRANCA_SERVICE.registrar_contato(cliente_id=cliente_id, parcela_id=parcela_id, tipo="COBRANCA", resultado="WhatsApp aberto", observacao="Mensagem preparada para conferência antes do envio.")
            registrar_historico(cliente_id,"COBRANÇA",f"Cobrança da parcela {num or 1} preparada no WhatsApp.")
            self.carregar_cobrancas_atrasadas()

    def registrar_contato_cobranca_selecionado(self):
        sel=self.tabela_cobrancas.selection() if hasattr(self,"tabela_cobrancas") else ()
        if not sel: messagebox.showwarning("Cobrança","Selecione uma promissória."); return
        parcela_id=int(sel[0]); dados=self._dados_parcela_cobranca(parcela_id)
        if not dados: return
        cliente_id=dados["cliente_id"]; nome=dados["nome"]; num=dados.get("numero_parcela")
        win=ctk.CTkToplevel(self); win.title("Registrar contato de cobrança"); win.geometry("480x410"); win.configure(fg_color="#0d1117"); win.grab_set()
        ctk.CTkLabel(win,text=f"Contato — {nome} / Parcela {num or 1}",font=ctk.CTkFont(size=17,weight="bold")).pack(pady=15)
        resultado=ctk.CTkComboBox(win,values=["Contatado","Prometeu pagar","Não respondeu","Número inválido","Negociando","Outro"]); resultado.set("Contatado"); resultado.pack(fill="x",padx=25,pady=6)
        obs=ctk.CTkTextbox(win,height=110); obs.pack(fill="both",expand=True,padx=25,pady=6); obs.insert("1.0","Observação da cobrança")
        proximo=ctk.CTkEntry(win,placeholder_text="Próximo contato (AAAA-MM-DD, opcional)"); proximo.pack(fill="x",padx=25,pady=6)
        def salvar():
            prox=proximo.get().strip()
            if prox:
                try: datetime.strptime(prox,"%Y-%m-%d")
                except ValueError: messagebox.showerror("Data inválida","Use o formato AAAA-MM-DD."); return
            texto=obs.get("1.0","end").strip()
            COBRANCA_SERVICE.registrar_contato(cliente_id=cliente_id, parcela_id=parcela_id, tipo="COBRANCA", resultado=resultado.get(), observacao=texto, proximo_contato=prox)
            registrar_historico(cliente_id,"CONTATO DE COBRANÇA",f"{resultado.get()}. {texto}")
            win.destroy(); self.carregar_cobrancas_atrasadas()
        ctk.CTkButton(win,text="Salvar contato",fg_color="#2ea043",command=salvar).pack(fill="x",padx=25,pady=14)

    def configurar_lembrete_cliente_selecionado(self):
        cliente_id=self._cliente_selecionado_id()
        if not cliente_id: return
        parcelas=COBRANCA_SERVICE.parcelas_pendentes_cliente(cliente_id)
        if not parcelas: messagebox.showinfo("Lembrete","Este cliente não possui promissórias pendentes com vencimento."); return
        mapa={f"Parcela {row.get('numero_parcela') or 1} — {row.get('vencimento')} — R$ {float(row.get('valor_parcela') or 0):.2f}":row["parcela_id"] for row in parcelas}
        win=ctk.CTkToplevel(self); win.title("Lembrar antes do vencimento"); win.geometry("510x390"); win.configure(fg_color="#0d1117"); win.grab_set()
        ctk.CTkLabel(win,text="🔔 Lembrete de promissória",font=ctk.CTkFont(size=18,weight="bold")).pack(pady=15)
        combo=ctk.CTkComboBox(win,values=list(mapa.keys()),width=450); combo.set(next(iter(mapa))); combo.pack(padx=25,pady=7)
        dias=ctk.CTkComboBox(win,values=["1","2","3","5","7","10"]); dias.set("2"); dias.pack(fill="x",padx=25,pady=7)
        ctk.CTkLabel(win,text="Dias de antecedência").pack()
        obs=ctk.CTkTextbox(win,height=100); obs.pack(fill="both",expand=True,padx=25,pady=7); obs.insert("1.0","Cliente pediu para ser lembrado pelo WhatsApp.")
        def salvar():
            pid=mapa[combo.get()]; anteced=int(dias.get()); texto=obs.get("1.0","end").strip()
            COBRANCA_SERVICE.salvar_lembrete(cliente_id=cliente_id, parcela_id=pid, dias_antecedencia=anteced, observacao=texto)
            registrar_historico(cliente_id,"LEMBRETE",f"Avisar {anteced} dia(s) antes do vencimento. {texto}")
            win.destroy(); messagebox.showinfo("Lembrete salvo","O NabiCode mostrará esta promissória na aba de lembretes na data correta.")
        ctk.CTkButton(win,text="Salvar lembrete",fg_color="#2ea043",command=salvar).pack(fill="x",padx=25,pady=14)

    def carregar_lembretes_cobranca(self):
        if not hasattr(self,"tabela_lembretes"):
            return
        for item in self.tabela_lembretes.get_children():
            self.tabela_lembretes.delete(item)
        rows=COBRANCA_SERVICE.listar_lembretes_para_hoje()
        for row in rows:
            dt=_data_sql(row.get("vencimento")); dias=int(row.get("dias_antecedencia") or 0)
            avisar=(dt-timedelta(days=dias)).strftime("%Y-%m-%d") if dt else "—"
            self.tabela_lembretes.insert("","end",iid=str(row["lembrete_id"]),values=(
                row["nome"],row.get("telefone") or "—",row.get("numero_parcela") or 1,
                f"R$ {float(row.get('valor_aberto') or 0):.2f}",row.get("vencimento") or "—",avisar,row.get("observacao") or ""),
                tags=(str(row["parcela_id"]),str(row["cliente_id"])))
        self.lbl_resumo_lembretes.configure(text=f"{len(rows)} lembrete(s) ainda não enviado(s) hoje")

    def avisar_lembrete_selecionado(self):
        sel=self.tabela_lembretes.selection() if hasattr(self,"tabela_lembretes") else ()
        if not sel: messagebox.showwarning("Lembrete","Selecione um lembrete."); return
        lid=int(sel[0]); row=COBRANCA_SERVICE.dados_lembrete(lid)
        if not row: return
        cid=row["cliente_id"]; pid=row["parcela_id"]; nome=row["nome"]; tel=row.get("telefone")
        num=row.get("numero_parcela"); valor=row.get("valor_aberto"); venc=row.get("vencimento"); obs=row.get("observacao")
        loja=obter_config("nome_loja") or "Nossa loja"
        mensagem=COBRANCA_SERVICE.mensagem_lembrete(nome=nome,loja=loja,parcela=num or 1,valor=float(valor or 0),vencimento=venc,observacao=obs or "")
        if self._abrir_whatsapp(tel,mensagem):
            COBRANCA_SERVICE.marcar_lembrete_enviado(lembrete_id=lid, cliente_id=cid, parcela_id=pid, observacao=obs or "")
            registrar_historico(cid,"LEMBRETE ENVIADO",f"Lembrete da parcela {num or 1} preparado no WhatsApp.")
        self.carregar_lembretes_cobranca()

    def carregar_retornos_cobranca(self):
        if not hasattr(self, "tabela_retornos"):
            return
        for item in self.tabela_retornos.get_children():
            self.tabela_retornos.delete(item)
        rows = COBRANCA_SERVICE.listar_retornos_pendentes()
        for row in rows:
            self.tabela_retornos.insert("", "end", iid=str(row["contato_id"]), values=(
                row["nome"], row.get("telefone") or "—", row.get("numero_parcela") or 1,
                f"R$ {float(row.get('valor_aberto') or 0):.2f}", row.get("vencimento") or "—",
                row.get("proximo_contato") or "—", row.get("resultado") or "—", row.get("observacao") or ""),
                tags=(str(row["parcela_id"]), str(row["cliente_id"])))
        self.lbl_resumo_retornos.configure(text=f"{len(rows)} retorno(s) vencido(s) ou para hoje")

    def _dados_retorno_selecionado(self):
        sel = self.tabela_retornos.selection() if hasattr(self, "tabela_retornos") else ()
        if not sel:
            messagebox.showwarning("Retorno", "Selecione um retorno agendado.")
            return None
        contato_id = int(sel[0])
        return COBRANCA_SERVICE.dados_retorno(contato_id)

    def cobrar_retorno_selecionado(self):
        dados=self._dados_retorno_selecionado()
        if not dados:
            return
        cliente_id=dados["cliente_id"]; parcela_id=dados["parcela_id"]; nome=dados["nome"]
        tel=dados.get("telefone"); num=dados.get("numero_parcela"); valor=dados.get("valor_aberto"); venc=dados.get("vencimento")
        loja=obter_config("nome_loja") or "Nossa loja"
        mensagem=COBRANCA_SERVICE.mensagem_cobranca(nome=nome,loja=loja,parcela=num or 1,valor=float(valor or 0),vencimento=venc)
        if self._abrir_whatsapp(tel,mensagem):
            COBRANCA_SERVICE.registrar_contato(cliente_id=cliente_id,parcela_id=parcela_id,tipo="RETORNO",resultado="WhatsApp aberto",observacao="Retorno de cobrança preparado para conferência.")
            registrar_historico(cliente_id,"RETORNO DE COBRANÇA",f"Retorno da parcela {num or 1} preparado no WhatsApp.")
            self.carregar_retornos_cobranca(); self.carregar_cobrancas_atrasadas()

    def registrar_retorno_selecionado(self):
        dados=self._dados_retorno_selecionado()
        if not dados:
            return
        cliente_id=dados["cliente_id"]; parcela_id=dados["parcela_id"]; nome=dados["nome"]; num=dados.get("numero_parcela")
        win=ctk.CTkToplevel(self); win.title("Registrar novo retorno"); win.geometry("480x410"); win.configure(fg_color="#0d1117"); win.grab_set()
        ctk.CTkLabel(win,text=f"Novo retorno — {nome} / Parcela {num or 1}",font=ctk.CTkFont(size=17,weight="bold")).pack(pady=15)
        resultado=ctk.CTkComboBox(win,values=["Contatado","Prometeu pagar","Não respondeu","Negociando","Outro"]); resultado.set("Contatado"); resultado.pack(fill="x",padx=25,pady=6)
        obs=ctk.CTkTextbox(win,height=110); obs.pack(fill="both",expand=True,padx=25,pady=6); obs.insert("1.0","Observação do retorno")
        proximo=ctk.CTkEntry(win,placeholder_text="Próximo contato (AAAA-MM-DD, opcional)"); proximo.pack(fill="x",padx=25,pady=6)
        def salvar():
            try:
                COBRANCA_SERVICE.registrar_contato(cliente_id=cliente_id,parcela_id=parcela_id,tipo="RETORNO",resultado=resultado.get(),observacao=obs.get("1.0","end").strip(),proximo_contato=proximo.get().strip())
            except ValueError:
                messagebox.showerror("Data inválida","Use o formato AAAA-MM-DD."); return
            registrar_historico(cliente_id,"RETORNO DE COBRANÇA",f"{resultado.get()}. {obs.get('1.0','end').strip()}")
            win.destroy(); self.carregar_retornos_cobranca(); self.carregar_cobrancas_atrasadas()
        ctk.CTkButton(win,text="Salvar retorno",fg_color="#2ea043",command=salvar).pack(fill="x",padx=25,pady=14)

    def receber_pagamento_cliente_selecionado(self):
        cliente_id = self._cliente_selecionado_id()
        if not cliente_id:
            return
        try:
            dados = FINANCEIRO_SERVICE.preparar_recebimento_cliente(cliente_id)
        except ValueError as exc:
            messagebox.showerror("Erro", str(exc))
            return

        nome = dados["cliente"]["nome"]
        saldo = dados["saldo"]
        alvo_map = dados["alvos"]
        if saldo <= 0:
            messagebox.showinfo("Sem dívida", f"{nome} não possui saldo devedor.")
            return

        win = ctk.CTkToplevel(self)
        win.title("Receber Pagamento")
        win.geometry("620x570")
        win.configure(fg_color="#0d1117")
        win.grab_set()

        ctk.CTkLabel(win, text="💰 Receber Pagamento", font=ctk.CTkFont(size=19, weight="bold"), text_color="#00FF88").pack(pady=(18, 8))
        ctk.CTkLabel(win, text=f"Cliente: {nome}", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffffff").pack(pady=4)
        ctk.CTkLabel(win, text=f"Saldo atual: R$ {saldo:.2f}", font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffd700").pack(pady=6)

        ctk.CTkLabel(
            win, text="Pagamento aplicado ao saldo total; distribuição automática pelas dívidas abertas.",
            text_color="#c9d1d9"
        ).pack(anchor="w", padx=28, pady=(10, 3))

        e_valor = ctk.CTkEntry(win, placeholder_text="Valor recebido (R$)", height=40, fg_color="#161b22", text_color="#ffffff")
        e_valor.pack(fill="x", padx=28, pady=(12, 7))
        e_valor.focus()

        forma = ctk.CTkComboBox(win, values=["Dinheiro", "PIX", "Cartão", "Transferência", "Outro"], height=38, fg_color="#161b22", button_color="#21262d")
        forma.set("Dinheiro")
        forma.pack(fill="x", padx=28, pady=7)

        e_obs = ctk.CTkEntry(win, placeholder_text="Observação opcional", height=38, fg_color="#161b22", text_color="#ffffff")
        e_obs.pack(fill="x", padx=28, pady=7)

        def preencher_total():
            e_valor.delete(0, "end")
            e_valor.insert(0, f"{saldo:.2f}")

        ctk.CTkButton(win, text="Preencher valor total", fg_color="#1f6feb", hover_color="#1158c7", height=34, command=preencher_total).pack(fill="x", padx=28, pady=7)

        def confirmar():
            alvo = {"tipo": "AUTO", "limite": saldo}
            try:
                valor = FinanceiroCalculator.dinheiro(tratar_numero(e_valor.get()), campo="pagamento")
                FinanceiroCalculator.limitar_pagamento(valor, saldo, saldo)
            except ValueError as exc:
                messagebox.showwarning("Valor inválido", str(exc))
                return
            if not messagebox.askyesno("Confirmar pagamento", f"Registrar pagamento de R$ {valor:.2f} para {nome}?"):
                return
            try:
                resultado = FINANCEIRO_SERVICE.receber_pagamento_cliente(
                    cliente_id=cliente_id,
                    valor=valor,
                    alvo=alvo,
                    forma_pagamento=forma.get(),
                    observacao=e_obs.get(),
                    usuario=self._usuario_financeiro(),
                )
            except Exception as exc:
                messagebox.showerror("Erro", f"Não foi possível registrar o pagamento: {exc}")
                return

            registrar_historico(
                cliente_id,
                "PAGAMENTO",
                f"Pagamento de R$ {resultado['valor']:.2f} recebido via {resultado['forma_pagamento']}. "
                f"Saldo restante: R$ {resultado['novo_saldo']:.2f}."
                + (f" Observação: {resultado['observacao']}" if resultado["observacao"] else ""),
            )
            win.destroy()
            termo_atual = self.entry_busca_cliente.get().strip() if hasattr(self, "entry_busca_cliente") else ""
            self.carregar_clientes(termo_atual, manter_pagina=True)
            self.atualizar_resumo_lateral()
            self.carregar_historico_dia()
            try:
                self.janela_recibo_pagamento_cliente(
                    resultado["pagamento_mov_id"],
                    resultado["alocacoes"],
                    saldo_anterior=resultado["saldo_anterior"],
                    novo_saldo=resultado["novo_saldo"],
                )
            except Exception as exc:
                logger.exception("Pagamento salvo, mas a preparação do recibo falhou", exc_info=exc)
                messagebox.showerror(
                    "Recibo",
                    "O pagamento foi salvo, mas o recibo não pôde ser preparado:\n"
                    f"{exc}",
                    parent=self,
                )
            self.mostrar_notificacao(
                "Pagamento registrado",
                f"Pagamento de R$ {resultado['valor']:.2f} registrado. Saldo restante: R$ {resultado['novo_saldo']:.2f}.",
                nivel="success",
                duracao_ms=6000,
            )

        ctk.CTkButton(win, text="✅ Confirmar Pagamento", fg_color="#2ea043", hover_color="#238636", height=42, font=ctk.CTkFont(weight="bold"), command=confirmar).pack(fill="x", padx=28, pady=(12, 8))
        e_valor.bind("<Return>", lambda event: confirmar())
        win.bind("<Escape>", lambda event: win.destroy())

    def abrir_historico_cliente_selecionado(self):
        cliente_id = self._cliente_selecionado_id()
        if cliente_id: self.abrir_historico_cliente(cliente_id)

    def abrir_historico_cliente(self, cliente_id):
        dados_historico = CLIENT_HISTORY_REPOSITORY.load(cliente_id)
        if dados_historico is None:
            return
        cli = dados_historico.client
        transacoes = dados_historico.transactions
        stats = dados_historico.stats
        resumo = dados_historico.purchase_summary
        eventos_cadastro = dados_historico.events

        ficha, nome, limite, saldo, observacoes = cli
        credito = max(0.0, float(limite or 0)-float(saldo or 0))
        win = ctk.CTkToplevel(self)
        prepare_hidden_toplevel(win)
        win.title(f"Histórico - Ficha {ficha or '—'} - {nome}")
        geometry, minimum = LayoutManager.window_geometry(
            win.winfo_screenwidth(),
            win.winfo_screenheight(),
            preferred_width=1100,
            preferred_height=780,
            min_width=840,
            min_height=620,
        )
        win.geometry(geometry)
        win.minsize(*minimum)
        win.configure(fg_color="#0d1117")
        cabecalho_historico = ctk.CTkFrame(win, fg_color="transparent")
        cabecalho_historico.pack(fill="x", padx=20, pady=(14, 5))
        ctk.CTkLabel(
            cabecalho_historico,
            text=f"📜 FICHA {ficha or '—'} — {nome}",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=self.cor_acento,
        ).pack(side="left", anchor="w")
        ctk.CTkLabel(
            cabecalho_historico,
            text=f"SALDO DEVEDOR: R$ {float(saldo or 0):.2f}",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#ff7b72" if float(saldo or 0) > 0.005 else "#3fb950",
        ).pack(side="right", anchor="e")

        painel = ctk.CTkFrame(win, fg_color="#161b22", corner_radius=10)
        painel.pack(fill="x", padx=20, pady=(4,8))
        faixas = resumo["faixas"]
        linha1 = (f"Compras: {resumo['total_compras']}   |   Sem atraso: {faixas.get(0,0)}   |   "
                  f"1 atraso: {faixas.get(1,0)}   |   2 atrasos: {faixas.get(2,0)}   |   "
                  f"3 atrasos: {faixas.get(3,0)}   |   4+ atrasos: {faixas.get(4,0)}")
        linha2 = (f"Parcelas rastreadas: {resumo['parcelas_emitidas']}   |   Pagas no prazo: {resumo['pagas_prazo']}   |   "
                  f"Pagas em atraso: {resumo['pagas_atraso']}   |   Vencidas em aberto: {resumo['vencidas_aberto']}")
        linha3 = (f"Saldo: R$ {float(saldo or 0):.2f}   |   Limite: R$ {float(limite or 0):.2f}   |   "
                  f"Crédito disponível: R$ {credito:.2f}   |   Primeira compra: {resumo['primeira_compra']}   |   "
                  f"Última compra: {resumo['ultima_compra']}")
        for texto, cor in ((linha1,"#ffffff"),(linha2,"#ffd33d"),(linha3,self.cor_acento)):
            ctk.CTkLabel(painel,text=texto,wraplength=920,justify="left",text_color=cor,
                         font=ctk.CTkFont(size=12,weight="bold")).pack(anchor="w",padx=14,pady=4)
        if faixas.get("sem_dados",0) or resumo["parcelas_sem_dados"]:
            ctk.CTkLabel(painel,
                text=(f"ℹ️ {faixas.get('sem_dados',0)} compra(s) antiga(s) não foram classificadas por atraso, "
                      "pois o banco anterior não registrava a data de pagamento de cada parcela."),
                wraplength=920,justify="left",text_color="#8b949e").pack(anchor="w",padx=14,pady=(0,7))

        ctk.CTkLabel(win,text=f"Observações: {observacoes or 'Nenhuma'}",wraplength=920,justify="left").pack(fill="x",padx=24,pady=3)
        abas = ctk.CTkTabview(win, fg_color="#161b22")
        abas.pack(fill="both",expand=True,padx=20,pady=(5,12))
        aba_transacoes = abas.add("Últimas 12 transações")
        aba_compras = abas.add("Compras e parcelas")
        aba_eventos = abas.add("Eventos do cadastro")

        caixa = ctk.CTkTextbox(aba_transacoes,fg_color="#0d1117",text_color="#ffffff")
        caixa.pack(fill="both",expand=True,padx=8,pady=8)
        icones={"COMPRA":"🛒","PAGAMENTO":"💰","ABATIMENTO":"🏷️","ESTORNO":"↩️","AJUSTE":"⚙️"}
        if transacoes:
            for mov_id,tipo,desc,valor,data in transacoes:
                sinal="-" if tipo in ("PAGAMENTO","ABATIMENTO") else "+"
                caixa.insert("end",f"{icones.get(tipo,'•')} {data or 'Sem data'} — {tipo} #{mov_id}\n   {desc or 'Sem descrição'}\n   Valor: {sinal} R$ {float(valor or 0):.2f}\n\n")
        else: caixa.insert("end","Nenhuma transação financeira encontrada.")
        caixa.configure(state="disabled")

        compras_txt=ctk.CTkTextbox(aba_compras,fg_color="#0d1117",text_color="#ffffff")
        compras_txt.pack(fill="both",expand=True,padx=8,pady=8)
        if resumo["compras"]:
            for compra in resumo["compras"]:
                atraso_txt = f"{compra['atrasos']} atraso(s)" if compra["confiavel"] else "sem dados confiáveis de parcelas"
                compras_txt.insert("end",f"🛒 Compra #{compra['id']} — {compra['data'] or 'Sem data'}\n   {compra['descricao']}\n   Valor: R$ {compra['valor']:.2f} | Resultado: {atraso_txt}\n")
                for p in compra["parcelas"]:
                    if not p["confiavel"]:
                        situacao="dados legados"
                    elif p["atrasada"] and str(p["status"]).upper()=="PAGO": situacao="PAGA COM ATRASO"
                    elif p["atrasada"]: situacao="VENCIDA EM ABERTO"
                    elif str(p["status"]).upper()=="PAGO": situacao="PAGA NO PRAZO"
                    else: situacao=str(p["status"]).upper()
                    compras_txt.insert("end",f"      Parcela {p['numero']}: R$ {p['valor']:.2f} | venc. {p['vencimento'] or '—'} | {situacao}\n")
                compras_txt.insert("end","\n")
        else: compras_txt.insert("end","Nenhuma compra encontrada.")
        compras_txt.configure(state="disabled")

        caixa_eventos=ctk.CTkTextbox(aba_eventos,fg_color="#0d1117",text_color="#ffffff")
        caixa_eventos.pack(fill="both",expand=True,padx=8,pady=8)
        for evento,detalhes,data in eventos_cadastro:
            caixa_eventos.insert("end",f"• {data} — {evento}\n   {detalhes or ''}\n\n")
        if not eventos_cadastro: caixa_eventos.insert("end","Nenhum evento cadastral encontrado.")
        caixa_eventos.configure(state="disabled")

        barra_doc=ctk.CTkFrame(win,fg_color="transparent")
        barra_doc.pack(fill="x",padx=20,pady=(0,10))
        ctk.CTkButton(barra_doc,text="Fechar",width=110,command=win.destroy).pack(side="right")
        reveal_prepared_toplevel_when_idle(win, grab=True)

    def excluir_cadastros_ficticios(self):
        if not messagebox.askyesno(
            "Excluir cadastros fictícios",
            "Excluir todos os clientes fictícios e seus históricos/movimentações?\nEssa ação não pode ser desfeita.",
        ):
            return
        try:
            total = CUSTOMER_MAINTENANCE_SERVICE.delete_fictitious_customers()
        except Exception as exc:
            logger.exception("Falha ao excluir cadastros fictícios.")
            messagebox.showerror("Excluir cadastros fictícios", str(exc))
            return
        self.carregar_clientes()
        self.atualizar_resumo_lateral()
        messagebox.showinfo("Concluído", f"{total} cadastro(s) fictício(s) excluído(s).")

    def exportar_clientes_csv(self):
        caminho = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="clientes_nabicode.csv",
        )
        if not caminho:
            return
        try:
            arquivo = CUSTOMER_MAINTENANCE_SERVICE.export_csv(caminho)
        except Exception as exc:
            logger.exception("Falha ao exportar clientes para CSV.")
            messagebox.showerror("Exportação", str(exc))
            return
        messagebox.showinfo("Exportação", f"Clientes exportados com sucesso.\n{arquivo}")

    def janela_venda_finalizada(self, cliente_id, itens, total, tipo, documento_id=None):
        """Mostra as ações pós-venda sem imprimir ou gerar arquivo automaticamente.

        O layout é deliberadamente simples e estável no Windows. Cada botão
        executa uma ação explícita: cupom 80 mm, somente finalizar ou gerar PDF.
        """
        parent = getattr(self, "pdv_window", self)
        janela = ctk.CTkToplevel(parent)
        janela.title("Venda finalizada")
        janela.geometry("460x300")
        janela.resizable(False, False)
        janela.configure(fg_color="#0d1117")
        try:
            janela.transient(parent)
            janela.grab_set()
        except tk.TclError:
            pass

        ctk.CTkLabel(
            janela,
            text="☑ Venda finalizada",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#00FF88",
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            janela,
            text=f"Total: R$ {DecimalStorage.to_decimal(total, field='total da venda'):.2f}",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#ffffff",
        ).pack(pady=(0, 2))
        ctk.CTkLabel(
            janela,
            text="Deseja imprimir o cupom de 80 mm?",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#c9d1d9",
        ).pack(pady=(0, 16))

        resultado = {"acao": "FINALIZAR"}

        def fechar():
            try:
                janela.grab_release()
            except tk.TclError:
                pass
            try:
                janela.destroy()
            except tk.TclError:
                pass

        def imprimir():
            try:
                nome = self.imprimir_cupom_venda_80mm(
                    cliente_id, itens, total, tipo, documento_id
                )
                resultado["acao"] = "IMPRIMIR"
                self.mostrar_notificacao(
                    "Cupom enviado",
                    f"Cupom de 80 mm enviado para: {nome}",
                    nivel="success",
                )
            except Exception as exc:
                logger.exception("Falha ao imprimir o cupom de 80 mm", exc_info=exc)
                messagebox.showerror(
                    "Impressão",
                    f"Não foi possível imprimir o cupom:\n{exc}",
                    parent=janela,
                )
                return
            fechar()

        def gerar_pdf():
            try:
                caminho = self.gerar_pdf_venda(
                    cliente_id, itens, total, tipo, documento_id
                )
                self._abrir_arquivo_sistema(caminho)
                resultado["acao"] = "PDF"
            except Exception as exc:
                logger.exception("Falha ao gerar o PDF da venda", exc_info=exc)
                messagebox.showerror(
                    "PDF",
                    f"Não foi possível gerar o PDF:\n{exc}",
                    parent=janela,
                )
                return
            fechar()

        ctk.CTkButton(
            janela,
            text="▣   SIM — imprimir cupom 80 mm",
            height=48,
            fg_color="#2ea043",
            hover_color="#238636",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            command=imprimir,
        ).pack(fill="x", padx=24, pady=(0, 10))

        rodape = ctk.CTkFrame(janela, fg_color="transparent")
        rodape.pack(fill="x", padx=24, pady=(0, 20))
        ctk.CTkButton(
            rodape,
            text="☑ Finalizar",
            height=40,
            fg_color="#21262d",
            hover_color="#30363d",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            command=fechar,
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(
            rodape,
            text="▧ Gerar PDF",
            height=40,
            fg_color="#1f6feb",
            hover_color="#1158c7",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            command=gerar_pdf,
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

        janela.bind("<Return>", lambda _event: imprimir())
        janela.bind("<Escape>", lambda _event: fechar())
        try:
            janela.wait_window()
        except tk.TclError:
            pass
        return resultado["acao"]

    def emitir_venda_conforme_perfil(self, cliente_id, itens, total, tipo, documento_id=None):
        """Emite cupom, A4 ou PDF conforme a configuração escolhida."""
        categoria = "entrega" if tipo == "ENTREGA" else "recibo"
        perfil = self.formato_impressao(categoria)
        chave_impressora = "impressora_entrega" if categoria == "entrega" else "impressora_recibo"
        impressora = obter_config(chave_impressora) or "Padrão do Sistema"

        if perfil == "PDF virtual":
            caminho = self.gerar_pdf_venda(cliente_id, itens, total, tipo, documento_id)
            self.janela_acoes_pdf(caminho, categoria, tipo)
            return f"PDF gerado em:\n{caminho}"

        texto = self.texto_comprovante_venda(cliente_id, itens, total, tipo, documento_id)
        if perfil == "Cupom 80 mm":
            texto = self.ajustar_texto_cupom(texto, 42)
            nome = self.imprimir_texto_windows(texto, impressora, tipo)
            return f"Cupom de 80 mm enviado para:\n{nome}"

        nome = self.imprimir_texto_a4_windows(texto, impressora, tipo)
        return f"Documento A4 enviado para:\n{nome}"

    def janela_preview_documento(
        self,
        texto,
        categoria="recibo",
        titulo="Documento pronto",
        subtitulo="Pré-visualização do cupom",
        pdf_callback=None,
    ):
        """Janela única de impressão: prévia textual, cupom 80 mm e PDF sob demanda."""
        perfil = self.formato_impressao(categoria)
        chave_impressora = "impressora_historico" if categoria == "fechamento" else f"impressora_{categoria}"
        impressora = obter_config(chave_impressora) or "Padrão do Sistema"

        win = ctk.CTkToplevel(self)
        win.title(titulo)
        win.geometry("700x640")
        win.minsize(620, 540)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(
            win, text=titulo, font=ctk.CTkFont(size=21, weight="bold"), text_color="#00FF88"
        ).pack(pady=(18, 4))
        ctk.CTkLabel(
            win,
            text=f"Saída configurada: {perfil}  •  Impressora: {impressora}",
            text_color="#c9d1d9",
        ).pack(pady=(0, 10))

        preview_frame = ctk.CTkFrame(win, fg_color="#0d1117", corner_radius=10)
        preview_frame.pack(fill="both", expand=True, padx=22, pady=(4, 12))
        ctk.CTkLabel(
            preview_frame, text=subtitulo, font=ctk.CTkFont(size=14, weight="bold"), text_color="#58a6ff"
        ).pack(anchor="w", padx=14, pady=(10, 5))
        preview = ctk.CTkTextbox(
            preview_frame, wrap="none", font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#010409", text_color="#f0f6fc"
        )
        preview.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        preview.insert("1.0", texto)
        preview.configure(state="disabled")

        botoes = ctk.CTkFrame(win, fg_color="transparent")
        botoes.pack(fill="x", padx=22, pady=(0, 18))

        def imprimir():
            try:
                if perfil == "Cupom 80 mm":
                    nome = self.imprimir_texto_windows(
                        self.ajustar_texto_cupom(texto, 42), impressora, titulo
                    )
                else:
                    nome = self.imprimir_texto_a4_windows(texto, impressora, titulo)
                messagebox.showinfo("Impressão", f"Documento enviado para:\n{nome}", parent=win)
            except Exception as exc:
                logger.exception("Falha ao imprimir documento textual", exc_info=exc)
                messagebox.showerror("Impressão", f"Não foi possível imprimir o documento:\n{exc}", parent=win)

        def salvar_pdf():
            if pdf_callback is None:
                messagebox.showinfo("PDF", "PDF não disponível para este documento.", parent=win)
                return
            destino = filedialog.asksaveasfilename(
                parent=win, title="Salvar documento em PDF", defaultextension=".pdf",
                filetypes=[("Arquivo PDF", "*.pdf")], initialfile=f"{self._nome_pdf_seguro(titulo)}.pdf"
            )
            if not destino:
                return
            try:
                caminho = pdf_callback(destino)
                messagebox.showinfo("PDF", f"PDF salvo em:\n{caminho or destino}", parent=win)
            except Exception as exc:
                logger.exception("Falha ao salvar PDF sob demanda", exc_info=exc)
                messagebox.showerror("PDF", f"Não foi possível salvar o PDF:\n{exc}", parent=win)

        print_label = "Imprimir cupom 80 mm" if perfil == "Cupom 80 mm" else "Imprimir documento A4"
        ctk.CTkButton(
            botoes, text=print_label, fg_color="#2ea043", height=44, command=imprimir
        ).pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            botoes, text="Salvar PDF (opcional)", fg_color="#8957e5", height=40, command=salvar_pdf
        ).pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            botoes, text="Fechar", fg_color="#30363d", height=38, command=win.destroy
        ).pack(fill="x")
        return win

    def janela_recibo_pagamento_cliente(self, mov_id, alocacoes, saldo_anterior=None, novo_saldo=None):
        """Mostra o recibo textual e imprime cupom; PDF só é gerado sob demanda."""
        texto = self.texto_recibo_pagamento_cliente(
            mov_id,
            alocacoes,
            saldo_anterior=saldo_anterior,
            novo_saldo=novo_saldo,
        )
        perfil = self.formato_impressao("recibo")
        impressora = obter_config("impressora_recibo") or "Padrão do Sistema"

        win = ctk.CTkToplevel(self)
        win.title("Recibo de pagamento")
        win.geometry("700x640")
        win.minsize(620, 540)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(
            win,
            text="Pagamento registrado",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color="#00FF88",
        ).pack(pady=(18, 4))

        ctk.CTkLabel(
            win,
            text=f"Saída configurada: {perfil}  •  Impressora: {impressora}",
            text_color="#c9d1d9",
        ).pack(pady=(0, 10))

        preview_frame = ctk.CTkFrame(win, fg_color="#0d1117", corner_radius=10)
        preview_frame.pack(fill="both", expand=True, padx=22, pady=(4, 12))

        ctk.CTkLabel(
            preview_frame,
            text="Pré-visualização do cupom",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#58a6ff",
        ).pack(anchor="w", padx=14, pady=(10, 5))

        preview = ctk.CTkTextbox(
            preview_frame,
            wrap="none",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#010409",
            text_color="#f0f6fc",
        )
        preview.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        preview.insert("1.0", texto)
        preview.configure(state="disabled")

        botoes = ctk.CTkFrame(win, fg_color="transparent")
        botoes.pack(fill="x", padx=22, pady=(0, 18))

        def imprimir_cupom():
            try:
                if perfil == "Cupom 80 mm":
                    conteudo = self.ajustar_texto_cupom(texto, 42)
                    nome = self.imprimir_texto_windows(
                        conteudo, impressora, "Recibo de pagamento"
                    )
                else:
                    nome = self.imprimir_texto_a4_windows(
                        texto, impressora, "Recibo de pagamento"
                    )
                messagebox.showinfo(
                    "Impressão",
                    f"Recibo enviado para:\n{nome}",
                    parent=win,
                )
            except Exception as exc:
                logger.exception("Falha ao imprimir recibo textual", exc_info=exc)
                messagebox.showerror(
                    "Impressão",
                    f"Não foi possível imprimir o recibo:\n{exc}",
                    parent=win,
                )

        def salvar_pdf_sob_demanda():
            destino = filedialog.asksaveasfilename(
                parent=win,
                title="Salvar recibo em PDF",
                defaultextension=".pdf",
                filetypes=[("Arquivo PDF", "*.pdf")],
                initialfile=f"recibo_pagamento_{mov_id}.pdf",
            )
            if not destino:
                return
            try:
                caminho = self.gerar_pdf_pagamento_cliente(
                    mov_id,
                    alocacoes,
                    destino=destino,
                    saldo_anterior=saldo_anterior,
                    novo_saldo=novo_saldo,
                )
                messagebox.showinfo(
                    "PDF",
                    f"PDF salvo em:\n{caminho}",
                    parent=win,
                )
            except Exception as exc:
                logger.exception("Falha ao salvar PDF do recibo", exc_info=exc)
                messagebox.showerror(
                    "PDF",
                    f"Não foi possível salvar o PDF:\n{exc}",
                    parent=win,
                )

        rotulo = (
            "Imprimir cupom 80 mm"
            if perfil == "Cupom 80 mm"
            else "Imprimir recibo A4"
        )

        ctk.CTkButton(
            botoes,
            text=rotulo,
            command=imprimir_cupom,
            fg_color="#2ea043",
            hover_color="#238636",
            height=44,
            font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", pady=5)

        ctk.CTkButton(
            botoes,
            text="Salvar PDF (opcional)",
            command=salvar_pdf_sob_demanda,
            fg_color="#8957e5",
            hover_color="#6e40c9",
            height=40,
        ).pack(fill="x", pady=5)

        ctk.CTkButton(
            botoes,
            text="Fechar",
            command=win.destroy,
            fg_color="#30363d",
            height=38,
        ).pack(fill="x", pady=5)

    def ajustar_texto_cupom(self, texto, largura):
        return self._servico_impressao().wrap_receipt_text(texto, largura)

    def _abrir_arquivo_sistema(self, caminho):
        if not caminho:
            raise ValueError("O caminho do PDF não foi informado.")
        caminho = os.path.abspath(os.fspath(caminho))
        if not os.path.isfile(caminho):
            raise FileNotFoundError(f"O PDF não foi encontrado: {caminho}")
        if os.name == "nt":
            opener = getattr(self, "_windows_file_opener", None)
            if opener is None:
                opener = WindowsFileOpener()
                self._windows_file_opener = opener
            try:
                opener.open(caminho)
            except WindowsFileOpenError as exc:
                raise RuntimeError(
                    "O Windows não conseguiu abrir o PDF no aplicativo associado."
                ) from exc
        else:
            webbrowser.open(Path(caminho).as_uri())
        return caminho

    def _abrir_diretorio_sistema(self, caminho):
        caminho = os.path.abspath(os.fspath(caminho))
        os.makedirs(caminho, exist_ok=True)
        if os.name == "nt":
            opener = getattr(self, "_windows_file_opener", None)
            if opener is None:
                opener = WindowsFileOpener()
                self._windows_file_opener = opener
            try:
                opener.open_directory(caminho)
            except WindowsFileOpenError as exc:
                raise RuntimeError("O Windows não conseguiu abrir a pasta.") from exc
        else:
            subprocess.Popen(["xdg-open", caminho])
        return caminho

    def _nome_pdf_seguro(self, texto):
        return self._servico_pdf_documentos().safe_name(texto)

    def janela_acoes_pdf(self, caminho_pdf, categoria, titulo, forcar_pergunta=False):
        """Solicita uma ação para o PDF usando diálogo nativo do sistema.

        O diálogo nativo evita janelas CTk/Tk vazias em algumas combinações de
        Windows, DPI, tema e janela-pai.  Sim imprime, Não abre o PDF e Cancelar
        apenas encerra a ação.
        """
        if not caminho_pdf:
            raise ValueError("O gerador de PDF não retornou um arquivo válido.")
        caminho_pdf = os.path.abspath(os.fspath(caminho_pdf))
        if not os.path.isfile(caminho_pdf) or os.path.getsize(caminho_pdf) <= 0:
            raise FileNotFoundError(f"O PDF não foi encontrado ou está vazio: {caminho_pdf}")

        acao = "PERGUNTAR" if forcar_pergunta else (obter_config("impressao_acao_pos_pdf") or "PERGUNTAR")
        if acao == "IMPRIMIR":
            self.imprimir_pdf_configurado(categoria, caminho_pdf)
            return caminho_pdf
        if acao == "ABRIR":
            self._abrir_arquivo_sistema(caminho_pdf)
            return caminho_pdf
        if acao == "NADA":
            return caminho_pdf

        parent = self._parent_dialogo_ativo()
        resposta = messagebox.askyesnocancel(
            titulo or "Documento pronto",
            "O documento foi gerado com sucesso.\n\n"
            "Sim: imprimir o documento\n"
            "Não: abrir o PDF\n"
            "Cancelar: fechar sem imprimir",
            parent=parent,
        )
        if resposta is True:
            try:
                self.imprimir_pdf_configurado(categoria, caminho_pdf)
                self.mostrar_notificacao(
                    "Documento enviado",
                    "Documento enviado para impressão.",
                    nivel="success",
                )
            except Exception as exc:
                logger.exception("Falha ao imprimir PDF", exc_info=exc)
                messagebox.showerror("Impressão", str(exc), parent=parent)
        elif resposta is False:
            try:
                self._abrir_arquivo_sistema(caminho_pdf)
            except Exception as exc:
                logger.exception("Falha ao abrir PDF", exc_info=exc)
                messagebox.showerror("PDF", f"Não foi possível abrir o PDF:\n{exc}", parent=parent)
        return caminho_pdf

    def _parent_dialogo_ativo(self):
        """Retorna uma janela viva e visível para diálogos nativos."""
        candidatos = (
            getattr(self, "pdv_window", None),
            getattr(self, "janela_vendas", None),
            self,
        )
        for janela in candidatos:
            if janela is None:
                continue
            try:
                if janela.winfo_exists() and janela.winfo_viewable():
                    return janela
            except (AttributeError, tk.TclError):
                continue
        return self

    def imprimir_pdf_configurado(self, categoria, caminho_pdf):
        """Imprime PDF em processo externo, sem ``os.startfile(..., 'print')``."""
        chave = {
            "recibo": "impressora_recibo",
            "entrega": "impressora_entrega",
            "ficha": "impressora_ficha",
            "historico": "impressora_historico",
            "fechamento": "impressora_historico",
        }.get(categoria, "impressora_recibo")
        impressora = obter_config(chave) or "Padrão do Sistema"
        caminho_pdf = os.path.abspath(os.fspath(caminho_pdf))
        printer = getattr(self, "_windows_pdf_printer", None)
        if printer is None:
            printer = WindowsPDFPrinter()
            self._windows_pdf_printer = printer
        try:
            return printer.print(caminho_pdf, impressora)
        except WindowsPDFPrintError as exc:
            try:
                self._abrir_arquivo_sistema(caminho_pdf)
            except Exception:
                pass
            raise RuntimeError(
                "O Windows não aceitou a impressão automática do PDF.\n"
                "O arquivo foi aberto; pressione Ctrl+P para imprimir manualmente."
            ) from exc

    def abrir_configuracao_modelos_impressao(self):
        win=ctk.CTkToplevel(self); win.title("NabiCode — Modelos e personalização de impressão"); win.geometry("900x720"); win.minsize(820,650); win.transient(self); win.grab_set()
        abas=ctk.CTkTabview(win); abas.pack(fill="both",expand=True,padx=15,pady=15)
        geral=abas.add("Aparência"); docs=abas.add("Documentos"); teste=abas.add("Prévia e teste")
        campos={}
        def entrada(parent,rotulo,chave,valores=None):
            linha=ctk.CTkFrame(parent,fg_color="transparent"); linha.pack(fill="x",padx=14,pady=5)
            ctk.CTkLabel(linha,text=rotulo,width=260,anchor="w").pack(side="left")
            w=ctk.CTkComboBox(linha,values=valores,state="readonly") if valores else ctk.CTkEntry(linha)
            w.pack(side="left",fill="x",expand=True); w.set(obter_config(chave)) if valores else w.insert(0,obter_config(chave)); campos[chave]=w
        entrada(geral,"Modelo visual do cupom:","modelo_cupom_visual",ReceiptTemplateService.names())
        entrada(geral,"Fonte:","impressao_fonte",["Helvetica","Times-Roman","Courier"])
        entrada(geral,"Tamanho da fonte:","impressao_fonte_tamanho")
        bools={}
        ctk.CTkLabel(geral,text="Escolha um dos 20 modelos prontos. Só fonte e tamanho precisam de ajuste.",text_color="#8b949e",wraplength=700).pack(padx=18,pady=18)
        modelos=["A4","Térmica 80 mm"]
        for rotulo,cat in [("Recibo / venda","recibo"),("Entrega","entrega"),("Ficha do cliente","ficha"),("Histórico","historico"),("Fechamento de caixa","fechamento")]: entrada(docs,f"Modelo para {rotulo}:",f"modelo_{cat}",modelos)
        entrada(docs,"Após gerar PDF:","impressao_acao_pos_pdf",["PERGUNTAR","ABRIR","IMPRIMIR","NADA"])
        ctk.CTkLabel(docs,text="A4: relatórios completos. 80 mm: formato térmico oficial.",text_color="#8b949e").pack(pady=15)
        preview=ctk.CTkTextbox(teste); preview.pack(fill="both",expand=True,padx=12,pady=12)
        def salvar_tudo():
            for chave,w in campos.items(): salvar_config(chave,w.get().strip())
            for chave,v in bools.items(): salvar_config(chave,"1" if v.get() else "0")
            messagebox.showinfo("Impressão","Modelos de impressão salvos.",parent=win)
        def previsualizar():
            salvar_tudo(); dados=self._dados_loja_impressao(); texto=f"{dados['nome']}\nCOMPROVANTE DE VENDA\n{'='*42}\nData: {datetime.now():%d/%m/%Y %H:%M}\nCliente: CLIENTE DE TESTE\n{'-'*42}\n1x Produto de demonstração\nR$ 100,00\n{'-'*42}\nTOTAL: R$ 100,00\n{'='*42}\n{obter_config('rodape_cupom')}"; preview.delete("1.0","end"); preview.insert("end",ReceiptTemplateService.render(texto,campos['modelo_cupom_visual'].get()))
        def pdf_teste():
            salvar_tudo(); caminho=self.gerar_pdf_venda(None,[{"qtd":1,"item":"Produto de demonstração","preco":100.0,"subtotal":100.0}],100.0,"COMPROVANTE"); self.janela_acoes_pdf(caminho,"recibo","Teste")
        barra=ctk.CTkFrame(teste,fg_color="transparent"); barra.pack(fill="x",padx=12,pady=(0,12))
        ctk.CTkButton(barra,text="Atualizar prévia",command=previsualizar).pack(side="left",expand=True,fill="x",padx=4)
        ctk.CTkButton(barra,text="Gerar PDF de teste",command=pdf_teste,fg_color="#2ea043").pack(side="left",expand=True,fill="x",padx=4)
        ctk.CTkButton(win,text="💾 Salvar configurações",command=salvar_tudo,fg_color="#8957e5",height=42).pack(fill="x",padx=20,pady=(0,15))
        previsualizar()

    def _escolher_logo(self, entry, parent):
        caminho=filedialog.askopenfilename(parent=parent,title="Selecionar logotipo",filetypes=[("Imagens","*.png;*.jpg;*.jpeg"),("Todos","*.*")])
        if caminho: entry.delete(0,"end"); entry.insert(0,caminho)

    def imprimir_documento_configurado(self, categoria, texto, titulo):
        chave = {
            "recibo": "impressora_recibo",
            "entrega": "impressora_entrega",
            "ficha": "impressora_ficha",
            "historico": "impressora_historico",
            "fechamento": "impressora_historico",
        }.get(categoria, "impressora_recibo")
        impressora = obter_config(chave) or "Padrão do Sistema"
        formato = self.formato_impressao(categoria)

        if formato == "PDF virtual":
            raise RuntimeError("Este documento está configurado como PDF virtual. Use a opção de gerar/salvar PDF.")
        if not self.impressora_disponivel(impressora):
            raise RuntimeError(f"A impressora configurada para {categoria} não está disponível: {impressora}")
        if formato == "A4":
            return self.imprimir_texto_a4_windows(texto, impressora, titulo)

        largura = 42
        return self.imprimir_texto_windows(self.ajustar_texto_cupom(texto, largura), impressora, titulo)

    def abrir_configuracao_impressoras(self):
        janela = ctk.CTkToplevel(self)
        janela.title("NabiCode — Impressoras e formatos")
        janela.geometry("900x650")
        janela.resizable(False, False)
        janela.configure(fg_color="#0d1117")
        janela.transient(self)
        janela.grab_set()

        ctk.CTkLabel(
            janela, text="🖨️ Impressoras e formatos de saída",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="#00FF88"
        ).pack(pady=(20, 5))
        ctk.CTkLabel(
            janela,
            text="Cupom imprime direto na térmica. A4 imprime direto na impressora comum. "
                 "PDF virtual só gera arquivo quando solicitado.",
            text_color="#c9d1d9", wraplength=820, justify="center"
        ).pack(pady=(0, 15))

        impressoras = self.listar_impressoras_windows()
        formatos = ["Cupom 80 mm", "A4", "PDF virtual"]
        campos_impressora = {}
        campos_formato = {}

        opcoes = [
            ("Recibo / comprovante", "impressora_recibo", "recibo"),
            ("Cupom de entrega", "impressora_entrega", "entrega"),
            ("Ficha do cliente", "impressora_ficha", "ficha"),
            ("Histórico do cliente", "impressora_historico", "historico"),
            ("Fechamento de caixa", "impressora_historico", "fechamento"),
        ]

        corpo = ctk.CTkScrollableFrame(janela, fg_color="#161b22", corner_radius=12)
        corpo.pack(fill="both", expand=True, padx=22, pady=8)

        cab = ctk.CTkFrame(corpo, fg_color="transparent")
        cab.pack(fill="x", padx=14, pady=(5, 2))
        ctk.CTkLabel(cab, text="Documento", width=180, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(cab, text="Formato", width=170, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=6)
        ctk.CTkLabel(cab, text="Impressora", width=300, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=6)

        for rotulo, chave, categoria in opcoes:
            linha = ctk.CTkFrame(corpo, fg_color="transparent")
            linha.pack(fill="x", padx=14, pady=8)

            ctk.CTkLabel(linha, text=rotulo, width=180, anchor="w").pack(side="left")

            combo_formato = ctk.CTkComboBox(linha, values=formatos, width=170, height=34, state="readonly")
            combo_formato.set(self.formato_impressao(categoria))
            combo_formato.pack(side="left", padx=6)
            campos_formato[categoria] = combo_formato

            combo = ctk.CTkComboBox(linha, values=impressoras, width=300, height=34)
            atual = obter_config(chave) or "Padrão do Sistema"
            combo.set(atual)
            combo.pack(side="left", padx=6)
            campos_impressora[categoria] = (chave, combo)

            def testar(cat=categoria, cb_imp=combo, cb_fmt=combo_formato, nome_rotulo=rotulo):
                nome = cb_imp.get().strip() or "Padrão do Sistema"
                formato = cb_fmt.get().strip()
                loja = obter_config("nome_loja") or "Nome da Loja"
                texto = (
                    f"{loja}\nTESTE DE IMPRESSAO\n{'='*42}\n"
                    f"Documento: {nome_rotulo}\n"
                    f"Formato: {formato}\n"
                    f"Data: {datetime.now():%d/%m/%Y %H:%M:%S}\n"
                    "Produto de teste ........ R$ 10,00\n"
                    "TOTAL ................... R$ 10,00\n\n"
                )
                try:
                    if formato == "PDF virtual":
                        caminho = self.gerar_pdf_venda(
                            None,
                            [{"qtd": 1, "item": "Produto de teste", "preco": 10.0, "subtotal": 10.0}],
                            10.0, "COMPROVANTE"
                        )
                        self.janela_acoes_pdf(caminho, "recibo", "Teste")
                        return
                    if formato == "A4":
                        usado = self.imprimir_texto_a4_windows(texto, nome, "Teste A4")
                    else:
                        largura = 32 if "58" in formato else 42
                        usado = self.imprimir_texto_windows(self.ajustar_texto_cupom(texto, largura), nome, "Teste Cupom")
                    messagebox.showinfo("Teste de impressão", f"Teste enviado para:\n{usado}", parent=janela)
                except Exception as exc:
                    messagebox.showerror("Teste de impressão", str(exc), parent=janela)

            ctk.CTkButton(linha, text="Testar", width=90, height=34, command=testar).pack(side="left", padx=(6, 0))

        status = ctk.CTkLabel(
            corpo,
            text=f"{max(0, len(impressoras)-1)} impressora(s) detectada(s) no Windows.",
            text_color="#8b949e"
        )
        status.pack(pady=(8, 4))

        corte_frame = ctk.CTkFrame(corpo, fg_color="#0d1117", corner_radius=10)
        corte_frame.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(
            corte_frame, text="Corte automático da impressora térmica",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#58a6ff"
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 7))
        corte_ativo_var = tk.BooleanVar(
            value=str(obter_config("impressao_corte_automatico") or "1").strip() != "0"
        )
        ctk.CTkCheckBox(
            corte_frame, text="Cortar o cupom após imprimir", variable=corte_ativo_var
        ).grid(row=1, column=0, sticky="w", padx=14, pady=8)
        ctk.CTkLabel(corte_frame, text="Tipo").grid(row=1, column=1, sticky="e", padx=(12, 4))
        corte_tipo = ctk.CTkComboBox(
            corte_frame, values=["PARCIAL", "TOTAL"], width=125, state="readonly"
        )
        corte_tipo.set((obter_config("impressao_tipo_corte") or "PARCIAL").upper())
        corte_tipo.grid(row=1, column=2, sticky="w", padx=4)
        ctk.CTkLabel(corte_frame, text="Linhas antes do corte").grid(row=1, column=3, sticky="e", padx=(12, 4))
        corte_linhas = ctk.CTkEntry(corte_frame, width=70)
        corte_linhas.insert(0, obter_config("impressao_linhas_antes_corte") or "4")
        corte_linhas.grid(row=1, column=4, sticky="w", padx=(4, 14), pady=8)
        ctk.CTkLabel(
            corte_frame,
            text="Funciona em térmicas com guilhotina e protocolo ESC/POS. "
                 "Se o modelo não aceitar o comando, a impressão continua normalmente.",
            text_color="#8b949e", wraplength=760, justify="left"
        ).grid(row=2, column=0, columnspan=5, sticky="w", padx=14, pady=(2, 12))

        def atualizar_lista():
            novas = self.listar_impressoras_windows()
            for _, combo in campos_impressora.values():
                combo.configure(values=novas)
            status.configure(text=f"{max(0, len(novas)-1)} impressora(s) detectada(s) no Windows.")

        def salvar():
            ausentes = []
            disponiveis = self.listar_impressoras_windows()
            for categoria, (chave, combo) in campos_impressora.items():
                nome = combo.get().strip() or "Padrão do Sistema"
                formato = campos_formato[categoria].get().strip()
                salvar_config(chave, nome)
                salvar_config(f"formato_impressao_{categoria}", formato)
                if formato != "PDF virtual" and nome != "Padrão do Sistema" and nome not in disponiveis:
                    ausentes.append(nome)

            try:
                linhas_corte = max(0, min(12, int(corte_linhas.get().strip() or "4")))
            except ValueError:
                messagebox.showwarning(
                    "Corte automático", "Informe de 0 a 12 linhas antes do corte.", parent=janela
                )
                return
            salvar_config("impressao_corte_automatico", "1" if corte_ativo_var.get() else "0")
            salvar_config("impressao_tipo_corte", corte_tipo.get().strip().upper() or "PARCIAL")
            salvar_config("impressao_linhas_antes_corte", str(linhas_corte))

            if ausentes:
                messagebox.showwarning(
                    "Configurações salvas",
                    "As configurações foram salvas, mas estas impressoras não foram encontradas:\n\n"
                    + "\n".join(sorted(set(ausentes))),
                    parent=janela
                )
            else:
                messagebox.showinfo(
                    "Impressão",
                    "Impressoras e formatos salvos com sucesso.",
                    parent=janela
                )
            janela.destroy()

        botoes = ctk.CTkFrame(janela, fg_color="transparent")
        botoes.pack(fill="x", padx=22, pady=(4, 18))
        ctk.CTkButton(
            botoes, text="🔄 Atualizar lista", command=atualizar_lista, fg_color="#1f6feb"
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(
            botoes, text="💾 Salvar configurações", command=salvar, fg_color="#2ea043"
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))


    def tela_compras(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="#0d1117")
        frame.grid(row=0, column=0, sticky="nsew")

        cabecalho = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=10)
        cabecalho.pack(fill="x", padx=20, pady=(18, 8))
        ctk.CTkLabel(cabecalho, text="Compras", font=ctk.CTkFont(size=24, weight="bold"), text_color="#ffffff").pack(side="left", padx=16, pady=12)

        corpo_scroll = BidirectionalScrollableFrame(frame, fg_color="transparent", content_width=1180)
        corpo_scroll.pack(fill="both", expand=True, padx=20, pady=4)
        corpo = corpo_scroll.content

        filtros = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=10)
        filtros.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(filtros, text="Status", text_color="#ffffff").pack(side="left", padx=(12, 4), pady=10)
        self.compra_status = ctk.CTkComboBox(filtros, values=["TODOS", "ABERTO", "PARCIAL", "RECEBIDO"], width=150, state="readonly")
        self.compra_status.set("TODOS")
        self.compra_status.pack(side="left", padx=4, pady=10)
        ctk.CTkButton(filtros, text="Atualizar", width=110, command=self.carregar_compras).pack(side="left", padx=8, pady=10)

        tabela_frame = ctk.CTkFrame(corpo, fg_color="#161b22", corner_radius=10)
        tabela_frame.pack(fill="both", expand=True)
        colunas = ("id", "status", "fornecedor", "criado", "valor", "pendente", "usuario")
        self.tabela_compras = ttk.Treeview(tabela_frame, columns=colunas, show="headings", height=18)
        titulos = {"id":"ID", "status":"Status", "fornecedor":"Fornecedor", "criado":"Criado em", "valor":"Valor", "pendente":"Qtd. pendente", "usuario":"Usuário"}
        larguras = {"id":65,"status":100,"fornecedor":260,"criado":150,"valor":120,"pendente":120,"usuario":130}
        for coluna in colunas:
            self.tabela_compras.heading(coluna, text=titulos[coluna])
            self.tabela_compras.column(coluna, width=larguras[coluna], minwidth=60, anchor="w")
        barra_y = ttk.Scrollbar(tabela_frame, orient="vertical", command=self.tabela_compras.yview)
        barra_x = ttk.Scrollbar(tabela_frame, orient="horizontal", command=self.tabela_compras.xview)
        self.tabela_compras.configure(yscrollcommand=barra_y.set, xscrollcommand=barra_x.set)
        self.tabela_compras.grid(row=0, column=0, sticky="nsew", padx=(10,0), pady=(10,0))
        barra_y.grid(row=0, column=1, sticky="ns", pady=(10,0))
        barra_x.grid(row=1, column=0, sticky="ew", padx=(10,0), pady=(0,10))
        tabela_frame.grid_rowconfigure(0, weight=1)
        tabela_frame.grid_columnconfigure(0, weight=1)
        self.tabela_compras.bind("<Double-1>", lambda _e: self.abrir_detalhes_compra())

        rodape = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=10)
        rodape.pack(fill="x", padx=20, pady=(8, 18))
        ctk.CTkButton(rodape, text="Novo pedido", command=self.novo_pedido_compra).pack(side="left", padx=10, pady=10)
        ctk.CTkButton(rodape, text="Fornecedores", command=self.abrir_fornecedores_compras).pack(side="left", padx=4, pady=10)
        ctk.CTkButton(rodape, text="Receber", command=self.receber_pedido_compra).pack(side="left", padx=4, pady=10)
        ctk.CTkButton(rodape, text="Detalhes", command=self.abrir_detalhes_compra).pack(side="left", padx=4, pady=10)
        return frame

    def carregar_compras(self):
        if not hasattr(self, "tabela_compras"):
            return
        status = self.compra_status.get().strip().upper()
        pedidos = COMPRA_SERVICE.repository.listar_pedidos(None if status == "TODOS" else status)
        for item in self.tabela_compras.get_children():
            self.tabela_compras.delete(item)
        for pedido in pedidos:
            self.tabela_compras.insert("", "end", iid=str(pedido["id"]), values=(
                pedido["id"], pedido["status"], pedido.get("fornecedor_nome") or "",
                pedido.get("criado_em") or "", f"R$ {float(pedido.get('valor_total') or 0):.2f}",
                f"{float(pedido.get('quantidade_pendente') or 0):g}", pedido.get("usuario") or "",
            ))

    def _pedido_compra_selecionado(self):
        selecao = self.tabela_compras.selection() if hasattr(self, "tabela_compras") else ()
        if not selecao:
            messagebox.showwarning("Compras", "Selecione um pedido.", parent=self)
            return None
        return int(selecao[0])

    def novo_pedido_compra(self):
        if not self._autorizar("compras", "create"):
            return
        fornecedores = COMPRA_SERVICE.repository.listar_fornecedores()
        produtos = COMPRA_SERVICE.repository.listar_produtos_compra()
        if not fornecedores:
            abrir = messagebox.askyesno(
                "Compras",
                "Nenhum fornecedor ativo foi encontrado.\n\nDeseja cadastrar um fornecedor agora?",
                parent=self,
            )
            if abrir:
                self.abrir_fornecedores_compras(retomar_pedido=True)
            return
        if not produtos:
            messagebox.showwarning("Compras", "Cadastre um produto ativo que controle estoque.", parent=self)
            return
        janela = ctk.CTkToplevel(self)
        janela.title("Novo pedido de compra")
        metricas = UniversalLayoutPolicy.metrics(
            janela.winfo_screenwidth(), janela.winfo_screenheight(),
            preferred_width=980, preferred_height=650,
        )
        janela.geometry(UniversalLayoutPolicy.geometry(metricas))
        janela.minsize(*UniversalLayoutPolicy.safe_minsize(metricas))
        janela.transient(self)
        janela.grab_set()
        cab = ctk.CTkFrame(janela, fg_color="#161b22")
        cab.pack(fill="x", padx=12, pady=(12,6))
        ctk.CTkLabel(cab, text="Novo pedido de compra", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=12, pady=10)
        corpo_scroll = BidirectionalScrollableFrame(janela, fg_color="#161b22", content_width=900)
        corpo_scroll.pack(fill="both", expand=True, padx=12, pady=6)
        corpo = corpo_scroll.content
        mapa_fornecedor = {f"{f['id']} - {f.get('nome_fantasia') or f.get('razao_social') or ''}": f for f in fornecedores}
        mapa_produto = {f"{p['codigo']} - {p['nome']}": p for p in produtos}
        ctk.CTkLabel(corpo, text="Fornecedor").grid(row=0,column=0,sticky="w",padx=10,pady=(10,2))
        fornecedor_combo = ctk.CTkComboBox(corpo, values=list(mapa_fornecedor), width=420, state="readonly")
        fornecedor_combo.grid(row=1,column=0,columnspan=3,sticky="ew",padx=10,pady=(0,8)); fornecedor_combo.set(next(iter(mapa_fornecedor)))
        ctk.CTkLabel(corpo, text="Produto").grid(row=2,column=0,sticky="w",padx=10,pady=(8,2))
        produto_combo = ctk.CTkComboBox(corpo, values=list(mapa_produto), width=420, state="readonly")
        produto_combo.grid(row=3,column=0,sticky="ew",padx=10,pady=(0,8)); produto_combo.set(next(iter(mapa_produto)))
        ctk.CTkLabel(corpo, text="Quantidade").grid(row=2,column=1,sticky="w",padx=10,pady=(8,2))
        quantidade_entry = ctk.CTkEntry(corpo); quantidade_entry.grid(row=3,column=1,sticky="ew",padx=10,pady=(0,8)); quantidade_entry.insert(0,"1")
        ctk.CTkLabel(corpo, text="Custo unitário").grid(row=2,column=2,sticky="w",padx=10,pady=(8,2))
        custo_entry = ctk.CTkEntry(corpo); custo_entry.grid(row=3,column=2,sticky="ew",padx=10,pady=(0,8)); custo_entry.insert(0,"0,00")
        itens = []
        tabela = ttk.Treeview(corpo, columns=("produto","qtd","custo","total"), show="headings", height=12)
        for c,t,w in (("produto","Produto",420),("qtd","Quantidade",110),("custo","Custo",110),("total","Total",120)):
            tabela.heading(c,text=t); tabela.column(c,width=w,anchor="w")
        tabela.grid(row=5,column=0,columnspan=3,sticky="nsew",padx=10,pady=10)
        corpo.grid_columnconfigure(0, weight=3); corpo.grid_columnconfigure(1, weight=1); corpo.grid_columnconfigure(2, weight=1); corpo.grid_rowconfigure(5, weight=1)
        def adicionar():
            try:
                produto = mapa_produto[produto_combo.get()]
                qtd = tratar_numero(quantidade_entry.get()); custo = tratar_numero(custo_entry.get())
                if qtd <= 0 or custo < 0: raise ValueError("Quantidade deve ser positiva e custo não pode ser negativo.")
                item={"produto_id":produto["id"],"quantidade":qtd,"custo_unitario":custo}
                itens.append(item)
                tabela.insert("","end",values=(f"{produto['codigo']} - {produto['nome']}",f"{qtd:g}",f"R$ {custo:.2f}",f"R$ {qtd*custo:.2f}"))
            except (ValueError, KeyError) as exc: messagebox.showerror("Compras", str(exc), parent=janela)
        ctk.CTkButton(corpo,text="Adicionar item",command=adicionar).grid(row=4,column=0,sticky="w",padx=10,pady=4)
        rod = ctk.CTkFrame(janela,fg_color="#161b22"); rod.pack(fill="x",padx=12,pady=(6,12))
        def salvar():
            try:
                fornecedor = mapa_fornecedor[fornecedor_combo.get()]
                pedido_id = COMPRA_SERVICE.criar_pedido(fornecedor["id"], itens, usuario=self._usuario_financeiro())
                janela.destroy(); self.carregar_compras(); self.mostrar_notificacao("Pedido criado", f"Pedido #{pedido_id} criado com sucesso.")
            except (ValueError, KeyError) as exc: messagebox.showerror("Compras", str(exc), parent=janela)
        ctk.CTkButton(rod,text="Cancelar",fg_color="#6b7280",command=janela.destroy).pack(side="right",padx=6,pady=10)
        ctk.CTkButton(rod,text="Salvar pedido",command=salvar).pack(side="right",padx=6,pady=10)
        janela.bind("<Control-s>",lambda _e: salvar()); janela.bind("<Escape>",lambda _e: janela.destroy())

    def abrir_fornecedores_compras(self, retomar_pedido=False):
        if not self._autorizar("compras", "create"):
            return

        def ao_fechar():
            if retomar_pedido and COMPRA_SERVICE.repository.listar_fornecedores():
                self.novo_pedido_compra()

        self.abrir_cadastros_auxiliares("fornecedor", ao_fechar=ao_fechar)

    def receber_pedido_compra(self):
        if not self._autorizar("compras", "receive"):
            return
        pedido_id = self._pedido_compra_selecionado()
        if pedido_id is None: return
        pedido = COMPRA_SERVICE.repository.obter_pedido(pedido_id)
        pendentes = [i for i in pedido["itens"] if float(i["quantidade_pendente"]) > 0]
        if not pendentes:
            messagebox.showinfo("Compras", "O pedido não possui itens pendentes.", parent=self); return
        documento = simpledialog.askstring("Recebimento", "Documento/NF:", parent=self) or ""
        gerar = messagebox.askyesno("Recebimento", "Gerar conta a pagar?", parent=self)
        vencimento = None
        if gerar:
            vencimento = simpledialog.askstring("Recebimento", "Vencimento da conta (AAAA-MM-DD):", parent=self)
            if vencimento is None: return
        itens=[]
        for item in pendentes:
            qtd = simpledialog.askfloat("Recebimento", f"{item['codigo']} - {item['nome']}\nPendente: {float(item['quantidade_pendente']):g}\nQuantidade recebida:", initialvalue=float(item["quantidade_pendente"]), minvalue=0.0, maxvalue=float(item["quantidade_pendente"]), parent=self)
            if qtd is None: return
            if qtd > 0:
                custo = simpledialog.askfloat("Recebimento", "Custo unitário:", initialvalue=float(item["custo_unitario"]), minvalue=0.0, parent=self)
                if custo is None: return
                itens.append({"pedido_item_id":item["id"],"quantidade":qtd,"custo_unitario":custo})
        try:
            resultado = COMPRA_SERVICE.receber(pedido_id,itens,documento=documento,usuario=self._usuario_financeiro(),gerar_conta_pagar=gerar,data_vencimento=vencimento)
            self.carregar_compras(); self.mostrar_notificacao("Compra recebida", f"Recebimento #{resultado.recebimento_id} concluído.")
        except ValueError as exc: messagebox.showerror("Compras", str(exc), parent=self)

    def abrir_detalhes_compra(self):
        pedido_id = self._pedido_compra_selecionado()
        if pedido_id is None: return
        pedido = COMPRA_SERVICE.repository.obter_pedido(pedido_id)
        linhas=[f"Pedido #{pedido['id']} | {pedido['status']}",f"Fornecedor: {pedido.get('fornecedor_nome') or ''}",f"Criado em: {pedido.get('criado_em') or ''}",""]
        for item in pedido["itens"]:
            linhas.append(f"{item['codigo']} - {item['nome']} | pedido {float(item['quantidade_pedida']):g} | recebido {float(item['quantidade_recebida']):g} | pendente {float(item['quantidade_pendente']):g} | custo R$ {float(item['custo_unitario']):.2f}")
        messagebox.showinfo("Detalhes da compra", "\n".join(linhas), parent=self)

    def tela_relatorios(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="#0d1117")
        frame.grid(row=0, column=0, sticky="nsew")
        cabecalho = ctk.CTkFrame(frame, fg_color="transparent")
        cabecalho.pack(fill="x", padx=20, pady=(18, 8))
        ctk.CTkLabel(cabecalho, text="📈 Relatórios e indicadores", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        self.rel_indicadores = ctk.CTkLabel(cabecalho, text="", text_color="#8b949e")
        self.rel_indicadores.pack(side="right")

        filtros = ctk.CTkFrame(frame, fg_color="#161b22")
        filtros.pack(fill="x", padx=20, pady=6)
        relatorios = self._relatorios_permitidos()
        valores_relatorios = list(relatorios) or [""]
        self.rel_tipo = ctk.CTkComboBox(filtros, values=valores_relatorios, width=150)
        self.rel_tipo.set(valores_relatorios[0])
        self.rel_tipo.pack(side="left", padx=6, pady=10)
        self.rel_inicio = ctk.CTkEntry(filtros, placeholder_text="Início AAAA-MM-DD", width=145)
        self.rel_inicio.pack(side="left", padx=6)
        self.rel_fim = ctk.CTkEntry(filtros, placeholder_text="Fim AAAA-MM-DD", width=145)
        self.rel_fim.pack(side="left", padx=6)
        self.rel_busca = ctk.CTkEntry(filtros, placeholder_text="Pesquisar", width=160)
        self.rel_busca.pack(side="left", padx=6)
        SearchEntryBehavior.attach(
            self.rel_busca, on_enter=self.gerar_relatorio_ui
        )
        self.rel_status = ctk.CTkEntry(filtros, placeholder_text="Status", width=110)
        self.rel_status.pack(side="left", padx=6)
        self.rel_usuario = ctk.CTkEntry(filtros, placeholder_text="Usuário", width=110)
        self.rel_usuario.pack(side="left", padx=6)
        ctk.CTkButton(filtros, text="Gerar", width=85, command=self.gerar_relatorio_ui).pack(side="left", padx=6)

        table_frame = ctk.CTkFrame(frame, fg_color="#161b22")
        table_frame.pack(fill="both", expand=True, padx=20, pady=8)
        self.rel_tabela = ttk.Treeview(table_frame, show="headings")
        sy = ttk.Scrollbar(table_frame, orient="vertical", command=self.rel_tabela.yview)
        sx = ttk.Scrollbar(table_frame, orient="horizontal", command=self.rel_tabela.xview)
        self.rel_tabela.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.rel_tabela.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        rodape = ctk.CTkFrame(frame, fg_color="transparent")
        rodape.pack(fill="x", padx=20, pady=(4, 16))
        for texto, formato in (("CSV", "CSV"), ("Excel", "XLSX"), ("PDF", "PDF")):
            ctk.CTkButton(rodape, text=texto, width=95, command=lambda f=formato: self.exportar_relatorio_ui(f)).pack(side="left", padx=4)
        ctk.CTkButton(rodape, text="Imprimir", width=95, command=self.imprimir_relatorio_ui).pack(side="left", padx=4)
        ctk.CTkButton(rodape, text="Gráfico / Dashboard", width=145, fg_color="#30363d", command=self.abrir_dashboard_relatorios).pack(side="left", padx=4)
        ctk.CTkButton(rodape, text="Indicadores", width=105, fg_color="#30363d", command=self.abrir_indicadores_personalizados).pack(side="left", padx=4)
        ctk.CTkButton(rodape, text="Histórico", width=100, fg_color="#30363d", command=self.abrir_historico_relatorios).pack(side="right", padx=4)
        ctk.CTkButton(rodape, text="Agendamentos", width=115, fg_color="#30363d", command=self.abrir_agendamentos_relatorios).pack(side="right", padx=4)
        return frame

    def _gerar_relatorio_por_enter(self):
        self.gerar_relatorio_ui()
        return SearchEntryBehavior.consume_enter()

    def gerar_relatorio_ui(self):
        if not hasattr(self, "rel_tipo"):
            return
        try:
            result = REPORT_SERVICE.generate(
                self.rel_tipo.get(), start_date=self.rel_inicio.get(), end_date=self.rel_fim.get(),
                search=self.rel_busca.get(), status=self.rel_status.get(), user=self.rel_usuario.get(),
                actor=self._usuario_relatorios(),
            )
            self._relatorio_atual = result
            self.rel_tabela.delete(*self.rel_tabela.get_children())
            self.rel_tabela["columns"] = result.columns
            for column in result.columns:
                self.rel_tabela.heading(column, text=column.replace("_", " ").title())
                self.rel_tabela.column(column, width=130, minwidth=80, stretch=True)
            for index, row in enumerate(result.rows):
                self.rel_tabela.insert("", "end", iid=str(index), values=row)
            indicators = REPORT_SERVICE.indicators(start_date=self.rel_inicio.get(), end_date=self.rel_fim.get())
            self.rel_indicadores.configure(text=f"Vendas R$ {indicators['vendas_total']:.2f} • A receber R$ {indicators['receber_aberto']:.2f} • Estoque baixo {indicators['estoque_baixo']}")
        except Exception as exc:
            messagebox.showerror("Relatórios", str(exc), parent=self)

    def exportar_relatorio_ui(self, formato):
        result = getattr(self, "_relatorio_atual", None)
        if not result:
            self.gerar_relatorio_ui(); result = getattr(self, "_relatorio_atual", None)
        if not result:
            return
        ext = {"CSV": ".csv", "XLSX": ".xlsx", "PDF": ".pdf"}[formato]
        destino = filedialog.asksaveasfilename(parent=self, defaultextension=ext, initialfile=f"{result.report_id}{ext}")
        if not destino:
            return
        try:
            caminho = REPORT_SERVICE.export(result, formato, destino, actor=self._usuario_relatorios())
            self.mostrar_notificacao("Relatório exportado", caminho.name, nivel="success")
        except Exception as exc:
            messagebox.showerror("Exportação", str(exc), parent=self)

    def imprimir_relatorio_ui(self):
        result = getattr(self, "_relatorio_atual", None)
        if not result:
            self.gerar_relatorio_ui()
            result = getattr(self, "_relatorio_atual", None)
        if not result:
            return
        try:
            caminho = REPORT_SERVICE.print_pdf(result, actor=self._usuario_relatorios(), dispatch=True)
            self.mostrar_notificacao("Relatório enviado para impressão", caminho.name, nivel="success")
        except Exception as exc:
            messagebox.showerror("Impressão", str(exc), parent=self)

    def abrir_indicadores_personalizados(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Indicadores personalizados")
        janela.geometry("900x520")
        janela.transient(self)
        tabela = ttk.Treeview(janela, columns=("nome", "relatorio", "agregacao", "coluna", "valor", "ativo"), show="headings")
        for col in tabela["columns"]:
            tabela.heading(col, text=col.title())
        tabela.pack(fill="both", expand=True, padx=15, pady=15)

        def carregar():
            tabela.delete(*tabela.get_children())
            valores = {str(row.get("name")): row for row in REPORT_SERVICE.evaluate_custom_indicators(start_date=self.rel_inicio.get(), end_date=self.rel_fim.get())}
            for row in REPORT_SERVICE.list_custom_indicators():
                atual = valores.get(str(row.get("name")), {})
                tabela.insert("", "end", iid=str(row["name"]), values=(row["name"], row["report_id"], row["aggregation"], row.get("column", ""), atual.get("value", ""), "SIM" if row.get("active", True) else "NÃO"))

        def novo():
            nome = simpledialog.askstring("Indicador", "Nome:", parent=janela)
            if not nome:
                return
            relatorio = simpledialog.askstring("Indicador", "Relatório: " + ", ".join(REPORT_SERVICE.available_reports()), initialvalue="vendas", parent=janela)
            agregacao = simpledialog.askstring("Indicador", "Agregação: COUNT, SUM, AVG, MIN ou MAX", initialvalue="COUNT", parent=janela)
            coluna = ""
            if str(agregacao or "").upper() != "COUNT":
                try:
                    amostra = REPORT_SERVICE.generate(str(relatorio or ""), limit=1, actor=self._usuario_relatorios())
                except Exception as exc:
                    messagebox.showerror("Indicador", str(exc), parent=janela); return
                coluna = simpledialog.askstring("Indicador", "Coluna: " + ", ".join(amostra.columns), parent=janela) or ""
            try:
                REPORT_SERVICE.save_custom_indicator({"name": nome, "report_id": relatorio, "aggregation": agregacao, "column": coluna, "filters": {"status": self.rel_status.get(), "search": self.rel_busca.get(), "user": self.rel_usuario.get()}}, actor=self._usuario_relatorios())
                carregar()
            except Exception as exc:
                messagebox.showerror("Indicador", str(exc), parent=janela)

        def excluir():
            selecao = tabela.selection()
            if not selecao:
                return
            try:
                REPORT_SERVICE.delete_custom_indicator(selecao[0], actor=self._usuario_relatorios())
                carregar()
            except Exception as exc:
                messagebox.showerror("Indicador", str(exc), parent=janela)

        botoes = ctk.CTkFrame(janela, fg_color="transparent")
        botoes.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkButton(botoes, text="Novo", command=novo).pack(side="left", padx=4)
        ctk.CTkButton(botoes, text="Atualizar", command=carregar).pack(side="left", padx=4)
        ctk.CTkButton(botoes, text="Excluir", fg_color="#da3633", command=excluir).pack(side="left", padx=4)
        carregar()

    def abrir_dashboard_relatorios(self):
        result = getattr(self, "_relatorio_atual", None)
        if not result:
            self.gerar_relatorio_ui()
            result = getattr(self, "_relatorio_atual", None)
        if not result:
            return
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            series = REPORT_SERVICE.chart_series(result)
            janela = ctk.CTkToplevel(self)
            janela.title("Dashboard de relatórios")
            janela.geometry("960x640")
            janela.transient(self)
            indicadores = REPORT_SERVICE.indicators(start_date=self.rel_inicio.get(), end_date=self.rel_fim.get())
            resumo = ctk.CTkFrame(janela, fg_color="#161b22")
            resumo.pack(fill="x", padx=15, pady=15)
            cards = (
                ("Vendas", f"R$ {indicadores['vendas_total']:.2f}"),
                ("A receber", f"R$ {indicadores['receber_aberto']:.2f}"),
                ("A pagar", f"R$ {indicadores['pagar_aberto']:.2f}"),
                ("Estoque baixo", str(indicadores['estoque_baixo'])),
            )
            for titulo, valor in cards:
                card = ctk.CTkFrame(resumo, fg_color="#21262d")
                card.pack(side="left", fill="x", expand=True, padx=5, pady=8)
                ctk.CTkLabel(card, text=titulo, text_color="#8b949e").pack(pady=(8, 2))
                ctk.CTkLabel(card, text=valor, font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 8))
            personalizados = REPORT_SERVICE.evaluate_custom_indicators(start_date=self.rel_inicio.get(), end_date=self.rel_fim.get())
            if personalizados:
                faixa = ctk.CTkFrame(janela, fg_color="#161b22")
                faixa.pack(fill="x", padx=15, pady=(0, 10))
                for indicador in personalizados[:6]:
                    card = ctk.CTkFrame(faixa, fg_color="#21262d")
                    card.pack(side="left", fill="x", expand=True, padx=5, pady=8)
                    ctk.CTkLabel(card, text=str(indicador.get("name", "Indicador")), text_color="#8b949e").pack(pady=(8, 2))
                    ctk.CTkLabel(card, text=str(indicador.get("value", 0)), font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 8))
            figure = Figure(figsize=(9, 4.8), dpi=100)
            axes = figure.add_subplot(111)
            if series["labels"]:
                axes.bar(series["labels"], series["values"])
                axes.tick_params(axis="x", rotation=35)
                axes.set_ylabel(series["value_column"].replace("_", " ").title())
            else:
                axes.text(0.5, 0.5, "Sem dados para o período", ha="center", va="center")
                axes.set_axis_off()
            axes.set_title(series["title"])
            figure.tight_layout()
            canvas = FigureCanvasTkAgg(figure, master=janela)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=(0, 15))
        except ImportError:
            messagebox.showerror("Dashboard", "Instale matplotlib para exibir gráficos.", parent=self)
        except Exception as exc:
            messagebox.showerror("Dashboard", str(exc), parent=self)

    def _executar_agendamentos_relatorios(self):
        try:
            caminhos = REPORT_SERVICE.run_due_schedules(actor=self._usuario_relatorios())
            if caminhos:
                self.mostrar_notificacao("Relatórios agendados", f"{len(caminhos)} arquivo(s) gerado(s).", nivel="success")
        except Exception as exc:
            registrar_auditoria("relatorios", "EXECUTAR_AGENDAMENTOS", "", str(exc), "ERRO", self._usuario_relatorios())
        finally:
            try:
                self.after(60000, self._executar_agendamentos_relatorios)
            except Exception:
                pass

    def abrir_historico_relatorios(self):
        janela = ctk.CTkToplevel(self); janela.title("Histórico de relatórios"); janela.geometry("900x500"); janela.transient(self)
        tabela = ttk.Treeview(janela, columns=("data","relatorio","formato","linhas","usuario","arquivo"), show="headings")
        for col in tabela["columns"]: tabela.heading(col, text=col.title())
        tabela.pack(fill="both", expand=True, padx=15, pady=15)
        historico = REPORT_SERVICE.history()
        for i, row in enumerate(historico):
            tabela.insert("", "end", iid=str(i), values=(row.get("generated_at"), row.get("title"), row.get("format"), row.get("row_count"), row.get("user"), row.get("path")))
        def abrir_arquivo_historico():
            selecao = tabela.selection()
            if not selecao:
                return
            caminho = str(historico[int(selecao[0])].get("path", "")).strip()
            if not caminho or not Path(caminho).exists():
                messagebox.showerror("Histórico", "O arquivo deste registro não está disponível.", parent=janela); return
            self._abrir_arquivo_sistema(caminho)
        botoes = ctk.CTkFrame(janela, fg_color="transparent"); botoes.pack(fill="x", padx=15, pady=(0,15))
        ctk.CTkButton(botoes, text="Abrir arquivo", command=abrir_arquivo_historico).pack(side="left", padx=4)
        ctk.CTkButton(botoes, text="Limpar histórico", fg_color="#da3633", command=lambda: (REPORT_SERVICE.clear_history(actor=self._usuario_relatorios()), janela.destroy())).pack(side="right", padx=4)

    def abrir_agendamentos_relatorios(self):
        janela = ctk.CTkToplevel(self); janela.title("Agendamentos de relatórios"); janela.geometry("760x520"); janela.transient(self)
        tabela = ttk.Treeview(janela, columns=("nome","relatorio","frequencia","horario","formato","ativo","proxima"), show="headings", height=12)
        for col in tabela["columns"]: tabela.heading(col, text=col.title())
        tabela.pack(fill="both", expand=True, padx=15, pady=15)
        def carregar():
            tabela.delete(*tabela.get_children())
            for row in REPORT_SERVICE.list_schedules():
                tabela.insert("", "end", iid=row["name"], values=(row["name"], row["report_id"], row["frequency"], row.get("run_time", "08:00"), row["format"], "SIM" if row.get("active") else "NÃO", row.get("next_run_at", "")))
        def novo():
            nome = simpledialog.askstring("Agendamento", "Nome:", parent=janela)
            if not nome: return
            permitidos = self._relatorios_permitidos()
            if not permitidos:
                messagebox.showerror("Agendamento", "Nenhum relatório permitido para este usuário.", parent=janela); return
            rel = simpledialog.askstring("Agendamento", "Relatório: " + ", ".join(permitidos), initialvalue=next(iter(permitidos)), parent=janela)
            freq = simpledialog.askstring("Agendamento", "Frequência: DIARIO, SEMANAL ou MENSAL", initialvalue="MENSAL", parent=janela)
            horario = simpledialog.askstring("Agendamento", "Horário (HH:MM):", initialvalue="08:00", parent=janela)
            fmt = simpledialog.askstring("Agendamento", "Formato: CSV, XLSX ou PDF", initialvalue="PDF", parent=janela)
            try:
                filtros_atuais = {"start_date": self.rel_inicio.get(), "end_date": self.rel_fim.get(), "search": self.rel_busca.get(), "status": self.rel_status.get(), "user": self.rel_usuario.get()}
                REPORT_SERVICE.save_schedule({"name":nome,"report_id":rel,"frequency":freq,"run_time":horario,"format":fmt,"active":True,"filters":filtros_atuais}, actor=self._usuario_relatorios()); carregar()
            except Exception as exc: messagebox.showerror("Agendamento", str(exc), parent=janela)
        def executar():
            sel=tabela.selection()
            if not sel: return
            try:
                path=REPORT_SERVICE.run_schedule(sel[0], actor=self._usuario_relatorios()); self.mostrar_notificacao("Relatório gerado", path.name, nivel="success")
            except Exception as exc: messagebox.showerror("Agendamento", str(exc), parent=janela)
        def alternar():
            sel=tabela.selection()
            if not sel: return
            atual = next(row for row in REPORT_SERVICE.list_schedules() if row["name"] == sel[0])
            REPORT_SERVICE.save_schedule({**atual, "active": not atual.get("active", True)}, actor=self._usuario_relatorios()); carregar()
        def excluir():
            sel=tabela.selection()
            if not sel: return
            REPORT_SERVICE.delete_schedule(sel[0], actor=self._usuario_relatorios()); carregar()
        botoes=ctk.CTkFrame(janela, fg_color="transparent"); botoes.pack(fill="x", padx=15, pady=(0,15))
        ctk.CTkButton(botoes,text="Novo",command=novo).pack(side="left",padx=4)
        ctk.CTkButton(botoes,text="Executar agora",command=executar).pack(side="left",padx=4)
        ctk.CTkButton(botoes,text="Ativar / Desativar",command=alternar).pack(side="left",padx=4)
        ctk.CTkButton(botoes,text="Excluir",fg_color="#da3633",command=excluir).pack(side="left",padx=4)
        carregar()

    def tela_financeiro(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        self.adicionar_rodape_status(frame)

        scroll_financeiro = BidirectionalScrollableFrame(frame, fg_color="transparent", content_width=1280)
        scroll_financeiro.pack(fill="both", expand=True, padx=20, pady=5)
        conteudo_financeiro = scroll_financeiro.content

        filtros = ctk.CTkFrame(conteudo_financeiro, fg_color="#161b22")
        filtros.pack(fill="x", padx=20, pady=(0, 10))
        hoje = datetime.now()
        inicio = hoje.replace(day=1).strftime("%Y-%m-%d")
        self.fin_inicio = ctk.CTkEntry(filtros, width=120)
        self.fin_inicio.insert(0, inicio)
        self.fin_inicio.pack(side="left", padx=(12, 4), pady=10)
        self.fin_fim = ctk.CTkEntry(filtros, width=120)
        self.fin_fim.insert(0, hoje.strftime("%Y-%m-%d"))
        self.fin_fim.pack(side="left", padx=4, pady=10)
        SearchEntryBehavior.attach(self.fin_inicio, on_enter=self.carregar_financeiro)
        SearchEntryBehavior.attach(self.fin_fim, on_enter=self.carregar_financeiro)
        self.fin_tipo = ctk.CTkComboBox(filtros, values=["TODOS", "PAGAR", "RECEBER"], width=120)
        self.fin_tipo.set("TODOS")
        self.fin_tipo.pack(side="left", padx=4, pady=10)
        self.fin_status = ctk.CTkComboBox(filtros, values=["TODOS", "ABERTO", "PARCIAL", "PAGO", "CANCELADO"], width=130)
        self.fin_status.set("TODOS")
        self.fin_status.pack(side="left", padx=4, pady=10)
        ctk.CTkButton(filtros, text="Atualizar", width=95, command=self.carregar_financeiro).pack(side="left", padx=4)
        ctk.CTkButton(filtros, text="Novo título", width=105, fg_color="#2ea043", command=self.novo_titulo_financeiro).pack(side="left", padx=4)
        ctk.CTkButton(filtros, text="Baixar", width=85, command=self.baixar_titulo_financeiro).pack(side="left", padx=4)
        ctk.CTkButton(filtros, text="Centro custo", width=110, command=self.definir_centro_custo_financeiro).pack(side="left", padx=4)
        ctk.CTkButton(filtros, text="Estornar baixa", width=110, command=self.estornar_pagamento_financeiro).pack(side="left", padx=4)
        ctk.CTkButton(filtros, text="Cancelar título", width=110, fg_color="#b42318", command=self.cancelar_titulo_financeiro).pack(side="left", padx=4)

        resumo = ctk.CTkFrame(conteudo_financeiro, fg_color="transparent")
        resumo.pack(fill="x", padx=20, pady=(0, 8))
        self.fin_lbl_fluxo = ctk.CTkLabel(resumo, text="Fluxo: --", font=ctk.CTkFont(size=14, weight="bold"))
        self.fin_lbl_fluxo.pack(side="left", padx=8)
        self.fin_lbl_dre = ctk.CTkLabel(resumo, text="DRE: --", font=ctk.CTkFont(size=14, weight="bold"))
        self.fin_lbl_dre.pack(side="left", padx=18)
        ctk.CTkButton(resumo, text="Recorrências", width=110, command=self.abrir_recorrencias_financeiro).pack(side="right", padx=4)
        ctk.CTkButton(resumo, text="Conciliações", width=105, command=self.abrir_conciliacoes_financeiro).pack(side="right", padx=4)
        ctk.CTkButton(resumo, text="Centros", width=90, command=self.abrir_relatorio_centros_custo).pack(side="right", padx=4)
        ctk.CTkButton(resumo, text="Detalhes", width=90, command=self.abrir_detalhes_financeiros).pack(side="right", padx=4)

        area = ctk.CTkFrame(conteudo_financeiro, fg_color="#0d1117")
        area.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        colunas = ("id", "tipo", "pessoa", "descricao", "vencimento", "original", "pago", "saldo", "status", "centro")
        self.tabela_financeiro = ttk.Treeview(area, columns=colunas, show="headings")
        titulos = {"id":"ID","tipo":"Tipo","pessoa":"Pessoa","descricao":"Descrição","vencimento":"Vencimento","original":"Original","pago":"Pago","saldo":"Saldo","status":"Status","centro":"Centro de custo"}
        larguras = {"id":55,"tipo":75,"pessoa":150,"descricao":190,"vencimento":95,"original":90,"pago":90,"saldo":90,"status":85,"centro":130}
        for c in colunas:
            self.tabela_financeiro.heading(c, text=titulos[c])
            self.tabela_financeiro.column(c, width=larguras[c], anchor="center" if c not in {"pessoa","descricao","centro"} else "w")
        sb_y = ttk.Scrollbar(area, orient="vertical", command=self.tabela_financeiro.yview)
        sb_x = ttk.Scrollbar(area, orient="horizontal", command=self.tabela_financeiro.xview)
        self.tabela_financeiro.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.tabela_financeiro.pack(fill="both", expand=True)
        return frame

    def _financeiro_callbacks(self):
        return cached_instance(
            self,
            "_financeiro_callback_controller",
            lambda: FinanceiroCallbackController(self, FINANCEIRO_SERVICE, FinanceiroViewData),
        )

    def carregar_financeiro(self):
        return self._financeiro_callbacks().carregar()

    def _titulo_financeiro_selecionado(self):
        return self._financeiro_callbacks().titulo_selecionado()

    def novo_titulo_financeiro(self):
        return self._financeiro_callbacks().novo_titulo()

    def baixar_titulo_financeiro(self):
        return self._financeiro_callbacks().baixar_titulo()

    def definir_centro_custo_financeiro(self):
        return self._financeiro_callbacks().definir_centro_custo()

    def abrir_recorrencias_financeiro(self):
        return self._financeiro_callbacks().abrir_recorrencias()

    def conciliar_pagamento_financeiro(self):
        return self._financeiro_callbacks().conciliar_pagamento()

    def cancelar_titulo_financeiro(self):
        return self._financeiro_callbacks().cancelar_titulo()

    def abrir_conciliacoes_financeiro(self):
        return self._financeiro_callbacks().abrir_conciliacoes()

    def abrir_relatorio_centros_custo(self):
        return self._financeiro_callbacks().abrir_relatorio_centros_custo()

    def abrir_detalhes_financeiros(self):
        return self._financeiro_callbacks().abrir_detalhes()

    def estornar_pagamento_financeiro(self):
        return self._financeiro_callbacks().estornar_pagamento()

    def tela_configs(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")

        self.adicionar_rodape_status(frame)

        scroll_configs = BidirectionalScrollableFrame(frame, fg_color="transparent", content_width=980)
        scroll_configs.pack(fill="both", expand=True, padx=20, pady=5)
        conteudo_cfg = scroll_configs.content
        conteudo_cfg.configure(fg_color="#161b22", corner_radius=12)

        lbl = ctk.CTkLabel(conteudo_cfg, text="⚙️ Configurações e Personalização", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.cor_acento)
        lbl.pack(anchor="w", padx=20, pady=(15, 10))
        self._widgets_acento.append(lbl)

        frame_form_cfg = ctk.CTkFrame(conteudo_cfg, fg_color="transparent")
        frame_form_cfg.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(frame_form_cfg, text="Identidade da loja", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.cor_acento).pack(anchor="w", pady=(2, 8))
        ctk.CTkLabel(frame_form_cfg, text="Nome exibido em todas as telas e no título da janela:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(2, 2))
        self.entry_cfg_loja = ctk.CTkEntry(frame_form_cfg, height=35)
        self.entry_cfg_loja.pack(fill="x", pady=(0, 10))
        self.entry_cfg_loja.insert(0, obter_config("nome_loja"))

        ctk.CTkLabel(frame_form_cfg, text="Telefone / Contato:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(2, 2))
        self.entry_cfg_tel = ctk.CTkEntry(frame_form_cfg, height=35)
        self.entry_cfg_tel.pack(fill="x", pady=(0, 14))
        self.entry_cfg_tel.insert(0, obter_config("telefone"))

        ctk.CTkLabel(frame_form_cfg, text="Endereço da loja:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(2, 2))
        self.entry_cfg_endereco = ctk.CTkEntry(frame_form_cfg, height=35); self.entry_cfg_endereco.pack(fill="x", pady=(0, 10)); self.entry_cfg_endereco.insert(0, obter_config("endereco"))
        ctk.CTkLabel(frame_form_cfg, text="CNPJ:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(2, 2))
        self.entry_cfg_cnpj = ctk.CTkEntry(frame_form_cfg, height=35); self.entry_cfg_cnpj.pack(fill="x", pady=(0, 10)); self.entry_cfg_cnpj.insert(0, obter_config("cnpj"))
        ctk.CTkLabel(frame_form_cfg, text="E-mail:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(2, 2))
        self.entry_cfg_email = ctk.CTkEntry(frame_form_cfg, height=35); self.entry_cfg_email.pack(fill="x", pady=(0, 14)); self.entry_cfg_email.insert(0, obter_config("email"))

        ctk.CTkLabel(frame_form_cfg, text="Modo de operação", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.cor_acento).pack(anchor="w", pady=(8, 6))
        ctk.CTkLabel(
            frame_form_cfg,
            text="Comercial permite item avulso sem estoque e imprime comprovante não fiscal. Fiscal exige produtos cadastrados e mantém os recursos fiscais disponíveis.",
            text_color="#8b949e", wraplength=780, justify="left",
        ).pack(anchor="w", pady=(0, 6))
        self.combo_modo_operacao = ctk.CTkComboBox(
            frame_form_cfg,
            values=["COMERCIAL — sem emissão fiscal", "FISCAL — com recursos fiscais"],
            state="readonly",
            height=38,
        )
        modo_salvo = (obter_config("modo_operacao") or "COMERCIAL").strip().upper()
        self.combo_modo_operacao.set(
            "FISCAL — com recursos fiscais" if modo_salvo == "FISCAL"
            else "COMERCIAL — sem emissão fiscal"
        )
        self.combo_modo_operacao.pack(fill="x", pady=(0, 12))

        separador1 = ctk.CTkFrame(frame_form_cfg, height=2, fg_color="#30363d"); separador1.pack(fill="x", pady=10)
        ctk.CTkLabel(frame_form_cfg, text="Aparência e cores", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.cor_acento).pack(anchor="w", pady=(2, 8))

        linha_tema = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); linha_tema.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_tema, text="Modo:", width=120, anchor="w").pack(side="left")
        self.combo_aparencia = ctk.CTkComboBox(linha_tema, values=["Dark", "Light", "System"], state="readonly")
        self.combo_aparencia.pack(side="left", fill="x", expand=True)
        self.combo_aparencia.set(obter_config("aparencia_sistema") or "Dark")

        linha_cor = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); linha_cor.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_cor, text="Cor de destaque:", width=120, anchor="w").pack(side="left")
        self.combo_cor_destaque = ctk.CTkComboBox(linha_cor, values=list(self._paletas.keys()), state="readonly")
        self.combo_cor_destaque.pack(side="left", fill="x", expand=True)
        self.combo_cor_destaque.set(obter_config("cor_destaque") or "Verde Nabi")

        ctk.CTkLabel(frame_form_cfg, text="Experiência de uso", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(14, 6))

        linha_modo = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); linha_modo.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_modo, text="Modo:", width=120, anchor="w").pack(side="left")
        self.combo_modo_interface = ctk.CTkComboBox(linha_modo, values=list(UIPreferencesService.MODES), state="readonly")
        self.combo_modo_interface.pack(side="left", fill="x", expand=True)
        self.combo_modo_interface.set(self.preferencias_interface["mode"])

        linha_espaco = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); linha_espaco.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_espaco, text="Espaço de trabalho:", width=120, anchor="w").pack(side="left")
        self.combo_espaco_interface = ctk.CTkComboBox(linha_espaco, values=list(UIPreferencesService.WORKSPACES), state="readonly")
        self.combo_espaco_interface.pack(side="left", fill="x", expand=True)
        self.combo_espaco_interface.set(self.preferencias_interface["workspace"])

        linha_densidade = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); linha_densidade.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_densidade, text="Densidade:", width=120, anchor="w").pack(side="left")
        self.combo_densidade_interface = ctk.CTkComboBox(linha_densidade, values=list(UIPreferencesService.DENSITIES), state="readonly")
        self.combo_densidade_interface.pack(side="left", fill="x", expand=True)
        self.combo_densidade_interface.set(self.preferencias_interface["density"])

        linha_tema_oficial = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); linha_tema_oficial.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_tema_oficial, text="Tema oficial:", width=120, anchor="w").pack(side="left")
        self.combo_tema_oficial = ctk.CTkComboBox(linha_tema_oficial, values=list(UIPreferencesService.THEMES), state="readonly")
        self.combo_tema_oficial.pack(side="left", fill="x", expand=True)
        self.combo_tema_oficial.set(self.preferencias_interface["theme"])

        ctk.CTkLabel(
            frame_form_cfg,
            text="Identidade visual do fundo",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(12, 4))

        self.var_background_enabled = tk.BooleanVar(
            value=self.preferencias_interface["background_enabled"]
        )
        ctk.CTkCheckBox(
            frame_form_cfg,
            text="Mostrar logo no fundo",
            variable=self.var_background_enabled,
        ).pack(anchor="w", pady=(2, 6))

        linha_opacidade = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        linha_opacidade.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_opacidade, text="Transparência:", width=120, anchor="w").pack(side="left")
        self.slider_background_opacity = ctk.CTkSlider(
            linha_opacidade, from_=0.02, to=0.25, number_of_steps=23,
        )
        self.slider_background_opacity.set(self.preferencias_interface["background_opacity"])
        self.slider_background_opacity.pack(side="left", fill="x", expand=True)

        linha_escala = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        linha_escala.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_escala, text="Escala:", width=120, anchor="w").pack(side="left")
        self.combo_background_scale = ctk.CTkComboBox(
            linha_escala, values=list(UIPreferencesService.BACKGROUND_SCALES), state="readonly",
        )
        self.combo_background_scale.set(self.preferencias_interface["background_scale"])
        self.combo_background_scale.pack(side="left", fill="x", expand=True)

        linha_posicao = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        linha_posicao.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_posicao, text="Posição:", width=120, anchor="w").pack(side="left")
        self.combo_background_position = ctk.CTkComboBox(
            linha_posicao, values=list(UIPreferencesService.BACKGROUND_POSITIONS), state="readonly",
        )
        self.combo_background_position.set(self.preferencias_interface["background_position"])
        self.combo_background_position.pack(side="left", fill="x", expand=True)

        self.var_menu_adaptativo = tk.BooleanVar(value=self.preferencias_interface["adaptive_menu"])
        ctk.CTkCheckBox(frame_form_cfg, text="Ocultar módulos que não pertencem ao espaço de trabalho", variable=self.var_menu_adaptativo).pack(anchor="w", pady=(8, 4))

        ctk.CTkLabel(frame_form_cfg, text="Botões visíveis na tela principal", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(12, 4))
        self.var_navegacao_personalizada = tk.BooleanVar(value=self.preferencias_interface["custom_navigation"])
        ctk.CTkCheckBox(
            frame_form_cfg,
            text="Escolher manualmente quais botões aparecem",
            variable=self.var_navegacao_personalizada,
        ).pack(anchor="w", pady=(2, 4))
        self.vars_modulos_navegacao = {}
        modulos_visiveis = set(self.preferencias_interface["navigation_modules"])
        frame_modulos = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        frame_modulos.pack(fill="x", pady=(0, 4))
        for indice, (module_id, titulo) in enumerate(UIPreferencesService.MODULE_LABELS.items()):
            var = tk.BooleanVar(value=module_id in modulos_visiveis)
            self.vars_modulos_navegacao[module_id] = var
            check = ctk.CTkCheckBox(frame_modulos, text=titulo, variable=var)
            check.grid(row=indice // 2, column=indice % 2, sticky="w", padx=(0, 24), pady=2)
        frame_modulos.grid_columnconfigure(0, weight=1)
        frame_modulos.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            frame_form_cfg,
            text="Ocultar um botão não desativa seu atalho: F1 Início, F2 Vendas, F3 Clientes, F4 Produtos e F5 Configurações continuam funcionando.",
            text_color="#8b949e",
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(frame_form_cfg, text="As alterações de modo, espaço e densidade são aplicadas completamente ao reiniciar o NabiCode.", text_color="#8b949e").pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(frame_form_cfg, text="Favoritos de módulos", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(8, 4))
        linha_favoritos = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        linha_favoritos.pack(fill="x", pady=(0, 8))
        self.combo_favoritos_config = ctk.CTkComboBox(linha_favoritos, values=["Nenhum favorito"], state="readonly")
        self.combo_favoritos_config.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(linha_favoritos, text="↑", width=42, command=lambda: self._mover_favorito_config(-1)).pack(side="left", padx=2)
        ctk.CTkButton(linha_favoritos, text="↓", width=42, command=lambda: self._mover_favorito_config(1)).pack(side="left", padx=2)
        ctk.CTkButton(linha_favoritos, text="Remover", width=84, fg_color="#da3633", hover_color="#b62324", command=self._remover_favorito_config).pack(side="left", padx=(5, 0))
        ctk.CTkLabel(frame_form_cfg, text="Use o botão direito nos módulos para adicionar ou remover. Alt+1 até Alt+9 abre os favoritos na ordem acima.", text_color="#8b949e", wraplength=780, justify="left").pack(anchor="w", pady=(0, 8))
        self._sincronizar_controles_favoritos_config()

        ctk.CTkLabel(frame_form_cfg, text="Notificações", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(8, 4))
        linha_notificacoes = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        linha_notificacoes.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(linha_notificacoes, text="Duração dos avisos (segundos):").pack(side="left")
        self.entry_duracao_notificacoes = ctk.CTkEntry(linha_notificacoes, width=90)
        self.entry_duracao_notificacoes.pack(side="left", padx=(10, 0))
        self.entry_duracao_notificacoes.insert(0, f"{self.notification_center.default_duration_ms / 1000:.1f}")
        ctk.CTkLabel(frame_form_cfg, text="Avisos de sucesso desaparecem automaticamente; erros críticos continuam usando janelas modais.", text_color="#8b949e", wraplength=780, justify="left").pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(frame_form_cfg, text="Painéis da tela inicial", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(8, 4))
        self.vars_dashboard_widgets = {}
        widgets_ativos = set(UIPreferencesService.dashboard_widgets(self.preferencias_interface))
        for widget_id, titulo in UIPreferencesService.DASHBOARD_WIDGETS.items():
            var = tk.BooleanVar(value=widget_id in widgets_ativos)
            self.vars_dashboard_widgets[widget_id] = var
            ctk.CTkCheckBox(frame_form_cfg, text=titulo, variable=var).pack(anchor="w", pady=2)

        separador2 = ctk.CTkFrame(frame_form_cfg, height=2, fg_color="#30363d"); separador2.pack(fill="x", pady=10)
        ctk.CTkLabel(frame_form_cfg, text="Backup local e em nuvem", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.cor_acento).pack(anchor="w", pady=(2, 4))
        ctk.CTkLabel(frame_form_cfg, text="Para nuvem, selecione uma pasta sincronizada do OneDrive, Google Drive ou Dropbox.", text_color="#8b949e").pack(anchor="w", pady=(0, 8))

        def linha_pasta(titulo, valor, atributo):
            ctk.CTkLabel(frame_form_cfg, text=titulo, font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(4, 2))
            linha = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); linha.pack(fill="x", pady=(0, 5))
            entrada = ctk.CTkEntry(linha, height=35); entrada.pack(side="left", fill="x", expand=True, padx=(0, 6)); entrada.insert(0, valor)
            setattr(self, atributo, entrada)
            def escolher():
                pasta = filedialog.askdirectory(parent=self, title=titulo)
                if pasta:
                    entrada.delete(0, "end"); entrada.insert(0, pasta)
            ctk.CTkButton(linha, text="📂 Escolher", width=110, command=escolher).pack(side="right")

        linha_pasta("Pasta principal dos backups:", obter_config("pasta_backup_local") or BACKUP_DIR, "entry_backup_local")
        linha_pasta("Pasta adicional sincronizada na nuvem (opcional):", obter_config("pasta_backup_nuvem"), "entry_backup_nuvem")

        self.var_backup_diario = tk.BooleanVar(value=obter_config("backup_diario_ativo") != "0")
        ctk.CTkCheckBox(frame_form_cfg, text="Criar automaticamente um backup por dia ao abrir o sistema", variable=self.var_backup_diario).pack(anchor="w", pady=8)

        botoes_backup = ctk.CTkFrame(frame_form_cfg, fg_color="transparent"); botoes_backup.pack(fill="x", pady=5)
        ctk.CTkButton(botoes_backup, text="💾 Fazer backup agora", fg_color="#1f6feb", command=self.fazer_backup_config_agora).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(botoes_backup, text="📂 Abrir pasta principal", fg_color="#8957e5", command=self.abrir_pasta_backup_config).pack(side="left", expand=True, fill="x", padx=(4, 0))

        btn_salvar_cfg = ctk.CTkButton(frame_form_cfg, text="✅ Salvar configurações e aplicar", fg_color="#2ea043", hover_color="#238636", height=42, font=ctk.CTkFont(size=13, weight="bold"), command=self.salvar_configuracoes_gerais)
        btn_salvar_cfg.pack(pady=(16, 8), fill="x")
        ctk.CTkButton(frame_form_cfg, text="🖨️ Configurar Impressoras", fg_color="#8957e5", hover_color="#6e40c9", height=40, command=self.abrir_configuracao_impressoras).pack(pady=5, fill="x")
        ctk.CTkButton(frame_form_cfg, text="🧾 Modelos e Personalização de Impressão", fg_color="#9e6a03", hover_color="#7d4e00", height=40, command=self.abrir_configuracao_modelos_impressao).pack(pady=5, fill="x")

        if modo_fiscal_ativo():
            ctk.CTkButton(frame_form_cfg, text="🧾 Fiscal oficial", fg_color="#1f6feb", hover_color="#1158c7", height=40, command=self.abrir_configuracao_fiscal).pack(pady=5, fill="x")

        ctk.CTkButton(frame_form_cfg, text="🏭 Restaurar padrão de fábrica", fg_color="#da3633", hover_color="#b62324", height=40, command=self.abrir_restauracao_fabrica).pack(pady=5, fill="x")

        return frame

    def _obter_senha_certificado(self, *, parent=None, title="Certificado A1"):
        cached = self.fiscal_service.session_certificate_password()
        if cached is not None:
            return cached
        config = self.fiscal_service.load_config()
        path = str(config.get("certificate_path") or "").strip()
        if not path or not Path(path).is_file():
            messagebox.showwarning(
                title,
                "Selecione e salve o certificado A1 uma única vez na Configuração Fiscal.",
                parent=parent or self,
            )
            return None
        secret = simpledialog.askstring(
            title,
            "Senha do certificado A1 (será lembrada somente até fechar o NabiCode):",
            show="*",
            parent=parent or self,
        )
        if secret is None:
            return None
        try:
            self.fiscal_service.cache_certificate_password(secret)
        except Exception as exc:
            messagebox.showerror(title, str(exc), parent=parent or self)
            return None
        return secret

    def abrir_configuracao_fiscal(self):
        if not modo_fiscal_ativo():
            messagebox.showinfo("Modo Comercial", "Os recursos fiscais estão ocultos. Ative o modo Fiscal em Configurações.", parent=self)
            return
        if not self._autorizar("fiscal", "configure"):
            return
        config = self.fiscal_service.load_config()
        janela = ctk.CTkToplevel(self)
        janela.title("Fiscal oficial — configuração opcional")
        janela.geometry("720x650")
        janela.minsize(620, 540)
        janela.transient(self)
        janela.grab_set()

        corpo = BidirectionalScrollableFrame(janela, fg_color="#161b22", content_width=650)
        corpo.pack(fill="both", expand=True, padx=12, pady=12)
        content = corpo.content
        ctk.CTkLabel(content, text="Fiscal oficial (opcional)", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.cor_acento).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(content, text="O NabiCode continua funcionando normalmente sem CNPJ ou certificado A1. Estes dados só são exigidos para transmitir documentos à SEFAZ.", wraplength=610, justify="left", text_color="#c9d1d9").pack(anchor="w", padx=16, pady=(0, 14))

        enabled = tk.BooleanVar(value=bool(config.get("enabled")))
        ctk.CTkCheckBox(content, text="Habilitar recursos fiscais oficiais", variable=enabled).pack(anchor="w", padx=16, pady=6)
        fields = {}
        def field(label, value="", parent=None):
            container = parent or content
            ctk.CTkLabel(container, text=label, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(8, 2))
            entry = ctk.CTkEntry(container, height=34)
            entry.pack(fill="x", padx=16)
            entry.insert(0, str(value or ""))
            return entry
        fields["cnpj"] = field("CNPJ do emitente", config.get("cnpj"))
        fields["state"] = field("UF", config.get("state"))
        ctk.CTkLabel(content, text="Regime tributário", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(8, 2))
        regime_labels = dict(self.fiscal_service.TAX_REGIME_LABELS)
        regime_by_label = {label: code for code, label in regime_labels.items()}
        tax_regime = ctk.CTkComboBox(content, values=list(regime_by_label), state="readonly")
        tax_regime.pack(fill="x", padx=16)
        current_regime = str(config.get("tax_regime") or "SIMPLES_NACIONAL").upper()
        tax_regime.set(regime_labels.get(current_regime, regime_labels["SIMPLES_NACIONAL"]))

        ctk.CTkLabel(content, text="Documentos fiscais habilitados", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(10, 2))
        enabled_models = {str(model) for model in config.get("enabled_models", ["55", "65"])}
        model_vars = {
            model: tk.BooleanVar(value=model in enabled_models)
            for model in ("55", "65")
        }
        model_row = ctk.CTkFrame(content, fg_color="transparent")
        model_row.pack(fill="x", padx=16)
        for model in ("55", "65"):
            ctk.CTkCheckBox(
                model_row, text=self.fiscal_service.MODEL_LABELS[model], variable=model_vars[model]
            ).pack(side="left", padx=(0, 18))
        ctk.CTkLabel(content, text="Documento padrão", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(8, 2))
        default_model = ctk.CTkComboBox(
            content, values=[self.fiscal_service.MODEL_LABELS["55"], self.fiscal_service.MODEL_LABELS["65"]], state="readonly"
        )
        default_model.pack(fill="x", padx=16)
        default_model.set(self.fiscal_service.MODEL_LABELS.get(str(config.get("default_model") or "65"), self.fiscal_service.MODEL_LABELS["65"]))
        issuer_config = config.get("issuer") or {}
        fields["issuer_name"] = field("Razão social do emitente", issuer_config.get("name"))
        fields["issuer_ie"] = field("Inscrição estadual", issuer_config.get("state_registration"))
        fields["issuer_city_code"] = field("Código IBGE do município", issuer_config.get("city_code"))
        fields["issuer_city"] = field("Município", issuer_config.get("city"))
        fields["issuer_street"] = field("Logradouro", issuer_config.get("street"))
        fields["issuer_number"] = field("Número", issuer_config.get("number"))
        fields["issuer_district"] = field("Bairro", issuer_config.get("district"))
        fields["issuer_zip"] = field("CEP", issuer_config.get("zip_code"))
        fields["return_series"] = field("Série padrão para NF-e de devolução", issuer_config.get("return_series", 1))
        ctk.CTkLabel(content, text="Ambiente", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(8, 2))
        environment = ctk.CTkComboBox(content, values=["HOMOLOGACAO", "PRODUCAO"], state="readonly")
        environment.pack(fill="x", padx=16); environment.set(config.get("environment") or "HOMOLOGACAO")

        certificado_card = ctk.CTkFrame(content, fg_color="#0d1117", corner_radius=10)
        certificado_card.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            certificado_card,
            text="Certificado digital A1",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.cor_acento,
        ).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            certificado_card,
            text=(
                "Selecione o arquivo recebido da certificadora (.pfx ou .p12). "
                "A senha é usada somente para validar e nunca é salva pelo NabiCode."
            ),
            text_color="#c9d1d9",
            wraplength=580,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        certificate = field(
            "Arquivo do certificado A1 (.pfx/.p12)",
            config.get("certificate_path"),
            parent=certificado_card,
        )
        password = field(
            "Senha do certificado A1 (não será salva)", "", parent=certificado_card
        )
        password.configure(show="*")
        certificate_status = ctk.CTkLabel(
            certificado_card,
            text="Selecione o arquivo e informe a senha para verificar.",
            text_color="#8b949e",
            wraplength=580,
            justify="left",
        )
        certificate_status.pack(anchor="w", padx=12, pady=(4, 10))
        def choose_certificate():
            path = filedialog.askopenfilename(parent=janela, title="Selecionar certificado A1", filetypes=[("Certificado A1", "*.pfx *.p12"), ("Todos", "*.*")])
            if path:
                certificate.delete(0, "end"); certificate.insert(0, path)
                certificate_status.configure(
                    text="Arquivo selecionado. Informe a senha e clique em Verificar certificado.",
                    text_color="#d29922",
                )

        def verify_certificate_now():
            path = certificate.get().strip()
            secret = password.get()
            if not path:
                certificate_status.configure(
                    text="Selecione primeiro um arquivo .pfx ou .p12.", text_color="#f85149"
                )
                return
            if not secret:
                certificate_status.configure(
                    text="Informe a senha do certificado para fazer a verificação.",
                    text_color="#f85149",
                )
                password.focus_set()
                return
            try:
                info = self.fiscal_service.inspect_certificate(path, secret)
                if info.expired:
                    certificate_status.configure(
                        text=f"Certificado fora da validade. Validade informada: {info.valid_until}.",
                        text_color="#f85149",
                    )
                    return
                certificate_status.configure(
                    text=(
                        f"Certificado válido. Documento: {info.document or 'não identificado'} | "
                        f"Validade: {info.valid_until}."
                    ),
                    text_color="#3fb950",
                )
                if str(Path(path).resolve()) == str(Path(config.get("certificate_path") or path).resolve()):
                    self.fiscal_service.cache_certificate_password(secret)
            except Exception as exc:
                certificate_status.configure(text=str(exc), text_color="#f85149")

        certificate_actions = ctk.CTkFrame(certificado_card, fg_color="transparent")
        certificate_actions.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(
            certificate_actions,
            text="1. Selecionar arquivo A1",
            command=choose_certificate,
            fg_color="#1f6feb",
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            certificate_actions,
            text="2. Verificar certificado",
            command=verify_certificate_now,
            fg_color="#8957e5",
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        endpoints = config.get("endpoints") or {}
        for ambiente, titulo in (("HOMOLOGACAO", "homologação"), ("PRODUCAO", "produção")):
            ambiente_endpoints = endpoints.get(ambiente) or {}
            for operacao, rotulo in (("autorizacao", "Autorização"), ("consulta", "Consulta de situação"), ("evento", "Eventos (cancelamento/CC-e)"), ("inutilizacao", "Inutilização")):
                fields[f"endpoint_{ambiente.lower()}_{operacao}"] = field(
                    f"Endpoint {rotulo} — {titulo}", ambiente_endpoints.get(operacao, "")
                )

        status = ctk.CTkLabel(content, text="", wraplength=610, justify="left")
        status.pack(anchor="w", padx=16, pady=8)
        def verify_fiscal_catalog():
            try:
                regime = regime_by_label[tax_regime.get()]
                crt = self.fiscal_service.TAX_REGIME_CODES[regime]
                report = self.fiscal_catalog_readiness_service.audit(crt=crt)
                if report.total == 0:
                    messagebox.showwarning(
                        "Catálogo fiscal", "Nenhum produto fiscal ativo foi encontrado.", parent=janela
                    )
                    return
                if report.is_ready:
                    messagebox.showinfo(
                        "Catálogo fiscal",
                        f"Todos os {report.total} produtos fiscais estão prontos para vendas nacionais.",
                        parent=janela,
                    )
                    return
                details = "\n".join(
                    f"• {issue.code} — {issue.name}: {issue.message}"
                    for issue in report.issues[:12]
                )
                remaining = report.blocked - min(report.blocked, 12)
                if remaining:
                    details += f"\n• ... e mais {remaining} produto(s)."
                should_open = messagebox.askyesno(
                    "Catálogo fiscal — revisão necessária",
                    (
                        f"Prontos: {report.ready} de {report.total}\n\n{details}\n\n"
                        "Deseja abrir o primeiro produto pendente diretamente na aba Fiscal?"
                    ),
                    parent=janela,
                )
                if should_open:
                    first_issue = report.issues[0]
                    janela.grab_release()
                    janela.destroy()
                    self.abrir_cadastro_produto(
                        first_issue.product_id,
                        aba_inicial="Fiscal",
                        ao_salvar=self.abrir_configuracao_fiscal,
                    )
            except Exception as exc:
                messagebox.showerror("Catálogo fiscal", str(exc), parent=janela)
        def save():
            try:
                enabled_changed = bool(config.get("enabled")) != bool(enabled.get())
                if enabled_changed and not self._confirmar_senha_mestra(
                    title="Alterar emissão fiscal oficial",
                    prompt=(
                        "Digite a senha mestra para habilitar ou desabilitar a emissão "
                        "fiscal oficial."
                    ),
                    parent=janela,
                ):
                    enabled.set(bool(config.get("enabled")))
                    status.configure(
                        text="A emissão fiscal não foi alterada.", text_color="#d29922"
                    )
                    return
                selected_models = [model for model, variable in model_vars.items() if variable.get()]
                selected_default = next(
                    model for model, label in self.fiscal_service.MODEL_LABELS.items()
                    if label == default_model.get()
                )
                previous_certificate = str(config.get("certificate_path") or "").strip()
                saved = self.fiscal_service.save_config({
                    "enabled": enabled.get(), "environment": environment.get(),
                    "cnpj": fields["cnpj"].get(), "state": fields["state"].get(),
                    "tax_regime": regime_by_label[tax_regime.get()],
                    "enabled_models": selected_models, "default_model": selected_default,
                    "certificate_path": certificate.get(),
                    "issuer": {
                        "name": fields["issuer_name"].get(),
                        "state_registration": fields["issuer_ie"].get(),
                        "city_code": fields["issuer_city_code"].get(),
                        "city": fields["issuer_city"].get(),
                        "street": fields["issuer_street"].get(),
                        "number": fields["issuer_number"].get(),
                        "district": fields["issuer_district"].get(),
                        "zip_code": fields["issuer_zip"].get(),
                        "return_series": fields["return_series"].get(),
                    },
                    "endpoints": {
                        ambiente: {
                            operacao: fields[f"endpoint_{ambiente.lower()}_{operacao}"].get()
                            for operacao in ("autorizacao", "consulta", "evento", "inutilizacao")
                        }
                        for ambiente in ("HOMOLOGACAO", "PRODUCAO")
                    },
                })
                if str(saved.get("certificate_path") or "").strip() != previous_certificate:
                    self.fiscal_service.clear_session_certificate_password()
                if certificate.get().strip() and password.get():
                    info = self.fiscal_service.configure_certificate(certificate.get().strip(), password.get())
                    status.configure(text=f"Certificado válido até {info.valid_until}.", text_color="#3fb950")
                else:
                    status.configure(text="Configuração salva. Certificado não validado nesta operação.", text_color="#d29922")
                registrar_auditoria(self._usuario_financeiro(), "CONFIGURAR_FISCAL", "Fiscal", saved.get("environment", ""), "SUCESSO")
            except Exception as exc:
                status.configure(text=str(exc), text_color="#f85149")
        ctk.CTkButton(content, text="Salvar configuração fiscal", fg_color="#2ea043", command=save).pack(fill="x", padx=16, pady=(8, 6))
        ctk.CTkButton(content, text="Verificar catálogo fiscal", fg_color="#8957e5", command=verify_fiscal_catalog).pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkButton(content, text="Abrir central de documentos fiscais", fg_color="#1f6feb", command=self.abrir_central_fiscal).pack(fill="x", padx=16, pady=(0, 16))

    def abrir_central_fiscal(self):
        if not self._autorizar("fiscal", "view"):
            return
        janela = ctk.CTkToplevel(self)
        janela.title("Central fiscal")
        janela.geometry("980x620")
        janela.minsize(760, 500)
        janela.transient(self)
        frame = ctk.CTkFrame(janela, fg_color="#161b22")
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(frame, text="Documentos e eventos fiscais", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.cor_acento).pack(anchor="w", padx=12, pady=(12, 8))
        ctk.CTkLabel(
            frame, text=f"Arquivos locais: {self.fiscal_service.storage_dir}",
            text_color="#8b949e", anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 6))
        summary_frame = ctk.CTkFrame(frame, fg_color="transparent")
        summary_frame.pack(fill="x", padx=12, pady=(0, 8))
        summary_labels = {}
        for key, title, color in (("authorized","Autorizadas","#2ea043"),("pending","Pendentes","#d29922"),("failed","Com erro","#da3633"),("cancelled","Canceladas","#6e7681"),("total","Total","#1f6feb")):
            label = ctk.CTkLabel(summary_frame, text=f"{title}: 0", fg_color=color, corner_radius=7, height=34, font=ctk.CTkFont(weight="bold"))
            label.pack(side="left", fill="x", expand=True, padx=4)
            summary_labels[key] = label
        filters = ctk.CTkFrame(frame, fg_color="transparent")
        filters.pack(fill="x", padx=12, pady=(0, 8))
        document_search = ctk.CTkEntry(
            filters, placeholder_text="Buscar por chave, protocolo, status, modelo ou ambiente...", height=34
        )
        document_search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        columns = ("tipo", "chave", "status", "protocolo", "data", "ambiente")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for col, title, width in (("tipo","Tipo",100),("chave","Chave / referência",300),("status","Status",120),("protocolo","Protocolo",130),("data","Data",150),("ambiente","Ambiente",110)):
            tree.heading(col, text=title); tree.column(col, width=width, anchor="w")
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.pack(fill="both", expand=True, padx=(12, 28), pady=(0, 24)); yscroll.place(relx=1.0, rely=0.12, relheight=0.76, anchor="ne"); xscroll.pack(fill="x", padx=12, pady=(0, 6))
        rows = {}
        def load():
            for item in tree.get_children(): tree.delete(item)
            rows.clear()
            query = document_search.get().strip().casefold()
            summary = self.fiscal_sale_service.summary()
            for key, label in summary_labels.items():
                title = {"authorized":"Autorizadas","pending":"Pendentes","failed":"Com erro","cancelled":"Canceladas","total":"Total"}[key]
                label.configure(text=f"{title}: {summary[key]}")
            queue_by_id = {str(item.get("id")): item for item in self.fiscal_service.list_transmission_queue()}
            for row in self.fiscal_sale_service.list_sales():
                queue = queue_by_id.get(str(row.get("queue_id")), {})
                merged = dict(row)
                merged.update({
                    "_kind": "VENDA", "_queue": queue,
                    "last_error": row.get("last_error") or queue.get("last_error", ""),
                })
                searchable = " ".join(str(merged.get(field, "")) for field in ("sale_id", "access_key", "protocol", "status", "environment", "last_error")).casefold()
                if query and query not in searchable:
                    continue
                item = tree.insert("", "end", values=(f"VENDA #{row.get('sale_id')}", row.get("access_key",""), row.get("status",""), row.get("protocol",""), row.get("created_at",""), row.get("environment","")))
                rows[item] = merged
            for row in self.fiscal_service.list_documents():
                searchable = " ".join(str(row.get(field, "")) for field in ("access_key", "protocol", "status", "model", "environment", "created_at")).casefold()
                if query and query not in searchable:
                    continue
                item = tree.insert("", "end", values=("DOCUMENTO", row.get("access_key",""), row.get("status",""), row.get("protocol",""), row.get("created_at",""), row.get("environment","")))
                rows[item] = dict(row, _kind="DOCUMENTO")
            for row in self.fiscal_service.list_events():
                searchable = " ".join(str(row.get(field, "")) for field in ("access_key", "protocol", "status_code", "event_type", "environment", "created_at")).casefold()
                if query and query not in searchable:
                    continue
                item = tree.insert("", "end", values=(row.get("event_type","EVENTO"), row.get("access_key",""), row.get("status_code",""), row.get("protocol",""), row.get("created_at",""), ""))
                rows[item] = dict(row, _kind="EVENTO")
        document_search.bind("<Return>", lambda _event: load())
        ctk.CTkButton(filters, text="Buscar", width=90, command=load).pack(side="left")
        def selected():
            selection = tree.selection()
            return rows.get(selection[0]) if selection else None
        def open_files():
            row = selected()
            if not row: return
            path = row.get("processed_path") or row.get("response_path") or row.get("request_path")
            if path and os.path.exists(path):
                self._abrir_arquivo_sistema(path)
            else: messagebox.showwarning("Fiscal", "Arquivo fiscal não localizado.", parent=janela)
        def details():
            row = selected()
            if not row:
                messagebox.showwarning("Central fiscal", "Selecione uma linha.", parent=janela)
                return
            queue = dict(row.get("_queue") or {})
            text = (
                f"Tipo: {row.get('_kind','-')}\nVenda: {row.get('sale_id','-')}\n"
                f"Status: {row.get('status') or row.get('status_code','-')}\n"
                f"Chave: {row.get('access_key','-')}\nProtocolo: {row.get('protocol','-')}\n"
                f"Fila: {row.get('queue_id') or queue.get('id','-')}\n"
                f"Tentativas: {queue.get('attempts','-')}\n\n"
                f"Última informação:\n{row.get('last_error') or queue.get('last_message') or 'Nenhuma pendência registrada.'}"
            )
            messagebox.showinfo("Detalhes fiscais", text, parent=janela)
        def danfe():
            row = selected()
            if not row or not row.get("processed_path"):
                messagebox.showwarning("DANFE", "Selecione um documento autorizado com XML processado.", parent=janela); return
            output = filedialog.asksaveasfilename(parent=janela, defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile=f"DANFE_{row.get('access_key','')}.pdf")
            if not output: return
            try:
                self.fiscal_service.generate_danfe_pdf(authorized_xml=Path(row["processed_path"]).read_bytes(), output_path=output)
                self.mostrar_notificacao("DANFE gerado", output, nivel="success")
            except Exception as exc: messagebox.showerror("DANFE", str(exc), parent=janela)
        today = datetime.now().date()
        period = ctk.CTkFrame(frame, fg_color="transparent")
        period.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkLabel(period, text="Período contábil:").pack(side="left", padx=(4, 6))
        start_entry = ctk.CTkEntry(period, width=115)
        start_entry.pack(side="left", padx=4); start_entry.insert(0, today.replace(day=1).isoformat())
        end_entry = ctk.CTkEntry(period, width=115)
        end_entry.pack(side="left", padx=4); end_entry.insert(0, today.isoformat())
        include_homologation = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            period, text="Incluir homologação (teste)", variable=include_homologation
        ).pack(side="left", padx=12)
        def export_accounting():
            output = filedialog.asksaveasfilename(
                parent=janela, title="Salvar pacote fiscal para a contabilidade",
                defaultextension=".zip", filetypes=[("Pacote ZIP", "*.zip")],
                initialfile=f"NabiCode_Fiscal_{start_entry.get()}_{end_entry.get()}.zip",
            )
            if not output:
                return
            try:
                result = self.fiscal_service.export_accounting_package(
                    start_date=start_entry.get(), end_date=end_entry.get(), output_path=output,
                    include_homologation=include_homologation.get(),
                )
                registrar_auditoria(
                    self._usuario_financeiro(), "EXPORTAR_XML_CONTABILIDADE", "Fiscal",
                    f"{result['period_start']} a {result['period_end']}", "SUCESSO",
                )
                self.mostrar_notificacao(
                    "Pacote fiscal gerado",
                    f"{result['documents']} documento(s) e {result['events']} evento(s).\n{result['path']}",
                    nivel="success", duracao_ms=7000,
                )
            except Exception as exc:
                messagebox.showerror("Exportação fiscal", str(exc), parent=janela)
        transmission_status = ctk.CTkLabel(frame, text="", text_color="#d29922", anchor="w")
        transmission_status.pack(fill="x", padx=16, pady=(0, 3))

        def transmit_queue(*, retry_selected=False):
            if not self._autorizar("fiscal", "configure"):
                return
            row = selected() if retry_selected else None
            if retry_selected:
                if not row or row.get("_kind") != "VENDA":
                    messagebox.showwarning("Central fiscal", "Selecione uma venda fiscal pendente.", parent=janela)
                    return
                queue = dict(row.get("_queue") or {})
                if queue.get("status") == "CONCLUIDO":
                    messagebox.showinfo("Central fiscal", "Este documento já foi concluído.", parent=janela)
                    return
                if queue.get("status") == "CANCELADO" or row.get("status") in {"CANCELADO", "CANCELADO_LOCAL", "CANCELADO_FISCAL"}:
                    messagebox.showinfo("Central fiscal", "Este documento foi cancelado e não pode ser reenviado.", parent=janela)
                    return
                if queue.get("id") and queue.get("status") in {"FALHA", "ERRO"}:
                    self.fiscal_service.retry_transmission(str(queue["id"]), actor=self._usuario_financeiro())
                else:
                    self.fiscal_sale_service.enqueue_pending(
                        sale_id=int(row["sale_id"]), actor=self._usuario_financeiro()
                    )
            password = self._obter_senha_certificado(
                parent=janela, title="Transmitir documentos fiscais"
            )
            if password is None:
                return
            transmission_status.configure(text="Transmitindo em segundo plano. Você pode continuar usando o NabiCode.")
            transmit_button.configure(state="disabled")
            retry_button.configure(state="disabled")
            task = TASK_MANAGER.submit(
                "Transmitir documentos fiscais",
                lambda context: self.fiscal_service.process_transmission_queue(
                    password=password, limit=20
                ),
            )

            def follow():
                nonlocal password
                current = TASK_MANAGER.get(task.id)
                if current is None or not janela.winfo_exists():
                    return
                if current.status == TaskStatus.COMPLETED:
                    processed = current.result or []
                    transmission_status.configure(
                        text=f"Transmissão concluída: {len(processed)} item(ns) processado(s).",
                        text_color="#2ea043",
                    )
                    transmit_button.configure(state="normal")
                    retry_button.configure(state="normal")
                    password = ""
                    load()
                    return
                if current.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
                    transmission_status.configure(text=current.error or "Transmissão cancelada.", text_color="#da3633")
                    transmit_button.configure(state="normal")
                    retry_button.configure(state="normal")
                    password = ""
                    load()
                    return
                janela.after(150, follow)
            janela.after(100, follow)

        def cancel_authorized_sale():
            if not self._autorizar("fiscal", "configure"):
                return
            row = selected()
            if not row or row.get("_kind") != "VENDA" or str(row.get("status")) not in {"AUTORIZADO", "CANCELADO_FISCAL"}:
                messagebox.showwarning("Central fiscal", "Selecione uma venda fiscal autorizada.", parent=janela)
                return
            justification = simpledialog.askstring(
                "Cancelar documento autorizado",
                "Justificativa para a SEFAZ (mínimo 15 caracteres):", parent=janela,
            )
            if justification is None:
                return
            if len(justification.strip()) < 15:
                messagebox.showwarning("Cancelamento fiscal", "Informe ao menos 15 caracteres.", parent=janela)
                return
            password = self._obter_senha_certificado(
                parent=janela, title="Cancelar documento autorizado"
            )
            if password is None:
                return
            if not messagebox.askyesno(
                "Confirmar cancelamento fiscal",
                "O evento será enviado à SEFAZ. Somente após a aceitação estoque e financeiro serão revertidos. Continuar?",
                parent=janela,
            ):
                return
            actor = self._usuario_financeiro()
            sale_id = int(row["sale_id"])
            cancel_button.configure(state="disabled")
            transmission_status.configure(text="Enviando cancelamento à SEFAZ em segundo plano...", text_color="#d29922")

            def work(_context):
                self.fiscal_sale_service.cancel_authorized(
                    sale_id=sale_id, password=password, actor=actor, justification=justification
                )
                self.pdv_transaction_service.cancel_sale(
                    sale_id, user=actor,
                    before_cancel_commit=self.fiscal_sale_service.prepare_local_cancellation,
                )
                self.fiscal_sale_service.finalize_local_cancellation(sale_id=sale_id, actor=actor)
                return sale_id

            task = TASK_MANAGER.submit("Cancelar venda fiscal autorizada", work)

            def follow_cancel():
                nonlocal password
                current = TASK_MANAGER.get(task.id)
                if current is None or not janela.winfo_exists():
                    return
                if current.status == TaskStatus.COMPLETED:
                    password = ""
                    cancel_button.configure(state="normal")
                    transmission_status.configure(text=f"Venda #{sale_id} cancelada na SEFAZ e revertida localmente.", text_color="#2ea043")
                    load()
                    return
                if current.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
                    password = ""
                    cancel_button.configure(state="normal")
                    transmission_status.configure(text=current.error or "Cancelamento não concluído.", text_color="#da3633")
                    load()
                    return
                janela.after(150, follow_cancel)
            janela.after(100, follow_cancel)
        actions = ctk.CTkFrame(frame, fg_color="transparent"); actions.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(actions, text="Atualizar", command=load).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Detalhes", command=details).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Abrir arquivo", command=open_files).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Gerar DANFE", command=danfe).pack(side="left", padx=4)
        transmit_button = ctk.CTkButton(actions, text="Transmitir pendentes", command=transmit_queue, fg_color="#2ea043")
        transmit_button.pack(side="left", padx=4)
        retry_button = ctk.CTkButton(actions, text="Reenviar selecionado", command=lambda: transmit_queue(retry_selected=True), fg_color="#d29922")
        retry_button.pack(side="left", padx=4)
        export_actions = ctk.CTkFrame(frame, fg_color="transparent")
        export_actions.pack(fill="x", padx=12, pady=(0, 10))
        cancel_button = ctk.CTkButton(export_actions, text="Cancelar autorizado", command=cancel_authorized_sale, fg_color="#da3633")
        cancel_button.pack(side="left", padx=4)
        ctk.CTkButton(
            export_actions, text="Abrir pasta fiscal",
            command=lambda: self._abrir_diretorio_sistema(self.fiscal_service.storage_dir),
            fg_color="#8957e5",
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            export_actions, text="Gerar arquivos para contabilidade", command=export_accounting,
            fg_color="#2ea043",
        ).pack(side="left", padx=4)
        load()

    def fazer_backup_config_agora(self):
        self._salvar_opcoes_backup_dos_campos()
        resultado = _servico_backups().create_all("backup_manual")
        if resultado.created:
            texto = "Backup criado em:\n\n" + "\n".join(resultado.created)
            if resultado.errors:
                texto += "\n\nAlguns destinos falharam:\n" + "\n".join(resultado.errors)
            self.mostrar_notificacao("Backup realizado", texto, nivel="success", duracao_ms=7000)
        else:
            messagebox.showerror("Backup", "Não foi possível criar o backup.\n" + "\n".join(resultado.errors))

    def abrir_pasta_backup_config(self):
        pasta = self.entry_backup_local.get().strip() or BACKUP_DIR
        try:
            self._abrir_diretorio_sistema(pasta)
        except Exception as exc:
            messagebox.showerror("Backup", f"Não foi possível abrir a pasta:\n{exc}")

    def _salvar_opcoes_backup_dos_campos(self):
        salvar_config("pasta_backup_local", self.entry_backup_local.get().strip() or BACKUP_DIR)
        salvar_config("pasta_backup_nuvem", self.entry_backup_nuvem.get().strip())
        salvar_config("backup_diario_ativo", "1" if self.var_backup_diario.get() else "0")

    def _confirmar_senha_mestra(self, *, title, prompt, parent=None):
        senha = simpledialog.askstring(
            title,
            prompt,
            show="*",
            parent=parent or self,
        )
        if senha is None:
            return False
        if not self.security.verify_master_password(senha):
            messagebox.showerror(
                title,
                "Senha mestra inválida. Nenhuma alteração protegida foi aplicada.",
                parent=parent or self,
            )
            return False
        return True

    def salvar_configuracoes_gerais(self):
        modo_anterior = (obter_config("modo_operacao") or "COMERCIAL").strip().upper()
        modo_operacao_texto = self.combo_modo_operacao.get() if hasattr(self, "combo_modo_operacao") else "COMERCIAL"
        modo_novo = "FISCAL" if modo_operacao_texto.startswith("FISCAL") else "COMERCIAL"
        modo_alterado = modo_anterior != modo_novo
        if modo_alterado and not self._confirmar_senha_mestra(
            title="Alterar modo Comercial/Fiscal",
            prompt=(
                f"A mudança de {modo_anterior} para {modo_novo} altera regras do PDV e "
                "o acesso às ferramentas fiscais.\n\nDigite a senha mestra para confirmar."
            ),
            parent=self,
        ):
            self.combo_modo_operacao.set(
                "FISCAL — com recursos fiscais"
                if modo_anterior == "FISCAL"
                else "COMERCIAL — sem emissão fiscal"
            )
            return
        novo_nome = self.entry_cfg_loja.get().strip()
        novo_tel = self.entry_cfg_tel.get().strip()
        novo_endereco = self.entry_cfg_endereco.get().strip()
        novo_cnpj = self.entry_cfg_cnpj.get().strip()
        novo_email = self.entry_cfg_email.get().strip()
        aparencia = self.combo_aparencia.get() or "Dark"
        cor_nome = self.combo_cor_destaque.get() or "Verde Nabi"

        if novo_nome:
            salvar_config("nome_loja", novo_nome)
        if novo_tel:
            salvar_config("telefone", novo_tel)
        salvar_config("endereco", novo_endereco)
        salvar_config("cnpj", novo_cnpj)
        salvar_config("email", novo_email)
        salvar_config("aparencia_sistema", aparencia)
        salvar_config("cor_destaque", cor_nome)
        salvar_config("modo_operacao", modo_novo)
        self._salvar_preferencias_interface()
        self._salvar_opcoes_backup_dos_campos()
        try:
            duracao_segundos = float((self.entry_duracao_notificacoes.get() or "4.2").replace(",", "."))
        except (TypeError, ValueError):
            messagebox.showerror("Notificações", "Informe uma duração válida em segundos.", parent=self)
            return
        duracao_ms = self.notification_center.set_default_duration(duracao_segundos * 1000)
        CORE_CONFIG.set("notificacoes.duracao_ms", duracao_ms)
        self._aplicar_personalizacao(aparencia, cor_nome)
        if hasattr(self, "background_manager"):
            self.background_manager.refresh(immediate=True)
        self._aplicar_visibilidade_navegacao()
        self._reconstruir_menu_favoritos()

        mensagem_config = "As configurações foram aplicadas."
        if modo_alterado:
            mensagem_config += " Reinicie o NabiCode para reconstruir menus e telas conforme o novo modo Comercial/Fiscal."
        self.mostrar_notificacao(
            "Configurações salvas", mensagem_config, nivel="success",
        )
        if modo_alterado:
            messagebox.showinfo("Modo de operação alterado", mensagem_config, parent=self)
        self.mostrar_tela("dashboard")

    def abrir_restauracao_fabrica(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Restaurar padrão de fábrica")
        janela.geometry("820x700")
        janela.minsize(760, 620)
        janela.configure(fg_color="#0d1117")
        self._preparar_janela_modal(janela, self)

        ctk.CTkLabel(
            janela,
            text="🏭 Restaurar padrão de fábrica",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color="#f85149",
        ).pack(pady=(18, 5))
        ctk.CTkLabel(
            janela,
            text="Escolha o nível de restauração. Antes de executar, o sistema mostrará uma confirmação e pedirá a senha administrativa.",
            text_color="#c9d1d9",
            wraplength=740,
            justify="center",
        ).pack(pady=(0, 12))

        corpo = BidirectionalScrollableFrame(janela, fg_color="#161b22", content_width=730)
        corpo.pack(fill="both", expand=True, padx=18, pady=6)
        area = corpo.content
        area.grid_columnconfigure(0, weight=1)

        opcao = tk.StringVar(value="APPEARANCE")
        modos = (
            "APPEARANCE", "PERSONALIZATION", "SETTINGS", "TEST_DATA", "OPERATIONAL_DATA", "COMPLETE",
        )
        preview = ctk.CTkTextbox(area, height=165, wrap="word")

        def atualizar_previa(*_args):
            try:
                plano = FACTORY_RESET_SERVICE.plan(opcao.get())
                linhas = [plano.title, "", plano.description]
                if plano.affected_tables:
                    linhas.extend(["", f"Registros atualmente afetados: {plano.total_rows}"])
                    for tabela, quantidade in plano.row_counts.items():
                        if quantidade:
                            linhas.append(f"• {tabela}: {quantidade}")
                else:
                    linhas.extend(["", "Nenhum cadastro ou movimento será apagado."])
                linhas.extend(["", "Backup validado obrigatório: SIM"])
                preview.configure(state="normal")
                preview.delete("1.0", "end")
                preview.insert("1.0", "\n".join(linhas))
                preview.configure(state="disabled")
            except Exception as exc:
                preview.configure(state="normal")
                preview.delete("1.0", "end")
                preview.insert("1.0", f"Não foi possível calcular a prévia:\n{exc}")
                preview.configure(state="disabled")

        for indice, modo in enumerate(modos):
            titulo, descricao, _confirmacao = FactoryResetService.MODES[modo]
            bloco = ctk.CTkFrame(area, fg_color="#0d1117", corner_radius=8)
            bloco.grid(row=indice, column=0, sticky="ew", padx=10, pady=6)
            ctk.CTkRadioButton(
                bloco,
                text=titulo,
                variable=opcao,
                value=modo,
                command=atualizar_previa,
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(anchor="w", padx=12, pady=(10, 3))
            ctk.CTkLabel(
                bloco,
                text=descricao,
                text_color="#8b949e",
                wraplength=650,
                justify="left",
            ).pack(anchor="w", padx=34, pady=(0, 10))

        ctk.CTkLabel(
            area,
            text="Prévia do impacto",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=6, column=0, sticky="w", padx=10, pady=(12, 3))
        preview.grid(row=7, column=0, sticky="ew", padx=10, pady=(0, 12))

        def aplicar_configuracoes(modo):
            if modo in {"APPEARANCE", "PERSONALIZATION", "SETTINGS", "COMPLETE"}:
                salvar_config("aparencia_sistema", "Dark")
                salvar_config("cor_destaque", "Verde Nabi")
            if modo in {"PERSONALIZATION", "SETTINGS", "COMPLETE"}:
                CORE_CONFIG.set("interface", UIPreferencesService.DEFAULTS)
                CORE_CONFIG.set("interface_usuarios", {})
            if modo in {"SETTINGS", "COMPLETE"}:
                defaults = {
                    "backup_diario_ativo": "1",
                    "impressora_recibo": "Padrão do Sistema",
                    "impressora_entrega": "Padrão do Sistema",
                    "impressora_ficha": "Padrão do Sistema",
                    "impressora_historico": "Padrão do Sistema",
                    "formato_impressao_recibo": "Cupom 80 mm",
                    "formato_impressao_entrega": "Cupom 80 mm",
                    "formato_impressao_ficha": "A4",
                    "formato_impressao_historico": "A4",
                    "impressao_acao_pos_pdf": "PERGUNTAR",
                    "login_usuarios_habilitado": "0",
                    "login_usuarios_configurado": "1",
                    "login_inicio_consentido_v2440": "0",
                    "login_inicio_ativado_pelo_usuario_v2442": "0",
                    "login_politica_v2442_inicializada": "1",
                }
                for chave, valor in defaults.items():
                    salvar_config(chave, valor)

        def solicitar_autorizacao_e_executar():
            modo = opcao.get()
            plano = FACTORY_RESET_SERVICE.plan(modo)

            auth = ctk.CTkToplevel(janela)
            auth.title("Autorizar restauração")
            auth.geometry("520x360" if modo in {"TEST_DATA", "OPERATIONAL_DATA", "COMPLETE"} else "520x285")
            auth.resizable(False, False)
            auth.configure(fg_color="#0d1117")
            self._preparar_janela_modal(auth, janela)

            ctk.CTkLabel(
                auth,
                text="Confirmação administrativa",
                font=ctk.CTkFont(size=19, weight="bold"),
                text_color="#f85149",
            ).pack(pady=(22, 8))
            ctk.CTkLabel(
                auth,
                text=plano.title,
                text_color="#c9d1d9",
                wraplength=455,
                justify="center",
            ).pack(padx=24, pady=(0, 14))

            ctk.CTkLabel(auth, text="Senha administrativa ou senha mestra").pack(anchor="w", padx=34, pady=(0, 4))
            senha = ctk.CTkEntry(auth, show="●", height=40)
            senha.pack(fill="x", padx=34)

            confirmacao = None
            if modo in {"TEST_DATA", "OPERATIONAL_DATA", "COMPLETE"}:
                ctk.CTkLabel(
                    auth,
                    text="Digite APAGAR TUDO para confirmar",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).pack(anchor="w", padx=34, pady=(14, 4))
                confirmacao = ctk.CTkEntry(auth, height=40)
                confirmacao.pack(fill="x", padx=34)

            def executar_confirmado():
                if not self._senha_administrativa_valida(senha.get()):
                    messagebox.showerror("Padrão de fábrica", "Senha administrativa inválida.", parent=auth)
                    senha.focus_set()
                    senha.select_range(0, "end")
                    return
                typed_confirmation = confirmacao.get() if confirmacao is not None else ""
                try:
                    backup_path, plano_exec = FACTORY_RESET_SERVICE.execute(
                        modo,
                        typed_confirmation=typed_confirmation,
                        apply_configuration_reset=aplicar_configuracoes,
                    )
                    registrar_auditoria(
                        "Configurações",
                        "PADRAO_FABRICA",
                        objeto=modo,
                        detalhes=f"backup={backup_path}; registros={plano_exec.total_rows}",
                        usuario="Administrador",
                    )
                    messagebox.showinfo(
                        "Padrão de fábrica",
                        f"Operação concluída.\nBackup validado: {backup_path}\nRegistros afetados: {plano_exec.total_rows}\n\nO NabiCode será fechado para reabrir com estado consistente.",
                        parent=auth,
                    )
                    auth.destroy()
                    janela.destroy()
                    self.after(150, self.destroy)
                except Exception as exc:
                    registrar_auditoria(
                        "Configurações",
                        "PADRAO_FABRICA",
                        objeto=modo,
                        detalhes=str(exc),
                        resultado="ERRO",
                        usuario="Administrador",
                    )
                    messagebox.showerror("Padrão de fábrica", str(exc), parent=auth)
                    auth.lift()
                    auth.focus_force()

            botoes_auth = ctk.CTkFrame(auth, fg_color="transparent")
            botoes_auth.pack(fill="x", padx=34, pady=22)
            ctk.CTkButton(botoes_auth, text="Cancelar", command=auth.destroy, fg_color="#30363d").pack(side="left")
            ctk.CTkButton(
                botoes_auth,
                text="Confirmar e executar",
                command=executar_confirmado,
                fg_color="#da3633",
                hover_color="#b62324",
            ).pack(side="right")
            auth.bind("<Escape>", lambda _event: auth.destroy())
            auth.bind("<Return>", lambda _event: executar_confirmado())
            senha.after(120, senha.focus_force)

        botoes = ctk.CTkFrame(janela, fg_color="#0d1117")
        botoes.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkButton(botoes, text="Cancelar", command=janela.destroy, fg_color="#30363d").pack(side="left")
        ctk.CTkButton(
            botoes,
            text="Continuar e informar senha",
            command=solicitar_autorizacao_e_executar,
            fg_color="#da3633",
            hover_color="#b62324",
        ).pack(side="right")
        janela.bind("<Escape>", lambda _event: janela.destroy())
        opcao.trace_add("write", atualizar_previa)
        atualizar_previa()

    def abrir_robo_ajuda(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Central de Ajuda")
        janela.geometry("760x590")
        janela.minsize(700, 520)
        janela.configure(fg_color="#0d1117")
        janela.transient(self)

        ctk.CTkLabel(janela, text="🆘 Central de Ajuda", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.cor_acento).pack(pady=(18, 5))
        ctk.CTkLabel(janela, text="Pesquise um assunto ou escolha uma orientação rápida.", text_color="#c9d1d9").pack(pady=(0, 12))
        busca = ctk.CTkEntry(janela, placeholder_text="Ex.: cadastrar cliente, ficha, venda, pagamento, backup, impressora...", height=40)
        busca.pack(fill="x", padx=24, pady=6)
        resposta = ctk.CTkTextbox(janela, wrap="word")
        resposta.pack(fill="both", expand=True, padx=24, pady=10)

        topicos = {
            "cliente": "CLIENTES E FICHAS\n1. Abra Clientes.\n2. Clique em Novo Cliente.\n3. Confira a ficha sugerida, preencha os dados e salve.\n4. A ficha pode ser alterada manualmente, mas não pode se repetir.",
            "ficha": "FICHAS\nA numeração automática começa em 5500 e continua pelo banco. Fichas antigas podem ser informadas manualmente sem reduzir a sequência automática.",
            "venda": "VENDAS\nAbra Vendas, selecione o cliente, adicione os itens e finalize. O formato de impressão segue a configuração: cupom 80 mm, A4 ou PDF virtual.",
            "pagamento": "PAGAMENTOS\nSelecione o cliente e registre o recebimento. Confira o valor, a forma de pagamento e o saldo restante antes de confirmar.",
            "backup": "BACKUP\nEm Configurações, use Fazer backup agora. Para restauração e ferramentas avançadas, o suporte técnico utiliza o Menu Técnico.",
            "impressora": "IMPRESSÃO\nEm Configurações, abra Configurar Impressoras. Escolha o formato correto e a impressora instalada, salve e use o botão Testar.",
            "whatsapp": "COBRANÇA PELO WHATSAPP\nAbra o cliente, clique em Editar e use Cobrar Cliente. A mensagem usa o nome da loja, o telefone e o saldo cadastrados.",
            "rede": "REDE\nA configuração de banco compartilhado é técnica. Entre em contato com o suporte para evitar apontar o sistema para um banco incorreto.",
        }

        def mostrar(texto):
            resposta.configure(state="normal"); resposta.delete("1.0", "end"); resposta.insert("end", texto); resposta.configure(state="disabled")
        def pesquisar(event=None):
            termo = busca.get().strip().lower()
            if not termo:
                mostrar("Digite um assunto no campo acima."); return
            encontrados = [v for k,v in topicos.items() if k in termo or termo in k or any(p in termo for p in k.split())]
            mostrar("\n\n".join(encontrados) if encontrados else "Não encontrei esse assunto. Use o botão Abrir chamado para falar com o suporte.")
        SearchEntryBehavior.attach(busca, on_enter=pesquisar)
        ctk.CTkButton(janela, text="🔎 Pesquisar", command=pesquisar).pack(fill="x", padx=24, pady=(0, 8))

        botoes = ctk.CTkFrame(janela, fg_color="transparent"); botoes.pack(fill="x", padx=24, pady=(0, 18))
        for titulo, chave in (("Clientes", "cliente"), ("Vendas", "venda"), ("Backup", "backup"), ("Impressão", "impressora")):
            ctk.CTkButton(botoes, text=titulo, command=lambda c=chave: mostrar(topicos[c]), width=120).pack(side="left", expand=True, fill="x", padx=3)
        ctk.CTkButton(botoes, text="📲 Abrir chamado", fg_color="#2ea043", command=self.abrir_chamado_suporte).pack(side="left", expand=True, fill="x", padx=3)
        mostrar("Bem-vindo à Central de Ajuda. Escolha um assunto ou faça uma pesquisa.")

    def abrir_chamado_suporte(self):
        loja = obter_config("nome_loja") or "Loja não identificada"
        info = (
            f"Olá, preciso de suporte no sistema.\n\n"
            f"Loja: {loja}\nVersão: {APP_VERSION} - {APP_VERSION_LABEL}\n"
            f"Computador: {socket.gethostname()}\nWindows: {platform.platform()}\n"
            f"Modo do banco: {'Rede compartilhada' if MODO_REDE else 'Local'}\n"
            f"Caminho do banco: {DB_NAME}\n\nProblema: "
        )
        telefone_suporte = re.sub(r"\D", "", obter_config("whatsapp_suporte") or obter_config("telefone") or "")
        if not telefone_suporte:
            messagebox.showinfo("Suporte", "Cadastre o WhatsApp de suporte nas configurações da loja para abrir chamados automaticamente.")
            return
        webbrowser.open(f"https://wa.me/55{telefone_suporte}?text={urllib.parse.quote(info)}")

    def gatilho_menu_secreto(self, event):
        agora = datetime.now().timestamp()
        if agora - getattr(self, "_ultimo_clique_dev", 0) > 5:
            self.clicks_dev = 0
        self._ultimo_clique_dev = agora
        self.clicks_dev += 1
        if self.clicks_dev < 10:
            return
        self.clicks_dev = 0
        self.abrir_login_admin()

    def abrir_login_admin(self):
        if not self._autorizar("technical", "view"):
            return
        janela = ctk.CTkToplevel(self)
        janela.title("Acesso ao Menu Técnico")
        janela.geometry("430x270")
        janela.resizable(False, False)
        janela.configure(fg_color="#0d1117")
        janela.transient(self)
        janela.grab_set()

        ctk.CTkLabel(janela, text="🔐 Menu Técnico", font=ctk.CTkFont(size=20, weight="bold"), text_color="#00FF88").pack(pady=(25, 8))
        ctk.CTkLabel(janela, text="Digite a senha técnica para continuar.", text_color="#c9d1d9").pack(pady=(0, 12))
        entrada = ctk.CTkEntry(janela, placeholder_text="Senha administrativa", show="●", height=40)
        entrada.pack(fill="x", padx=35, pady=6)
        entrada.focus_set()

        def confirmar(event=None):
            senha = entrada.get()
            valido = self._senha_administrativa_valida(senha)
            if valido:
                self._registrar_acesso_admin(True, "Acesso autorizado ao painel administrativo.")
                janela.destroy()
                self.abrir_painel_admin()
            else:
                self._registrar_acesso_admin(False, "Tentativa de acesso com senha incorreta.")
                entrada.delete(0, "end")
                messagebox.showerror("Acesso negado", "Senha administrativa incorreta.", parent=janela)
                entrada.focus_set()

        ctk.CTkButton(janela, text="Entrar", height=40, fg_color="#2ea043", hover_color="#238636", command=confirmar).pack(fill="x", padx=35, pady=(12, 5))
        entrada.bind("<Return>", confirmar)
        janela.bind("<Escape>", lambda e: janela.destroy())

    def abrir_painel_admin(self):
        if not self._autorizar("technical", "view"):
            return
        janela = ctk.CTkToplevel(self)
        janela.title("NabiCode — Painel Administrativo")
        janela.geometry("1000x720")
        janela.minsize(860, 640)
        janela.configure(fg_color="#0d1117")
        janela.transient(self)
        janela.grab_set()

        ctk.CTkLabel(janela, text="🛠 Painel Administrativo NabiCode", font=ctk.CTkFont(size=22, weight="bold"), text_color="#00FF88").pack(pady=(14, 4))
        ctk.CTkLabel(
            janela, text="Escolha uma área técnica no cardápio abaixo.", text_color="#8b949e"
        ).pack(pady=(0, 8))
        menu_cards = ctk.CTkFrame(janela, fg_color="#161b22", corner_radius=10)
        menu_cards.pack(fill="x", padx=16, pady=(0, 8))
        abas = ctk.CTkTabview(janela, fg_color="#161b22", segmented_button_selected_color="#2ea043")
        abas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        admin_sections = (
            ("Licença", "🔑", "Validade e bloqueio"),
            ("Banco de Dados", "🗄", "Integridade e reparo"),
            ("Backup", "💾", "Cópias e restauração"),
            ("Atualizações", "⬆", "Versões e snapshots"),
            ("Padrão de fábrica", "🏭", "Restauração protegida"),
            ("Diagnóstico", "🩺", "Saúde do sistema"),
            ("Migração", "🔄", "Importar bases"),
            ("Demonstração", "🧪", "Dados de exemplo"),
            ("Ferramentas", "🧰", "Utilitários técnicos"),
            ("Sistema", "🖥", "Informações locais"),
            ("Segurança", "🛡", "Acessos e auditoria"),
            ("Suporte", "🆘", "Ajuda e atendimento"),
        )
        for nome, _icone, _descricao in admin_sections:
            abas.add(nome)
        try:
            abas._segmented_button.grid_remove()
        except (AttributeError, tk.TclError):
            pass
        admin_card_buttons = {}
        def selecionar_secao_admin(nome):
            abas.set(nome)
            for section_name, component in admin_card_buttons.items():
                selected = section_name == nome
                component.configure(
                    fg_color="#2ea043" if selected else "#21262d",
                    hover_color="#238636" if selected else "#30363d",
                    border_width=2 if selected else 1,
                    border_color="#58d68d" if selected else "#30363d",
                )
        for index, (nome, icone, descricao) in enumerate(admin_sections):
            row, column = divmod(index, 4)
            card = ctk.CTkButton(
                menu_cards, text=f"{icone}  {nome}\n{descricao}", anchor="w",
                height=54, corner_radius=8, fg_color="#21262d", hover_color="#30363d",
                border_width=1, border_color="#30363d",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda section=nome: selecionar_secao_admin(section),
            )
            card.grid(row=row, column=column, sticky="ew", padx=5, pady=5)
            admin_card_buttons[nome] = card
        for column in range(4):
            menu_cards.grid_columnconfigure(column, weight=1, uniform="admin_cards")
        selecionar_secao_admin("Licença")

        def botao(parent, texto, comando, cor="#1f6feb"):
            componente = ctk.CTkButton(parent, text=texto, command=comando, height=38, fg_color=cor)
            componente.pack(fill="x", padx=18, pady=6)
            return componente

        def executar_tarefa_ui(nome, trabalho, ao_concluir, ao_falhar, ao_progresso=None):
            """Executa trabalho fora da thread gráfica e consulta o estado via after()."""
            # O painel administrativo nasce modal. Durante tarefas demoradas, liberar
            # o grab mantém o restante do NabiCode utilizável sem tocar no Tk pelo worker.
            if janela.grab_current() == janela:
                janela.grab_release()
            tarefa = TASK_MANAGER.submit(nome, trabalho)

            def acompanhar():
                atual = TASK_MANAGER.get(tarefa.id)
                if atual is None or not janela.winfo_exists():
                    return
                if ao_progresso:
                    ao_progresso(atual.progress, atual.message, atual.status)
                if atual.status == TaskStatus.COMPLETED:
                    ao_concluir(atual.result)
                    return
                if atual.status == TaskStatus.FAILED:
                    ao_falhar(atual.error or "Falha não identificada.")
                    return
                if atual.status == TaskStatus.CANCELLED:
                    ao_falhar("Operação cancelada.")
                    return
                janela.after(100, acompanhar)

            janela.after(50, acompanhar)
            return tarefa

        # LICENÇA
        aba = abas.tab("Licença")
        lbl_validade = ctk.CTkLabel(aba, text="", font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffd700")
        lbl_validade.pack(pady=(20, 10))
        def atualizar_licenca():
            validade, bloqueada = _ADMIN_OPERATIONS.license_status()
            lbl_validade.configure(text=f"Validade: {validade}  |  Situação: {'BLOQUEADA' if bloqueada else 'ATIVA'}")
        def renovar(dias):
            nova = _ADMIN_OPERATIONS.renew_license(dias)
            atualizar_licenca()
            messagebox.showinfo("Licença", f"Licença renovada até {nova}.", parent=janela)
        botao(aba, "➕ Renovar por 30 dias", lambda: renovar(30))
        botao(aba, "⭐ Renovar por 365 dias", lambda: renovar(365), "#2ea043")
        def teste_um_minuto():
            if not messagebox.askyesno("Teste de licença", "Ativar licença de teste por 1 minuto? Ao expirar, o sistema será bloqueado para validar o funcionamento.", parent=janela):
                return
            limite = _ADMIN_OPERATIONS.activate_test_license()
            lbl_validade.configure(text=f"TESTE ATIVO até {limite:%d/%m/%Y %H:%M:%S}")
            messagebox.showinfo("Teste de licença", "Teste iniciado. O bloqueio será acionado automaticamente em 1 minuto.", parent=janela)
        botao(aba, "🧪 Licença de teste — 1 minuto", teste_um_minuto, "#9e6a03")
        def alternar_bloqueio():
            _ADMIN_OPERATIONS.toggle_license_block()
            atualizar_licenca()
        botao(aba, "🔒 Bloquear / Desbloquear licença", alternar_bloqueio, "#da3633")
        atualizar_licenca()

        # BANCO
        aba = abas.tab("Banco de Dados")
        resultado_bd = ctk.CTkTextbox(aba, height=180)
        resultado_bd.pack(fill="both", expand=True, padx=18, pady=(18, 8))
        def executar_bd(acao):
            try:
                relatorio = _ADMIN_OPERATIONS.run_database_action(acao)
                resultado_bd.delete("1.0", "end")
                resultado_bd.insert("end", database_report_text(relatorio))
            except Exception as exc:
                messagebox.showerror("Banco de dados", str(exc), parent=janela)
        frame_bd = ctk.CTkFrame(aba, fg_color="transparent"); frame_bd.pack(fill="x", padx=12, pady=8)
        for txt, acao in (("Verificar integridade", "integridade"), ("Reparar", "reparar"), ("Reindexar", "reindex"), ("Compactar (VACUUM)", "vacuum")):
            ctk.CTkButton(frame_bd, text=txt, command=lambda a=acao: executar_bd(a)).pack(side="left", expand=True, fill="x", padx=4)

        # BACKUP
        aba = abas.tab("Backup")
        ctk.CTkLabel(aba, text="Ferramentas administrativas de segurança do banco", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 12))
        def criar_backup_admin():
            try:
                destino, relatorio = _ADMIN_OPERATIONS.create_backup()
                messagebox.showinfo("Backup", f"Backup criado e validado em:\n{destino}\n\nSchema: {relatorio.schema_version}", parent=janela)
            except Exception as exc:
                messagebox.showerror("Backup", str(exc), parent=janela)

        def restaurar_backup_admin():
            origem = filedialog.askopenfilename(parent=janela, title="Selecionar backup", filetypes=[("Banco SQLite", "*.db"), ("Todos", "*.*")])
            if not origem:
                return
            if not messagebox.askyesno(
                "Restauração",
                "O backup será validado e uma cópia de segurança do banco atual será criada antes da restauração. Continuar?",
                parent=janela,
            ):
                return
            try:
                seguranca, relatorio = _ADMIN_OPERATIONS.restore_backup(origem)
                messagebox.showinfo("Restauração", f"Banco restaurado e validado.\nBackup de segurança: {seguranca}\nSchema: {relatorio.schema_version}\n\nReinicie o sistema.", parent=janela)
            except Exception as exc:
                messagebox.showerror("Restauração", str(exc), parent=janela)
        def abrir_pasta_backup():
            self._abrir_diretorio_sistema(BACKUP_DIR)
        def limpar_backups():
            mantidos = _ADMIN_OPERATIONS.cleanup_backups(10)
            messagebox.showinfo("Backup", f"Limpeza concluída. Mantidos {mantidos} backups recentes.", parent=janela)
        botao(aba, "💾 Criar backup agora", criar_backup_admin, "#2ea043")
        botao(aba, "♻ Restaurar backup", restaurar_backup_admin, "#8957e5")
        botao(aba, "📂 Abrir pasta de backups", abrir_pasta_backup)
        botao(aba, "🧹 Limpar backups antigos", limpar_backups, "#da3633")

        # ATUALIZAÇÕES, PACOTES E ROLLBACK
        aba = abas.tab("Atualizações")
        revisao_instalada = _ADMIN_OPERATIONS.update_service().current_revision
        ctk.CTkLabel(aba, text="Atualização segura do NabiCode", font=ctk.CTkFont(size=17, weight="bold"), text_color="#00FF88").pack(pady=(14, 5))
        ctk.CTkLabel(
            aba,
            text=f"Instalado: {APP_VERSION} R{revisao_instalada}. Selecione um pacote oficial .zip; o sistema valida, cria snapshot e aplica após fechar.",
            text_color="#c9d1d9", wraplength=760, justify="center"
        ).pack(pady=(0, 8))

        pacote_var = tk.StringVar(value="Nenhum pacote selecionado.")
        pacote_selecionado = {"path": None, "manifest": None}
        avisos_atualizacao = {}
        status_pacote = ctk.CTkLabel(aba, textvariable=pacote_var, text_color="#8b949e", wraplength=760, justify="left")
        status_pacote.pack(fill="x", padx=18, pady=(2, 8))

        def mostrar_aviso_atualizacao(titulo, detalhes, *, erro=False):
            """Aviso recuperável, minimizável e sem bloquear a janela principal."""
            existente = avisos_atualizacao.get("janela")
            try:
                if existente is not None and existente.winfo_exists():
                    existente.deiconify(); existente.lift()
                    return
            except tk.TclError:
                pass
            aviso = ctk.CTkToplevel(self)
            avisos_atualizacao["janela"] = aviso
            aviso.title(f"NabiCode — {titulo}")
            aviso.geometry("620x330")
            aviso.minsize(520, 280)
            aviso.configure(fg_color="#0d1117")
            ctk.CTkLabel(
                aviso, text=titulo, font=ctk.CTkFont(size=20, weight="bold"),
                text_color="#ff6b6b" if erro else "#f0b429",
            ).pack(anchor="w", padx=28, pady=(24, 10))
            ctk.CTkLabel(
                aviso, text=str(detalhes), wraplength=550, justify="left", anchor="w",
                text_color="#c9d1d9",
            ).pack(fill="x", padx=28, pady=(0, 18))
            botoes = ctk.CTkFrame(aviso, fg_color="transparent")
            botoes.pack(side="bottom", fill="x", padx=24, pady=22)

            def copiar():
                aviso.clipboard_clear(); aviso.clipboard_append(str(detalhes))

            def fechar():
                avisos_atualizacao.pop("janela", None)
                aviso.destroy()

            ctk.CTkButton(botoes, text="Minimizar", fg_color="#30363d", command=aviso.iconify).pack(side="left", padx=4)
            ctk.CTkButton(botoes, text="Copiar detalhes", fg_color="#1f6feb", command=copiar).pack(side="left", padx=4)
            ctk.CTkButton(botoes, text="Fechar", command=fechar).pack(side="right", padx=4)
            aviso.protocol("WM_DELETE_WINDOW", fechar)
            aviso.lift()

        def _validar_pacote_atualizacao(caminho):
            return _ADMIN_OPERATIONS.validate_update_package(caminho)

        def selecionar_pacote_atualizacao():
            caminho = filedialog.askopenfilename(
                parent=janela, title="Selecionar pacote de atualização NabiCode",
                filetypes=[("Pacote NabiCode", "*.zip"), ("Todos", "*.*")]
            )
            if not caminho:
                return
            try:
                manifesto = _validar_pacote_atualizacao(caminho)
                pacote_selecionado.update(path=caminho, manifest=manifesto)
                pacote_var.set(
                    f"Pacote validado: {manifesto['version']} R{manifesto.get('revision', 0)} — {Path(caminho).name}"
                )
                btn_aplicar_pacote.configure(state="normal")
            except Exception as exc:
                pacote_selecionado.update(path=None, manifest=None)
                btn_aplicar_pacote.configure(state="disabled")
                mesma_revisao = "não é mais novo" in str(exc).lower()
                pacote_var.set("Nenhuma atualização necessária." if mesma_revisao else "Pacote rejeitado.")
                mostrar_aviso_atualizacao(
                    "Nenhuma atualização necessária" if mesma_revisao else "Pacote de atualização rejeitado",
                    str(exc), erro=not mesma_revisao,
                )

        def aplicar_pacote_atualizacao():
            caminho = pacote_selecionado.get("path")
            manifesto = pacote_selecionado.get("manifest")
            if not caminho or not manifesto:
                return
            senha = simpledialog.askstring(
                "Autorizar atualização",
                "Senha administrativa ou senha mestra:",
                show="●",
                parent=janela,
            )
            if senha is None:
                return
            if not self._senha_administrativa_valida(senha):
                messagebox.showerror("Atualização", "Senha administrativa inválida.", parent=janela)
                return
            texto_confirmacao = (
                f"Aplicar {manifesto['version']} R{manifesto.get('revision', 0)}?\n\n"
                f"Origem aceita: {', '.join(manifesto.get('accepted_source_versions') or ['qualquer versão compatível'])}.\n"
                "Será criado snapshot do banco e backup dos arquivos alterados. "
                "Após reiniciar, arquivos e banco serão validados automaticamente. "
                "Qualquer falha provoca rollback."
            )
            if not messagebox.askyesno("Confirmar atualização", texto_confirmacao, parent=janela):
                return
            try:
                snapshot = criar_snapshot_sistema(
                    f"antes_atualizacao_{manifesto['version'].replace('.', '_')}_r{manifesto.get('revision', 0)}"
                )
                state, command, update_cwd = _ADMIN_OPERATIONS.prepare_update(
                    caminho, manifesto, snapshot["id"], executable=sys.executable,
                    source_dir=SOURCE_DIR, frozen=getattr(sys, "frozen", False), pid=os.getpid(),
                )
                registrar_auditoria(
                    self._usuario_financeiro(),
                    "ATUALIZAR_SISTEMA",
                    APP_VERSION,
                    f"{manifesto['version']} R{manifesto.get('revision', 0)}",
                    "PREPARADO",
                )
                messagebox.showinfo(
                    "Atualização",
                    f"Pacote preparado.\nSnapshot: {snapshot['id']}\n"
                    f"Backup de arquivos: {state['file_backup']}\n\n"
                    "O NabiCode será fechado, atualizado, reaberto e validado.",
                    parent=janela,
                )
                subprocess.Popen(
                    command,
                    cwd=update_cwd,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
                self.after(150, self.destroy)
            except Exception as exc:
                try:
                    _ADMIN_OPERATIONS.register_update_prepare_failure(manifesto, exc)
                except Exception:
                    pass
                messagebox.showerror("Atualização", str(exc), parent=janela)

        linha_pacote = ctk.CTkFrame(aba, fg_color="transparent")
        linha_pacote.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(linha_pacote, text="📦 Selecionar pacote .zip", command=selecionar_pacote_atualizacao, fg_color="#1f6feb").pack(side="left", fill="x", expand=True, padx=4)
        btn_aplicar_pacote = ctk.CTkButton(linha_pacote, text="⬆ Aplicar atualização", command=aplicar_pacote_atualizacao, fg_color="#2ea043", state="disabled")
        btn_aplicar_pacote.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkLabel(aba, text="Snapshots e rollback", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffd700").pack(pady=(8, 3))
        lista_snapshots = ctk.CTkTextbox(aba, height=150)
        lista_snapshots.pack(fill="both", expand=True, padx=18, pady=6)
        snapshots_cache = []

        def atualizar_lista_snapshots():
            nonlocal snapshots_cache
            snapshots_cache = listar_snapshots_sistema()
            linhas = []
            for indice, item in enumerate(snapshots_cache, 1):
                linhas.append(f"{indice}. {item.get('id', 'sem id')} | {'VÁLIDO' if item.get('valido') else 'INVÁLIDO'} | {item.get('motivo', '')}")
            lista_snapshots.delete("1.0", "end")
            lista_snapshots.insert("end", "\n".join(linhas) if linhas else "Nenhum snapshot criado.")

        def criar_snapshot_ui():
            botao_snapshot.configure(state="disabled", text="Criando snapshot...")
            def trabalho(ctx):
                ctx.report_progress(0.1, "Preparando snapshot")
                item = criar_snapshot_sistema("manual_menu_tecnico")
                ctx.report_progress(1.0, "Snapshot validado")
                return item
            def concluir(item):
                botao_snapshot.configure(state="normal", text="📸 Criar snapshot verificado")
                atualizar_lista_snapshots()
                messagebox.showinfo("Snapshot", f"Snapshot criado e validado:\n{item['id']}", parent=janela)
            def falhar(erro):
                botao_snapshot.configure(state="normal", text="📸 Criar snapshot verificado")
                messagebox.showerror("Snapshot", erro, parent=janela)
            executar_tarefa_ui("Criar snapshot", trabalho, concluir, falhar)

        def restaurar_ultimo_snapshot_ui():
            validos = [item for item in snapshots_cache if item.get("valido")]
            if not validos:
                messagebox.showwarning("Rollback", "Não existe snapshot válido para restauração.", parent=janela)
                return
            item = validos[0]
            if not messagebox.askyesno("Confirmar rollback", f"Restaurar o snapshot {item['id']}?\n\nO estado atual será salvo antes da restauração.", parent=janela):
                return
            try:
                seguranca = restaurar_snapshot_sistema(item["id"])
                messagebox.showinfo("Rollback", f"Restauração concluída.\nBackup do estado anterior: {seguranca['id']}\n\nReinicie o NabiCode.", parent=janela)
            except Exception as exc:
                messagebox.showerror("Rollback", str(exc), parent=janela)

        linha_snapshot = ctk.CTkFrame(aba, fg_color="transparent")
        linha_snapshot.pack(fill="x", padx=14, pady=(0, 8))
        botao_snapshot = ctk.CTkButton(linha_snapshot, text="📸 Criar snapshot verificado", command=criar_snapshot_ui, fg_color="#2ea043")
        botao_snapshot.pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(linha_snapshot, text="↩ Restaurar snapshot recente", command=restaurar_ultimo_snapshot_ui, fg_color="#8957e5").pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(linha_snapshot, text="🔄 Atualizar lista", command=atualizar_lista_snapshots).pack(side="left", fill="x", expand=True, padx=4)
        atualizar_lista_snapshots()

        # PADRÃO DE FÁBRICA — aba própria, sempre visível no painel administrativo
        aba = abas.tab("Padrão de fábrica")
        ctk.CTkLabel(aba, text="Restaurar padrão de fábrica", font=ctk.CTkFont(size=18, weight="bold"), text_color="#f85149").pack(pady=(35, 10))
        ctk.CTkLabel(
            aba,
            text="Escolha o nível de restauração em uma janela dedicada. Antes de qualquer alteração, o sistema mostra a prévia e cria backup validado.",
            wraplength=700, justify="center", text_color="#c9d1d9"
        ).pack(padx=30, pady=(0, 18))
        ctk.CTkButton(
            aba, text="🏭 Abrir restauração de fábrica", height=48,
            fg_color="#da3633", hover_color="#b62324", command=self.abrir_restauracao_fabrica
        ).pack(fill="x", padx=80, pady=10)

        # DIAGNÓSTICO DO SISTEMA
        aba = abas.tab("Diagnóstico")
        ctk.CTkLabel(aba, text="Diagnóstico técnico do sistema", font=ctk.CTkFont(size=17, weight="bold"), text_color="#ffd700").pack(pady=(18, 8))
        caixa_diag = ctk.CTkTextbox(aba)
        caixa_diag.pack(fill="both", expand=True, padx=18, pady=8)

        def executar_diagnostico_ui():
            botao_diagnostico.configure(state="disabled", text="Executando diagnóstico...")
            caixa_diag.delete("1.0", "end")
            caixa_diag.insert("end", "Diagnóstico em execução. A interface pode continuar sendo usada.\n")

            def trabalho(ctx):
                ctx.report_progress(0.1, "Verificando banco")
                resultado = executar_diagnostico_sistema()
                ctx.report_progress(1.0, "Relatório concluído")
                return resultado

            def progresso(valor, mensagem, status):
                if mensagem:
                    botao_diagnostico.configure(text=f"{mensagem} ({int(valor * 100)}%)")

            def concluir(resultado):
                botao_diagnostico.configure(state="normal", text="🩺 Executar diagnóstico completo")
                caixa_diag.delete("1.0", "end")
                caixa_diag.insert("end", formatar_diagnostico(resultado))
                pendencias = [
                    f"• {item['name']}: {item['detail']}"
                    for item in resultado.get("checks", [])
                    if not item.get("ok")
                ]
                detalhe = "\n".join(pendencias[:5]) or "Nenhuma pendência encontrada."
                messagebox.showinfo(
                    "Diagnóstico",
                    f"Diagnóstico concluído.\nResultado: {'APROVADO' if resultado['aprovado'] else 'ATENÇÃO NECESSÁRIA'}\n\n{detalhe}\n\nRelatório: {resultado['arquivo']}",
                    parent=janela,
                )

            def falhar(erro):
                botao_diagnostico.configure(state="normal", text="🩺 Executar diagnóstico completo")
                messagebox.showerror("Diagnóstico", erro, parent=janela)

            executar_tarefa_ui("Diagnóstico técnico", trabalho, concluir, falhar, progresso)

        botao_diagnostico = botao(aba, "🩺 Executar diagnóstico completo", executar_diagnostico_ui, "#1f6feb")
        botao(aba, "📂 Abrir pasta de diagnósticos", lambda: self._abrir_diretorio_sistema(DIAGNOSTIC_DIR), "#8957e5")

        # MIGRAÇÃO — FASE 1: análise e simulação sem gravação
        aba = abas.tab("Migração")
        conteudo_mig = ctk.CTkScrollableFrame(aba, fg_color="transparent")
        conteudo_mig.pack(fill="both", expand=True)
        ctk.CTkLabel(conteudo_mig, text="📦 Assistente de Migração", font=ctk.CTkFont(size=17, weight="bold"), text_color="#00FF88").pack(pady=(14, 4))
        ctk.CTkLabel(conteudo_mig, text="Selecione um .sql antigo ou um pacote .nabimig; o formato será reconhecido automaticamente.", text_color="#c9d1d9").pack(pady=(0, 10))
        frame_arq = ctk.CTkFrame(conteudo_mig, fg_color="transparent"); frame_arq.pack(fill="x", padx=18, pady=4)
        entrada_sql = ctk.CTkEntry(frame_arq, placeholder_text="Selecione um arquivo .sql ou .nabimig", height=38)
        entrada_sql.pack(side="left", fill="x", expand=True, padx=(0, 6))
        def escolher_sql():
            arq = filedialog.askopenfilename(parent=janela, title="Selecionar arquivo de migração", filetypes=[("Migração NabiCode", "*.nabimig *.sql"), ("Pacote .nabimig", "*.nabimig"), ("Backup SQL", "*.sql")])
            if arq:
                entrada_sql.delete(0, "end"); entrada_sql.insert(0, arq)
                caminho_nabimig.set(arq)
        ctk.CTkButton(frame_arq, text="Selecionar arquivo...", width=145, command=escolher_sql).pack(side="right")
        progresso_mig = ctk.CTkProgressBar(conteudo_mig); progresso_mig.pack(fill="x", padx=18, pady=(8, 4)); progresso_mig.set(0)
        status_mig = ctk.CTkLabel(conteudo_mig, text="Aguardando arquivo.", text_color="#8b949e"); status_mig.pack(anchor="w", padx=18)
        resultado_mig = ctk.CTkTextbox(conteudo_mig, height=210, font=("Consolas", 11)); resultado_mig.pack(fill="x", padx=18, pady=8)
        resultado_mig.insert("end", "Nenhuma análise executada.\n")
        self.ultimo_relatorio_migracao = None
        self.dados_migracao_fase2 = None

        def registrar_log_mig(arquivo, etapa, status, detalhes):
            _ADMIN_OPERATIONS.log_migration(arquivo, etapa, status, detalhes)

        def analisar_sql_ui():
            caminho = entrada_sql.get().strip()
            if not caminho or not os.path.isfile(caminho):
                messagebox.showwarning("Migração", "Selecione um arquivo .sql válido.", parent=janela); return
            progresso_mig.set(0); status_mig.configure(text="Analisando backup...", text_color="#ffd700")
            resultado_mig.delete("1.0", "end"); resultado_mig.insert("end", "Análise em andamento. Aguarde...\n")
            def trabalho(ctx):
                return analisar_dump_mysql(caminho, lambda valor: ctx.report_progress(valor, "Analisando o backup..."))

            def concluir(rel):
                self.ultimo_relatorio_migracao = rel
                texto = mysql_migration_report_text(rel)
                resultado_mig.delete("1.0", "end"); resultado_mig.insert("end", texto)
                status_mig.configure(text="Simulação concluída. Nenhum dado foi alterado.", text_color="#00FF88")
                registrar_log_mig(caminho, "ANÁLISE", "SUCESSO", texto)

            def falhar(erro):
                progresso_mig.set(0); status_mig.configure(text="Falha na análise.", text_color="#ff6b6b")
                registrar_log_mig(caminho, "ANÁLISE", "ERRO", erro)
                messagebox.showerror("Migração", f"Não foi possível analisar o arquivo:\n{erro}", parent=janela)

            executar_tarefa_ui(
                "Analisar backup SQL", trabalho, concluir, falhar,
                lambda valor, mensagem, _status: (progresso_mig.set(valor), status_mig.configure(text=f"{mensagem} {valor*100:.0f}%")),
            )

        def salvar_relatorio_mig():
            if Path(entrada_sql.get().strip()).suffix.lower() == ".nabimig":
                texto_nabimig = estado_nabimig.get("relatorio", "")
                if not texto_nabimig:
                    messagebox.showwarning("Migração", "Execute a importação do pacote primeiro.", parent=janela); return
                destino = filedialog.asksaveasfilename(parent=janela, title="Salvar relatório", defaultextension=".txt", filetypes=[("Texto", "*.txt")], initialfile=f"relatorio_nabimig_{datetime.now():%Y%m%d_%H%M%S}.txt")
                if destino:
                    Path(destino).write_text(texto_nabimig, encoding="utf-8")
                    messagebox.showinfo("Migração", "Relatório salvo com sucesso.", parent=janela)
                return
            if not self.ultimo_relatorio_migracao:
                messagebox.showwarning("Migração", "Execute a análise primeiro.", parent=janela); return
            destino = filedialog.asksaveasfilename(parent=janela, title="Salvar relatório", defaultextension=".txt", filetypes=[("Texto", "*.txt")], initialfile=f"relatorio_migracao_{datetime.now():%Y%m%d_%H%M%S}.txt")
            if destino:
                Path(destino).write_text(mysql_migration_report_text(self.ultimo_relatorio_migracao), encoding="utf-8")
                messagebox.showinfo("Migração", "Relatório salvo com sucesso.", parent=janela)

        def preparar_fase2_ui():
            caminho = entrada_sql.get().strip()
            if not caminho or not os.path.isfile(caminho):
                messagebox.showwarning("Migração", "Selecione um arquivo .sql válido.", parent=janela); return
            progresso_mig.set(0); status_mig.configure(text="Calculando saldos e escolhendo as 12 últimas transações...", text_color="#ffd700")
            resultado_mig.delete("1.0", "end"); resultado_mig.insert("end", "Preparação da Fase 2 em andamento. Aguarde...\n")
            def trabalho(ctx):
                return preparar_migracao_resumida(caminho, lambda valor: ctx.report_progress(valor, "Preparando dados..."))

            def concluir(dados):
                self.dados_migracao_fase2 = dados
                texto = migration_phase2_preview_text(dados)
                resultado_mig.delete("1.0", "end"); resultado_mig.insert("end", texto)
                status_mig.configure(text="Prévia concluída. Confira e use Importar Fase 2.", text_color="#00FF88")
                registrar_log_mig(caminho, "PREPARAÇÃO FASE 2", "SUCESSO", texto)

            def falhar(erro):
                status_mig.configure(text="Falha ao preparar a Fase 2.", text_color="#ff6b6b")
                registrar_log_mig(caminho, "PREPARAÇÃO FASE 2", "ERRO", erro)
                messagebox.showerror("Migração", f"Não foi possível preparar a migração:\n{erro}", parent=janela)

            executar_tarefa_ui(
                "Preparar migração SQL", trabalho, concluir, falhar,
                lambda valor, mensagem, _status: (progresso_mig.set(valor), status_mig.configure(text=f"{mensagem} {valor*100:.0f}%")),
            )

        def importar_fase2_ui():
            if not self.dados_migracao_fase2:
                messagebox.showwarning("Migração", "Clique primeiro em Preparar Fase 2.", parent=janela); return
            dados = self.dados_migracao_fase2
            pergunta = (f"Serão importados/atualizados {len(dados['clientes'])} clientes, o saldo atual e até 12 transações por cliente.\n\n"
                        "Um backup automático será criado antes da gravação.\nOs clientes de demonstração serão removidos.\n\nContinuar?")
            if not messagebox.askyesno("Confirmar Migração — Fase 2", pergunta, parent=janela): return
            progresso_mig.set(0); status_mig.configure(text="Migração em segundo plano. Você pode continuar usando o NabiCode.", text_color="#ffd700")

            def trabalho(ctx):
                return executar_migracao_resumida(dados, remover_demos=True, progresso=lambda valor: ctx.report_progress(valor, "Importando dados..."))

            def concluir(res):
                texto = migration_phase2_result_text(res)
                resultado_mig.delete("1.0", "end"); resultado_mig.insert("end", texto)
                status_mig.configure(text="Migração Fase 2 concluída com sucesso.", text_color="#00FF88")
                registrar_log_mig(dados["arquivo"], "IMPORTAÇÃO FASE 2", "SUCESSO", texto)
                self.carregar_clientes(); self.atualizar_resumo_lateral()
                messagebox.showinfo("Migração", "Migração concluída. Cadastros, saldos e histórico resumido já estão disponíveis.", parent=janela)

            def falhar(erro):
                status_mig.configure(text="Falha na importação; a transação foi desfeita.", text_color="#ff6b6b")
                registrar_log_mig(dados["arquivo"], "IMPORTAÇÃO FASE 2", "ERRO", erro)
                messagebox.showerror("Migração", f"A importação falhou e nenhum dado parcial foi mantido:\n{erro}", parent=janela)

            executar_tarefa_ui(
                "Importar migração SQL", trabalho, concluir, falhar,
                lambda valor, mensagem, _status: (progresso_mig.set(valor), status_mig.configure(text=f"{mensagem} {valor*100:.0f}% — você pode continuar usando o programa")),
            )

        frame_botoes_mig = ctk.CTkFrame(conteudo_mig, fg_color="transparent"); frame_botoes_mig.pack(fill="x", padx=14, pady=(0, 10))
        def arquivo_nabimig_selecionado():
            return Path(entrada_sql.get().strip()).suffix.lower() == ".nabimig"

        ctk.CTkButton(frame_botoes_mig, text="1. Analisar", command=lambda: validar_nabimig_ui(False) if arquivo_nabimig_selecionado() else analisar_sql_ui(), fg_color="#2ea043", height=40).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(frame_botoes_mig, text="2. Preparar", command=lambda: validar_nabimig_ui(True) if arquivo_nabimig_selecionado() else preparar_fase2_ui(), fg_color="#1f6feb", height=40).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(frame_botoes_mig, text="3. Migrar", command=lambda: importar_nabimig_ui() if arquivo_nabimig_selecionado() else importar_fase2_ui(), fg_color="#8957e5", height=40).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(frame_botoes_mig, text="💾 Relatório", command=salvar_relatorio_mig, fg_color="#30363d", height=40).pack(side="left", expand=True, fill="x", padx=4)

        # Pacotes do conversor usam o mesmo destino, sem substituir a Migração Fase 2.
        separador_nabimig = ctk.CTkFrame(conteudo_mig, fg_color="#21262d")
        ctk.CTkLabel(
            separador_nabimig,
            text="IMPORTAR PACOTE DO CONVERSOR NABICODE (.nabimig)",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#58a6ff",
        ).pack(anchor="w", padx=14, pady=(12, 3))
        ctk.CTkLabel(
            separador_nabimig,
            text="Validação completa, backup obrigatório e gravação em uma única transação.",
            text_color="#c9d1d9",
        ).pack(anchor="w", padx=14, pady=(0, 10))

        servico_nabimig = NabiMigImportService()
        estado_nabimig = {"preview": None, "preparado": False, "cancelar": False, "relatorio": ""}
        caminho_nabimig = tk.StringVar(value="")
        modo_nabimig = tk.StringVar(value="tudo")
        remover_demos_nabimig = tk.BooleanVar(value=True)
        categorias_nabimig = {category: tk.BooleanVar(value=True) for category in CATEGORY_LABELS}

        frame_pacote = ctk.CTkFrame(conteudo_mig, fg_color="transparent")
        entrada_nabimig = ctk.CTkEntry(frame_pacote, textvariable=caminho_nabimig, state="readonly", height=38)
        entrada_nabimig.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def escolher_nabimig():
            arquivo = filedialog.askopenfilename(
                parent=janela, title="Selecionar pacote do conversor NabiCode",
                filetypes=[("Pacote NabiCode", "*.nabimig")],
            )
            if arquivo:
                caminho_nabimig.set(arquivo)
                estado_nabimig.update(preview=None, relatorio="")
                status_nabimig.configure(text="Pacote selecionado. Clique em Validar pacote.", text_color="#ffd700")
                resultado_nabimig.delete("1.0", "end")
                resultado_nabimig.insert("end", "Aguardando validação completa do pacote.\n")

        ctk.CTkButton(frame_pacote, text="Selecionar pacote .nabimig", width=205, command=escolher_nabimig).pack(side="right")

        controles_nabimig = ctk.CTkFrame(conteudo_mig, fg_color="transparent")
        ctk.CTkRadioButton(controles_nabimig, text="Importar tudo", variable=modo_nabimig, value="tudo").pack(side="left", padx=(0, 18))
        ctk.CTkRadioButton(controles_nabimig, text="Somente categorias escolhidas", variable=modo_nabimig, value="parcial").pack(side="left")

        frame_categorias = ctk.CTkFrame(conteudo_mig, fg_color="#161b22")
        checks_nabimig = {}

        def atualizar_dependencias_nabimig():
            if modo_nabimig.get() == "tudo":
                preview = estado_nabimig.get("preview")
                disponiveis = set(preview.counts) if preview else set(CATEGORY_LABELS)
                for category, variable in categorias_nabimig.items():
                    variable.set(category in disponiveis)
                dependencias_nabimig.configure(text="Todas as categorias disponíveis serão importadas.")
                return
            escolhidas = tuple(category for category, variable in categorias_nabimig.items() if variable.get())
            completas, automaticas = servico_nabimig.resolve_categories(escolhidas)
            for category in automaticas:
                categorias_nabimig[category].set(True)
            if automaticas:
                nomes = ", ".join(CATEGORY_LABELS[item] for item in automaticas)
                dependencias_nabimig.configure(text=f"Dependências incluídas automaticamente: {nomes}")
            else:
                dependencias_nabimig.configure(text="Nenhuma dependência adicional necessária.")

        for indice, (category, label) in enumerate(CATEGORY_LABELS.items()):
            check = ctk.CTkCheckBox(
                frame_categorias, text=label, variable=categorias_nabimig[category],
                command=lambda cat=category: (modo_nabimig.set("parcial"), atualizar_dependencias_nabimig()),
            )
            check.grid(row=indice // 2, column=indice % 2, sticky="w", padx=14, pady=6)
            checks_nabimig[category] = check
        frame_categorias.grid_columnconfigure((0, 1), weight=1)
        dependencias_nabimig = ctk.CTkLabel(conteudo_mig, text="Todas as categorias disponíveis serão importadas.", text_color="#f0b429")
        demo_remover_nabimig = ctk.CTkRadioButton(

            conteudo_mig, text="Remover clientes demonstrativos antes da importação (recomendado)",
            variable=remover_demos_nabimig, value=True,
        )
        demo_preservar_nabimig = ctk.CTkRadioButton(
            conteudo_mig, text="Preservar clientes demonstrativos",
            variable=remover_demos_nabimig, value=False,
        )

        progresso_nabimig = progresso_mig
        status_nabimig = status_mig
        resultado_nabimig = resultado_mig

        def validar_nabimig_ui(preparar=False):
            caminho = entrada_sql.get().strip()
            caminho_nabimig.set(caminho)
            if not caminho:
                messagebox.showwarning("Migração .nabimig", "Selecione um pacote .nabimig.", parent=janela); return
            progresso_nabimig.set(0.1)
            status_nabimig.configure(text="Validando estrutura, hashes, contagens e vínculos...", text_color="#ffd700")
            botao_validar_nabimig.configure(state="disabled")

            def concluir(preview):
                estado_nabimig["preview"] = preview
                estado_nabimig["preparado"] = bool(preparar and preview.ready)
                botao_validar_nabimig.configure(state="normal")
                progresso_nabimig.set(1)
                resultado_nabimig.delete("1.0", "end"); resultado_nabimig.insert("end", preview_text(preview))
                for category, check in checks_nabimig.items():
                    check.configure(state="normal" if category in preview.counts else "disabled")
                    categorias_nabimig[category].set(category in preview.counts)
                if preparar and preview.ready:
                    controles_nabimig.pack(fill="x", padx=18, pady=5)
                    frame_categorias.pack(fill="x", padx=18, pady=5)
                    dependencias_nabimig.pack(anchor="w", padx=22, pady=(2, 7))
                    demo_remover_nabimig.pack(anchor="w", padx=22, pady=3)
                    demo_preservar_nabimig.pack(anchor="w", padx=22, pady=3)
                atualizar_dependencias_nabimig()
                status_nabimig.configure(
                    text=("Preparação concluída. Confira as opções e clique em 3. Migrar." if preparar else "Análise concluída. Clique em 2. Preparar.") if preview.ready else "Pacote reprovado. Corrija os erros antes de importar.",
                    text_color="#00FF88" if preview.ready else "#ff6b6b",
                )

            def falhar(erro):
                estado_nabimig["preview"] = None
                botao_validar_nabimig.configure(state="normal")
                progresso_nabimig.set(0)
                status_nabimig.configure(text="Pacote reprovado.", text_color="#ff6b6b")
                messagebox.showerror("Migração .nabimig", f"O pacote não passou na validação:\n{erro}", parent=janela)

            executar_tarefa_ui(
                "Validar pacote .nabimig",
                lambda ctx: servico_nabimig.preview(caminho, ctx.report_progress),
                concluir, falhar,
                lambda valor, mensagem, _status: (progresso_nabimig.set(valor), status_nabimig.configure(text=mensagem)),
            )

        def importar_nabimig_ui():
            preview = estado_nabimig.get("preview")
            if preview is None or not preview.ready or not estado_nabimig.get("preparado"):
                messagebox.showwarning("Migração .nabimig", "Conclua primeiro as etapas 1. Analisar e 2. Preparar.", parent=janela); return
            if not Path(DB_NAME).is_file():
                messagebox.showerror("Migração .nabimig", "O banco ativo não foi localizado. Nada foi alterado.", parent=janela); return
            if modo_nabimig.get() == "tudo":
                escolhidas = tuple(category for category in CATEGORY_LABELS if category in preview.counts)
            else:
                escolhidas = tuple(category for category, variable in categorias_nabimig.items() if variable.get())
            completas, automaticas = servico_nabimig.resolve_categories(escolhidas)
            if not escolhidas or set(completas) - set(preview.counts):
                messagebox.showerror("Migração .nabimig", "A seleção não forma um conjunto consistente para este pacote.", parent=janela); return
            resumo = ", ".join(CATEGORY_LABELS[item] for item in completas)
            if not messagebox.askyesno(
                "Confirmar importação .nabimig",
                f"Categorias: {resumo}\n\nUm backup obrigatório será criado antes da gravação.\n"
                f"Clientes demonstrativos: {'remover quando não houver vínculos' if remover_demos_nabimig.get() else 'preservar'}.\n\nContinuar?",
                parent=janela,
            ):
                return
            estado_nabimig["cancelar"] = False
            remover_demos = bool(remover_demos_nabimig.get())
            progresso_nabimig.set(0.2)
            status_nabimig.configure(text="Migração em segundo plano. Você pode continuar usando o NabiCode.", text_color="#ffd700")
            botao_importar_nabimig.configure(state="disabled")
            botao_cancelar_nabimig.configure(state="normal")

            def trabalho(ctx):
                return servico_nabimig.execute(
                    preview.package, database_path=DB_NAME, backup_dir=Path(APP_DIR) / "backups",
                    connect=lambda: open_connection(DB_NAME, network_mode=MODO_REDE, logger=logger),
                    backup_database=lambda origem, destino: backup_database(
                        origem, destino, timeout=60, network_mode=MODO_REDE, logger=logger,
                    ),
                    categories=escolhidas, remove_demo_customers=remover_demos,
                    cancel_check=lambda: ctx.cancelled() or bool(estado_nabimig["cancelar"]),
                    progress=ctx.report_progress,
                )

            def concluir(result):
                botao_importar_nabimig.configure(state="normal"); botao_cancelar_nabimig.configure(state="disabled")
                progresso_nabimig.set(1)
                relatorio = final_report_text(
                    preview, result, DB_NAME, demos_requested_for_removal=remover_demos,
                )
                estado_nabimig["relatorio"] = relatorio
                resultado_nabimig.delete("1.0", "end"); resultado_nabimig.insert("end", relatorio)
                status_nabimig.configure(text="Importação concluída e verificada.", text_color="#00FF88")
                registrar_log_mig(preview.package, "IMPORTAÇÃO NABIMIG", "SUCESSO", relatorio)
                self.carregar_clientes(); self.atualizar_resumo_lateral()
                messagebox.showinfo("Migração .nabimig", f"Importação concluída.\nBackup: {result.backup}", parent=janela)

            def falhar(erro):
                botao_importar_nabimig.configure(state="normal"); botao_cancelar_nabimig.configure(state="disabled")
                cancelado = "cancelada antes da transacao" in erro.lower()
                status = "CANCELADO" if cancelado else "FALHA COM ROLLBACK"
                progresso_nabimig.set(0)
                status_nabimig.configure(text=status, text_color="#f0b429" if cancelado else "#ff6b6b")
                resultado_nabimig.delete("1.0", "end"); resultado_nabimig.insert("end", f"Status: {status}\n{erro}\n")
                registrar_log_mig(preview.package, "IMPORTAÇÃO NABIMIG", status, erro)
                if not cancelado:
                    messagebox.showerror("Migração .nabimig", f"A importação falhou e foi desfeita:\n{erro}", parent=janela)

            executar_tarefa_ui(
                "Importar pacote .nabimig", trabalho, concluir, falhar,
                lambda valor, mensagem, _status: (
                    progresso_nabimig.set(valor),
                    status_nabimig.configure(text=f"{mensagem} — você pode continuar usando o programa"),
                ),
            )

        def cancelar_nabimig_ui():
            estado_nabimig["cancelar"] = True
            status_nabimig.configure(text="Cancelamento solicitado; será aplicado antes da transação.", text_color="#f0b429")
            botao_cancelar_nabimig.configure(state="disabled")

        frame_acoes_nabimig = ctk.CTkFrame(conteudo_mig, fg_color="transparent")
        botao_validar_nabimig = ctk.CTkButton(frame_acoes_nabimig, text="Validar pacote", command=validar_nabimig_ui, fg_color="#2ea043", height=40)
        botao_validar_nabimig.pack(side="left", expand=True, fill="x", padx=4)
        botao_importar_nabimig = ctk.CTkButton(frame_acoes_nabimig, text="Criar backup e importar", command=importar_nabimig_ui, fg_color="#8957e5", height=40)
        botao_importar_nabimig.pack(side="left", expand=True, fill="x", padx=4)
        botao_cancelar_nabimig = ctk.CTkButton(frame_acoes_nabimig, text="Cancelar", command=cancelar_nabimig_ui, fg_color="#da3633", state="disabled", height=40)
        botao_cancelar_nabimig.pack(side="left", expand=True, fill="x", padx=4)

        # DEMONSTRAÇÃO
        aba = abas.tab("Demonstração")
        def excluir_demos_admin():
            if not messagebox.askyesno("Demonstração", "Excluir todos os clientes fictícios?", parent=janela):
                return
            try:
                total = CUSTOMER_MAINTENANCE_SERVICE.delete_fictitious_customers()
            except Exception as exc:
                logging.exception("Falha ao excluir clientes de demonstração")
                messagebox.showerror("Demonstração", f"Não foi possível excluir os cadastros fictícios:\n{exc}", parent=janela)
                return
            self.carregar_clientes()
            self.atualizar_resumo_lateral()
            messagebox.showinfo("Demonstração", f"{total} cadastro(s) fictício(s) excluído(s).", parent=janela)

        def recriar_demos_admin():
            try:
                criados = CUSTOMER_MAINTENANCE_SERVICE.recreate_demo_customers()
            except Exception as exc:
                logging.exception("Falha ao recriar clientes de demonstração")
                messagebox.showerror("Demonstração", f"Não foi possível recriar os cadastros fictícios:\n{exc}", parent=janela)
                return
            self.carregar_clientes()
            self.atualizar_resumo_lateral()
            messagebox.showinfo(
                "Demonstração",
                f"Cadastros fictícios disponíveis. {criados} novo(s) cadastro(s) criado(s).",
                parent=janela,
            )
        botao(aba, "♻ Recriar clientes de demonstração", recriar_demos_admin, "#2ea043")
        botao(aba, "🗑 Excluir clientes de demonstração", excluir_demos_admin, "#da3633")

        # FERRAMENTAS TÉCNICAS (migradas das Configurações)
        aba = abas.tab("Ferramentas")
        ctk.CTkLabel(aba, text="Configurações avançadas", font=ctk.CTkFont(size=17, weight="bold"), text_color="#ffd700").pack(pady=(18, 8))
        ctk.CTkLabel(aba, text="Use estas opções somente durante atendimento técnico.", text_color="#c9d1d9").pack(pady=(0, 10))
        botao(aba, "🖥️ Rede local / banco compartilhado", self.abrir_configuracao_rede)
        botao(aba, "📤 Exportar clientes para CSV", self.exportar_clientes_csv, "#1f6feb")
        botao(aba, "🗑 Excluir cadastros fictícios", self.excluir_cadastros_ficticios, "#da3633")
        ferramentas_dev = DeveloperToolsService(SOURCE_DIR, os.path.abspath(DB_NAME))

        def abrir_diretorio_tecnico(caminho):
            self._abrir_diretorio_sistema(caminho)

        def executar_testes_tecnicos():
            def trabalho(ctx):
                ctx.report_progress(0.1, "Executando testes")
                resultado = ferramentas_dev.run_tests()
                ctx.report_progress(1.0, "Testes concluídos")
                return resultado

            def concluir(resultado):
                texto = (resultado.stdout + "\n" + resultado.stderr).strip()
                messagebox.showinfo(
                    "Testes",
                    f"Resultado: {'APROVADO' if resultado.ok else 'FALHA'}\nCódigo: {resultado.returncode}\n\n{texto[-3500:]}",
                    parent=janela,
                )

            executar_tarefa_ui("Executar testes", trabalho, concluir, lambda erro: messagebox.showerror("Testes", erro, parent=janela))

        def limpar_build_tecnico():
            removidos = ferramentas_dev.clean_build()
            messagebox.showinfo("Build", f"{len(removidos)} item(ns) removido(s).", parent=janela)

        def exportar_diagnostico_tecnico():
            try:
                arquivo = ferramentas_dev.export_diagnostic(DIAGNOSTIC_DIR)
                messagebox.showinfo("Diagnóstico", f"Pacote exportado em:\n{arquivo}", parent=janela)
            except Exception as exc:
                messagebox.showerror("Diagnóstico", str(exc), parent=janela)

        def mostrar_versoes_tecnicas():
            dados = ferramentas_dev.runtime_versions()
            texto = "\n".join(f"{chave}: {valor}" for chave, valor in dados.items())
            messagebox.showinfo("Versões", texto, parent=janela)

        def validar_ferramentas_tecnicas():
            resultado = ferramentas_dev.validate_tooling()
            linhas = [
                f"Status: {'APROVADO' if resultado['ok'] else 'INCOMPLETO'}",
                f"Versão: {resultado.get('version') or '-'}",
                f"Projeto: {resultado['project_dir']}",
            ]
            if resultado["missing"]:
                linhas.append("\nAusentes:\n- " + "\n- ".join(resultado["missing"]))
            if resultado["errors"]:
                linhas.append("\nErros:\n- " + "\n- ".join(resultado["errors"]))
            exibidor = messagebox.showinfo if resultado["ok"] else messagebox.showwarning
            exibidor("Ferramentas do desenvolvedor", "\n".join(linhas), parent=janela)

        def verificar_atualizacoes_tecnicas():
            resultado = ferramentas_dev.check_update()
            messagebox.showinfo(
                "Atualizações",
                f"Versão atual: {resultado['current']}\n\nNenhuma origem oficial de atualização está configurada neste projeto.",
                parent=janela,
            )

        botao(aba, "📂 Abrir pasta de logs", lambda: abrir_diretorio_tecnico(LOG_DIR), "#8957e5")
        botao(aba, "📂 Abrir pasta de backups", lambda: abrir_diretorio_tecnico(BACKUP_DIR), "#8957e5")
        botao(aba, "📂 Abrir pasta do banco", lambda: abrir_diretorio_tecnico(os.path.dirname(os.path.abspath(DB_NAME))), "#8957e5")
        botao(aba, "📦 Exportar diagnóstico", exportar_diagnostico_tecnico, "#1f6feb")
        botao(aba, "🧪 Executar testes", executar_testes_tecnicos, "#2ea043")
        botao(aba, "🧹 Limpar build", limpar_build_tecnico, "#da3633")
        botao(aba, "✅ Validar ferramentas", validar_ferramentas_tecnicas, "#2ea043")
        botao(aba, "ℹ Mostrar versões", mostrar_versoes_tecnicas, "#30363d")
        botao(aba, "🔄 Verificar atualizações", verificar_atualizacoes_tecnicas, "#30363d")
        botao(aba, "📂 Abrir pasta de PDFs", lambda: abrir_diretorio_tecnico(PDF_DIR), "#8957e5")

        # SISTEMA
        aba = abas.tab("Sistema")
        info = f"Versão: {APP_VERSION} — {APP_VERSION_LABEL}\nPython: {platform.python_version()}\nSistema: {platform.platform()}\nPasta do programa: {SOURCE_DIR}\nBanco: {os.path.abspath(DB_NAME)}"
        caixa_info=ctk.CTkTextbox(aba); caixa_info.pack(fill="both", expand=True, padx=18, pady=18); caixa_info.insert("end", info); caixa_info.configure(state="disabled")
        botao(aba, "📂 Abrir pasta do sistema", lambda: self._abrir_diretorio_sistema(os.getcwd()))

        # SUPORTE
        aba = abas.tab("Suporte")
        ctk.CTkLabel(aba, text="Suporte e diagnóstico", font=ctk.CTkFont(size=17, weight="bold"), text_color="#00FF88").pack(pady=(20, 10))
        relatorio = ctk.CTkTextbox(aba, height=250)
        relatorio.pack(fill="both", expand=True, padx=18, pady=8)
        def gerar_relatorio():
            dados = "\n".join([
                f"Loja: {obter_config('nome_loja')}", f"Versão: {APP_VERSION} - {APP_VERSION_LABEL}",
                f"Computador: {socket.gethostname()}", f"Sistema: {platform.platform()}",
                f"Python: {platform.python_version()}", f"Modo: {'REDE' if MODO_REDE else 'LOCAL'}",
                f"Banco: {DB_NAME}", f"Banco existe: {os.path.exists(DB_NAME)}",
                f"Login inicial efetivo: {'ATIVO' if self._login_usuarios_habilitado() else 'DESATIVADO'}",
                f"Login solicitado pelo usuário v2442: {obter_config('login_inicio_ativado_pelo_usuario_v2442') or '0'}",
                f"Login habilitado (legado): {obter_config('login_usuarios_habilitado') or '0'}",
                f"Política de login v2442: {obter_config('login_politica_v2442_inicializada') or '0'}",
                f"Pasta backup: {os.path.abspath(BACKUP_DIR)}", f"Data: {datetime.now():%d/%m/%Y %H:%M:%S}",
            ])
            relatorio.delete("1.0", "end"); relatorio.insert("end", dados)
            self.clipboard_clear(); self.clipboard_append(dados)
            messagebox.showinfo("Relatório técnico", "Informações geradas e copiadas para a área de transferência.", parent=janela)
        botao(aba, "📋 Gerar e copiar relatório técnico", gerar_relatorio, "#1f6feb")
        botao(aba, "📲 Abrir chamado pelo WhatsApp", self.abrir_chamado_suporte, "#2ea043")

        # SEGURANÇA
        aba = abas.tab("Segurança")
        painel_seg = ctk.CTkFrame(aba, fg_color="transparent")
        painel_seg.pack(fill="both", expand=True, padx=18, pady=14)
        painel_seg.grid_columnconfigure(0, weight=1)
        painel_seg.grid_columnconfigure(1, weight=1)
        painel_seg.grid_rowconfigure(2, weight=1)

        login_ativo_var = ctk.BooleanVar(value=self._login_usuarios_habilitado())
        topo_login = ctk.CTkFrame(painel_seg, fg_color="#161b22")
        topo_login.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ctk.CTkCheckBox(topo_login, text="Exigir usuário e senha ao abrir o sistema", variable=login_ativo_var).pack(side="left", padx=12, pady=12)
        def salvar_modo_login():
            _ADMIN_OPERATIONS.save_login_mode(bool(login_ativo_var.get()))
            messagebox.showinfo("Segurança", "Configuração salva. A mudança vale na próxima abertura do sistema.", parent=janela)
        ctk.CTkButton(topo_login, text="Salvar opção", command=salvar_modo_login, width=120).pack(side="right", padx=12, pady=8)

        ctk.CTkLabel(painel_seg, text="Usuários e perfis", font=ctk.CTkFont(size=17, weight="bold"), text_color="#00FF88").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        usuarios_tree = ttk.Treeview(painel_seg, columns=("Usuario", "Nome", "Perfil", "Ativo"), show="headings", height=11)
        for coluna, largura in (("Usuario", 130), ("Nome", 190), ("Perfil", 110), ("Ativo", 70)):
            usuarios_tree.heading(coluna, text=coluna)
            usuarios_tree.column(coluna, width=largura, anchor="w")
        usuarios_tree.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 10))

        def recarregar_usuarios_seguranca():
            for item in usuarios_tree.get_children():
                usuarios_tree.delete(item)
            for usuario_seg in self.security.list_users():
                usuarios_tree.insert("", "end", iid=usuario_seg.username, values=(usuario_seg.username, usuario_seg.display_name, usuario_seg.profile, "SIM" if usuario_seg.active else "NÃO"))

        def usuario_selecionado_seguranca():
            selecionados = usuarios_tree.selection()
            if not selecionados:
                messagebox.showwarning("Segurança", "Selecione um usuário.", parent=janela)
                return None
            return str(selecionados[0])

        def abrir_editor_usuario(username=None):
            perfis = list(self.security.list_profiles())
            atual_user = self.security.get_user(username) if username else None
            editor = ctk.CTkToplevel(janela)
            editor.title("Editar usuário" if atual_user else "Novo usuário")
            editor.geometry("470x460")
            editor.transient(janela); editor.grab_set()
            campos = {}
            for rotulo, chave, valor in (("Usuário", "username", atual_user.username if atual_user else ""), ("Nome exibido", "display", atual_user.display_name if atual_user else "")):
                ctk.CTkLabel(editor, text=rotulo).pack(anchor="w", padx=28, pady=(14 if not campos else 8, 3))
                ent = ctk.CTkEntry(editor, height=38); ent.pack(fill="x", padx=28); ent.insert(0, valor); campos[chave] = ent
            campos["username"].configure(state="disabled" if atual_user else "normal")
            ctk.CTkLabel(editor, text="Perfil").pack(anchor="w", padx=28, pady=(10, 3))
            perfil_var = ctk.StringVar(value=atual_user.profile if atual_user else (perfis[0] if perfis else "OPERADOR"))
            ctk.CTkOptionMenu(editor, variable=perfil_var, values=perfis or ["OPERADOR"]).pack(fill="x", padx=28)
            ativo_var = ctk.BooleanVar(value=atual_user.active if atual_user else True)
            ctk.CTkCheckBox(editor, text="Usuário ativo", variable=ativo_var).pack(anchor="w", padx=28, pady=12)
            ctk.CTkLabel(editor, text="Senha (opcional)" if not atual_user else "Nova senha (vazia mantém a atual)").pack(anchor="w", padx=28, pady=(2, 3))
            senha_ent = ctk.CTkEntry(editor, show="●", height=38); senha_ent.pack(fill="x", padx=28)
            def salvar_usuario_editor():
                try:
                    if atual_user:
                        self.security.update_user(atual_user.username, display_name=campos["display"].get(), profile=perfil_var.get(), active=ativo_var.get())
                        if senha_ent.get():
                            self.security.set_password(atual_user.username, senha_ent.get())
                        acao = "USUARIO_ATUALIZADO"
                    else:
                        self.security.create_user(campos["username"].get(), campos["display"].get(), senha_ent.get(), perfil_var.get(), active=ativo_var.get())
                        acao = "USUARIO_CRIADO"
                    registrar_auditoria(self.security.session.user.username if self.security.session else "Sistema", "SEGURANCA", acao, campos["username"].get(), "SUCESSO")
                    recarregar_usuarios_seguranca(); editor.destroy()
                except Exception as exc:
                    messagebox.showerror("Segurança", str(exc), parent=editor)
            ctk.CTkButton(editor, text="Salvar", command=salvar_usuario_editor, fg_color="#2ea043").pack(fill="x", padx=28, pady=18)

        acoes_seg = ctk.CTkFrame(painel_seg, fg_color="transparent")
        acoes_seg.grid(row=3, column=0, columnspan=2, sticky="ew")
        ctk.CTkButton(acoes_seg, text="Novo usuário", command=lambda: abrir_editor_usuario()).pack(side="left", padx=3)
        ctk.CTkButton(acoes_seg, text="Editar usuário", command=lambda: (lambda u: abrir_editor_usuario(u) if u else None)(usuario_selecionado_seguranca())).pack(side="left", padx=3)
        ctk.CTkButton(acoes_seg, text="Ativar/Desativar", command=lambda: alternar_usuario_seguranca()).pack(side="left", padx=3)

        def alternar_usuario_seguranca():
            username = usuario_selecionado_seguranca()
            if not username:
                return
            try:
                user = self.security.get_user(username)
                self.security.set_user_active(username, not user.active)
                registrar_auditoria(self.security.session.user.username if self.security.session else "Sistema", "SEGURANCA", "USUARIO_ATIVADO" if not user.active else "USUARIO_DESATIVADO", username, "SUCESSO")
                recarregar_usuarios_seguranca()
            except Exception as exc:
                messagebox.showerror("Segurança", str(exc), parent=janela)

        def editar_perfil_seguranca():
            nome = simpledialog.askstring("Perfil", "Nome do perfil:", parent=janela)
            if not nome:
                return
            perfis = self.security.list_profiles()
            atual = perfis.get(nome.strip().upper(), {})
            texto = simpledialog.askstring("Permissões", "Informe uma permissão por linha no formato modulo:acao1,acao2", initialvalue="\n".join(f"{m}:{','.join(a)}" for m, a in sorted(atual.items())), parent=janela)
            if texto is None:
                return
            try:
                permissoes = parse_profile_permissions(texto)
                self.security.save_profile(nome, permissoes)
                registrar_auditoria(self.security.session.user.username if self.security.session else "Sistema", "SEGURANCA", "PERFIL_SALVO", nome.strip().upper(), "SUCESSO")
                messagebox.showinfo("Segurança", "Perfil salvo.", parent=janela)
            except Exception as exc:
                messagebox.showerror("Segurança", str(exc), parent=janela)
        ctk.CTkButton(acoes_seg, text="Gerenciar perfil", command=editar_perfil_seguranca, fg_color="#8957e5").pack(side="left", padx=3)

        def mostrar_logs():
            log=ctk.CTkToplevel(janela); log.title("Histórico de login e auditoria"); log.geometry("900x520"); log.configure(fg_color="#0d1117")
            tabela=ttk.Treeview(log, columns=("Data","Usuario","Acao","Resultado","Detalhes"), show="headings")
            for coluna, largura in (("Data",150),("Usuario",120),("Acao",170),("Resultado",90),("Detalhes",330)):
                tabela.heading(coluna,text=coluna); tabela.column(coluna,width=largura)
            try:
                linhas = self._servico_auditoria_admin().list_security_audit(500)
            except sqlite3.Error as exc:
                logging.getLogger("nabicode.security_audit").exception("Falha ao carregar auditoria de segurança")
                messagebox.showerror("Histórico de segurança", str(exc), parent=log)
                linhas = []
            for linha in linhas:
                tabela.insert('', 'end', values=(linha.date, linha.user, linha.action, linha.result, linha.details))
            tabela.pack(fill='both', expand=True, padx=12, pady=12)
        ctk.CTkButton(acoes_seg, text="Histórico de segurança", command=mostrar_logs, fg_color="#30363d").pack(side="left", padx=3)
        recarregar_usuarios_seguranca()

if __name__ == "__main__":
    app = FicharioMoveisApp()
    app.mainloop()
