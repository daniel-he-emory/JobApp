"""
Resume Parsing and Caching Utility

This module provides functionality to extract structured data from resume files
using AI parsing with intelligent caching for efficiency.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from .gemini_client import GeminiClient


class ResumeParsingError(Exception):
    """Custom exception for resume parsing errors"""
    pass


class ResumeParser:
    """
    Resume parser that extracts structured data from PDF files
    using AI parsing with intelligent caching for performance
    """
    
    def __init__(self, config: Dict[str, Any], gemini_client: GeminiClient):
        """
        Initialize the resume parser
        
        Args:
            config: Configuration dictionary containing resume path
            gemini_client: Configured Gemini AI client for parsing
        """
        self.config = config
        self.gemini_client = gemini_client
        self.logger = logging.getLogger(__name__)
        
        # Define cache file path
        self.cache_path = Path("/home/daniel/JobApp/data/resume_cache.json")
        
        # Ensure data directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Validate dependencies
        if not PyPDF2:
            raise ResumeParsingError(
                "PyPDF2 library not installed. Run: pip install PyPDF2"
            )
        
        self.logger.info("Resume parser initialized with cache at: %s", self.cache_path)
    
    def _read_resume_file(self) -> str:
        """
        Read resume file and extract text content
        
        Returns:
            Full text content of the resume as a single string
            
        Raises:
            ResumeParsingError: If file cannot be read or is in unsupported format
        """
        try:
            # Get resume path from config
            resume_path = self.config.get('application', {}).get('resume_path', '')
            
            if not resume_path:
                raise ResumeParsingError("Resume path not configured in application.resume_path")
            
            resume_file = Path(resume_path)
            
            if not resume_file.exists():
                raise ResumeParsingError(f"Resume file not found: {resume_path}")
            
            # Check file extension
            file_extension = resume_file.suffix.lower()
            
            if file_extension == '.pdf':
                return self._extract_pdf_text(resume_file)
            else:
                raise ResumeParsingError(
                    f"Unsupported file format: {file_extension}. "
                    "Currently only PDF files are supported."
                )
                
        except Exception as e:
            if isinstance(e, ResumeParsingError):
                raise
            else:
                raise ResumeParsingError(f"Error reading resume file: {str(e)}")
    
    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text from PDF file using PyPDF2
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
            
        Raises:
            ResumeParsingError: If PDF cannot be processed
        """
        try:
            text_content = []
            
            with open(pdf_path, 'rb') as file:
                # Create PDF reader object
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Check if PDF is encrypted
                if pdf_reader.is_encrypted:
                    # Try to decrypt with empty password
                    if not pdf_reader.decrypt(""):
                        raise ResumeParsingError(
                            "PDF is password-protected and cannot be read"
                        )
                
                # Extract text from all pages
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(page_text)
                            self.logger.debug(f"Extracted text from page {page_num + 1}")
                    except Exception as e:
                        self.logger.warning(f"Could not extract text from page {page_num + 1}: {e}")
                        continue
                
                if not text_content:
                    raise ResumeParsingError("No text content could be extracted from PDF")
                
                # Combine all pages with proper spacing
                full_text = '\n\n'.join(text_content)
                
                self.logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
                return full_text
                
        except Exception as e:
            if isinstance(e, ResumeParsingError):
                raise
            else:
                raise ResumeParsingError(f"Error processing PDF file: {str(e)}")
    
    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """
        Load cached resume data if available
        
        Returns:
            Cached resume data or None if cache doesn't exist or is invalid
        """
        try:
            if not self.cache_path.exists():
                self.logger.debug("Resume cache file does not exist")
                return None
            
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Validate cache structure
            if not isinstance(cached_data, dict):
                self.logger.warning("Invalid cache format, ignoring cache")
                return None
            
            # Check if cache has basic expected structure
            required_keys = ['full_name', 'contact_info', 'skills']
            if not any(key in cached_data for key in required_keys):
                self.logger.warning("Cache appears to be empty or malformed, ignoring cache")
                return None
            
            self.logger.info("Loaded resume data from cache")
            return cached_data
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Cache file is corrupted, ignoring cache: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Error loading cache: {e}")
            return None
    
    def _save_cache(self, resume_data: Dict[str, Any]) -> None:
        """
        Save resume data to cache file
        
        Args:
            resume_data: Structured resume data to cache
        """
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(resume_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info("Resume data saved to cache")
            
        except Exception as e:
            self.logger.error(f"Error saving cache: {e}")
            # Don't raise exception for cache save failures
    
    async def get_structured_resume(self) -> Dict[str, Any]:
        """
        Get structured resume data with caching
        
        Returns:
            Dictionary containing structured resume data with keys:
            - full_name: str
            - contact_info: dict with email, phone
            - summary: str
            - skills: list of strings
            - experience: list of dicts with title, company, duration, responsibilities
            - education: list of dicts
            
        Raises:
            ResumeParsingError: If resume cannot be parsed or processed
        """
        try:
            # Step 1: Check cache first
            cached_data = self._load_cache()
            if cached_data:
                return cached_data
            
            self.logger.info("No valid cache found, parsing resume with AI")
            
            # Step 2: Read resume file
            resume_text = self._read_resume_file()
            
            if not resume_text.strip():
                raise ResumeParsingError("Resume file appears to be empty")
            
            # Step 3: Create AI parsing prompt
            prompt = self._create_parsing_prompt(resume_text)
            
            # Step 4: Get structured data from AI
            self.logger.info("Sending resume to AI for structured parsing...")
            structured_data = await self.gemini_client.generate_content(prompt, is_json=True)
            
            # Step 5: Validate AI response
            if not structured_data or not isinstance(structured_data, dict):
                raise ResumeParsingError("AI parsing failed to return valid structured data")
            
            # Step 6: Validate required fields
            self._validate_structured_data(structured_data)
            
            # Step 7: Save to cache
            self._save_cache(structured_data)
            
            self.logger.info("Resume successfully parsed and cached")
            return structured_data
            
        except Exception as e:
            if isinstance(e, ResumeParsingError):
                raise
            else:
                raise ResumeParsingError(f"Error getting structured resume: {str(e)}")
    
    def _create_parsing_prompt(self, resume_text: str) -> str:
        """
        Create AI prompt for resume parsing
        
        Args:
            resume_text: Raw text from resume file
            
        Returns:
            Formatted prompt for AI parsing
        """
        prompt = """Please parse the following resume text and return a structured JSON object with the following keys:

- 'full_name': The person's full name as a string
- 'contact_info': An object with sub-keys:
  - 'email': Email address if found
  - 'phone': Phone number if found  
  - 'location': City/state/country if found
- 'summary': Professional summary or objective (if present)
- 'skills': Array of technical and professional skills
- 'experience': Array of work experience objects, each with:
  - 'title': Job title
  - 'company': Company name
  - 'duration': Time period (e.g., "2020-2023")
  - 'responsibilities': Array of key responsibilities/achievements
- 'education': Array of education objects, each with:
  - 'degree': Degree type and field
  - 'institution': School/university name
  - 'year': Graduation year or time period
  - 'gpa': GPA if mentioned

Please extract as much relevant information as possible. If a field is not found, include it with an appropriate empty value (empty string for strings, empty array for arrays).

Resume Text:
""" + resume_text

        return prompt
    
    def _validate_structured_data(self, data: Dict[str, Any]) -> None:
        """
        Validate that structured data has required fields
        
        Args:
            data: Structured resume data from AI
            
        Raises:
            ResumeParsingError: If required fields are missing
        """
        required_fields = [
            'full_name', 'contact_info', 'summary', 
            'skills', 'experience', 'education'
        ]
        
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            self.logger.warning(f"AI response missing fields: {missing_fields}")
            # Add empty values for missing fields
            for field in missing_fields:
                if field == 'contact_info':
                    data[field] = {'email': '', 'phone': '', 'location': ''}
                elif field in ['skills', 'experience', 'education']:
                    data[field] = []
                else:
                    data[field] = ''
        
        # Validate contact_info structure
        if 'contact_info' in data and isinstance(data['contact_info'], dict):
            contact_fields = ['email', 'phone', 'location']
            for field in contact_fields:
                if field not in data['contact_info']:
                    data['contact_info'][field] = ''
    
    def clear_cache(self) -> bool:
        """
        Clear the resume cache file
        
        Returns:
            True if cache was cleared successfully, False otherwise
        """
        try:
            if self.cache_path.exists():
                self.cache_path.unlink()
                self.logger.info("Resume cache cleared")
                return True
            else:
                self.logger.info("No cache file to clear")
                return True
                
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the cache status
        
        Returns:
            Dictionary with cache information
        """
        cache_exists = self.cache_path.exists()
        cache_size = 0
        cache_modified = None
        
        if cache_exists:
            try:
                stat = self.cache_path.stat()
                cache_size = stat.st_size
                cache_modified = stat.st_mtime
            except Exception:
                pass
        
        return {
            'cache_exists': cache_exists,
            'cache_path': str(self.cache_path),
            'cache_size_bytes': cache_size,
            'cache_modified_timestamp': cache_modified
        }


def create_resume_parser_from_config(config: Dict[str, Any], 
                                   gemini_client: GeminiClient) -> ResumeParser:
    """
    Create a resume parser from configuration
    
    Args:
        config: Configuration dictionary
        gemini_client: Configured Gemini client
        
    Returns:
        Configured ResumeParser instance
        
    Raises:
        ResumeParsingError: If configuration is invalid
    """
    try:
        parser = ResumeParser(config, gemini_client)
        logging.getLogger(__name__).info("Resume parser created successfully from config")
        return parser
    except Exception as e:
        raise ResumeParsingError(f"Failed to create resume parser: {str(e)}")