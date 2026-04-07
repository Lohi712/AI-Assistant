"""
Wake Word Detection for VEGA AI Assistant.

Uses Picovoice Porcupine to detect the custom "Hey Vega"
wake word before activating the assistant.
"""

import struct

import pvporcupine
import pyaudio

from utils.logger import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """
    Listens for the "Hey Vega" wake word using Picovoice Porcupine.

    Supports context-manager usage for proper resource cleanup:

        with WakeWordDetector(settings) as detector:
            if detector.wait_for_wake_word():
                ...
    """

    def __init__(self, settings):
        """
        Initialize the wake word detector.

        Args:
            settings: A Settings instance containing picovoice_access_key
                      and wake_word_model path.
        """
        self._access_key = settings.picovoice_access_key
        self._keyword_path = settings.wake_word_model
        self._porcupine = None
        self._pa = None
        self._stream = None
        logger.info("WakeWordDetector configured (model=%s).", self._keyword_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()
        return False

    def wait_for_wake_word(self) -> bool:
        """
        Block until the wake word is detected.

        Returns:
            True if the wake word was detected, False on error.
        """
        try:
            self._porcupine = pvporcupine.create(
                access_key=self._access_key,
                keyword_paths=[self._keyword_path],
            )
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length,
            )

            logger.info("Listening for wake word ('Hey Vega')...")
            print("\n🎤 Listening for wake word ('Hey Vega')...")

            while True:
                pcm = self._stream.read(self._porcupine.frame_length)
                pcm = struct.unpack_from(
                    "h" * self._porcupine.frame_length, pcm
                )

                keyword_index = self._porcupine.process(pcm)

                if keyword_index >= 0:
                    logger.info("Wake word detected!")
                    print("✅ Wake word detected!")
                    self._cleanup()
                    return True

        except Exception as e:
            logger.error("Wake word detection error: %s", e)
            self._cleanup()
            return False

    def _cleanup(self) -> None:
        """Release all audio resources."""
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None
