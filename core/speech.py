"""
Speech Engine for VEGA AI Assistant.

Text-to-Speech:
  - PRIMARY:  edge-tts (Microsoft Neural TTS) — sounds genuinely human.
              Playback via Windows MCI API (built-in, no extra packages).
  - FALLBACK: Windows SAPI — used if edge-tts or internet is unavailable.

Interrupting speech:
  - Press the ESCAPE key at any time to stop VEGA mid-sentence.
  - Or say "stop" / "quiet" — the background listener will catch it.
"""

import asyncio
import ctypes
import datetime
import msvcrt       # Windows built-in: keyboard input without Enter
import os
import tempfile
import threading
import time

import speech_recognition as sr
import win32com.client

from utils.logger import get_logger

logger = get_logger(__name__)

# ── Optional: edge-tts for neural voice ─────────────────────────
try:
    import edge_tts
    _EDGE_TTS_AVAILABLE = True
    logger.info("edge-tts available — using neural voice.")
except ImportError:
    _EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts not installed — falling back to SAPI voice. "
                   "Run: pip install edge-tts")

# ── SAPI async flags ─────────────────────────────────────────────
_SVSF_ASYNC              = 1
_SVSF_PURGE_BEFORE_SPEAK = 2

# ── Windows MCI (built-in MP3 player) ───────────────────────────
_mci = ctypes.windll.winmm.mciSendStringW

def _mci_cmd(cmd: str) -> None:
    _mci(cmd, None, 0, None)


