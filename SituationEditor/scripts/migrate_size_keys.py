# -*- coding: utf-8 -*-
"""サイズプリセットのキー名変更に追随して situations/recipes の参照を一括移行する。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OLD = sys.argv[1] if len(sys.argv) > 1 else "portrait"
NEW = sys.argv[2] if len(sys.argv) > 2 else "portrait_v"
fixed = 0

p = ROOT / "data" / "situations.json"
doc = json.loads(p.read_text(encoding="utf-8-sig"))
for s in doc["situations"]:
    if s.get("defaultSize") == OLD:
        s["defaultSize"] = NEW
        fixed += 1
p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

for rp in (ROOT / "recipes").glob("*.json"):
    r = json.loads(rp.read_text(encoding="utf-8-sig"))
    changed = False
    for st in r.get("steps", []):
        if st.get("size") == OLD:
            st["size"] = NEW
            changed = True
            fixed += 1
    if changed:
        rp.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"{OLD} -> {NEW}: {fixed} 箇所を移行")
