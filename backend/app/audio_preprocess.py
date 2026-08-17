import subprocess
from pathlib import Path

from app import config


def to_wav(audio_path: Path) -> Path:
    """Transcode the uploaded audio to a canonical 16kHz mono WAV file.

    Source containers (especially .m4a from mobile recorders) can carry encoder
    padding/priming samples that make their reported duration disagree with the
    actual decoded sample count, which trips up pyannote.audio's chunked reader.
    Re-encoding through ffmpeg once up front sidesteps that for both the STT and
    diarization engines.
    """
    wav_path = audio_path.with_suffix(".proc.wav")
    subprocess.run(
        [
            config.FFMPEG_EXE,
            "-y",
            "-i", str(audio_path),
            "-ar", "16000",
            "-ac", "1",
            str(wav_path),
        ],
        check=True,
        capture_output=True,
    )
    return wav_path
