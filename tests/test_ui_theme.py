from ui.theme import (
    DEFAULT_THEME,
    DEFAULT_THEME_MANAGER,
    NabiTheme,
    ThemeManager,
    apply_responsive_geometry,
    configure_ttk,
)


class FakeWindow:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.geometry_value = None
        self.minsize_value = None

    def winfo_screenwidth(self):
        return self.width

    def winfo_screenheight(self):
        return self.height

    def geometry(self, value):
        self.geometry_value = value

    def minsize(self, width, height):
        self.minsize_value = (width, height)


class FakeStyle:
    def __init__(self):
        self.theme = None
        self.configurations = {}
        self.mappings = {}

    def theme_use(self, value):
        self.theme = value

    def configure(self, name, **options):
        self.configurations[name] = options

    def map(self, name, **options):
        self.mappings[name] = options


def test_theme_tokens_keep_accessible_dark_contrast_contract():
    theme = NabiTheme()
    assert theme.background != theme.text
    assert theme.surface != theme.text
    assert theme.min_width >= 1000
    assert theme.min_height >= 650
    assert theme.button_height == theme.input_height


def test_default_manager_uses_default_theme():
    assert DEFAULT_THEME_MANAGER.theme is DEFAULT_THEME


def test_font_roles_are_centralized_and_have_safe_fallback():
    manager = ThemeManager()
    assert manager.font_spec("title") == ("Segoe UI", 20, "bold")
    assert manager.font_spec("body") == ("Segoe UI", 12, "normal")
    assert manager.font_spec("invalid") == ("Segoe UI", 12, "normal")


def test_button_variants_share_dimensions_and_allow_overrides():
    manager = ThemeManager()
    primary = manager.button_options("primary")
    secondary = manager.button_options("secondary", height=40)
    fallback = manager.button_options("unknown")

    assert primary["height"] == DEFAULT_THEME.button_height
    assert primary["corner_radius"] == DEFAULT_THEME.radius_medium
    assert secondary["height"] == 40
    assert secondary["border_width"] == 1
    assert fallback["fg_color"] == primary["fg_color"]


def test_entry_menu_and_scrollbar_options_use_shared_tokens():
    manager = ThemeManager()
    entry = manager.entry_options()
    menu = manager.menu_options()
    scrollbar = manager.scrollbar_options()

    assert entry["height"] == DEFAULT_THEME.input_height
    assert entry["font"] == manager.font_spec("body")
    assert menu["activebackground"] == DEFAULT_THEME.accent_hover
    assert scrollbar["width"] == DEFAULT_THEME.scrollbar_width


def test_ttk_configuration_covers_tables_headers_and_scrollbars():
    style = FakeStyle()
    ThemeManager().configure_ttk(style)

    assert style.theme == "clam"
    assert style.configurations["Treeview"]["rowheight"] == DEFAULT_THEME.table_row_height
    assert style.configurations["Treeview.Heading"]["font"] == ("Segoe UI", 10, "bold")
    assert "Vertical.TScrollbar" in style.configurations
    assert "Horizontal.TScrollbar" in style.configurations
    assert style.mappings["Treeview"]["background"] == [
        ("selected", DEFAULT_THEME.accent_hover)
    ]


def test_legacy_ttk_adapter_preserves_custom_theme_and_row_height():
    custom = NabiTheme(table_row_height=31, accent_hover="#123456")
    style = FakeStyle()
    configure_ttk(style, theme=custom, row_height=32)

    assert style.configurations["Treeview"]["rowheight"] == 32
    assert style.mappings["Treeview"]["background"] == [("selected", "#123456")]


def test_geometry_uses_preferred_size_on_large_screen():
    window = FakeWindow(1920, 1080)
    assert apply_responsive_geometry(window) == "1220x780"
    assert window.geometry_value == "1220x780"
    assert window.minsize_value == (DEFAULT_THEME.min_width, DEFAULT_THEME.min_height)


def test_geometry_respects_minimum_on_small_screen():
    window = FakeWindow(900, 600)
    assert apply_responsive_geometry(window) == "1050x680"
    assert window.minsize_value == (1050, 680)


def test_geometry_adapts_between_minimum_and_preferred():
    window = FakeWindow(1150, 760)
    assert apply_responsive_geometry(window) == "1070x680"


