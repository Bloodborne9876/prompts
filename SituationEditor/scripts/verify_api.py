# -*- coding: utf-8 -*-
"""検証: サイズ反映 + last_request + api_log"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
_port = json.loads((ROOT / "data" / "settings.json").read_text(encoding="utf-8-sig")).get("editorPort", 7861)
B = f"http://127.0.0.1:{_port}"
recipes = requests.get(B + "/api/recipes").json()
name, recipe = next(iter(recipes.items()))
print("使用レシピ:", name, "/ step1 size:", recipe["steps"][0].get("size"))
recipe["title"] = "_chk"
recipe["steps"] = [dict(recipe["steps"][0], count=1)]

r = requests.post(B + "/api/generate", json={"recipe": recipe, "mode": "step", "stepIndex": 0})
print("generate:", r.status_code, r.text[:120] if not r.ok else r.json())
while True:
    p = requests.get(B + "/api/progress").json()
    if not p["running"]:
        print("done:", p["done"], "error:", p["error"] or "none")
        break
    time.sleep(2)

lr = requests.get(B + "/api/last_request").json()
pl = lr["payload"]
print("last_request:", lr["file"], "size:", pl["width"], "x", pl["height"],
      "/ steps:", pl["steps"], "/ cfg:", pl["cfg_scale"], "/ scheduler:", pl["scheduler"])
print("infotext size line:", [s for s in lr["infotext"].split(", ") if s.startswith("Size")])

log = ROOT / "output" / "_chk" / "_test" / "api_log.jsonl"
print("api_log:", log.exists(), "entries:", sum(1 for _ in open(log, encoding="utf-8")) if log.exists() else 0)

from PIL import Image
img_path = next((ROOT / "output" / "_chk" / "_test").rglob("*.png"))
print("actual image:", Image.open(img_path).size)
