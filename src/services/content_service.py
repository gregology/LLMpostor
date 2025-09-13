"""
Content Service for LLMpostor Game

Handles content loading and management, separating I/O from validation logic.
Extracted from ContentManager to follow Single Responsibility Principle.
"""

import logging
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptData:
    """Data structure for a prompt/response pair."""
    id: str
    prompt: str
    model: str
    responses: List[str]
    selected_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'prompt': self.prompt,
            'model': self.model,
            'responses': self.responses,
            'selected_response': self.selected_response
        }
    
    def get_response(self) -> str:
        """Get the selected response, or select one randomly if none selected."""
        if self.selected_response is None:
            self.selected_response = random.choice(self.responses)
        return self.selected_response
    
    def select_random_response(self) -> str:
        """Select and return a random response from the available responses."""
        self.selected_response = random.choice(self.responses)
        return self.selected_response


class ContentService:
    """Manages content loading and retrieval operations."""
    
    def __init__(self, content_loader):
        """
        Initialize ContentService with a content loader.
        
        Args:
            content_loader: Object that handles loading content from source
        """
        self.content_loader = content_loader
        self.prompts: List[PromptData] = []
        self._loaded = False
    
    def load_content(self) -> None:
        """
        Load content using the configured loader.
        
        Raises:
            RuntimeError: If content loading fails
        """
        try:
            self.content_loader.load_prompts_from_yaml()
            self.prompts = self.content_loader.get_all_prompts()
            self._loaded = True
            logger.info(f"Successfully loaded {len(self.prompts)} prompts via ContentService")
        except Exception as e:
            logger.error(f"Failed to load content: {e}")
            raise RuntimeError(f"Content loading failed: {e}")
    
    def get_random_prompt_response(self) -> PromptData:
        """
        Get a random prompt/response pair with a response selected.
        
        Returns:
            Random PromptData object with selected_response set
            
        Raises:
            RuntimeError: If no prompts are loaded
        """
        if not self._loaded or not self.prompts:
            raise RuntimeError("No prompts loaded. Call load_content() first.")
        
        prompt_data = random.choice(self.prompts)
        # Select a random response for this game round
        prompt_data.select_random_response()
        return prompt_data
    
    def get_prompt_by_id(self, prompt_id: str) -> Optional[PromptData]:
        """
        Get a specific prompt by its ID.
        
        Args:
            prompt_id: The ID of the prompt to retrieve
            
        Returns:
            PromptData object if found, None otherwise
        """
        if not self._loaded:
            raise RuntimeError("No prompts loaded. Call load_content() first.")
        
        for prompt in self.prompts:
            if prompt.id == prompt_id:
                return prompt
        
        return None
    
    def get_all_prompts(self) -> List[PromptData]:
        """
        Get all loaded prompts.
        
        Returns:
            List of all PromptData objects
            
        Raises:
            RuntimeError: If no prompts are loaded
        """
        if not self._loaded:
            raise RuntimeError("No prompts loaded. Call load_content() first.")
        
        return self.prompts.copy()
    
    def is_loaded(self) -> bool:
        """Check if prompts have been loaded."""
        return self._loaded
    
    def get_prompt_count(self) -> int:
        """Get the number of loaded prompts."""
        return len(self.prompts) if self._loaded else 0
    
    def validate_content_availability(self) -> bool:
        """
        Validate that content is available for game use.
        
        Returns:
            True if content is ready, False otherwise
        """
        return self._loaded and len(self.prompts) > 0
    
    def get_content_stats(self) -> Dict[str, Any]:
        """
        Get statistics about loaded content.
        
        Returns:
            Dict containing content statistics
        """
        if not self._loaded:
            return {"loaded": False, "count": 0, "models": []}
        
        models = list(set(prompt.model for prompt in self.prompts))
        
        return {
            "loaded": True,
            "count": len(self.prompts),
            "models": models,
            "total_responses": sum(len(prompt.responses) for prompt in self.prompts)
        }