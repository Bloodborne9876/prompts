# -*- coding: utf-8 -*-
"""
シチュエーションエディター ローカルサーバー
  - editor.html の配信・データ/レシピのファイルIO
  - タグ補完API (a1111-sd-webui-tagcomplete の辞書を流用、日本語検索対応)
  - 生成エンジン (scripts/Invoke-Generate.ps1 と同一ロジック・出力互換)

起動: python server.py  (または start_editor.bat)
"""
import base64
import csv
import io
import json
import re
import threading
import time
import webbrowser
from pathlib import Path

import requests
import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
RECIPES_DIR = ROOT / "recipes"
OUTPUT_DIR = ROOT / "output"
TAGS_DIR = Path(r"C:\sd-webui-forge-neo\extensions\a1111-sd-webui-tagcomplete\tags")

DATA_FILES = {"settings", "characters", "situations", "faces"}
BAD_NAME = re.compile(r'[\\/:*?"<>|]|^\.|^$')

app = FastAPI(title="SituationEditor")


@app.middleware("http")
async def no_cache(request, call_next):
    # テスト生成は同名ファイルに上書きするため、/output と editor.html はキャッシュさせない
    resp = await call_next(request)
    if request.url.path.startswith("/output/") or request.url.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- ユーティリティ
def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings():
    return read_json(DATA_DIR / "settings.json")


def check_name(name: str) -> str:
    if BAD_NAME.search(name):
        raise HTTPException(400, f"不正な名前: {name}")
    return name


def join_tags(*parts):
    return ", ".join(p.strip() for p in parts if p and p.strip())


# ---------------------------------------------------------------- タグ辞書
TAGS = []  # [(name, count, aliases(list), jp(str))] count降順


