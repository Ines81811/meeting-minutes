import io

from docx import Document


def _format_time(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_verbatim_docx(transcript: dict) -> io.BytesIO:
    """Render a transcript's segments as a VERBATIM docx (spec 4.1): no LLM
    processing, just the segments in order as `[HH:MM:SS] Speaker N：text`."""
    document = Document()
    document.add_heading(transcript["audio_filename"], level=1)

    for seg in transcript["segments"]:
        ts = _format_time(seg["start"])
        speaker_label = f"{seg['speaker']}：" if seg.get("speaker") else ""
        document.add_paragraph(f"[{ts}] {speaker_label}{seg['text']}")

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def build_output_docx(title: str, content: str) -> io.BytesIO:
    """Render a Claude-generated ACTION_ITEMS/SUMMARY output as a docx."""
    document = Document()
    document.add_heading(title, level=1)

    for line in content.split("\n"):
        document.add_paragraph(line)

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer
