import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _find_ffmpeg_bin_dir() -> Path | None:
    override = os.getenv("FFMPEG_DLL_DIR")
    if override:
        return Path(override)

    winget_packages = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    for bin_dir in winget_packages.glob("Gyan.FFmpeg.Shared_*/ffmpeg-*-shared/bin"):
        return bin_dir
    return None


_FFMPEG_BIN_DIR = _find_ffmpeg_bin_dir()

# torchcodec (a pyannote.audio dependency) loads FFmpeg's shared libraries via
# ctypes at import time. On Windows this requires the DLL directory to be
# registered explicitly, since PATH changes from installers don't reach an
# already-running process.
if sys.platform == "win32" and _FFMPEG_BIN_DIR:
    os.add_dll_directory(str(_FFMPEG_BIN_DIR))

FFMPEG_EXE = str(_FFMPEG_BIN_DIR / "ffmpeg.exe") if _FFMPEG_BIN_DIR else "ffmpeg"

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# STT and diarization run concurrently (see api/transcribe.py), so their thread
# budgets are split rather than each defaulting to "use every core" — tuned for
# a 12-core machine, override in .env for other hardware.
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "8"))
DIARIZATION_CPU_THREADS = int(os.getenv("DIARIZATION_CPU_THREADS", "4"))

HF_TOKEN = os.getenv("HF_TOKEN")
PYANNOTE_MODEL = os.getenv("PYANNOTE_MODEL", "pyannote/speaker-diarization-community-1")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

DATA_DIR = BACKEND_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
OUTPUTS_DIR = DATA_DIR / "outputs"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}
MAX_DURATION_SECONDS = 2 * 60 * 60