class SpeechEngine:
    """
    Handles all voice I/O for VEGA.

    Speak pipeline:
        edge-tts  →  generate MP3  →  Windows MCI play  →  poll loop
        (falls back to SAPI if edge-tts unavailable or offline)

    Interruption:
        • Press ESC at any time — instant stop
        • Say "stop" / "quiet" / "enough" — caught by background thread
    """

    STOP_PHRASES = {
        "stop", "stop it", "vega stop", "quiet", "shut up",
        "enough", "cancel", "silence", "pause"
    }

    # Change this to switch voice:
    # en-US-JennyNeural  →  warm conversational female (US)
    # en-US-GuyNeural    →  natural male (US)
    # en-US-AriaNeural   →  expressive female (US)
    # en-IN-NeerjaNeural →  Indian English female
    # en-IN-PrabhatNeural→  Indian English male
    DEFAULT_VOICE  = "en-US-JennyNeural"
    DEFAULT_RATE   = "+5%"    # Slightly faster = more natural
    DEFAULT_VOLUME = "+0%"

    def __init__(
        self,
        language: str     = "en-in",
        timeout: int      = 8,
        phrase_limit: int = 15,
        voice: str        = None,
    ):
        self._sapi         = win32com.client.Dispatch("SAPI.SpVoice")
        self._recognizer   = sr.Recognizer()
        self._language     = language
        self._timeout      = timeout
        self._phrase_limit = phrase_limit
        self._voice        = voice or self.DEFAULT_VOICE

        # Interrupt control
        self._stop_event  = threading.Event()
        self._is_speaking = False
        self._shutdown    = False
        self._mci_alias   = "vega_audio"   # MCI playback alias

        # Background thread for voice-based stop detection
        self._interrupt_thread = threading.Thread(
            target=self._interrupt_listener, daemon=True, name="vega-interrupt"
        )
        self._interrupt_thread.start()

        engine = "edge-tts (neural)" if _EDGE_TTS_AVAILABLE else "SAPI"
        logger.info("SpeechEngine ready | engine=%s | voice=%s", engine, self._voice)

    # ── Public API ───────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """
        Speak text aloud. Interruptible via ESC key or "stop" voice command.
        Uses neural TTS if available, SAPI otherwise.
        """
        if not text:
            return

        logger.debug("Speaking: %s", text[:80])
        self._stop_event.clear()
        self._is_speaking = True
        print(f"\n🔊 VEGA: {text[:80]}{'...' if len(text) > 80 else ''}")

        try:
            if _EDGE_TTS_AVAILABLE:
                success = self._neural_speak(text)
                if not success:
                    logger.warning("Neural TTS failed — using SAPI fallback.")
                    self._sapi_speak(text)
            else:
                self._sapi_speak(text)
        finally:
            self._is_speaking = False

    def stop_speaking(self) -> None:
        """Interrupt and cancel any ongoing speech instantly."""
        self._stop_event.set()
        # Stop MCI playback
        try:
            _mci_cmd(f"stop {self._mci_alias}")
            _mci_cmd(f"close {self._mci_alias}")
        except Exception:
            pass
        # Stop SAPI (in case fallback was active)
        try:
            self._sapi.Speak("", _SVSF_ASYNC | _SVSF_PURGE_BEFORE_SPEAK)
        except Exception:
            pass
        logger.info("Speech interrupted.")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def listen(self) -> str:
        """Listen for voice input. Returns recognized text or 'None'."""
        with sr.Microphone() as source:
            logger.info("Listening...")
            print("Listening...")

            # ── Mic sensitivity tuning ──────────────────────────
            # Short calibration — just enough to gauge background noise
            self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

            # Lower energy threshold = picks up quieter speech
            # Default is ~4000 which misses soft/short words
            self._recognizer.energy_threshold = 300

            # Auto-adapt threshold based on ambient noise over time
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.dynamic_energy_adjustment_damping = 0.15
            self._recognizer.dynamic_energy_ratio = 1.5

            # How long silence must last before phrase is considered "done"
            # 1.5s = user can pause to think mid-sentence without being cut off
            self._recognizer.pause_threshold = 1.5

            # Minimum audio length that counts as a phrase (seconds)
            self._recognizer.phrase_threshold = 0.15

            # Grace period: won't cut off if speech resumes within this window
            self._recognizer.non_speaking_duration = 1.0

            try:
                audio = self._recognizer.listen(
                    source,
                    timeout=self._timeout,
                    phrase_time_limit=30,  # Allow up to 30s for long inputs
                )
            except sr.WaitTimeoutError:
                self.speak("I didn't hear anything, please try again.")
                return "None"

        try:
            print("Recognizing...")
            query = self._recognizer.recognize_google(audio, language=self._language)
            logger.info("User said: %s", query)
            print(f"User said: {query}")
            return query
        except sr.UnknownValueError:
            logger.warning("Could not understand audio.")
            print("Sorry, I didn't catch that...")
            return "None"
        except sr.RequestError as e:
            logger.error("Speech recognition service error: %s", e)
            self.speak("Speech recognition service is unavailable.")
            return "None"

    def greet(self) -> None:
        """Greet the user based on time of day."""
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good Morning Sir!"
        elif hour < 18:
            greeting = "Good Afternoon Sir!"
        else:
            greeting = "Good Evening Sir!"

        # Single speak() call — no gap between greeting and intro
        self.speak(
            f"{greeting} This is VEGA, your Virtual Enhanced General Assistant. "
            "How may I help you today?"
        )

    # ── Neural TTS: edge-tts + Windows MCI ──────────────────────

    def _neural_speak(self, text: str) -> bool:
        """
        Generate speech with edge-tts, play via Windows MCI.
        Returns True on success, False to trigger SAPI fallback.
        """
        tmp_path = None
        try:
            # Generate MP3
            tmp_path = self._generate_mp3(text)
            if not tmp_path:
                return False

            # Check if stopped during generation
            if self._stop_event.is_set():
                return True

            # Open and play via Windows MCI
            _mci_cmd(f'open "{tmp_path}" type mpegvideo alias {self._mci_alias}')
            _mci_cmd(f"play {self._mci_alias}")

            # Poll loop: exits on completion or ESC/voice stop
            while True:
                # ── Check ESC key (instant interrupt) ──
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':   # Escape
                        logger.info("ESC pressed — stopping speech.")
                        print("\n[ESC — speech stopped]\n")
                        self._stop_event.set()

                # ── Check stop event (voice command) ──
                if self._stop_event.is_set():
                    break

                # ── Check if MCI finished playing ──
                status_buf = ctypes.create_unicode_buffer(64)
                _mci(f"status {self._mci_alias} mode", status_buf, 64, None)
                if status_buf.value.strip().lower() not in ("playing", "paused"):
                    break

                time.sleep(0.05)

            return True

        except Exception as e:
            logger.error("Neural TTS error: %s", e)
            return False

        finally:
            # Always clean up MCI + temp file
            try:
                _mci_cmd(f"stop {self._mci_alias}")
                _mci_cmd(f"close {self._mci_alias}")
            except Exception:
                pass
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _generate_mp3(self, text: str) -> str | None:
        """Generate an MP3 from text using edge-tts. Returns temp file path."""
        try:
            async def _run():
                communicate = edge_tts.Communicate(
                    text,
                    voice=self._voice,
                    rate=self.DEFAULT_RATE,
                    volume=self.DEFAULT_VOLUME,
                )
                fd, path = tempfile.mkstemp(suffix=".mp3", prefix="vega_")
                os.close(fd)
                await communicate.save(path)
                return path

            # Use an isolated event loop to avoid conflicts
            loop = asyncio.new_event_loop()
            try:
                path = loop.run_until_complete(_run())
                logger.debug("edge-tts generated: %s", path)
                return path
            finally:
                loop.close()

        except Exception as e:
            logger.error("edge-tts generation failed: %s", e)
            return None

    # ── SAPI Fallback ────────────────────────────────────────────

    def _sapi_speak(self, text: str) -> None:
        """SAPI fallback: async speak with ESC + stop event polling."""
        try:
            self._sapi.Speak(text, _SVSF_ASYNC)
            while True:
                # Check ESC
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':
                        logger.info("ESC pressed — stopping SAPI speech.")
                        print("\n[ESC — speech stopped]\n")
                        self._sapi.Speak("", _SVSF_ASYNC | _SVSF_PURGE_BEFORE_SPEAK)
                        break

                if self._stop_event.is_set():
                    self._sapi.Speak("", _SVSF_ASYNC | _SVSF_PURGE_BEFORE_SPEAK)
                    self._stop_event.clear()
                    break

                if self._sapi.WaitUntilDone(50):
                    break

        except Exception as e:
            logger.error("SAPI fallback error: %s", e)

    # ── Background Voice Interrupt Listener ──────────────────────

    def _interrupt_listener(self) -> None:
        """
        Daemon thread: listens for stop phrases while VEGA is speaking.
        This is a best-effort voice interrupt — ESC is more reliable.
        """
        while not self._shutdown:
            if not self._is_speaking:
                time.sleep(0.05)
                continue
            try:
                with sr.Microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.1)
                    audio = self._recognizer.listen(
                        source, timeout=1.5, phrase_time_limit=3
                    )
                phrase = self._recognizer.recognize_google(
                    audio, language=self._language
                ).lower().strip()

                logger.debug("Interrupt listener: '%s'", phrase)
                if any(s in phrase for s in self.STOP_PHRASES):
                    logger.info("Voice stop command: '%s'", phrase)
                    print(f"\n[Stop: '{phrase}']\n")
                    self.stop_speaking()

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as e:
                logger.debug("Interrupt listener: %s", e)
