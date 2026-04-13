#!/usr/bin/env python3
"""
PlyFileToCavePlan.py

PLY/XYZファイルを読み込み、XY座標を2Dでプロットします。

使い方 (例):
	python PlyFileToCavePlan.py sample.ply --output sample_plot.png

対応:
- 行は空白区切りかカンマ区切りを想定 (x y [z])  # XYZ のテキスト行フォーマットに対応
- コメント行 (先頭が #) や非数値行は無視
"""
from __future__ import annotations

import argparse
import os
import re
from typing import List, Tuple, Optional
import sys
import json

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import random
import threading
import time

# tkinter を使った簡易 GUI を追加
try:
	import tkinter as tk
	from tkinter import filedialog, ttk, messagebox
	from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
	TK_AVAILABLE = True
except Exception:
	TK_AVAILABLE = False


FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_xyz(filepath: str,
			  progress_callback: Optional[callable] = None,
			  cancel_check: Optional[callable] = None) -> Tuple[List[float], List[float], Optional[List[float]]]:
	"""XYZファイルを読み、x,y,(z)のリストを返す。

	progress_callback(percent: float) を呼び出して進捗を通知できます。
	cancel_check() が True を返すと処理を中断して途中までのデータを返します。

	進捗はファイルサイズを元にバイト位置で計算します（おおよその割合）。
	"""
	xs: List[float] = []
	ys: List[float] = []
	zs: List[float] = []
	has_z = False

	try:
		total_size = os.path.getsize(filepath)
	except Exception:
		total_size = None

	last_report = 0.0
	report_interval_lines = 1000
	lines = 0

	with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
		for raw in f:
			if cancel_check and cancel_check():
				# キャンセル要求があれば中断
				break
			line = raw.strip()
			lines += 1
			if not line:
				continue
			if line.lstrip().startswith("#"):
				continue
			nums = FLOAT_RE.findall(line)
			if len(nums) < 2:
				continue
			try:
				x = float(nums[0])
				y = float(nums[1])
			except ValueError:
				continue
			xs.append(x)
			ys.append(y)
			if len(nums) >= 3:
				try:
					z = float(nums[2])
					zs.append(z)
					has_z = True
				except ValueError:
					zs.append(0.0)

			# 進捗通知
			if progress_callback and (lines % report_interval_lines == 0):
				if total_size:
					try:
						pct = (f.tell() / total_size) * 100.0
					except Exception:
						pct = min(100.0, (lines / (lines + 1)) * 100.0)
				else:
					pct = float(lines % 100)  # not meaningful but triggers updates
				# レポート間隔を抑える
				if pct - last_report >= 0.5 or pct == 100.0:
					last_report = pct
					try:
						progress_callback(pct)
					except Exception:
						pass

	# 最終報告
	if progress_callback:
		try:
			progress_callback(100.0)
		except Exception:
			pass

	return xs, ys, (zs if has_z else None)


