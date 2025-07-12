# Autonomous Job Application Agent

This project is a sophisticated, end-to-end autonomous agent for applying to jobs. It is written in Python using Playwright and is designed to be robust, modular, and well-documented.

## Target Audience
This tool is for anyone frustrated with the job application process who is looking for a seamless way to automate applications, especially for roles that use Greenhouse and require email verification.

## Features

*   **Multi-Platform Modularity**: The architecture is extensible to support multiple job boards. It uses a base `JobAgent` class with specific implementations for each platform (e.g., `LinkedInAgent`, `WellfoundAgent`).
*   **Greenhouse Email Verification Bypass**: The agent can autonomously handle Greenhouse email verification by parsing verification links from a dedicated Gmail account.
*   **Anonymity & Anti-Tracking**: Integrates with rotating residential proxy services (e.g., Bright Data, Oxylabs) to prevent IP tracking and blocking.
*   **State Management**: Prevents duplicate applications by tracking applied jobs in a local SQLite database.
*   **Headless Operation**: Designed to run on a remote, headless Linux server.
*   **Configuration Driven**: All user-specific settings (credentials, search parameters, proxy settings) are managed in a `config.yaml` file.

## Quick Start

### 🚀 Automated Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/daniel-he-emory/JobApp.git
cd JobApp

# Run the automated setup script
./setup.sh

# Edit your configuration
nano config/my_config.yaml

# Test the setup
./run.sh --dry-run --verbose

# Start applying to jobs
./run.sh --platforms linkedin --max-apps 3
```

### ⚡ Manual Setup

If you prefer manual setup, see the detailed [SETUP_GUIDE.md](SETUP_GUIDE.md).

### 🎯 Quick Commands

```bash
# Always use these commands to ensure virtual environment is active:
./run.sh --help                           # Show all options
./run.sh --dry-run                        # Test without applying
./run.sh --platforms linkedin,wellfound   # Run specific platforms
./run.sh --max-apps 5                     # Limit applications
./run.sh --verbose                        # Detailed logging
```

## Architecture Overview

The project is structured as follows:

*   `main.py`: The main execution script that orchestrates the agents.
*   `config.yaml`: Configuration file for all user-specific settings.
*   `database.py`: Handles state management with an SQLite database.
*   `agents/`: Directory for job board specific agents.
    *   `base_agent.py`: Defines the abstract base class for all agents.
    *   `linkedin_agent.py`: Implementation for applying to jobs on LinkedIn.
*   `utils/`: Directory for utility modules.
    *   `email_parser.py`: Module for parsing emails to find verification links.
    *   `proxy_manager.py`: Module for managing proxy configurations.

---

### Note for AI Assistants

To maintain context across sessions, please navigate to the `AI_CONTEXT.md` file at the beginning of each new session. This file contains a summary of previous interactions and the project's direction.
