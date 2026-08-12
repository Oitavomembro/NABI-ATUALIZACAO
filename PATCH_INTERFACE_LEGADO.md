# PATCH_INTERFACE_LEGADO — Identidade visual e responsividade global

Base: `NabiCode_v2_4_95_TESTE_REIMPRESSAO_LAYOUT`

Este arquivo é somente instrução de patch. `nabicode_legacy.py` **não foi modificado** nesta entrega.

## 1. Imports visuais

Localização aproximada: linhas 35–36.

### Bloco antigo
```python
from ui import NabiTheme, configure_ctk, configure_ttk, apply_responsive_geometry
from ui.keyboard_navigation import install_global_arrow_navigation
```

### Bloco novo
```python
from ui import (
    NabiTheme,
    BackgroundManager,
    BackgroundSettings,
    LayoutManager,
    configure_ctk,
    configure_ttk,
    apply_responsive_geometry,
)
from ui.keyboard_navigation import install_global_arrow_navigation
```

Motivo: usar exclusivamente a infraestrutura visual centralizada, sem regras de negócio.

## 2. Remover desenho local duplicado da borboleta

Função: `_criar_borboleta_fundo` — aproximadamente linha 1119.

### Bloco antigo
```python
    def _criar_borboleta_fundo(self, parent):
        """Desenha a marca d'água sem depender de arquivo de imagem externo."""
        canvas = tk.Canvas(parent, width=150, height=120, bg="#161b22", highlightthickness=0, bd=0)
        canvas.place(relx=1.0, rely=1.0, x=-18, y=-18, anchor="se")
        canvas.create_oval(22, 20, 72, 72, outline="#243447", width=3)
        canvas.create_oval(78, 20, 128, 72, outline="#243447", width=3)
        canvas.create_oval(32, 60, 72, 105, outline="#1d2b3a", width=3)
        canvas.create_oval(78, 60, 118, 105, outline="#1d2b3a", width=3)
        canvas.create_oval(70, 30, 80, 96, fill="#243447", outline="#243447")
        canvas.create_line(73, 32, 58, 12, fill="#243447", width=2, smooth=True)
        canvas.create_line(77, 32, 92, 12, fill="#243447", width=2, smooth=True)
        def rebaixar_canvas():
            try:
                if canvas.winfo_exists():
                    canvas.tk.call("lower", canvas._w)
            except Exception:
                pass
        parent.after_idle(rebaixar_canvas)
        return canvas
```

### Bloco novo
```python
    def _criar_borboleta_fundo(self, parent):
        """Compatibilidade temporária: delega a marca d'água ao gerenciador único."""
        manager = getattr(self, "background_manager", None)
        if manager is None:
            return None
        return manager.attach(parent)
```

Motivo: eliminar lógica de fundo espalhada, `Canvas` decorativo duplicado e redraw independente.

## 3. Inicialização única e aplicação a todas as telas

Função: `criar_telas` — aproximadamente linha 1404.

### Bloco antigo
```python
    def criar_telas(self):
        self.container_telas = ctk.CTkFrame(self, fg_color="transparent")
        self.container_telas.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.container_telas.grid_rowconfigure(0, weight=1)
        self.container_telas.grid_columnconfigure(0, weight=1)
        
        self.telas = {}
        self.telas["dashboard"] = self.tela_dashboard(self.container_telas)
        self.telas["vendas"] = self.tela_vendas(self.container_telas)
        self.telas["clientes"] = self.tela_clientes(self.container_telas)
        self.telas["produtos"] = self.tela_produtos(self.container_telas)
        self.telas["financeiro"] = self.tela_financeiro(self.container_telas)
        self.telas["compras"] = self.tela_compras(self.container_telas)
        self.telas["relatorios"] = self.tela_relatorios(self.container_telas)
        self.telas["configs"] = self.tela_configs(self.container_telas)
```

### Bloco novo
```python
    def criar_telas(self):
        self.container_telas = ctk.CTkFrame(self, fg_color="transparent")
        self.container_telas.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        LayoutManager.configure_root(self.container_telas)

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

        self.telas = {}
        self.telas["dashboard"] = self.tela_dashboard(self.container_telas)
        self.telas["vendas"] = self.tela_vendas(self.container_telas)
        self.telas["clientes"] = self.tela_clientes(self.container_telas)
        self.telas["produtos"] = self.tela_produtos(self.container_telas)
        self.telas["financeiro"] = self.tela_financeiro(self.container_telas)
        self.telas["compras"] = self.tela_compras(self.container_telas)
        self.telas["relatorios"] = self.tela_relatorios(self.container_telas)
        self.telas["configs"] = self.tela_configs(self.container_telas)
        for tela in self.telas.values():
            self.background_manager.attach(tela)
```

Motivo: uma instância, um debounce, cache limitado e aplicação global. A leitura de `impressao_logo_path` é somente para reutilizar o caminho da logo já existente; nenhuma rotina documental é modificada.

## 4. Persistência das preferências de fundo

Função: `_salvar_preferencias_interface` — aproximadamente linha 1787.

### Inserir no dicionário passado a `UIPreferencesService.normalize`
```python
            "background_enabled": bool(self.var_background_enabled.get()) if hasattr(self, "var_background_enabled") else self.preferencias_interface.get("background_enabled", True),
            "background_opacity": float(self.slider_background_opacity.get()) if hasattr(self, "slider_background_opacity") else self.preferencias_interface.get("background_opacity", 0.10),
            "background_scale": self.combo_background_scale.get() if hasattr(self, "combo_background_scale") else self.preferencias_interface.get("background_scale", "automática"),
            "background_position": self.combo_background_position.get() if hasattr(self, "combo_background_position") else self.preferencias_interface.get("background_position", "centro"),
```

