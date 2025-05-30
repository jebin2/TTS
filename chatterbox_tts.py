import sys
import argparse
import shutil
import os
from pathlib import Path
from typing import List, Optional
import spacy
from pydub import AudioSegment
from chatterbox.tts import ChatterboxTTS
import torchaudio as ta

import logging
logging.getLogger().setLevel(logging.ERROR)
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


# Constants
CONTENT_FILE = Path("content.txt")
COMBINED_OUTPUT = "output_audio.wav"
OUTPUT_DIR = Path("temp_audio_chunks")
DEFAULT_VOICE_INDEX = 5
DEFAULT_SPEED = 0.8

VOICE_NAMES = [
	None,
    'assets/Main-4.wav',
    'assets/Ellen-TTS-10.wav',
    'assets/kratos(ambient)_en.wav',
	'assets/20250329-audio-american-female.wav',
	'assets/20250329-audio-american-male.wav'
]

class TTSProcessor:
	"""Text-to-Speech processor using ChatterboxTTS."""
	
	def __init__(self, device: str = "cuda"):
		"""Initialize the TTS processor.
		
		Args:
			device: Device to run the model on (cuda/cpu)
		"""
		print("Initializing Chatterbox...")
		self.model = ChatterboxTTS.from_pretrained(device=device)
		self.nlp = spacy.load("en_core_web_sm")
		print("Model loaded successfully")

	def tokenize_sentences(self, text: str) -> List[str]:
		"""Split text into sentences using spaCy.
		
		Args:
			text: Input text to tokenize
			
		Returns:
			List of sentence strings
		"""
		doc = self.nlp(text)
		return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

	def norm_and_token_count(self, text):
		"""Get normalized text and token count.
		
		Args:
			text: Input text to normalize and count tokens
			
		Returns:
			Tuple of (normalized_text, token_count)
		"""
		try:
			from chatterbox.tts import punc_norm
			normalized = punc_norm(text)
			tokens = self.model.tokenizer.text_to_tokens(normalized)
			return normalized, tokens.shape[1]
		except Exception as e:
			print(f"Error in tokenization: {e}")
			# Fallback: estimate tokens as roughly 1 token per 4 characters
			return text, len(text) // 4

	def split_text_by_tokens(self, text, max_tokens=500):
		"""Split text into chunks based on token count.
		
		Args:
			text: Input text to split
			max_tokens: Maximum tokens per chunk
			
		Returns:
			List of text chunks
		"""
		sentences = self.tokenize_sentences(text)
		chunks = []
		current = ""

		for sentence in sentences:
			# Check if sentence alone exceeds max tokens
			_, sentence_tokens = self.norm_and_token_count(sentence)
			if sentence_tokens > max_tokens:
				# If current chunk has content, save it first
				if current:
					chunks.append(current.strip())
					current = ""
				
				# Split long sentence by words if it's too long
				words = sentence.split()
				temp_chunk = ""
				
				for word in words:
					test_chunk = (temp_chunk + " " + word).strip() if temp_chunk else word
					_, test_tokens = self.norm_and_token_count(test_chunk)
					
					if test_tokens <= max_tokens:
						temp_chunk = test_chunk
					else:
						if temp_chunk:
							chunks.append(temp_chunk.strip())
						temp_chunk = word
				
				if temp_chunk:
					current = temp_chunk.strip()
				continue
			
			# Try adding sentence to current chunk
			candidate = (current + " " + sentence).strip() if current else sentence.strip()
			_, token_count = self.norm_and_token_count(candidate)
			
			if token_count <= max_tokens:
				current = candidate
			else:
				# Current chunk is full, save it and start new one
				if current:
					chunks.append(current.strip())
				current = sentence.strip()
		
		# Don't forget the last chunk
		if current:
			chunks.append(current.strip())
			
		return chunks

	def read_content_file(self, filepath: Path = CONTENT_FILE) -> str:
		"""Read content from file.
		
		Args:
			filepath: Path to content file
			
		Returns:
			File content as string
			
		Raises:
			FileNotFoundError: If content file doesn't exist
		"""
		try:
			with open(filepath, 'r', encoding='utf-8') as file:
				return file.read().strip()
		except FileNotFoundError:
			raise FileNotFoundError(f"Content file not found: {filepath}")

	def setup_output_directory(self):
		"""Create clean output directory for audio chunks."""
		if OUTPUT_DIR.exists():
			shutil.rmtree(OUTPUT_DIR)
		OUTPUT_DIR.mkdir(exist_ok=True)

	def generate_chunk_audio_file(self, chunk: str, chunk_index: int, voicepack: str, speed: float) -> Path:
		"""Generate audio file for a single text chunk.
		
		Args:
			chunk: Text chunk to convert to speech
			chunk_index: Index of the chunk for filename
			voicepack: Voice to use for generation
			speed: Speech speed
			
		Returns:
			Path to generated audio file
		"""
		wav = self.model.generate(
			chunk,
			audio_prompt_path=voicepack,
			temperature=speed
		)
		print("Saving...")
		
		# Save chunk to numbered file
		chunk_file = OUTPUT_DIR / f"chunk_{chunk_index:04d}.wav"
		ta.save(str(chunk_file), wav, self.model.sr)
		
		return chunk_file

	def generate_audio_files(self, text: str, voicepack: str, speed: float) -> List[Path]:
		"""Generate audio files for all text chunks.
		
		Args:
			text: Full text to convert
			voicepack: Voice to use
			speed: Speech speed
			
		Returns:
			List of generated audio file paths
		"""
		chunks = self.split_text_by_tokens(text)
		audio_files = []
		
		print(f"Processing {len(chunks)} text chunks...")
		
		for i, chunk in enumerate(chunks):
			try:
				chunk_file = self.generate_chunk_audio_file(chunk, i, voicepack, speed)
				audio_files.append(chunk_file)
				print(f"Chunk {i + 1}/{len(chunks)} processed -> {chunk_file.name}")
			except Exception as e:
				print(f"Error processing chunk {i + 1}: {e}")
				continue
				
		return audio_files

	def combine_audio_files(self, audio_files: List[Path]) -> bool:
		"""Combine multiple audio files into one.
		
		Args:
			audio_files: List of audio file paths to combine
			
		Returns:
			True if successful, False otherwise
		"""
		if not audio_files:
			print("No audio files to combine")
			return False
			
		try:
			print(f"Combining {len(audio_files)} audio files...")
			combined = AudioSegment.empty()
			
			for i, audio_file in enumerate(audio_files):
				if audio_file.exists():
					segment = AudioSegment.from_wav(str(audio_file))
					combined += segment
					print(f"Added {audio_file.name} ({i + 1}/{len(audio_files)})")
				else:
					print(f"Warning: {audio_file} does not exist, skipping")
			
			# Export combined audio
			combined.export(COMBINED_OUTPUT, format="wav")
			print(f"Combined audio saved as {COMBINED_OUTPUT}")
			return True
			
		except Exception as e:
			print(f"Error combining audio files: {e}")
			return False

	def cleanup_temp_files(self):
		"""Clean up temporary audio files."""
		try:
			if OUTPUT_DIR.exists():
				shutil.rmtree(OUTPUT_DIR)
				print("Temporary files cleaned up")
			os.remove(COMBINED_OUTPUT)
		except Exception as e:
			print(f"Warning: Could not clean up temporary files: {e}")

	def save_audio(self, voice: str, speed: float, cleanup: bool = True) -> bool:
		"""Generate and save complete audio file.
		
		Args:
			voice: Voice name to use
			speed: Speech speed
			cleanup: Whether to clean up temporary files after combining
			
		Returns:
			True if successful, False otherwise
		"""
		try:
			# Read content
			text = self.read_content_file()
			if not text:
				print("Warning: Content file is empty")
				return False
			
			# Clean up temporary files if requested
			if cleanup:
				self.cleanup_temp_files()
			
			# Setup output directory
			self.setup_output_directory()
			
			# Generate audio files
			audio_files = self.generate_audio_files(text, voice, speed)
			
			if not audio_files:
				print("Error: No audio files generated")
				return False
			
			# Combine audio files
			success = self.combine_audio_files(audio_files)
			
			return success
			
		except Exception as e:
			print(f"Error in save_audio: {e}")
			return False

