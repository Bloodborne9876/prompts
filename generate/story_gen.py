"""
販売用同人CG集 生成ツール v2
5幕ストーリー構成 + Dynamic Prompts記法 + Hires.fix対応
設定は config.jsonc で外部管理

使い方:
  python story_gen.py                      # 全幕生成
  python story_gen.py --start 3            # 幕3から再開
  python story_gen.py --hires              # Hires.fix ON で上書き起動
  python story_gen.py --no-hires           # Hires.fix OFF で上書き起動
  python story_gen.py --config my.jsonc    # 別の設定ファイルを使う
  python story_gen.py --dry-run            # プロンプト確認のみ（生成しない）
"""

import argparse
import base64
import io
import json
import random
import time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, PngImagePlugin

# ============================================================
# CLI 引数
# ============================================================
parser = argparse.ArgumentParser(description="Story-based image batch generator")
parser.add_argument("--config",   default="config.jsonc", help="設定JSONCファイルのパス")
parser.add_argument("--start",    type=int, default=1,   help="開始幕番号 (1-5)")
parser.add_argument("--hires",    action="store_true",   help="Hires.fix を強制ON")
parser.add_argument("--no-hires", action="store_true",   help="Hires.fix を強制OFF")
parser.add_argument("--seed",     type=int, default=-1,  help="固定seed (-1でランダム)")
parser.add_argument("--dry-run",  action="store_true",   help="プロンプト確認のみ（生成しない）")
args = parser.parse_args()

# ============================================================
# 設定読み込み
# ============================================================
config_path = Path(args.config)
if not config_path.exists():
    print(f"❌ 設定ファイルが見つかりません: {config_path}")
    exit(1)

def _load_jsonc(path: Path) -> dict:
    """JSONC（// および /* */ コメント付き）を読み込む"""
    text = path.read_text(encoding="utf-8")
    # 状態機械で文字列内の // や /* を誤って除去しないよう処理する
    result = []
    i = 0
    in_string = False
    while i < len(text):
        if in_string:
            if text[i] == '\\':
                result.append(text[i])
                i += 1
                if i < len(text):
                    result.append(text[i])
                    i += 1
            elif text[i] == '"':
                result.append(text[i])
                in_string = False
                i += 1
            else:
                result.append(text[i])
                i += 1
        else:
            if text[i] == '"':
                result.append(text[i])
                in_string = True
                i += 1
            elif text[i:i+2] == '//':
                # 行コメント: 行末まで読み飛ばす
                while i < len(text) and text[i] != '\n':
                    i += 1
            elif text[i:i+2] == '/*':
                # ブロックコメント: */ まで読み飛ばす
                i += 2
                while i < len(text) - 1 and text[i:i+2] != '*/':
                    i += 1
                i += 2
            else:
                result.append(text[i])
                i += 1
    return json.loads(''.join(result))

CFG = _load_jsonc(config_path)

WEBUI_URL   = CFG["webui_url"]
OUTPUT_DIR  = Path(CFG["output_dir"])
TITLE       = CFG["title"]
BASE        = CFG["base"]
HIRES       = CFG["hires"]
STORY_SCENES = CFG["scenes"]
QUALITY     = CFG["quality"]
NEGATIVE    = CFG["negative"]
CHARACTER   = CFG["character"]

TOTAL = sum(s["count"] for s in STORY_SCENES)

# CLI引数でhires ON/OFF を上書き
if args.no_hires:
    HIRES["enabled"] = False
elif args.hires:
    HIRES["enabled"] = True

# ============================================================
# ユーティリティ
# ============================================================

def check_connection() -> bool:
    try:
        requests.get(f"{WEBUI_URL}/sdapi/v1/sd-models", timeout=5).raise_for_status()
        print("✅ WebUI接続OK")
        return True
    except Exception as e:
        print(f"❌ 接続失敗: {e}")
        return False


def build_prompt(scene: dict) -> str:
    return ", ".join([QUALITY, CHARACTER, scene["tone"], scene["prompt_dp"]])


