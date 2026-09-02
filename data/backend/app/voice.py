"""Offline Vosk voice listener with reliable 16 kHz audio handling."""

import array
import json
import math
import queue
from typing import Optional

from vosk import KaldiRecognizer, Model
import sounddevice as sd

MODEL_PATH = "models/vosk-model-small-en-us-0.15"
TARGET_SAMPLE_RATE = 16000

model = None
recognizer = None
audio_queue = None
input_stream = None
input_samplerate: Optional[int] = None
input_channels: Optional[int] = None


def _to_pcm_bytes(data):
    if hasattr(data, "tobytes"):
        return data.tobytes()
    return bytes(data)


def _get_default_input_device_info() -> tuple[int, int]:
    try:
        device = sd.default.device
        if isinstance(device, (tuple, list)) and device:
            device_info = sd.query_devices(device[0], "input")
        else:
            device_info = sd.query_devices(sd.default.device, "input")

        if isinstance(device_info, dict):
            samplerate = int(device_info.get("default_samplerate", TARGET_SAMPLE_RATE))
            channels = int(device_info.get("max_input_channels", 1))
            return samplerate, max(1, channels)
    except Exception:
        pass

    return TARGET_SAMPLE_RATE, 1


def _close_stream() -> None:
    global input_stream, audio_queue, input_samplerate, input_channels
    if input_stream is not None:
        try:
            input_stream.stop()
        except Exception:
            pass
        try:
            input_stream.close()
        except Exception:
            pass
        input_stream = None
    audio_queue = None
    input_samplerate = None
    input_channels = None


def _resample_pcm16(data: bytes, src_rate: int, target_rate: int) -> bytes:
    if not data or src_rate == target_rate:
        return data

    try:
        samples = array.array("h")
        samples.frombytes(data)
    except Exception:
        return b""

    if len(samples) < 2:
        return b""

    dst_length = int(round(len(samples) * target_rate / src_rate))
    if dst_length <= 0:
        return b""

    dst = array.array("h", [0]) * dst_length
    ratio = float(src_rate) / float(target_rate)

    for i in range(dst_length):
        position = i * ratio
        lo = int(math.floor(position))
        hi = min(lo + 1, len(samples) - 1)
        fraction = position - lo
        value = int(round((1 - fraction) * samples[lo] + fraction * samples[hi]))
        dst[i] = max(-32768, min(32767, value))

    return dst.tobytes()


def _downmix_to_mono(pcm: bytes, channels: int) -> bytes:
    if channels <= 1:
        return pcm

    try:
        samples = array.array("h")
        samples.frombytes(pcm)
    except Exception:
        return b""

    mono_samples = array.array("h")
    for i in range(0, len(samples), channels):
        frame = samples[i : i + channels]
        if not frame:
            continue
        mono_value = int(round(sum(frame) / len(frame)))
        mono_samples.append(max(-32768, min(32767, mono_value)))

    return mono_samples.tobytes()


def _audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Audio status: {status}")

    if audio_queue is None:
        return

    pcm = _to_pcm_bytes(indata)
    if input_channels is not None and input_channels > 1:
        pcm = _downmix_to_mono(pcm, input_channels)

    if input_samplerate is not None and input_samplerate != TARGET_SAMPLE_RATE:
        pcm = _resample_pcm16(pcm, input_samplerate, TARGET_SAMPLE_RATE)

    if pcm:
        audio_queue.put(pcm)


def load_model() -> bool:
    global model

    if model is not None:
        return True

    try:
        model = Model(MODEL_PATH)
        print("✅ Vosk model loaded")
        return True
    except FileNotFoundError:
        print(f"❌ Model not found at {MODEL_PATH}")
        return False
    except Exception as err:
        print(f"❌ Failed to load Vosk model: {err}")
        return False


def open_stream() -> bool:
    global recognizer, audio_queue, input_stream, input_samplerate, input_channels

    if recognizer is not None and input_stream is not None and audio_queue is not None:
        return True

    if not load_model():
        return False

    device_samplerate, device_channels = _get_default_input_device_info()
    input_channels = device_channels if device_channels >= 1 else 1
    audio_queue = queue.Queue()
    recognizer = KaldiRecognizer(model, TARGET_SAMPLE_RATE)

    try:
        input_samplerate = TARGET_SAMPLE_RATE
        input_stream = sd.RawInputStream(
            samplerate=TARGET_SAMPLE_RATE,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=_audio_callback,
        )
        input_stream.start()
        return True
    except Exception:
        _close_stream()

    try:
        input_samplerate = device_samplerate
        audio_queue = queue.Queue()
        recognizer = KaldiRecognizer(model, TARGET_SAMPLE_RATE)
        input_stream = sd.RawInputStream(
            samplerate=device_samplerate,
            blocksize=8000,
            dtype="int16",
            channels=device_channels,
            callback=_audio_callback,
        )
        input_stream.start()
        return True
    except Exception as err:
        print(f"❌ Failed to open microphone stream: {err}")
        _close_stream()
        recognizer = None
        return False


def shutdown_voice() -> None:
    global recognizer, audio_queue
    _close_stream()
    recognizer = None
    audio_queue = None


def listen() -> str:
    global recognizer, input_stream, audio_queue

    if recognizer is None or input_stream is None or audio_queue is None:
        if not open_stream():
            raise RuntimeError("Vosk voice input could not be initialized")

    print("🎤 Listening...")

    while True:
        try:
            chunk = audio_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        if not chunk:
            continue

        try:
            if recognizer.AcceptWaveform(chunk):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip().lower()

                if text:
                    print(f"FINAL : {text}")
                    return text

            partial = json.loads(recognizer.PartialResult())
            partial_text = partial.get("partial", "").strip()
            if partial_text:
                print(f"PARTIAL : {partial_text}")
        except json.JSONDecodeError:
            continue

