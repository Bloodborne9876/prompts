# -*- coding: utf-8 -*-
"""situations.json の base に埋まっている __face/*__ wildcard を defaultFace へ移行する。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAP = {
    "__face/emberassed__": "haji_rand",
    "__face/mesu__": "mesu_rand",
    "__face/disgust__": "disgust_rand",
    "__face/fellatio_smile__": "fera_smile_rand",
    "__face/sex_smile__": "sex_smile_rand",
}

p = ROOT / "data" / "situations.json"
doc = json.loads(p.read_text(encoding="utf-8-sig"))
moved = 0
for s in doc["situations"]:
    base = s.get("base", "")
    for wc, face_id in MAP.items():
        if wc in base:
            base = base.replace(wc, "")
            base = re.sub(r"(\s*,\s*)+", ", ", base).strip().strip(",").strip()
            s["base"] = base
            if not s.get("defaultFace"):
                s["defaultFace"] = face_id
            moved += 1
    if "defaultFace" not in s:
        s["defaultFace"] = "none"
p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"base から defaultFace へ移行: {moved} 件 / 全 {len(doc['situations'])} 件に defaultFace を付与")
