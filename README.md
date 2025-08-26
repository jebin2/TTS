# TTS-Engine-Runner

This repository provides a unified interface to run various Text-to-Speech (TTS) engines, including Chatterbox, KittenTTS, and KokoroTTS. It allows for easy switching between engines by managing separate Python virtual environments for each. The runner supports generating audio from a text file, as well as real-time audio streaming from text input.

## Features

*   **Multiple TTS Engine Support**: Easily switch between different TTS engines.
    *   **Chatterbox**: An open-source TTS model by Resemble AI known for high-quality, natural-sounding speech and zero-shot voice cloning.
    *   **KittenTTS**: An ultra-lightweight, open-source TTS model designed for fast, real-time inference, even on CPU.
    *   **KokoroTTS**: An efficient and high-quality open-weight TTS model that can run locally, even without a GPU.
*   **Real-time Audio Streaming**: Stream audio as it's being generated from text.
*   **Batch Processing**: Generate and save a complete audio file from a text file.
*   **Customizable Voice and Speed**: Adjust the voice and speed of the generated speech.
*   **Server Mode**: Run the script in a server mode to continuously process TTS requests.

## Requirements

Each TTS engine has its own set of dependencies, which are managed through separate `requirements.txt` files.

*   **General**:
    *   pydub
    *   sounddevice

*   **Chatterbox**:
    *   chatterbox-tts
    *   spacy
    *   peft
    *   `en_core_web_sm` spacy model

*   **KittenTTS**:
    *   KittenTTS
    *   `en_core_web_sm` spacy model

*   **KokoroTTS**:
    *   kokoro>=0.9.4
    *   soundfile

## Usage

1.  **Setup Virtual Environments**:
    Create and activate a virtual environment for the desired TTS engine. For example, for kokoro:

    ```bash
    python -m venv kokoro_env
    source kokoro_env/bin/activate
    pip install -r kokoro_requirements.txt
    ```

2.  **Prepare `content.txt`**:
    Create a `content.txt` file in the root directory and add the text you want to convert to speech.

3.  **Run the TTS Runner**:

    *   **Generate a single audio file**:
        ```bash
        python tts_runner.py --voice <voice_index> --speed <speed_value>
        ```

    *   **Stream audio in real-time**:
        ```bash
        python tts_runner.py --stream-text --voice <voice_index> --speed <speed_value>
        ```

    *   **Run in server mode**:
        The script will listen for input from stdin.
        ```bash
        python tts_runner.py --server-mode
        ```

### Arguments

*   `--server-mode`: Run in server mode to listen for commands from stdin.
*   `--speed`: (Optional) Floating point number to set the speech speed.
*   `--voice`: (Optional) Integer to select the voice index.
*   `--stream-text`: Enable real-time text streaming.
