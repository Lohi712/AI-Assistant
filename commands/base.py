"""
Abstract base class for all VEGA commands.

Every command module (e.g., weather_cmd.py, email_cmd.py) must
subclass BaseCommand and implement the required interface.
"""

from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """
    Abstract base for a voice command handler.

    Subclasses define:
        - triggers: keywords that activate the command
        - priority: lower number = matched first (default 50)
        - match():  whether a query activates this command
        - execute(): the actual command logic
    """

    priority: int = 50  # Lower = matched earlier

    @property
    @abstractmethod
    def triggers(self) -> list[str]:
        """
        Keywords/phrases that activate this command.

        Returns:
            List of trigger strings to match against user queries.
        """
        ...

    def match(self, query: str) -> bool:
        """
        Check if the user query matches this command.

        Default implementation checks if any trigger is a substring
        of the query. Override for more complex matching.

        Args:
            query: Lowercased user query string.

        Returns:
            True if the query should be handled by this command.
        """
        return any(trigger in query for trigger in self.triggers)

    @abstractmethod
    def execute(self, query: str, assistant) -> None:
        """
        Execute the command.

        Args:
            query: The full lowercased user query.
            assistant: Reference to the VegaAssistant (provides
                       access to speech, settings, ai, etc.).
        """
        ...