def parse_ply(filepath: str,
			  progress_callback: Optional[callable] = None,
			  cancel_check: Optional[callable] = None) -> Tuple[List[float], List[float], Optional[List[float]]]:
	"""Simple PLY (ASCII) parser: 頂点要素から x,y,(z) を抽出する。

	バイナリ PLY はサポートしていません（エラーを投げます）。進捗とキャンセルは parse_file と同じインタフェースです。
	"""

	xs: List[float] = []
	ys: List[float] = []
	zs: List[float] = []
	has_z = False

	# まずヘッダを読み込む
	header_lines = []
	format_ascii = False
	vertex_count = None
	property_names: List[str] = []

	with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
		# read header
		while True:
			line = f.readline()
			if not line:
				raise ValueError("PLY header が見つかりませんでした")
			header_lines.append(line.rstrip('\n'))
			l = line.strip()
			if l.startswith("format"):
				if "ascii" in l.lower():
					format_ascii = True
				else:
					raise ValueError("バイナリ PLY はサポートされていません (ascii のみ)" )
			if l.startswith("element"):
				parts = l.split()
				if len(parts) >= 3 and parts[1] == "vertex":
					try:
						vertex_count = int(parts[2])
					except Exception:
						vertex_count = None
			if l.startswith("property") and vertex_count is not None:
				parts = l.split()
				# property 型 名 の形式
				if len(parts) >= 3:
					property_names.append(parts[-1])
			if l == "end_header":
				break

		if not format_ascii:
			raise ValueError("ASCII PLY のみサポートされています")

		# property_names に x,y,z が含まれていることを想定。インデックスを決める
		try:
			ix = property_names.index("x")
			iy = property_names.index("y")
			iz = property_names.index("z") if "z" in property_names else None
		except ValueError:
			raise ValueError("PLY のプロパティに x,y が見つかりません")

		# 以降は頂点データを読み取る
		# 進捗用の情報
		try:
			total_size = os.path.getsize(filepath)
		except Exception:
			total_size = None
		last_report = 0.0
		lines = 0

		# f は既にヘッダの直後に位置している
		if vertex_count is not None:
			# ヘッダで指定された頂点数だけ読み込む
			for _ in range(vertex_count):
				if cancel_check and cancel_check():
					break
				line = f.readline()
				if not line:
					break
				s = line.strip()
				if not s:
					continue
				parts = s.split()
				# if the line doesn't have enough parts, skip
				if len(parts) <= max(ix, iy, iz or 0):
					continue
				try:
					x = float(parts[ix])
					y = float(parts[iy])
				except Exception:
					continue
				xs.append(x)
				ys.append(y)
				if iz is not None and len(parts) > iz:
					try:
						z = float(parts[iz])
						zs.append(z)
						has_z = True
					except Exception:
						zs.append(0.0)

				lines += 1
				if progress_callback and (lines % 1000 == 0):
					if total_size:
						try:
							pct = (f.tell() / total_size) * 100.0
						except Exception:
							pct = min(100.0, (lines / (vertex_count or (lines+1))) * 100.0)
					else:
						pct = min(100.0, (lines / (vertex_count or (lines+1))) * 100.0)
					if pct - last_report >= 0.5 or pct == 100.0:
						last_report = pct
						try:
							progress_callback(pct)
						except Exception:
							pass
		else:
			for line in f:
				if cancel_check and cancel_check():
					break
				s = line.strip()
				if not s:
					continue
				parts = s.split()
				# if the line doesn't have enough parts, skip
				if len(parts) <= max(ix, iy, iz or 0):
					continue
				try:
					x = float(parts[ix])
					y = float(parts[iy])
				except Exception:
					continue
				xs.append(x)
				ys.append(y)
				if iz is not None and len(parts) > iz:
					try:
						z = float(parts[iz])
						zs.append(z)
						has_z = True
					except Exception:
						zs.append(0.0)

				lines += 1
				if progress_callback and (lines % 1000 == 0):
					if total_size:
						try:
							pct = (f.tell() / total_size) * 100.0
						except Exception:
							pct = min(100.0, (lines / (lines+1)) * 100.0)
					else:
						pct = float(lines % 100)
					if pct - last_report >= 0.5 or pct == 100.0:
						last_report = pct
						try:
							progress_callback(pct)
						except Exception:
							pass

	if progress_callback:
		try:
			progress_callback(100.0)
		except Exception:
			pass

	return xs, ys, (zs if has_z else None)


def parse_file(filepath: str,
			   progress_callback: Optional[callable] = None,
			   cancel_check: Optional[callable] = None) -> Tuple[List[float], List[float], Optional[List[float]]]:
	"""拡張子に応じて適切なパーサに委譲する (ply または xyz)。"""
	ext = os.path.splitext(filepath)[1].lower()
	if ext == ".ply":
		return parse_ply(filepath, progress_callback=progress_callback, cancel_check=cancel_check)
	else:
		# デフォルトは従来の xyz パーサ
		return parse_xyz(filepath, progress_callback=progress_callback, cancel_check=cancel_check)


