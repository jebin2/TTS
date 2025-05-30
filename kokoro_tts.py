import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import soundfile as sf
import numpy as np
import sys
import json
import argparse
import shutil
import os
from pydub import AudioSegment
from functools import reduce

VOICE_NAMES = [
    'af',  # Default voice is a 50-50 mix of Bella & Sarah
    'af_bella', 'af_sarah', 'am_adam', 'am_michael',
    'bf_emma', 'bf_isabella', 'bm_george', 'bm_lewis',
    'af_nicole', 'af_sky', 'af_heart', 'am_echo'
]

OUTPUT_DIR = "output_audio"

class TTSProcessor:
    def __init__(self):
        print("Initialising Kokoro...")
        from kokoro import KPipeline
        print("Loading Modal...")
        self.pipeline = KPipeline(lang_code='a')
        print("Modal Loaded")

    def generate_audio(self, voicepack=VOICE_NAMES[8], max_len=450, speed=1):
        text = ""
        with open('content.txt', 'r') as file:
            text = file.read()

        return self.pipeline(
            text,
            voice=voicepack,
            speed=speed,
            split_pattern=r'\n+'
        )

    def __extract_number(self, filename):
        return int(filename.split("/")[-1].replace("output_audio_", "").replace(".wav", ""))

    def combine_audio(self):
        file_list = []
        for file in os.listdir(OUTPUT_DIR):
            full_path = os.path.join(OUTPUT_DIR, file)
            if os.path.isfile(full_path):
                file_list.append(full_path)
        
        file_list = sorted(file_list, key=self.__extract_number)

        combined = reduce(
            lambda acc, file_name: acc + AudioSegment.from_wav(file_name),
            file_list,
            AudioSegment.empty()
        )

        combined.export("output_audio.wav", format='wav')

    def save_audio(self, generator):
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)

        os.makedirs(OUTPUT_DIR)
        word_timestamps = []

        counter = 0
        for i, result in enumerate(generator):
            tokens = result.tokens
            audio = result.audio

            sf.write(f'{OUTPUT_DIR}/output_audio_{i}.wav', audio, 24000)

            temp_words = ""
            for word in tokens:
                temp_words += word.text
                word_timestamps.append({
                    "word": word.text,
                    "phonemes": word.phonemes,
                    "start_time": word.start_ts,
                    "end_time": word.end_ts
                })
            counter += 1
            print(f"Processed-{counter} {temp_words}")

        self.combine_audio()
        # Save timestamps to a JSON file
        with open('output_timestamps.json', 'w') as f:
            json.dump(word_timestamps, f, indent=4)

        print('Audio saved as output_audio.wav')
        print('Timestamps saved as output_timestamps.json')
        
        return True

def main(args, tts):
    try: speed = float(args.speed)
    except: speed = 1

    try: voice = VOICE_NAMES[int(args.voice)]
    except: voice = VOICE_NAMES[8]
    # except: voice = args.voice # testing voices

    print("Generating Audio...")
    generator = tts.generate_audio(speed=speed, voicepack=voice)

    tts.save_audio(generator)
    return True

def server_mode(args, tts):
    while True:
        try:
            input = sys.stdin.readline().strip()
            input = input.split("voice")

            try: args.speed = float(input[0])
            except: args.speed = 1

            try: args.voice = int(input[1])
            except: args.voice = 8
            # except: args.voice = input[0] # testing voices

            output_path = main(args, tts)

            print(output_path)
            sys.stdout.flush()
            
        except (EOFError, KeyboardInterrupt):
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-mode", action="store_true", help="Run in server mode")
    parser.add_argument("--speed", type=float, default=0.8, help="Speech speed")
    parser.add_argument("--voice", type=int, default=1, help="Sooech voice")
    args = parser.parse_args()

    tts = TTSProcessor()
    if args.server_mode:
        server_mode(args, tts)
    else:
        main(args, tts)