def load_tags():
    # 辞書フォルダは settings.json の tagsDir で変更可能 (既定: forge-neo の tagcomplete)
    tags_dir = TAGS_DIR
    try:
        tags_dir = Path(load_settings().get("tagsDir", str(TAGS_DIR)))
    except Exception:
        pass
    jp_map = {}
    jp_file = tags_dir / "danbooru_translations_jp.csv"
    if jp_file.exists():
        with open(jp_file, encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    jp_map[row[0]] = row[1]
    entries = []
    tag_file = tags_dir / "danbooru.csv"
    if tag_file.exists():
        with open(tag_file, encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 3 and row[2].isdigit():
                    aliases = [a for a in row[3].split(",") if a] if len(row) >= 4 and row[3] else []
                    entries.append((row[0], int(row[2]), aliases, jp_map.get(row[0], "")))
    entries.sort(key=lambda e: -e[1])
    return entries


@app.get("/api/tags")
def api_tags(q: str = "", limit: int = 10):
    q = q.strip().lower()
    if not q:
        return []
    is_jp = any(ord(c) > 0x7F for c in q)
    qn = q.replace(" ", "_")
    pref, sub, alias, jp_hits = [], [], [], []
    for name, count, aliases, jp in TAGS:
        if is_jp:
            if jp and q in jp:
                jp_hits.append((name, count, jp))
        elif name.startswith(qn):
            pref.append((name, count, jp))
        elif qn in name:
            sub.append((name, count, jp))
        elif any(a.startswith(qn) for a in aliases):
            alias.append((name, count, jp))
        if len(pref) >= limit and len(jp_hits) >= limit:
            break
    hits = (jp_hits if is_jp else pref + sub + alias)[:limit]
    return [{"tag": t, "count": c, "jp": j} for t, c, j in hits]


# ---------------------------------------------------------------- ファイルIO API
@app.get("/api/data/{name}")
def get_data(name: str):
    if name not in DATA_FILES:
        raise HTTPException(404)
    return read_json(DATA_DIR / f"{name}.json")


@app.put("/api/data/{name}")
def put_data(name: str, body: dict = Body(...)):
    if name not in DATA_FILES:
        raise HTTPException(404)
    write_json(DATA_DIR / f"{name}.json", body)
    return {"ok": True}


@app.get("/api/recipes")
def list_recipes():
    out = {}
    for p in sorted(RECIPES_DIR.glob("*.json")):
        try:
            out[p.stem] = read_json(p)
        except Exception:
            pass
    return out


@app.put("/api/recipes/{name}")
def put_recipe(name: str, body: dict = Body(...)):
    check_name(name)
    write_json(RECIPES_DIR / f"{name}.json", body)
    return {"ok": True}


@app.delete("/api/recipes/{name}")
def delete_recipe(name: str):
    check_name(name)
    p = RECIPES_DIR / f"{name}.json"
    if p.exists():
        p.unlink()
    return {"ok": True}


# ---------------------------------------------------------------- 生成エンジン (Invoke-Generate.ps1 移植)
JOB = {
    "running": False, "mode": "", "title": "", "done": 0, "total": 0,
    "current": "", "eta_sec": None, "error": "", "images": [], "stop": False,
}
JOB_LOCK = threading.Lock()

# 直近にAPIへ送った生リクエスト (デバッグ用)。全リクエストは output\<title>\api_log.jsonl にも残す
LAST_REQUEST = {"time": None, "file": "", "payload": None, "infotext": ""}


def resolve_jobs(recipe, settings, characters, situations, faces, mode="full", step_index=None):
    """レシピ → ジョブ一覧 (PS版と同一の合成・seed・命名)"""
    char = next((c for c in characters if c["id"] == recipe.get("character")), None)
    if not char:
        raise HTTPException(400, f"キャラ '{recipe.get('character')}' が characters.json に見つかりません")
    face_map = {f["id"]: f.get("tags", "") for f in faces}

    neg_name = recipe.get("negative") or settings.get("defaultNegative", "")
    negative = settings.get("negativePresets", {}).get(neg_name, neg_name)

    situ_map = {s["id"]: s for s in situations}
    seed_val = int(recipe.get("seed", -1) if recipe.get("seed") is not None else -1)
    seed_mode = recipe.get("seedMode") or ("increment" if seed_val >= 0 else "random")

    jobs = []
    for idx, step in enumerate(recipe.get("steps", []), start=1):
        if mode == "step" and (step_index is None or idx != step_index + 1):
            continue
        situ = situ_map.get(step.get("situation"))
        if not situ:
            raise HTTPException(400, f"シチュエーション '{step.get('situation')}' が見つかりません (step {idx})")

        outfit_key = step.get("outfit") or situ.get("defaultOutfit", "normal")
        outfit = char.get("outfits", {}).get(outfit_key)
        if outfit is None:
            raise HTTPException(400, f"キャラ '{char['id']}' に服装 '{outfit_key}' がありません (step {idx})")

        size_key = step.get("size") or situ.get("defaultSize", "portrait")
        size = settings["sizes"].get(size_key)
        if not size:
            raise HTTPException(400, f"サイズプリセット '{size_key}' がありません (step {idx})")

        # 表情: step上書き ('inherit'/未指定=シチュエーション既定, 'none'=なし) > situ.defaultFace
        face_key = step.get("face") or "inherit"
        if face_key == "inherit":
            face_key = situ.get("defaultFace") or "none"
        face_tags = ""
        if face_key != "none":
            if face_key not in face_map:
                raise HTTPException(400, f"表情 '{face_key}' が faces.json にありません (step {idx})")
            face_tags = face_map[face_key]

        variations = situ.get("variations") or [""]
        var_mode = step.get("variationMode", "cycle")
        count = 1 if mode == "test" else max(1, int(step.get("count", 1)))

        neg_extra = situ.get("negativeExtra", "")
        job_negative = f"{negative}, {neg_extra}" if neg_extra else negative

        nn = f"{idx:02d}"
        for i in range(count):
            if var_mode == "random":
                import random
                variation = random.choice(variations)
            else:
                variation = variations[i % len(variations)]
            # useBreak=false (既定) は WebUI と同じ「ただの改行」区切り。
            # BREAK はCLIP系チャンク分割用で、Qwenエンコーダのモデルでは挙動が変わるため任意化
            blocks = [
                settings.get("qualityHeader", ""),
                join_tags(char.get("base", ""), outfit),
                join_tags(face_tags, situ.get("base", ""), variation, settings.get("commonTail", "")),
            ]
            sep = "\nBREAK\n" if settings.get("useBreak") else "\n"
            prompt = sep.join(b for b in blocks if b.strip())

            step_own = bool(step.get("seedMode") and step["seedMode"] != "inherit")
            m = step["seedMode"] if step_own else seed_mode
            base = int(step["seed"]) if (step_own and step.get("seed") is not None) else seed_val
            seed = -1
            if base >= 0:
                if m == "fixed":
                    seed = base
                elif m == "increment":
                    seed = base + (i if step_own else len(jobs))

            date_str = time.strftime("%Y%m%d")
            plan_file = f"{date_str}_{seed}.png" if seed >= 0 else f"{date_str}_random.png"
            jobs.append({
                "step": idx, "nn": nn, "situId": situ["id"], "seq": i + 1,
                "width": size["width"], "height": size["height"],
                "prompt": prompt, "negative": job_negative, "seed": seed,
                "file": plan_file,
                "folder": f"{nn}_{situ['id']}",
            })
    return jobs


def build_payload(job, recipe, settings):
    gen = settings["generation"]
    spec = gen.get("spectrum") or {
        "w": 0.25, "m": 6, "lam": 0.5, "window_size": 2, "flex_window": 0.0,
        "warmup_steps": 6, "stop_caching_step": 0.9, "enable_calibration": True,
        "calibration_strength": 0.5,
    }
    spec_enabled = bool(recipe.get("spectrum", True))   # 未指定は有効
    enable_hr = bool(recipe.get("hiresFix", gen.get("enable_hr", False)))
    return {
        "prompt": job["prompt"],
        "negative_prompt": job["negative"],
        "width": job["width"], "height": job["height"],
        "steps": gen["steps"], "cfg_scale": gen["cfg_scale"],
        # Forge Neo: distilled_cfg_scale = UIの「Shift」。未指定だとAPI既定3.5になりWebUIと絵が変わる
        "distilled_cfg_scale": gen.get("shift", 3.5),
        "hr_distilled_cfg": gen.get("shift", 3.5),
        "sampler_name": gen["sampler_name"], "scheduler": gen["scheduler"],
        "seed": job["seed"], "batch_size": 1, "n_iter": 1,
        "enable_hr": enable_hr, "hr_scale": gen["hr_scale"], "hr_upscaler": gen["hr_upscaler"],
        # Forge Neo: 未指定だと500、空配列だとVAE等のモジュールが外れる
        "hr_additional_modules": ["Use same choices"],
        "denoising_strength": gen["denoising_strength"],
        "override_settings": {"CLIP_stop_at_last_layers": gen["clip_skip"]},
        "override_settings_restore_afterwards": True,
        # Calibrated Spectrum: alwayson_scripts で明示しないとUI既定 (無効) になる
        "alwayson_scripts": {"Calibrated Spectrum": {"args": [
            spec_enabled, spec["w"], spec["m"], spec["lam"], spec["window_size"],
            spec["flex_window"], spec["warmup_steps"], spec["stop_caching_step"],
            bool(spec["enable_calibration"]), spec["calibration_strength"],
        ]}},
        "save_images": False, "send_images": True,
    }


def save_png(path: Path, b64: str, infotext: str):
    img = Image.open(io.BytesIO(base64.b64decode(b64)))
    meta = PngInfo()
    if infotext:
        meta.add_text("parameters", infotext)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", pnginfo=meta)


def run_generation(recipe, settings, jobs, mode, resume):
    title = recipe.get("title", "untitled")
    work_dir = OUTPUT_DIR / title
    if mode in ("test", "step"):
        work_dir = work_dir / "_test"
    work_dir.mkdir(parents=True, exist_ok=True)
    log_path = work_dir / "generation_log.jsonl"
    api = settings["apiUrl"].rstrip("/") + "/sdapi/v1/txt2img"

    def make_out_file(folder: str, seed: int) -> Path:
        """YYYYMMDD_<seed>.png、同名が存在する場合は YYYYMMDD_<seed>_N.png"""
        date_str = time.strftime("%Y%m%d")
        base = f"{date_str}_{seed}"
        p = work_dir / folder / f"{base}.png"
        n = 2
        while p.exists():
            p = work_dir / folder / f"{base}_{n}.png"
            n += 1
        return p

    t0 = time.time()
    generated = 0
    try:
        for j in jobs:
            if JOB["stop"]:
                break
            folder = j["folder"]
            JOB["current"] = folder

            # resume: seed が既知の場合のみ事前スキップ可能
            if resume and j["seed"] >= 0:
                candidate = make_out_file(folder, j["seed"])
                if candidate.exists():
                    JOB["done"] += 1
                    continue

            payload = build_payload(j, recipe, settings)
            LAST_REQUEST.update(time=time.strftime("%H:%M:%S"), file=folder,
                                payload=payload, infotext="")
            with open(work_dir / "api_log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"file": folder, "payload": payload},
                                   ensure_ascii=False) + "\n")
            resp = None
            for attempt in range(3):
                try:
                    r = requests.post(api, json=payload, timeout=900)
                    r.raise_for_status()
                    resp = r.json()
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    time.sleep(10 * (attempt + 1))

            info = json.loads(resp.get("info") or "{}")
            actual_seed = info.get("seed") if info.get("seed") is not None else j["seed"]
            infotext = (info.get("infotexts") or [""])[0]
            LAST_REQUEST["infotext"] = infotext

            out_file = make_out_file(folder, actual_seed)
            save_png(out_file, resp["images"][0], infotext)
            fname = out_file.name

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "file": f"{folder}/{fname}", "seed": actual_seed,
                    "prompt": j["prompt"],
                }, ensure_ascii=False) + "\n")

            generated += 1
            JOB["done"] += 1
            rel = out_file.relative_to(OUTPUT_DIR).as_posix()
            JOB["current"] = f"{folder}/{fname}"
            JOB["images"].append({"url": f"/output/{rel}", "seed": actual_seed, "label": f"{j['nn']}-{j['seq']} {j['situId']}"})
            if generated:
                avg = (time.time() - t0) / generated
                JOB["eta_sec"] = int(avg * (JOB["total"] - JOB["done"]))
    except Exception as e:
        JOB["error"] = str(e)
    finally:
        JOB["running"] = False
        JOB["current"] = ""
        JOB["eta_sec"] = None


