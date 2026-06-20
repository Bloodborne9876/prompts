# -*- coding: utf-8 -*-
"""検証: 表情の3パターン (シチュ既定 / step上書き / なし) が plan に反映されること"""
import json
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
_port = json.loads((ROOT / "data" / "settings.json").read_text(encoding="utf-8-sig")).get("editorPort", 7861)
B = f"http://127.0.0.1:{_port}"

recipe = {
    "title": "_face_chk", "character": "yuuka", "negative": "標準",
    "seedMode": "fixed", "seed": 1,
    "steps": [
        {"situation": "panchira_front", "outfit": "normal", "count": 1, "size": "portrait_v"},                      # 既定 (haji_rand → __face/emberassed__)
        {"situation": "panchira_front", "outfit": "normal", "count": 1, "size": "portrait_v", "face": "ahegao"},    # 上書き
        {"situation": "panchira_front", "outfit": "normal", "count": 1, "size": "portrait_v", "face": "none"},      # なし
        {"situation": "panchira_front", "outfit": "normal", "count": 1, "size": "portrait_v", "face": "naki"},      # 泣き顔
    ],
}
r = requests.post(B + "/api/plan", json={"recipe": recipe})
r.raise_for_status()
labels = ["既定(haji_rand)", "上書き(ahegao)", "なし", "泣き顔(naki)"]
blocks = r.text.split("=====")[1:]
for label, block in zip(labels, blocks):
    line3 = [ln for ln in block.strip().splitlines() if ln][-1]  # シチュエーションブロック行
    print(f"{label:18} -> {line3[:90]}")
