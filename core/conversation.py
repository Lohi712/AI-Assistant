"""
AI Conversation Engine for VEGA AI Assistant.

Uses Google Gemini with chat-based sessions to maintain
context across multiple queries within a single session.
"""

import google.generativeai as genai

from utils.logger import get_logger
from utils.text_format import cmd_format

logger = get_logger(__name__)

# System instruction that shapes VEGA's personality and behavior
SYSTEM_INSTRUCTION = (
    "You are VEGA (Virtual Enhanced General Assistant), a helpful, "
    "friendly, and intelligent personal AI assistant running on the user's "
    "Windows laptop. You assist with daily tasks, answer questions concisely, "
    "and provide useful information. Keep responses reasonably brief unless "
    "the user asks for detail. Be conversational and natural."
)


class AIConversation:
    """
    Manages a Gemini chat session with persistent context.

    Unlike the old generate_content() approach, this uses start_chat()
    so the model remembers everything said within the session.
    """

    def __init__(self, settings):
        """
        Initialize the AI conversation engine.

        Args:
            settings: A Settings instance with google_ai_api_key.
        """
        self._api_key = settings.google_ai_api_key
        self._model = None
        self._chat = None
        self._initialize()

    def _initialize(self) -> None:
        """Configure the Gemini API and start a fresh chat session."""
        if not self._api_key:
            logger.error("Google AI API key is not set.")
            return

        try:
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=SYSTEM_INSTRUCTION,
            )
            self._chat = self._model.start_chat(history=[])
            logger.info("Gemini AI conversation engine initialized.")
        except Exception as e:
            logger.error("Failed to initialize Gemini: %s", e)

    def ask(self, query: str) -> str:
        """
        Send a query to the AI and get a context-aware response.

        The chat session retains history, so follow-up questions
        within the same session are understood naturally.

        Args:
            query: The user's question or statement.

        Returns:
            Cleaned plain-text response from the AI.
        """
        if not self._chat:
            return "Sorry, my AI brain is not configured. Please check your API key."

        try:
            response = self._chat.send_message(query)
            cleaned = cmd_format(response.text)
            logger.debug("AI response: %s", cleaned[:100])
            return cleaned
        except Exception as e:
            logger.error("AI conversation error: %s", e)
            return "Sorry, I encountered an error while thinking. Please try again."

    def reset_session(self) -> None:
        """Clear conversation history and start a fresh session."""
        if self._model:
            self._chat = self._model.start_chat(history=[])
            logger.info("AI conversation session reset.")

    @property
    def has_context(self) -> bool:
        """Check if there's any conversation history."""
        return bool(self._chat and self._chat.history)
