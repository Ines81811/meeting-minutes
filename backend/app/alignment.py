from app.diarization.base import SpeakerTurn
from app.stt.base import Segment


def _closest_turn(midpoint: float, turns: list[SpeakerTurn]) -> SpeakerTurn | None:
    best_turn = None
    best_distance = float("inf")
    for turn in turns:
        if turn.start <= midpoint < turn.end:
            return turn
        distance = turn.start - midpoint if midpoint < turn.start else midpoint - turn.end
        if distance < best_distance:
            best_distance = distance
            best_turn = turn
    return best_turn


def align_segments(segments: list[Segment], turns: list[SpeakerTurn]) -> list[Segment]:
    """Assign a speaker to each STT segment using the midpoint of its time range.

    If a segment spans a speaker-turn boundary, the speaker of the turn containing
    the segment's midpoint wins (per spec 3.2). Falls back to the nearest turn when
    the midpoint doesn't fall inside any turn (e.g. a silence gap).
    """
    if not turns:
        return segments

    aligned = []
    for seg in segments:
        midpoint = (seg.start + seg.end) / 2
        turn = _closest_turn(midpoint, turns)
        speaker = turn.speaker if turn else None
        aligned.append(Segment(start=seg.start, end=seg.end, text=seg.text, speaker=speaker))
    return aligned
