class FiscalDocumentWorkspaceController:
    """Controla a área de consulta fiscal sem reposicionar widgets irmãos."""

    def __init__(self, *, workspace, result_frame, context_actions, action_panel):
        self.workspace = workspace
        self.result_frame = result_frame
        self.context_actions = context_actions
        self.action_panel = action_panel

    def show_filters(self):
        self.workspace.pack(
            fill="both", expand=True, padx=12, pady=(0, 10), before=self.action_panel
        )
        self.hide_results()

    def show_results(self):
        self.result_frame.pack(fill="both", expand=True)

    def hide_results(self):
        self.context_actions.pack_forget()
        self.result_frame.pack_forget()

    def hide(self):
        self.hide_results()
        self.workspace.pack_forget()
