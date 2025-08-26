
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
		"""Initialize BaseTTS with environment settings and configuration."""
		# Environment setup
		os.environ["TORCH_USE_CUDA_DSA"] = "1"
		os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
		os.environ["HF_HUB_TIMEOUT"] = "120"
		
		# File paths and directories
		self.content_file = Path("content.txt")
		self.final_output_audio = "output_audio.wav"
		self.final_output_timestamps = "output_timestamps.json"
		self.temp_output_dir = Path("temp_audio_chunks")
		
		# Voice and speed configuration
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
		
		# General settings
		self.type = type
		self.save_audio_file = True
		self.stream_audio = True
		
		# Audio streaming configuration
		self.audio_queue = queue.Queue()
		self.is_streaming = False
		self.stream_thread = None
		self.sample_rate = 24000  # Default, can be overridden by subclasses
		
		# Text streaming configuration
		self.text_queue = queue.Queue()
		self.text_processing_thread = None
		self.is_text_streaming = False
		self.text_chunk_size = 10  # Number of words per chunk
		self.current_voice = None
		self.current_speed = None
		
		# Text buffering for streaming input
		self.temp_feed_words = []
		
		# Emergency stop control
		self.emergency_stop = False
		self.setup_signal_handler()

	# ===== UTILITY METHODS =====
	
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
		"""Read content from the content file."""
		with open(self.content_file, 'r', encoding='utf-8') as file:
			return file.read().strip()

	def validate_voice_index(self, args) -> str:
		"""Validate and return voice file path."""
		voice_index = self.default_voice_index
		try:
			voice_index = int(getattr(args, 'voice'))
			if not 0 <= voice_index < len(self.voices):
				print(f"Invalid voice index {voice_index}, using default voice")
				voice_index = self.default_voice_index
		except: 
			voice_index = self.default_voice_index

		print(f"Voice Value: {self.voices[voice_index]}")
		return self.voices[voice_index]

	def validate_speed(self, args) -> float:
		"""Validate and return speed value."""
		speed_value = self.default_speed
		try:
			speed_value = float(getattr(args, 'speed'))
			if speed_value <= 0:
				print(f"Invalid speed {speed_value}, using default speed")
				speed_value = self.default_speed
		except: 
			speed_value = self.default_speed

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

	def split_sentences(self, text, max_chars=300):
		"""Common split method for all frameworks. Override in subclasses if needed.
		
		Args:
			text (str): Text to split
			max_chars (int): Maximum characters per chunk
			
		Returns:
			list: List of text chunks
		"""
		words = text.split()
		chunks = []
		current = ""
		
		for word in words:
			test_chunk = current + " " + word if current else word
			if len(test_chunk) <= max_chars:
				current = test_chunk
			else:
				if current:
					chunks.append(current)
				current = word
		
		if current:
			chunks.append(current)
		
		return chunks

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
			import sounddevice as sd
			sd.stop()
		except:
			pass
		
		# Stop streaming
		self.force_stop_streaming()
		self.force_stop_text_streaming()
		
		# Cleanup
		try:
			self.cleanup_temp_files()
		except:
			pass
		
		print("✅ Emergency stop completed. Exiting...")
		sys.exit(0)

	def force_stop_streaming(self):
		"""Force stop audio streaming immediately without waiting."""
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

	def force_stop_text_streaming(self):
		"""Force stop text streaming immediately without waiting."""
		if self.is_text_streaming:
			self.is_text_streaming = False
			
			# Clear the text queue
			try:
				while not self.text_queue.empty():
					self.text_queue.get_nowait()
			except:
				pass
			
			# Send poison pill
			try:
				self.text_queue.put(None)
			except:
				pass
			
			print("📝 Text streaming force stopped")

	def check_emergency_stop(self):
		"""Check if emergency stop was triggered. Call this in loops."""
		if self.emergency_stop:
			raise KeyboardInterrupt("Emergency stop triggered")

	# ===== AUDIO STREAMING METHODS =====
	
	def _audio_stream_worker(self):
		"""Worker thread that plays audio chunks as they arrive."""
		while self.is_streaming and not self.emergency_stop:
			try:
				audio_data = self.audio_queue.get(timeout=0.1)
				if audio_data is None or self.emergency_stop:  # Poison pill or emergency stop
					break
				
				# Play audio chunk
				import sounddevice as sd
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

	def start_audio_streaming(self):
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
			print("🔇 No sounddevice available.")
			pass

	def stop_audio_streaming(self):
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

	def wait_for_audio_streaming_complete(self):
		"""Wait for all queued audio to finish playing."""
		time.sleep(0.5)  # Small delay to ensure last chunk starts
		while not self.audio_queue.empty() and not self.emergency_stop:
			time.sleep(0.1)

	# ===== TEXT STREAMING METHODS =====
	
	def _text_processing_worker(self):
		"""Worker thread that processes text chunks from the queue."""
		chunk_counter = 0
		
		while self.is_text_streaming and not self.emergency_stop:
			try:
				text_chunk = self.text_queue.get(timeout=0.1)
				if text_chunk is None or self.emergency_stop:  # Poison pill or emergency stop
					break
				
				if not text_chunk.strip():  # Skip empty chunks
					continue
				
				print(f"📝 Processing text chunk {chunk_counter + 1}: '{text_chunk[:50]}...'")
				
				# Generate audio for this text chunk
				try:
					audio_files = self.generate_audio_files(
						text_chunk, 
						self.current_voice, 
						self.current_speed,
						chunk_id=chunk_counter
					)
					
					if audio_files:
						print(f"✅ Generated audio for chunk {chunk_counter + 1}")
					else:
						print(f"⚠️ No audio generated for chunk {chunk_counter + 1}")
						
				except Exception as e:
					print(f"❌ Error processing chunk {chunk_counter + 1}: {e}")
				
				chunk_counter += 1
				
			except queue.Empty:
				continue
			except Exception as e:
				if not self.emergency_stop:
					print(f"Text processing error: {e}")
				break
		
		print(f"📝 Text processing completed. Processed {chunk_counter} chunks.")

	def start_text_streaming(self, voice, speed):
		"""Start the text processing streaming thread."""
		if not self.is_text_streaming and not self.emergency_stop:
			self.current_voice = voice
			self.current_speed = speed
			self.is_text_streaming = True
			self.text_processing_thread = threading.Thread(target=self._text_processing_worker)
			self.text_processing_thread.daemon = True
			self.text_processing_thread.start()
			print("📝 Text streaming started")

	def stop_text_streaming(self):
		"""Stop the text processing streaming thread."""
		if self.is_text_streaming:
			self.is_text_streaming = False
			self.text_queue.put(None)  # Poison pill
			if self.text_processing_thread:
				self.text_processing_thread.join(timeout=5)  # Wait a bit longer for text processing
			print("📝 Text streaming stopped")

	def add_text_chunk(self, text_chunk):
		"""Add a text chunk to the processing queue.
		
		Args:
			text_chunk (str): Text chunk to process
		"""
		if self.is_text_streaming and not self.emergency_stop and text_chunk.strip():
			# Ensure chunk ends with punctuation for better TTS pronunciation
			cleaned_chunk = text_chunk.strip()
			if not any(cleaned_chunk.endswith(p) for p in ['.', '!', '?', ':', ';', ',']):
				cleaned_chunk += '.'  # Add period if no punctuation
			
			self.text_queue.put(cleaned_chunk)
			print(f"📝 Queued text chunk: '{cleaned_chunk[:30]}...'")
		else:
			if not self.is_text_streaming:
				print("⚠️ Text streaming not started. Call start_text_streaming() first.")

	def add_text_by_words(self, text, words_per_chunk=None):
		"""Split text into word chunks and add to queue.
		
		Args:
			text (str): Full text to split and queue
			words_per_chunk (int, optional): Number of words per chunk. Uses self.text_chunk_size if None.
		"""
		if words_per_chunk is None:
			words_per_chunk = self.text_chunk_size
		
		words = text.split()
		
		for i in range(0, len(words), words_per_chunk):
			chunk = ' '.join(words[i:i + words_per_chunk])
			self.add_text_chunk(chunk)
			
		print(f"📝 Split text into {(len(words) + words_per_chunk - 1) // words_per_chunk} chunks of {words_per_chunk} words each")

	def wait_for_text_processing_complete(self):
		"""Wait for all queued text chunks to be processed."""
		print("📝 Waiting for text processing to complete...")
		while not self.text_queue.empty() and not self.emergency_stop:
			time.sleep(0.1)
		time.sleep(1)  # Extra time for last chunk to process
		print("📝 Text processing queue empty")

	# ===== STREAMING TEXT INPUT METHODS =====

	def feed_text_chunk(self, text_chunk):
		"""Feed a single text chunk for processing with smart buffering.
		
		Args:
			text_chunk (str): Text chunk to process
		"""
		# Add new words to the buffer
		self.temp_feed_words.extend(text_chunk.split())
		
		# Combine all buffered words and split into sentences/chunks
		all_words = " ".join(self.temp_feed_words)
		sentences = self.split_sentences(all_words)
		total_sentences = len(sentences)
		
		# Process all complete sentences except the last one (which might be incomplete)
		for i, sentence in enumerate(sentences):
			if i + 1 != total_sentences:  # Not the last sentence
				print(f"📝 Feeding chunk: {sentence}")
				self.add_text_chunk(sentence)
		
		# Keep the last sentence in buffer (might be incomplete)
		self.temp_feed_words = sentences[-1].split() if sentences else []

	def flush_remaining_words(self):
		"""Flush any remaining words in the buffer. Call this when done feeding text."""
		if self.temp_feed_words:
			chunk_text = " ".join(self.temp_feed_words)
			print(f"📝 Flushing final chunk: {chunk_text}")
			self.add_text_chunk(chunk_text)
			self.temp_feed_words = []

	# ===== HIGH-LEVEL STREAMING METHODS =====

	def stream_real_time_text(self, args):
		"""Initialize streaming for real-time text input.
		
		Args:
			args: Arguments containing voice, speed, etc.
		"""
		speed = self.validate_speed(args)
		voice = self.validate_voice_index(args)
		
		# Setup directories
		self.cleanup_temp_files()
		self.setup_output_directory()
		
		# Start both streaming systems
		if self.stream_audio:
			self.start_audio_streaming()
		
		self.start_text_streaming(voice, speed)
		
		print("🚀 Real-time text streaming initialized!")
		print("📝 Use feed_text_chunk() to add text incrementally")
		print("📝 Use add_text_chunk() to add individual chunks")
		print("📝 Use add_text_by_words() to split and add text automatically")
		print("🛑 Use stop_all_streaming() when done")

	def stop_all_streaming(self):
		"""Stop all streaming operations and cleanup."""
		print("🛑 Stopping all streaming operations...")
		
		# Flush any remaining words first
		self.flush_remaining_words()
		
		# Wait for queues to empty
		self.wait_for_text_processing_complete()
		self.wait_for_audio_streaming_complete()
		
		# Stop streaming threads
		self.stop_text_streaming()
		self.stop_audio_streaming()
		
		print("✅ All streaming operations stopped")

	# ===== BACKWARD COMPATIBILITY METHODS =====

	def start_streaming(self):
		"""Start audio streaming (backward compatibility)."""
		self.start_audio_streaming()

	def stop_streaming(self):
		"""Stop audio streaming (backward compatibility)."""
		self.stop_audio_streaming()

	def wait_for_streaming_complete(self):
		"""Wait for audio streaming to complete (backward compatibility)."""
		self.wait_for_audio_streaming_complete()

	# ===== ABSTRACT METHODS =====
	
	def generate_audio_files(self, text: str, voice: str, speed: float, chunk_id: int = None):
		"""Generate audio files. To be implemented by subclasses.
		
		Args:
			text (str): Text to convert to audio
			voice (str): Voice file path
			speed (float): Speed multiplier
			chunk_id (int, optional): Unique identifier for this chunk (for streaming)
		"""
		raise NotImplementedError("Subclasses must implement generate_audio_files")

	# ===== MAIN METHODS =====

	def save_audio(self, args) -> bool:
		"""Generate and save complete audio file (batch mode).
		
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
			self.start_audio_streaming()

		audio_files = self.generate_audio_files(text, voice, speed)
		
		if not audio_files:
			raise ValueError("Error: No audio files generated")

		# Combine audio files
		success = self.combine_audio_files(audio_files)

		self.wait_for_audio_streaming_complete()
		self.stop_audio_streaming()
	
		return success