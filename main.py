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

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any
import traceback

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.config_loader import ConfigLoader
from utils.state_manager import StateManager
from base_agent import SearchCriteria
from agents.linkedin_agent import LinkedInAgent

# Import additional agents as they're implemented
from agents.wellfound_agent import WellfoundAgent

class JobApplicationOrchestrator:
    """
    Main orchestrator for the job application automation system
    Manages configuration, agents, and provides execution coordination
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()
        self.state_manager = self._init_state_manager()
        self.logger = self._setup_logging()
        
        # Available agents
        self.available_agents = {
            'linkedin': LinkedInAgent,
            'wellfound': WellfoundAgent,
        }
        
    def _init_state_manager(self) -> StateManager:
        """Initialize state management system"""
        state_config = self.config.get('state', {})
        storage_type = state_config.get('storage_type', 'sqlite')
        database_path = state_config.get('database_path', './data/job_applications.db')
        
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
    
    def get_search_criteria(self) -> SearchCriteria:
        """Build search criteria from configuration"""
        search_config = self.config.get('search_settings', {})
        
        return SearchCriteria(
            keywords=search_config.get('default_keywords', ['Software Engineer']),
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
            platform_enabled = platform_config.get(platform_name, {}).get('enabled', True)
            
            # Check if platform credentials are available
            credentials = self.config_loader.get_credentials(platform_name)
            has_credentials = credentials and credentials.get('email') and credentials.get('password')
            
            # Include platform if enabled, has credentials, and is requested (if specified)
            if platform_enabled and has_credentials:
                if requested_platforms is None or platform_name in requested_platforms:
                    enabled_platforms.append(platform_name)
                    
        return enabled_platforms
    
    async def run_agent(self, platform_name: str, search_criteria: SearchCriteria, 
                       max_applications: int) -> Dict[str, Any]:
        """Run a specific platform agent"""
        try:
            agent_class = self.available_agents[platform_name]
            credentials = self.config_loader.get_credentials(platform_name)
            proxy_config = self.config_loader.get_proxy_config()
            
            self.logger.info(f"Starting {platform_name} agent")
            
            # Initialize agent
            agent = agent_class(self.config, proxy_config)
            
            # Filter jobs to avoid duplicates
            def filter_new_jobs(jobs):
                new_jobs = []
                for job in jobs:
                    if not self.state_manager.has_applied(job.job_id, platform_name):
                        new_jobs.append(job)
                    else:
                        self.logger.info(f"Skipping already applied job: {job.title} at {job.company}")
                return new_jobs
            
            # Run automation with custom filtering
            original_search = agent.search_jobs
            
            async def filtered_search(criteria):
                jobs = await original_search(criteria)
                return filter_new_jobs(jobs)
            
            agent.search_jobs = filtered_search
            
            # Track applications in state manager
            original_apply = agent.apply_to_job
            
            async def tracked_apply(job):
                success = await original_apply(job)
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
            self.logger.error("No enabled platforms found with valid credentials")
            return {'total_platforms': 0, 'results': []}
        
        self.logger.info(f"Running automation on platforms: {', '.join(enabled_platforms)}")
        
        # Get search criteria
        search_criteria = self.get_search_criteria()
        self.logger.info(f"Search criteria: {search_criteria.keywords} in {search_criteria.locations}")
        
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
                self.logger.error(f"Fatal error with {platform_name}: {str(e)}")
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
        
        return final_summary
    
    def _print_summary(self, summary: Dict[str, Any]):
        """Print a formatted summary to console"""
        print("\n" + "="*60)
        print("JOB APPLICATION AUTOMATION SUMMARY")
        print("="*60)
        
        print(f"Platforms processed: {summary['total_platforms']}")
        print(f"Total jobs found: {summary['total_jobs_found']}")
        print(f"Total applications submitted: {summary['total_applications_submitted']}")
        print(f"Total errors: {summary['total_errors']}")
        
        print("\nPlatform Results:")
        print("-" * 40)
        
        for result in summary['platform_results']:
            platform = result['platform']
            jobs = result['jobs_found']
            apps = result['applications_submitted']
            errors = result['errors']
            
            status = "✓" if errors == 0 else "✗"
            print(f"{status} {platform}: {jobs} jobs found, {apps} applications submitted")
            
            if result.get('error_message'):
                print(f"  Error: {result['error_message']}")
            
            if result.get('applied_jobs'):
                print("  Applied to:")
                for job in result['applied_jobs'][:3]:  # Show first 3
                    print(f"    - {job['title']} at {job['company']}")
                if len(result['applied_jobs']) > 3:
                    print(f"    ... and {len(result['applied_jobs']) - 3} more")
        
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
        # Initialize orchestrator
        orchestrator = JobApplicationOrchestrator(args.config)
        
        # Set verbose logging if requested
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Parse platforms
        platforms = None
        if args.platforms:
            platforms = [p.strip() for p in args.platforms.split(',')]
        
        # Run automation
        if args.dry_run:
            print("DRY RUN MODE - No applications will be submitted")
            # TODO: Implement dry run mode
            return
        
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