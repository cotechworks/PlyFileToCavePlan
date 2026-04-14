"""Utility functions for PlyFileToCavePlan.

切り出した内容: parse_xyz, parse_ply, parse_file, plot_xy, create_figure
"""
from __future__ import annotations

import os
import re
import random
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_xyz(filepath: str,
              progress_callback: Optional[callable] = None,
              cancel_check: Optional[callable] = None) -> Tuple[List[float], List[float], Optional[List[float]]]:
    """XYZファイルを読み、x,y,(z)のリストを返す。"""
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

            if progress_callback and (lines % report_interval_lines == 0):
                if total_size:
                    try:
                        pct = (f.tell() / total_size) * 100.0
                    except Exception:
                        pct = min(100.0, (lines / (lines + 1)) * 100.0)
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


def parse_ply(filepath: str,
              progress_callback: Optional[callable] = None,
              cancel_check: Optional[callable] = None) -> Tuple[List[float], List[float], Optional[List[float]]]:
    """Simple PLY (ASCII) parser: 頂点要素から x,y,(z) を抽出する。"""
    xs: List[float] = []
    ys: List[float] = []
    zs: List[float] = []
    has_z = False

    header_lines = []
    format_ascii = False
    vertex_count = None
    property_names: List[str] = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
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
                    raise ValueError("バイナリ PLY はサポートされていません (ascii のみ)")
            if l.startswith("element"):
                parts = l.split()
                if len(parts) >= 3 and parts[1] == "vertex":
                    try:
                        vertex_count = int(parts[2])
                    except Exception:
                        vertex_count = None
            if l.startswith("property") and vertex_count is not None:
                parts = l.split()
                if len(parts) >= 3:
                    property_names.append(parts[-1])
            if l == "end_header":
                break

        if not format_ascii:
            raise ValueError("ASCII PLY のみサポートされています")

        try:
            ix = property_names.index("x")
            iy = property_names.index("y")
            iz = property_names.index("z") if "z" in property_names else None
        except ValueError:
            raise ValueError("PLY のプロパティに x,y が見つかりません")

        try:
            total_size = os.path.getsize(filepath)
        except Exception:
            total_size = None
        last_report = 0.0
        lines = 0

        if vertex_count is not None:
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
        return parse_xyz(filepath, progress_callback=progress_callback, cancel_check=cancel_check)


def plot_xy(xs: List[float], ys: List[float], zs: Optional[List[float]] = None, *,
            title: Optional[str] = None, outpath: Optional[str] = None,
            cmap: str = "jet", point_size: float = 1.0,
            plot_mode: str = "scatter", gridsize: int = 50, downsample: Optional[int] = None) -> None:
    """XYを2Dで散布図プロットする。"""
    fig, ax = plt.subplots(figsize=(8, 6))
    if zs is not None:
        try:
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
        # 固定余白を使ってプロット領域をキャンバスいっぱいにする
        # 値は比率（0.0-1.0）。必要に応じて調整してください。
        fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
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
    # キャンバス内の余白を固定（比率）にして、グラフ領域をキャンバスいっぱいに広げる
    # 必要に応じてこの値を調整してください（left,right,top,bottom）。
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    return fig