def print_config_summary():
    print("\n📋 現在の設定 (config.jsonc)")
    print(f"   タイトル    : {TITLE}")
    print(f"   サンプラー  : {BASE['sampler_name']} / {BASE['scheduler']}")
    print(f"   ベースサイズ: {BASE['width']}x{BASE['height']}")
    print(f"   Steps / CFG : {BASE['steps']} / {BASE['cfg_scale']}")
    hires_status = "✅ ON" if HIRES["enabled"] else "⬜ OFF"
    print(f"   Hires.fix  : {hires_status}")
    if HIRES["enabled"]:
        w2 = int(BASE["width"]  * HIRES["hr_scale"])
        h2 = int(BASE["height"] * HIRES["hr_scale"])
        print(f"     アップスケーラー : {HIRES['upscaler']}")
        print(f"     倍率             : x{HIRES['hr_scale']}  ({BASE['width']}x{BASE['height']} → {w2}x{h2})")
        print(f"     Hires steps      : {HIRES['hr_steps']}  (0 = 1stパスと同値)")
        print(f"     Denoising        : {HIRES['denoising_strength']}")
    print()

# ============================================================
# 生成コア
# ============================================================

def generate_image(
    prompt: str,
    scene_name: str,
    index: int,
    seed: int,
) -> Path | None:

    date_str = datetime.now().strftime("%Y%m%d")
    scene_dir = OUTPUT_DIR / TITLE / scene_name / date_str
    scene_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%H%M%S")
    base_name = f"{TITLE}_{scene_name}_{index:02d}_{ts}"

    payload = {
        "prompt":          prompt,
        "negative_prompt": NEGATIVE,
        "steps":           BASE["steps"],
        "cfg_scale":       BASE["cfg_scale"],
        "width":           BASE["width"],
        "height":          BASE["height"],
        "sampler_name":    BASE["sampler_name"],
        "scheduler":       BASE["scheduler"],
        "seed":            seed,
        "batch_size":      1,
        "restore_faces":   BASE["restore_faces"],
        "tiling":          BASE["tiling"],
        "override_settings": {
            "CLIP_stop_at_last_layers": BASE.get("clip_skip", 1),
        },
    }

    # Hires.fix オプション
    if HIRES["enabled"]:
        payload.update({
            "enable_hr":              True,
            "hr_upscaler":            HIRES["upscaler"],
            "hr_scale":               HIRES["hr_scale"],
            "hr_second_pass_steps":   HIRES["hr_steps"],
            "denoising_strength":     HIRES["denoising_strength"],
        })

    try:
        r = requests.post(
            f"{WEBUI_URL}/sdapi/v1/txt2img",
            json=payload,
            timeout=600,  # Hires.fix は時間がかかるので余裕を持たせる
        )
        r.raise_for_status()
        result = r.json()
    except requests.exceptions.Timeout:
        print("    ⚠️  タイムアウト - hr_scale / steps を下げてください")
        return None
    except Exception as e:
        print(f"    ❌ 生成失敗: {e}")
        return None

    images = result.get("images", [])
    if not images:
        print("    ⚠️  画像なし")
        return None

    img_path = scene_dir / f"{base_name}.png"

    # WebUI info から実際の生成パラメータを取得
    try:
        info_json = json.loads(result.get("info", "{}"))
    except Exception:
        info_json = {}

    used_seed  = info_json.get("seed", seed)
    model_name = info_json.get("sd_model_name", "")
    model_hash = info_json.get("sd_model_hash", "")
    out_w      = info_json.get("width",  BASE["width"])
    out_h      = info_json.get("height", BASE["height"])

    # WebUI互換の parameters テキストを組み立て
    param_line = (
        f"Steps: {BASE['steps']}, "
        f"Sampler: {BASE['sampler_name']}, "
        f"Schedule type: {BASE['scheduler']}, "
        f"CFG scale: {BASE['cfg_scale']}, "
        f"Seed: {used_seed}, "
        f"Size: {out_w}x{out_h}"
    )
    if model_hash:
        param_line += f", Model hash: {model_hash}"
    if model_name:
        param_line += f", Model: {model_name}"
    if HIRES["enabled"]:
        param_line += (
            f", Denoising strength: {HIRES['denoising_strength']}"
            f", Hires upscale: {HIRES['hr_scale']}"
            f", Hires steps: {HIRES['hr_steps']}"
            f", Hires upscaler: {HIRES['upscaler']}"
        )
    parameters_text = f"{prompt}\nNegative prompt: {NEGATIVE}\n{param_line}"

    # PNG の tEXt チャンク "parameters" に埋め込んで保存
    img = Image.open(io.BytesIO(base64.b64decode(images[0])))
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("parameters", parameters_text)
    img.save(img_path, pnginfo=png_info)

    return img_path

