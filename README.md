# AI-Enhanced Autonomous Job Application Agent

This project is a sophisticated, enterprise-grade autonomous agent for applying to jobs with **AI-powered intelligent filtering and personalized content generation**. Built with Python, Playwright, and Google Gemini AI, it's designed to be undetectable, efficient, and highly successful.

## Target Audience
This tool is for job seekers who want to:
- Automate high-volume job applications with intelligent filtering
- Generate personalized cover letters and optimized content for each job
- Bypass bot detection systems with enterprise-grade evasion
- Scale their job search while maintaining high application quality

## 🤖 AI-Enhanced Features

*   **Intelligent Job Filtering**: AI-powered relevance scoring (1-10 scale) ensures you only apply to suitable positions
*   **Personalized Content Generation**: AI-generated cover letters and resume optimization for each specific job
*   **Resume Parsing & Caching**: Automatic PDF resume analysis with structured data extraction
*   **Smart Application Strategy**: Configurable relevance threshold to focus on high-potential opportunities
*   **Multi-Platform AI Integration**: LinkedIn and Wellfound agents enhanced with AI content injection

## 🛡️ Enterprise Anti-Detection

*   **Residential Proxy Integration**: SmartProxy, Bright Data, Oxylabs support with IP rotation
*   **CAPTCHA Solving**: Automated reCAPTCHA v2/v3 solving with 2captcha/Anti-Captcha services
*   **Advanced Browser Stealth**: Navigator.webdriver spoofing, fingerprint randomization, human behavior simulation
*   **Greenhouse Email Verification Bypass**: Autonomous Gmail IMAP integration for verification handling
*   **Enhanced Evasion**: 18+ stealth parameters, realistic device specs, human-like interaction patterns

## 📊 Core Platform Features

*   **Multi-Platform Architecture**: Extensible base `JobAgent` class with LinkedIn and Wellfound implementations
*   **State Management**: SQLite database prevents duplicate applications with comprehensive tracking
*   **Google Sheets Integration**: Automatic application logging with OAuth2 authentication
*   **Production-Ready**: Designed for headless Linux servers with enterprise scalability
*   **Configuration Driven**: Comprehensive YAML configuration for all settings and AI parameters

## Quick Start

### 🚀 Prerequisites
1. **Gemini API Key**: Get from [Google AI Studio](https://aistudio.google.com/)
2. **Resume PDF**: Your resume file for AI parsing
3. **Platform Credentials**: LinkedIn, Wellfound accounts
4. **Gmail App Password**: For Greenhouse verification

### ⚡ Installation

```bash
# Clone the repository
git clone https://github.com/daniel-he-emory/JobApp.git
cd JobApp

# Run the automated setup script
./setup.sh

# Configure your settings (copy from config.yaml template)
cp config/config.yaml config/my_config.yaml
nano config/my_config.yaml
```

### 🤖 Configuration Setup
```yaml
# Essential AI Configuration
gemini:
  api_key: "your_gemini_api_key_here"

# Resume for AI parsing
application:
  resume_path: "./documents/resume.pdf"

# AI Enhancement Settings
ai:
  relevance_threshold: 6  # Only apply to jobs scoring 6+ out of 10
```

### 🚀 Usage

```bash
# Test AI configuration
./run.sh --dry-run --verbose

# Start AI-enhanced applications
./run.sh --platforms linkedin --max-apps 5

# Full automation with both platforms
./run.sh --platforms linkedin,wellfound --max-apps 10
```

### 🎯 Quick Commands

```bash
# Always use these commands to ensure virtual environment is active:
./run.sh --help                           # Show all options
./run.sh --dry-run                        # Test without applying
./run.sh --platforms linkedin,wellfound   # Run specific platforms
./run.sh --max-apps 5                     # Limit applications
./run.sh --verbose                        # Detailed logging
```

## 🏗️ Architecture Overview

### Core System Components:
```
JobApp/
├── 🤖 AI Services
│   ├── services/ai_enhancer.py         # AI job scoring & content generation
│   ├── utils/gemini_client.py          # Google Gemini AI integration
│   └── utils/resume_parser.py          # PDF resume parsing with caching
│
├── 🛡️ Anti-Detection & Security
│   ├── utils/stealth_browser.py        # Browser fingerprint spoofing
│   ├── utils/proxy_manager.py          # Residential proxy rotation
│   ├── utils/captcha_solver.py         # Automated CAPTCHA solving
│   └── utils/email_verifier.py         # Greenhouse bypass automation
│
├── 🎯 Job Application Agents
│   ├── base_agent.py                   # Abstract base with AI integration
│   ├── agents/linkedin_agent.py        # LinkedIn automation + AI content
│   └── agents/wellfound_agent.py       # Wellfound automation + AI content
│
├── 📊 Orchestration & Tracking
│   ├── main.py                         # Main orchestrator with AI workflow
│   ├── utils/state_manager.py          # SQLite application tracking
│   └── utils/google_sheets_reporter.py # Automatic spreadsheet logging
│
└── ⚙️ Configuration & Setup
    ├── config/config.yaml              # Comprehensive system configuration
    ├── setup.sh                        # Automated environment setup
    └── run.sh                          # Production execution script
```

### 🔄 AI-Enhanced Workflow:
1. **AI Job Analysis**: Score job relevance (1-10) using Gemini AI
2. **Intelligent Filtering**: Only apply to jobs meeting threshold criteria
3. **Content Generation**: Create personalized cover letters and optimize resume
4. **Stealth Application**: Apply with enterprise anti-detection measures
5. **Automatic Tracking**: Log results to database and Google Sheets

---

### Note for AI Assistants

To maintain context across sessions, please navigate to the `AI_CONTEXT.md` file at the beginning of each new session. This file contains a summary of previous interactions and the project's direction.
