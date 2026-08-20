from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
INNO = (ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
SPEC = (ROOT / "build_tools" / "pyinstaller" / "nabicode.spec").read_text(encoding="utf-8")
BUILD = (ROOT / "build_tools" / "build_windows.py").read_text(encoding="utf-8")


def method_block(name: str, next_name: str) -> str:
    start = LEGACY.index(f"    def {name}")
    end = LEGACY.index(f"    def {next_name}", start)
    return LEGACY[start:end]


def test_xml_import_dashboard_uses_guided_responsive_conference_flow():
    opening = method_block("abrir_importacao_xml", "abrir_pdv_independente")
    assert 'text="Importar NF-e de compra"' in opening
    assert "XML identificado" in opening
    assert "Empresa conferida" in opening
    assert "Revisar e importar" in opening
    assert 'abas_item.add("Vínculo")' in opening
    assert 'abas_item.add("Cadastro")' in opening
    assert 'abas_item.add("Estoque")' in opening
    assert 'abas_item.add("Tributos")' in opening
    assert 'campo_editor(aba_cadastro, "NCM (8 dígitos)"' in opening
    assert 'campo_editor(aba_cadastro, "CEST (7 dígitos, quando aplicável)"' in opening
    assert 'campo_editor(aba_cadastro, "Origem da mercadoria (0 a 8)"' in opening
    assert "não substitui o CFOP de venda" in opening
    assert "Valores informados pelo fornecedor" in opening
    assert "Estes valores não substituem a regra tributária da sua venda" in opening
    assert "reveal_prepared_toplevel_when_idle(win, maximize=True)" in opening
    assert "win.grab_set()" not in opening
    assert 'text="Revisar e importar NF-e"' in opening


def test_pdv_uses_native_minimize_without_changing_function_shortcuts():
    opening = method_block("abrir_pdv_independente", "_enter_contexto_pdv")
    minimize = method_block("_minimizar_pdv", "_nome_item_tabela_pdv")
    assert "win.transient(self)" not in opening
    assert 'text="Minimizar"' not in opening
    assert "win.transient(self)" not in opening
    assert "win.iconify()" in minimize
    assert "self.deiconify()" in minimize
    for key, action in (
        ("<F3>", "entry_cliente_venda.focus_set"),
        ("<F5>", "alternar_modo_orcamento_pdv"),
        ("<F7>", "abrir_vendas_do_dia_pdv"),
    ):
        assert f'win.bind("{key}"' in opening
        assert action in opening


def test_double_click_edits_and_right_click_removes_explicitly():
    opening = method_block("abrir_pdv_independente", "_enter_contexto_pdv")
    double_binding = opening.split('"<Double-Button-1>"', 1)[1].split(")", 1)[0]
    assert "self.abrir_editor_item_carrinho" in double_binding
    assert "remover_item_carrinho" not in double_binding
    assert 'bind("<Button-3>", self.abrir_menu_item_carrinho)' in opening
    menu = method_block("abrir_menu_item_carrinho", "aplicar_desconto_item_pdv")
    assert 'label="Remover item"' in menu
    assert "messagebox.askyesno(" in menu


def test_item_editor_is_transactional_and_does_not_write_master_product_fields():
    editor = method_block("abrir_editor_item_carrinho", "abrir_menu_item_carrinho")
    assert 'editor.title("Editar item da venda")' in editor
    assert "valem somente para esta venda" in editor
    assert "self.pdv_service.editar_item_venda(" in editor
    assert "self.carrinho_venda[indice] = atualizado" in editor
    assert "self.atualizar_total_carrinho()" in editor
    for forbidden in (
        "PRODUTO_SERVICE.salvar",
        "UPDATE produtos",
        "preco_custo",
        "categoria_id",
        "marca_id",
        "fornecedor_id",
    ):
        assert forbidden not in editor


def test_product_entry_uses_focus_state_machine_without_rebinding_enter():
    opening = method_block("abrir_pdv_independente", "_enter_contexto_pdv")
    assert "SearchEntryBehavior.attach_focus(self.entry_item_venda)" in opening
    assert "PDVEnterController(" in opening
    assert 'self.entry_item_venda.bind("<Return>"' not in opening


def test_notification_history_is_explicitly_session_scoped():
    notifications = (ROOT / "core" / "notifications.py").read_text(encoding="utf-8")
    assert "histórico em memória" in notifications
    assert "deque(maxlen=" in notifications
    assert "sqlite" not in notifications.casefold()
    assert "APPDATA" not in notifications


def test_installer_mutex_contract_is_stable_and_released_last():
    assert "INSTALLER_APP_MUTEX = \"NabiCodeApplicationMutex\"" in MAIN
    assert "CreateMutexW" in MAIN
    assert "CloseHandle" in MAIN
    assert MAIN.rindex("_release_installer_app_mutex(installer_app_mutex)") > MAIN.rindex(
        "database_lock.release()"
    )
    assert "AppMutex=NabiCodeApplicationMutex" in INNO
    assert "CloseApplications=yes" in INNO
    assert "RestartApplications=no" in INNO
    assert "taskkill" not in INNO.casefold()


def test_uninstaller_preserves_appdata_and_keeps_append_only_install_log():
    assert "UninstallLogMode=append" in INNO
    assert "uninsdelete" not in INNO.casefold()
    assert "if DeleteAllUserData then" in INNO
    assert "DeleteAllNabiCodeData();" in INNO


def test_official_icon_is_valid_and_wired_to_executable_and_installer():
    icon = ROOT / "build_tools/resources/NabiCode.ico"
    png = ROOT / "build_tools/resources/NabiCode.png"
    png_data = png.read_bytes()
    icon_header = icon.read_bytes()[:6]

    assert png_data.startswith(b"\x89PNG\r\n\x1a\n")
    assert png_data[25] == 6  # PNG RGBA: o ícone deve permanecer sem placa de fundo.
    assert icon_header[:4] == b"\x00\x00\x01\x00"
    assert int.from_bytes(icon_header[4:6], "little") >= 9
    assert 'optional_app_icon = project_root / "build_tools" / "resources" / "NabiCode.ico"' in SPEC
    assert "if optional_app_icon.is_file():" in SPEC
    assert "#ifdef AppIconFile" in INNO
    assert "SetupIconFile={#AppIconFile}" in INNO
    assert "if optional_icon.is_file():" in BUILD
    assert 'shutil.copy2(app_icon, distribution / "NabiCode.ico")' in BUILD
    assert 'IconFilename: "{app}\\NabiCode.ico"' in INNO
    assert "UninstallDisplayIcon={app}\\NabiCode.ico" in INNO


def test_fiscal_onboarding_prioritizes_xml_and_hides_automatic_sefaz_addresses():
    opening = method_block("abrir_configuracao_fiscal", "abrir_central_fiscal")
    assert "1. IMPORTAR DADOS DA EMPRESA PELO XML" in opening
    assert 'fields["issuer_trade_name"]' in opening
    assert '"issuer_trade_name": "trade_name"' in opening
    assert "if info.company_name and not fields[\"issuer_name\"].get().strip()" in opening
    assert "Deixe estes campos vazios para usar automaticamente o catálogo oficial da UF" in opening
    assert "advanced_endpoints.pack(fill=" in opening
    assert opening.index("def toggle_advanced_endpoints") < opening.index("advanced_endpoints.pack(fill=")
    assert 'text="Mostrar configuração técnica da SEFAZ"' in opening


def test_initial_numbering_fields_are_labeled_and_fit_the_modal():
    opening = method_block("abrir_configuracao_fiscal", "abrir_central_fiscal")
    assert 'modal.geometry("520x520")' in opening
    assert 'text="Tipo de documento fiscal"' in opening
    assert 'text="Série fiscal"' in opening
    assert 'text="Próximo número da nota"' in opening
    assert "número seguinte ao último autorizado" in opening


def test_fiscal_center_keeps_actions_accessible_in_scrollable_panel():
    opening = method_block("abrir_central_fiscal", "abrir_pasta_backup_config")
    assert "Ações do documento selecionado" in opening
    assert "action_panel = ctk.CTkScrollableFrame(" in opening
    assert "height=155" in opening
