"""Wake-word detector for Astra.

This module implements a local wake-word detector using the existing Vosk model
as a lightweight keyword spotter (grammar-based). It intentionally keeps
microphone ownership separate from the main Vosk command listener: the
wake-word detector opens its own short-lived audio stream and stops it when the
wake word is detected so the main Vosk listener can take the microphone.

If Vosk or sounddevice are unavailable, the module marks itself as unavailable
and provides a no-op API so Astra keeps working with typed input.
"""

import json
import logging
import queue
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from vosk import Model, KaldiRecognizer
    import sounddevice as sd
    from app.voice import MODEL_PATH
    from app.config import TARGET_SAMPLE_RATE, WAKE_WORD_PHRASE
    _VOSK_AVAILABLE = True
except Exception:
    _VOSK_AVAILABLE = False


class WakeWordDetector:
    def __init__(self, phrase: str = WAKE_WORD_PHRASE, sample_rate: int = TARGET_SAMPLE_RATE):
        self.phrase = phrase.lower().strip()
        self.sample_rate = sample_rate
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._detect_event = threading.Event()
        self._stopped_event = threading.Event()  # New: signals when worker truly stopped
        self._running = False
        self._model = None
        self._q: Optional[queue.Queue] = None
        self._stream = None  # Track the audio stream explicitly

        self.available = _VOSK_AVAILABLE

    def _load_model(self) -> bool:
        try:
            if self._model is None:
                self._model = Model(MODEL_PATH)
            return True
        except Exception as e:
            logger.exception("Wake-word model load failed: %s", e)
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.debug("Wake audio status: %s", status)
        if self._q is not None:
            try:
                # Ensure bytes representation
                self._q.put_nowait(indata.tobytes())
            except Exception:
                pass

    def _worker(self):
        if not self._load_model():
            self.available = False
            self._stopped_event.set()
            return

        self._q = queue.Queue()

        # Grammar: only listen for the wake phrase (helps speed and reduces false positives)
        grammar = json.dumps([self.phrase])

        try:
            recognizer = KaldiRecognizer(self._model, self.sample_rate, grammar)
        except Exception as e:
            logger.exception("Wake recognizer init failed: %s", e)
            self.available = False
            self._stopped_event.set()
            return

        stream = None
        try:
            stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback
            )
            self._stream = stream  # Store reference for cleanup
            stream.start()
            
            logger.info("Wake-word listener started (phrase='%s')", self.phrase)
            self._running = True

            while not self._stop_event.is_set():
                try:
                    data = self._q.get(timeout=0.2)
                except queue.Empty:
                    continue

                if not data:
                    continue

                try:
                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        text = res.get("text", "").strip().lower()
                        if self.phrase in text:
                            logger.info("Wake phrase detected: %s", text)
                            self._detect_event.set()
                            break
                    else:
                        # Partial results can also contain the phrase in noisy environments
                        partial = json.loads(recognizer.PartialResult())
                        partial_text = partial.get("partial", "").strip().lower()
                        if self.phrase in partial_text:
                            logger.info("Wake phrase detected (partial): %s", partial_text)
                            self._detect_event.set()
                            break
                except Exception:
                    # Ignore decode errors and keep listening
                    continue

        except Exception as e:
            logger.exception("Wake-word audio stream failed: %s", e)

        finally:
            # Explicitly close the stream
            self._running = False
            if stream is not None:
                try:
                    stream.stop()
                    logger.info("Wake-word audio stream stopped")
                except Exception as e:
                    logger.exception("Error stopping wake-word stream: %s", e)
                try:
                    stream.close()
                    logger.info("Wake-word audio stream closed")
                except Exception as e:
                    logger.exception("Error closing wake-word stream: %s", e)
            
            self._stream = None
            self._stopped_event.set()  # Signal that worker is truly done
            logger.info("Wake-word listener worker finished")

    def start(self):
        if not self.available:
            logger.warning("Wake-word not available (missing dependencies or model)")
            return False

        if self._thread is not None and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._detect_event.clear()
        self._thread = threading.Thread(target=self._worker, name="Astra-Wake", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Stop the wake-word detector and wait for it to fully shut down."""
        logger.info("Stopping wake-word detector...")
        self._stop_event.set()
        
        # Wait for the worker thread to actually finish
        try:
            if self._thread is not None:
                self._thread.join(timeout=2.0)
        except Exception as e:
            logger.exception("Error joining wake-word thread: %s", e)
        
        # Wait for the worker to signal it's actually stopped (stream closed)
        if not self._stopped_event.wait(timeout=2.0):
            logger.warning("Wake-word detector did not stop cleanly within timeout")
        
        self._thread = None
        self._running = False
        self._stream = None
        logger.info("Wake-word detector stopped")

    def wait_for_wake(self, timeout: Optional[float] = None) -> bool:
        """Block until wake phrase is detected or timeout occurs."""
        return self._detect_event.wait(timeout=timeout)

    def is_running(self) -> bool:
        return self._running
    
    def is_stopped(self) -> bool:
        """Check if the wake-word detector stream is fully stopped."""
        return self._stopped_event.is_set()
    
    def wait_until_stopped(self, timeout: Optional[float] = 2.0) -> bool:
        """Wait until the wake-word detector is fully stopped (microphone released)."""
        return self._stopped_event.wait(timeout=timeout)


# Module level detector for convenience
detector = WakeWordDetector()

def start():
    return detector.start()

def stop():
    return detector.stop()

def wait_for_wake(timeout: Optional[float] = None) -> bool:
    return detector.wait_for_wake(timeout=timeout)

def wait_until_stopped(timeout: Optional[float] = 2.0) -> bool:
    """Wait until the wake-word detector is fully stopped (microphone released)."""
    return detector.wait_until_stopped(timeout=timeout)

def available() -> bool:
    return detector.available