Depois de `_persistir_preferencias_interface()` inserir:
```python
        manager = getattr(self, "background_manager", None)
        if manager is not None:
            manager.set_enabled(dados["background_enabled"])
            manager.set_opacity(dados["background_opacity"])
            manager.set_scale(dados["background_scale"])
            manager.set_position(dados["background_position"])
            manager.set_logo_path(obter_config("impressao_logo_path") or None)
```

Motivo: persistir no mecanismo existente de preferências por usuário, sem criar segundo sistema de configuração.

## 5. Controles em Configurações

Função: `tela_configs` — inserir imediatamente após `self.combo_tema_oficial.set(...)`, aproximadamente linha 8485.

```python
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
            linha_opacidade,
            from_=0.02,
            to=0.25,
            number_of_steps=23,
        )
        self.slider_background_opacity.set(self.preferencias_interface["background_opacity"])
        self.slider_background_opacity.pack(side="left", fill="x", expand=True)

        linha_escala = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        linha_escala.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_escala, text="Escala:", width=120, anchor="w").pack(side="left")
        self.combo_background_scale = ctk.CTkComboBox(
            linha_escala,
            values=list(UIPreferencesService.BACKGROUND_SCALES),
            state="readonly",
        )
        self.combo_background_scale.set(self.preferencias_interface["background_scale"])
        self.combo_background_scale.pack(side="left", fill="x", expand=True)

        linha_posicao = ctk.CTkFrame(frame_form_cfg, fg_color="transparent")
        linha_posicao.pack(fill="x", pady=4)
        ctk.CTkLabel(linha_posicao, text="Posição:", width=120, anchor="w").pack(side="left")
        self.combo_background_position = ctk.CTkComboBox(
            linha_posicao,
            values=list(UIPreferencesService.BACKGROUND_POSITIONS),
            state="readonly",
        )
        self.combo_background_position.set(self.preferencias_interface["background_position"])
        self.combo_background_position.pack(side="left", fill="x", expand=True)
```

Motivo: disponibilizar ativação, opacidade, escala e posição usando as preferências existentes.

## 6. Clientes — substituir shell rolável por grid expansível

Função: `tela_clientes` — aproximadamente linha 6051.

Substituir, dentro da função, o trecho desde `self.criar_cabecalho_e_botoes(frame)` até a criação de `conteudo_cli` por:

```python
        LayoutManager.configure_vertical_shell(frame, expandable_row=1)
        self.criar_cabecalho_e_botoes(frame)

        conteudo_cli = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=12)
        conteudo_cli.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)
        LayoutManager.configure_vertical_shell(conteudo_cli, expandable_row=2)
        self.background_manager.attach(conteudo_cli)
```

Depois, migrar os quatro blocos diretos de `conteudo_cli` para grid, mantendo widgets e comandos existentes:

```python
        frame_topo_cli.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        frame_busca_cli.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 5))
        tabela_cli_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=5)
        acoes_clientes.grid(row=3, column=0, sticky="ew", padx=15, pady=(6, 6))
        self.adicionar_rodape_status(frame)
```

No `tabela_cli_frame`, configurar expansão e scrollbar vertical:

```python
        LayoutManager.configure_root(tabela_cli_frame)
        scrollbar_cli = ttk.Scrollbar(tabela_cli_frame, orient="vertical", command=self.tabela_cli.yview)
        self.tabela_cli.configure(yscrollcommand=scrollbar_cli.set)
        self.tabela_cli.grid(row=0, column=0, sticky="nsew")
        scrollbar_cli.grid(row=0, column=1, sticky="ns")
```

Remover o `self.tabela_cli.pack(...)` antigo.

Após a criação da tabela, configurar ajuste horizontal somente quando a largura realmente mudar:

```python
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
```

Motivo: a tabela absorve o espaço vertical e horizontal; cabeçalho, pesquisa, botões e rodapé não crescem artificialmente; CPF/Favorito preservam mínimos; elimina scroll horizontal estrutural desnecessário.

Observação: remover também `self.scroll_clientes` e o bloco `scroll_clientes.canvas.xview_moveto(0)` de `mostrar_tela`, pois o shell de Clientes deixa de usar `BidirectionalScrollableFrame`.

## 7. Histórico de cliente — geometry responsivo e miolo expansível

Função: `abrir_historico_cliente` — aproximadamente linha 6818.

### Bloco antigo
```python
        win.geometry("980x760")
        win.minsize(840, 650)
```

### Bloco novo
```python
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
```

Manter cabeçalho, painel, observações e barra de botões sem `expand=True`. Manter somente `abas.pack(fill="both", expand=True, ...)` como área expansível.

Motivo: saldo permanece no cabeçalho fixo; abas absorvem toda a altura restante; botão Fechar permanece acessível em janela restaurada.

## 8. Aplicação imediata após salvar Configurações

Função: `salvar_configuracoes_gerais` — logo após `_aplicar_personalizacao(...)`.

Inserir:
```python
        if hasattr(self, "background_manager"):
            self.background_manager.refresh(immediate=True)
```

Motivo: aplicar identidade visual sem reinício e sem recriar o gerenciador.

## Escopo preservado

O patch não altera cálculos, saldo, recebimentos, banco, schema, migração, estoque, regras de venda, impressão, PDF ou reimpressão. `BackgroundManager` apenas lê o caminho de logo já configurado e não modifica a configuração documental.