@app.post("/api/generate")
def api_generate(body: dict = Body(...)):
    with JOB_LOCK:
        if JOB["running"]:
            raise HTTPException(409, "生成ジョブが実行中です")
        recipe = body.get("recipe")
        if not isinstance(recipe, dict):
            raise HTTPException(400, "recipe (レシピ本体) が必要です")
        mode = body.get("mode", "full")
        settings = load_settings()
        characters = read_json(DATA_DIR / "characters.json")["characters"]
        situations = read_json(DATA_DIR / "situations.json")["situations"]
        faces = read_json(DATA_DIR / "faces.json")["faces"]
        jobs = resolve_jobs(recipe, settings, characters, situations, faces, mode, body.get("stepIndex"))
        from_step = int(body.get("from", 1))
        jobs = [j for j in jobs if j["step"] >= from_step]
        if not jobs:
            raise HTTPException(400, "対象ジョブがありません")
        JOB.update(running=True, mode=mode, title=recipe.get("title", ""), done=0,
                   total=len(jobs), current="", eta_sec=None, error="", images=[], stop=False)
        threading.Thread(
            target=run_generation,
            args=(recipe, settings, jobs, mode, bool(body.get("resume"))),
            daemon=True,
        ).start()
        return {"ok": True, "total": len(jobs)}