def test_frame_and_label_options_are_centralized():
    manager = ThemeManager()
    frame = manager.frame_options()
    elevated = manager.frame_options(elevated=True)
    label = manager.label_options("subtitle", muted=True)

    assert frame["fg_color"] == DEFAULT_THEME.surface
    assert frame["border_width"] == DEFAULT_THEME.border_width
    assert elevated["fg_color"] == DEFAULT_THEME.surface_elevated
    assert label["font"] == manager.font_spec("subtitle")
    assert label["text_color"] == DEFAULT_THEME.text_muted


def test_form_component_options_share_accessible_tokens():
    manager = ThemeManager()
    combo = manager.combobox_options()
    textbox = manager.textbox_options()
    checkbox = manager.checkbox_options()

    assert combo["height"] == DEFAULT_THEME.input_height
    assert combo["dropdown_text_color"] == DEFAULT_THEME.text
    assert textbox["scrollbar_button_color"] == DEFAULT_THEME.border
    assert checkbox["hover_color"] == DEFAULT_THEME.accent_hover


def test_tabview_options_remove_visual_differences():
    options = ThemeManager().tabview_options()

    assert options["height"] == DEFAULT_THEME.tab_height
    assert options["border_width"] == DEFAULT_THEME.border_width
    assert options["segmented_button_selected_color"] == DEFAULT_THEME.accent_hover


def test_additional_ctk_controls_share_theme_tokens():
    manager = ThemeManager()
    optionmenu = manager.optionmenu_options()
    radio = manager.radiobutton_options()
    switch = manager.switch_options()
    slider = manager.slider_options()
    progress = manager.progressbar_options()

    assert optionmenu["width"] == DEFAULT_THEME.control_width
    assert optionmenu["font"] == manager.font_spec("body")
    assert radio["fg_color"] == DEFAULT_THEME.accent
    assert switch["progress_color"] == DEFAULT_THEME.accent
    assert slider["button_hover_color"] == DEFAULT_THEME.accent_hover
    assert progress["height"] == DEFAULT_THEME.spacing_medium


def test_scrollable_frame_centralizes_scrollbar_and_heading_style():
    options = ThemeManager().scrollable_frame_options()

    assert options["fg_color"] == DEFAULT_THEME.surface
    assert options["scrollbar_button_color"] == DEFAULT_THEME.border
    assert options["label_font"] == ("Segoe UI", 14, "bold")


def test_component_options_dispatches_aliases_and_overrides():
    manager = ThemeManager()

    assert manager.component_options("option_menu", width=220)["width"] == 220
    assert manager.component_options("scrollable-frame")["corner_radius"] == DEFAULT_THEME.radius_large
    assert manager.component_options("button", variant="danger")["fg_color"] == DEFAULT_THEME.danger


def test_component_options_rejects_unknown_component():
    manager = ThemeManager()

    try:
        manager.component_options("unknown")
    except ValueError as exc:
        assert "Componente visual desconhecido" in str(exc)
    else:
        raise AssertionError("Componente desconhecido deveria gerar ValueError")


def test_component_registry_covers_all_supported_ctk_factories():
    manager = ThemeManager()
    supported = {
        "button",
        "frame",
        "label",
        "entry",
        "combobox",
        "optionmenu",
        "textbox",
        "checkbox",
        "radiobutton",
        "switch",
        "slider",
        "progressbar",
        "scrollableframe",
        "tabview",
        "scrollbar",
    }

    assert set(manager._COMPONENT_FACTORIES) == supported
    for component in supported:
        assert isinstance(manager.component_options(component), dict)


def test_component_alias_normalization_ignores_spacing_separators_and_case():
    manager = ThemeManager()

    assert manager.component_options("  OPTION_MENU  ") == manager.optionmenu_options()
    assert manager.component_options("Scrollable-Frame") == manager.scrollable_frame_options()


def test_text_controls_share_visual_base_without_sharing_mutable_dicts():
    manager = ThemeManager()
    entry = manager.entry_options()
    textbox = manager.textbox_options()

    for key in ("corner_radius", "fg_color", "border_width", "border_color", "text_color", "font"):
        assert entry[key] == textbox[key]

    entry["fg_color"] = "changed"
    assert textbox["fg_color"] == DEFAULT_THEME.surface


def test_selection_controls_share_accessible_visual_base():
    manager = ThemeManager()
    checkbox = manager.checkbox_options()
    radio = manager.radiobutton_options()

    for key in ("fg_color", "hover_color", "border_color", "text_color", "font"):
        assert checkbox[key] == radio[key]
