from typing import List
from pathlib import Path
from base_tts import BaseTTS

class KittenTTSProcessor(BaseTTS):
	"""Text-to-Speech processor using KittenTTS with streaming support."""

	def __init__(self, stream_audio=False):
		super().__init__("Kitten", stream_audio=stream_audio)
		self.default_voice_index = 7
		self.voices = [  'expr-voice-2-m', 'expr-voice-2-f', 'expr-voice-3-m', 'expr-voice-3-f',  'expr-voice-4-m', 'expr-voice-4-f', 'expr-voice-5-m', 'expr-voice-5-f' ]
		print("Initialising Kitten...")
		from kittentts import KittenTTS
		print("Loading Modal...")
		self.pipeline = KittenTTS("KittenML/kitten-tts-nano-0.2")
		print("Model loaded successfully")

	def generate_audio_files(self, text: str, voice: str, speed: float, chunk_id: int = None):
		sentences = self.split_sentences(text)
		audio_files = []
		total_sentences = len(sentences)
		
		print(f"Processing {total_sentences} text sentences...")
		for i, sentence in enumerate(sentences):
			audio = self.pipeline.generate(sentence, voice=voice)
			if self.stream_audio:
				self.queue_audio_for_streaming(audio)
			if self.save_audio_file:
				chunk_file = self.generate_chunk_audio_file(audio, chunk_id if chunk_id else i)
				audio_files.append(chunk_file)
			print(f"Sentence {i + 1} processed -> {chunk_file.name} -> {sentence}")

		return audio_files