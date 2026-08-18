import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
ADMIN_MANAGER = (ROOT / "managers" / "admin_operations_manager.py").read_text(encoding="utf-8")


class UpdateAndFactoryIntegrationTests(unittest.TestCase):
    def test_secret_admin_menu_uses_visual_cards_without_plain_tab_selector(self):
        self.assertIn("admin_sections = (", SOURCE)
        self.assertIn('text=f"{icone}  {nome}\\n{descricao}"', SOURCE)
        self.assertIn("def selecionar_secao_admin(nome):", SOURCE)
        self.assertIn("abas._segmented_button.grid_remove()", SOURCE)
        self.assertIn('uniform="admin_cards"', SOURCE)

    def test_factory_reset_has_own_admin_tab(self):
        self.assertIn('"Padrão de fábrica"', SOURCE)
        self.assertIn('abas.tab("Padrão de fábrica")', SOURCE)
        self.assertIn('command=self.abrir_restauracao_fabrica', SOURCE)

    def test_update_tab_accepts_validated_zip_packages(self):
        self.assertIn("Selecionar pacote .zip", SOURCE)
        self.assertIn("_ADMIN_OPERATIONS.validate_update_package", SOURCE)
        self.assertIn("criar_snapshot_sistema(", SOURCE)
        self.assertIn("_ADMIN_OPERATIONS.prepare_update", SOURCE)
        self.assertIn("UpdatePackageService", ADMIN_MANAGER)
        self.assertIn("--apply-update", ADMIN_MANAGER)
        self.assertIn("service.prepare(", ADMIN_MANAGER)
        self.assertIn("_validar_atualizacao_apos_reinicio()", SOURCE)

    def test_update_rejection_uses_recoverable_minimizable_window(self):
        self.assertIn("def mostrar_aviso_atualizacao", SOURCE)
        self.assertIn('text="Minimizar"', SOURCE)
        self.assertIn("command=aviso.iconify", SOURCE)
        self.assertIn('text="Copiar detalhes"', SOURCE)
        self.assertIn('mesma_revisao = "não é mais novo"', SOURCE)
        block = SOURCE[SOURCE.index("def selecionar_pacote_atualizacao"):SOURCE.index("def aplicar_pacote_atualizacao")]
        self.assertNotIn('messagebox.showerror("Atualização"', block)

    def test_factory_reset_requests_password_in_dedicated_modal(self):
        self.assertIn('text="Continuar e informar senha"', SOURCE)
        self.assertIn('auth.title("Autorizar restauração")', SOURCE)
        self.assertIn('text="Senha administrativa ou senha mestra"', SOURCE)
        self.assertIn("command=solicitar_autorizacao_e_executar", SOURCE)
        self.assertNotIn(
            'text="Senha administrativa", font=ctk.CTkFont(size=12, weight="bold")).grid(row=8',
            SOURCE,
        )

    def test_existing_installations_start_without_login_window(self):
        create_ui = SOURCE.index("self.criar_menu_lateral()")
        automatic_session = SOURCE.index(
            'self.security.start_session_without_password("admin")'
        )
        self.assertGreater(automatic_session, create_ui)
        self.assertIn("def _login_usuarios_habilitado(self):", SOURCE)
        self.assertIn("Login automático desativado", SOURCE)
        self.assertIn("def abrir_login_usuario(self):", SOURCE)
        self.assertNotIn("self.after(250, self.abrir_login_usuario)", SOURCE)


if __name__ == "__main__":
    unittest.main()