def plot_xy(xs: List[float], ys: List[float], zs: Optional[List[float]] = None, *,
			title: Optional[str] = None, outpath: Optional[str] = None,
			cmap: str = "jet", point_size: float = 1.0,
			plot_mode: str = "scatter", gridsize: int = 50, downsample: Optional[int] = None) -> None:
	"""XYを2Dで散布図プロットする。zがある場合は色付けする。
	outpathを指定すると画像を保存し、指定しない場合はウィンドウを表示する。
	"""
	fig, ax = plt.subplots(figsize=(8, 6))
	if zs is not None:
		# draw lower z first so that larger z (higher value) appears on top
		try:
			# sort by z ascending (small first, large last)
			pairs = sorted(zip(xs, ys, zs), key=lambda t: t[2])
			xs_s, ys_s, zs_s = zip(*pairs) if pairs else ([], [], [])
		except Exception:
			xs_s, ys_s, zs_s = xs, ys, zs
		sc = ax.scatter(xs_s, ys_s, c=zs_s, cmap=cmap, s=point_size)
		cbar = fig.colorbar(sc, ax=ax)
		cbar.set_label("z")
	else:
		ax.scatter(xs, ys, color="black", s=point_size)

	ax.set_xlabel("X")
	ax.set_ylabel("Y")
	if title:
		ax.set_title(title)
	ax.grid(True)
	ax.set_aspect("equal", adjustable="datalim")

	# downsample if requested
	if downsample and downsample > 0 and len(xs) > downsample:
		idxs = set(random.sample(range(len(xs)), downsample))
		xs = [v for i, v in enumerate(xs) if i in idxs]
		ys = [v for i, v in enumerate(ys) if i in idxs]
		if zs is not None:
			zs = [v for i, v in enumerate(zs) if i in idxs]

	if plot_mode == "hexbin":
		if zs is not None:
			hb = ax.hexbin(xs, ys, C=zs, gridsize=gridsize, cmap=cmap)
			fig.colorbar(hb, ax=ax).set_label("value")
		else:
			hb = ax.hexbin(xs, ys, gridsize=gridsize, cmap=cmap)
			fig.colorbar(hb, ax=ax).set_label("count")

	if outpath:
		fig.tight_layout()
		plt.savefig(outpath, dpi=200)
		print(f"Saved plot to: {outpath}")
		plt.close(fig)
	else:
		plt.show()


def create_figure(xs: List[float], ys: List[float], zs: Optional[List[float]] = None,
				  title: Optional[str] = None, cmap: str = "jet", point_size: float = 1.0,
				  plot_mode: str = "scatter", gridsize: int = 50, downsample: Optional[int] = None) -> Figure:
	"""matplotlib Figure を返す（GUI で埋め込みや保存に使う）。"""
	fig = Figure(figsize=(6, 4))
	ax = fig.subplots()
	# downsample
	if downsample and downsample > 0 and len(xs) > downsample:
		idxs = set(random.sample(range(len(xs)), downsample))
		xs = [v for i, v in enumerate(xs) if i in idxs]
		ys = [v for i, v in enumerate(ys) if i in idxs]
		if zs is not None:
			zs = [v for i, v in enumerate(zs) if i in idxs]

	if plot_mode == "hexbin":
		if zs is not None:
			hb = ax.hexbin(xs, ys, C=zs, gridsize=gridsize, cmap=cmap)
			fig.colorbar(hb, ax=ax).set_label("value")
		else:
			hb = ax.hexbin(xs, ys, gridsize=gridsize, cmap=cmap)
			fig.colorbar(hb, ax=ax).set_label("count")
	else:
		if zs is not None:
			# ensure drawing order: plot points sorted by z so larger z are on top
			try:
				pairs = sorted(zip(xs, ys, zs), key=lambda t: t[2])
				xs, ys, zs = zip(*pairs) if pairs else ([], [], [])
			except Exception:
				pass
			sc = ax.scatter(xs, ys, c=zs, cmap=cmap, s=point_size)
			fig.colorbar(sc, ax=ax)
		else:
			ax.scatter(xs, ys, color="black", s=point_size)
	ax.set_xlabel("X")
	ax.set_ylabel("Y")
	if title:
		ax.set_title(title)
	ax.grid(True)
	ax.set_aspect("equal", adjustable="datalim")
	return fig


