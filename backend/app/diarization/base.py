from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str


class DiarizationEngine(ABC):
    @abstractmethod
    def diarize(self, audio_path: str) -> list[SpeakerTurn]:
        """Return non-overlapping speaker turns for an audio file, ordered by start time."""
