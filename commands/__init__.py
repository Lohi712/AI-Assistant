"""
Command Registry and Dispatcher for VEGA AI Assistant.

Auto-discovers all command modules in the commands/ directory,
registers them by priority, and dispatches user queries to the
first matching command.
"""

import importlib
import pkgutil
from pathlib import Path

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


class CommandRegistry:
    """
    Registry that discovers, registers, and dispatches voice commands.

    New commands are auto-discovered: just add a new *_cmd.py file to
    the commands/ directory with a class that subclasses BaseCommand.
    """

    def __init__(self, assistant):
        """
        Initialize the registry and discover all command modules.

        Args:
            assistant: The VegaAssistant instance (passed to commands on execute).
        """
        self._assistant = assistant
        self._commands: list[BaseCommand] = []
        self._discover_commands()

    def _discover_commands(self) -> None:
        """
        Scan the commands/ package for all modules ending in _cmd.py,
        import them, and register any BaseCommand subclasses found.
        """
        commands_dir = Path(__file__).parent

        for module_info in pkgutil.iter_modules([str(commands_dir)]):
            if not module_info.name.endswith("_cmd"):
                continue

            try:
                module = importlib.import_module(f"commands.{module_info.name}")

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseCommand)
                        and attr is not BaseCommand
                    ):
                        instance = attr()
                        self._commands.append(instance)
                        logger.info(
                            "Registered command: %s (triggers=%s, priority=%d)",
                            attr.__name__, instance.triggers, instance.priority,
                        )

            except Exception as e:
                logger.error("Failed to load command module '%s': %s", module_info.name, e)

        # Sort by priority (lower = first)
        self._commands.sort(key=lambda c: c.priority)
        logger.info("Total commands registered: %d", len(self._commands))

    def dispatch(self, query: str) -> bool:
        """
        Find and execute the first matching command for the query.

        Args:
            query: Lowercased user query string.

        Returns:
            True if a command handled the query, False otherwise.
        """
        for cmd in self._commands:
            if cmd.match(query):
                logger.info("Dispatching to %s", cmd.__class__.__name__)
                try:
                    cmd.execute(query, self._assistant)
                except Exception as e:
                    logger.error("Command %s failed: %s", cmd.__class__.__name__, e)
                    self._assistant.speech.speak(
                        "Sorry, I encountered an error executing that command."
                    )
                return True

        logger.debug("No command matched query: %s", query)
        return False

    @property
    def registered_commands(self) -> list[str]:
        """Return a list of registered command class names."""
        return [cmd.__class__.__name__ for cmd in self._commands]