# ============================================================
# メイン
# ============================================================

def main():
    print_config_summary()

    print(f"📚 ストーリー構成: {len(STORY_SCENES)}幕 / 合計{TOTAL}枚")
    for i, s in enumerate(STORY_SCENES, 1):
        marker = "→" if i == args.start else " "
        print(f"  {marker} 幕{i}: {s['label']:12s}  {s['count']}枚")

    if args.dry_run:
        print("\n🔍 Dry-run: プロンプト確認のみ")
        for s in STORY_SCENES:
            p = build_prompt(s)
            print(f"\n[{s['label']}]\n  {p[:200]}...")
        return

    if not check_connection():
        return

    if args.seed != -1:
        seed_summary = f"全シーン固定 seed={args.seed} (CLI指定)"
    else:
        scene_seeds = [(s["label"], s.get("seed", -1)) for s in STORY_SCENES]
        fixed = [(lbl, sv) for lbl, sv in scene_seeds if sv != -1]
        if fixed:
            fixed_str = ", ".join(f"{lbl}={sv}" for lbl, sv in fixed)
            seed_summary = f"シーン個別設定あり ({fixed_str})"
        else:
            seed_summary = "全シーンランダム"
    print(f"\n🎬 生成開始 (幕{args.start}から / {seed_summary})\n")

    overall = sum(s["count"] for s in STORY_SCENES[: args.start - 1])

    for act_num, scene in enumerate(STORY_SCENES[args.start - 1:], start=args.start):
        print(f"\n{'='*52}")
        print(f"🎭 幕{act_num}: {scene['label']}  ({scene['count']}枚)")
        print(f"   steps={BASE['steps']}  cfg={BASE['cfg_scale']}")
        print(f"{'='*52}")

        prompt = build_prompt(scene)

        # シーン個別seed: CLIの--seedが指定されていれば優先、なければシーン設定、それもなければランダム
        scene_seed = scene.get("seed", -1)

        for i in range(1, scene["count"] + 1):
            overall += 1
            if args.seed != -1:
                seed = args.seed
            elif scene_seed != -1:
                seed = scene_seed
            else:
                seed = random.randint(1, 2**31)

            seed_label = f"{seed} (固定)" if (args.seed != -1 or scene_seed != -1) else f"{seed} (ランダム)"
            print(f"  [{i:2d}/{scene['count']}] 全体 {overall}/{TOTAL}  seed={seed_label}")

            path = generate_image(
                prompt=prompt,
                scene_name=scene["name"],
                index=i,
                seed=seed,
            )
            if path:
                print(f"    💾 {path.name}")

            time.sleep(0.3)

        print(f"  ✅ {scene['label']} 完了")

    # 全体サマリー保存
    summary_dir = OUTPUT_DIR / TITLE
    summary_dir.mkdir(parents=True, exist_ok=True)
    with open(summary_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "title": TITLE,
            "total": TOTAL,
            "hires_enabled": HIRES["enabled"],
            "config_used": str(config_path.resolve()),
            "generated_at": datetime.now().isoformat(),
            "scenes": [
                {"act": i+1, "name": s["name"], "label": s["label"], "count": s["count"]}
                for i, s in enumerate(STORY_SCENES)
            ],
        }, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 全{TOTAL}枚 生成完了!")
    print(f"📁 出力先: {(OUTPUT_DIR / TITLE).resolve()}")


if __name__ == "__main__":
    main()
