import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False
    structlog = None


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """
    Setup comprehensive logging configuration with both standard and structured logging
    """
    log_config = config.get('logging', {})

    # Get configuration values
    log_level = getattr(logging, log_config.get(
        'level', 'INFO').upper(), logging.INFO)
    log_file = log_config.get('log_file', './logs/job_agent.log')
    max_size_mb = log_config.get('max_log_size_mb', 10)
    backup_count = log_config.get('backup_count', 5)

    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Error file handler (only errors and above)
    error_log_file = log_path.parent / \
        f"{log_path.stem}_errors{log_path.suffix}"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)

    # Setup structured logging if available
    if HAS_STRUCTLOG:
        setup_structured_logging(log_level)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized - Level: {logging.getLevelName(log_level)}, File: {log_file}")

    return logger


def setup_structured_logging(log_level: int):
    """Setup structured logging with structlog"""
    if not HAS_STRUCTLOG:
        return

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class JobAgentLogger:
    """
    Custom logger wrapper for job agent with structured logging and metrics
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.struct_logger = structlog.get_logger(
            name) if HAS_STRUCTLOG else None
        self.metrics = {
            'errors': 0,
            'warnings': 0,
            'applications_attempted': 0,
            'applications_successful': 0,
            'login_attempts': 0,
            'login_successes': 0
        }

    def info(self, message: str, **kwargs):
        """Log info message with optional structured data"""
        self.logger.info(message)
        if kwargs and self.struct_logger:
            self.struct_logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with optional structured data"""
        self.metrics['warnings'] += 1
        self.logger.warning(message)
        if kwargs and self.struct_logger:
            self.struct_logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with optional structured data"""
        self.metrics['errors'] += 1
        self.logger.error(message)
        if kwargs and self.struct_logger:
            self.struct_logger.error(message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message with optional structured data"""
        self.logger.debug(message)
        if kwargs and self.struct_logger:
            self.struct_logger.debug(message, **kwargs)

    def log_application_attempt(self, job_title: str, company: str, platform: str):
        """Log job application attempt with structured data"""
        self.metrics['applications_attempted'] += 1
        if self.struct_logger:
            self.struct_logger.info(
                "Application attempted",
                job_title=job_title,
                company=company,
                platform=platform,
                attempt_number=self.metrics['applications_attempted']
            )
        else:
            self.logger.info(
                f"Application attempted: {job_title} at {company} ({platform})")

    def log_application_success(self, job_title: str, company: str, platform: str):
        """Log successful job application with structured data"""
        self.metrics['applications_successful'] += 1
        if self.struct_logger:
            self.struct_logger.info(
                "Application successful",
                job_title=job_title,
                company=company,
                platform=platform,
                success_number=self.metrics['applications_successful']
            )
        else:
            self.logger.info(
                f"Application successful: {job_title} at {company} ({platform})")

    def log_login_attempt(self, platform: str, email: str):
        """Log login attempt with structured data"""
        self.metrics['login_attempts'] += 1
        masked_email = email[:3] + "***@" + \
            email.split('@')[1] if '@' in email else "***"
        if self.struct_logger:
            self.struct_logger.info(
                "Login attempted",
                platform=platform,
                email=masked_email,
                attempt_number=self.metrics['login_attempts']
            )
        else:
            self.logger.info(f"Login attempted: {platform} ({masked_email})")

    def log_login_success(self, platform: str):
        """Log successful login with structured data"""
        self.metrics['login_successes'] += 1
        if self.struct_logger:
            self.struct_logger.info(
                "Login successful",
                platform=platform,
                success_number=self.metrics['login_successes']
            )
        else:
            self.logger.info(f"Login successful: {platform}")

    def log_proxy_rotation(self, old_proxy: str, new_proxy: str):
        """Log proxy rotation with structured data"""
        if self.struct_logger:
            self.struct_logger.info(
                "Proxy rotated",
                old_proxy=old_proxy,
                new_proxy=new_proxy
            )
        else:
            self.logger.info(f"Proxy rotated: {old_proxy} -> {new_proxy}")

    def log_error_with_context(self, error: Exception, context: Dict[str, Any]):
        """Log error with full context information"""
        self.metrics['errors'] += 1
        if self.struct_logger:
            self.struct_logger.error(
                f"Error occurred: {str(error)}",
                error_type=type(error).__name__,
                error_message=str(error),
                **context
            )
        else:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            self.logger.error(
                f"Error occurred: {str(error)} ({type(error).__name__}) - Context: {context_str}")

    def get_metrics(self) -> Dict[str, int]:
        """Get current metrics"""
        return self.metrics.copy()

    def reset_metrics(self):
        """Reset all metrics"""
        for key in self.metrics:
            self.metrics[key] = 0


