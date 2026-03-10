from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from uuid import uuid4
from pydub import AudioSegment
import random
import shutil

app = FastAPI(title="Sound AI Tool API")

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
SAVED_DIR = BASE_DIR / "saved"
LAYER_DIR = BASE_DIR / "layers"

for folder in [TEMP_DIR, OUTPUT_DIR, SAVED_DIR, LAYER_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

API_BASE = "http://127.0.0.1:8000"


# -----------------------------
# Utils
# -----------------------------
def audio_file_response(path: Path):
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


def change_speed(sound: AudioSegment, speed: float = 1.0) -> AudioSegment:
    altered = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return altered.set_frame_rate(sound.frame_rate)


def make_preview_item(path: Path, file_type: str = "variation") -> dict:
    return {
        "filename": path.name,
        "preview_url": f"{API_BASE}/preview/{path.name}",
        "type": file_type,
    }


def safe_load_audio(path: Path) -> AudioSegment:
    try:
        return AudioSegment.from_file(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"오디오 로드 실패: {str(e)}")


def export_wav(audio: AudioSegment, path: Path):
    try:
        audio.export(path, format="wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WAV 저장 실패: {str(e)}")


def normalize_gain_range(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def get_layer_candidates(category: str, sub_type: str) -> list[Path]:
    target_dir = LAYER_DIR / category / sub_type
    if not target_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"레이어 경로가 없습니다: {category}/{sub_type}"
        )

    files = []
    for ext in ("*.wav", "*.mp3", "*.ogg", "*.flac"):
        files.extend(target_dir.glob(ext))

    if not files:
        raise HTTPException(
            status_code=404,
            detail=f"레이어 파일이 없습니다: {category}/{sub_type}"
        )

    return files


def build_layer_options() -> dict:
    options = {}

    if not LAYER_DIR.exists():
        return options

    for category_dir in sorted([p for p in LAYER_DIR.iterdir() if p.is_dir()]):
        sub_types = []
        for sub_dir in sorted([p for p in category_dir.iterdir() if p.is_dir()]):
            has_audio = any(
                list(sub_dir.glob("*.wav")) +
                list(sub_dir.glob("*.mp3")) +
                list(sub_dir.glob("*.ogg")) +
                list(sub_dir.glob("*.flac"))
            )
            if has_audio:
                sub_types.append(sub_dir.name)

        if sub_types:
            options[category_dir.name] = sub_types

    return options


# -----------------------------
# Health check
# -----------------------------
@app.get("/")
def root():
    return {"message": "Sound AI Tool backend is running"}


# -----------------------------
# Preview / Download
# -----------------------------
@app.get("/preview/{filename}")
def preview_file(filename: str):
    path = OUTPUT_DIR / filename
    return audio_file_response(path)


@app.get("/download/{filename}")
def download_file(filename: str):
    path = OUTPUT_DIR / filename
    return audio_file_response(path)


# -----------------------------
# Generate variations
# -----------------------------
@app.post("/generate")
async def generate_variations(
    file: UploadFile = File(...),
    num: int = Form(10),
):
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="WAV 파일만 업로드 가능합니다.")

    num = max(1, min(20, num))

    temp_name = f"{uuid4().hex}_{file.filename}"
    temp_path = TEMP_DIR / temp_name

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    source = safe_load_audio(temp_path)
    generated_files = []

    try:
        for i in range(num):
            new_sound = source

            # speed
            speed = random.uniform(0.97, 1.03)
            new_sound = change_speed(new_sound, speed)

            # pitch (cent)
            pitch = random.uniform(-30, 30)
            new_sound = new_sound._spawn(
                new_sound.raw_data,
                overrides={
                    "frame_rate": int(
                        new_sound.frame_rate * (2.0 ** (pitch / 1200.0))
                    )
                },
            ).set_frame_rate(source.frame_rate)

            # gain
            gain = random.uniform(-2.0, 2.0)
            new_sound = new_sound + gain

            output_name = f"{Path(file.filename).stem}_var_{i+1}_{uuid4().hex[:8]}.wav"
            output_path = OUTPUT_DIR / output_name
            export_wav(new_sound, output_path)

            generated_files.append(make_preview_item(output_path, "variation"))

    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {"files": generated_files}


# -----------------------------
# Save output to saved folder
# -----------------------------
@app.post("/save/{filename}")
def save_file(filename: str):
    src = OUTPUT_DIR / filename
    if not src.exists():
        raise HTTPException(status_code=404, detail="저장할 파일이 없습니다.")

    dst = SAVED_DIR / filename
    shutil.copy2(src, dst)

    return {
        "message": "저장 완료",
        "filename": filename,
        "saved_path": str(dst),
    }


# -----------------------------
# Delete output file
# -----------------------------
@app.delete("/delete/{filename}")
def delete_file(filename: str):
    target = OUTPUT_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="삭제할 파일이 없습니다.")

    target.unlink()
    return {"message": "삭제 완료", "filename": filename}


# -----------------------------
# Layer options
# -----------------------------
@app.get("/layer-options")
def get_layer_options():
    return {"options": build_layer_options()}


# -----------------------------
# Apply layer
# -----------------------------
@app.post("/apply-layer")
def apply_layer(
    filename: str = Form(...),
    category: str = Form(...),
    sub_type: str = Form(...),
    layer_gain: float = Form(-8),
    position_ms: int = Form(0),
):
    base_path = OUTPUT_DIR / filename
    if not base_path.exists():
        raise HTTPException(status_code=404, detail="원본 파일을 찾을 수 없습니다.")

    position_ms = max(0, position_ms)
    layer_gain = normalize_gain_range(layer_gain, -60, 12)

    base_audio = safe_load_audio(base_path)

    candidates = get_layer_candidates(category, sub_type)
    layer_path = random.choice(candidates)
    layer_audio = safe_load_audio(layer_path)

    layer_audio = layer_audio + layer_gain

    mixed = base_audio.overlay(layer_audio, position=position_ms)

    output_name = f"{Path(filename).stem}_layered_{category}_{sub_type}_{uuid4().hex[:8]}.wav"
    output_path = OUTPUT_DIR / output_name
    export_wav(mixed, output_path)

    return make_preview_item(output_path, "layered")