def validate_voice_index(voice_index: int) -> str:
	"""Validate and return voice name from index.
	
	Args:
		voice_index: Index into VOICE_NAMES list
		
	Returns:
		Valid voice name
	"""
	if 0 <= voice_index < len(VOICE_NAMES):
		return VOICE_NAMES[voice_index]
	else:
		print(f"Invalid voice index {voice_index}, using default voice")
		return VOICE_NAMES[DEFAULT_VOICE_INDEX]  # Default fallback

def validate_speed(speed_value: float) -> float:
	"""Validate speed parameter.
	
	Args:
		speed_value: Speed value to validate
		
	Returns:
		Valid speed value
	"""
	if speed_value <= 0:
		print(f"Invalid speed {speed_value}, using default speed")
		return DEFAULT_SPEED
	return speed_value

def process_audio(args, tts: TTSProcessor) -> bool:
	"""Process audio with given arguments.
	
	Args:
		args: Command line arguments
		tts: TTS processor instance
		
	Returns:
		True if successful
	"""
	speed = validate_speed(getattr(args, 'speed', DEFAULT_SPEED))
	voice = validate_voice_index(getattr(args, 'voice', DEFAULT_VOICE_INDEX))
	
	print(f"Using voice: {voice}, speed: {speed}")
	return tts.save_audio(voice, speed)

