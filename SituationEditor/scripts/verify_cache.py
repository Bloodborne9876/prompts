# -*- coding: utf-8 -*-
"""検証: no-storeヘッダー + 同一行の連続テストで画像が実際に変わること (ランダムseed)"""
import hashlib
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
_port = json.loads((ROOT / "data" / "settings.json").read_text(encoding="utf-8-sig")).get("editorPort", 7861)
B = f"http://127.0.0.1:{_port}"

recipes = requests.get(B + "/api/recipes").json()
name, recipe = next(iter(recipes.items()))
recipe["title"] = "_chk"
recipe["seedMode"] = "random"
recipe["steps"] = [dict(recipe["steps"][0], count=1, seedMode="inherit")]


def run_once():
    requests.post(B + "/api/generate", json={"recipe": recipe, "mode": "step", "stepIndex": 0}).raise_for_status()
    while requests.get(B + "/api/progress").json()["running"]:
        time.sleep(2)
    p = requests.get(B + "/api/progress").json()
    assert not p["error"], p["error"]
    url = p["images"][0]["url"]
    r = requests.get(B + url)
    return p["images"][0]["seed"], hashlib.md5(r.content).hexdigest()[:10], r.headers.get("Cache-Control")


s1, h1, cc = run_once()
s2, h2, _ = run_once()
print("Cache-Control:", cc)
print(f"1回目 seed={s1} hash={h1}")
print(f"2回目 seed={s2} hash={h2}")
print("同一URLで画像が更新される:", h1 != h2)
