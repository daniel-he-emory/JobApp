from config.config_loader import ConfigLoader, get_config, reload_config
import pytest
import os
import yaml
from unittest.mock import patch

import sys
sys.path.append('/home/daniel/JobApp')


class TestConfigLoader:
    """Test configuration loading and validation"""

    def test_load_config_from_file(self, config_file, sample_config):
        """Test loading configuration from YAML file"""
        loader = ConfigLoader(str(config_file))
        config = loader.load_config()

        assert config['credentials']['linkedin']['email'] == 'test@example.com'
        assert config['application']['personal_info']['first_name'] == 'John'
        assert config['search_settings']['easy_apply_only'] is True

    def test_load_config_missing_file(self, temp_dir):
        """Test behavior when config file is missing"""
        missing_file = temp_dir / 'missing.yaml'
        loader = ConfigLoader(str(missing_file))

        # Should not raise exception, just log warning
        config = loader.load_config()
        assert isinstance(config, dict)

    def test_environment_variable_override(self, config_file):
        """Test that environment variables override file config"""
        with patch.dict(os.environ, {
            'LINKEDIN_EMAIL': 'env@example.com',
            'MAX_APPLICATIONS_PER_SESSION': '10',
            'BROWSER_HEADLESS': 'false'
        }):
            loader = ConfigLoader(str(config_file))
            config = loader.load_config()

            assert config['credentials']['linkedin']['email'] == 'env@example.com'
            assert config['application']['max_applications_per_session'] == 10
            assert config['browser']['headless'] is False

    def test_env_value_conversion(self):
        """Test environment variable type conversion"""
        loader = ConfigLoader()

        # Test boolean conversion
        assert loader._convert_env_value('true') is True
        assert loader._convert_env_value('false') is False
        assert loader._convert_env_value('yes') is True
        assert loader._convert_env_value('no') is False
        assert loader._convert_env_value('1') is True
        assert loader._convert_env_value('0') is False

        # Test numeric conversion
        assert loader._convert_env_value('123') == 123
        assert loader._convert_env_value('123.45') == 123.45

        # Test string fallback
        assert loader._convert_env_value('test_string') == 'test_string'

    def test_nested_config_setting(self):
        """Test setting nested configuration values"""
        loader = ConfigLoader()
        loader.config = {}

        loader._set_nested_config(['level1', 'level2', 'key'], 'value')
        assert loader.config['level1']['level2']['key'] == 'value'

    def test_nested_config_getting(self):
        """Test getting nested configuration values"""
        loader = ConfigLoader()
        loader.config = {
            'level1': {
                'level2': {
                    'key': 'value'
                }
            }
        }

        result = loader._get_nested_config(['level1', 'level2', 'key'])
        assert result == 'value'

        # Test missing path
        result = loader._get_nested_config(['missing', 'path'])
        assert result is None

    def test_placeholder_detection(self):
        """Test detection of placeholder values"""
        loader = ConfigLoader()

        # Test placeholder detection
        assert loader._is_placeholder_value('your_email@example.com') is True
        assert loader._is_placeholder_value('your_linkedin_password') is True
        assert loader._is_placeholder_value('placeholder_value') is True
        assert loader._is_placeholder_value('change_me') is True

        # Test real values
        assert loader._is_placeholder_value('real@email.com') is False
        assert loader._is_placeholder_value('actual_password') is False
        assert loader._is_placeholder_value(123) is False

    def test_validation_missing_credentials(self, temp_dir):
        """Test validation fails with missing critical credentials"""
        # Create config with placeholder values
        bad_config = {
            'credentials': {
                'verification_email': {
                    'address': 'your_email@example.com',  # placeholder
                    'password': 'your_password'  # placeholder
                }
            }
        }

        config_path = temp_dir / 'bad_config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(bad_config, f)

        loader = ConfigLoader(str(config_path))
        with pytest.raises(ValueError, match="Missing required configurations"):
            loader.load_config()

    def test_validation_no_platform_credentials(self, temp_dir):
        """Test validation fails when no platform credentials are configured"""
        # Config with verification email but no platform credentials
        config = {
            'credentials': {
                'verification_email': {
                    'address': 'real@email.com',
                    'password': 'real_password'
                },
                'linkedin': {
                    'email': 'your_linkedin@example.com',  # placeholder
                    'password': 'placeholder'
                },
                'wellfound': {
                    'email': 'your_wellfound@example.com',  # placeholder
                    'password': 'placeholder'
                }
            }
        }

        config_path = temp_dir / 'no_platforms.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(str(config_path))
        with pytest.raises(ValueError, match="No platform credentials configured"):
            loader.load_config()

    def test_validation_success(self, config_file):
        """Test validation passes with proper config"""
        loader = ConfigLoader(str(config_file))
        config = loader.load_config()  # Should not raise exception
        assert isinstance(config, dict)

    def test_get_method_dot_notation(self, config_file):
        """Test get method with dot notation"""
        loader = ConfigLoader(str(config_file))
        loader.load_config()

        # Test dot notation
        email = loader.get('credentials.linkedin.email')
        assert email == 'test@example.com'

        # Test simple key
        browser = loader.get('browser')
        assert browser['headless'] is True

        # Test default value
        missing = loader.get('missing.key', 'default')
        assert missing == 'default'

    def test_get_credentials(self, config_file):
        """Test platform credential retrieval"""
        loader = ConfigLoader(str(config_file))
        loader.load_config()

        linkedin_creds = loader.get_credentials('linkedin')
        assert linkedin_creds['email'] == 'test@example.com'
        assert linkedin_creds['password'] == 'test_password'

        missing_creds = loader.get_credentials('missing_platform')
        assert missing_creds is None

    def test_get_proxy_config_enabled(self, temp_dir):
        """Test proxy config retrieval when enabled"""
        config = {
            'proxy': {
                'enabled': True,
                'host': 'proxy.example.com',
                'port': 8080
            }
        }

        config_path = temp_dir / 'proxy_config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(str(config_path))
        loader.load_config()

        proxy_config = loader.get_proxy_config()
        assert proxy_config is not None
        assert proxy_config['host'] == 'proxy.example.com'
        assert proxy_config['port'] == 8080

    def test_get_proxy_config_disabled(self, config_file):
        """Test proxy config when disabled"""
        loader = ConfigLoader(str(config_file))
        loader.load_config()

        proxy_config = loader.get_proxy_config()
        assert proxy_config is None

    def test_get_search_settings(self, config_file):
        """Test search settings retrieval"""
        loader = ConfigLoader(str(config_file))
        loader.load_config()

        search_settings = loader.get_search_settings()
        assert 'default_keywords' in search_settings
        assert 'Developer' in search_settings['default_keywords']

    def test_get_application_settings(self, config_file):
        """Test application settings retrieval"""
        loader = ConfigLoader(str(config_file))
        loader.load_config()

        app_settings = loader.get_application_settings()
        assert app_settings['max_applications_per_session'] == 5
        assert app_settings['personal_info']['first_name'] == 'John'

    def test_get_browser_settings(self, config_file):
        """Test browser settings retrieval"""
        loader = ConfigLoader(str(config_file))
        loader.load_config()

        browser_settings = loader.get_browser_settings()
        assert browser_settings['headless'] is True
        assert browser_settings['user_agent'] == 'test-agent'

    def test_save_config(self, temp_dir, sample_config):
        """Test saving configuration to file"""
        loader = ConfigLoader()
        loader.config = sample_config

        output_path = temp_dir / 'saved_config.yaml'
        loader.save_config(str(output_path))

        # Verify file was created and content is correct
        assert output_path.exists()
        with open(output_path, 'r') as f:
            saved_config = yaml.safe_load(f)

        assert saved_config['credentials']['linkedin']['email'] == 'test@example.com'


