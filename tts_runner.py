import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
import logging
logging.getLogger().setLevel(logging.ERROR)

import argparse
import os
import sys

TTS_ENGINE = None
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

def server_mode(args):
	while True:
		input = sys.stdin.readline().strip()
		input = input.split("voice")

		try: args.speed = float(input[0])
		except: args.speed = 1

		try: args.voice = int(input[1])
		except: args.voice = 8

		output_path = initiate(args)

		print(output_path)
		sys.stdout.flush()

def current_env():
	"""Detect current virtual environment."""
	venv_path = os.environ.get("VIRTUAL_ENV")
	if venv_path:
		return os.path.basename(venv_path)
	raise ValueError("Please set env first")

def initiate(args):
	if current_env() == "kokoro_env":
		from kokoro_tts import KokoroTTSProcessor as TTSEngine
	else:
		from chatterbox_tts import ChatterboxTTSProcessor as TTSEngine

	global TTS_ENGINE
	if not TTS_ENGINE:
		TTS_ENGINE = TTSEngine()

	TTS_ENGINE.save_audio(args)


def main():
	"""Main entry point."""
	parser = argparse.ArgumentParser(
		description="Text-to-Speech processor"
	)
	parser.add_argument(
		"--server-mode", 
		action="store_true", 
		help="Run in server mode (read commands from stdin)"
	)
	parser.add_argument(
		"--speed", 
		type=float, 
		help=f"Speech speed"
	)
	parser.add_argument(
		"--voice", 
		type=int, 
		help=f"Voice index"
	)
	
	args = parser.parse_args()

	if args.server_mode:
		server_mode(args)
	else:
		success = initiate(args)
		return 0 if success else 1

if __name__ == "__main__":
	main()