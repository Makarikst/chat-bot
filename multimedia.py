import base64
import tempfile

import cv2
import numpy as np
import streamlit as st
from faster_whisper import WhisperModel


@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")


def transcribe_audio(file_obj, sample_rate: int = 16000) -> str:
    ext = file_obj.name.rsplit(".", 1)[-1].lower()
    suffix = f".{ext}" if ext else ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file_obj.seek(0)
        tmp.write(file_obj.read())
        tmp_path = tmp.name

    try:
        model = load_whisper()
        segments, info = model.transcribe(tmp_path, language=None, beam_size=5)
        transcript = "".join(segment.text for segment in segments)
        return transcript.strip() if transcript else "(no speech detected)"
    finally:
        import os
        os.unlink(tmp_path)


def extract_video_frames(file_obj, max_frames: int = 8) -> list[str]:
    ext = file_obj.name.rsplit(".", 1)[-1].lower()
    suffix = f".{ext}" if ext else ".mp4"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file_obj.seek(0)
        tmp.write(file_obj.read())
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0

        if duration <= 0 or total_frames <= 0:
            return []

        frame_indices = np.linspace(0, total_frames - 1, max_frames, dtype=int)
        data_uris = []

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            _, buffer = cv2.imencode(".jpg", frame)
            b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
            data_uris.append(f"data:image/jpeg;base64,{b64}")

        cap.release()
        return data_uris
    finally:
        import os
        os.unlink(tmp_path)
