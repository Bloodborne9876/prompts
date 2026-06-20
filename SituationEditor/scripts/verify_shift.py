# -*- coding: utf-8 -*-
"""検証: Shift=2 / BREAKなし / infotext が WebUI と同形式になること"""
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
recipe["steps"] = [dict(recipe["steps"][0], count=1)]

requests.post(B + "/api/generate", json={"recipe": recipe, "mode": "step", "stepIndex": 0}).raise_for_status()
while requests.get(B + "/api/progress").json()["running"]:
    time.sleep(2)
p = requests.get(B + "/api/progress").json()
assert not p["error"], p["error"]

lr = requests.get(B + "/api/last_request").json()
print("BREAK in prompt:", "BREAK" in lr["payload"]["prompt"])
print("payload distilled_cfg_scale:", lr["payload"]["distilled_cfg_scale"])
last = lr["infotext"].splitlines()[-1]
keys = ("Shift", "CFG scale", "Steps", "Schedule type", "Size", "Clip skip", "spec_enable")
print("infotext:", ", ".join(s for s in last.split(", ") if s.startswith(keys)))
