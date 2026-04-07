"""Core modules for VEGA AI Assistant."""

from core.speech import SpeechEngine
from core.wake_word import WakeWordDetector
from core.conversation import AIConversation

__all__ = ["SpeechEngine", "WakeWordDetector", "AIConversation"]
