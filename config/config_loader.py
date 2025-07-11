import yaml
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

class ConfigLoader:
    """
    Configuration loader that supports both YAML files and environment variables
    Provides fallback mechanisms and validation
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file and environment variables
        Environment variables take precedence over file config
        """
        # Load from YAML file
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    self.config = yaml.safe_load(file) or {}
                self.logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                self.logger.error(f"Error loading config file: {str(e)}")
                self.config = {}
        else:
            self.logger.warning(f"Config file {self.config_path} not found, using environment variables only")
            self.config = {}
        
        # Override with environment variables
        self._load_env_overrides()
        
        # Validate critical configuration
        self._validate_config()
        
        return self.config
    
    def _load_env_overrides(self):
        """Load configuration overrides from environment variables"""
        env_mappings = {
            # LinkedIn credentials
            'LINKEDIN_EMAIL': ['credentials', 'linkedin', 'email'],
            'LINKEDIN_PASSWORD': ['credentials', 'linkedin', 'password'],
            
            # Wellfound credentials  
            'WELLFOUND_EMAIL': ['credentials', 'wellfound', 'email'],
            'WELLFOUND_PASSWORD': ['credentials', 'wellfound', 'password'],
            
            # Email verification credentials
            'VERIFICATION_EMAIL': ['credentials', 'verification_email', 'address'],
            'VERIFICATION_PASSWORD': ['credentials', 'verification_email', 'password'],
            'VERIFICATION_IMAP_SERVER': ['credentials', 'verification_email', 'imap_server'],
            'VERIFICATION_IMAP_PORT': ['credentials', 'verification_email', 'imap_port'],
            
            # Proxy settings
            'PROXY_ENABLED': ['proxy', 'enabled'],
            'PROXY_HOST': ['proxy', 'host'],
            'PROXY_PORT': ['proxy', 'port'],
            'PROXY_USERNAME': ['proxy', 'username'],
            'PROXY_PASSWORD': ['proxy', 'password'],
            
            # Application settings
            'MAX_APPLICATIONS_PER_SESSION': ['application', 'max_applications_per_session'],
            'MAX_APPLICATIONS_PER_PLATFORM': ['application', 'max_applications_per_platform'],
            'RESUME_PATH': ['application', 'resume_path'],
            
            # Browser settings
            'BROWSER_HEADLESS': ['browser', 'headless'],
            
            # State management
            'STATE_STORAGE_TYPE': ['state', 'storage_type'],
            'STATE_DATABASE_PATH': ['state', 'database_path'],
            
            # Logging
            'LOG_LEVEL': ['logging', 'level'],
            'LOG_FILE': ['logging', 'log_file'],
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                converted_value = self._convert_env_value(value)
                self._set_nested_config(config_path, converted_value)
                self.logger.debug(f"Set config from env: {'.'.join(config_path)} = {converted_value}")
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type"""
        # Handle boolean values
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        
        # Handle numeric values
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _set_nested_config(self, path: list, value: Any):
        """Set a nested configuration value"""
        current = self.config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value
    
    def _validate_config(self):
        """Validate critical configuration settings"""
        required_configs = [
            ['credentials', 'verification_email', 'address'],
            ['credentials', 'verification_email', 'password'],
        ]
        
        missing_configs = []
        for config_path in required_configs:
            value = self._get_nested_config(config_path)
            # Check if value is missing or is a placeholder
            if not value or self._is_placeholder_value(value):
                missing_configs.append('.'.join(config_path))
        
        # Fail fast if critical configurations are missing
        if missing_configs:
            raise ValueError(f"Missing required configurations: {', '.join(missing_configs)}. "
                           "Please update your config file or set environment variables.")
        
        # Validate platform credentials (at least one platform should be configured)
        platforms_configured = []
        linkedin_email = self._get_nested_config(['credentials', 'linkedin', 'email'])
        if linkedin_email and not self._is_placeholder_value(linkedin_email):
            platforms_configured.append('LinkedIn')
        
        wellfound_email = self._get_nested_config(['credentials', 'wellfound', 'email'])
        if wellfound_email and not self._is_placeholder_value(wellfound_email):
            platforms_configured.append('Wellfound')
        
        if not platforms_configured:
            raise ValueError("No platform credentials configured. At least one platform "
                           "(LinkedIn or Wellfound) must have valid email/password credentials.")
        else:
            self.logger.info(f"Configured platforms: {', '.join(platforms_configured)}")
    
    def _is_placeholder_value(self, value: str) -> bool:
        """Check if a value is a placeholder that needs to be replaced"""
        if not isinstance(value, str):
            return False
        
        placeholder_indicators = [
            'your_', 'example.com', 'placeholder', 'change_me', 'todo',
            'your_app_password', 'your_linkedin_', 'your_wellfound_'
        ]
        
        value_lower = value.lower()
        return any(indicator in value_lower for indicator in placeholder_indicators)
    
    def _get_nested_config(self, path: list) -> Any:
        """Get a nested configuration value"""
        current = self.config
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with dot notation support"""
        if '.' in key:
            path = key.split('.')
            return self._get_nested_config(path)
        else:
            return self.config.get(key, default)
    
    def get_credentials(self, platform: str) -> Optional[Dict[str, str]]:
        """Get credentials for a specific platform"""
        return self._get_nested_config(['credentials', platform])
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """Get proxy configuration if enabled"""
        proxy_config = self._get_nested_config(['proxy'])
        if proxy_config and proxy_config.get('enabled', False):
            return proxy_config
        return None
    
    def get_search_settings(self) -> Dict[str, Any]:
        """Get job search settings"""
        return self._get_nested_config(['search_settings']) or {}
    
    def get_application_settings(self) -> Dict[str, Any]:
        """Get application settings"""
        return self._get_nested_config(['application']) or {}
    
    def get_browser_settings(self) -> Dict[str, Any]:
        """Get browser configuration"""
        return self._get_nested_config(['browser']) or {}
    
    def save_config(self, output_path: Optional[str] = None):
        """Save current configuration to YAML file"""
        output_path = output_path or self.config_path
        
        try:
            with open(output_path, 'w', encoding='utf-8') as file:
                yaml.dump(self.config, file, default_flow_style=False, indent=2)
            self.logger.info(f"Configuration saved to {output_path}")
        except Exception as e:
            self.logger.error(f"Error saving config: {str(e)}")

# Global config instance
_config_loader = None

def get_config() -> Dict[str, Any]:
    """Get global configuration instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
        _config_loader.load_config()
    return _config_loader.config

def reload_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """Reload configuration from file"""
    global _config_loader
    _config_loader = ConfigLoader(config_path)
    return _config_loader.load_config()