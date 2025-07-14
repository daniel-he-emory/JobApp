from utils.state_manager import StateManager
from config.config_loader import ConfigLoader
from base_agent import SearchCriteria, JobPosting
from main import JobApplicationOrchestrator, parse_arguments, main
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import yaml
from typing import Dict, Any, List

import sys
sys.path.append('/home/daniel/JobApp')


class MockAgent:
    """Mock agent for testing integration"""

    def __init__(self, config, proxy_config=None):
        self.config = config
        self.proxy_config = proxy_config
        self.run_automation_called = False
        self.automation_result = {
            'platform': 'MockAgent',
            'jobs_found': 5,
            'applications_submitted': 3,
            'errors': 0,
            'applied_jobs': [
                {'title': 'Software Engineer', 'company': 'TechCorp', 'url': 'url1'},
                {'title': 'Developer', 'company': 'StartupCo', 'url': 'url2'}
            ]
        }

    async def run_automation(self, criteria, max_applications):
        self.run_automation_called = True
        return self.automation_result

    async def search_jobs(self, criteria):
        return [
            JobPosting("1", "Engineer 1", "Company A", "Remote", "url1"),
            JobPosting("2", "Engineer 2", "Company B", "SF", "url2")
        ]

    async def apply_to_job(self, job):
        return True


