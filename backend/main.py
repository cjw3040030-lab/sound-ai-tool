from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from uuid import uuid4
from pydub import AudioSegment
import random
import shutil
import numpy as np
from scipy.signal import hilbert

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


def make_preview_item(path: Path, file_type: str = "variation") -> dict:
    return {
        "filename": path.name,
        "preview_url": f"{API_BASE}/preview/{path.name}",
        "type": file_type,
    }


def normalize_gain_range(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def change_speed(sound: AudioSegment, speed: float = 1.0) -> AudioSegment:
    altered = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return altered.set_frame_rate(sound.frame_rate)


def apply_pitch_shift(
    sound: AudioSegment,
    pitch_cents: float,
    base_frame_rate: int
) -> AudioSegment:
    shifted = sound._spawn(
        sound.raw_data,
        overrides={
            "frame_rate": int(
                sound.frame_rate * (2.0 ** (pitch_cents / 1200.0))
            )
        },
    )
    return shifted.set_frame_rate(base_frame_rate)


def apply_frequency_shift(
    sound: AudioSegment,
    shift_hz: float
) -> AudioSegment:
    if abs(shift_hz) < 0.01:
        return sound

    sample_width = sound.sample_width
    frame_rate = sound.frame_rate
    channels = sound.channels

    samples = np.array(sound.get_array_of_samples())

    if channels == 2:
        samples = samples.reshape((-1, 2))

    if sample_width == 1:
        dtype = np.int8
        max_val = np.iinfo(np.int8).max
    elif sample_width == 2:
        dtype = np.int16
        max_val = np.iinfo(np.int16).max
    elif sample_width == 4:
        dtype = np.int32
        max_val = np.iinfo(np.int32).max
    else:
        raise HTTPException(
            status_code=500,
            detail=f"지원하지 않는 sample width: {sample_width}"
        )

    def shift_channel(channel_data: np.ndarray) -> np.ndarray:
        x = channel_data.astype(np.float32) / max_val

        analytic = hilbert(x)
        t = np.arange(len(x), dtype=np.float32) / frame_rate
        shifted = np.real(analytic * np.exp(2j * np.pi * shift_hz * t))

        shifted = np.clip(shifted, -1.0, 1.0)
        return (shifted * max_val).astype(dtype)

    if channels == 2:
        left = shift_channel(samples[:, 0])
        right = shift_channel(samples[:, 1])
        shifted_samples = np.column_stack((left, right)).reshape(-1)
    else:
        shifted_samples = shift_channel(samples)

    return sound._spawn(shifted_samples.tobytes())


def trim_with_random_offset(sound: AudioSegment, max_offset_ms: int = 80) -> AudioSegment:
    if len(sound) <= 100:
        return sound

    safe_max = min(max_offset_ms, max(0, len(sound) // 4))
    if safe_max <= 0:
        return sound

    offset = random.randint(0, safe_max)
    trimmed = sound[offset:]

    if len(trimmed) < 50:
        return sound

    return trimmed


def apply_random_fade(
    sound: AudioSegment,
    min_fade_ms: int = 5,
    max_fade_ms: int = 30
) -> AudioSegment:
    if len(sound) < 30:
        return sound

    fade_ms = random.randint(min_fade_ms, max_fade_ms)
    fade_ms = min(fade_ms, max(1, len(sound) // 3))

    return sound.fade_in(fade_ms).fade_out(fade_ms)


def get_variation_params():
    mode = random.choice(["light", "medium", "strong"])

    if mode == "light":
        return {
            "mode": mode,
            "speed": random.uniform(0.97, 1.03),
            "pitch": random.uniform(-40, 40),
            "freq_shift": random.uniform(-15.0, 15.0),
            "gain": random.uniform(-2.0, 2.0),
            "offset_ms": random.randint(0, 20),
        }

    if mode == "medium":
        return {
            "mode": mode,
            "speed": random.uniform(0.92, 1.08),
            "pitch": random.uniform(-100, 100),
            "freq_shift": random.uniform(-40.0, 40.0),
            "gain": random.uniform(-3.0, 3.0),
            "offset_ms": random.randint(0, 50),
        }

    return {
        "mode": mode,
        "speed": random.uniform(0.88, 1.12),
        "pitch": random.uniform(-180, 180),
        "freq_shift": random.uniform(-80.0, 80.0),
        "gain": random.uniform(-5.0, 5.0),
        "offset_ms": random.randint(0, 80),
    }


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
            params = get_variation_params()
            new_sound = source

            # 1. speed
            new_sound = change_speed(new_sound, params["speed"])

            # 2. pitch shift
            new_sound = apply_pitch_shift(
                new_sound,
                params["pitch"],
                source.frame_rate
            )

            # 3. frequency shift
            new_sound = apply_frequency_shift(
                new_sound,
                params["freq_shift"]
            )

            # 4. gain
            new_sound = new_sound + params["gain"]

            # 5. start offset
            new_sound = trim_with_random_offset(
                new_sound,
                max_offset_ms=params["offset_ms"]
            )

            # 6. fade in / out
            new_sound = apply_random_fade(new_sound)

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

    output_name = (
        f"{Path(filename).stem}_layered_{category}_{sub_type}_{uuid4().hex[:8]}.wav"
    )
    output_path = OUTPUT_DIR / output_name

    export_wav(mixed, output_path)

    return make_preview_item(output_path, "layered")