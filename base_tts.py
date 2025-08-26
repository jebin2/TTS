
from pathlib import Path
import shutil
from pydub import AudioSegment
import os
import traceback
from functools import reduce
import threading
import queue
import time
import signal
import sys

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
		self.save_audio_file = True
		self.stream_audio = True
		
		# Streaming setup
		self.audio_queue = queue.Queue()
		self.is_streaming = False
		self.stream_thread = None
		self.sample_rate = 24000  # Default, can be overridden by subclasses
		
		# Emergency stop flag
		self.emergency_stop = False
		
		# Setup signal handler for Ctrl+C
		self.setup_signal_handler()

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

	# ===== EMERGENCY STOP METHODS =====
	
	def setup_signal_handler(self):
		"""Setup signal handler for Ctrl+C to stop everything immediately."""
		signal.signal(signal.SIGINT, self.emergency_stop_handler)
		signal.signal(signal.SIGTERM, self.emergency_stop_handler)

	def emergency_stop_handler(self, signum, frame):
		"""Handle Ctrl+C - stop everything immediately."""
		print("\n🛑 Emergency stop triggered! Stopping all operations...")
		self.emergency_stop = True
		
		# Stop audio playback immediately
		try:
			sd.stop()
		except:
			pass
		
		# Stop streaming
		self.force_stop_streaming()
		
		# Cleanup
		try:
			self.cleanup_temp_files()
		except:
			pass
		
		print("✅ Emergency stop completed. Exiting...")
		sys.exit(0)

	def force_stop_streaming(self):
		"""Force stop streaming immediately without waiting."""
		if self.is_streaming:
			self.is_streaming = False
			
			# Clear the queue
			try:
				while not self.audio_queue.empty():
					self.audio_queue.get_nowait()
			except:
				pass
			
			# Send poison pill
			try:
				self.audio_queue.put(None)
			except:
				pass
			
			print("🔇 Audio streaming force stopped")

	def check_emergency_stop(self):
		"""Check if emergency stop was triggered. Call this in loops."""
		if self.emergency_stop:
			raise KeyboardInterrupt("Emergency stop triggered")

	# ===== STREAMING METHODS =====
	
	def _audio_stream_worker(self):
		"""Worker thread that plays audio chunks as they arrive."""
		while self.is_streaming and not self.emergency_stop:
			try:
				audio_data = self.audio_queue.get(timeout=0.1)
				if audio_data is None or self.emergency_stop:  # Poison pill or emergency stop
					break
				
				# Play audio chunk
				sd.play(audio_data, samplerate=self.sample_rate)
				
				# Check for emergency stop while playing
				while sd.get_stream().active and not self.emergency_stop:
					time.sleep(0.01)
				
				if self.emergency_stop:
					sd.stop()
					break
				
			except queue.Empty:
				continue
			except Exception as e:
				if not self.emergency_stop:
					print(f"Audio playback error: {e}")
				break

	def start_streaming(self):
		"""Start the audio streaming thread."""
		try:
			import sounddevice as sd
			if not self.is_streaming and not self.emergency_stop:
				self.is_streaming = True
				self.stream_thread = threading.Thread(target=self._audio_stream_worker)
				self.stream_thread.daemon = True
				self.stream_thread.start()
				print("🔊 Audio streaming started")
		except:
			self.stream_audio = False
			print("🔇 No sounddevice.")
			pass

	def stop_streaming(self):
		"""Stop the audio streaming thread."""
		if self.is_streaming:
			self.is_streaming = False
			self.audio_queue.put(None)  # Poison pill
			if self.stream_thread:
				self.stream_thread.join(timeout=2)  # Don't wait forever
			print("🔇 Audio streaming stopped")

	def queue_audio_for_streaming(self, audio_data):
		"""Queue audio data for streaming playback."""
		if self.is_streaming and not self.emergency_stop:
			self.audio_queue.put(audio_data)

	def wait_for_streaming_complete(self):
		"""Wait for all queued audio to finish playing."""
		time.sleep(0.5)  # Small delay to ensure last chunk starts
		while not self.audio_queue.empty() and not self.emergency_stop:
			time.sleep(0.1)

	# ===== ABSTRACT METHODS =====
	
	def generate_audio_files(self, text: str, voice: str, speed: float):
		"""Generate audio files. To be implemented by subclasses."""
		raise NotImplementedError("Subclasses must implement generate_audio_files")

	# ===== MAIN METHODS =====

	def save_audio(self, args) -> bool:
		"""Generate and save complete audio file.
		
		Args:
			args: Arguments containing voice, speed, etc.
			
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
		
		# Generate audio files (with optional streaming)
		if self.stream_audio:
			self.start_streaming()

		audio_files = self.generate_audio_files(text, voice, speed)
		
		if not audio_files:
			raise ValueError("Error: No audio files generated")

		# Combine audio files
		success = self.combine_audio_files(audio_files)

		self.wait_for_streaming_complete()
		self.stop_streaming()
	
		return success