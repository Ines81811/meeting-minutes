from functools import lru_cache

import torch
from pyannote.audio import Pipeline

from app import config
from app.diarization.base import DiarizationEngine, SpeakerTurn


class PyannoteEngine(DiarizationEngine):
    def __init__(self):
        # pyannote runs on torch; whisper runs on ctranslate2 (a separate thread
        # pool) — capping torch's threads here doesn't steal from whisper's budget.
        torch.set_num_threads(config.DIARIZATION_CPU_THREADS)
        self._pipeline = Pipeline.from_pretrained(
            config.PYANNOTE_MODEL, token=config.HF_TOKEN
        )

    def diarize(self, audio_path: str) -> list[SpeakerTurn]:
        output = self._pipeline(audio_path)

        raw_turns = [
            (turn.start, turn.end, label)
            for turn, label in output.exclusive_speaker_diarization
        ]
        raw_turns.sort(key=lambda t: t[0])

        # Map raw labels (e.g. SPEAKER_00) to "Speaker N" in order of first appearance.
        label_map: dict[str, str] = {}
        for _, _, label in raw_turns:
            if label not in label_map:
                label_map[label] = f"Speaker {len(label_map) + 1}"

        return [
            SpeakerTurn(start=start, end=end, speaker=label_map[label])
            for start, end, label in raw_turns
        ]


@lru_cache
def get_engine() -> DiarizationEngine:
    """Load the pipeline once and reuse it across requests."""
    return PyannoteEngine()
