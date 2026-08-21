from ui.fiscal_center_layout import FiscalDocumentWorkspaceController


class FakeWidget:
    def __init__(self):
        self.visible = False
        self.pack_calls = []
        self.forget_calls = 0

    def pack(self, **kwargs):
        self.visible = True
        self.pack_calls.append(kwargs)

    def pack_forget(self):
        self.visible = False
        self.forget_calls += 1


def make_controller():
    widgets = {name: FakeWidget() for name in (
        "workspace", "result_frame", "context_actions", "action_panel"
    )}
    controller = FiscalDocumentWorkspaceController(**widgets)
    return controller, widgets


def test_card_opens_only_filters_in_one_isolated_workspace():
    controller, widgets = make_controller()

    controller.show_filters()

    assert widgets["workspace"].visible is True
    assert widgets["workspace"].pack_calls[-1]["before"] is widgets["action_panel"]
    assert widgets["result_frame"].visible is False
    assert widgets["context_actions"].visible is False


def test_results_are_shown_only_after_explicit_confirmation():
    controller, widgets = make_controller()
    controller.show_filters()

    controller.show_results()

    assert widgets["result_frame"].visible is True


def test_closing_workspace_hides_results_and_filters_together():
    controller, widgets = make_controller()
    controller.show_filters()
    controller.show_results()

    controller.hide()

    assert widgets["workspace"].visible is False
    assert widgets["result_frame"].visible is False
