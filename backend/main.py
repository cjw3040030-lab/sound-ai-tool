from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from pydub import AudioSegment
from typing import Optional
import random
import shutil
import json
import time
import zipfile
import io
import re


app = FastAPI(title="Sound AI Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SAVED_DIR = BASE_DIR / "saved"
LAYER_DIR = BASE_DIR / "layers"
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"

for directory in [INPUT_DIR, OUTPUT_DIR, SAVED_DIR, LAYER_DIR, DATA_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = DATA_DIR / "history.json"
PRESETS_FILE = DATA_DIR / "layer_presets.json"
DISPLAY_NAMES_FILE = DATA_DIR / "display_names.json"


def ensure_json_file(path: Path, default_value):
    if not path.exists():
        path.write_text(
            json.dumps(default_value, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


ensure_json_file(HISTORY_FILE, [])
ensure_json_file(PRESETS_FILE, {})
ensure_json_file(DISPLAY_NAMES_FILE, {})


def load_json(path: Path, default_value):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_value


def save_json(path: Path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name


def unique_output_name(prefix: str, ext: str = ".wav") -> str:
    timestamp = int(time.time() * 1000)
    rand = random.randint(1000, 9999)
    return f"{prefix}_{timestamp}_{rand}{ext}"


def audio_file_response(filename: str, request: Request, file_type: str = "variation"):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    base_url = str(request.base_url).rstrip("/")
    return {
        "filename": filename,
        "preview_url": f"{base_url}/preview/{filename}",
        "type": file_type,
    }


def append_history(entry: dict):
    history = load_json(HISTORY_FILE, [])
    history.insert(0, entry)
    history = history[:300]
    save_json(HISTORY_FILE, history)


def change_speed(sound: AudioSegment, speed: float = 1.0) -> AudioSegment:
    altered = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return altered.set_frame_rate(sound.frame_rate)


def change_pitch(sound: AudioSegment, cents: float = 0.0) -> AudioSegment:
    altered = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * (2.0 ** (cents / 1200.0)))}
    )
    return altered.set_frame_rate(sound.frame_rate)


def get_layer_options():
    """
    폴더 구조 예시:
    backend/layers/
      impact/
        hit_01.wav
        hit_02.wav
      whoosh/
        whoosh_01.wav
    """
    options = {}
    if not LAYER_DIR.exists():
        return options

    for category_dir in sorted(LAYER_DIR.iterdir()):
        if category_dir.is_dir():
            wavs = sorted([p.stem for p in category_dir.glob("*.wav")])
            options[category_dir.name] = wavs
    return options


def find_layer_file(category: str, sub_type: str) -> Optional[Path]:
    category_dir = LAYER_DIR / category
    if not category_dir.exists():
        return None

    candidate = category_dir / f"{sub_type}.wav"
    if candidate.exists():
        return candidate

    return None


@app.get("/")
def root():
    return {"message": "Sound AI Tool backend running"}


@app.get("/layer-options")
def layer_options():
    return {"options": get_layer_options()}


@app.get("/preview/{filename}")
def preview_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="미리듣기 파일이 없습니다.")
    return FileResponse(file_path, media_type="audio/wav", filename=filename)


@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="다운로드 파일이 없습니다.")
    return FileResponse(file_path, media_type="audio/wav", filename=filename)


