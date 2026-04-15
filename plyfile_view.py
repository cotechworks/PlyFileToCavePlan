"""Stable view helper functions.

These helpers keep the Tk Treeview and Matplotlib overlay in sync with the
ViewModel. This module is a clean, single-version implementation copied from
the working temporary helper and is safe to import from the GUI.
"""
from typing import List, Dict

import numpy as np
import matplotlib.colors as mcolors


def populate_tree_from_vm(tree, vm) -> List[Dict[str, float]]:
    # clear existing rows
    for item in list(tree.get_children()):
        try:
            tree.delete(item)
        except Exception:
            pass

    pts = vm.get_points() if vm is not None else []
    new_added = []
    for p in pts:
        try:
            item_id = tree.insert("", "end", values=(f"{p['x']:.6f}", f"{p['y']:.6f}", ""))
            new_added.append({"x": p["x"], "y": p["y"], "item": item_id})
        except Exception:
            pass
    return new_added


def points_from_tree(tree):
    pts = []
    for cid in list(tree.get_children()):
        try:
            vals = tree.item(cid, "values")
            if vals and len(vals) >= 2:
                x = float(vals[0])
                y = float(vals[1])
                pts.append({"x": x, "y": y})
        except Exception:
            pass
    return pts


def update_overlay_colors(state, sp_overlay_point_size=None, cmb_point_color=None, cmb_highlight_color=None):
    overlay = state.get("overlay")
    pts = state.get("added_points", [])
    if overlay is None or pts is None:
        return

    n = len(pts)
    if n == 0:
        try:
            overlay.set_offsets(np.empty((0, 2)))
        except Exception:
            pass
        return

    try:
        base_color = (
            mcolors.to_rgba(cmb_point_color.get()) if cmb_point_color is not None else (1.0, 0.0, 0.0, 1.0)
        )
    except Exception:
        base_color = (1.0, 0.0, 0.0, 1.0)
    try:
        hl_color = (
            mcolors.to_rgba(cmb_highlight_color.get()) if cmb_highlight_color is not None else (0.0, 0.0, 1.0, 1.0)
        )
    except Exception:
        hl_color = (0.0, 0.0, 1.0, 1.0)

    cols = np.tile(np.array(base_color), (n, 1))
    sel = set(state.get("points_table").selection()) if state.get("points_table") else set()
    for i, ap in enumerate(pts):
        try:
            if ap.get("item") in sel:
                cols[i] = np.array(hl_color)
        except Exception:
            pass

    try:
        overlay.set_facecolors(cols)
    except Exception:
        pass

    try:
        if sp_overlay_point_size is not None and hasattr(sp_overlay_point_size, "get") and sp_overlay_point_size.get():
            size_val = float(sp_overlay_point_size.get())
        else:
            size_val = state.get("cfg", {}).get("overlay_point_size", 40)
        overlay.set_sizes(np.full((n,), size_val))
    except Exception:
        pass

    try:
        cw = state.get("canvas_widget")
        if cw is not None:
            cw.draw_idle()
    except Exception:
        pass


