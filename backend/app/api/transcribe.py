from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import mutagen
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app import config, jobs, llm, storage
from app.alignment import align_segments
from app.audio_preprocess import to_wav
from app.diarization.pyannote_engine import get_engine as get_diarization_engine
from app.docx_export import build_output_docx, build_verbatim_docx
from app.stt.faster_whisper_engine import get_engine as get_stt_engine

router = APIRouter(prefix="/api")

OUTPUT_MODE_LABELS = {"ACTION_ITEMS": "Action Items", "SUMMARY": "會議摘要"}


def _load_ready_transcript(transcript_id: str) -> dict:
    """Transcript JSON on disk is the source of truth for "done" — it survives
    server restarts, unlike the in-memory job dict. Fall back to job status
    only to explain why it's not ready yet (still processing vs failed vs
    never existed)."""
    transcript = storage.load_transcript_json(transcript_id)
    if transcript is not None:
        return transcript

    job = jobs.get_status(transcript_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到該筆逐字稿")
    raise HTTPException(status_code=400, detail=f"逐字稿尚未完成（狀態：{job['status']}）")


def _validate_duration(audio_path: Path) -> None:
    audio = mutagen.File(audio_path)
    if audio is None or audio.info is None:
        raise HTTPException(status_code=400, detail="無法讀取音檔資訊，檔案可能已損毀")
    if audio.info.length > config.MAX_DURATION_SECONDS:
        raise HTTPException(status_code=400, detail="音檔時長超過 2 小時上限")


def _run_transcription(transcript_id: str, audio_path: Path, audio_filename: str) -> None:
    jobs.set_status(transcript_id, "processing")
    wav_path = None
    try:
        wav_path = to_wav(audio_path)
        # STT and diarization are independent — run them concurrently instead
        # of back-to-back. Both release the GIL during the heavy native/torch
        # work, so plain threads give real wall-clock overlap.
        with ThreadPoolExecutor(max_workers=2) as executor:
            stt_future = executor.submit(get_stt_engine().transcribe, str(wav_path))
            diarization_future = executor.submit(get_diarization_engine().diarize, str(wav_path))
            segments = stt_future.result()
            turns = diarization_future.result()
        segments = align_segments(segments, turns)
        storage.save_transcript_json(transcript_id, audio_filename, segments)
        jobs.set_status(transcript_id, "done")
    except Exception as exc:
        jobs.set_status(transcript_id, "failed", error=str(exc))
    finally:
        if wav_path is not None:
            wav_path.unlink(missing_ok=True)


@router.post("/upload")
def upload_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in config.ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支援的檔案格式：{ext}，僅接受 mp3/wav/m4a",
        )

    transcript_id, audio_path = storage.save_audio(file)

    try:
        _validate_duration(audio_path)
    except HTTPException:
        audio_path.unlink(missing_ok=True)
        raise

    jobs.create_job(transcript_id)
    background_tasks.add_task(_run_transcription, transcript_id, audio_path, file.filename)

    return {"transcript_id": transcript_id, "status": "pending"}


@router.get("/transcripts")
def list_transcripts():
    return storage.list_transcripts()


@router.get("/transcripts/{transcript_id}")
def get_transcript(transcript_id: str):
    job = jobs.get_status(transcript_id)
    if job is None:
        # Job status is in-memory only and resets on server restart, but the
        # transcript JSON on disk is durable — fall back to it so existing
        # transcripts and their output versions stay reachable across restarts.
        if storage.load_transcript_json(transcript_id) is None:
            raise HTTPException(status_code=404, detail="找不到該筆逐字稿")
        job = {"status": "done", "error": None}

    response = {"transcript_id": transcript_id, **job}
    if job["status"] == "done":
        response["transcript"] = storage.load_transcript_json(transcript_id)
        response["outputs"] = storage.list_outputs(transcript_id)
    return response


@router.get("/transcripts/{transcript_id}/outputs")
def get_outputs(transcript_id: str):
    if storage.load_transcript_json(transcript_id) is None:
        raise HTTPException(status_code=404, detail="找不到該筆逐字稿")
    return storage.list_outputs(transcript_id)


@router.get("/transcripts/{transcript_id}/verbatim.docx")
def download_verbatim(transcript_id: str):
    transcript = _load_ready_transcript(transcript_id)
    buffer = build_verbatim_docx(transcript)

    base_name = Path(transcript["audio_filename"]).stem
    filename = f"{base_name}_逐字稿.docx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.post("/transcripts/{transcript_id}/outputs")
def create_output(transcript_id: str, mode: str, style: str = "auto"):
    if mode not in OUTPUT_MODE_LABELS:
        raise HTTPException(status_code=400, detail="mode 必須是 ACTION_ITEMS 或 SUMMARY")

    # style only applies to SUMMARY — ACTION_ITEMS ignores it entirely.
    if mode == "SUMMARY" and style not in llm.SUMMARY_STYLES:
        raise HTTPException(
            status_code=400,
            detail=f"style 必須是以下之一：{', '.join(llm.SUMMARY_STYLES)}",
        )

    transcript = _load_ready_transcript(transcript_id)
    transcript_text = llm.build_transcript_text(transcript)

    try:
        if mode == "ACTION_ITEMS":
            content = llm.generate_action_items(transcript_text)
            output_style = None
        else:
            content = llm.generate_summary(transcript_text, style=style)
            output_style = style
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"呼叫 Gemini API 失敗：{exc}")

    return storage.save_output(transcript_id, mode, content, style=output_style)


@router.get("/transcripts/{transcript_id}/outputs/{output_id}/download.docx")
def download_output(transcript_id: str, output_id: str):
    output = storage.load_output(output_id)
    if output is None or output["transcript_id"] != transcript_id:
        raise HTTPException(status_code=404, detail="找不到該筆輸出")

    transcript = storage.load_transcript_json(transcript_id)
    label = OUTPUT_MODE_LABELS[output["mode"]]
    style_key = output.get("style")
    if style_key and style_key in llm.SUMMARY_STYLES:
        label = f"{label}-{llm.SUMMARY_STYLES[style_key]['label']}"
    buffer = build_output_docx(f"{label}（v{output['version']}）", output["content"])

    base_name = Path(transcript["audio_filename"]).stem
    filename = f"{base_name}_{label}_v{output['version']}.docx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )
