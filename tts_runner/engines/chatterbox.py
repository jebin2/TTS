from pathlib import Path
from typing import List
import spacy
import torchaudio as ta
import torch
from ..base import BaseTTS

class ChatterboxTTSProcessor(BaseTTS):
	"""Text-to-Speech processor using ChatterboxTTS."""
	
	def __init__(self, stream_audio=False):
		super().__init__("Chatterbox", stream_audio=stream_audio)
		print("Initializing Chatterbox...")
		from chatterbox.tts import ChatterboxTTS
		print("Loading Modal...")
		self.model = ChatterboxTTS.from_pretrained(device=self.device)

		self.nlp=None
		try:
			self.nlp = spacy.load("en_core_web_sm")
		except OSError:
			from spacy.cli import download
			download("en_core_web_sm")
			self.nlp = spacy.load("en_core_web_sm")
		print("Model loaded successfully")

	def tokenize_sentences(self, text):
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
		from chatterbox.tts import punc_norm
		with torch.inference_mode():
			normalized = punc_norm(text)
			tokens = self.model.tokenizer.text_to_tokens(normalized)
			token_count = tokens.shape[1]

			# Clear tokens from GPU memory immediately
			if hasattr(tokens, 'cpu'):
				tokens = tokens.cpu()
			del tokens
			return normalized, token_count

	def split_sentences(self, text, max_tokens=200):
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

	def generate_chunk_audio_file(self, sentence: str, chunk_index: int, voice: str, speed: float) -> Path:
		wav = self.model.generate(
			sentence,
			audio_prompt_path=voice,
			temperature=speed
		)
		
		# Save sentence to numbered file
		chunk_file = self.temp_output_dir / f"chunk_{chunk_index:04d}.wav"
		ta.save(str(chunk_file), wav, self.model.sr)
		del wav
		
		if self.stream_audio:
			self.queue_audio_for_streaming(str(chunk_file))
		return chunk_file

	def generate_audio_files(self, text: str, voice: str, speed: float, chunk_id: int = None):
		sentences = self.split_sentences(text)
		audio_files = []
		total_sentences = len(sentences)
		
		print(f"Processing {total_sentences} text sentences...")
		with torch.inference_mode():
			for i, sentence in enumerate(sentences):
				if self.save_audio_file:
					chunk_file = self.generate_chunk_audio_file(sentence, chunk_id if chunk_id else i, voice, speed)
					audio_files.append(chunk_file)
				print(f"Sentence {i + 1}/{total_sentences} processed -> {chunk_file.name} -> {sentence}")
				
		return audio_files