def update_lengths_and_line(state, cmb_line_color=None, sp_line_width=None):
    pts = state.get("added_points", [])
    tbl = state.get("points_table")
    if tbl is None:
        return

    n = len(pts)
    if n == 0:
        lbl = state.get("total_len_label")
        if lbl is not None:
            try:
                lbl.config(text="Horizontal distance: 0.000000")
            except Exception:
                pass
        line = state.get("line_artist")
        if line is not None:
            try:
                line.remove()
            except Exception:
                pass
            state["line_artist"] = None
        try:
            overlay = state.get("overlay")
            if overlay is not None:
                overlay.set_offsets(np.empty((0, 2)))
            cw = state.get("canvas_widget")
            if cw is not None:
                cw.draw_idle()
        except Exception:
            pass
        return

    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    lens = [0.0] * n
    total = 0.0
    for i in range(1, n):
        dx = xs[i] - xs[i - 1]
        dy = ys[i] - ys[i - 1]
        d = (dx * dx + dy * dy) ** 0.5
        lens[i] = d
        total += d

    for i, ap in enumerate(pts):
        try:
            item = ap.get("item")
            if item:
                length_str = f"{lens[i]:.6f}" if i > 0 else ""
                tbl.item(item, values=(f"{ap['x']:.6f}", f"{ap['y']:.6f}", length_str))
        except Exception:
            pass

    try:
        lbl = state.get("total_len_label")
        if lbl is not None:
            lbl.config(text=f"Horizontal distance: {total:.6f}")
    except Exception:
        pass

    try:
        fig = state.get("fig")
        ax = fig.axes[0] if fig and fig.axes else None
        if ax is not None:
            line = state.get("line_artist")
            if n >= 2:
                if line is None:
                    try:
                        lc = mcolors.to_rgba(cmb_line_color.get()) if cmb_line_color is not None else "black"
                    except Exception:
                        lc = "black"
                    try:
                        lw = float(sp_line_width.get()) if sp_line_width is not None and sp_line_width.get() else 1.0
                    except Exception:
                        lw = 1.0
                    (lineobj,) = ax.plot(xs, ys, color=lc, linewidth=lw, zorder=90)
                    state["line_artist"] = lineobj
                else:
                    try:
                        line.set_data(xs, ys)
                    except Exception:
                        pass
                    try:
                        if cmb_line_color is not None:
                            line.set_color(mcolors.to_rgba(cmb_line_color.get()))
                    except Exception:
                        pass
                    try:
                        if sp_line_width is not None:
                            lw = float(sp_line_width.get()) if sp_line_width.get() else 1.0
                            line.set_linewidth(lw)
                    except Exception:
                        pass
            else:
                if line is not None:
                    try:
                        line.remove()
                    except Exception:
                        pass
                    state["line_artist"] = None
            try:
                cw = state.get("canvas_widget")
                if cw is not None:
                    cw.draw_idle()
            except Exception:
                pass
    except Exception:
        pass
"""Clean view helper functions (canonical).

Copy of the working helpers used to keep the Treeview and Matplotlib overlay
in sync with the ViewModel.
"""
from typing import List, Dict

import numpy as np
import matplotlib.colors as mcolors


def populate_tree_from_vm(tree, vm) -> List[Dict[str, float]]:
    # clear existing rows
    for item in list(tree.get_children()):
        try:
            tree.delete(item)
        except Exception:
            pass

    pts = vm.get_points() if vm is not None else []
    new_added = []
    for p in pts:
        try:
            item_id = tree.insert("", "end", values=(f"{p['x']:.6f}", f"{p['y']:.6f}", ""))
            new_added.append({"x": p["x"], "y": p["y"], "item": item_id})
        except Exception:
            pass
    return new_added


def points_from_tree(tree):
    pts = []
    for cid in list(tree.get_children()):
        try:
            vals = tree.item(cid, "values")
            if vals and len(vals) >= 2:
                x = float(vals[0])
                y = float(vals[1])
                pts.append({"x": x, "y": y})
        except Exception:
            pass
    return pts


