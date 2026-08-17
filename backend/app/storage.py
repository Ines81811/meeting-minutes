import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from app import config
from app.stt.base import Segment


def save_audio(upload_file: UploadFile) -> tuple[str, Path]:
    transcript_id = str(uuid.uuid4())
    ext = Path(upload_file.filename).suffix.lower()
    audio_path = config.AUDIO_DIR / f"{transcript_id}{ext}"

    with audio_path.open("wb") as out_file:
        shutil.copyfileobj(upload_file.file, out_file)

    return transcript_id, audio_path


def save_transcript_json(
    transcript_id: str, audio_filename: str, segments: list[Segment]
) -> Path:
    data = {
        "transcript_id": transcript_id,
        "audio_filename": audio_filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "speaker": seg.speaker,
                "text": seg.text,
            }
            for seg in segments
        ],
    }
    transcript_path = config.TRANSCRIPTS_DIR / f"{transcript_id}.json"
    transcript_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return transcript_path


def load_transcript_json(transcript_id: str) -> dict | None:
    transcript_path = config.TRANSCRIPTS_DIR / f"{transcript_id}.json"
    if not transcript_path.exists():
        return None
    return json.loads(transcript_path.read_text(encoding="utf-8"))


def list_transcripts() -> list[dict]:
    """Summaries of every transcript on disk, newest first — the data source
    for the history page (spec §6/§7)."""
    summaries = []
    for path in config.TRANSCRIPTS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        transcript_id = data["transcript_id"]
        output_counts: dict[str, int] = {}
        for output in list_outputs(transcript_id):
            output_counts[output["mode"]] = output_counts.get(output["mode"], 0) + 1
        summaries.append({
            "transcript_id": transcript_id,
            "audio_filename": data["audio_filename"],
            "created_at": data["created_at"],
            "segment_count": len(data["segments"]),
            "output_counts": output_counts,
        })
    summaries.sort(key=lambda d: d["created_at"], reverse=True)
    return summaries


def list_outputs(transcript_id: str, mode: str | None = None) -> list[dict]:
    results = []
    for path in config.OUTPUTS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["transcript_id"] != transcript_id:
            continue
        if mode is not None and data["mode"] != mode:
            continue
        results.append(data)
    results.sort(key=lambda d: (d["mode"], d["version"]))
    return results


def _next_output_version(transcript_id: str, mode: str) -> int:
    return len(list_outputs(transcript_id, mode)) + 1


def save_output(transcript_id: str, mode: str, content: str) -> dict:
    output_id = str(uuid.uuid4())
    data = {
        "output_id": output_id,
        "transcript_id": transcript_id,
        "mode": mode,
        "version": _next_output_version(transcript_id, mode),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "content": content,
    }
    output_path = config.OUTPUTS_DIR / f"{output_id}.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_output(output_id: str) -> dict | None:
    output_path = config.OUTPUTS_DIR / f"{output_id}.json"
    if not output_path.exists():
        return None
    return json.loads(output_path.read_text(encoding="utf-8"))