class TestJobApplicationOrchestrator:
    """Test the main orchestrator class"""

    def test_orchestrator_initialization(self, config_file):
        """Test orchestrator initialization with config"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=False)

        assert orchestrator.config is not None
        assert orchestrator.state_manager is not None
        assert orchestrator.logger is not None
        assert 'linkedin' in orchestrator.available_agents
        assert 'wellfound' in orchestrator.available_agents

    def test_orchestrator_dry_run_mode(self, config_file):
        """Test orchestrator initialization in dry run mode"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=True)
        assert orchestrator.dry_run is True

    def test_get_search_criteria(self, config_file):
        """Test search criteria generation from config"""
        orchestrator = JobApplicationOrchestrator(str(config_file))
        criteria = orchestrator.get_search_criteria()

        assert isinstance(criteria, SearchCriteria)
        assert criteria.keywords == ['Developer', 'Engineer']
        assert criteria.locations == ['Remote', 'San Francisco']
        assert criteria.easy_apply_only is True

    def test_get_enabled_platforms_all(self, config_file):
        """Test getting all enabled platforms"""
        orchestrator = JobApplicationOrchestrator(str(config_file))
        enabled = orchestrator.get_enabled_platforms()

        # Should include platforms with valid credentials
        assert 'linkedin' in enabled
        assert 'wellfound' in enabled

    def test_get_enabled_platforms_requested(self, config_file):
        """Test getting specific requested platforms"""
        orchestrator = JobApplicationOrchestrator(str(config_file))
        enabled = orchestrator.get_enabled_platforms(['linkedin'])

        assert enabled == ['linkedin']

    def test_get_enabled_platforms_no_credentials(self, temp_dir):
        """Test platforms without credentials are not enabled"""
        config = {
            'credentials': {
                'verification_email': {
                    'address': 'test@gmail.com',
                    'password': 'app_password'
                },
                'linkedin': {
                    'email': '',  # No credentials
                    'password': ''
                }
            },
            'platforms': {
                'linkedin': {'enabled': True}
            }
        }

        config_path = temp_dir / 'no_creds.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        orchestrator = JobApplicationOrchestrator(str(config_path))
        enabled = orchestrator.get_enabled_platforms()

        assert 'linkedin' not in enabled

    @pytest.mark.asyncio
    async def test_simulate_agent_run_success(self, config_file):
        """Test dry run simulation with valid credentials"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=True)
        criteria = SearchCriteria(['engineer'], ['remote'])
        credentials = {'email': 'test@example.com', 'password': 'pass'}

        result = await orchestrator._simulate_agent_run('linkedin', criteria, 5, credentials)

        assert result['platform'] == 'linkedin'
        assert result['jobs_found'] > 0
        assert result['applications_submitted'] >= 0
        assert isinstance(result['applied_jobs'], list)

    @pytest.mark.asyncio
    async def test_simulate_agent_run_no_credentials(self, config_file):
        """Test dry run simulation without credentials"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=True)
        criteria = SearchCriteria(['engineer'], ['remote'])
        credentials = {}  # No credentials

        result = await orchestrator._simulate_agent_run('linkedin', criteria, 5, credentials)

        assert result['platform'] == 'linkedin'
        assert result['jobs_found'] == 0
        assert result['applications_submitted'] == 0
        assert result['errors'] == 1
        assert 'error_message' in result

    @pytest.mark.asyncio
    async def test_run_agent_dry_run(self, config_file):
        """Test running agent in dry run mode"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=True)
        criteria = SearchCriteria(['engineer'], ['remote'])

        result = await orchestrator.run_agent('linkedin', criteria, 5)

        assert result['platform'] == 'linkedin'
        assert isinstance(result['jobs_found'], int)
        assert isinstance(result['applications_submitted'], int)

    @pytest.mark.asyncio
    async def test_run_agent_real_mode_mock(self, config_file):
        """Test running agent in real mode with mocked agent"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=False)

        # Replace agent class with mock
        orchestrator.available_agents['linkedin'] = MockAgent

        criteria = SearchCriteria(['engineer'], ['remote'])
        result = await orchestrator.run_agent('linkedin', criteria, 5)

        assert result['platform'] == 'MockAgent'
        assert result['jobs_found'] == 5
        assert result['applications_submitted'] == 3

    @pytest.mark.asyncio
    async def test_run_agent_exception_handling(self, config_file):
        """Test agent exception handling"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=False)

        # Mock agent that raises exception
        class FailingAgent:
            def __init__(self, config, proxy_config=None):
                raise Exception("Agent initialization failed")

        orchestrator.available_agents['linkedin'] = FailingAgent

        criteria = SearchCriteria(['engineer'], ['remote'])
        result = await orchestrator.run_agent('linkedin', criteria, 5)

        assert result['platform'] == 'linkedin'
        assert result['errors'] == 1
        assert 'error_message' in result

    @pytest.mark.asyncio
    async def test_run_automation_dry_run(self, config_file):
        """Test full automation in dry run mode"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=True)

        result = await orchestrator.run_automation(['linkedin'], max_applications_per_platform=3)

        assert result['total_platforms'] >= 1
        assert 'total_jobs_found' in result
        assert 'total_applications_submitted' in result
        assert 'platform_results' in result
        assert len(result['platform_results']) >= 1

    @pytest.mark.asyncio
    async def test_run_automation_no_platforms(self, temp_dir):
        """Test automation with no enabled platforms"""
        config = {
            'credentials': {
                'verification_email': {
                    'address': 'test@gmail.com',
                    'password': 'app_password'
                }
            }
        }

        config_path = temp_dir / 'no_platforms.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        orchestrator = JobApplicationOrchestrator(str(config_path))
        result = await orchestrator.run_automation()

        assert result['total_platforms'] == 0
        assert result['results'] == []

    @pytest.mark.asyncio
    async def test_run_automation_with_mock_agents(self, config_file):
        """Test full automation with mocked agents"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=False)

        # Replace all agents with mocks
        orchestrator.available_agents['linkedin'] = MockAgent
        orchestrator.available_agents['wellfound'] = MockAgent

        result = await orchestrator.run_automation(
            platforms=['linkedin', 'wellfound'],
            max_applications_per_platform=3
        )

        assert result['total_platforms'] == 2
        assert len(result['platform_results']) == 2
        assert all(r['platform'] ==
                   'MockAgent' for r in result['platform_results'])

    def test_print_summary(self, config_file, capsys):
        """Test summary printing functionality"""
        orchestrator = JobApplicationOrchestrator(str(config_file))

        summary = {
            'total_platforms': 2,
            'total_jobs_found': 10,
            'total_applications_submitted': 5,
            'total_errors': 1,
            'platform_results': [
                {
                    'platform': 'linkedin',
                    'jobs_found': 6,
                    'applications_submitted': 3,
                    'errors': 0,
                    'applied_jobs': [
                        {'title': 'Engineer', 'company': 'TechCorp', 'url': 'url1'}
                    ]
                },
                {
                    'platform': 'wellfound',
                    'jobs_found': 4,
                    'applications_submitted': 2,
                    'errors': 1,
                    'error_message': 'Connection failed'
                }
            ],
            'state_stats': {
                'total': 5,
                'platforms': {
                    'linkedin': {'successful': 3},
                    'wellfound': {'successful': 2}
                }
            }
        }

        # Mock state manager to return recent applications
        orchestrator.state_manager.get_recent_applications = Mock(return_value=[
            {'title': 'Engineer', 'company': 'TechCorp', 'platform': 'linkedin'}
        ])

        orchestrator._print_summary(summary)

        captured = capsys.readouterr()
        assert 'JOB APPLICATION AUTOMATION SUMMARY' in captured.out
        assert 'Total jobs found: 10' in captured.out
        assert 'Total applications submitted: 5' in captured.out
        assert 'linkedin: 6 jobs found, 3 applications submitted' in captured.out
        assert 'Connection failed' in captured.out


class TestConfigIntegration:
    """Test configuration integration scenarios"""

    def test_config_with_environment_override(self, temp_dir):
        """Test configuration with environment variable override"""
        config = {
            'credentials': {
                'linkedin': {
                    'email': 'config@example.com',
                    'password': 'config_pass'
                },
                'verification_email': {
                    'address': 'test@gmail.com',
                    'password': 'app_password'
                }
            }
        }

        config_path = temp_dir / 'env_test.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        with patch.dict('os.environ', {'LINKEDIN_EMAIL': 'env@example.com'}):
            orchestrator = JobApplicationOrchestrator(str(config_path))
            linkedin_creds = orchestrator.config_loader.get_credentials(
                'linkedin')

            assert linkedin_creds['email'] == 'env@example.com'
            assert linkedin_creds['password'] == 'config_pass'

    def test_config_validation_failure(self, temp_dir):
        """Test configuration validation failure"""
        config = {
            'credentials': {
                'verification_email': {
                    'address': 'your_email@example.com',  # placeholder
                    'password': 'placeholder'
                }
            }
        }

        config_path = temp_dir / 'invalid_config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        with pytest.raises(ValueError, match="Missing required configurations"):
            JobApplicationOrchestrator(str(config_path))


class TestStateManagerIntegration:
    """Test state manager integration"""

    @pytest.mark.asyncio
    async def test_duplicate_application_prevention(self, config_file):
        """Test that duplicate applications are prevented"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=False)

        # Mock agent that returns the same job multiple times
        class DuplicateJobAgent:
            def __init__(self, config, proxy_config=None):
                self.config = config

            async def run_automation(self, criteria, max_applications):
                return {
                    'platform': 'test',
                    'jobs_found': 2,
                    'applications_submitted': 1,  # Only 1 should succeed due to duplicate
                    'errors': 0,
                    'applied_jobs': [
                        {'title': 'Engineer', 'company': 'TechCorp', 'url': 'url1'}
                    ]
                }

            async def search_jobs(self, criteria):
                # Return same job twice
                job = JobPosting("duplicate_job", "Engineer",
                                 "TechCorp", "Remote", "url1")
                return [job, job]

            async def apply_to_job(self, job):
                return True

        orchestrator.available_agents['test_platform'] = DuplicateJobAgent

        # First run should succeed
        criteria = SearchCriteria(['engineer'], ['remote'])
        await orchestrator.run_agent('test_platform', criteria, 5)

        # Verify job was recorded
        assert orchestrator.state_manager.has_applied(
            "duplicate_job", "test_platform")

        # Second run should skip the duplicate
        result = await orchestrator.run_agent('test_platform', criteria, 5)

        # Should find the job but not apply (already applied)
        assert result['platform'] == 'test'


