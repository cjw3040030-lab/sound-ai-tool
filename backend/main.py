from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from pydub import AudioSegment
import random
import shutil
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
LAYER_DIR = BASE_DIR / "assets" / "layers"

TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LAYER_DIR.mkdir(parents=True, exist_ok=True)


def change_speed(sound, speed=1.0):
    sound_with_altered_frame_rate = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return sound_with_altered_frame_rate.set_frame_rate(sound.frame_rate)


def match_length(layer_sound: AudioSegment, target_length_ms: int) -> AudioSegment:
    if len(layer_sound) == target_length_ms:
        return layer_sound

    if len(layer_sound) > target_length_ms:
        return layer_sound[:target_length_ms]

    repeated = layer_sound
    while len(repeated) < target_length_ms:
        repeated += layer_sound

    return repeated[:target_length_ms]


def list_layer_options():
    result = {}

    if not LAYER_DIR.exists():
        return result

    for category_dir in LAYER_DIR.iterdir():
        if not category_dir.is_dir():
            continue

        sub_types = []
        for sub_dir in category_dir.iterdir():
            if sub_dir.is_dir():
                wav_files = list(sub_dir.glob("*.wav"))
                if wav_files:
                    sub_types.append(sub_dir.name)

        if sub_types:
            result[category_dir.name] = sub_types

    return result


def get_random_layer_file(category: str, sub_type: str):
    target_dir = LAYER_DIR / category / sub_type
    if not target_dir.exists() or not target_dir.is_dir():
        return None

    wav_files = list(target_dir.glob("*.wav"))
    if not wav_files:
        return None

    return random.choice(wav_files)


@app.get("/layer-options")
def get_layer_options():
    return {"options": list_layer_options()}


@app.post("/generate")
async def generate(file: UploadFile = File(...), num: int = Form(...)):
    sound = AudioSegment.from_file(file.file)
    results = []

    original_name = Path(file.filename).stem
    session_id = uuid.uuid4().hex[:8]

    for i in range(num):
        new_sound = sound

        speed = random.uniform(0.97, 1.03)
        new_sound = change_speed(new_sound, speed)

        pitch = random.uniform(-30, 30)
        new_sound = new_sound._spawn(
            new_sound.raw_data,
            overrides={
                "frame_rate": int(
                    new_sound.frame_rate * (2.0 ** (pitch / 1200.0))
                )
            },
        ).set_frame_rate(sound.frame_rate)

        gain = random.uniform(-2, 2)
        new_sound = new_sound + gain

        filename = f"{original_name}_{session_id}_variation_{i+1}.wav"
        output = TEMP_DIR / filename
        new_sound.export(output, format="wav")

        results.append({
            "filename": filename,
            "preview_url": f"http://127.0.0.1:8000/preview/{filename}",
            "type": "variation"
        })

    return {"files": results}


@app.post("/apply-layer")
async def apply_layer(
    filename: str = Form(...),
    category: str = Form(...),
    sub_type: str = Form(...),
    layer_gain: float = Form(-8.0),
    position_ms: int = Form(0),
):
    base_path = TEMP_DIR / filename

    if not base_path.exists():
        raise HTTPException(status_code=404, detail="기본 파일을 찾을 수 없습니다.")

    layer_file = get_random_layer_file(category, sub_type)
    if not layer_file:
        raise HTTPException(status_code=404, detail="레이어 소스를 찾을 수 없습니다.")

    base_sound = AudioSegment.from_file(base_path)
    layer_sound = AudioSegment.from_file(layer_file)

    layer_sound = match_length(layer_sound, len(base_sound))
    layer_sound = layer_sound + layer_gain

    mixed = base_sound.overlay(layer_sound, position=position_ms)

    new_filename = (
        f"{Path(filename).stem}_layered_{category}_{sub_type}_{uuid.uuid4().hex[:6]}.wav"
    )
    output_path = TEMP_DIR / new_filename
    mixed.export(output_path, format="wav")

    return {
        "filename": new_filename,
        "preview_url": f"http://127.0.0.1:8000/preview/{new_filename}",
        "type": "layered",
        "layer_category": category,
        "layer_sub_type": sub_type,
    }


@app.get("/preview/{filename}")
def preview_file(filename: str):
    file_path = TEMP_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="audio/wav", filename=filename)


@app.post("/save/{filename}")
def save_file(filename: str):
    temp_path = TEMP_DIR / filename
    if not temp_path.exists():
        raise HTTPException(status_code=404, detail="임시 파일을 찾을 수 없습니다.")

    output_path = OUTPUT_DIR / filename
    shutil.copy(temp_path, output_path)

    return {
        "message": "저장 완료",
        "saved_file": str(output_path)
    }


@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = TEMP_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, media_type="audio/wav", filename=filename)