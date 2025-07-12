import pytest
import os
import tempfile
import sqlite3
from pathlib import Path
import yaml

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_config():
    """Provide a sample configuration for testing"""
    return {
        'credentials': {
            'linkedin': {
                'email': 'test@example.com',
                'password': 'test_password'
            },
            'wellfound': {
                'email': 'test@example.com', 
                'password': 'test_password'
            },
            'verification_email': {
                'address': 'test@gmail.com',
                'password': 'app_password',
                'imap_server': 'imap.gmail.com',
                'imap_port': 993
            }
        },
        'application': {
            'personal_info': {
                'first_name': 'John',
                'last_name': 'Doe',
                'phone_number': '555-123-4567'
            },
            'max_applications_per_session': 5,
            'delay_between_applications': 30,
            'resume_path': './documents/resume.pdf',
            'default_answers': {
                'years_experience': '3-5 years',
                'willing_to_relocate': False,
                'authorized_to_work': True,
                'require_sponsorship': False
            }
        },
        'search_settings': {
            'default_keywords': ['Developer', 'Engineer'],
            'default_locations': ['Remote', 'San Francisco'],
            'experience_levels': ['Mid-Senior level'],
            'easy_apply_only': True
        },
        'state': {
            'storage_type': 'sqlite',
            'database_path': './data/test_applications.db'
        },
        'browser': {
            'headless': True,
            'user_agent': 'test-agent'
        },
        'logging': {
            'level': 'DEBUG'
        }
    }

@pytest.fixture
def config_file(temp_dir, sample_config):
    """Create a temporary config file"""
    config_path = temp_dir / 'config.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(sample_config, f)
    return config_path

@pytest.fixture
def test_db(temp_dir):
    """Create a test SQLite database"""
    db_path = temp_dir / 'test.db'
    conn = sqlite3.connect(str(db_path))
    
    # Create applications table
    conn.execute('''
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE,
            company TEXT,
            title TEXT,
            url TEXT,
            platform TEXT,
            status TEXT,
            applied_date TEXT,
            application_data TEXT
        )
    ''')
    
    # Create statistics table
    conn.execute('''
        CREATE TABLE statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            platform TEXT,
            applications_submitted INTEGER,
            jobs_found INTEGER,
            session_duration_minutes REAL
        )
    ''')
    
    conn.commit()
    conn.close()
    return db_path

@pytest.fixture
def mock_browser():
    """Mock browser context for testing"""
    class MockBrowser:
        def __init__(self):
            self.headless = True
            
        async def new_context(self, **kwargs):
            return MockBrowserContext()
    
    class MockBrowserContext:
        def __init__(self):
            pass
            
        async def new_page(self):
            return MockPage()
            
        async def close(self):
            pass
    
    class MockPage:
        def __init__(self):
            self.url = 'https://example.com'
            
        async def goto(self, url, **kwargs):
            self.url = url
            
        async def wait_for_selector(self, selector, **kwargs):
            pass
            
        async def click(self, selector, **kwargs):
            pass
            
        async def fill(self, selector, text, **kwargs):
            pass
            
        async def close(self):
            pass
            
        async def locator(self, selector):
            return MockLocator()
    
    class MockLocator:
        def __init__(self):
            pass
            
        async def count(self):
            return 1
            
        async def nth(self, index):
            return self
            
        async def text_content(self):
            return 'Mock text'
            
        async def get_attribute(self, attr):
            return 'mock-value'
            
        async def fill(self, text):
            pass
            
        async def click(self):
            pass
    
    return MockBrowser()