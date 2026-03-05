from pathlib import Path
import random
import gradio as gr
from pydub import AudioSegment

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def change_speed(sound, speed=1.0):
    sound_with_altered_frame_rate = sound._spawn(
        sound.raw_data,
        overrides={"frame_rate": int(sound.frame_rate * speed)}
    )
    return sound_with_altered_frame_rate.set_frame_rate(sound.frame_rate)

def generate_variations(files, num_variations):

    results = []

    for file in files:

        sound = AudioSegment.from_file(file)

        for i in range(num_variations):

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

            output_file = OUTPUT_DIR / f"{Path(file).stem}_{i+1}.wav"

            new_sound.export(output_file, format="wav")

            results.append(str(output_file))

    return results


with gr.Blocks() as demo:

    gr.Markdown("## WAV Variation Generator")

    files = gr.File(file_types=[".wav"], file_count="multiple")

    num_variations = gr.Slider(1, 20, value=10, step=1, label="Variations")

    btn = gr.Button("Generate")

    output = gr.File()

    btn.click(
        generate_variations,
        inputs=[files, num_variations],
        outputs=output
    )

demo.launch()