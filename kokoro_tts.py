import soundfile as sf
import json
from typing import List
from pathlib import Path
from base_tts import BaseTTS

class KokoroTTSProcessor(BaseTTS):
	"""Text-to-Speech processor using KokoroTTS."""

	def __init__(self):
		super().__init__("Kokoro")
		self.default_voice_index = 8
		self.default_speed = 1
		self.voices = [
			'af',  # Default voice is a 50-50 mix of Bella & Sarah
			'af_bella', 'af_sarah', 'am_adam', 'am_michael',
			'bf_emma', 'bf_isabella', 'bm_george', 'bm_lewis',
			'af_nicole', 'af_sky', 'af_heart', 'am_echo'
		]
		print("Initialising Kokoro...")
		from kokoro import KPipeline
		print("Loading Modal...")
		self.pipeline = KPipeline(lang_code='a')
		print("Model loaded successfully")

	def generate_chunk_audio_file(self, audio, chunk_index) -> Path:

		# Save chunk to numbered file
		chunk_file = self.temp_output_dir / f"chunk_{chunk_index:04d}.wav"
		sf.write(chunk_file, audio, 24000)
		
		return chunk_file

	def generate_audio_files(self, text: str, voicepack: str, speed: float) -> List[Path]:
		generator = self.pipeline(
			text,
			voice=voicepack,
			speed=speed,
			split_pattern=r'\n+'
		)
		audio_files = []
		word_timestamps = []
		
		print(f"Processing text chunks...")

		for i, result in enumerate(generator):
			tokens = result.tokens
			audio = result.audio

			chunk = ""
			for word in tokens:
				chunk += word.text
				word_timestamps.append({
					"word": word.text,
					"phonemes": word.phonemes,
					"start_time": word.start_ts,
					"end_time": word.end_ts
				})

			chunk_file = self.generate_chunk_audio_file(audio, i)
			audio_files.append(chunk_file)
			print(f"Chunk {i + 1} processed -> {chunk_file.name} -> {chunk}")

		# Save timestamps to a JSON file
		with open(self.final_output_timestamps, 'w') as f:
			json.dump(word_timestamps, f, indent=4)

		print(f'Timestamps saved as {self.final_output_timestamps}')
		
		return audio_files