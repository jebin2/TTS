
from pathlib import Path
import shutil
from pydub import AudioSegment
import os
import traceback
from functools import reduce

class BaseTTS:
	def __init__(self, type):
		os.environ["TORCH_USE_CUDA_DSA"] = "1"
		os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
		os.environ["HF_HUB_TIMEOUT"] = "120"
		self.content_file = Path("content.txt")
		self.final_output_audio = "output_audio.wav"
		self.final_output_timestamps = "output_timestamps.json"
		self.temp_output_dir = Path("temp_audio_chunks")
		self.default_voice_index = 8
		self.default_speed = 0.8
		self.voices = [
			None,
			'voices/Main-4.wav',
			'voices/Ellen-TTS-10.wav',
			'voices/kratos(ambient)_en.wav',
			'voices/20250329-audio-american-male.wav',
			'voices/Ellen13y TTS-14.wav',
			'voices/Simple guy.wav',
			None,
			'voices/bbc_news.wav',
			'voices/en_woman.wav',
			'voices/voice_preview_david castlemore - newsreader and educator.mp3',
		]
		self.type = type

	def cleanup_temp_files(self):
		"""Clean up temporary audio files."""
		if self.temp_output_dir.exists():
			shutil.rmtree(self.temp_output_dir)
		if os.path.exists(self.final_output_audio):
			os.remove(self.final_output_audio)
		if os.path.exists(self.final_output_timestamps):
			os.remove(self.final_output_timestamps)
		print("Temporary files cleaned up")

	def setup_output_directory(self):
		"""Create clean output directory for audio chunks."""
		if self.temp_output_dir.exists():
			shutil.rmtree(self.temp_output_dir)
		self.temp_output_dir.mkdir(exist_ok=True)

	def read_content_file(self):
		with open(self.content_file, 'r', encoding='utf-8') as file:
			return file.read().strip()

	def validate_voice_index(self, args) -> str:
		voice_index = self.default_voice_index
		try:
			voice_index = int(getattr(args, 'voice'))
			if not 0 <= voice_index < len(self.voices):
				print(f"Invalid voice index {voice_index}, using default voice")
				voice_index = self.default_voice_index
		except: voice_index = self.default_voice_index

		print(f"Speed Value: {self.voices[voice_index]}")
		return self.voices[voice_index]

	def validate_speed(self, args) -> float:
		speed_value = self.default_speed
		try:
			speed_value = float(getattr(args, 'speed'))
			if speed_value <= 0:
				print(f"Invalid speed {speed_value}, using default speed")
				speed_value = self.default_speed
		except: speed_value = self.default_speed

		print(f"Speed Value: {speed_value}")
		return speed_value

	def combine_audio_files(self, audio_files):
		"""Combine multiple audio files into one.
		
		Args:
			audio_files: List of audio file paths to combine
			
		Returns:
			True if successful, False otherwise
		"""
		if not audio_files:
			raise ValueError("No audio files to combine")

		print(f"Combining {len(audio_files)} audio files...")
		combined = reduce(
			lambda acc, file_name: acc + AudioSegment.from_wav(file_name),
			audio_files,
			AudioSegment.empty()
		)
		
		# Export combined audio
		combined.export(self.final_output_audio, format="wav")
		print(f"Combined audio saved as {self.final_output_audio}")
		return True

	def save_audio(self, args) -> bool:
		"""Generate and save complete audio file.
		
		Args:
			voice: Voice name to use
			speed: Speech speed
			cleanup: Whether to clean up temporary files after combining
			
		Returns:
			True if successful, False otherwise
		"""
		# Read content
		text = self.read_content_file()
		if not text:
			raise ValueError("Warning: Content file is empty")

		speed = self.validate_speed(args)
		voice = self.validate_voice_index(args)
		
		# Clean up temporary files
		self.cleanup_temp_files()
		
		# Setup output directory
		self.setup_output_directory()
		
		# Generate audio files
		audio_files = self.generate_audio_files(text, voice, speed)
		
		if not audio_files:
			raise ValueError("Error: No audio files generated")

		# Combine audio files
		success = self.combine_audio_files(audio_files)
		
		return success