def launch_gui(initial_dir: Optional[str] = None) -> None:
	if not TK_AVAILABLE:
		print("tkinter が利用できません。GUI を開始できません。")
		return

	def _get_config_path() -> str:
		# store config next to executable when frozen, otherwise next to script
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
				# merge defaults
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
			# fail silently; do not prevent UI
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

	# load config and possibly override initial directory
	cfg = _load_config()
	if not initial_dir and cfg.get("last_dir"):
		initial_dir = cfg.get("last_dir")

	def open_file():
		p = filedialog.askopenfilename(initialdir=initial_dir or os.getcwd(),
				       filetypes=[("PLY/XYZ files", "*.ply;*.plyz;*.xyz;*.*")])
		if not p:
			return
		state["path"] = p
		lbl_path.config(text=os.path.basename(p))
		# remember last dir in config
		try:
			cfg = _load_config()
			cfg["last_dir"] = os.path.dirname(p)
			_save_config(cfg)
		except Exception:
			pass

		# 読み込みはバックグラウンドで実施し、進捗バーとキャンセルを提供する
		cancel_event = threading.Event()
		state["cancel_event"] = cancel_event

		# 進捗UI を作る/初期化
		for w in progress_frame.winfo_children():
			w.destroy()
		prog = ttk.Progressbar(progress_frame, mode="determinate")
		prog.pack(fill=tk.X, expand=1, side=tk.LEFT)
		lbl_prog = ttk.Label(progress_frame, text="0%", width=6)
		lbl_prog.pack(side=tk.LEFT, padx=6)
		btn_cancel = ttk.Button(progress_frame, text="Cancel", command=cancel_event.set)
		btn_cancel.pack(side=tk.LEFT)

		def progress_cb(pct: float):
			# メインスレッドで UI 更新する
			def _update():
				try:
					prog['value'] = pct
					lbl_prog.config(text=f"{pct:.0f}%")
				except Exception:
					pass
			root.after(1, _update)

		def cancel_check():
			return cancel_event.is_set()

		def worker():
			try:
				xs, ys, zs = parse_file(p, progress_callback=progress_cb, cancel_check=cancel_check)
				# メインスレッドで結果を反映
				def _done():
					state["xs"] = xs
					state["ys"] = ys
					state["zs"] = zs
					# 最終表示
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
		# オプション: downsample, hexbin, gridsize
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

		# save UI parameters to config
		try:
			cfg = _load_config()
			cfg["point_size"] = ps
			cfg["downsample"] = ds if ds is not None else 0
			cfg["cmap"] = cmap
			cfg["plot_mode"] = plot_mode
			cfg["gridsize"] = gs
			_save_config(cfg)
		except Exception:
			pass

		# プレビューは時間がかかる可能性があるためバックグラウンドで実行し、進捗を表示する
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

		def progress_cb(pct: float):
			def _update():
				try:
					prog['value'] = max(0, min(100, pct))
					lbl_prog.config(text=f"{pct:.0f}%")
				except Exception:
					pass
			root.after(1, _update)

		def worker_preview():
			# Phase 1: preparation
			progress_cb(5)
			xs = state.get("xs", [])
			ys = state.get("ys", [])
			zs = state.get("zs")
			# Phase 2: downsample (if requested)
			if cancel_preview.is_set():
				progress_cb(0)
				return
			progress_cb(20)
			if ds and len(xs) > ds:
				# チャンク化したダウンサンプリング: 大きなデータでも段階的に進捗を更新する
				try:
					idxs_list = random.sample(range(len(xs)), ds)
				except Exception:
					# random.sample が失敗した場合は間隔を取る簡易サンプリング
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
						progress_cb(0)
						return
					start = b * chunk_size
					end = min(total, start + chunk_size)
					for idx in idxs_list[start:end]:
						xs2.append(xs[idx])
						ys2.append(ys[idx])
						if zs is not None:
							zs2.append(zs[idx])
					# 進捗を 20% -> 50% の範囲で更新
					try:
						pct = 20.0 + ((b + 1) / batches) * 30.0
						progress_cb(pct)
					except Exception:
						pass
			else:
				xs2, ys2, zs2 = xs, ys, zs
			progress_cb(50)
			if cancel_preview.is_set():
				progress_cb(0)
				return
			# Phase 3: create figure (plotting)
			try:
				fig = create_figure(xs2, ys2, zs2, title=os.path.basename(state.get("path", "")),
						cmap=cmap, point_size=ps, plot_mode=plot_mode, gridsize=gs, downsample=None)
			except Exception as e:
				# report error on main thread
				def _err():
					messagebox.showerror("エラー", f"プレビュー作成中にエラーが発生しました: {e}")
					progress_cb(0)
				root.after(1, _err)
				return
			progress_cb(80)
			if cancel_preview.is_set():
				progress_cb(0)
				return
			# Phase 4: draw on canvas (must run on main thread)
			def _done():
				for w in canvas_frame.winfo_children():
					w.destroy()
				canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
				canvas.draw()
				canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
				state["fig"] = fig
				progress_cb(100)
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

		# save current UI parameters to config
		try:
			ps = float(sp_point_size.get())
			ds = int(sp_downsample.get()) if sp_downsample.get() else 0
			cfg = _load_config()
			cfg["point_size"] = ps
			cfg["downsample"] = ds
			cfg["cmap"] = cmb_cmap.get()
			cfg["plot_mode"] = "hexbin" if var_hex.get() else "scatter"
			cfg["gridsize"] = int(sp_gridsize.get()) if sp_gridsize.get() else cfg.get("gridsize", 50)
			_save_config(cfg)
		except Exception:
			pass

		# 保存はブロッキングなのでバックグラウンドで実行し、インジケータを表示する
		for w in progress_frame.winfo_children():
			w.destroy()
		prog = ttk.Progressbar(progress_frame, mode="indeterminate")
		prog.pack(fill=tk.X, expand=1, side=tk.LEFT)
		lbl_prog = ttk.Label(progress_frame, text="Saving...", width=12)
		lbl_prog.pack(side=tk.LEFT, padx=6)
		# disable buttons to avoid re-entrancy
		btn_preview.config(state=tk.DISABLED)
		btn_save.config(state=tk.DISABLED)

		def worker_save():
			try:
				prog.start(20)
				state.get("fig").savefig(p, dpi=200)
				prog.stop()
				def _ok():
					# re-enable
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

	# ダウンサンプリングと hexbin オプション
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

	# apply config values to widgets
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

	# 進捗表示フレーム（バックグラウンド読み込み中に使用）
	progress_frame = ttk.Frame(frm)
	progress_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

	canvas_frame = ttk.Frame(root)
	canvas_frame.grid(row=1, column=0, sticky=tk.NSEW)
	root.rowconfigure(1, weight=1)
	root.columnconfigure(0, weight=1)

	btn_quit = ttk.Button(frm, text="Quit", command=root.destroy)
	btn_quit.grid(row=8, column=0, pady=8)

	root.geometry("800x600")
	root.mainloop()


