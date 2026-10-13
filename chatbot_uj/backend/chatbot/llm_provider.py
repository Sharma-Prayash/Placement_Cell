"""
LLM Provider Abstraction for NFSU Placement Chatbot.
Enables pluggable LLM backends while decoupling business logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class LLMProvider(ABC):
    """
    Abstract Base Class for LLM generation providers.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is configured and operational."""
        pass

    @abstractmethod
    def generate_response(
        self,
        user_message: str,
        retrieved_context: List[Dict[str, Any]],
        system_instruction: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Generates a grounded answer from retrieved context.
        Returns None or raises an error if generation cannot proceed.
        """
        pass
