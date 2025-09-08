"""
Unit tests for ContentManager class.

Tests YAML loading, validation, and prompt retrieval functionality.
"""

import pytest
import tempfile
import os
import yaml
from src.content_manager import ContentManager, PromptData, ContentValidationError


class TestPromptData:
    """Test PromptData dataclass functionality."""
    
    def test_prompt_data_creation(self):
        """Test creating a PromptData instance."""
        prompt = PromptData(
            id="test_001",
            prompt="Test prompt",
            model="GPT-4",
            responses=["Test response"]
        )
        
        assert prompt.id == "test_001"
        assert prompt.prompt == "Test prompt"
        assert prompt.model == "GPT-4"
        assert prompt.responses == ["Test response"]
        assert prompt.selected_response is None
    
    def test_prompt_data_to_dict(self):
        """Test converting PromptData to dictionary."""
        prompt = PromptData(
            id="test_001",
            prompt="Test prompt",
            model="GPT-4",
            responses=["Test response"]
        )
        
        expected_dict = {
            'id': 'test_001',
            'prompt': 'Test prompt',
            'model': 'GPT-4',
            'responses': ['Test response'],
            'selected_response': None
        }
        
        assert prompt.to_dict() == expected_dict
    
    def test_prompt_data_get_response(self):
        """Test get_response method."""
        prompt = PromptData(
            id="test_001",
            prompt="Test prompt",
            model="GPT-4",
            responses=["Response 1", "Response 2", "Response 3"]
        )
        
        # First call should select and return a response
        response1 = prompt.get_response()
        assert response1 in ["Response 1", "Response 2", "Response 3"]
        assert prompt.selected_response == response1
        
        # Second call should return the same response
        response2 = prompt.get_response()
        assert response2 == response1
    
    def test_prompt_data_select_random_response(self):
        """Test select_random_response method."""
        prompt = PromptData(
            id="test_001",
            prompt="Test prompt",
            model="GPT-4",
            responses=["Response 1", "Response 2", "Response 3"]
        )
        
        response = prompt.select_random_response()
        assert response in ["Response 1", "Response 2", "Response 3"]
        assert prompt.selected_response == response