def build_arg_parser() -> argparse.ArgumentParser:
	p = argparse.ArgumentParser(description="Read PLY/XYZ file and plot XY coordinates.")
	# input は GUI 起動時に必須ではないようにオプション化する
	p.add_argument("input", nargs='?', help="Path to input PLY or XYZ file")
	p.add_argument("--output", "-o", help="Output image path (PNG, JPG). If omitted, show interactively.")
	p.add_argument("--point-size", type=float, default=1.0, help="Point size for scatter (default: 1.0)")
	p.add_argument("--cmap", default="jet", help="Colormap used when z present (default: jet)")
	p.add_argument("--cli", action="store_true", help="Run in CLI mode (default: launch GUI when no args are given)")
	return p


def main() -> None:
	parser = build_arg_parser()
	args = parser.parse_args()
	# デフォルトは GUI 起動とする: 引数無しで実行した場合は GUI を起動
	# 明示的に CLI を実行したい場合は --cli を付けるか、input を指定してください
	if len(os.sys.argv) == 1 and not getattr(args, "cli", False):
		initial = None
		if getattr(args, "input", None):
			initial = os.path.dirname(os.path.abspath(args.input))
		launch_gui(initial_dir=initial)
		return

	# CLI 実行パス: input が必要
	if not getattr(args, "input", None):
		print("入力ファイルを指定してください。--help を参照してください。")
		raise SystemExit(1)

	input_path = args.input
	if not os.path.isfile(input_path):
		print(f"入力ファイルが見つかりません: {input_path}")
		raise SystemExit(1)

	xs, ys, zs = parse_file(input_path)
	if not xs or not ys:
		print("有効なXYデータが見つかりませんでした。")
		raise SystemExit(1)

	title = os.path.basename(input_path)
	plot_xy(xs, ys, zs, title=title, outpath=args.output, cmap=args.cmap, point_size=args.point_size)


if __name__ == "__main__":
	main()