@app.get("/api/progress")
def api_progress():
    return {k: v for k, v in JOB.items() if k != "stop"}


@app.post("/api/stop")
def api_stop():
    JOB["stop"] = True
    return {"ok": True}


@app.get("/api/last_request")
def api_last_request():
    return LAST_REQUEST


@app.get("/api/gallery")
def api_gallery():
    result = {}
    for folder in sorted(OUTPUT_DIR.iterdir()):
        if not folder.is_dir():
            continue
        entries = []
        for p in sorted(folder.rglob("*.png")):
            entries.append({
                "path": p.relative_to(OUTPUT_DIR).as_posix(),
                "mtime": int(p.stat().st_mtime),
            })
        if entries:
            result[folder.name] = entries
    return result


@app.post("/api/delete-images")
def api_delete_images(body: dict = Body(...)):
    paths = body.get("paths", [])
    deleted, errors = [], []
    for rel in paths:
        target = (OUTPUT_DIR / Path(rel)).resolve()
        try:
            if not str(target).startswith(str(OUTPUT_DIR.resolve())):
                raise ValueError("禁止パス")
            if target.exists():
                target.unlink()
            deleted.append(rel)
        except Exception as e:
            errors.append({"path": rel, "error": str(e)})
    return {"deleted": deleted, "errors": errors}


