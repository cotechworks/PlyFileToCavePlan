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
from plyfile_utils import (
	parse_xyz,
	parse_ply,
	parse_file,
	plot_xy,
	create_figure,
)

# GUI entrypoint was moved to `plyfile_gui.py` as `launch_gui`.
# Importing the function here so CLI or other callers can use it.
from plyfile_gui import launch_gui


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
