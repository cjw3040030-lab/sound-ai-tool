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

TEMP_DIR = Path("temp")
OUTPUT_DIR = Path("output")
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def change_speed(sound, speed=1.0):
    sound_with_altered_frame_rate = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return sound_with_altered_frame_rate.set_frame_rate(sound.frame_rate)


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
            "preview_url": f"http://127.0.0.1:8000/preview/{filename}"
        })

    return {"files": results}


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