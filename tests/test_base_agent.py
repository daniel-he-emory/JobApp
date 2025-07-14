from base_agent import JobAgent, JobPosting, SearchCriteria
import pytest
from unittest.mock import AsyncMock, patch
from typing import Dict, List, Optional, Any

import sys
sys.path.append('/home/daniel/JobApp')


class ConcreteJobAgent(JobAgent):
    """Concrete implementation of JobAgent for testing"""

    def __init__(self, config: Dict[str, Any], proxy_config: Optional[Dict[str, str]] = None):
        super().__init__(config, proxy_config)
        self.login_called = False
        self.search_called = False
        self.apply_called = False
        self.get_details_called = False

        # Mock return values
        self.login_result = True
        self.search_result = []
        self.apply_result = True
        self.details_result = None

    async def login(self) -> bool:
        self.login_called = True
        return self.login_result

    async def search_jobs(self, criteria: SearchCriteria) -> List[JobPosting]:
        self.search_called = True
        return self.search_result

    async def apply_to_job(self, job: JobPosting, ai_content: Optional[Dict[str, str]] = None) -> bool:
        self.apply_called = True
        return self.apply_result

    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        self.get_details_called = True
        return self.details_result


class TestJobPosting:
    """Test JobPosting data class"""

    def test_job_posting_creation(self):
        """Test creating JobPosting with required fields"""
        job = JobPosting(
            job_id="12345",
            title="Software Engineer",
            company="TechCorp",
            location="San Francisco, CA",
            url="https://example.com/jobs/12345"
        )

        assert job.job_id == "12345"
        assert job.title == "Software Engineer"
        assert job.company == "TechCorp"
        assert job.location == "San Francisco, CA"
        assert job.url == "https://example.com/jobs/12345"
        assert job.description is None
        assert job.salary is None
        assert job.posted_date is None
        assert job.platform is None

    def test_job_posting_with_optional_fields(self):
        """Test creating JobPosting with all fields"""
        job = JobPosting(
            job_id="12345",
            title="Senior Software Engineer",
            company="TechCorp",
            location="Remote",
            url="https://example.com/jobs/12345",
            description="Great job opportunity",
            salary="$120k-$150k",
            posted_date="2023-12-01",
            platform="linkedin"
        )

        assert job.description == "Great job opportunity"
        assert job.salary == "$120k-$150k"
        assert job.posted_date == "2023-12-01"
        assert job.platform == "linkedin"


class TestSearchCriteria:
    """Test SearchCriteria data class"""

    def test_search_criteria_creation(self):
        """Test creating SearchCriteria with required fields"""
        criteria = SearchCriteria(
            keywords=["software engineer", "python"],
            locations=["San Francisco", "Remote"]
        )

        assert criteria.keywords == ["software engineer", "python"]
        assert criteria.locations == ["San Francisco", "Remote"]
        assert criteria.experience_level is None
        assert criteria.job_type is None
        assert criteria.remote_options is None
        assert criteria.date_posted is None
        assert criteria.easy_apply_only is True

    def test_search_criteria_with_optional_fields(self):
        """Test creating SearchCriteria with all fields"""
        criteria = SearchCriteria(
            keywords=["senior engineer"],
            locations=["New York"],
            experience_level="Senior level",
            job_type="Full-time",
            remote_options="Remote",
            date_posted="Past week",
            easy_apply_only=False
        )

        assert criteria.experience_level == "Senior level"
        assert criteria.job_type == "Full-time"
        assert criteria.remote_options == "Remote"
        assert criteria.date_posted == "Past week"
        assert criteria.easy_apply_only is False


