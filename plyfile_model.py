"""Model layer for PlyFileToCavePlan.

This module contains data/IO and parsing/plotting helpers. It is the
central Model in the MVVM refactor and intentionally includes the
lightweight parsers (ASCII PLY/XYZ) plus plotting helpers used by the GUI
and CLI.
"""

from __future__ import annotations

import json
import os
import re
import random
import threading
from typing import Callable, List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np


FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


CONFIG_NAME = "plyfiletocaveplan_config.json"


def get_config_path() -> str:
    """Return the full path to the configuration file in the user's home dir."""
    home = os.path.expanduser("~")
    return os.path.join(home, CONFIG_NAME)


def load_config() -> dict:
    path = get_config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def parse_xyz(
    filepath: str,
    progress_callback: Optional[callable] = None,
    cancel_check: Optional[callable] = None,
) -> Tuple[List[float], List[float], Optional[List[float]]]:
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


def parse_ply(
    filepath: str,
    progress_callback: Optional[callable] = None,
    cancel_check: Optional[callable] = None,
) -> Tuple[List[float], List[float], Optional[List[float]]]:
    """Simple PLY (ASCII) parser: extract x,y,(z) from vertex elements."""
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
                raise ValueError("PLY header not found")
            header_lines.append(line.rstrip("\n"))
            l = line.strip()
            if l.startswith("format"):
                if "ascii" in l.lower():
                    format_ascii = True
                else:
                    raise ValueError("Only ascii PLY is supported")
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
            raise ValueError("Only ASCII PLY is supported")

        try:
            ix = property_names.index("x")
            iy = property_names.index("y")
            iz = property_names.index("z") if "z" in property_names else None
        except ValueError:
            raise ValueError("PLY properties x,y not found")

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
                            pct = min(
                                100.0, (lines / (vertex_count or (lines + 1))) * 100.0
                            )
                    else:
                        pct = min(
                            100.0, (lines / (vertex_count or (lines + 1))) * 100.0
                        )
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


def parse_file(
    filepath: str,
    progress_callback: Optional[callable] = None,
    cancel_check: Optional[callable] = None,
) -> Tuple[List[float], List[float], Optional[List[float]]]:
    """Delegate to the right parser based on file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".ply":
        return parse_ply(
            filepath, progress_callback=progress_callback, cancel_check=cancel_check
        )
    else:
        return parse_xyz(
            filepath, progress_callback=progress_callback, cancel_check=cancel_check
        )


def plot_xy(
    xs: List[float],
    ys: List[float],
    zs: Optional[List[float]] = None,
    *,
    title: Optional[str] = None,
    outpath: Optional[str] = None,
    cmap: str = "jet",
    point_size: float = 1.0,
    plot_mode: str = "scatter",
    gridsize: int = 50,
    downsample: Optional[int] = None,
) -> None:
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
        fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        plt.savefig(outpath, dpi=200)
        print(f"Saved plot to: {outpath}")
        plt.close(fig)
    else:
        plt.show()


def create_figure(
    xs: List[float],
    ys: List[float],
    zs: Optional[List[float]] = None,
    title: Optional[str] = None,
    cmap: str = "jet",
    point_size: float = 1.0,
    plot_mode: str = "scatter",
    gridsize: int = 50,
    downsample: Optional[int] = None,
) -> Figure:
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
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    return fig


def parse_with_progress(
    filepath: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse a .ply/.xyz file and expose progress/cancel as a simple wrapper."""
    # provide a callable cancel_check if caller passed an Event
    cancel_check = None
    if cancel_event is not None:
        try:
            cancel_check = cancel_event.is_set
        except Exception:
            cancel_check = None

    xs, ys, zs = parse_file(
        filepath, progress_callback=progress_cb, cancel_check=cancel_check
    )
    return np.array(xs), np.array(ys), (np.array(zs) if zs is not None else None)


def export_points_csv(csv_path: str, points: List[Tuple[float, float, float]]) -> None:
    try:
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("x,y,z\n")
            for x, y, z in points:
                f.write(f"{x},{y},{z}\n")
    except Exception:
        raise


def import_points_csv(csv_path: str) -> List[Tuple[float, float, float]]:
    out: List[Tuple[float, float, float]] = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            header = f.readline()
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                try:
                    x = float(parts[0])
                    y = float(parts[1])
                    z = float(parts[2])
                    out.append((x, y, z))
                except ValueError:
                    continue
    except Exception:
        raise
    return out


class Model:
    """In-memory model for the application."""

    def __init__(self) -> None:
        self.path: Optional[str] = None
        self.xs: Optional[np.ndarray] = None
        self.ys: Optional[np.ndarray] = None
        self.zs: Optional[np.ndarray] = None
        self.added_points: List[Tuple[float, float, float]] = []
        self.remove_history: List[List[Tuple[float, float, float]]] = []