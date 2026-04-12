"""
VEGA — Virtual Enhanced General Assistant
==========================================

A voice-controlled AI assistant for Windows that automates
daily laptop tasks, powered by Google Gemini AI.

Entry point: python main.py
"""

import sys

from config.settings import Settings
from core.speech import SpeechEngine
from core.wake_word import WakeWordDetector
from core.conversation import AIConversation
from commands import CommandRegistry
from utils.logger import setup_logging, get_logger


class VegaAssistant:
    """
    Main orchestrator that ties together speech, wake word
    detection, AI conversation, and command dispatch.
    """

    def __init__(self):
        """Initialize all VEGA subsystems."""
        # Load configuration
        self.settings = Settings.load()

        # Setup logging
        setup_logging(self.settings.log_level)
        self.logger = get_logger("main")
        self.logger.info("=" * 50)
        self.logger.info("VEGA AI Assistant starting up...")
        self.logger.info("=" * 50)

        # Initialize core engines
        self.speech = SpeechEngine(
            language=self.settings.speech_language,
            timeout=self.settings.listen_timeout,
            phrase_limit=self.settings.listen_phrase_limit,
        )
        self.ai = AIConversation(self.settings)
        self.wake_word = WakeWordDetector(self.settings)

        # Initialize command registry (auto-discovers all commands)
        self.registry = CommandRegistry(self)

        self.logger.info(
            "Registered commands: %s", self.registry.registered_commands
        )

    def run(self) -> None:
        """Main loop: wait for wake word, then process commands."""
        print("\n" + "=" * 50)
        print("   🚀 VEGA AI Assistant")
        print("   Virtual Enhanced General Assistant")
        print("=" * 50)

        try:
            consecutive_failures = 0
            MAX_FAILURES = 3

            while True:
                # Wait for wake word
                if self.wake_word.wait_for_wake_word():
                    consecutive_failures = 0  # Reset on success
                    self.speech.greet()

                    # Reset AI context for a fresh session
                    self.ai.reset_session()

                    # Command loop — runs until user says exit
                    self._command_loop()
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_FAILURES:
                        self.logger.error(
                            "Wake word detection failed %d times in a row. "
                            "Please fix the issue above and restart VEGA.",
                            consecutive_failures,
                        )
                        print(
                            "\n[FATAL] Wake word detection is failing repeatedly.\n"
                            "Please fix the issue printed above, then run 'python main.py' again.\n"
                        )
                        break

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user (Ctrl+C).")
            self.speech.speak("Goodbye sir!")
            print("\n👋 VEGA shutting down. Goodbye!")

    def _command_loop(self) -> None:
        """Process voice commands until the user says goodbye."""
        EXIT_PHRASES = ("go to sleep", "bye", "exit", "quit", "goodbye", "stop")

        while True:
            query = self.speech.listen().lower()

            # Skip empty / failed recognitions
            if query in ("none", ""):
                continue

            # Check for exit commands
            if any(phrase in query for phrase in EXIT_PHRASES):
                self.speech.speak("Goodbye Sir! Going to sleep now.")
                self.logger.info("User exited command loop.")
                print("💤 VEGA going to sleep...\n")
                break

            # Dispatch to the matching command
            self.registry.dispatch(query)


def main():
    """Entry point for VEGA AI Assistant."""
    try:
        vega = VegaAssistant()
        vega.run()
    except SystemExit:
        # Settings validation failed
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
