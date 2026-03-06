from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydub import AudioSegment
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("output")
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

        output = OUTPUT_DIR / f"variation_{i+1}.wav"
        new_sound.export(output, format="wav")

        results.append(str(output))

    return {"files": results}