@app.get("/api/imageinfo")
def api_imageinfo(path: str):
    # path は output/ 以下の相対パス (例: "_free/20260621_081251/free_001.png")
    target = OUTPUT_DIR / Path(path)
    try:
        target = target.resolve()
        OUTPUT_DIR.resolve()
    except Exception:
        raise HTTPException(400, "パスが不正です")
    if not str(target).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(403, "アクセス禁止")
    if not target.exists():
        raise HTTPException(404, "ファイルが見つかりません")
    img = Image.open(target)
    info = img.info  # PNG テキストチャンク
    return {
        "parameters": info.get("parameters", ""),
        "comment": info.get("comment", ""),
    }


@app.post("/api/plan")
def api_plan(body: dict = Body(...)):
    recipe = body.get("recipe")
    if not isinstance(recipe, dict):
        raise HTTPException(400, "recipe が必要です")
    settings = load_settings()
    characters = read_json(DATA_DIR / "characters.json")["characters"]
    situations = read_json(DATA_DIR / "situations.json")["situations"]
    faces = read_json(DATA_DIR / "faces.json")["faces"]
    jobs = resolve_jobs(recipe, settings, characters, situations, faces, "full", None)
    lines = []
    for j in jobs:
        seed = j["seed"] if j["seed"] >= 0 else "random"
        lines.append(f"===== {j['folder']}\\{j['file']}  [{j['width']}x{j['height']}]  seed={seed}")
        lines.append(j["prompt"])
        lines.append("")
    return PlainTextResponse("\n".join(lines))


@app.post("/api/generate-free")
def api_generate_free(body: dict = Body(...)):
    with JOB_LOCK:
        if JOB["running"]:
            raise HTTPException(409, "生成ジョブが実行中です")
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            raise HTTPException(400, "prompt が必要です")
        settings = load_settings()
        neg_name = body.get("negative") or settings.get("defaultNegative", "")
        negative = settings.get("negativePresets", {}).get(neg_name, neg_name)
        default_size = next(iter(settings["sizes"].values()))
        size_key = body.get("size") or next(iter(settings["sizes"]))
        size = settings["sizes"].get(size_key, default_size)
        seed_val = int(body.get("seed", -1) if body.get("seed") is not None else -1)
        count = max(1, min(int(body.get("count", 1)), 50))
        date_str = time.strftime("%Y%m%d")
        jobs = []
        for i in range(count):
            seed = seed_val + i if seed_val >= 0 else -1
            plan_file = f"{date_str}_{seed}.png" if seed >= 0 else f"{date_str}_random.png"
            jobs.append({
                "step": 1, "nn": "01", "situId": "free", "seq": i + 1,
                "width": size["width"], "height": size["height"],
                "prompt": prompt, "negative": negative,
                "seed": seed,
                "file": plan_file,
                "folder": date_str,
            })
        recipe = {
            "title": "_free",
            "spectrum": bool(body.get("spectrum", True)),
            "hiresFix": bool(body.get("hiresFix", False)),
        }
        JOB.update(running=True, mode="free", title="_free", done=0,
                   total=len(jobs), current="", eta_sec=None, error="", images=[], stop=False)
        threading.Thread(
            target=run_generation,
            args=(recipe, settings, jobs, "free", False),
            daemon=True,
        ).start()
        return {"ok": True, "total": len(jobs)}


# ---------------------------------------------------------------- 静的配信
@app.get("/")
def index():
    return FileResponse(ROOT / "editor.html")


OUTPUT_DIR.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


# ---------------------------------------------------------------- 起動
def find_free_port(start: int, max_try: int = 20) -> int:
    import socket
    for p in range(start, start + max_try):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError(f"ポート {start}〜{start + max_try - 1} がすべて使用中です")


def main():
    global TAGS
    print("タグ辞書を読み込み中...")
    TAGS = load_tags()
    print(f"  タグ {len(TAGS)} 件")
    try:
        base_port = int(load_settings().get("editorPort", 7861))
    except Exception:
        base_port = 7861
    port = find_free_port(base_port)
    if port != base_port:
        print(f"  ポート {base_port} は使用中のため {port} で起動します")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