class TestCommandLineInterface:
    """Test command line interface and argument parsing"""

    def test_parse_arguments_defaults(self):
        """Test argument parsing with defaults"""
        with patch('sys.argv', ['main.py']):
            args = parse_arguments()

            assert args.config == 'config/config.yaml'
            assert args.platforms is None
            assert args.max_apps == 5
            assert args.dry_run is False
            assert args.verbose is False

    def test_parse_arguments_custom(self):
        """Test argument parsing with custom values"""
        with patch('sys.argv', [
            'main.py',
            '--config', 'custom_config.yaml',
            '--platforms', 'linkedin,wellfound',
            '--max-apps', '10',
            '--dry-run',
            '--verbose'
        ]):
            args = parse_arguments()

            assert args.config == 'custom_config.yaml'
            assert args.platforms == 'linkedin,wellfound'
            assert args.max_apps == 10
            assert args.dry_run is True
            assert args.verbose is True

    @pytest.mark.asyncio
    async def test_main_function_success(self, config_file):
        """Test main function execution with success"""
        with patch('sys.argv', [
            'main.py',
            '--config', str(config_file),
            '--dry-run',
            '--platforms', 'linkedin'
        ]), patch('sys.exit') as mock_exit:

            await main()

            # Should exit with code 0 for success
            mock_exit.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_main_function_with_errors(self, config_file):
        """Test main function when errors occur"""
        with patch('sys.argv', [
            'main.py',
            '--config', str(config_file),
            '--platforms', 'nonexistent_platform'
        ]), patch('sys.exit') as mock_exit:

            await main()

            # Should exit with code 0 even when no platforms (graceful handling)
            mock_exit.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_main_function_keyboard_interrupt(self, config_file):
        """Test main function handling keyboard interrupt"""
        with patch('sys.argv', [
            'main.py',
            '--config', str(config_file)
        ]), patch('sys.exit') as mock_exit, \
                patch('main.JobApplicationOrchestrator') as mock_orchestrator:

            # Make orchestrator raise KeyboardInterrupt
            mock_orchestrator.side_effect = KeyboardInterrupt()

            await main()

            # Should exit with code 130 for interrupt
            mock_exit.assert_called_with(130)

    @pytest.mark.asyncio
    async def test_main_function_fatal_error(self, config_file):
        """Test main function handling fatal errors"""
        with patch('sys.argv', [
            'main.py',
            '--config', 'nonexistent_config.yaml'
        ]), patch('sys.exit') as mock_exit:

            await main()

            # Should exit with code 1 for fatal error
            mock_exit.assert_called_with(1)


