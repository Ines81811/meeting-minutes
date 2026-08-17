from functools import lru_cache

from faster_whisper import WhisperModel

from app import config
from app.stt.base import STTEngine, Segment


class FasterWhisperEngine(STTEngine):
    def __init__(self):
        self._model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
            cpu_threads=config.WHISPER_CPU_THREADS,
        )

    def transcribe(self, audio_path: str) -> list[Segment]:
        # vad_filter skips silence/non-speech before decoding — meeting
        # recordings often have real pauses, so this cuts wall time for free.
        segments, _info = self._model.transcribe(audio_path, vad_filter=True)
        return [
            Segment(start=seg.start, end=seg.end, text=seg.text.strip())
            for seg in segments
        ]


@lru_cache
def get_engine() -> STTEngine:
    """Load the model once and reuse it across requests."""
    return FasterWhisperEngine()
