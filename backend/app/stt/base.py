from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


class STTEngine(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> list[Segment]:
        """Transcribe an audio file into time-stamped segments."""
