"""GUI module for PlyFileToCavePlan.

Contains `launch_gui(initial_dir=None)` which starts the Tkinter GUI.
This module imports tkinter and matplotlib's TkAgg backend only when needed.
"""

from __future__ import annotations

import os
import sys
import json
import csv
import threading
import random
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

try:
    import tkinter as tk
    from tkinter import filedialog, ttk, messagebox
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

from plyfile_model import (
    load_config,
    save_config,
    parse_with_progress,
    export_points_csv,
    import_points_csv,
    get_config_path,
    create_figure,
    parse_file,
    plot_xy,
)


def launch_gui(initial_dir: Optional[str] = None) -> None:
    """Start the Tkinter GUI for PlyFileToCavePlan.

    If tkinter is not available, print a message and return.
    """
    if not TK_AVAILABLE:
        print("tkinter が利用できません。GUI を開始できません。")
        return

    def _get_config_path() -> str:
        # Delegate to the model implementation so there's a single source
        # of truth for the config file location.
        return get_config_path()

    def _load_config() -> dict:
        # Use the model's config loader
        return load_config()

    def _save_config(cfg: dict) -> None:
        # Delegate saving to the model
        save_config(cfg)

    state = {
        "path": None,
        "xs": [],
        "ys": [],
        "zs": None,
        "fig": None,
    }

    root = tk.Tk()
    root.title("PlyFileToCavePlan - GUI")

    frm = ttk.Frame(root, padding=8)
    frm.grid(row=0, column=0, sticky=tk.NSEW)

    cfg = _load_config()
    if not initial_dir and cfg.get("last_dir"):
        initial_dir = cfg.get("last_dir")

    # progress frame will be created after left_ctrl_frame so it can be
    # placed above the Quit button in the left controls column
    progress_frame = None

    # Main display: left = canvas, right = table
    display_frame = ttk.Frame(root)
    display_frame.grid(row=1, column=0, sticky=tk.NSEW)
    root.rowconfigure(1, weight=1)
    root.columnconfigure(0, weight=1)

    # left-side small frame for file controls (Open File etc.) to place at left of the graph
    left_ctrl_frame = ttk.Frame(display_frame, padding=(4, 4))
    left_ctrl_frame.grid(row=0, column=0, sticky=tk.NS)

    # create progress frame in left_ctrl_frame so it appears above Quit
    progress_frame = ttk.Frame(left_ctrl_frame)
    progress_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

    canvas_frame = ttk.Frame(display_frame)
    canvas_frame.grid(row=0, column=1, sticky=tk.NSEW)
    # allow the canvas_frame to expand to fill available vertical space
    try:
        display_frame.rowconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
    except Exception:
        pass
    # table on the right
    table_frame = ttk.Frame(display_frame, padding=(6, 0))
    table_frame.grid(row=0, column=2, sticky=tk.NS)
    # make the center canvas column take most of the horizontal space
    display_frame.columnconfigure(0, weight=0)
    display_frame.columnconfigure(1, weight=4)
    # set right table column to weight 0 to maximize canvas width
    display_frame.columnconfigure(2, weight=0)
    lbl_table = ttk.Label(table_frame, text="Added points:")
    lbl_table.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
    tree = ttk.Treeview(
        table_frame,
        columns=("x", "y", "len"),
        show="headings",
        height=5,
        selectmode="extended",
    )
    tree.heading("x", text="X")
    tree.heading("y", text="Y")
    tree.heading("len", text="Len")
    tree.column("x", width=120, anchor=tk.CENTER)
    tree.column("y", width=120, anchor=tk.CENTER)
    tree.column("len", width=100, anchor=tk.CENTER)
    # place tree across column 0 and 1 so controls can span the same columns
    tree.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW)
    # scrollbar for table placed in 3rd column
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.grid(row=1, column=2, sticky=tk.NS)
    table_frame.rowconfigure(1, weight=1)
    # tree spans columns 0-1; make column 0 flexible and column1 fixed so
    # tree gets the available width while the scrollbar (col 2) stays narrow
    table_frame.columnconfigure(0, weight=1)
    table_frame.columnconfigure(1, weight=0)
    table_frame.columnconfigure(2, weight=0)
    # store tree in state for access
    state["added_points"] = []
    state["points_table"] = tree
    state["canvas_widget"] = None
    state["mpl_cid"] = None
    state["remove_history"] = []  # stack of lists of removed points for undo
    state["overlay"] = None
    state["line_artist"] = None
    # buttons for remove/undo will be created after handlers are defined

    def _attach_canvas_handlers(canvas, fig):
        # attach click handler to canvas and store connection id
        try:
            ax = fig.axes[0] if fig.axes else None

            def _onclick(event):
                if event.inaxes is None or event.button != 1:
                    return
                x = event.xdata
                y = event.ydata
                if x is None or y is None:
                    return
                # insert into tree and state
                try:
                    item_id = state["points_table"].insert(
                        "", "end", values=(f"{x:.6f}", f"{y:.6f}", "")
                    )
                    state["added_points"].append({"x": x, "y": y, "item": item_id})
                except Exception:
                    pass
                try:
                    # update overlay scatter offsets instead of plotting a new artist
                    overlay = state.get("overlay")
                    if overlay is not None:
                        pts = state.get("added_points", [])
                        if pts:
                            xs = [p["x"] for p in pts]
                            ys = [p["y"] for p in pts]
                            offsets = np.column_stack((xs, ys))
                        else:
                            offsets = np.empty((0, 2))
                        try:
                            overlay.set_offsets(offsets)
                            # update sizes according to overlay size control
                            try:
                                size_val = (
                                    float(sp_overlay_point_size.get())
                                    if sp_overlay_point_size is not None
                                    else cfg.get("overlay_point_size", 40)
                                )
                                overlay.set_sizes(np.full((len(pts),), size_val))
                            except Exception:
                                pass
                            canvas.draw_idle()
                        except Exception:
                            pass
                        try:
                            _update_overlay_colors()
                        except Exception:
                            pass
                        try:
                            _update_lengths_and_line()
                        except Exception:
                            pass
                    else:
                        # fallback: draw single point using configured point color and size
                        try:
                            pc = (
                                cmb_point_color.get()
                                if cmb_point_color is not None
                                else "red"
                            )
                            try:
                                size_val = (
                                    float(sp_overlay_point_size.get())
                                    if sp_overlay_point_size is not None
                                    else cfg.get("overlay_point_size", 40)
                                )
                            except Exception:
                                size_val = cfg.get("overlay_point_size", 40)
                            ax.scatter([x], [y], c=pc, s=size_val, zorder=100)
                            canvas.draw_idle()
                        except Exception:
                            pass
                except Exception:
                    pass

            cid = canvas.mpl_connect("button_press_event", _onclick)
            state["mpl_cid"] = cid
        except Exception:
            state["mpl_cid"] = None

    def _rebuild_canvas_with_added_points(canvas_parent, xs2, ys2, zs2):
        # create new figure for underlying data and plot added red points
        fig2 = create_figure(
            xs2,
            ys2,
            zs2,
            title=os.path.basename(state.get("path", "")),
            cmap=cmb_cmap.get(),
            point_size=float(sp_point_size.get()) if sp_point_size.get() else 1.0,
            plot_mode=("hexbin" if var_hex.get() else "scatter"),
            gridsize=int(sp_gridsize.get()) if sp_gridsize.get() else 50,
            downsample=None,
        )
        # destroy previous canvas widget if any
        try:
            old_canvas = state.get("canvas_widget")
            if old_canvas is not None:
                try:
                    # disconnect previous mpl cid
                    cid = state.get("mpl_cid")
                    if cid is not None:
                        old_canvas.mpl_disconnect(cid)
                except Exception:
                    pass
                try:
                    old_canvas.get_tk_widget().destroy()
                except Exception:
                    pass
        except Exception:
            pass
        # create and pack new canvas
        canvas2 = FigureCanvasTkAgg(fig2, master=canvas_parent)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=1)
        state["fig"] = fig2
        state["canvas_widget"] = canvas2
        # create overlay scatter for added points (fast updates)
        try:
            ax2 = fig2.axes[0] if fig2.axes else None
            if ax2 is not None:
                try:
                    size_val = (
                        float(sp_overlay_point_size.get())
                        if sp_overlay_point_size is not None
                        else cfg.get("overlay_point_size", 40)
                    )
                except Exception:
                    size_val = cfg.get("overlay_point_size", 40)
                overlay = ax2.scatter([], [], c="red", s=size_val, zorder=100)
                state["overlay"] = overlay
                # populate initial offsets
                pts = state.get("added_points", [])
                if pts:
                    xs_o = [p["x"] for p in pts]
                    ys_o = [p["y"] for p in pts]
                    try:
                        overlay.set_offsets(np.column_stack((xs_o, ys_o)))
                        try:
                            overlay.set_sizes(np.full((len(pts),), size_val))
                        except Exception:
                            pass
                    except Exception:
                        pass
                    try:
                        _update_overlay_colors()
                    except Exception:
                        pass
                    try:
                        _update_lengths_and_line()
                    except Exception:
                        pass
        except Exception:
            state["overlay"] = None
        # plot existing added points
        try:
            # drawing of overlay already handled; just refresh canvas
            canvas2.draw_idle()
        except Exception:
            pass
        # attach handlers
        _attach_canvas_handlers(canvas2, fig2)

    def _update_overlay_colors():
        """Update overlay facecolors so selected table rows are blue and others red."""
        try:
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
            # compute color arrays from widgets or defaults
            try:
                base_color = (
                    mcolors.to_rgba(cmb_point_color.get())
                    if cmb_point_color is not None
                    else (1.0, 0.0, 0.0, 1.0)
                )
            except Exception:
                base_color = (1.0, 0.0, 0.0, 1.0)
            try:
                hl_color = (
                    mcolors.to_rgba(cmb_highlight_color.get())
                    if cmb_highlight_color is not None
                    else (0.0, 0.0, 1.0, 1.0)
                )
            except Exception:
                hl_color = (0.0, 0.0, 1.0, 1.0)
            cols = np.tile(np.array(base_color), (n, 1))
            sel = (
                set(state.get("points_table").selection())
                if state.get("points_table")
                else set()
            )
            # mark selected as highlight color
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
                cw = state.get("canvas_widget")
                if cw is not None:
                    cw.draw_idle()
            except Exception:
                pass
        except Exception:
            pass

    def _update_lengths_and_line():
        """Compute per-segment lengths, update table values and draw connecting line."""
        try:
            pts = state.get("added_points", [])
            tbl = state.get("points_table")
            if tbl is None:
                return

            n = len(pts)
            if n == 0:
                # clear total label and remove any existing line
                try:
                    lbl = state.get("total_len_label")
                    if lbl is not None:
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

            # compute per-segment lengths (length for index i is distance from i-1 to i)
            lens = [0.0] * n
            total = 0.0
            for i in range(1, n):
                dx = xs[i] - xs[i - 1]
                dy = ys[i] - ys[i - 1]
                d = (dx * dx + dy * dy) ** 0.5
                lens[i] = d
                total += d

            # update table rows
            for i, ap in enumerate(pts):
                try:
                    item = ap.get("item")
                    if item:
                        length_str = f"{lens[i]:.6f}" if i > 0 else ""
                        tbl.item(
                            item,
                            values=(f"{ap['x']:.6f}", f"{ap['y']:.6f}", length_str),
                        )
                except Exception:
                    pass

            # update total label
            try:
                lbl = state.get("total_len_label")
                if lbl is not None:
                    lbl.config(text=f"Horizontal distance: {total:.6f}")
            except Exception:
                pass

            # update or create line artist connecting points
            try:
                fig = state.get("fig")
                ax = fig.axes[0] if fig and fig.axes else None
                if ax is not None:
                    line = state.get("line_artist")
                    if n >= 2:
                        if line is None:
                            try:
                                lc = (
                                    mcolors.to_rgba(cmb_line_color.get())
                                    if cmb_line_color is not None
                                    else "black"
                                )
                            except Exception:
                                lc = "black"
                            try:
                                lw = (
                                    float(sp_line_width.get())
                                    if sp_line_width is not None and sp_line_width.get()
                                    else 1.0
                                )
                            except Exception:
                                lw = 1.0
                            (lineobj,) = ax.plot(
                                xs, ys, color=lc, linewidth=lw, zorder=90
                            )
                            state["line_artist"] = lineobj
                        else:
                            try:
                                line.set_data(xs, ys)
                            except Exception:
                                pass
                            try:
                                if cmb_line_color is not None:
                                    line.set_color(
                                        mcolors.to_rgba(cmb_line_color.get())
                                    )
                            except Exception:
                                pass
                            try:
                                if sp_line_width is not None:
                                    lw = (
                                        float(sp_line_width.get())
                                        if sp_line_width.get()
                                        else 1.0
                                    )
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
                    # redraw
                    try:
                        cw = state.get("canvas_widget")
                        if cw is not None:
                            cw.draw_idle()
                    except Exception:
                        pass
                    try:
                        _update_overlay_colors()
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_table_select(event=None):
        try:
            _update_overlay_colors()
        except Exception:
            pass

    def _on_style_change(event=None):
        # update overlay colors immediately
        try:
            _update_overlay_colors()
        except Exception:
            pass

        # update existing line style
        try:
            line = state.get("line_artist")
            if line is not None:
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
        except Exception:
            pass

        # update overlay sizes
        try:
            overlay = state.get("overlay")
            if overlay is not None and sp_overlay_point_size is not None:
                try:
                    size_val = (
                        float(sp_overlay_point_size.get())
                        if sp_overlay_point_size.get()
                        else cfg.get("overlay_point_size", 40)
                    )
                    n = len(state.get("added_points", []))
                    if n > 0:
                        overlay.set_sizes(np.full((n,), size_val))
                except Exception:
                    pass
        except Exception:
            pass

        # redraw canvas
        try:
            cw = state.get("canvas_widget")
            if cw is not None:
                cw.draw_idle()
        except Exception:
            pass
        # persist style changes to config
        try:
            cfg2 = _load_config()
            try:
                cfg2["line_color"] = (
                    cmb_line_color.get()
                    if cmb_line_color is not None
                    else cfg2.get("line_color", "black")
                )
            except Exception:
                pass
            try:
                cfg2["line_width"] = (
                    float(sp_line_width.get())
                    if sp_line_width is not None and sp_line_width.get()
                    else cfg2.get("line_width", 1.0)
                )
            except Exception:
                pass
            try:
                cfg2["point_color"] = (
                    cmb_point_color.get()
                    if cmb_point_color is not None
                    else cfg2.get("point_color", "red")
                )
            except Exception:
                pass
            try:
                cfg2["highlight_color"] = (
                    cmb_highlight_color.get()
                    if cmb_highlight_color is not None
                    else cfg2.get("highlight_color", "blue")
                )
            except Exception:
                pass
            try:
                cfg2["overlay_point_size"] = (
                    float(sp_overlay_point_size.get())
                    if sp_overlay_point_size is not None and sp_overlay_point_size.get()
                    else cfg2.get("overlay_point_size", 40)
                )
            except Exception:
                pass
            _save_config(cfg2)
        except Exception:
            pass

    def _reorder_state_from_tree():
        """Rebuild state['added_points'] to match the current Treeview row order."""
        try:
            tbl = state.get("points_table")
            if not tbl:
                return
            children = list(tbl.get_children())
            existing = {ap.get("item"): ap for ap in state.get("added_points", [])}
            new_pts = []
            for cid in children:
                ap = existing.get(cid)
                if ap:
                    new_pts.append(ap)
            state["added_points"] = new_pts
        except Exception:
            pass

    def move_selected_up():
        try:
            tbl = state.get("points_table")
            if not tbl:
                return
            children = list(tbl.get_children())
            sel = [c for c in tbl.selection() if c in children]
            if not sel:
                return
            # get indices and sort ascending
            indices = sorted([children.index(s) for s in sel])
            for idx in indices:
                if idx <= 0:
                    continue
                item = children[idx]
                try:
                    tbl.move(item, "", idx - 1)
                except Exception:
                    pass
                # update local children list to reflect move
                children.pop(idx)
                children.insert(idx - 1, item)
            _reorder_state_from_tree()
            # after reordering the internal state, refresh overlay offsets so
            # the scatter points are in the same order as the table, then
            # refresh colors and recompute lengths/line
            try:
                overlay = state.get("overlay")
                pts = state.get("added_points", [])
                if overlay is not None:
                    if pts:
                        xs_o = [p["x"] for p in pts]
                        ys_o = [p["y"] for p in pts]
                        try:
                            overlay.set_offsets(np.column_stack((xs_o, ys_o)))
                        except Exception:
                            pass
                        try:
                            size_val = (
                                float(sp_overlay_point_size.get())
                                if sp_overlay_point_size is not None
                                else cfg.get("overlay_point_size", 40)
                            )
                            overlay.set_sizes(np.full((len(pts),), size_val))
                        except Exception:
                            pass
                    else:
                        try:
                            overlay.set_offsets(np.empty((0, 2)))
                        except Exception:
                            pass
                    try:
                        cw = state.get("canvas_widget")
                        if cw is not None:
                            cw.draw_idle()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                _update_overlay_colors()
            except Exception:
                pass
            try:
                _update_lengths_and_line()
            except Exception:
                pass
        except Exception:
            pass

    def move_selected_down():
        try:
            tbl = state.get("points_table")
            if not tbl:
                return
            children = list(tbl.get_children())
            sel = [c for c in tbl.selection() if c in children]
            if not sel:
                return
            # move in reverse order to avoid index shifting issues
            indices = sorted([children.index(s) for s in sel], reverse=True)
            for idx in indices:
                if idx >= len(children) - 1:
                    continue
                item = children[idx]
                try:
                    tbl.move(item, "", idx + 1)
                except Exception:
                    pass
                children.pop(idx)
                children.insert(idx + 1, item)
            _reorder_state_from_tree()
            # refresh overlay offsets to match new ordering and update visuals
            try:
                overlay = state.get("overlay")
                pts = state.get("added_points", [])
                if overlay is not None:
                    if pts:
                        xs_o = [p["x"] for p in pts]
                        ys_o = [p["y"] for p in pts]
                        try:
                            overlay.set_offsets(np.column_stack((xs_o, ys_o)))
                        except Exception:
                            pass
                        try:
                            size_val = (
                                float(sp_overlay_point_size.get())
                                if sp_overlay_point_size is not None
                                else cfg.get("overlay_point_size", 40)
                            )
                            overlay.set_sizes(np.full((len(pts),), size_val))
                        except Exception:
                            pass
                    else:
                        try:
                            overlay.set_offsets(np.empty((0, 2)))
                        except Exception:
                            pass
                    try:
                        cw = state.get("canvas_widget")
                        if cw is not None:
                            cw.draw_idle()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                _update_overlay_colors()
            except Exception:
                pass
            try:
                _update_lengths_and_line()
            except Exception:
                pass
        except Exception:
            pass

    # bind selection change to handler
    try:
        tree.bind("<<TreeviewSelect>>", _on_table_select)
    except Exception:
        pass

    # Enable drag-and-drop reordering within the Treeview (supports multi-selection)
    try:

        def _on_tree_button_press(event):
            try:
                item = tree.identify_row(event.y)
                if not item:
                    state.pop("dragging", None)
                    return
                sel = list(tree.selection())
                if item in sel and sel:
                    # dragging current selection
                    state["dragging"] = {"items": sel, "last_target": None}
                else:
                    # clicked a non-selected row: select it and drag single
                    try:
                        tree.selection_set(item)
                    except Exception:
                        pass
                    state["dragging"] = {"items": [item], "last_target": None}
            except Exception:
                pass

        def _on_tree_b1_motion(event):
            try:
                drag = state.get("dragging")
                if not drag:
                    return
                target = tree.identify_row(event.y)
                if not target:
                    return
                # avoid redundant work
                if drag.get("last_target") == target:
                    return
                children = list(tree.get_children())
                items = drag.get("items", [])
                # if target is one of the items, ignore
                if target in items:
                    return
                # build new children list by removing dragged items and inserting before target
                new_children = [c for c in children if c not in items]
                try:
                    insert_at = new_children.index(target)
                except ValueError:
                    return
                for i, it in enumerate(items):
                    new_children.insert(insert_at + i, it)
                # apply new order
                for idx, cid in enumerate(new_children):
                    try:
                        tree.move(cid, "", idx)
                    except Exception:
                        pass
                drag["last_target"] = target
                # sync internal state and visuals
                try:
                    _reorder_state_from_tree()
                except Exception:
                    pass
                try:
                    _update_overlay_colors()
                except Exception:
                    pass
                try:
                    _update_lengths_and_line()
                except Exception:
                    pass
            except Exception:
                pass

        def _on_tree_button_release(event):
            try:
                if "dragging" in state:
                    state.pop("dragging", None)
            except Exception:
                pass

        tree.bind("<ButtonPress-1>", _on_tree_button_press)
        tree.bind("<B1-Motion>", _on_tree_b1_motion)
        tree.bind("<ButtonRelease-1>", _on_tree_button_release)
    except Exception:
        pass

    # bind style controls (if present)
    try:
        if cmb_line_color is not None:
            cmb_line_color.bind("<<ComboboxSelected>>", _on_style_change)
        if cmb_point_color is not None:
            cmb_point_color.bind("<<ComboboxSelected>>", _on_style_change)
        if cmb_highlight_color is not None:
            cmb_highlight_color.bind("<<ComboboxSelected>>", _on_style_change)
        if sp_line_width is not None:
            sp_line_width.bind("<FocusOut>", _on_style_change)
            sp_line_width.bind("<Return>", _on_style_change)
    except Exception:
        pass

    def remove_selected_points():
        # remove selected rows from table and corresponding points, then rebuild canvas
        try:
            sel = state["points_table"].selection()
            if not sel:
                return
            # remove from state list
            removed_now = []
            for item in sel:
                try:
                    # find and remove matching entry
                    for i, ap in enumerate(list(state.get("added_points", []))):
                        if ap.get("item") == item:
                            # remove by index
                            removed_now.append(state["added_points"][i])
                            del state["added_points"][i]
                            break
                except Exception:
                    pass
                try:
                    state["points_table"].delete(item)
                except Exception:
                    pass
            # record removal in history for undo
            if removed_now:
                state["remove_history"].append(removed_now)
            # update overlay offsets in-place for performance
            try:
                overlay = state.get("overlay")
                if overlay is not None:
                    pts = state.get("added_points", [])
                    if pts:
                        xs_o = [p["x"] for p in pts]
                        ys_o = [p["y"] for p in pts]
                        try:
                            overlay.set_offsets(np.column_stack((xs_o, ys_o)))
                        except Exception:
                            pass
                    else:
                        try:
                            overlay.set_offsets(np.empty((0, 2)))
                        except Exception:
                            pass
                    try:
                        cw = state.get("canvas_widget")
                        if cw is not None:
                            cw.draw_idle()
                    except Exception:
                        pass
                    try:
                        _update_overlay_colors()
                    except Exception:
                        pass
                    try:
                        _update_lengths_and_line()
                    except Exception:
                        pass
                else:
                    # fallback: rebuild canvas if no overlay
                    xs = state.get("xs", [])
                    ys = state.get("ys", [])
                    zs = state.get("zs")
                    _rebuild_canvas_with_added_points(canvas_frame, xs, ys, zs)
            except Exception:
                pass
        except Exception:
            pass

    def undo_remove():
        try:
            if not state.get("remove_history"):
                return
            last = state["remove_history"].pop()
            # re-insert into state and table
            for ap in last:
                try:
                    item_id = state["points_table"].insert(
                        "", "end", values=(f"{ap['x']:.6f}", f"{ap['y']:.6f}", "")
                    )
                    # update item id in ap to new one and append
                    ap_copy = {"x": ap["x"], "y": ap["y"], "item": item_id}
                    state["added_points"].append(ap_copy)
                except Exception:
                    pass
            # update overlay offsets in-place to show restored points
            try:
                overlay = state.get("overlay")
                if overlay is not None:
                    pts = state.get("added_points", [])
                    if pts:
                        xs_o = [p["x"] for p in pts]
                        ys_o = [p["y"] for p in pts]
                        try:
                            overlay.set_offsets(np.column_stack((xs_o, ys_o)))
                        except Exception:
                            pass
                    else:
                        try:
                            overlay.set_offsets(np.empty((0, 2)))
                        except Exception:
                            pass
                    try:
                        cw = state.get("canvas_widget")
                        if cw is not None:
                            cw.draw_idle()
                    except Exception:
                        pass
                    try:
                        _update_overlay_colors()
                    except Exception:
                        pass
                    try:
                        _update_lengths_and_line()
                    except Exception:
                        pass
                else:
                    xs = state.get("xs", [])
                    ys = state.get("ys", [])
                    zs = state.get("zs")
                    _rebuild_canvas_with_added_points(canvas_frame, xs, ys, zs)
            except Exception:
                pass
        except Exception:
            pass

    def export_table_csv():
        try:
            tbl = state.get("points_table")
            if not tbl:
                return
            children = list(tbl.get_children())
            if not children:
                messagebox.showinfo("情報", "エクスポートする行がありません")
                return
            p = filedialog.asksaveasfilename(
                defaultextension=".csv", filetypes=[("CSV files", "*.csv")]
            )
            if not p:
                return
            # build map of item->point to keep numeric precision and order
            existing = {ap.get("item"): ap for ap in state.get("added_points", [])}
            with open(p, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["x", "y"])  # header
                for cid in children:
                    ap = existing.get(cid)
                    if ap:
                        writer.writerow([f"{ap['x']:.6f}", f"{ap['y']:.6f}"])
            messagebox.showinfo("保存完了", f"CSV を保存しました: {p}")
        except Exception as e:
            try:
                messagebox.showerror(
                    "エラー", f"CSV エクスポート中にエラーが発生しました: {e}"
                )
            except Exception:
                pass

    def import_points_csv():
        try:
            p = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv"), ("All files", "*")]
            )
            if not p:
                return
            # ask user whether to append or replace
            # Yes -> replace (置換), No -> append (追加)
            try:
                do_replace = messagebox.askyesno(
                    "CSV インポート", "既存の点を置換しますか？\nはい=置換、いいえ=追加"
                )
            except Exception:
                do_replace = False

            # read CSV and add rows to table/state
            added = []
            if do_replace:
                # clear existing points and table
                try:
                    for item in list(state.get("points_table").get_children()):
                        try:
                            state["points_table"].delete(item)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    state["added_points"] = []
                except Exception:
                    state["added_points"] = []
            with open(p, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                # skip header if present
                first = True
                for row in reader:
                    if first:
                        first = False
                        # check if header-like
                        if len(row) >= 2 and (
                            row[0].strip().lower() == "x" or not _is_number(row[0])
                        ):
                            continue
                    if not row:
                        continue
                    try:
                        x = float(row[0])
                        y = float(row[1])
                    except Exception:
                        continue
                    item_id = state["points_table"].insert(
                        "", "end", values=(f"{x:.6f}", f"{y:.6f}", "")
                    )
                    ap = {"x": x, "y": y, "item": item_id}
                    state["added_points"].append(ap)
                    added.append(ap)
            if not added:
                messagebox.showinfo("情報", "インポートできる行がありませんでした")
                return
            # update overlay and visuals
            try:
                overlay = state.get("overlay")
                pts = state.get("added_points", [])
                if overlay is not None:
                    if pts:
                        xs_o = [p["x"] for p in pts]
                        ys_o = [p["y"] for p in pts]
                        try:
                            overlay.set_offsets(np.column_stack((xs_o, ys_o)))
                        except Exception:
                            pass
                        try:
                            size_val = (
                                float(sp_overlay_point_size.get())
                                if sp_overlay_point_size is not None
                                else cfg.get("overlay_point_size", 40)
                            )
                            overlay.set_sizes(np.full((len(pts),), size_val))
                        except Exception:
                            pass
                    else:
                        try:
                            overlay.set_offsets(np.empty((0, 2)))
                        except Exception:
                            pass
                    try:
                        cw = state.get("canvas_widget")
                        if cw is not None:
                            cw.draw_idle()
                    except Exception:
                        pass
                else:
                    xs = state.get("xs", [])
                    ys = state.get("ys", [])
                    zs = state.get("zs")
                    _rebuild_canvas_with_added_points(canvas_frame, xs, ys, zs)
            except Exception:
                pass
            try:
                _update_overlay_colors()
            except Exception:
                pass
            try:
                _update_lengths_and_line()
            except Exception:
                pass
        except Exception as e:
            try:
                messagebox.showerror(
                    "エラー", f"CSV インポート中にエラーが発生しました: {e}"
                )
            except Exception:
                pass

    # helper used when detecting header-like CSV first column
    def _is_number(s: str) -> bool:
        try:
            float(s)
            return True
        except Exception:
            return False

    def open_file():
        p = filedialog.askopenfilename(
            initialdir=initial_dir or os.getcwd(),
            filetypes=[("PLY/XYZ files", "*.ply;*.plyz;*.xyz;*.*")],
        )
        if not p:
            return
        state["path"] = p
        lbl_path.config(text=os.path.basename(p))
        try:
            cfg2 = _load_config()
            cfg2["last_dir"] = os.path.dirname(p)
            _save_config(cfg2)
        except Exception:
            pass

        cancel_event = threading.Event()
        state["cancel_event"] = cancel_event

        for w in progress_frame.winfo_children():
            w.destroy()
        prog = ttk.Progressbar(progress_frame, mode="determinate")
        prog.pack(fill=tk.X, expand=1, side=tk.LEFT)
        lbl_prog = ttk.Label(progress_frame, text="0%", width=6)
        lbl_prog.pack(side=tk.LEFT, padx=6)
        btn_cancel = ttk.Button(progress_frame, text="Cancel", command=cancel_event.set)
        btn_cancel.pack(side=tk.LEFT)

        def progress_cb(pct: float):
            def _update():
                try:
                    prog["value"] = pct
                    lbl_prog.config(text=f"{pct:.0f}%")
                except Exception:
                    pass

            root.after(1, _update)

        def cancel_check():
            return cancel_event.is_set()

        def worker():
            try:
                # Use model's parsing wrapper which accepts our progress/cancel
                # callbacks. This keeps parsing logic centralized in the model.
                xs, ys, zs = parse_with_progress(
                    p, progress_cb=progress_cb, cancel_event=cancel_event
                )

                def _done():
                    state["xs"] = xs
                    state["ys"] = ys
                    state["zs"] = zs
                    if cancel_event.is_set():
                        messagebox.showinfo("中断", "読み込みがキャンセルされました")
                    else:
                        lbl_prog.config(text="Done")

                root.after(1, _done)
            except Exception as e:
                # Exception variables are cleared after the except block; bind
                # the exception into a default argument so the scheduled
                # callback can still reference it.
                def _err(exc=e):
                    messagebox.showerror(
                        "エラー", f"読み込み中にエラーが発生しました: {exc}"
                    )

                root.after(1, _err)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def do_preview():
        if not state["path"]:
            messagebox.showinfo("情報", "ファイルを選択してください")
            return
        try:
            ps = float(sp_point_size.get())
        except Exception:
            ps = 5.0
        cmap = cmb_cmap.get()
        try:
            ds = int(sp_downsample.get()) if sp_downsample.get() else None
            if ds is not None and ds <= 0:
                ds = None
        except Exception:
            ds = None
        try:
            gs = int(sp_gridsize.get())
        except Exception:
            gs = 50
        plot_mode = "hexbin" if var_hex.get() else "scatter"

        try:
            cfg3 = _load_config()
            cfg3["point_size"] = ps
            cfg3["downsample"] = ds if ds is not None else 0
            cfg3["cmap"] = cmap
            cfg3["plot_mode"] = plot_mode
            cfg3["gridsize"] = gs
            _save_config(cfg3)
        except Exception:
            pass

        for w in progress_frame.winfo_children():
            w.destroy()
        prog = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        prog.pack(fill=tk.X, expand=1, side=tk.LEFT)
        lbl_prog = ttk.Label(progress_frame, text="0%", width=6)
        lbl_prog.pack(side=tk.LEFT, padx=6)
        btn_cancel_preview = ttk.Button(progress_frame, text="Cancel")
        btn_cancel_preview.pack(side=tk.LEFT)

        cancel_preview = threading.Event()
        btn_cancel_preview.config(command=cancel_preview.set)

        def progress_cb2(pct: float):
            def _update():
                try:
                    prog["value"] = max(0, min(100, pct))
                    lbl_prog.config(text=f"{pct:.0f}%")
                except Exception:
                    pass

            root.after(1, _update)

        def worker_preview():
            progress_cb2(5)
            xs = state.get("xs", [])
            ys = state.get("ys", [])
            zs = state.get("zs")
            if cancel_preview.is_set():
                progress_cb2(0)
                return
            progress_cb2(20)
            if ds and len(xs) > ds:
                try:
                    idxs_list = random.sample(range(len(xs)), ds)
                except Exception:
                    step = max(1, len(xs) // ds)
                    idxs_list = list(range(0, len(xs), step))[:ds]
                idxs_list = sorted(idxs_list)
                xs2 = []
                ys2 = []
                zs2 = [] if zs is not None else None

                chunk_size = max(1000, max(1, len(idxs_list) // 10))
                total = len(idxs_list)
                batches = (total + chunk_size - 1) // chunk_size
                for b in range(batches):
                    if cancel_preview.is_set():
                        progress_cb2(0)
                        return
                    start = b * chunk_size
                    end = min(total, start + chunk_size)
                    for idx in idxs_list[start:end]:
                        xs2.append(xs[idx])
                        ys2.append(ys[idx])
                        if zs is not None:
                            zs2.append(zs[idx])
                    try:
                        pct = 20.0 + ((b + 1) / batches) * 30.0
                        progress_cb2(pct)
                    except Exception:
                        pass
            else:
                xs2, ys2, zs2 = xs, ys, zs
            progress_cb2(50)
            if cancel_preview.is_set():
                progress_cb2(0)
                return
            try:
                fig = create_figure(
                    xs2,
                    ys2,
                    zs2,
                    title=os.path.basename(state.get("path", "")),
                    cmap=cmap,
                    point_size=ps,
                    plot_mode=plot_mode,
                    gridsize=gs,
                    downsample=None,
                )
            except Exception as e:

                # bind exception into callback default arg so it remains available
                def _err(exc=e):
                    messagebox.showerror(
                        "エラー", f"プレビュー作成中にエラーが発生しました: {exc}"
                    )
                    progress_cb2(0)

                root.after(1, _err)
                return
            progress_cb2(80)
            if cancel_preview.is_set():
                progress_cb2(0)
                return

            def _done():
                # clear only canvas area; table_frame is a sibling so unaffected
                for w in canvas_frame.winfo_children():
                    w.destroy()
                canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)

                # reset added points and clear table
                state["added_points"] = []
                try:
                    for item in state["points_table"].get_children():
                        state["points_table"].delete(item)
                except Exception:
                    pass

                state["fig"] = fig
                # create overlay scatter for added points (fast updates)
                try:
                    ax = fig.axes[0] if fig.axes else None
                    if ax is not None:
                        overlay = ax.scatter([], [], c="red", s=40, zorder=100)
                        state["overlay"] = overlay
                        # populate initial offsets if any
                        pts = state.get("added_points", [])
                        if pts:
                            xs_o = [p["x"] for p in pts]
                            ys_o = [p["y"] for p in pts]
                            try:
                                overlay.set_offsets(np.column_stack((xs_o, ys_o)))
                            except Exception:
                                pass
                except Exception:
                    state["overlay"] = None

                # connect mouse click handler to add red points
                try:
                    # attach standardized handlers which also keep mapping of tree-item ids
                    state["canvas_widget"] = canvas
                    _attach_canvas_handlers(canvas, fig)
                except Exception:
                    pass

                progress_cb2(100)

            root.after(1, _done)

        t = threading.Thread(target=worker_preview, daemon=True)
        t.start()

    def do_save():
        if not state.get("fig"):
            messagebox.showinfo("情報", "まずプレビューを表示してください")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg;*.jpeg")],
        )
        if not p:
            return

        try:
            ps = float(sp_point_size.get())
            ds = int(sp_downsample.get()) if sp_downsample.get() else 0
            cfg4 = _load_config()
            cfg4["point_size"] = ps
            cfg4["downsample"] = ds
            cfg4["cmap"] = cmb_cmap.get()
            cfg4["plot_mode"] = "hexbin" if var_hex.get() else "scatter"
            cfg4["gridsize"] = (
                int(sp_gridsize.get())
                if sp_gridsize.get()
                else cfg4.get("gridsize", 50)
            )
            _save_config(cfg4)
        except Exception:
            pass

        for w in progress_frame.winfo_children():
            w.destroy()
        prog = ttk.Progressbar(progress_frame, mode="indeterminate")
        prog.pack(fill=tk.X, expand=1, side=tk.LEFT)
        lbl_prog = ttk.Label(progress_frame, text="Saving...", width=12)
        lbl_prog.pack(side=tk.LEFT, padx=6)
        btn_preview.config(state=tk.DISABLED)
        btn_save.config(state=tk.DISABLED)

        def worker_save():
            try:
                prog.start(20)
                state.get("fig").savefig(p, dpi=200)
                prog.stop()

                def _ok():
                    btn_preview.config(state=tk.NORMAL)
                    btn_save.config(state=tk.NORMAL)
                    messagebox.showinfo("保存完了", f"保存しました: {p}")
                    for w in progress_frame.winfo_children():
                        w.destroy()

                root.update_idletasks()
                root.after(1, _ok)
            except Exception as e:
                prog.stop()

                # bind exception into callback default arg so scheduled callback
                # can access it after this except block exits
                def _err(exc=e):
                    btn_preview.config(state=tk.NORMAL)
                    btn_save.config(state=tk.NORMAL)
                    messagebox.showerror("エラー", f"保存中にエラーが発生しました: {exc}")

                for w in progress_frame.winfo_children():
                    w.destroy()
                root.after(1, _err)

        t = threading.Thread(target=worker_save, daemon=True)
        t.start()

    # place Open File controls into left-side frame next to the graph
    btn_open = ttk.Button(left_ctrl_frame, text="Open File", command=open_file)
    btn_open.grid(row=0, column=0, sticky=tk.W)
    lbl_path = ttk.Label(left_ctrl_frame, text="(no file)")
    lbl_path.grid(row=0, column=1, sticky=tk.W, padx=8)

    ttk.Label(left_ctrl_frame, text="Point size:").grid(
        row=1, column=0, sticky=tk.W, pady=(6, 0)
    )
    sp_point_size = ttk.Entry(left_ctrl_frame, width=8)
    sp_point_size.insert(0, "1.0")
    sp_point_size.grid(row=1, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(left_ctrl_frame, text="Colormap:").grid(
        row=2, column=0, sticky=tk.W, pady=(6, 0)
    )
    cmaps = sorted(plt.colormaps())
    cmb_cmap = ttk.Combobox(left_ctrl_frame, values=cmaps, width=20)
    cmb_cmap.set("jet")
    cmb_cmap.grid(row=2, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(left_ctrl_frame, text="Downsample (max points):").grid(
        row=4, column=0, sticky=tk.W, pady=(6, 0)
    )
    sp_downsample = ttk.Entry(left_ctrl_frame, width=10)
    sp_downsample.insert(0, "50000")
    sp_downsample.grid(row=4, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(left_ctrl_frame, text="Hexbin (density):").grid(
        row=5, column=0, sticky=tk.W, pady=(6, 0)
    )
    var_hex = tk.BooleanVar(value=False)
    chk_hex = ttk.Checkbutton(left_ctrl_frame, variable=var_hex, text="Use hexbin")
    chk_hex.grid(row=5, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(left_ctrl_frame, text="Hexbin gridsize:").grid(
        row=6, column=0, sticky=tk.W, pady=(6, 0)
    )
    sp_gridsize = ttk.Entry(left_ctrl_frame, width=10)
    sp_gridsize.insert(0, "50")
    sp_gridsize.grid(row=6, column=1, sticky=tk.W, pady=(6, 0))

    try:
        sp_point_size.delete(0, tk.END)
        sp_point_size.insert(0, str(cfg.get("point_size", 1.0)))
        cmb_cmap.set(cfg.get("cmap", "jet"))
        sp_downsample.delete(0, tk.END)
        sp_downsample.insert(0, str(cfg.get("downsample", 50000)))
        sp_gridsize.delete(0, tk.END)
        sp_gridsize.insert(0, str(cfg.get("gridsize", 50)))
        if cfg.get("plot_mode", "scatter") == "hexbin":
            var_hex.set(True)
        else:
            var_hex.set(False)
        try:
            # overlay point size
            sp_overlay_point_size.delete(0, tk.END)
            sp_overlay_point_size.insert(0, str(cfg.get("overlay_point_size", 40)))
        except Exception:
            pass
    except Exception:
        pass

    btn_preview = ttk.Button(left_ctrl_frame, text="Preview", command=do_preview)
    btn_preview.grid(row=3, column=0, pady=8)
    btn_save = ttk.Button(left_ctrl_frame, text="Save PNG", command=do_save)
    btn_save.grid(row=3, column=1, pady=8, sticky=tk.W)

    # Now that remove_selected_points and undo_remove are defined, create their buttons
    try:
        # place Move Up / Move Down above Remove/Undo for intuitive ordering
        btn_move_up = ttk.Button(table_frame, text="Move Up", command=move_selected_up)
        btn_move_up.grid(
            row=2, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0), padx=(0, 4)
        )
        btn_move_down = ttk.Button(
            table_frame, text="Move Down", command=move_selected_down
        )
        btn_move_down.grid(
            row=3, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0), padx=(0, 4)
        )

        btn_remove = ttk.Button(
            table_frame, text="Remove Selected", command=remove_selected_points
        )
        btn_remove.grid(
            row=4, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0), padx=(0, 4)
        )
        # place Undo under Remove (same column)
        btn_undo = ttk.Button(table_frame, text="Undo Remove", command=undo_remove)
        btn_undo.grid(
            row=5, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0), padx=(0, 4)
        )
    except Exception:
        pass

    try:
        lbl_total = ttk.Label(table_frame, text="Horizontal distance: 0.000000")
        lbl_total.grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))
        state["total_len_label"] = lbl_total
    except Exception:
        state["total_len_label"] = None

    # Styling controls: line color/width, point color, highlight color
    try:
        common_colors = [
            "black",
            "red",
            "green",
            "blue",
            "yellow",
            "magenta",
            "cyan",
            "orange",
            "purple",
            "brown",
            "gray",
        ]
        ttk.Label(table_frame, text="Line color:").grid(
            row=9, column=0, sticky=tk.W, pady=(6, 0)
        )
        cmb_line_color = ttk.Combobox(table_frame, values=common_colors, width=12)
        cmb_line_color.set(cfg.get("line_color", "black"))
        cmb_line_color.grid(row=9, column=1, sticky=tk.W, pady=(6, 0))

        ttk.Label(table_frame, text="Line width:").grid(
            row=10, column=0, sticky=tk.W, pady=(4, 0)
        )
        sp_line_width = ttk.Entry(table_frame, width=10)
        sp_line_width.insert(0, str(cfg.get("line_width", 1.0)))
        sp_line_width.grid(row=10, column=1, sticky=tk.W, pady=(4, 0))

        ttk.Label(table_frame, text="Point color:").grid(
            row=11, column=0, sticky=tk.W, pady=(4, 0)
        )
        cmb_point_color = ttk.Combobox(table_frame, values=common_colors, width=12)
        cmb_point_color.set(cfg.get("point_color", "red"))
        cmb_point_color.grid(row=11, column=1, sticky=tk.W, pady=(4, 0))

        ttk.Label(table_frame, text="Highlight color:").grid(
            row=12, column=0, sticky=tk.W, pady=(4, 0)
        )
        cmb_highlight_color = ttk.Combobox(table_frame, values=common_colors, width=12)
        cmb_highlight_color.set(cfg.get("highlight_color", "blue"))
        cmb_highlight_color.grid(row=12, column=1, sticky=tk.W, pady=(4, 0))
        # overlay (red point) size
        ttk.Label(table_frame, text="Point size:").grid(
            row=13, column=0, sticky=tk.W, pady=(4, 0)
        )
        sp_overlay_point_size = ttk.Entry(table_frame, width=10)
        sp_overlay_point_size.insert(0, str(cfg.get("overlay_point_size", 40)))
        sp_overlay_point_size.grid(row=13, column=1, sticky=tk.W, pady=(4, 0))
    except Exception:
        cmb_line_color = None
        sp_line_width = None
        cmb_point_color = None
        cmb_highlight_color = None

    # CSV import/export buttons (placed under Undo Remove)
    try:
        btn_import_csv = ttk.Button(
            table_frame, text="Import CSV", command=import_points_csv
        )
        btn_import_csv.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))
        btn_export_csv = ttk.Button(
            table_frame, text="Export CSV", command=export_table_csv
        )
        # place Export under Import and span both columns
        btn_export_csv.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))
    except Exception:
        pass

    # bind style control events to handler so changes are saved/applied
    try:
        if cmb_line_color is not None:
            cmb_line_color.bind("<<ComboboxSelected>>", _on_style_change)
        if cmb_point_color is not None:
            cmb_point_color.bind("<<ComboboxSelected>>", _on_style_change)
        if cmb_highlight_color is not None:
            cmb_highlight_color.bind("<<ComboboxSelected>>", _on_style_change)
        if sp_line_width is not None:
            sp_line_width.bind("<FocusOut>", _on_style_change)
            sp_line_width.bind("<Return>", _on_style_change)
        if sp_overlay_point_size is not None:
            sp_overlay_point_size.bind("<FocusOut>", _on_style_change)
            sp_overlay_point_size.bind("<Return>", _on_style_change)
    except Exception:
        pass

    btn_quit = ttk.Button(left_ctrl_frame, text="Quit", command=root.destroy)
    btn_quit.grid(row=8, column=0, columnspan=2, pady=8)

    root.geometry("800x600")
    root.mainloop()
