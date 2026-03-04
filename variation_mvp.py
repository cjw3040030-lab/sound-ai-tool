from pathlib import Path
import random
from pydub import AudioSegment

INPUT = Path("input/source.wav")
OUTPUT_DIR = Path("output")

OUTPUT_DIR.mkdir(exist_ok=True)

NUM_VARIATIONS = 10

def change_speed(sound, speed=1.0):
    sound_with_altered_frame_rate = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return sound_with_altered_frame_rate.set_frame_rate(sound.frame_rate)

sound = AudioSegment.from_file(INPUT)

for i in range(NUM_VARIATIONS):

    new_sound = sound

    speed = random.uniform(0.97, 1.03)
    new_sound = change_speed(new_sound, speed)

    pitch = random.uniform(-30, 30)
    new_sound = new_sound._spawn(
        new_sound.raw_data,
        overrides={"frame_rate": int(new_sound.frame_rate * (2.0 ** (pitch / 1200.0)))}
    ).set_frame_rate(sound.frame_rate)

    gain = random.uniform(-2, 2)
    new_sound = new_sound.apply_gain(gain)

    output_file = OUTPUT_DIR / f"variation_{i}.wav"

    new_sound.export(output_file, format="wav")

    print("Saved:", output_file)