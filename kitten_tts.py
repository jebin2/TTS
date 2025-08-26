import soundfile as sf
from typing import List
from pathlib import Path
from base_tts import BaseTTS

class KittenTTSProcessor(BaseTTS):
	"""Text-to-Speech processor using KittenTTS with streaming support."""

	def __init__(self):
		super().__init__("Kitten")
		self.default_voice_index = 7
		self.voices = [  'expr-voice-2-m', 'expr-voice-2-f', 'expr-voice-3-m', 'expr-voice-3-f',  'expr-voice-4-m', 'expr-voice-4-f', 'expr-voice-5-m', 'expr-voice-5-f' ]
		print("Initialising Kitten...")
		from kittentts import KittenTTS
		print("Loading Modal...")
		self.pipeline = KittenTTS("KittenML/kitten-tts-nano-0.2")
		print("Model loaded successfully")
		
		# Set sample rate for streaming
		self.sample_rate = 24000

	def split_sentences(self, text, max_chars=300):
		words = text.split()
		chunks = []
		current = ""
		
		for word in words:
			if len(current + " " + word) <= max_chars:
				current += " " + word if current else word
			else:
				if current:
					chunks.append(current)
				current = word
		
		if current:
			chunks.append(current)
		
		return chunks

	def generate_chunk_audio_file(self, audio, chunk_index) -> Path:
		chunk_file = self.temp_output_dir / f"chunk_{chunk_index:04d}.wav"
		sf.write(chunk_file, audio, 24000)
		return chunk_file

	def generate_audio_files(self, text: str, voicepack: str, speed: float) -> List[Path]:
		"""Original method for file generation (non-streaming)."""
		sentences = self.split_sentences(text)
		audio_files = []

		for i, sentence in enumerate(sentences):
			audio = self.pipeline.generate(sentence, voice=voicepack)
			if self.stream_audio:
				self.queue_audio_for_streaming(audio)
			if self.save_audio_file:
				chunk_file = self.generate_chunk_audio_file(audio, i)
				audio_files.append(chunk_file)
			print(f"Chunk {i + 1} processed -> {chunk_file.name} -> {sentence}")

		return audio_files