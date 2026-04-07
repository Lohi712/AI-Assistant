"""
Speech Engine for VEGA AI Assistant.

Provides text-to-speech (via Windows SAPI) and speech-to-text
(via Google Speech Recognition) with a reusable COM object.
"""

import datetime
import speech_recognition as sr
import win32com.client

from utils.logger import get_logger

logger = get_logger(__name__)


class SpeechEngine:
    """
    Handles all voice input/output for the assistant.

    The SAPI COM object is created once and reused for all speak()
    calls, avoiding the overhead of re-initializing it every time.
    """

    def __init__(self, language: str = "en-in", timeout: int = 5, phrase_limit: int = 15):
        """
        Initialize the speech engine.

        Args:
            language: BCP-47 language code for speech recognition.
            timeout: Seconds to wait for speech before giving up.
            phrase_limit: Maximum seconds of speech to capture.
        """
        self._speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self._recognizer = sr.Recognizer()
        self._language = language
        self._timeout = timeout
        self._phrase_limit = phrase_limit
        logger.info("SpeechEngine initialized (lang=%s).", language)

    def speak(self, text: str) -> None:
        """
        Convert text to speech and play it aloud.

        Args:
            text: The text to speak.
        """
        if not text:
            return
        logger.debug("Speaking: %s", text[:80])
        try:
            self._speaker.Speak(text)
        except Exception as e:
            logger.error("Speech synthesis failed: %s", e)

    def listen(self) -> str:
        """
        Listen for voice input through the microphone.

        Returns:
            Recognized text, or "None" if nothing was captured.
        """
        with sr.Microphone() as source:
            logger.info("Listening...")
            print("Listening...")
            self._recognizer.adjust_for_ambient_noise(source, duration=1)
            self._recognizer.pause_threshold = 1

            try:
                audio = self._recognizer.listen(
                    source, timeout=self._timeout, phrase_time_limit=self._phrase_limit
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
        """Greet the user based on the current time of day."""
        hour = datetime.datetime.now().hour
        if hour < 12:
            self.speak("Good Morning Sir!")
        elif hour < 18:
            self.speak("Good Afternoon Sir!")
        else:
            self.speak("Good Evening Sir!")
        self.speak(
            "This is VEGA, your Virtual Enhanced General Assistant. "
            "How may I help you today?"
        )
        logger.info("Greeted user (hour=%d).", hour)