class TestJobAgentBase:
    """Test JobAgent base class functionality"""

    def test_job_agent_initialization(self):
        """Test JobAgent initialization"""
        config = {"test": "config"}
        proxy_config = {"host": "proxy.example.com", "port": "8080"}

        agent = ConcreteJobAgent(config, proxy_config)

        assert agent.config == config
        assert agent.proxy_config == proxy_config
        assert agent.browser is None
        assert agent.context is None
        assert agent.page is None
        assert agent.logger.name == "ConcreteJobAgent"

    def test_job_agent_initialization_no_proxy(self):
        """Test JobAgent initialization without proxy"""
        config = {"test": "config"}

        agent = ConcreteJobAgent(config)

        assert agent.config == config
        assert agent.proxy_config is None

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test browser cleanup"""
        agent = ConcreteJobAgent({})

        # Mock browser components
        agent.page = AsyncMock()
        agent.context = AsyncMock()
        agent.browser = AsyncMock()

        await agent.cleanup()

        agent.page.close.assert_called_once()
        agent.context.close.assert_called_once()
        agent.browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_partial_components(self):
        """Test cleanup when only some components are initialized"""
        agent = ConcreteJobAgent({})

        # Only browser is initialized
        agent.browser = AsyncMock()

        await agent.cleanup()  # Should not raise exception

        agent.browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_components(self):
        """Test cleanup when no components are initialized"""
        agent = ConcreteJobAgent({})

        await agent.cleanup()  # Should not raise exception


class TestJobAgentBrowserInitialization:
    """Test browser initialization functionality"""

    @pytest.mark.asyncio
    @patch('base_agent.async_playwright')
    @patch('utils.proxy_manager.AntiDetectionManager')
    async def test_initialize_browser_basic(self, mock_anti_detection, mock_playwright):
        """Test basic browser initialization without proxy"""
        # Setup mocks
        mock_playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(
            return_value=mock_playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright_instance.chromium.launch = AsyncMock(
            return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_anti_detection.get_random_user_agent.return_value = "test-user-agent"
        mock_anti_detection.get_random_viewport.return_value = {
            "width": 1920, "height": 1080}
        mock_anti_detection.get_stealth_script.return_value = "stealth script"

        agent = ConcreteJobAgent({})
        await agent.initialize_browser(headless=True)

        # Verify browser components were set
        assert agent.browser == mock_browser
        assert agent.context == mock_context
        assert agent.page == mock_page

        # Verify browser launch was called with correct options
        mock_playwright_instance.chromium.launch.assert_called_once()
        launch_args = mock_playwright_instance.chromium.launch.call_args[1]
        assert launch_args['headless'] is True
        assert '--disable-blink-features=AutomationControlled' in launch_args['args']

        # Verify context creation with anti-detection measures
        mock_browser.new_context.assert_called_once()
        context_args = mock_browser.new_context.call_args[1]
        assert context_args['user_agent'] == "test-user-agent"
        assert context_args['viewport'] == {"width": 1920, "height": 1080}

        # Verify stealth script was added
        mock_context.add_init_script.assert_called_once_with("stealth script")

        # Verify page creation and stealth measures
        mock_context.new_page.assert_called_once()
        mock_page.evaluate.assert_called_once()

    @pytest.mark.asyncio
    @patch('base_agent.async_playwright')
    @patch('utils.proxy_manager.AntiDetectionManager')
    async def test_initialize_browser_with_proxy_dict(self, mock_anti_detection, mock_playwright):
        """Test browser initialization with proxy configuration as dict"""
        # Setup mocks
        mock_playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(
            return_value=mock_playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright_instance.chromium.launch = AsyncMock(
            return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_anti_detection.get_random_user_agent.return_value = "test-user-agent"
        mock_anti_detection.get_random_viewport.return_value = {
            "width": 1920, "height": 1080}
        mock_anti_detection.get_stealth_script.return_value = "stealth script"

        proxy_config = {
            "host": "proxy.example.com",
            "port": "8080",
            "username": "user",
            "password": "pass"
        }

        agent = ConcreteJobAgent({}, proxy_config)
        await agent.initialize_browser()

        # Verify proxy was configured in launch options
        launch_args = mock_playwright_instance.chromium.launch.call_args[1]
        assert 'proxy' in launch_args
        proxy_settings = launch_args['proxy']
        assert proxy_settings['server'] == "http://proxy.example.com:8080"
        assert proxy_settings['username'] == "user"
        assert proxy_settings['password'] == "pass"

    @pytest.mark.asyncio
    @patch('base_agent.async_playwright')
    @patch('utils.proxy_manager.AntiDetectionManager')
    async def test_initialize_browser_headless_false(self, mock_anti_detection, mock_playwright):
        """Test browser initialization with headless=False"""
        # Setup mocks
        mock_playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(
            return_value=mock_playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright_instance.chromium.launch = AsyncMock(
            return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_anti_detection.get_random_user_agent.return_value = "test-user-agent"
        mock_anti_detection.get_random_viewport.return_value = {
            "width": 1920, "height": 1080}
        mock_anti_detection.get_stealth_script.return_value = "stealth script"

        agent = ConcreteJobAgent({})
        await agent.initialize_browser(headless=False)

        # Verify headless setting
        launch_args = mock_playwright_instance.chromium.launch.call_args[1]
        assert launch_args['headless'] is False


class TestJobAgentWorkflow:
    """Test the main automation workflow"""

    @pytest.mark.asyncio
    async def test_run_automation_success(self):
        """Test successful automation workflow"""
        agent = ConcreteJobAgent({})

        # Mock browser initialization and cleanup
        agent.initialize_browser = AsyncMock()
        agent.cleanup = AsyncMock()

        # Setup mock data
        job1 = JobPosting("1", "Engineer 1", "Company A", "Remote", "url1")
        job2 = JobPosting("2", "Engineer 2", "Company B", "SF", "url2")
        agent.search_result = [job1, job2]

        criteria = SearchCriteria(["engineer"], ["remote"])

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await agent.run_automation(criteria, max_applications=2)

        # Verify workflow was executed
        assert agent.login_called
        assert agent.search_called
        assert agent.apply_called

        # Verify summary
        assert result['platform'] == 'ConcreteJobAgent'
        assert result['jobs_found'] == 2
        assert result['applications_submitted'] == 2
        assert result['errors'] == 0
        assert len(result['applied_jobs']) == 2

        # Verify cleanup was called
        agent.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_automation_login_failure(self):
        """Test automation workflow when login fails"""
        agent = ConcreteJobAgent({})
        agent.login_result = False

        agent.initialize_browser = AsyncMock()
        agent.cleanup = AsyncMock()

        criteria = SearchCriteria(["engineer"], ["remote"])
        result = await agent.run_automation(criteria)

        # Verify login was called but search/apply were not
        assert agent.login_called
        assert not agent.search_called
        assert not agent.apply_called

        # Verify error was recorded
        assert result['errors'] == 1
        assert result['jobs_found'] == 0
        assert result['applications_submitted'] == 0

        # Verify cleanup was called
        agent.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_automation_application_errors(self):
        """Test automation workflow with application errors"""
        agent = ConcreteJobAgent({})

        agent.initialize_browser = AsyncMock()
        agent.cleanup = AsyncMock()

        # Setup jobs but make applications fail
        job1 = JobPosting("1", "Engineer 1", "Company A", "Remote", "url1")
        job2 = JobPosting("2", "Engineer 2", "Company B", "SF", "url2")
        agent.search_result = [job1, job2]
        agent.apply_result = False  # Applications will fail

        criteria = SearchCriteria(["engineer"], ["remote"])

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await agent.run_automation(criteria, max_applications=2)

        # Verify workflow executed but applications failed
        assert agent.login_called
        assert agent.search_called
        assert agent.apply_called

        assert result['jobs_found'] == 2
        # No successful applications
        assert result['applications_submitted'] == 0
        assert len(result['applied_jobs']) == 0

    @pytest.mark.asyncio
    async def test_run_automation_max_applications_limit(self):
        """Test that max_applications limit is respected"""
        agent = ConcreteJobAgent({})

        agent.initialize_browser = AsyncMock()
        agent.cleanup = AsyncMock()

        # Setup more jobs than max_applications
        jobs = [
            JobPosting(str(i), f"Engineer {i}",
                       f"Company {i}", "Remote", f"url{i}")
            for i in range(10)
        ]
        agent.search_result = jobs

        criteria = SearchCriteria(["engineer"], ["remote"])

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await agent.run_automation(criteria, max_applications=3)

        # Should only apply to 3 jobs despite finding 10
        assert result['jobs_found'] == 10
        assert result['applications_submitted'] == 3
        assert len(result['applied_jobs']) == 3

    @pytest.mark.asyncio
    async def test_run_automation_no_jobs_found(self):
        """Test automation workflow when no jobs are found"""
        agent = ConcreteJobAgent({})

        agent.initialize_browser = AsyncMock()
        agent.cleanup = AsyncMock()

        # No jobs found
        agent.search_result = []

        criteria = SearchCriteria(["rare_skill"], ["nowhere"])
        result = await agent.run_automation(criteria)

        assert result['jobs_found'] == 0
        assert result['applications_submitted'] == 0
        assert result['errors'] == 0
        assert len(result['applied_jobs']) == 0

    @pytest.mark.asyncio
    async def test_run_automation_exception_handling(self):
        """Test that exceptions during automation are handled gracefully"""
        agent = ConcreteJobAgent({})

        agent.initialize_browser = AsyncMock()
        agent.cleanup = AsyncMock()

        # Make login raise an exception
        async def failing_login():
            raise Exception("Network error")

        agent.login = failing_login

        criteria = SearchCriteria(["engineer"], ["remote"])
        result = await agent.run_automation(criteria)

        # Should handle exception gracefully
        assert result['errors'] == 1
        assert result['jobs_found'] == 0
        assert result['applications_submitted'] == 0

        # Cleanup should still be called
        agent.cleanup.assert_called_once()


class TestJobAgentAbstractMethods:
    """Test that abstract methods are properly defined"""

    def test_abstract_methods_exist(self):
        """Test that all abstract methods are defined"""
        # Attempting to instantiate JobAgent directly should raise TypeError
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            JobAgent({})

    def test_concrete_implementation_works(self):
        """Test that concrete implementation can be instantiated"""
        agent = ConcreteJobAgent({})
        assert isinstance(agent, JobAgent)
        assert hasattr(agent, 'login')
        assert hasattr(agent, 'search_jobs')
        assert hasattr(agent, 'apply_to_job')
        assert hasattr(agent, 'get_job_details')


class TestJobAgentIntegration:
    """Test integration scenarios"""

    @pytest.mark.asyncio
    async def test_full_workflow_integration(self):
        """Test a complete workflow with realistic data"""
        config = {
            'credentials': {'linkedin': {'email': 'test@example.com', 'password': 'pass'}},
            'application': {'max_applications_per_session': 5}
        }

        agent = ConcreteJobAgent(config)

        # Mock browser initialization
        agent.initialize_browser = AsyncMock()
        agent.cleanup = AsyncMock()

        # Setup realistic job data
        jobs = [
            JobPosting(
                job_id="linkedin_123",
                title="Senior Software Engineer",
                company="TechCorp",
                location="San Francisco, CA",
                url="https://linkedin.com/jobs/123",
                salary="$150k-$200k",
                platform="linkedin"
            ),
            JobPosting(
                job_id="linkedin_456",
                title="Full Stack Developer",
                company="StartupCo",
                location="Remote",
                url="https://linkedin.com/jobs/456",
                description="Great opportunity for full stack development",
                platform="linkedin"
            )
        ]
        agent.search_result = jobs

        criteria = SearchCriteria(
            keywords=["software engineer", "full stack"],
            locations=["San Francisco", "Remote"],
            experience_level="Senior level",
            easy_apply_only=True
        )

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await agent.run_automation(criteria, max_applications=2)

        # Verify comprehensive result
        assert result['platform'] == 'ConcreteJobAgent'
        assert result['jobs_found'] == 2
        assert result['applications_submitted'] == 2
        assert result['errors'] == 0

        applied_jobs = result['applied_jobs']
        assert len(applied_jobs) == 2
        assert applied_jobs[0]['title'] == "Senior Software Engineer"
        assert applied_jobs[0]['company'] == "TechCorp"
        assert applied_jobs[1]['title'] == "Full Stack Developer"
        assert applied_jobs[1]['company'] == "StartupCo"
