# シチュエーションエディター

キャラ × 服装パターン × シチュエーションを「レシピ」として組み、SD WebUI API で
イラスト集（1作品 約100枚）を一括生成するツール。

## 起動

```
start_editor.bat   （= python server.py。ブラウザが自動で開く）
```

ローカルサーバー `http://127.0.0.1:7861`（ポートは settings.json の `editorPort`）。
SD WebUI (Forge Neo, :7860) を先に起動しておくこと。

## 構成

| パス | 役割 |
|---|---|
| `server.py` | ローカルサーバー本体（FastAPI）。editor配信 / ファイルIO / タグ補完 / 生成実行 / 進捗 |
| `start_editor.bat` | サーバー起動ランチャー |
| `editor.html` | GUI（サーバー経由で配信。フォルダ選択は不要になった） |
| `data\settings.json` | API URL / 品質ヘッダ / ネガティブプリセット / サイズ / 生成パラメータ / editorPort |
| `data\characters.json` | キャラ定義（base + 服装パターン normal/torn/underwear/nude/seifuku…） |
| `data\situations.json` | シチュエーションライブラリ（フェーズ分類・整理済み） |
| `data\faces.json` | 表情プリセット（泣き顔/アヘ顔/メス堕ち…＋`__face/*__`ラップのランダム系） |
| `data\situations_raw_backup.json` | 整理前の自動取り込みデータ（バックアップ） |
| `recipes\*.json` | レシピ＝1作品の設計図（キャラ＋step列） |
| `library\プロンプトライブラリ.md` | ライブラリの可読版（自動生成・直接編集しない） |
| `scripts\Invoke-Generate.ps1` | CLI版の生成（server.py と同一ロジック・出力互換。普段はGUIで足りる） |
| `scripts\Export-Library.ps1` | situations.json → library\*.md 再生成 |
| `scripts\Import-Markdown.ps1` | Tentacle*.md 等 → situations.json 取り込み |
| `scripts\Import-Characters.ps1` | キャラ\*.md → characters.json 取り込み |
| `output\<作品名>\` | 生成結果。`NN_シチュエーションID\キャラID_NN_連番.png`（行テストは `_test\` 配下） |

## タグ補完

プロンプト入力欄（シチュエーション base/variations、キャラ base、服装、追加ネガティブ）で
タグの一部を入力すると候補がポップアップする（tagcomplete の danbooru 辞書 14万件を流用）。

- 英語は2文字以上、**日本語は1文字以上**で検索（例:「制服」→ school uniform）
- ↑↓で選択、Tab / Enter で確定、Esc で閉じる
- 挿入時は WebUI 流に `_`→スペース、`(` `)` は `\(` `\)` に自動エスケープ（`^_^` 等の顔文字タグは除く）

## シチュエーションライブラリ（2026-06 整理済み）

Tentacle4/5/6.md・連続.md・ネタ帳.md（触手/パンチラ）・memo.md を統合し、
ストーリー進行順の **フェーズ**（導入 → 序盤 → 中盤 → 終盤 → アフター → 演出）で30件に整理。
タイプミス修正・重複統合・消失した `__tentacle/*__` wildcard のインライン置換済み。

- シチュエーションごとの追加項目: `phase`（フェーズ）/ `notes`（運用メモ）/ `negativeExtra`（そのシチュエーションだけに足すネガティブ。例: 騎乗位の `1boy, penis`）
- 表情 wildcard はネタ帳の定義から復元済み:
  `__face/emberassed__` `__face/mesu__` `__face/disgust__` `__face/fellatio_smile__` `__face/sex_smile__`
  （場所: `C:\sd-webui-forge-neo\extensions\sd-dynamic-prompts\wildcards\face\`）
- 元の md は変更していない。`old\` フォルダ（Tentacle3_xl・下着 等）はアーカイブ扱いで未移行

## プロンプト合成順

```
qualityHeader
<キャラbase>, <服装パターン>
<表情>, <シチュエーションbase>, <variation>, <commonTail>
```

- **表情**は3層で決まる: step行の「表情」列（既定/なし/各表情）＞ シチュエーションの「既定の表情」＞ なし。
  表情タブで自由に追加・編集できる（タグに `__face/xxx__` wildcardを書けば毎回ランダムになる）

- 区切りは既定で改行のみ（WebUIと同じ）。`settings.json` の `useBreak: true` でBREAK区切りに変更可
  （BREAKはCLIP系のチャンク分割。Qwenエンコーダ系モデル＝現行のhakushiMixAnimaでは入れない方が正しい）
- `generation.shift` = Forge Neo の「Shift」(API名 distilled_cfg_scale)。**未指定だとAPI既定の3.5になり
  WebUIと絵柄がズレる**ため必ず設定しておく（現在 2.0）

- variation は step の `variationMode` に従い順繰り(cycle)またはランダム(random)
- `{a|b}` / `__wildcard__` は Dynamic Prompts 拡張がサーバ側で毎回展開（同じ variation でも絵が変わる）
- 生成PNGには infotext を埋め込み済み → WebUI の PNG Info / `Export\extract_prompts.py` 互換

## 日常の流れ（新作を作る）

1. `start_editor.bat` で起動（ブラウザが自動で開く。フォルダ選択は不要）
2. レシピタブで既存レシピを**複製** → キャラ id を差し替え → 枚数調整（合計表示を見ながら）→ 保存
   - **シード（一括）**: ランダム / 固定（全画像同一）/ インクリメント（通しで+1、レシピ全体を再現可能）
   - step の**シード列**で行ごとに上書き可: 一括に従う / 固定 / INC（行内+1）/ 乱
   - **HiresFix チェック**: ON でレシピ全体を hires 生成（倍率・アップスケーラーは settings.json）
   - **Calibrated Spectrum チェック**: 既定ON。APIでは明示送信しないと無効になるためツールが常に制御する
3. step 行の **🧪 ボタン**でその行を**設定枚数ぶん**テスト生成 → 画面下に表示＋ `output\<作品名>\_test\` に保存
   - シード・HiresFix・Spectrum 設定はテストにも反映（一括インクリメント時は本生成でその行が引くシードと一致）
4. **📄 DryRun** で全プロンプト＋シードをプレビュー欄に表示して確認
   - **🔍 API生データ**: 直近にWebUIへ送った txt2img リクエストJSONと返ってきたinfotextを表示。
     全履歴は `output\<作品名>\api_log.jsonl`（WebUI本体との設定差を調べるときはこれを見る）
5. **▶ 本生成**（確認ダイアログ→保存→実行。進捗バー＋ETA表示、⏹停止、⏩再開=既存スキップ）
   1枚あたり約13〜20秒 = 130枚で約40分。画面を閉じても生成は続く（開き直せば進捗表示が復帰）
   - CLI派: `scripts\Invoke-Generate.ps1 -Recipe ..\recipes\X.json`（-DryRun / -Test / -Resume / -From。出力互換）
6. `output\<作品名>\` をエクスプローラーで選別 → 既存のモザイク/Export/zip 工程へ

選別を見込み、目標枚数の 1.3〜1.5 倍で組むこと（合計バーが100枚で✓表示）。

## メモ

- キャラの取り込み直後は base がキャラ名タグのみ。LoRA・髪・目のタグは GUI のキャラタブで追記する
- `__face/emberassed__` は `C:\sd-webui-forge-neo\extensions\sd-dynamic-prompts\wildcards\face\emberassed.txt`
  に作成済み（旧環境の資産が無かったため再作成。内容は要調整）
- hires fix は `settings.json` の `generation.enable_hr: true` で有効化（hr_scale 1.5 → 縦 2304px 相当）
- 生成ログ: `output\<作品名>\generation_log.jsonl`（ファイル/seed/プロンプト）
