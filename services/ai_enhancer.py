"""
AI Enhancement Service Layer

This module provides the AIEnhancer class that serves as a bridge between
the core application and AI utilities for intelligent job application features.
"""

import json
import logging
from typing import Dict, Any

from base_agent import JobPosting
from utils.gemini_client import GeminiClient


class AIEnhancementError(Exception):
    """Custom exception for AI enhancement errors"""
    pass


class AIEnhancer:
    """
    AI Enhancement service that provides intelligent job application features

    Acts as a bridge between the core application and AI utilities,
    providing job relevance scoring, cover letter generation, and resume optimization.
    """

    def __init__(self, gemini_client: GeminiClient, structured_resume: Dict[str, Any],
                 config: Dict[str, Any]):
        """
        Initialize the AI enhancer service

        Args:
            gemini_client: Configured Gemini AI client
            structured_resume: Parsed resume data from ResumeParser
            config: Main configuration dictionary containing prompt templates
        """
        self.gemini_client = gemini_client
        self.structured_resume = structured_resume
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Validate prompt templates
        self.prompts = config.get('prompts', {})
        if not self.prompts:
            raise AIEnhancementError(
                "No prompt templates found in configuration")

        # Validate structured resume
        if not structured_resume or not isinstance(structured_resume, dict):
            raise AIEnhancementError("Invalid structured resume data provided")

        self.logger.info("AI enhancer initialized with resume for: %s",
                         structured_resume.get('full_name', 'Unknown'))

    async def score_job_relevance(self, job_posting: JobPosting) -> Dict[str, Any]:
        """
        Score job relevance using AI analysis

        Args:
            job_posting: Job posting object with description and details

        Returns:
            Dictionary with 'score' (1-10) and 'reasoning' fields

        Raises:
            AIEnhancementError: If scoring fails or returns invalid data
        """
        try:
            # Get prompt template
            prompt_template = self.prompts.get('score_job_relevance')
            if not prompt_template:
                raise AIEnhancementError(
                    "score_job_relevance prompt template not found in config")

            # Prepare job description
            job_description = self._extract_job_description(job_posting)

            # Prepare user profile from structured resume
            user_profile = self._format_resume_for_prompt()

            # Replace placeholders in prompt
            prompt = prompt_template.replace(
                '[JOB_DESCRIPTION]', job_description)
            prompt = prompt.replace('[USER_PROFILE]', user_profile)

            self.logger.debug("Scoring job relevance for: %s at %s",
                              job_posting.title, job_posting.company)

            # Generate AI response
            result = await self.gemini_client.generate_content(prompt, is_json=True)

            # Validate response structure
            if not isinstance(result, dict):
                raise AIEnhancementError(
                    "AI returned invalid response format for job scoring")

            # Validate required fields
            if 'score' not in result or 'reasoning' not in result:
                raise AIEnhancementError(
                    "AI response missing required fields: score, reasoning")

            # Validate score is numeric and in range
            try:
                score = int(result['score'])
                if not (1 <= score <= 10):
                    raise ValueError("Score out of range")
                result['score'] = score
            except (ValueError, TypeError):
                raise AIEnhancementError(
                    f"Invalid score value: {result.get('score')}")

            # Ensure reasoning is a string
            if not isinstance(result['reasoning'], str):
                result['reasoning'] = str(result['reasoning'])

            self.logger.info("Job relevance scored: %d/10 for %s",
                             result['score'], job_posting.title)

            return result

        except Exception as e:
            if isinstance(e, AIEnhancementError):
                raise
            else:
                raise AIEnhancementError(
                    f"Error scoring job relevance: {str(e)}")

    async def generate_cover_letter(self, job_posting: JobPosting) -> str:
        """
        Generate personalized cover letter using AI

        Args:
            job_posting: Job posting object with description and details

        Returns:
            Generated cover letter as a string

        Raises:
            AIEnhancementError: If generation fails or returns invalid data
        """
        try:
            # Get prompt template
            prompt_template = self.prompts.get('generate_cover_letter')
            if not prompt_template:
                raise AIEnhancementError(
                    "generate_cover_letter prompt template not found in config")

            # Prepare job description
            job_description = self._extract_job_description(job_posting)

            # Prepare user profile from structured resume
            user_profile = self._format_resume_for_prompt()

            # Replace placeholders in prompt
            prompt = prompt_template.replace(
                '[JOB_DESCRIPTION]', job_description)
            prompt = prompt.replace('[USER_PROFILE]', user_profile)

            self.logger.debug("Generating cover letter for: %s at %s",
                              job_posting.title, job_posting.company)

            # Generate AI response
            cover_letter = await self.gemini_client.generate_content(prompt, is_json=False)

            # Validate response
            if not isinstance(cover_letter, str) or not cover_letter.strip():
                raise AIEnhancementError(
                    "AI returned empty or invalid cover letter")

            # Clean up the cover letter
            cover_letter = cover_letter.strip()

            self.logger.info("Generated cover letter (%d chars) for %s",
                             len(cover_letter), job_posting.title)

            return cover_letter

        except Exception as e:
            if isinstance(e, AIEnhancementError):
                raise
            else:
                raise AIEnhancementError(
                    f"Error generating cover letter: {str(e)}")

    async def optimize_resume_section(self, job_posting: JobPosting,
                                      resume_section_text: str) -> str:
        """
        Optimize resume section text for better job matching

        Args:
            job_posting: Job posting object with description and details
            resume_section_text: Text of resume section to optimize

        Returns:
            Optimized resume section text

        Raises:
            AIEnhancementError: If optimization fails or returns invalid data
        """
        try:
            # Get prompt template
            prompt_template = self.prompts.get('optimize_resume_keywords')
            if not prompt_template:
                raise AIEnhancementError(
                    "optimize_resume_keywords prompt template not found in config")

            # Validate input
            if not resume_section_text or not resume_section_text.strip():
                raise AIEnhancementError("Resume section text cannot be empty")

            # Prepare job description
            job_description = self._extract_job_description(job_posting)

            # Replace placeholders in prompt
            prompt = prompt_template.replace(
                '[JOB_DESCRIPTION]', job_description)
            prompt = prompt.replace(
                '[RESUME_SECTION]', resume_section_text.strip())

            self.logger.debug("Optimizing resume section (%d chars) for: %s",
                              len(resume_section_text), job_posting.title)

            # Generate AI response
            result = await self.gemini_client.generate_content(prompt, is_json=True)

            # Validate response structure
            if not isinstance(result, dict):
                raise AIEnhancementError(
                    "AI returned invalid response format for resume optimization")

            # Extract optimized text
            optimized_text = result.get('optimized_text')
            if not optimized_text or not isinstance(optimized_text, str):
                raise AIEnhancementError(
                    "AI response missing or invalid 'optimized_text' field")

            optimized_text = optimized_text.strip()

            if not optimized_text:
                raise AIEnhancementError("AI returned empty optimized text")

            self.logger.info("Optimized resume section: %d -> %d chars for %s",
                             len(resume_section_text), len(optimized_text), job_posting.title)

            return optimized_text

        except Exception as e:
            if isinstance(e, AIEnhancementError):
                raise
            else:
                raise AIEnhancementError(
                    f"Error optimizing resume section: {str(e)}")

    def _extract_job_description(self, job_posting: JobPosting) -> str:
        """
        Extract comprehensive job description from JobPosting object

        Args:
            job_posting: Job posting object

        Returns:
            Formatted job description string
        """
        description_parts = []

        # Add basic job info
        description_parts.append(f"Job Title: {job_posting.title}")
        description_parts.append(f"Company: {job_posting.company}")

        if job_posting.location:
            description_parts.append(f"Location: {job_posting.location}")

        if job_posting.salary:
            description_parts.append(f"Salary: {job_posting.salary}")

        # Add main description
        if job_posting.description:
            description_parts.append(
                f"Job Description:\n{job_posting.description}")
        else:
            # Fallback if no detailed description
            description_parts.append(
                f"Job Description: {job_posting.title} position at {job_posting.company}")

        return "\n\n".join(description_parts)

    def _format_resume_for_prompt(self) -> str:
        """
        Format structured resume data for AI prompts

        Returns:
            Formatted resume string for AI consumption
        """
        try:
            profile_parts = []

            # Add personal info
            if self.structured_resume.get('full_name'):
                profile_parts.append(
                    f"Name: {self.structured_resume['full_name']}")

            # Add contact info
            contact_info = self.structured_resume.get('contact_info', {})
            if contact_info.get('email'):
                profile_parts.append(f"Email: {contact_info['email']}")
            if contact_info.get('phone'):
                profile_parts.append(f"Phone: {contact_info['phone']}")
            if contact_info.get('location'):
                profile_parts.append(f"Location: {contact_info['location']}")

            # Add summary
            if self.structured_resume.get('summary'):
                profile_parts.append(
                    f"Professional Summary:\n{self.structured_resume['summary']}")

            # Add skills
            skills = self.structured_resume.get('skills', [])
            if skills:
                profile_parts.append(f"Skills: {', '.join(skills)}")

            # Add experience
            experience = self.structured_resume.get('experience', [])
            if experience:
                exp_parts = []
                for exp in experience:
                    exp_text = f"• {exp.get('title', 'Unknown Title')} at {exp.get('company', 'Unknown Company')}"
                    if exp.get('duration'):
                        exp_text += f" ({exp['duration']})"
                    if exp.get('responsibilities'):
                        if isinstance(exp['responsibilities'], list):
                            responsibilities = '; '.join(
                                exp['responsibilities'])
                        else:
                            responsibilities = str(exp['responsibilities'])
                        exp_text += f"\n  Responsibilities: {responsibilities}"
                    exp_parts.append(exp_text)
                profile_parts.append(
                    f"Work Experience:\n" + "\n".join(exp_parts))

            # Add education
            education = self.structured_resume.get('education', [])
            if education:
                edu_parts = []
                for edu in education:
                    edu_text = f"• {edu.get('degree', 'Unknown Degree')}"
                    if edu.get('institution'):
                        edu_text += f" from {edu['institution']}"
                    if edu.get('year'):
                        edu_text += f" ({edu['year']})"
                    if edu.get('gpa'):
                        edu_text += f" - GPA: {edu['gpa']}"
                    edu_parts.append(edu_text)
                profile_parts.append(f"Education:\n" + "\n".join(edu_parts))

            return "\n\n".join(profile_parts)

        except Exception as e:
            self.logger.error(f"Error formatting resume for prompt: {e}")
            # Fallback to JSON representation
            return json.dumps(self.structured_resume, indent=2)

    def get_enhancement_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the AI enhancer capabilities

        Returns:
            Dictionary with enhancer information
        """
        return {
            'resume_loaded': bool(self.structured_resume),
            'candidate_name': self.structured_resume.get('full_name', 'Unknown'),
            'available_prompts': list(self.prompts.keys()),
            'gemini_model': self.gemini_client.get_model_info().get('model_name', 'Unknown')
        }


def create_ai_enhancer_from_config(config: Dict[str, Any], gemini_client: GeminiClient,
                                   structured_resume: Dict[str, Any]) -> AIEnhancer:
    """
    Create an AI enhancer from configuration and dependencies

    Args:
        config: Main configuration dictionary
        gemini_client: Configured Gemini client
        structured_resume: Parsed resume data

    Returns:
        Configured AIEnhancer instance

    Raises:
        AIEnhancementError: If configuration or dependencies are invalid
    """
    try:
        enhancer = AIEnhancer(gemini_client, structured_resume, config)
        logging.getLogger(__name__).info("AI enhancer created successfully")
        return enhancer
    except Exception as e:
        raise AIEnhancementError(f"Failed to create AI enhancer: {str(e)}")
