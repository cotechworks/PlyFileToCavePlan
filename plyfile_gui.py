"""GUI module for PlyFileToCavePlan.

Contains `launch_gui(initial_dir=None)` which starts the Tkinter GUI.
This module imports tkinter and matplotlib's TkAgg backend only when needed.
"""
from __future__ import annotations

import os
import sys
import json
import threading
import random
from typing import Optional

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

try:
    import tkinter as tk
    from tkinter import filedialog, ttk, messagebox
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

from plyfile_utils import parse_file, create_figure


def launch_gui(initial_dir: Optional[str] = None) -> None:
    """Start the Tkinter GUI for PlyFileToCavePlan.

    If tkinter is not available, print a message and return.
    """
    if not TK_AVAILABLE:
        print("tkinter が利用できません。GUI を開始できません。")
        return

    def _get_config_path() -> str:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "plyfiletocaveplan_config.json")

    def _load_config() -> dict:
        path = _get_config_path()
        defaults = {
            "point_size": 1.0,
            "downsample": 50000,
            "cmap": "jet",
            "plot_mode": "scatter",
            "gridsize": 50,
            "last_dir": None,
        }
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in defaults.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return defaults

    def _save_config(cfg: dict) -> None:
        path = _get_config_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

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

    # progress and canvas frames are created later
    progress_frame = ttk.Frame(frm)
    progress_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

    canvas_frame = ttk.Frame(root)
    canvas_frame.grid(row=1, column=0, sticky=tk.NSEW)
    root.rowconfigure(1, weight=1)
    root.columnconfigure(0, weight=1)

    def open_file():
        p = filedialog.askopenfilename(initialdir=initial_dir or os.getcwd(),
                                       filetypes=[("PLY/XYZ files", "*.ply;*.plyz;*.xyz;*.*")])
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
                xs, ys, zs = parse_file(p, progress_callback=progress_cb, cancel_check=cancel_check)
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
                def _err():
                    messagebox.showerror("エラー", f"読み込み中にエラーが発生しました: {e}")
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
                fig = create_figure(xs2, ys2, zs2, title=os.path.basename(state.get("path", "")),
                                    cmap=cmap, point_size=ps, plot_mode=plot_mode, gridsize=gs, downsample=None)
            except Exception as e:
                def _err():
                    messagebox.showerror("エラー", f"プレビュー作成中にエラーが発生しました: {e}")
                    progress_cb2(0)
                root.after(1, _err)
                return
            progress_cb2(80)
            if cancel_preview.is_set():
                progress_cb2(0)
                return

            def _done():
                for w in canvas_frame.winfo_children():
                    w.destroy()
                canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
                state["fig"] = fig
                progress_cb2(100)
            root.after(1, _done)

        t = threading.Thread(target=worker_preview, daemon=True)
        t.start()

    def do_save():
        if not state.get("fig"):
            messagebox.showinfo("情報", "まずプレビューを表示してください")
            return
        p = filedialog.asksaveasfilename(defaultextension=".png",
                                         filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg;*.jpeg")])
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
            cfg4["gridsize"] = int(sp_gridsize.get()) if sp_gridsize.get() else cfg4.get("gridsize", 50)
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
                def _err():
                    btn_preview.config(state=tk.NORMAL)
                    btn_save.config(state=tk.NORMAL)
                    messagebox.showerror("エラー", f"保存中にエラーが発生しました: {e}")
                for w in progress_frame.winfo_children():
                    w.destroy()
                root.after(1, _err)

        t = threading.Thread(target=worker_save, daemon=True)
        t.start()

    btn_open = ttk.Button(frm, text="Open File", command=open_file)
    btn_open.grid(row=0, column=0, sticky=tk.W)
    lbl_path = ttk.Label(frm, text="(no file)")
    lbl_path.grid(row=0, column=1, sticky=tk.W, padx=8)

    ttk.Label(frm, text="Point size:").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
    sp_point_size = ttk.Entry(frm, width=8)
    sp_point_size.insert(0, "1.0")
    sp_point_size.grid(row=1, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(frm, text="Colormap:").grid(row=2, column=0, sticky=tk.W, pady=(6, 0))
    cmaps = sorted(plt.colormaps())
    cmb_cmap = ttk.Combobox(frm, values=cmaps, width=20)
    cmb_cmap.set("jet")
    cmb_cmap.grid(row=2, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(frm, text="Downsample (max points):").grid(row=4, column=0, sticky=tk.W, pady=(6, 0))
    sp_downsample = ttk.Entry(frm, width=10)
    sp_downsample.insert(0, "50000")
    sp_downsample.grid(row=4, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(frm, text="Hexbin (density):").grid(row=5, column=0, sticky=tk.W, pady=(6, 0))
    var_hex = tk.BooleanVar(value=False)
    chk_hex = ttk.Checkbutton(frm, variable=var_hex, text="Use hexbin")
    chk_hex.grid(row=5, column=1, sticky=tk.W, pady=(6, 0))

    ttk.Label(frm, text="Hexbin gridsize:").grid(row=6, column=0, sticky=tk.W, pady=(6, 0))
    sp_gridsize = ttk.Entry(frm, width=10)
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
    except Exception:
        pass

    btn_preview = ttk.Button(frm, text="Preview", command=do_preview)
    btn_preview.grid(row=3, column=0, pady=8)
    btn_save = ttk.Button(frm, text="Save PNG", command=do_save)
    btn_save.grid(row=3, column=1, pady=8, sticky=tk.W)

    btn_quit = ttk.Button(frm, text="Quit", command=root.destroy)
    btn_quit.grid(row=8, column=0, pady=8)

    root.geometry("800x600")
    root.mainloop()
