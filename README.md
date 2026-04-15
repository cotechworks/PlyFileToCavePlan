# PlyFileToCavePlan

このスクリプトは PLY形式（ASCII）および XYZ 形式のファイルを読み、XY 座標を2Dプロットします。

## インストール

GitHub の Releases ページからアプリをダウンロードしてください:
	https://github.com/cotechworks/PlyFileToCavePlan/releases

インストールは不要です。

注意事項:
- このアプリはWindows専用です。
- ダウンロードした実行ファイルを初めて実行する場合、Windows の SmartScreen やアンチウイルスが警告を出すことがあります。信頼できる出所から入手したことを確認して実行してください。

## 使い方（GUI 起動）:

このツールは引数無しで実行すると GUI を起動します。主な操作手順と UI の説明を以下に示します。

1. 起動
	- ダブルクリック、または:

```powershell
python PlyFileToCavePlan.py
```

2. ファイルを開く
	- [Open File] ボタンで `.ply` / `.xyz` ファイルを選択します。

3. プレビュー
	- [Preview] を押すと読み込み・（必要なら）ダウンサンプリング・描画が行われ、ウィンドウ内に表示されます。
	- 大きなファイルでは進捗バーが表示され、処理をキャンセルできます。

4. 画像保存
	- [Save PNG] で現在のプレビューを PNG/JPEG として保存します。保存中はインジケータが回転し、操作は一時的に無効化されます。

5. 主なオプション
	- Point size: 散布図の点の大きさを指定します。
	- Colormap: z 値がある場合のカラーマップを選択します。
	- Downsample: GUI で読み込む際の最大点数（大きいデータはランダムサンプリングされます）。0 を指定するとダウンサンプリングを無効化します。
	- Hexbin (Use hexbin): 密度表示（六角形ビン）モードに切替えます。gridsize で精度を調整します。

6. 設定の永続化
	- GUI で指定したパラメータ（Point size, Downsample, Colormap, Plot mode, Gridsize, 最終ディレクトリ）は実行ファイルと同じディレクトリに
	  `plyfiletocaveplan_config.json` という名前で保存されます。必要なら手動で編集できます（JSON）。


## コマンドライン（CLI）で実行する方法
- CLI で実行するには入力ファイルを指定するか、`--cli` を付けて明示的に CLI モードで起動します。

## 使い方（CLI 実行）:

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

## Blender から PLY をエクスポートする方法

ここでは、Blender を使って PLY（ASCII）ファイルを作成する手順を説明します。PlyFileToCavePlan は ASCII PLY を期待しますので、エクスポート時に「ASCII」を選択してください。

1. Blender を開き、エクスポートしたいオブジェクトを選択します（Object Mode）。

2. 必要ならモディファイアを適用します（例: Subdivision, Decimate など）。メッシュの形状や頂点数がそのまま出力されます。

3. メニューから File → Export → PLY (.ply) を選びます。

4. エクスポートダイアログの主な設定:
    - Format: ASCII を選択（必須）。
    - Apply Modifiers: 必要に応じてチェック（モディファイアの効果を反映したい場合）。
    - Selection Only: 選択したオブジェクトだけを出力したい場合はチェック。
    - Include Normals / Include UVs / Include Colors: PlyFileToCavePlan は x,y,(z) の座標のみを使用します。余分な情報は不要なのでオフでも問題ありません。
    - Forward / Up: 座標系の向きを確認してください（Blender は Z-up）。必要に応じてここで軸変換を行ってください。

5. 出力ファイル名を指定してエクスポートします。

注意点:
- バイナリ PLY は本ツールではサポートしていません（エラーになります）。必ず ASCII を選んでください。
- メッシュから頂点のみを点群として使いたい場合、PLY に頂点座標 (x,y,z) が出力されます。フェースや他の要素が含まれていても本スクリプトは頂点情報のみを読み取ります。
- 座標の向き（Z-up / Y-up）によって XY 平面にプロットした結果が変わるため、必要に応じてエクスポート時に軸変換（Forward / Up）を設定してください。