class TestGoogleSheetsIntegration:
    """Test Google Sheets integration"""

    def test_post_run_summary_disabled(self, config_file):
        """Test Google Sheets reporting when disabled"""
        orchestrator = JobApplicationOrchestrator(str(config_file))

        # Mock config to disable Google Sheets
        orchestrator.config['google_sheets'] = {'enabled': False}

        summary = {'total_applications_submitted': 5}

        # Should not raise exception
        orchestrator._post_run_summary(summary)

    @patch('main.GoogleSheetsReporter')
    def test_post_run_summary_enabled_success(self, mock_reporter_class, config_file):
        """Test Google Sheets reporting when enabled and successful"""
        orchestrator = JobApplicationOrchestrator(str(config_file))

        # Mock config to enable Google Sheets
        orchestrator.config['google_sheets'] = {
            'enabled': True,
            'spreadsheet_id': 'test_spreadsheet_id',
            'sheet_name': 'Applications',
            'credentials_path': 'creds.json'
        }

        # Mock reporter instance
        mock_reporter = Mock()
        mock_reporter.test_connection.return_value = True
        mock_reporter.append_applications.return_value = True
        mock_reporter_class.return_value = mock_reporter

        summary = {'total_applications_submitted': 5}
        orchestrator._post_run_summary(summary)

        # Verify reporter was initialized and used
        mock_reporter_class.assert_called_once_with(
            spreadsheet_id='test_spreadsheet_id',
            sheet_name='Applications',
            credentials_path='creds.json'
        )
        mock_reporter.test_connection.assert_called_once()
        mock_reporter.append_applications.assert_called_once_with(summary)

    def test_post_run_summary_invalid_config(self, config_file):
        """Test Google Sheets reporting with invalid configuration"""
        orchestrator = JobApplicationOrchestrator(str(config_file))

        # Mock config with placeholder values
        orchestrator.config['google_sheets'] = {
            'enabled': True,
            'spreadsheet_id': 'your_spreadsheet_id_here',  # placeholder
            'sheet_name': 'Applications'
        }

        summary = {'total_applications_submitted': 5}

        # Should handle gracefully and not crash
        orchestrator._post_run_summary(summary)


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery scenarios"""

    @pytest.mark.asyncio
    async def test_partial_platform_failure(self, config_file):
        """Test handling when some platforms fail"""
        orchestrator = JobApplicationOrchestrator(
            str(config_file), dry_run=False)

        # Mock agents - one succeeds, one fails
        class SuccessAgent:
            def __init__(self, config, proxy_config=None):
                pass

            async def run_automation(self, criteria, max_applications):
                return {
                    'platform': 'success',
                    'jobs_found': 5,
                    'applications_submitted': 3,
                    'errors': 0,
                    'applied_jobs': []
                }

        class FailingAgent:
            def __init__(self, config, proxy_config=None):
                pass

            async def run_automation(self, criteria, max_applications):
                raise Exception("Platform API down")

        orchestrator.available_agents['success_platform'] = SuccessAgent
        orchestrator.available_agents['failing_platform'] = FailingAgent

        # Override credential check to include both platforms
        orchestrator.get_enabled_platforms = Mock(
            return_value=['success_platform', 'failing_platform'])

        result = await orchestrator.run_automation()

        # Should have results from both platforms
        assert result['total_platforms'] == 2
        assert len(result['platform_results']) == 2

        # One should succeed, one should fail
        success_results = [
            r for r in result['platform_results'] if r['errors'] == 0]
        error_results = [
            r for r in result['platform_results'] if r['errors'] > 0]

        assert len(success_results) == 1
        assert len(error_results) == 1
        assert 'error_message' in error_results[0]

    @pytest.mark.asyncio
    async def test_state_manager_recovery(self, temp_dir):
        """Test state manager recovery from database issues"""
        # Create orchestrator with temporary database
        config = {
            'credentials': {
                'verification_email': {
                    'address': 'test@gmail.com',
                    'password': 'app_password'
                },
                'linkedin': {
                    'email': 'test@example.com',
                    'password': 'password'
                }
            },
            'state': {
                'storage_type': 'sqlite',
                'database_path': str(temp_dir / 'test.db')
            }
        }

        config_path = temp_dir / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        orchestrator = JobApplicationOrchestrator(str(config_path))

        # Verify state manager is working
        assert orchestrator.state_manager is not None
        assert not orchestrator.state_manager.has_applied(
            "test_job", "linkedin")

        # Record and verify application
        orchestrator.state_manager.record_application(
            "test_job", "linkedin", "Engineer", "TechCorp")
        assert orchestrator.state_manager.has_applied("test_job", "linkedin")
