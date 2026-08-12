from ui.layout_manager import LayoutManager


class FakeGrid:
    def __init__(self): self.rows = {}; self.columns = {}
    def grid_rowconfigure(self, row, **kwargs): self.rows[row] = kwargs
    def grid_columnconfigure(self, col, **kwargs): self.columns[col] = kwargs


class FakeTree:
    def __init__(self): self.columns = {}
    def column(self, name, **kwargs): self.columns[name] = kwargs


def test_required_resolutions_produce_valid_viewports():
    for width, height in LayoutManager.SUPPORTED_RESOLUTIONS:
        viewport = LayoutManager.viewport(width, height)
        assert viewport.width == width and viewport.height == height
        assert viewport.table_min_height >= 180


def test_central_area_receives_expansion_weight():
    grid = FakeGrid()
    LayoutManager.configure_vertical_shell(grid, expandable_row=2)
    assert grid.rows[2]["weight"] == 1
    assert grid.columns[0]["weight"] == 1


def test_client_columns_never_cut_cpf_or_favorite():
    minimum_total = sum(LayoutManager.CLIENT_COLUMN_MINIMUMS.values())
    widths = LayoutManager.client_columns(minimum_total)
    assert widths["CPF"] >= 120
    assert widths["Fav"] >= 46
    assert widths["Nome"] >= 210


def test_client_table_absorbs_free_horizontal_space():
    minimum_total = sum(LayoutManager.CLIENT_COLUMN_MINIMUMS.values())
    widths = LayoutManager.client_columns(minimum_total + 600)
    assert sum(widths.values()) == minimum_total + 600
    assert widths["Nome"] > LayoutManager.CLIENT_COLUMN_MINIMUMS["Nome"]


def test_horizontal_scroll_only_when_minimum_columns_do_not_fit():
    widths = LayoutManager.client_columns(1600)
    assert LayoutManager.needs_horizontal_scroll(1600, widths) is False
    assert LayoutManager.needs_horizontal_scroll(700, LayoutManager.CLIENT_COLUMN_MINIMUMS) is True


def test_client_treeview_applies_safe_stretch_policy():
    tree = FakeTree(); widths = LayoutManager.apply_client_treeview(tree, 1400)
    assert tree.columns["CPF"]["stretch"] is True
    assert tree.columns["Fav"]["stretch"] is False
    assert tree.columns["CPF"]["width"] == widths["CPF"]


def test_history_window_geometry_fits_restored_and_large_windows():
    small_geo, small_min = LayoutManager.window_geometry(1024, 768)
    large_geo, large_min = LayoutManager.window_geometry(3840, 2160)
    sw, sh = map(int, small_geo.split("x")); lw, lh = map(int, large_geo.split("x"))
    assert sw <= 1024 and sh <= 768
    assert small_min[0] <= sw and small_min[1] <= sh
    assert (lw, lh) == (1100, 780)
    assert large_min == (840, 620)
