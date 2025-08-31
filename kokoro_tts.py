import json
from typing import List
from pathlib import Path
from base_tts import BaseTTS

class KokoroTTSProcessor(BaseTTS):
	"""Text-to-Speech processor using KokoroTTS."""

	def __init__(self, stream_audio=False):
		super().__init__("Kokoro", stream_audio=stream_audio)
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
		self.pipeline = KPipeline(lang_code='a', device=self.device)
		print("Model loaded successfully")

	def generate_audio_files(self, text: str, voice: str, speed: float, chunk_id: int = None):
		generator = self.pipeline(
			text,
			voice=voice,
			speed=speed,
			split_pattern=r'\n+'
		)
		audio_files = []
		word_timestamps = []
		
		print(f"Processing text sentences...")

		for i, result in enumerate(generator):
			tokens = result.tokens
			audio = result.audio

			sentence = ""
			for word in tokens:
				sentence += word.text
				word_timestamps.append({
					"word": word.text,
					"phonemes": word.phonemes,
					"start_time": word.start_ts,
					"end_time": word.end_ts
				})

			if self.stream_audio:
				self.queue_audio_for_streaming(audio)
			if self.save_audio_file:
				chunk_file = self.generate_chunk_audio_file(audio, chunk_id if chunk_id else i)
				audio_files.append(chunk_file)
			print(f"Sentence {i + 1} processed -> {chunk_file.name} -> {sentence}")

		# Save timestamps to a JSON file
		with open(self.final_output_timestamps, 'w') as f:
			json.dump(word_timestamps, f, indent=4)

		print(f'Timestamps saved as {self.final_output_timestamps}')
		
		return audio_files