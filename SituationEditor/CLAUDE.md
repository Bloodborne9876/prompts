# CLAUDE.md — SituationEditor

## プロジェクト概要

SD WebUI (Forge Neo) の txt2img API を使い、キャラ × 服装 × シチュエーションの組み合わせ（レシピ）からイラストを一括生成するツール。
FastAPI サーバー (`server.py`) + シングルページ GUI (`editor.html`) の構成。

## 起動

```
start_editor.bat          # = python server.py → http://127.0.0.1:8861
```

前提: SD WebUI Forge Neo が `:7860` で起動済みであること。

## 技術スタック

- **サーバー**: Python 3 / FastAPI / uvicorn
- **フロントエンド**: バニラ HTML + JS (editor.html 1ファイル、フレームワークなし)
- **画像処理**: Pillow (PNG infotext 埋め込み)
- **外部API**: SD WebUI Forge Neo `/sdapi/v1/txt2img`

## ディレクトリ構成

```
server.py              サーバー本体 (配信 / ファイルIO / タグ補完 / 生成エンジン)
editor.html            GUI (サーバーから配信)
start_editor.bat       起動ランチャー
data/
  settings.json        API URL / サイズプリセット / 生成パラメータ / ポート
  characters.json      キャラ定義 (base + 服装パターン)
  situations.json      シチュエーションライブラリ (フェーズ分類済み)
  faces.json           表情プリセット
recipes/*.json         レシピ = 1作品の設計図
output/                生成結果 (NN_シチュID/キャラID_NN_連番.png)
scripts/               CLI版生成・取り込み・検証スクリプト
library/               situations.json の可読エクスポート (自動生成)
```

## 開発ルール

- `editor.html` は1ファイル完結。JS/CSS の分離やバンドラーは使わない
- `server.py` も1ファイル完結。生成ロジックは `scripts/Invoke-Generate.ps1` と出力互換を維持する
- データファイル (`data/*.json`) のスキーマを変える場合は GUI 側のロード/セーブも合わせて修正する
- `output/` 配下は生成物なのでコミットしない
- タグ辞書は `settings.json` の `tagsDir` が指すローカルパス (SD WebUI の tagcomplete 拡張) に依存

## コーディング規約

- Python: UTF-8、インデント4スペース
- HTML/JS/CSS: editor.html 内にインライン、インデント2スペース
- コミットメッセージ・コメント: 日本語可
- JSON ファイル: `ensure_ascii=False`, `indent=2`

## 生成エンジンの重要ポイント

- `distilled_cfg_scale` (Forge Neo の Shift) を明示送信しないと API 既定 3.5 になり WebUI と絵柄がズレる
- Calibrated Spectrum は `alwayson_scripts` で明示しないと UI 既定 (無効) になる
- `hr_additional_modules: ["Use same choices"]` を送らないと hires 時に VAE 等が外れる
- `useBreak` は既定 false。Qwen エンコーダ系モデル (hakushiMixAnima) では BREAK を入れない

## テスト / 検証

自動テストスイートはない。検証は以下で行う:

- `scripts/verify_*.py` — API 接続・パラメータ確認用の手動スクリプト
- GUI のテスト生成ボタン (🧪) — 1行分を生成して `output/<作品名>/_test/` に出力
- DryRun (📄) — 全プロンプトとシードをプレビュー表示