def server_mode(tts: TTSProcessor):
	"""Run in server mode, processing stdin commands.
	
	Args:
		tts: TTS processor instance
	"""
	print("Entering server mode. Format: 'speed voice_index' or Ctrl+C to exit")
	
	while True:
		try:
			line = sys.stdin.readline().strip()
			if not line:  # EOF
				break
				
			# Parse input: "speed voice_index"
			parts = line.split()
			
			# Default values
			speed = DEFAULT_SPEED
			voice_index = DEFAULT_VOICE_INDEX
			
			# Parse speed
			if len(parts) >= 1:
				try:
					speed = float(parts[0])
				except ValueError:
					print(f"Invalid speed value: {parts[0]}, using default")
					speed = DEFAULT_SPEED
			
			# Parse voice index  
			if len(parts) >= 2:
				try:
					voice_index = int(parts[1])
				except ValueError:
					print(f"Invalid voice index: {parts[1]}, using default")
					voice_index = DEFAULT_VOICE_INDEX
			
			speed = validate_speed(speed)
			voice = validate_voice_index(voice_index)
			
			print(f"Processing with speed: {speed}, voice: {voice}")
			
			# Process audio
			success = tts.save_audio(voice, speed)
			print(f"Processing {'successful' if success else 'failed'}")
			sys.stdout.flush()
			
		except (EOFError, KeyboardInterrupt):
			print("\nExiting server mode")
			break
		except Exception as e:
			print(f"Error in server mode: {e}")

def main():
	"""Main entry point."""
	parser = argparse.ArgumentParser(
		description="Text-to-Speech processor using ChatterboxTTS"
	)
	parser.add_argument(
		"--server-mode", 
		action="store_true", 
		help="Run in server mode (read commands from stdin)"
	)
	parser.add_argument(
		"--speed", 
		type=float, 
		default=DEFAULT_SPEED,
		help=f"Speech speed (default: {DEFAULT_SPEED})"
	)
	parser.add_argument(
		"--voice", 
		type=int, 
		default=DEFAULT_VOICE_INDEX,
		help=f"Voice index (0-{len(VOICE_NAMES)-1}, default: {DEFAULT_VOICE_INDEX})"
	)
	parser.add_argument(
		"--device",
		type=str,
		default="cuda",
		help="Device to run model on (cuda/cpu, default: cuda)"
	)
	parser.add_argument(
		"--keep-chunks",
		action="store_true",
		help="Keep temporary audio chunk files (don't cleanup)"
	)
	
	args = parser.parse_args()
	
	# Initialize TTS processor
	try:
		tts = TTSProcessor(device=args.device)
	except Exception as e:
		print(f"Failed to initialize TTS processor: {e}")
		return 1
	
	# Run in appropriate mode
	if args.server_mode:
		server_mode(tts)
	else:
		success = process_audio(args, tts)
		return 0 if success else 1

if __name__ == "__main__":
	sys.exit(main())