class TestGlobalConfig:
    """Test global configuration functions"""

    def test_get_config_singleton(self):
        """Test that get_config returns singleton instance"""
        with patch('config.config_loader.ConfigLoader') as MockLoader:
            mock_instance = MockLoader.return_value
            mock_instance.config = {'test': 'value'}
            mock_instance.load_config.return_value = {'test': 'value'}

            # First call creates instance
            config1 = get_config()
            assert config1 == {'test': 'value'}

            # Second call reuses instance
            config2 = get_config()
            assert config1 is config2
            assert MockLoader.call_count == 1

    def test_reload_config(self, config_file):
        """Test reloading configuration"""
        # Mock the global variable to test reload
        with patch('config.config_loader._config_loader', None):
            config = reload_config(str(config_file))
            assert config['credentials']['linkedin']['email'] == 'test@example.com'


class TestConfigValidationEdgeCases:
    """Test edge cases in configuration validation"""

    def test_invalid_yaml_file(self, temp_dir):
        """Test handling of invalid YAML syntax"""
        invalid_yaml = temp_dir / 'invalid.yaml'
        with open(invalid_yaml, 'w') as f:
            f.write('invalid: yaml: content: [unclosed bracket')

        loader = ConfigLoader(str(invalid_yaml))
        config = loader.load_config()  # Should handle gracefully
        assert isinstance(config, dict)

    def test_env_override_nested_creation(self):
        """Test that env overrides create nested structure correctly"""
        loader = ConfigLoader()
        loader.config = {}

        with patch.dict(os.environ, {'LINKEDIN_EMAIL': 'test@env.com'}):
            loader._load_env_overrides()

            assert loader.config['credentials']['linkedin']['email'] == 'test@env.com'

    def test_numeric_env_values_edge_cases(self):
        """Test edge cases in numeric environment variable conversion"""
        loader = ConfigLoader()

        # Test invalid numeric values
        assert loader._convert_env_value('not_a_number') == 'not_a_number'
        assert loader._convert_env_value(
            '12.34.56') == '12.34.56'  # Invalid float
        assert loader._convert_env_value('') == ''  # Empty string
