# setup.py
import os
from setuptools import setup, find_packages

# Read README.md
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Base dependencies
BASE_DEPS = [
    'numpy',
    'torch',
    'pydub',
    'sounddevice',
    'python-dotenv',
    # 'textual',       # From requirement_tui.txt
    # 'pyperclip',     # From requirement_tui.txt
    'scipy'          # Implicit dependency for wavfile reading in base
]

# Optional extras (engines)
extras_require = {
    "chatterbox": [
        "chatterbox-tts",
        "spacy",
        "peft"
    ],
    "kitten": [
        "kittentts",
        "spacy"
    ],
    "kokoro": [
        "kokoro>=0.9.4",
        "soundfile"
    ],
}

# All extras
all_deps = []
for deps in extras_require.values():
    all_deps.extend(deps)
extras_require["all"] = list(set(all_deps))

setup(
    name="tts-runner",
    version="1.0.0",
    author="Jebin Einstein",
    author_email="jebin@gmail.com",
    description="A flexible, multi-engine Text-to-Speech runner with TUI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jebin2/TTS",

    packages=find_packages(),
    include_package_data=True,

    install_requires=BASE_DEPS,
    extras_require=extras_require,

    entry_points={
        "console_scripts": [
            "tts-runner=tts_runner.runner:main",
            "tts-tui=tts_runner.tui:main",
        ],
    },

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],

    python_requires=">=3.10",
)
