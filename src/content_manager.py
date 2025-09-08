"""
Content Manager for LLMpostor Game

Handles loading and validation of YAML configuration files containing
prompts, responses, and model information for the guessing game.
"""

import yaml
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

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


class ContentValidationError(Exception):
    """Raised when YAML content validation fails."""
    pass


class ContentManager:
    """Manages loading and validation of game content from YAML files."""
    
    def __init__(self, yaml_file_path: str = "prompts.yaml"):
        """
        Initialize ContentManager with path to YAML file.
        
        Args:
            yaml_file_path: Path to the YAML file containing prompts and responses
        """
        self.yaml_file_path = yaml_file_path
        self.prompts: List[PromptData] = []
        self._loaded = False
    
    def load_prompts_from_yaml(self) -> None:
        """
        Load prompts and responses from YAML file.
        
        Raises:
            FileNotFoundError: If YAML file doesn't exist
            ContentValidationError: If YAML structure is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        try:
            with open(self.yaml_file_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
            
            self.validate_yaml_structure(data)
            self.prompts = self._parse_prompts(data)
            self._loaded = True
            logger.info(f"Successfully loaded {len(self.prompts)} prompts from {self.yaml_file_path}")
            
        except FileNotFoundError:
            logger.error(f"YAML file not found: {self.yaml_file_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise
        except ContentValidationError as e:
            logger.error(f"Content validation error: {e}")
            raise
    
    def validate_yaml_structure(self, data: Any) -> None:
        """
        Validate the structure of loaded YAML data.
        
        Args:
            data: Parsed YAML data to validate
            
        Raises:
            ContentValidationError: If structure is invalid
        """
        if not isinstance(data, dict):
            raise ContentValidationError("YAML root must be a dictionary")
        
        if 'prompts' not in data:
            raise ContentValidationError("YAML must contain 'prompts' key")
        
        prompts = data['prompts']
        if not isinstance(prompts, list):
            raise ContentValidationError("'prompts' must be a list")
        
        if len(prompts) == 0:
            raise ContentValidationError("'prompts' list cannot be empty")
        
        required_fields = {'id', 'prompt', 'model', 'responses'}
        
        for i, prompt_item in enumerate(prompts):
            if not isinstance(prompt_item, dict):
                raise ContentValidationError(f"Prompt item {i} must be a dictionary")
            
            missing_fields = required_fields - set(prompt_item.keys())
            if missing_fields:
                raise ContentValidationError(
                    f"Prompt item {i} missing required fields: {missing_fields}"
                )
            
            # Validate responses array
            responses = prompt_item['responses']
            if not isinstance(responses, list):
                raise ContentValidationError(
                    f"Prompt item {i} 'responses' must be a list"
                )
            if len(responses) == 0:
                raise ContentValidationError(
                    f"Prompt item {i} 'responses' list cannot be empty"
                )
            for j, response in enumerate(responses):
                if not isinstance(response, str):
                    raise ContentValidationError(
                        f"Prompt item {i} response {j} must be a string"
                    )
                if not response.strip():
                    raise ContentValidationError(
                        f"Prompt item {i} response {j} cannot be empty"
                    )
            
            # Validate other required fields
            for field in ['id', 'prompt', 'model']:
                if not isinstance(prompt_item[field], str):
                    raise ContentValidationError(
                        f"Prompt item {i} field '{field}' must be a string"
                    )
                if not prompt_item[field].strip():
                    raise ContentValidationError(
                        f"Prompt item {i} field '{field}' cannot be empty"
                    )
        
        # Check for duplicate IDs
        ids = [item['id'] for item in prompts]
        if len(ids) != len(set(ids)):
            raise ContentValidationError("Duplicate prompt IDs found")
    
    def _parse_prompts(self, data: Dict[str, Any]) -> List[PromptData]:
        """
        Parse validated YAML data into PromptData objects.
        
        Args:
            data: Validated YAML data
            
        Returns:
            List of PromptData objects
        """
        prompts = []
        for item in data['prompts']:
            responses = [r.strip() for r in item['responses']]
            
            prompt_data = PromptData(
                id=item['id'].strip(),
                prompt=item['prompt'].strip(),
                model=item['model'].strip(),
                responses=responses
            )
            prompts.append(prompt_data)
        
        return prompts
    
    def get_random_prompt_response(self) -> PromptData:
        """
        Get a random prompt/response pair with a response selected.
        
        Returns:
            Random PromptData object with selected_response set
            
        Raises:
            RuntimeError: If no prompts are loaded
        """
        if not self._loaded or not self.prompts:
            raise RuntimeError("No prompts loaded. Call load_prompts_from_yaml() first.")
        
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
            raise RuntimeError("No prompts loaded. Call load_prompts_from_yaml() first.")
        
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
            raise RuntimeError("No prompts loaded. Call load_prompts_from_yaml() first.")
        
        return self.prompts.copy()
    
    def is_loaded(self) -> bool:
        """Check if prompts have been loaded."""
        return self._loaded
    
    def get_prompt_count(self) -> int:
        """Get the number of loaded prompts."""
        return len(self.prompts) if self._loaded else 0