"""
PNG ファイルから Stable Diffusion のポジティブプロンプトを抽出し、
カテゴリごとに JSON ファイルを生成するスクリプト。

ファイル名形式: 名前_カテゴリ_連番.png
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillowが必要です: pip install Pillow")
    sys.exit(1)

DEFAULT_IGNORE = [
    "8k wallpaper, extremely detailed fingers, detail eyes , perfect anatomy, highly detailed background, shiny skin, narrow waist, BREAK",
    "1girl, solo , <lora:illyasviel_von_einzbern_(fate_kaleid_liner)_v1:0.8:lbw=OUTD> ,aaillya, long hair, two side up, hair ornament, small breasts, magical girl, cape, yellow ascot, pink dress, sleeveless, detached sleeves, white gloves, white skirt, pink thighhighs",
    "fate/kaleid liner prisma illya, long hair, blonde hair, two side up, hair ornament, red eyes, pink dress, torn clothes, white gloves, heart-shaped pupils, pink eyes , half-closed eyes, heavy breathing, drooling, upper body",
    "purple , mucus, no humans, sound effects, masterpiece, best quality, absurdres, very aesthetic, general, perfect anatomy, 1girl, solo, (nsfw:1.2) 9yo, loli, flat chest, fate/kaleid liner prisma illya, long hair, blonde hair, two side up, hair ornament, red eyes, pink dress, torn clothes, white gloves, white skirt, heart-shaped pupils, pink eyes, (simple background, black background:1.1) , masterpiece, best quality, absurdres, very aesthetic, general, perfect anatomy, 1girl, solo , (nsfw:1.2) 9yo , loli , flat chest, illyasviel von einzbern, long hair, blonde hair, blonde hair, red eyes, nude , half-closed eyes",
]


def normalize(text: str) -> str:
    """改行・連続スペースを単一スペースに正規化"""
    return re.sub(r"\s+", " ", text).strip()


def get_positive_prompt(png_path: Path) -> str | None:
    """PNG メタデータからポジティブプロンプトを抽出"""
    try:
        with Image.open(png_path) as img:
            parameters = img.info.get("parameters", "")
        if not parameters:
            print(f"  [SKIP] メタデータなし: {png_path.name}")
            return None
        # "Negative prompt:" より前がポジティブプロンプト
        positive = parameters.split("Negative prompt:")[0]
        return normalize(positive)
    except Exception as e:
        print(f"  [ERROR] {png_path.name}: {e}")
        return None


def remove_ignore(prompt: str, ignore_list: list[str]) -> str:
    """ignore_list の文字列をプロンプトから除去"""
    for ig in ignore_list:
        ig_norm = normalize(ig)
        prompt = prompt.replace(ig_norm, "")
    # 残った余分なカンマ・スペースを整理
    prompt = re.sub(r",\s*,", ",", prompt)
    prompt = re.sub(r"\s+", " ", prompt)
    prompt = prompt.strip(" ,")
    return prompt


def main():
    parser = argparse.ArgumentParser(
        description="PNG から SD ポジティブプロンプトを抽出し、カテゴリ別 JSON を生成"
    )
    parser.add_argument("folder", nargs="?", help="PNG ファイルが入っているフォルダ")
    parser.add_argument(
        "--ignore",
        nargs="+",
        metavar="STRING",
        help="追加で除去する文字列（スペース区切りで複数指定可）",
    )
    parser.add_argument(
        "--no-default-ignore",
        action="store_true",
        help="デフォルトの ignore 文字列を使わない",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="JSON 出力先フォルダ（デフォルト: folder と同じ）",
    )
    args = parser.parse_args()

    if not args.folder:
        args.folder = input("PNG Folder (drag & drop or type path): ").strip().strip('"')

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"フォルダが見つかりません: {folder}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else folder
    output_dir.mkdir(parents=True, exist_ok=True)

    # ignore リスト構築
    ignore_list: list[str] = []
    if not args.no_default_ignore:
        ignore_list.extend(DEFAULT_IGNORE)
    if args.ignore:
        ignore_list.extend(args.ignore)

    # PNG を名前_カテゴリ_連番 でパース
    category_map: dict[str, list[dict]] = {}

    for png_file in sorted(folder.glob("*.png")):
        stem = png_file.stem
        parts = stem.split("_")
        if len(parts) < 3:
            print(f"[SKIP] ファイル名形式が不正（名前_カテゴリ_連番）: {png_file.name}")
            continue

        # 名前_カテゴリ_連番 → parts[0]=名前, parts[1]=カテゴリ, parts[2:]=連番(複数_対応)
        char_name = parts[0]
        category = parts[1]

        prompt = get_positive_prompt(png_file)
        if prompt is None:
            continue

        prompt = remove_ignore(prompt, ignore_list)

        if category not in category_map:
            category_map[category] = []

        category_map[category].append(
            {
                "file": png_file.name,
                "name": char_name,
                "prompt": prompt,
            }
        )

    if not category_map:
        print("対象ファイルが見つかりませんでした。")
        sys.exit(0)

    # 名前を取得（全エントリの最初のファイルから）
    char_name = next(iter(category_map.values()))[0]["name"]

    # 全カテゴリをまとめて1つの JSON に出力
    payload = [
        {
            "category": category,
            "prompt": [entry["prompt"] for entry in entries],
        }
        for category, entries in sorted(category_map.items())
    ]

    out_path = output_dir / f"{char_name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    total = sum(len(e) for e in category_map.values())
    print(f"[OK] {out_path}  ({len(category_map)} カテゴリ, {total} 件)")
    print(f"\n完了: {out_path}")


if __name__ == "__main__":
    main()