@app.post("/generate")
async def generate_variations(
    request: Request,
    file: UploadFile = File(...),
    num: int = Form(10)
):
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="WAV 파일만 업로드 가능합니다.")

    if num < 1 or num > 20:
        raise HTTPException(status_code=400, detail="생성 개수는 1~20 사이여야 합니다.")

    input_name = sanitize_filename(file.filename)
    input_path = INPUT_DIR / input_name

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        sound = AudioSegment.from_file(input_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"오디오 로드 실패: {str(e)}")

    generated_files = []

    for i in range(num):
        new_sound = sound

        speed = random.uniform(0.97, 1.03)
        new_sound = change_speed(new_sound, speed)

        pitch = random.uniform(-30, 30)
        new_sound = change_pitch(new_sound, pitch)

        gain = random.uniform(-2.0, 2.0)
        new_sound = new_sound.apply_gain(gain)

        if len(new_sound) > 300:
            trim_ms = random.randint(0, min(80, max(0, len(new_sound) // 12)))
            if trim_ms > 0 and len(new_sound) - trim_ms > 50:
                new_sound = new_sound[:-trim_ms]

        filename = unique_output_name(prefix=f"variation_{i+1}")
        out_path = OUTPUT_DIR / filename
        new_sound.export(out_path, format="wav")

        generated_files.append(audio_file_response(filename, request, "variation"))

    append_history({
        "action": "generate",
        "source_file": input_name,
        "count": len(generated_files),
        "timestamp": int(time.time()),
        "files": [item["filename"] for item in generated_files],
    })

    return {"files": generated_files}


@app.post("/save/{filename}")
def save_file(filename: str):
    source = OUTPUT_DIR / filename
    if not source.exists():
        raise HTTPException(status_code=404, detail="저장할 파일이 없습니다.")

    target = SAVED_DIR / filename
    shutil.copy2(source, target)

    append_history({
        "action": "save",
        "filename": filename,
        "saved_to": str(target),
        "timestamp": int(time.time()),
    })

    return {"message": "저장 완료", "filename": filename}


@app.delete("/delete/{filename}")
def delete_file(filename: str):
    target = OUTPUT_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="삭제할 파일이 없습니다.")

    target.unlink(missing_ok=True)

    append_history({
        "action": "delete",
        "filename": filename,
        "timestamp": int(time.time()),
    })

    return {"message": "삭제 완료", "filename": filename}


@app.post("/apply-layer")
async def apply_layer(
    request: Request,
    filename: str = Form(...),
    category: str = Form(...),
    sub_type: str = Form(...),
    layer_gain: float = Form(-8.0),
    position_ms: int = Form(0)
):
    base_file = OUTPUT_DIR / filename
    if not base_file.exists():
        raise HTTPException(status_code=404, detail="원본 결과 파일이 없습니다.")

    layer_file = find_layer_file(category, sub_type)
    if not layer_file or not layer_file.exists():
        raise HTTPException(status_code=404, detail="선택한 레이어 파일이 없습니다.")

    try:
        base_sound = AudioSegment.from_file(base_file)
        layer_sound = AudioSegment.from_file(layer_file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"오디오 로드 실패: {str(e)}")

    layer_sound = layer_sound.apply_gain(layer_gain)

    if position_ms < 0:
        position_ms = 0

    mixed = base_sound.overlay(layer_sound, position=position_ms)

    out_name = unique_output_name(prefix="layered")
    out_path = OUTPUT_DIR / out_name
    mixed.export(out_path, format="wav")

    append_history({
        "action": "apply_layer",
        "base_filename": filename,
        "category": category,
        "sub_type": sub_type,
        "layer_gain": layer_gain,
        "position_ms": position_ms,
        "result_filename": out_name,
        "timestamp": int(time.time()),
    })

    return audio_file_response(out_name, request, "layered")


@app.post("/rename")
async def rename_display_name(
    filename: str = Form(...),
    display_name: str = Form(...)
):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="이름을 바꿀 파일이 없습니다.")

    clean_name = display_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="표시 이름이 비어 있습니다.")

    display_names = load_json(DISPLAY_NAMES_FILE, {})
    display_names[filename] = clean_name
    save_json(DISPLAY_NAMES_FILE, display_names)

    append_history({
        "action": "rename",
        "filename": filename,
        "display_name": clean_name,
        "timestamp": int(time.time()),
    })

    return {
        "message": "표시 이름 변경 완료",
        "filename": filename,
        "display_name": clean_name,
    }


@app.get("/display-names")
def get_display_names():
    return {"display_names": load_json(DISPLAY_NAMES_FILE, {})}


@app.post("/bulk-download")
async def bulk_download(filenames: str = Form(...)):
    items = [name.strip() for name in filenames.split(",") if name.strip()]
    if not items:
        raise HTTPException(status_code=400, detail="다운로드할 파일이 없습니다.")

    memory_file = io.BytesIO()

    with zipfile.ZipFile(memory_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        added_count = 0
        for name in items:
            file_path = OUTPUT_DIR / name
            if file_path.exists():
                zf.write(file_path, arcname=name)
                added_count += 1

    if added_count == 0:
        raise HTTPException(status_code=404, detail="ZIP에 담을 파일이 없습니다.")

    memory_file.seek(0)

    temp_zip_name = unique_output_name("bulk_download", ".zip")
    temp_zip_path = TEMP_DIR / temp_zip_name
    with open(temp_zip_path, "wb") as f:
        f.write(memory_file.read())

    append_history({
        "action": "bulk_download",
        "filenames": items,
        "zip_name": temp_zip_name,
        "timestamp": int(time.time()),
    })

    return FileResponse(
        temp_zip_path,
        media_type="application/zip",
        filename="sound_ai_selected.zip"
    )


@app.get("/history")
def get_history(limit: int = 50):
    history = load_json(HISTORY_FILE, [])
    return {"history": history[:limit]}


@app.post("/presets")
async def save_preset(
    preset_name: str = Form(...),
    category: str = Form(...),
    sub_type: str = Form(...),
    layer_gain: float = Form(-8.0),
    position_ms: int = Form(0)
):
    preset_name = preset_name.strip()
    if not preset_name:
        raise HTTPException(status_code=400, detail="프리셋 이름이 비어 있습니다.")

    presets = load_json(PRESETS_FILE, {})
    presets[preset_name] = {
        "category": category,
        "sub_type": sub_type,
        "layer_gain": layer_gain,
        "position_ms": position_ms,
        "updated_at": int(time.time()),
    }
    save_json(PRESETS_FILE, presets)

    append_history({
        "action": "save_preset",
        "preset_name": preset_name,
        "category": category,
        "sub_type": sub_type,
        "layer_gain": layer_gain,
        "position_ms": position_ms,
        "timestamp": int(time.time()),
    })

    return {"message": "프리셋 저장 완료", "preset_name": preset_name}


@app.get("/presets")
def get_presets():
    return {"presets": load_json(PRESETS_FILE, {})}


@app.delete("/presets/{preset_name}")
def delete_preset(preset_name: str):
    presets = load_json(PRESETS_FILE, {})
    if preset_name not in presets:
        raise HTTPException(status_code=404, detail="프리셋이 없습니다.")

    del presets[preset_name]
    save_json(PRESETS_FILE, presets)

    append_history({
        "action": "delete_preset",
        "preset_name": preset_name,
        "timestamp": int(time.time()),
    })

    return {"message": "프리셋 삭제 완료", "preset_name": preset_name}


@app.get("/saved-files")
def saved_files():
    files = sorted(SAVED_DIR.glob("*.wav"))
    return {
        "files": [
            {
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": int(f.stat().st_mtime),
            }
            for f in files
        ]
    }