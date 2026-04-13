# PlyFileToCavePlan

このスクリプトは PLY（ASCII）および従来の XYZ 形式のファイルを読み、XY 座標を2Dプロットします。

デフォルト動作
- 引数無しでスクリプトを実行すると GUI を起動します（例: ダブルクリックや `python PlyFileToCavePlan.py`）。

コマンドライン（CLI）で実行する方法
- CLI で実行するには入力ファイルを指定するか、`--cli` を付けて明示的に CLI モードで起動します。

使い方（GUI 起動）:

```powershell
python PlyFileToCavePlan.py
```

使い方（CLI 実行）:

```powershell
# positional に入力ファイルを指定する (例)
python PlyFileToCavePlan.py sample.ply --output sample_plot.png

# または --cli を明示して実行
python PlyFileToCavePlan.py --cli sample.ply --output sample_plot.png
```

- `input.ply` / `input.xyz`: 読み込むファイル（PLY (ASCII) または各行 x y [z] のテキスト）。PLY のバイナリ形式はサポートしていません。
- `--output, -o`: 指定すると画像を保存、指定しないとウィンドウ表示
- `--point-size`: 散布図の点サイズ (デフォルト: 1.0)
- `--cmap`: zが含まれる場合のカラーマップ (デフォルト: `jet`)

GUI の既定値
- Point size: 1.0
- Downsample (GUI の初期値): 50000  ※ 0 を指定するとダウンサンプリングを無効にします

簡単な検証:

1. 依存パッケージをインストールします。

```powershell
python -m pip install -r requirements.txt
```

2. サンプルデータで実行 (CLI 例):

```powershell
python PlyFileToCavePlan.py sample.ply --output sample_plot.png
```

生成された画像を開いて確認してください。

設定の永続化
- GUI で指定したパラメータ（Point size, Downsample, Colormap, Plot mode, Gridsize, 最終ディレクトリ）は実行ファイルと同じディレクトリに
	`plyfiletocaveplan_config.json` という名前で保存されます。ファイルは隠し属性にはなりません。必要なら手動で編集できます（JSON）。
