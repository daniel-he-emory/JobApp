"""
Gemini API Client for AI-enhanced job application features

This module provides a client for interacting with Google's Gemini AI API
to support intelligent job relevance scoring, cover letter generation,
and resume optimization.
"""

import json
import logging
from typing import Dict, Any, Union
import asyncio

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    from google.api_core import exceptions as google_exceptions
except ImportError:
    genai = None
    google_exceptions = None
    HarmCategory = None
    HarmBlockThreshold = None


class GeminiError(Exception):
    """Custom exception for Gemini API errors"""
    pass


class GeminiClient:
    """
    Client for interacting with Google Gemini AI API
    
    Provides asynchronous content generation with robust error handling,
    JSON parsing capabilities, and token counting for cost management.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the Gemini client
        
        Args:
            api_key: Google AI API key for Gemini access
            
        Raises:
            GeminiError: If the google-generativeai library is not installed
        """
        if not genai:
            raise GeminiError(
                "google-generativeai library not installed. "
                "Run: pip install google-generativeai"
            )
        
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
        # Configure the API
        genai.configure(api_key=api_key)
        
        # Initialize the model with safety settings
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash-latest',
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
        
        self.logger.info("Gemini client initialized with model: gemini-1.5-flash-latest")
    
    async def generate_content(self, prompt: str, is_json: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Generate content using Gemini AI with async support
        
        Args:
            prompt: The input prompt for content generation
            is_json: If True, configures model for JSON output and parses response
            
        Returns:
            Generated content as string or parsed JSON dictionary
            Returns empty string or empty dict on failure
            
        Raises:
            Logs errors but doesn't raise exceptions for robust operation
        """
        try:
            if not prompt or not prompt.strip():
                self.logger.warning("Empty prompt provided to generate_content")
                return {} if is_json else ""
            
            # Configure generation parameters
            generation_config = {
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,
            }
            
            # Configure for JSON output if requested
            if is_json:
                generation_config.update({
                    'temperature': 0.3,  # Lower temperature for more consistent JSON
                    'response_mime_type': 'application/json'
                })
                # Add JSON instruction to prompt if not already present
                if 'json' not in prompt.lower():
                    prompt += "\n\nPlease respond with valid JSON only."
            
            self.logger.debug(f"Generating content with prompt length: {len(prompt)} chars")
            
            # Make async API call
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            # Check if response was blocked
            if not response.candidates:
                self.logger.warning("Content generation was blocked by safety filters")
                return {} if is_json else ""
            
            # Get the response text
            if not response.text:
                self.logger.warning("Empty response received from Gemini API")
                return {} if is_json else ""
            
            response_text = response.text.strip()
            
            # Parse JSON if requested
            if is_json:
                try:
                    # Clean up response text for JSON parsing
                    json_text = self._clean_json_response(response_text)
                    parsed_response = json.loads(json_text)
                    self.logger.debug("Successfully parsed JSON response")
                    return parsed_response
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON response: {e}")
                    self.logger.debug(f"Raw response: {response_text[:500]}...")
                    return {}
            
            self.logger.debug(f"Generated content length: {len(response_text)} chars")
            return response_text
            
        except google_exceptions.ResourceExhausted as e:
            self.logger.error(f"Gemini API quota exceeded: {e}")
            return {} if is_json else ""
        
        except google_exceptions.InvalidArgument as e:
            self.logger.error(f"Invalid request to Gemini API: {e}")
            return {} if is_json else ""
        
        except google_exceptions.PermissionDenied as e:
            self.logger.error(f"Permission denied for Gemini API: {e}")
            return {} if is_json else ""
        
        except google_exceptions.DeadlineExceeded as e:
            self.logger.error(f"Gemini API request timeout: {e}")
            return {} if is_json else ""
        
        except Exception as e:
            self.logger.error(f"Unexpected error in content generation: {e}")
            return {} if is_json else ""
    
    def _clean_json_response(self, response_text: str) -> str:
        """
        Clean and prepare response text for JSON parsing
        
        Args:
            response_text: Raw response from Gemini API
            
        Returns:
            Cleaned text ready for JSON parsing
        """
        # Remove markdown code blocks if present
        if '```json' in response_text:
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            if end != -1:
                response_text = response_text[start:end].strip()
        elif '```' in response_text:
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            if end != -1:
                response_text = response_text[start:end].strip()
        
        # Remove any leading/trailing non-JSON text
        start_bracket = response_text.find('{')
        end_bracket = response_text.rfind('}')
        
        if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
            response_text = response_text[start_bracket:end_bracket + 1]
        
        return response_text.strip()
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text for cost estimation
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens, or 0 if counting fails
        """
        try:
            if not text:
                return 0
                
            result = self.model.count_tokens(text)
            token_count = result.total_tokens
            
            self.logger.debug(f"Token count for text ({len(text)} chars): {token_count}")
            return token_count
            
        except Exception as e:
            self.logger.error(f"Error counting tokens: {e}")
            # Fallback estimation: roughly 4 characters per token
            estimated_tokens = len(text) // 4
            self.logger.debug(f"Using fallback token estimation: {estimated_tokens}")
            return estimated_tokens
    
    async def generate_with_retry(self, prompt: str, is_json: bool = False, 
                                max_retries: int = 3, delay: float = 1.0) -> Union[str, Dict[str, Any]]:
        """
        Generate content with automatic retry on transient failures
        
        Args:
            prompt: The input prompt for content generation
            is_json: If True, expects JSON response
            max_retries: Maximum number of retry attempts
            delay: Base delay between retries (exponential backoff)
            
        Returns:
            Generated content or empty response on failure
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await self.generate_content(prompt, is_json)
                
                # Check if we got a valid response
                if is_json and isinstance(result, dict) and result:
                    return result
                elif not is_json and isinstance(result, str) and result.strip():
                    return result
                
                # If we got an empty response, it might be a transient issue
                if attempt < max_retries:
                    wait_time = delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(f"Empty response on attempt {attempt + 1}, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = delay * (2 ** attempt)
                    self.logger.warning(f"Error on attempt {attempt + 1}: {e}, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
        
        self.logger.error(f"Failed to generate content after {max_retries + 1} attempts. Last error: {last_error}")
        return {} if is_json else ""
    
    def get_model_info(self) -> Dict[str, str]:
        """
        Get information about the current model
        
        Returns:
            Dictionary with model information
        """
        return {
            'model_name': 'gemini-1.5-flash-latest',
            'api_key_configured': bool(self.api_key),
            'client_status': 'ready'
        }


def create_gemini_client_from_config(config: Dict[str, Any]) -> GeminiClient:
    """
    Create a Gemini client from configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured GeminiClient instance or None if not configured
        
    Raises:
        GeminiError: If configuration is invalid
    """
    gemini_config = config.get('gemini', {})
    api_key = gemini_config.get('api_key', '')
    
    if not api_key or api_key == 'your_gemini_api_key_here':
        raise GeminiError("Gemini API key not configured in config.yaml")
    
    try:
        client = GeminiClient(api_key)
        logging.getLogger(__name__).info("Gemini client created successfully from config")
        return client
    except Exception as e:
        raise GeminiError(f"Failed to create Gemini client: {str(e)}")