def update_overlay_colors(state, sp_overlay_point_size=None, cmb_point_color=None, cmb_highlight_color=None):
    overlay = state.get("overlay")
    pts = state.get("added_points", [])
    if overlay is None or pts is None:
        return

    n = len(pts)
    if n == 0:
        try:
            overlay.set_offsets(np.empty((0, 2)))
        except Exception:
            pass
        return

    try:
        base_color = (
            mcolors.to_rgba(cmb_point_color.get()) if cmb_point_color is not None else (1.0, 0.0, 0.0, 1.0)
        )
    except Exception:
        base_color = (1.0, 0.0, 0.0, 1.0)
    try:
        hl_color = (
            mcolors.to_rgba(cmb_highlight_color.get()) if cmb_highlight_color is not None else (0.0, 0.0, 1.0, 1.0)
        )
    except Exception:
        hl_color = (0.0, 0.0, 1.0, 1.0)

    cols = np.tile(np.array(base_color), (n, 1))
    sel = set(state.get("points_table").selection()) if state.get("points_table") else set()
    for i, ap in enumerate(pts):
        try:
            if ap.get("item") in sel:
                cols[i] = np.array(hl_color)
        except Exception:
            pass

    try:
        overlay.set_facecolors(cols)
    except Exception:
        pass

    try:
        if sp_overlay_point_size is not None and hasattr(sp_overlay_point_size, "get") and sp_overlay_point_size.get():
            size_val = float(sp_overlay_point_size.get())
        else:
            size_val = state.get("cfg", {}).get("overlay_point_size", 40)
        overlay.set_sizes(np.full((n,), size_val))
    except Exception:
        pass

    try:
        cw = state.get("canvas_widget")
        if cw is not None:
            cw.draw_idle()
    except Exception:
        pass


def update_lengths_and_line(state, cmb_line_color=None, sp_line_width=None):
    pts = state.get("added_points", [])
    tbl = state.get("points_table")
    if tbl is None:
        return

    n = len(pts)
    if n == 0:
        lbl = state.get("total_len_label")
        if lbl is not None:
            try:
                lbl.config(text="Horizontal distance: 0.000000")
            except Exception:
                pass
        line = state.get("line_artist")
        if line is not None:
            try:
                line.remove()
            except Exception:
                pass
            state["line_artist"] = None
        try:
            overlay = state.get("overlay")
            if overlay is not None:
                overlay.set_offsets(np.empty((0, 2)))
            cw = state.get("canvas_widget")
            if cw is not None:
                cw.draw_idle()
        except Exception:
            pass
        return

    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    lens = [0.0] * n
    total = 0.0
    for i in range(1, n):
        dx = xs[i] - xs[i - 1]
        dy = ys[i] - ys[i - 1]
        d = (dx * dx + dy * dy) ** 0.5
        lens[i] = d
        total += d

    for i, ap in enumerate(pts):
        try:
            item = ap.get("item")
            if item:
                length_str = f"{lens[i]:.6f}" if i > 0 else ""
                tbl.item(item, values=(f"{ap['x']:.6f}", f"{ap['y']:.6f}", length_str))
        except Exception:
            pass

    try:
        lbl = state.get("total_len_label")
        if lbl is not None:
            lbl.config(text=f"Horizontal distance: {total:.6f}")
    except Exception:
        pass

    try:
        fig = state.get("fig")
        ax = fig.axes[0] if fig and fig.axes else None
        if ax is not None:
            line = state.get("line_artist")
            if n >= 2:
                if line is None:
                    try:
                        lc = mcolors.to_rgba(cmb_line_color.get()) if cmb_line_color is not None else "black"
                    except Exception:
                        lc = "black"
                    try:
                        lw = float(sp_line_width.get()) if sp_line_width is not None and sp_line_width.get() else 1.0
                    except Exception:
                        lw = 1.0
                    (lineobj,) = ax.plot(xs, ys, color=lc, linewidth=lw, zorder=90)
                    state["line_artist"] = lineobj
                else:
                    try:
                        line.set_data(xs, ys)
                    except Exception:
                        pass
                    try:
                        if cmb_line_color is not None:
                            line.set_color(mcolors.to_rgba(cmb_line_color.get()))
                    except Exception:
                        pass
                    try:
                        if sp_line_width is not None:
                            lw = float(sp_line_width.get()) if sp_line_width.get() else 1.0
                            line.set_linewidth(lw)
                    except Exception:
                        pass
            else:
                if line is not None:
                    try:
                        line.remove()
                    except Exception:
                        pass
                    state["line_artist"] = None
            try:
                cw = state.get("canvas_widget")
                if cw is not None:
                    cw.draw_idle()
            except Exception:
                pass
    except Exception:
        pass