class ErrorHandler:
    """
    Centralized error handling for job agent operations
    """

    def __init__(self, logger: JobAgentLogger):
        self.logger = logger

    def handle_login_error(self, platform: str, error: Exception, email: str = "") -> bool:
        """Handle login-related errors"""
        context = {
            'platform': platform,
            'operation': 'login',
            'email': email[:3] + "***" + email[-10:] if email else ""
        }

        if "timeout" in str(error).lower():
            self.logger.warning(
                f"Login timeout for {platform} - network may be slow", **context)
            return True  # Retry login
        elif "credentials" in str(error).lower() or "authentication" in str(error).lower():
            self.logger.error(
                f"Authentication failed for {platform} - check credentials", **context)
            return False  # Don't retry
        elif "captcha" in str(error).lower() or "verification" in str(error).lower():
            self.logger.warning(
                f"Verification required for {platform} - manual intervention needed", **context)
            return False  # Don't retry automatically
        else:
            self.logger.log_error_with_context(error, context)
            return True  # Retry for unknown errors

    def handle_application_error(self, job_title: str, company: str, platform: str, error: Exception) -> bool:
        """Handle job application-related errors"""
        context = {
            'job_title': job_title,
            'company': company,
            'platform': platform,
            'operation': 'apply'
        }

        if "not found" in str(error).lower() or "404" in str(error):
            self.logger.warning(
                f"Job posting no longer available: {job_title} at {company}", **context)
            return False  # Don't retry
        elif "already applied" in str(error).lower():
            self.logger.info(
                f"Already applied to: {job_title} at {company}", **context)
            return False  # Don't retry
        elif "timeout" in str(error).lower():
            self.logger.warning(
                f"Application timeout for: {job_title} at {company}", **context)
            return True  # Retry
        else:
            self.logger.log_error_with_context(error, context)
            return True  # Retry for unknown errors

    def handle_proxy_error(self, proxy_host: str, error: Exception) -> bool:
        """Handle proxy-related errors"""
        context = {
            'proxy_host': proxy_host,
            'operation': 'proxy'
        }

        if "timeout" in str(error).lower() or "connection" in str(error).lower():
            self.logger.warning(
                f"Proxy connection failed: {proxy_host}", **context)
            return True  # Try next proxy
        elif "authentication" in str(error).lower():
            self.logger.error(
                f"Proxy authentication failed: {proxy_host}", **context)
            return False  # Don't retry this proxy
        else:
            self.logger.log_error_with_context(error, context)
            return True  # Try next proxy

    def handle_page_error(self, url: str, error: Exception, operation: str = "navigation") -> bool:
        """Handle page/navigation-related errors"""
        context = {
            'url': url,
            'operation': operation
        }

        if "timeout" in str(error).lower():
            self.logger.warning(
                f"Page timeout for {operation}: {url}", **context)
            return True  # Retry
        elif "403" in str(error) or "blocked" in str(error).lower():
            self.logger.error(
                f"Access blocked for {operation}: {url}", **context)
            return False  # Don't retry
        elif "502" in str(error) or "503" in str(error):
            self.logger.warning(
                f"Server error for {operation}: {url}", **context)
            return True  # Retry
        else:
            self.logger.log_error_with_context(error, context)
            return True  # Retry for unknown errors


def create_logger(name: str, config: Dict[str, Any]) -> JobAgentLogger:
    """Create a job agent logger with the given name and configuration"""
    # Setup logging if not already done
    if not logging.getLogger().handlers:
        setup_logging(config)

    return JobAgentLogger(name)
