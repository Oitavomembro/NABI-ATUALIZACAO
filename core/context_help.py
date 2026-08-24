"""Ajuda contextual acionada por F1 em qualquer tela do NabiCode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Sequence, Tuple
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class HelpShortcut:
    keys: str
    action: str


@dataclass(frozen=True)
class HelpTopic:
    context: str
    title: str
    description: str
    shortcuts: Tuple[HelpShortcut, ...]
    notes: Tuple[str, ...] = ()


GLOBAL_SHORTCUTS: Tuple[HelpShortcut, ...] = (
    HelpShortcut("Enter", "Confirmar ou avançar para o próximo campo"),
    HelpShortcut("Shift+Enter", "Voltar ao campo anterior"),
    HelpShortcut("Ctrl+S", "Salvar"),
    HelpShortcut("Ctrl+N", "Novo registro"),
    HelpShortcut("Ctrl+E", "Editar o registro selecionado"),
    HelpShortcut("Ctrl+F", "Pesquisar na tela atual"),
    HelpShortcut("Del", "Excluir o item selecionado"),
    HelpShortcut("Esc", "Fechar a janela atual"),
    HelpShortcut("Ctrl+M", "Minimizar a janela ativa"),
    HelpShortcut("F11", "Alternar tela cheia"),
    HelpShortcut("F1", "Abrir esta ajuda"),
)


DEFAULT_TOPICS: Tuple[HelpTopic, ...] = (
    HelpTopic(
        "global",
        "Atalhos gerais",
        "Comandos disponíveis em todo o NabiCode.",
        GLOBAL_SHORTCUTS,
        (
            "Dentro de campos de texto, Del apaga caracteres normalmente.",
            "Operações destrutivas exibem confirmação antes de executar.",
        ),
    ),
    HelpTopic(
        "dashboard",
        "Início / Dashboard",
        "Resumo operacional e acesso rápido aos módulos.",
        (
            HelpShortcut("Ctrl+F", "Pesquisar na tela atual"),
            HelpShortcut("Ctrl+N", "Abrir uma nova operação quando suportado"),
            HelpShortcut("F1", "Ajuda do Dashboard"),
            HelpShortcut("Esc", "Fechar o sistema com confirmação"),
        ),
        ("Os cartões exibidos dependem do modo e das preferências do usuário.",),
    ),
    HelpTopic(
        "produtos",
        "Produtos",
        "Cadastro, consulta, importação XML e manutenção de produtos.",
        (
            HelpShortcut("Ctrl+N", "Cadastrar novo produto"),
            HelpShortcut("Ctrl+E", "Editar produto selecionado"),
            HelpShortcut("Ctrl+F", "Focar a pesquisa de produtos"),
            HelpShortcut("Enter", "Abrir ou confirmar o produto selecionado"),
            HelpShortcut("Del", "Excluir/desativar o produto selecionado"),
            HelpShortcut("F1", "Ajuda de Produtos"),
        ),
        (
            "Nomes de produtos são normalizados em caixa alta quando a configuração estiver ativa.",
            "Produtos com movimentação podem ser bloqueados contra exclusão definitiva.",
        ),
    ),
    HelpTopic(
        "produto_form",
        "Cadastro de Produto",
        "Preencha os dados do produto e use Enter para avançar pelos campos.",
        (
            HelpShortcut("Enter", "Próximo campo; no último campo, salvar"),
            HelpShortcut("Shift+Enter", "Campo anterior"),
            HelpShortcut("Ctrl+S", "Salvar produto"),
            HelpShortcut("Esc", "Fechar; pergunta sobre alterações não salvas"),
            HelpShortcut("Ctrl+C / Ctrl+V", "Copiar e colar no campo ativo"),
            HelpShortcut("F1", "Ajuda do cadastro"),
        ),
        ("Campos inválidos recebem foco antes que o produto seja salvo.",),
    ),
    HelpTopic(
        "clientes",
        "Clientes",
        "Consulta e manutenção do cadastro de clientes.",
        (
            HelpShortcut("Ctrl+N", "Cadastrar novo cliente"),
            HelpShortcut("Ctrl+E", "Editar cliente selecionado"),
            HelpShortcut("Ctrl+F", "Focar a pesquisa de clientes"),
            HelpShortcut("Enter", "Abrir cliente selecionado"),
            HelpShortcut("Del", "Excluir cliente selecionado"),
            HelpShortcut("F1", "Ajuda de Clientes"),
        ),
    ),
    HelpTopic(
        "vendas",
        "Vendas / PDV",
        "Tela independente para registrar vendas com operação por teclado.",
        (
            HelpShortcut("F2", "Focar busca de produto"),
            HelpShortcut("F3", "Focar seleção de cliente"),
            HelpShortcut("F4", "Alterar quantidade"),
            HelpShortcut("Enter", "Adicionar produto ou confirmar o campo atual"),
            HelpShortcut("Del", "Remover item selecionado do carrinho"),
            HelpShortcut("F9", "Finalizar venda"),
            HelpShortcut("F11", "Alternar tela cheia"),
            HelpShortcut("Esc", "Fechar o PDV; preserva venda em andamento"),
            HelpShortcut("F1", "Ajuda do PDV"),
        ),
        ("Ao reabrir o PDV, a venda em andamento é restaurada.",),
    ),
    HelpTopic(
        "xml_import",
        "Importação de XML",
        "Conferência obrigatória dos itens antes de gravar nota, estoque e financeiro.",
        (
            HelpShortcut("Enter", "Confirmar o campo e avançar; no último, validar o item"),
            HelpShortcut("Shift+Enter", "Voltar ao campo anterior"),
            HelpShortcut("Ctrl+S", "Concluir importação quando não houver pendências"),
            HelpShortcut("Del", "Desvincular/remover seleção do item"),
            HelpShortcut("Ctrl+C / Ctrl+V", "Copiar e colar quantidade, fator, margem ou preço"),
            HelpShortcut("Esc", "Cancelar importação"),
            HelpShortcut("F1", "Ajuda da importação"),
        ),
        (
            "A importação não deve concluir enquanto houver item sem vínculo, quantidade, fator, unidade, custo ou preço.",
            "Quantidade de estoque = quantidade recebida × fator de conversão.",
        ),
    ),
    HelpTopic(
        "nfe_devolucao",
        "NF-e de Devolução",
        "Assistente para localizar a nota original e montar uma devolução integral ou parcial.",
        (
            HelpShortcut("Enter", "Confirmar campo ou avançar"),
            HelpShortcut("Ctrl+S", "Salvar/finalizar rascunho quando válido"),
            HelpShortcut("Del", "Remover item selecionado da devolução"),
            HelpShortcut("Esc", "Fechar o assistente"),
            HelpShortcut("F1", "Ajuda da devolução"),
        ),
        ("O rascunho interno não substitui transmissão e autorização oficial pela SEFAZ.",),
    ),
    HelpTopic(
        "configs",
        "Configurações",
        "Preferências visuais, módulos, manutenção e parâmetros do sistema.",
        (
            HelpShortcut("Ctrl+S", "Salvar configurações"),
            HelpShortcut("Ctrl+F", "Pesquisar opção quando disponível"),
            HelpShortcut("Esc", "Fechar a janela atual"),
            HelpShortcut("F1", "Ajuda de Configurações"),
        ),
        ("Restaurações e limpezas exigem backup e confirmação reforçada.",),
    ),
    HelpTopic("caixa", "Caixa", "Abertura, movimentos e fechamento do caixa.", (
        HelpShortcut("Enter", "Confirmar a ação ou campo atual"), HelpShortcut("Shift+Enter", "Voltar ao campo anterior"),
        HelpShortcut("Esc", "Fechar somente a janela atual"),
    ), ("Sangria, suprimento e fechamento exigem permissão e confirmação.",)),
    HelpTopic("financeiro", "Financeiro", "Consulta e baixa de contas a receber e pagar.", (
        HelpShortcut("Ctrl+F", "Pesquisar títulos"), HelpShortcut("Enter", "Abrir ou confirmar o título selecionado"),
        HelpShortcut("Esc", "Fechar somente a janela atual"),
    ), ("Baixas usam a identidade da sessão autenticada.",)),
    HelpTopic("relatorios", "Relatórios", "Consultas e exportações comerciais.", (
        HelpShortcut("Enter", "Gerar o relatório com os filtros atuais"), HelpShortcut("Esc", "Fechar a janela"),
    )),
    HelpTopic("compras", "Fornecedores / Compras", "Pedidos e recebimentos pelos serviços oficiais.", (
        HelpShortcut("Enter", "Confirmar a etapa atual"), HelpShortcut("Shift+Enter", "Voltar à etapa anterior"),
        HelpShortcut("Esc", "Fechar a janela atual"),
    ), ("Recebimentos repetidos são recusados pelo núcleo.",)),
    HelpTopic("usuarios", "Usuários", "Contas, perfis e permissões do NabiCode.", (
        HelpShortcut("Enter", "Abrir ou salvar a ação atual"), HelpShortcut("Esc", "Cancelar ou fechar"),
    ), ("Nenhuma tela concede permissão fora do perfil autenticado.",)),
    HelpTopic("impressao", "Impressão", "Impressoras, formatos e modelos de comprovante.", (
        HelpShortcut("Enter", "Confirmar o controle atual"), HelpShortcut("Shift+Enter", "Voltar ao controle anterior"),
        HelpShortcut("Esc", "Fechar Configurações"),
    ), ("Atualizar a prévia ou salvar não envia documento à impressora.",)),
)


class ContextHelpRegistry:
    """Armazena tópicos e resolve aliases sem depender da interface gráfica."""

    ALIASES = {
        "inicio": "dashboard",
        "home": "dashboard",
        "pdv": "vendas",
        "sale": "vendas",
        "produto": "produto_form",
        "cadastro_produto": "produto_form",
        "importacao_xml": "xml_import",
        "xml": "xml_import",
        "devolucao": "nfe_devolucao",
        "configuracoes": "configs",
        "fornecedores": "compras",
        "printing": "impressao",
    }

    def __init__(self, topics: Iterable[HelpTopic] = DEFAULT_TOPICS) -> None:
        self._topics: Dict[str, HelpTopic] = {topic.context: topic for topic in topics}
        if "global" not in self._topics:
            raise ValueError("O tópico global é obrigatório.")

    def normalize_context(self, context: Optional[str]) -> str:
        key = (context or "global").strip().lower()
        return self.ALIASES.get(key, key)

    def get(self, context: Optional[str]) -> HelpTopic:
        key = self.normalize_context(context)
        return self._topics.get(key, self._topics["global"])

    def register(self, topic: HelpTopic) -> None:
        if not topic.context.strip():
            raise ValueError("O contexto do tópico não pode ser vazio.")
        self._topics[topic.context.strip().lower()] = topic

    def contexts(self) -> Sequence[str]:
        return tuple(sorted(self._topics))


class ContextHelpController:
    """Detecta a tela ativa e abre uma ajuda não destrutiva e pesquisável."""

    def __init__(self, root: tk.Misc, registry: Optional[ContextHelpRegistry] = None) -> None:
        self.root = root
        self.registry = registry or ContextHelpRegistry()
        self._window: Optional[tk.Toplevel] = None

    def resolve_context(self, explicit: Optional[str] = None) -> str:
        if explicit:
            return self.registry.normalize_context(explicit)
        try:
            focused = self.root.focus_get()
            if focused is not None:
                top = focused.winfo_toplevel()
                context = getattr(top, "nabi_help_context", None)
                if context:
                    return self.registry.normalize_context(context)
        except Exception:
            pass
        return self.registry.normalize_context(getattr(self.root, "tela_atual", "global"))

    def show(self, context: Optional[str] = None) -> str:
        resolved = self.resolve_context(context)
        topic = self.registry.get(resolved)
        if self._window is not None:
            try:
                if self._window.winfo_exists():
                    self._window.destroy()
            except Exception:
                pass

        win = tk.Toplevel(self.root)
        self._window = win
        win.title(f"Ajuda — {topic.title}")
        win.geometry("760x590")
        win.minsize(620, 460)
        win.transient(self.root)
        win.configure(bg="#0d1117")
        win.nabi_help_context = resolved
        win.grid_rowconfigure(2, weight=1)
        win.grid_columnconfigure(0, weight=1)

        header = tk.Frame(win, bg="#161b22", padx=18, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text=topic.title, bg="#161b22", fg="#58a6ff", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(header, text=topic.description, bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 10), wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))

        search_frame = tk.Frame(win, bg="#0d1117", padx=18, pady=10)
        search_frame.grid(row=1, column=0, sticky="ew")
        tk.Label(search_frame, text="Filtrar atalhos:", bg="#0d1117", fg="#c9d1d9", font=("Segoe UI", 10, "bold")).pack(side="left")
        query = tk.StringVar()
        entry = ttk.Entry(search_frame, textvariable=query)
        entry.pack(side="left", fill="x", expand=True, padx=(10, 0))

        body = tk.Frame(win, bg="#0d1117", padx=18, pady=0)
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(body, columns=("keys", "action"), show="headings", selectmode="browse")
        tree.heading("keys", text="Tecla")
        tree.heading("action", text="Ação")
        tree.column("keys", width=145, minwidth=110, anchor="center")
        tree.column("action", width=510, minwidth=300, anchor="w")
        sy = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        sx = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")

        notes_text = "\n".join(f"• {note}" for note in topic.notes)
        notes = tk.Label(win, text=notes_text, bg="#0d1117", fg="#8b949e", font=("Segoe UI", 9), justify="left", wraplength=710, padx=18, pady=10)
        notes.grid(row=3, column=0, sticky="ew")

        footer = tk.Frame(win, bg="#161b22", padx=18, pady=10)
        footer.grid(row=4, column=0, sticky="ew")
        ttk.Button(footer, text="Atalhos gerais", command=lambda: self._replace_topic(win, "global")).pack(side="left")
        ttk.Button(footer, text="Fechar [Esc]", command=win.destroy).pack(side="right")

        def refresh(*_args: object) -> None:
            term = query.get().strip().casefold()
            tree.delete(*tree.get_children())
            for shortcut in topic.shortcuts:
                haystack = f"{shortcut.keys} {shortcut.action}".casefold()
                if term and term not in haystack:
                    continue
                tree.insert("", "end", values=(shortcut.keys, shortcut.action))

        query.trace_add("write", refresh)
        refresh()
        win.bind("<Escape>", lambda _event: win.destroy())
        win.bind("<F1>", lambda _event: "break")
        win.after(80, entry.focus_set)
        return resolved

    def _replace_topic(self, win: tk.Toplevel, context: str) -> None:
        try:
            win.destroy()
        finally:
            self.show(context)