class TestContentManager:
    """Test ContentManager class functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.valid_yaml_data = {
            'prompts': [
                {
                    'id': 'test_001',
                    'prompt': 'What is AI?',
                    'model': 'GPT-4',
                    'responses': ['AI is artificial intelligence.']
                },
                {
                    'id': 'test_002',
                    'prompt': 'Explain quantum computing',
                    'model': 'Claude-3',
                    'responses': ['Quantum computing uses quantum mechanics.']
                }
            ]
        }
        
        self.valid_yaml_content = yaml.dump(self.valid_yaml_data)
    
    def test_content_manager_initialization(self):
        """Test ContentManager initialization."""
        manager = ContentManager("test.yaml")
        assert manager.yaml_file_path == "test.yaml"
        assert manager.prompts == []
        assert not manager.is_loaded()
        assert manager.get_prompt_count() == 0
    
    def test_load_prompts_from_yaml_success(self):
        """Test successful loading of prompts from YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            assert manager.is_loaded()
            assert manager.get_prompt_count() == 2
            
            prompts = manager.get_all_prompts()
            assert len(prompts) == 2
            assert prompts[0].id == 'test_001'
            assert prompts[0].prompt == 'What is AI?'
            assert prompts[1].id == 'test_002'
            assert prompts[1].model == 'Claude-3'
            
        finally:
            os.unlink(temp_file)
    
    def test_load_prompts_file_not_found(self):
        """Test handling of missing YAML file."""
        manager = ContentManager("nonexistent.yaml")
        
        with pytest.raises(FileNotFoundError):
            manager.load_prompts_from_yaml()
        
        assert not manager.is_loaded()
    
    def test_load_prompts_invalid_yaml(self):
        """Test handling of invalid YAML syntax."""
        invalid_yaml = "prompts:\n  - id: test\n    prompt: 'unclosed quote"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_yaml)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            
            with pytest.raises(yaml.YAMLError):
                manager.load_prompts_from_yaml()
            
            assert not manager.is_loaded()
            
        finally:
            os.unlink(temp_file)
    
    def test_validate_yaml_structure_valid(self):
        """Test validation of valid YAML structure."""
        manager = ContentManager()
        
        # Should not raise any exception
        manager.validate_yaml_structure(self.valid_yaml_data)
    
    def test_validate_yaml_structure_not_dict(self):
        """Test validation fails when root is not a dictionary."""
        manager = ContentManager()
        
        with pytest.raises(ContentValidationError, match="YAML root must be a dictionary"):
            manager.validate_yaml_structure("not a dict")
    
    def test_validate_yaml_structure_missing_prompts_key(self):
        """Test validation fails when 'prompts' key is missing."""
        manager = ContentManager()
        invalid_data = {'other_key': 'value'}
        
        with pytest.raises(ContentValidationError, match="YAML must contain 'prompts' key"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_prompts_not_list(self):
        """Test validation fails when 'prompts' is not a list."""
        manager = ContentManager()
        invalid_data = {'prompts': 'not a list'}
        
        with pytest.raises(ContentValidationError, match="'prompts' must be a list"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_empty_prompts(self):
        """Test validation fails when prompts list is empty."""
        manager = ContentManager()
        invalid_data = {'prompts': []}
        
        with pytest.raises(ContentValidationError, match="'prompts' list cannot be empty"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_prompt_not_dict(self):
        """Test validation fails when prompt item is not a dictionary."""
        manager = ContentManager()
        invalid_data = {'prompts': ['not a dict']}
        
        with pytest.raises(ContentValidationError, match="Prompt item 0 must be a dictionary"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        manager = ContentManager()
        invalid_data = {
            'prompts': [
                {
                    'id': 'test_001',
                    'prompt': 'What is AI?',
                    # Missing 'model' and 'response'
                }
            ]
        }
        
        with pytest.raises(ContentValidationError, match="missing required fields"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_non_string_fields(self):
        """Test validation fails when fields are not strings."""
        manager = ContentManager()
        invalid_data = {
            'prompts': [
                {
                    'id': 123,  # Should be string
                    'prompt': 'What is AI?',
                    'model': 'GPT-4',
                    'responses': ['AI is artificial intelligence.']
                }
            ]
        }
        
        with pytest.raises(ContentValidationError, match="must be a string"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_empty_fields(self):
        """Test validation fails when fields are empty strings."""
        manager = ContentManager()
        invalid_data = {
            'prompts': [
                {
                    'id': '',  # Empty string
                    'prompt': 'What is AI?',
                    'model': 'GPT-4',
                    'responses': ['AI is artificial intelligence.']
                }
            ]
        }
        
        with pytest.raises(ContentValidationError, match="cannot be empty"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_duplicate_ids(self):
        """Test validation fails when duplicate IDs exist."""
        manager = ContentManager()
        invalid_data = {
            'prompts': [
                {
                    'id': 'duplicate_id',
                    'prompt': 'First prompt',
                    'model': 'GPT-4',
                    'responses': ['First response']
                },
                {
                    'id': 'duplicate_id',  # Duplicate ID
                    'prompt': 'Second prompt',
                    'model': 'Claude-3',
                    'responses': ['Second response']
                }
            ]
        }
        
        with pytest.raises(ContentValidationError, match="Duplicate prompt IDs found"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_get_random_prompt_response_success(self):
        """Test getting random prompt when prompts are loaded."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            prompt = manager.get_random_prompt_response()
            assert isinstance(prompt, PromptData)
            assert prompt.id in ['test_001', 'test_002']
            
        finally:
            os.unlink(temp_file)
    
    def test_get_random_prompt_response_not_loaded(self):
        """Test getting random prompt when no prompts are loaded."""
        manager = ContentManager()
        
        with pytest.raises(RuntimeError, match="No prompts loaded"):
            manager.get_random_prompt_response()
    
    def test_get_prompt_by_id_success(self):
        """Test getting prompt by ID when it exists."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            prompt = manager.get_prompt_by_id('test_001')
            assert prompt is not None
            assert prompt.id == 'test_001'
            assert prompt.prompt == 'What is AI?'
            
        finally:
            os.unlink(temp_file)
    
    def test_get_prompt_by_id_not_found(self):
        """Test getting prompt by ID when it doesn't exist."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            prompt = manager.get_prompt_by_id('nonexistent')
            assert prompt is None
            
        finally:
            os.unlink(temp_file)
    
    def test_get_prompt_by_id_not_loaded(self):
        """Test getting prompt by ID when no prompts are loaded."""
        manager = ContentManager()
        
        with pytest.raises(RuntimeError, match="No prompts loaded"):
            manager.get_prompt_by_id('test_001')
    
    def test_get_all_prompts_success(self):
        """Test getting all prompts when loaded."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.valid_yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            prompts = manager.get_all_prompts()
            assert len(prompts) == 2
            assert all(isinstance(p, PromptData) for p in prompts)
            
            # Verify it returns a copy (not the original list)
            prompts.append(PromptData('new', 'new', 'new', ['new']))
            assert len(manager.get_all_prompts()) == 2
            
        finally:
            os.unlink(temp_file)
    
    def test_get_all_prompts_not_loaded(self):
        """Test getting all prompts when no prompts are loaded."""
        manager = ContentManager()
        
        with pytest.raises(RuntimeError, match="No prompts loaded"):
            manager.get_all_prompts()
    
    def test_whitespace_trimming(self):
        """Test that whitespace is properly trimmed from fields."""
        yaml_with_whitespace = {
            'prompts': [
                {
                    'id': '  test_001  ',
                    'prompt': '  What is AI?  ',
                    'model': '  GPT-4  ',
                    'responses': ['  AI is artificial intelligence.  ']
                }
            ]
        }
        
        yaml_content = yaml.dump(yaml_with_whitespace)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            prompt = manager.get_prompt_by_id('test_001')
            assert prompt is not None
            assert prompt.id == 'test_001'
            assert prompt.prompt == 'What is AI?'
            assert prompt.model == 'GPT-4'
            assert prompt.responses == ['AI is artificial intelligence.']
            
        finally:
            os.unlink(temp_file)
    
    
    def test_multi_response_selection_consistency(self):
        """Test that response selection is consistent within a prompt."""
        multi_response_yaml = {
            'prompts': [
                {
                    'id': 'multi_001',
                    'prompt': 'Generate a greeting',
                    'model': 'GPT-4',
                    'responses': ['Hello!', 'Hi there!', 'Greetings!', 'Hey!']
                }
            ]
        }
        
        yaml_content = yaml.dump(multi_response_yaml)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            prompt = manager.get_prompt_by_id('multi_001')
            assert len(prompt.responses) == 4
            
            # First call selects a response
            response1 = prompt.get_response()
            assert response1 in ['Hello!', 'Hi there!', 'Greetings!', 'Hey!']
            
            # Subsequent calls return the same response
            response2 = prompt.get_response()
            response3 = prompt.get_response()
            assert response1 == response2 == response3
            
            # Manual selection should update
            new_response = prompt.select_random_response()
            assert new_response in ['Hello!', 'Hi there!', 'Greetings!', 'Hey!']
            assert prompt.get_response() == new_response
            
        finally:
            os.unlink(temp_file)
    
    def test_get_random_prompt_response_selects_response(self):
        """Test that get_random_prompt_response selects a response."""
        yaml_data = {
            'prompts': [
                {
                    'id': 'auto_select_001',
                    'prompt': 'Generate a number',
                    'model': 'GPT-4',
                    'responses': ['One', 'Two', 'Three']
                }
            ]
        }
        
        yaml_content = yaml.dump(yaml_data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            manager = ContentManager(temp_file)
            manager.load_prompts_from_yaml()
            
            # get_random_prompt_response should automatically select a response
            prompt = manager.get_random_prompt_response()
            assert prompt.selected_response is not None
            assert prompt.selected_response in ['One', 'Two', 'Three']
            
        finally:
            os.unlink(temp_file)
    
    def test_validate_yaml_structure_empty_responses_array(self):
        """Test validation fails when responses array is empty."""
        manager = ContentManager()
        invalid_data = {
            'prompts': [
                {
                    'id': 'test_001',
                    'prompt': 'What is AI?',
                    'model': 'GPT-4',
                    'responses': []  # Empty array
                }
            ]
        }
        
        with pytest.raises(ContentValidationError, match="responses.*cannot be empty"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_responses_not_list(self):
        """Test validation fails when responses is not a list."""
        manager = ContentManager()
        invalid_data = {
            'prompts': [
                {
                    'id': 'test_001',
                    'prompt': 'What is AI?',
                    'model': 'GPT-4',
                    'responses': 'Single string instead of array'
                }
            ]
        }
        
        with pytest.raises(ContentValidationError, match="responses.*must be a list"):
            manager.validate_yaml_structure(invalid_data)
    
    def test_validate_yaml_structure_missing_responses_field(self):
        """Test validation fails when responses field is missing."""
        manager = ContentManager()
        invalid_data = {
            'prompts': [
                {
                    'id': 'test_001',
                    'prompt': 'What is AI?',
                    'model': 'GPT-4'
                    # Missing 'responses' field
                }
            ]
        }
        
        with pytest.raises(ContentValidationError, match="missing required fields"):
            manager.validate_yaml_structure(invalid_data)