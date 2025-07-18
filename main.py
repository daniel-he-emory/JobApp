#!/usr/bin/env python3
"""
Autonomous Job Application Agent - Main Orchestrator

This script coordinates the entire job application process across multiple platforms.
It manages configuration, state tracking, and execution of platform-specific agents.

Usage:
    python main.py [--config CONFIG_PATH] [--platforms PLATFORM1,PLATFORM2] [--max-apps MAX]

Example:
    python main.py --platforms linkedin,wellfound --max-apps 10
"""

from agents.wellfound_agent import WellfoundAgent
from agents.linkedin_agent import LinkedInAgent
from base_agent import SearchCriteria, JobPosting
from services.ai_enhancer import create_ai_enhancer_from_config
from utils.resume_parser import create_resume_parser_from_config
from utils.gemini_client import create_gemini_client_from_config
from utils.google_sheets_reporter import GoogleSheetsReporter
from utils.state_manager import StateManager
from config.config_loader import ConfigLoader
import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any
import traceback

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


# Import additional agents as they're implemented


class JobApplicationOrchestrator:
    """
    Main orchestrator for the job application automation system
    Manages configuration, agents, and provides execution coordination
    """

    def __init__(self, config_path: str = "config/config.yaml", dry_run: bool = False, validate_config: bool = True):
        self.dry_run = dry_run
        self.config_loader = ConfigLoader(config_path, validate=validate_config)
        self.config = self.config_loader.load_config()
        self.state_manager = self._init_state_manager()
        self.logger = self._setup_logging()

        # AI services (initialized in async factory)
        self.gemini_client = None
        self.resume_parser = None
        self.ai_enhancer = None
        self.structured_resume = None

        # Available agents
        self.available_agents = {
            'linkedin': LinkedInAgent,
            'wellfound': WellfoundAgent,
        }

    @classmethod
    async def create(cls, config_path: str = "config/config.yaml", dry_run: bool = False,
                     enable_ai: bool = True) -> 'JobApplicationOrchestrator':
        """
        Async factory method to create orchestrator with AI services

        Args:
            config_path: Path to configuration file
            dry_run: Whether to run in simulation mode
            enable_ai: Whether to initialize AI services

        Returns:
            Fully initialized orchestrator instance
        """
        # Create basic orchestrator
        orchestrator = cls(config_path, dry_run)

        if enable_ai and not dry_run:
            try:
                # Initialize AI services
                await orchestrator._init_ai_services()
                orchestrator.logger.info(
                    "AI services initialized successfully")
            except Exception as e:
                orchestrator.logger.warning(
                    f"AI services initialization failed: {e}")
                orchestrator.logger.info("Continuing without AI enhancements")

        return orchestrator

    async def _init_ai_services(self) -> None:
        """Initialize AI enhancement services"""
        try:
            # Initialize Gemini client
            self.gemini_client = create_gemini_client_from_config(self.config)

            # Initialize resume parser
            self.resume_parser = create_resume_parser_from_config(
                self.config, self.gemini_client)

            # Get structured resume data
            self.structured_resume = await self.resume_parser.get_structured_resume()

            # Initialize AI enhancer
            self.ai_enhancer = create_ai_enhancer_from_config(
                self.config, self.gemini_client, self.structured_resume
            )

            self.logger.info("AI services ready for candidate: %s",
                             self.structured_resume.get('full_name', 'Unknown'))

        except Exception as e:
            self.logger.error(f"Failed to initialize AI services: {e}")
            raise

    def _init_state_manager(self) -> StateManager:
        """Initialize state management system"""
        state_config = self.config.get('state', {})
        storage_type = state_config.get('storage_type', 'sqlite')
        database_path = state_config.get(
            'database_path', './data/job_applications.db')

        # Ensure data directory exists
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        return StateManager(storage_type=storage_type, file_path=database_path)

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_file = log_config.get('log_file', './logs/job_agent.log')

        # Ensure logs directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

        return logging.getLogger(__name__)

    async def _simulate_agent_run(self, platform_name: str, search_criteria: SearchCriteria,
                                  max_applications: int, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Simulate agent run for dry run mode"""
        import random

        print(f"\n🔍 DRY RUN: {platform_name} Agent Simulation")
        print("=" * 50)

        # Simulate credential validation
        if not credentials or not credentials.get('email'):
            print(f"❌ {platform_name} credentials not configured")
            return {
                'platform': platform_name,
                'jobs_found': 0,
                'applications_submitted': 0,
                'errors': 1,
                'applied_jobs': [],
                'error_message': 'No credentials configured'
            }

        print(
            f"✅ {platform_name} credentials configured ({credentials['email'][:3]}***)")

        # Simulate search criteria
        print("\n📋 Search Configuration:")
        print(f"   Keywords: {search_criteria.keywords}")
        print(f"   Locations: {search_criteria.locations}")
        print(f"   Date posted: {search_criteria.date_posted}")
        print(f"   Easy Apply only: {search_criteria.easy_apply_only}")

        # Simulate finding jobs
        simulated_jobs_found = random.randint(3, 15)
        print(
            f"\n🔍 Would search {platform_name} and find: {simulated_jobs_found} jobs")

        # Simulate filtering existing applications
        existing_applications = random.randint(0, 3)
        available_jobs = simulated_jobs_found - existing_applications
        if existing_applications > 0:
            print(
                f"⏭️  Would skip {existing_applications} jobs (already applied)")

        # Simulate applications
        jobs_to_apply = min(available_jobs, max_applications)
        successful_applications = random.randint(
            max(0, jobs_to_apply - 1), jobs_to_apply)
        failed_applications = jobs_to_apply - successful_applications

        print(f"\n📝 Would attempt to apply to: {jobs_to_apply} jobs")
        print(f"   Successful applications: {successful_applications}")
        if failed_applications > 0:
            print(f"   Failed applications: {failed_applications}")

        # Generate simulated job titles
        sample_titles = [
            "Senior Software Engineer", "Developer Advocate", "Solutions Engineer",
            "Forward Deployed Engineer", "Technical Account Manager", "Product Engineer",
            "Staff Software Engineer", "Senior Frontend Developer", "Backend Engineer"
        ]

        applied_jobs = []
        for i in range(successful_applications):
            job_title = random.choice(sample_titles)
            company = f"AI Startup {chr(65 + i)}"
            applied_jobs.append({
                'title': job_title,
                'company': company,
                'url': f"https://{platform_name.lower()}.com/jobs/example-{i+1}"
            })
            print(f"   ✅ Would apply: {job_title} at {company}")

        print(f"\n📊 {platform_name} Simulation Summary:")
        print(f"   Jobs found: {simulated_jobs_found}")
        print(f"   Applications submitted: {successful_applications}")
        print(f"   Errors: {failed_applications}")

        return {
            'platform': platform_name,
            'jobs_found': simulated_jobs_found,
            'applications_submitted': successful_applications,
            'errors': failed_applications,
            'applied_jobs': applied_jobs
        }

    def get_search_criteria(self) -> SearchCriteria:
        """Build search criteria from configuration"""
        search_config = self.config.get('search_settings', {})

        return SearchCriteria(
            keywords=search_config.get(
                'default_keywords', ['Software Engineer']),
            locations=search_config.get('default_locations', ['Remote']),
            experience_level=search_config.get('experience_levels', [None])[0],
            date_posted=search_config.get('date_posted', 'Past week'),
            easy_apply_only=search_config.get('easy_apply_only', True),
            remote_options=search_config.get('remote_options', 'Remote')
        )

    def get_enabled_platforms(self, requested_platforms: List[str] = None) -> List[str]:
        """Get list of enabled platforms"""
        platform_config = self.config.get('platforms', {})

        enabled_platforms = []
        for platform_name, agent_class in self.available_agents.items():
            # Check if platform is enabled in config
            platform_enabled = platform_config.get(
                platform_name, {}).get('enabled', True)

            # Check if platform credentials are available
            credentials = self.config_loader.get_credentials(platform_name)
            has_credentials = credentials and credentials.get(
                'email') and credentials.get('password')

            # Include platform if enabled, has credentials, and is requested (if specified)
            if platform_enabled and has_credentials:
                if requested_platforms is None or platform_name in requested_platforms:
                    enabled_platforms.append(platform_name)

        return enabled_platforms

    async def run_agent(self, platform_name: str, search_criteria: SearchCriteria,
                        max_applications: int) -> Dict[str, Any]:
        """Run a specific platform agent with AI-enhanced job filtering and content generation"""
        try:
            agent_class = self.available_agents[platform_name]
            credentials = self.config_loader.get_credentials(platform_name)
            proxy_config = self.config_loader.get_proxy_config()

            self.logger.info(f"Starting {platform_name} agent")

            # Handle dry run mode
            if self.dry_run:
                return await self._simulate_agent_run(platform_name, search_criteria, max_applications, credentials)

            # Initialize agent
            agent = agent_class(self.config, proxy_config)

            # Check if AI services are available
            ai_enabled = self.ai_enhancer is not None
            if ai_enabled:
                self.logger.info(
                    "AI services enabled - using intelligent job filtering and content generation")
                return await self._run_agent_with_ai(agent, platform_name, search_criteria, max_applications)
            else:
                self.logger.info(
                    "AI services not available - using standard automation")
                return await self._run_agent_standard(agent, platform_name, search_criteria, max_applications)

        except Exception as e:
            self.logger.error(f"Error running {platform_name} agent: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                'platform': platform_name,
                'jobs_found': 0,
                'applications_submitted': 0,
                'errors': 1,
                'applied_jobs': [],
                'error_message': str(e)
            }

    async def _run_agent_with_ai(self, agent, platform_name: str, search_criteria: SearchCriteria,
                                 max_applications: int) -> Dict[str, Any]:
        """Run agent with AI-enhanced job filtering and content generation"""
        summary = {
            'platform': platform_name,
            'jobs_found': 0,
            'applications_submitted': 0,
            'errors': 0,
            'applied_jobs': [],
            'ai_filtered_jobs': 0,
            'ai_generated_content': 0
        }

        try:
            # Initialize agent browser
            await agent.initialize_browser()

            # Login to platform
            login_success = await agent.login()
            if not login_success:
                raise Exception("Login failed")

            # Search for jobs
            self.logger.info("Searching for jobs...")
            jobs = await agent.search_jobs(search_criteria)
            summary['jobs_found'] = len(jobs)

            if not jobs:
                self.logger.info("No jobs found matching criteria")
                return summary

            # Filter out already applied jobs
            new_jobs = []
            for job in jobs:
                if not self.state_manager.has_applied(job.job_id, platform_name):
                    new_jobs.append(job)
                else:
                    self.logger.debug(
                        f"Skipping already applied job: {job.title} at {job.company}")

            if not new_jobs:
                self.logger.info("All found jobs have already been applied to")
                return summary

            # Get AI filtering threshold from config
            ai_score_threshold = self.config.get(
                'ai', {}).get('relevance_threshold', 6)

            # Process jobs with AI filtering and content generation
            qualified_jobs = []
            applications_submitted = 0

            # Check more jobs than we plan to apply to
            for job in new_jobs[:max_applications * 3]:
                try:
                    # Score job relevance
                    self.logger.info(
                        f"Analyzing job relevance: {job.title} at {job.company}")
                    relevance_result = await self.ai_enhancer.score_job_relevance(job)

                    score = relevance_result.get('score', 0)
                    reasoning = relevance_result.get(
                        'reasoning', 'No reasoning provided')

                    self.logger.info(
                        f"Job relevance score: {score}/10 - {reasoning}")

                    if score >= ai_score_threshold:
                        self.logger.info(
                            f"Job passed AI filter (score: {score} >= {ai_score_threshold})")

                        # Generate AI content for this job
                        ai_content = await self._generate_ai_content(job)

                        # Add to qualified jobs with AI content
                        qualified_jobs.append({
                            'job': job,
                            'ai_content': ai_content,
                            'relevance_score': score,
                            'relevance_reasoning': reasoning
                        })

                        summary['ai_generated_content'] += 1

                        # Stop if we have enough qualified jobs
                        if len(qualified_jobs) >= max_applications:
                            break
                    else:
                        self.logger.info(
                            f"Job filtered out by AI (score: {score} < {ai_score_threshold})")
                        summary['ai_filtered_jobs'] += 1

                except Exception as e:
                    self.logger.error(f"Error processing job with AI: {e}")
                    summary['errors'] += 1
                    continue

            # Apply to qualified jobs with AI-generated content
            for job_data in qualified_jobs:
                try:
                    job = job_data['job']
                    ai_content = job_data['ai_content']

                    self.logger.info(
                        f"Applying to high-relevance job: {job.title} at {job.company}")

                    # Apply to job with AI-generated content
                    success = await agent.apply_to_job(job, ai_content)

                    if success:
                        applications_submitted += 1
                        summary['applied_jobs'].append({
                            'title': job.title,
                            'company': job.company,
                            'url': job.url,
                            'relevance_score': job_data['relevance_score'],
                            'ai_enhanced': True
                        })

                        # Record in state manager
                        self.state_manager.record_application(
                            job_id=job.job_id,
                            platform=platform_name,
                            title=job.title,
                            company=job.company,
                            url=job.url,
                            status='applied'
                        )

                        self.logger.info(
                            f"Successfully applied to {job.title} with AI enhancements")

                    # Rate limiting between applications
                    await asyncio.sleep(2)

                except Exception as e:
                    self.logger.error(
                        f"Error applying to {job.title}: {str(e)}")
                    summary['errors'] += 1
                    continue

            summary['applications_submitted'] = applications_submitted

            self.logger.info(
                f"AI-enhanced automation completed: {applications_submitted} applications submitted")
            return summary

        except Exception as e:
            self.logger.error(f"Error in AI-enhanced agent run: {str(e)}")
            summary['errors'] += 1
            raise
        finally:
            await agent.cleanup()

    async def _run_agent_standard(self, agent, platform_name: str, search_criteria: SearchCriteria,
                                  max_applications: int) -> Dict[str, Any]:
        """Run agent with standard automation (fallback when AI is not available)"""
        # Filter jobs to avoid duplicates
        def filter_new_jobs(jobs):
            new_jobs = []
            for job in jobs:
                if not self.state_manager.has_applied(job.job_id, platform_name):
                    new_jobs.append(job)
                else:
                    self.logger.info(
                        f"Skipping already applied job: {job.title} at {job.company}")
            return new_jobs

        # Run automation with custom filtering
        original_search = agent.search_jobs

        async def filtered_search(criteria):
            jobs = await original_search(criteria)
            return filter_new_jobs(jobs)

        agent.search_jobs = filtered_search

        # Track applications in state manager
        original_apply = agent.apply_to_job

        async def tracked_apply(job, ai_content=None):
            success = await original_apply(job, ai_content)
            if success:
                self.state_manager.record_application(
                    job_id=job.job_id,
                    platform=platform_name,
                    title=job.title,
                    company=job.company,
                    url=job.url,
                    status='applied'
                )
            return success

        agent.apply_to_job = tracked_apply

        # Execute automation
        summary = await agent.run_automation(search_criteria, max_applications)

        self.logger.info(f"Completed {platform_name} agent: {summary}")
        return summary

    async def _generate_ai_content(self, job: JobPosting) -> Dict[str, str]:
        """Generate AI-enhanced content for a job application"""
        ai_content = {}

        try:
            # Generate cover letter
            self.logger.debug("Generating personalized cover letter...")
            cover_letter = await self.ai_enhancer.generate_cover_letter(job)
            ai_content['cover_letter'] = cover_letter

            # Optimize resume sections (example: summary/skills)
            if self.structured_resume.get('summary'):
                self.logger.debug("Optimizing resume summary...")
                optimized_summary = await self.ai_enhancer.optimize_resume_section(
                    job, self.structured_resume['summary']
                )
                ai_content['optimized_summary'] = optimized_summary

            if self.structured_resume.get('skills'):
                skills_text = ', '.join(self.structured_resume['skills'])
                self.logger.debug("Optimizing skills section...")
                optimized_skills = await self.ai_enhancer.optimize_resume_section(
                    job, skills_text
                )
                ai_content['optimized_skills'] = optimized_skills

            self.logger.debug("AI content generation completed successfully")

        except Exception as e:
            self.logger.error(f"Error generating AI content: {e}")
            # Return partial content if some generation succeeded

        return ai_content

    async def run_automation(self, platforms: List[str] = None,
                             max_applications_per_platform: int = 5) -> Dict[str, Any]:
        """
        Run the complete job application automation

        Args:
            platforms: List of platform names to run (None for all enabled)
            max_applications_per_platform: Maximum applications per platform

        Returns:
            Summary dictionary with results from all platforms
        """
        self.logger.info("Starting job application automation")

        # Get enabled platforms
        enabled_platforms = self.get_enabled_platforms(platforms)

        if not enabled_platforms:
            self.logger.error(
                "No enabled platforms found with valid credentials")
            return {'total_platforms': 0, 'results': []}

        self.logger.info(
            f"Running automation on platforms: {', '.join(enabled_platforms)}")

        # Get search criteria
        search_criteria = self.get_search_criteria()
        self.logger.info(
            f"Search criteria: {search_criteria.keywords} in {search_criteria.locations}")

        # Run agents
        results = []
        total_jobs_found = 0
        total_applications = 0
        total_errors = 0

        for platform_name in enabled_platforms:
            try:
                summary = await self.run_agent(
                    platform_name,
                    search_criteria,
                    max_applications_per_platform
                )
                results.append(summary)

                total_jobs_found += summary.get('jobs_found', 0)
                total_applications += summary.get('applications_submitted', 0)
                total_errors += summary.get('errors', 0)

            except Exception as e:
                self.logger.error(
                    f"Fatal error with {platform_name}: {str(e)}")
                results.append({
                    'platform': platform_name,
                    'jobs_found': 0,
                    'applications_submitted': 0,
                    'errors': 1,
                    'applied_jobs': [],
                    'error_message': str(e)
                })
                total_errors += 1

        # Final summary
        final_summary = {
            'total_platforms': len(enabled_platforms),
            'total_jobs_found': total_jobs_found,
            'total_applications_submitted': total_applications,
            'total_errors': total_errors,
            'platform_results': results,
            'state_stats': self.state_manager.get_application_stats()
        }

        self.logger.info("Automation completed")
        self._print_summary(final_summary)

        # Google Sheets reporting
        self._post_run_summary(final_summary)

        return final_summary

    def _print_summary(self, summary: Dict[str, Any]):
        """Print a formatted summary to console"""
        print("\n" + "="*60)
        print("JOB APPLICATION AUTOMATION SUMMARY")
        print("="*60)

        print(f"Platforms processed: {summary['total_platforms']}")
        print(f"Total jobs found: {summary['total_jobs_found']}")
        print(
            f"Total applications submitted: {summary['total_applications_submitted']}")
        print(f"Total errors: {summary['total_errors']}")

        print("\nPlatform Results:")
        print("-" * 40)

        for result in summary['platform_results']:
            platform = result['platform']
            jobs = result['jobs_found']
            apps = result['applications_submitted']
            errors = result['errors']

            status = "✓" if errors == 0 else "✗"
            print(
                f"{status} {platform}: {jobs} jobs found, {apps} applications submitted")

            if result.get('error_message'):
                print(f"  Error: {result['error_message']}")

            if result.get('applied_jobs'):
                print("  Applied to:")
                for job in result['applied_jobs'][:3]:  # Show first 3
                    print(f"    - {job['title']} at {job['company']}")
                if len(result['applied_jobs']) > 3:
                    print(
                        f"    ... and {len(result['applied_jobs']) - 3} more")

        # Show recent applications from state
        print("\nRecent Applications:")
        print("-" * 40)
        recent_apps = self.state_manager.get_recent_applications(5)
        for app in recent_apps:
            print(f"• {app['title']} at {app['company']} ({app['platform']})")

        print("\nOverall Statistics:")
        print("-" * 40)
        stats = summary['state_stats']
        print(f"Total applications in database: {stats['total']}")
        for platform, platform_stats in stats.get('platforms', {}).items():
            print(f"  {platform}: {platform_stats['successful']} applications")

        print("="*60)

    def _post_run_summary(self, summary: Dict[str, Any]):
        """Handle post-run reporting, including Google Sheets integration"""
        try:
            # Check if Google Sheets reporting is enabled
            google_sheets_config = self.config.get('google_sheets', {})
            if not google_sheets_config.get('enabled', False):
                self.logger.debug("Google Sheets reporting is disabled")
                return

            # Get configuration values
            spreadsheet_id = google_sheets_config.get('spreadsheet_id', '')
            sheet_name = google_sheets_config.get(
                'sheet_name', 'Job Applications')
            credentials_path = google_sheets_config.get(
                'credentials_path', 'google_credentials.json')

            # Validate configuration
            if not spreadsheet_id or spreadsheet_id == 'your_spreadsheet_id_here':
                self.logger.warning(
                    "Google Sheets reporting enabled but no valid spreadsheet_id configured")
                return

            # Initialize and use Google Sheets reporter
            self.logger.info("Initializing Google Sheets reporting...")
            reporter = GoogleSheetsReporter(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                credentials_path=credentials_path
            )

            # Test connection first
            if reporter.test_connection():
                # Report the applications
                if reporter.append_applications(summary):
                    self.logger.info(
                        "Successfully reported applications to Google Sheets")
                else:
                    self.logger.warning(
                        "Failed to report applications to Google Sheets")
            else:
                self.logger.warning(
                    "Google Sheets connection test failed, skipping reporting")

        except Exception as e:
            self.logger.error(
                f"Error in post-run Google Sheets reporting: {str(e)}")
            # Don't let reporting errors crash the main application


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Autonomous Job Application Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config', '-c',
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )

    parser.add_argument(
        '--platforms', '-p',
        help='Comma-separated list of platforms to run (e.g., linkedin,wellfound)'
    )

    parser.add_argument(
        '--max-apps', '-m',
        type=int,
        default=5,
        help='Maximum applications per platform (default: 5)'
    )

    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Show what would be done without actually applying'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


async def main():
    """Main entry point"""
    args = parse_arguments()

    try:
        # Initialize orchestrator with AI services
        orchestrator = await JobApplicationOrchestrator.create(
            config_path=args.config,
            dry_run=args.dry_run,
            enable_ai=True
        )

        # Set verbose logging if requested
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Parse platforms
        platforms = None
        if args.platforms:
            platforms = [p.strip() for p in args.platforms.split(',')]

        # Run automation (handles dry run internally)
        summary = await orchestrator.run_automation(
            platforms=platforms,
            max_applications_per_platform=args.max_apps
        )

        # Exit with appropriate code
        if summary['total_errors'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\nAutomation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
