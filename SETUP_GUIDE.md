# Setup Guide - Autonomous Job Application Agent

This guide will walk you through setting up and configuring the autonomous job application agent.

## Prerequisites

- Python 3.8 or higher
- Git
- A dedicated Gmail account for job applications
- LinkedIn account (required)
- Wellfound account (optional)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/daniel-he-emory/JobApp.git
cd JobApp
```

### 2. Create Virtual Environment

```bash
python -m venv job_agent_env
source job_agent_env/bin/activate  # On Windows: job_agent_env\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

## Configuration

### 1. Copy Configuration Template

```bash
cp config/config.yaml config/my_config.yaml
```

### 2. Configure Credentials

Edit `config/my_config.yaml` and update the following sections:

#### Platform Credentials

```yaml
credentials:
  linkedin:
    email: "your_linkedin_email@example.com"
    password: "your_linkedin_password"
  
  wellfound:
    email: "your_wellfound_email@example.com" 
    password: "your_wellfound_password"
```

#### Email Verification Setup

For Greenhouse email verification, you'll need a Gmail account with App Password:

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. **Update configuration**:

```yaml
credentials:
  verification_email:
    address: "your_job_applications@gmail.com"
    password: "your_16_char_app_password"  # NOT your regular Gmail password
    imap_server: "imap.gmail.com"
    imap_port: 993
```

### 3. Configure Job Search Settings

```yaml
search_settings:
  default_keywords:
    - "Developer Advocate"
    - "Solutions Engineer" 
    - "Forward Deployed Engineer"
    - "Technical Account Manager"
  
  default_locations:
    - "Canada"
    - "Remote"
    - "San Francisco"
  
  date_posted: "Past week"
  easy_apply_only: true
```

### 4. Configure Application Settings

```yaml
application:
  max_applications_per_session: 5
  default_answers:
    years_experience: "3-5 years"
    willing_to_relocate: false
    authorized_to_work: true
    require_sponsorship: false
    salary_expectation: "Competitive"
```

## Optional: Proxy Configuration

For anonymity and to avoid IP blocking:

### 1. Sign up for a proxy service
- [Bright Data](https://brightdata.com) (recommended)
- [Oxylabs](https://oxylabs.io)
- [ProxyMesh](https://proxymesh.com)

### 2. Configure proxy in config file:

```yaml
proxy:
  enabled: true
  host: "rotating-residential.brightdata.com"
  port: 22225
  username: "your_proxy_username"
  password: "your_proxy_password"
```

## Running the Agent

### Basic Usage

```bash
# Run with default settings
python main.py

# Run specific platforms
python main.py --platforms linkedin,wellfound

# Limit number of applications
python main.py --max-apps 3

# Use custom config file
python main.py --config config/my_config.yaml

# Verbose logging
python main.py --verbose
```

### Command Line Options

- `--config, -c`: Path to configuration file
- `--platforms, -p`: Comma-separated list of platforms (linkedin,wellfound)
- `--max-apps, -m`: Maximum applications per platform
- `--dry-run, -d`: Show what would be done without applying
- `--verbose, -v`: Enable verbose logging

## Monitoring and Logs

### Log Files

Logs are stored in `logs/job_agent.log` by default. Monitor progress:

```bash
tail -f logs/job_agent.log
```

### Application Database

Applied jobs are tracked in `data/job_applications.db`. You can query this with:

```bash
sqlite3 data/job_applications.db "SELECT * FROM applied_jobs ORDER BY applied_date DESC LIMIT 10;"
```

## Deploying to Remote Server

### 1. Server Requirements

- Ubuntu 18.04+ or similar Linux distribution
- Python 3.8+
- At least 2GB RAM
- 10GB storage

### 2. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3 python3-pip python3-venv git -y

# Install system dependencies for Playwright
sudo apt install libnss3 libxss1 libasound2 libxtst6 libxrandr2 libasound2 libpangocairo-1.0-0 libatk1.0-0 libcairo-gobject2 libgtk-3-0 libgdk-pixbuf2.0-0 -y
```

### 3. Deploy Application

```bash
# Clone repository
git clone https://github.com/daniel-he-emory/JobApp.git
cd JobApp

# Setup virtual environment
python3 -m venv job_agent_env
source job_agent_env/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Copy and configure
cp config/config.yaml config/production_config.yaml
# Edit production_config.yaml with your settings
```

### 4. Run as Service (Optional)

Create a systemd service for automatic startup:

```bash
sudo nano /etc/systemd/system/job-agent.service
```

```ini
[Unit]
Description=Autonomous Job Application Agent
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/JobApp
Environment=PATH=/home/your_username/JobApp/job_agent_env/bin
ExecStart=/home/your_username/JobApp/job_agent_env/bin/python main.py --config config/production_config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable job-agent
sudo systemctl start job-agent
```

### 5. Schedule with Cron

Run the agent automatically at specific times:

```bash
crontab -e
```

Add line to run daily at 9 AM:
```
0 9 * * * cd /home/your_username/JobApp && ./job_agent_env/bin/python main.py --config config/production_config.yaml
```

## Troubleshooting

### Common Issues

#### 1. "No module named 'playwright'"
```bash
pip install playwright
playwright install chromium
```

#### 2. "LinkedIn login failed"
- Check credentials in config file
- Try logging in manually first to handle any security challenges
- Consider using 2FA

#### 3. "Email verification not working"
- Ensure Gmail App Password is correct (16 characters, no spaces)
- Check IMAP is enabled in Gmail settings
- Verify email credentials

#### 4. "Browser launch failed on server"
```bash
# Install missing dependencies
sudo apt install chromium-browser
export DISPLAY=:99
```

#### 5. "Permission denied" errors
```bash
chmod +x main.py
# Or run with python explicitly
python main.py
```

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
python main.py --verbose --config config/my_config.yaml
```

### Testing Configuration

Test your configuration without applying to jobs:

```bash
python main.py --dry-run --verbose
```

## Security Considerations

1. **Never commit credentials** to version control
2. **Use App Passwords** for Gmail, not your main password
3. **Consider using a VPN** in addition to proxies
4. **Regularly rotate credentials** and proxy settings
5. **Monitor for unusual account activity**

## Support

If you encounter issues:

1. Check the logs in `logs/job_agent.log`
2. Verify your configuration against this guide
3. Test individual components (login, search, etc.)
4. Create an issue on GitHub with logs and error details

## Advanced Configuration

### Custom Resume and Cover Letter

Place your documents in a `documents/` folder:

```yaml
application:
  resume_path: "./documents/resume.pdf"
  cover_letter_template: "./documents/cover_letter_template.txt"
```

### Platform-Specific Settings

Customize behavior per platform:

```yaml
platforms:
  linkedin:
    enabled: true
    search_url: "https://www.linkedin.com/jobs/search/"
    easy_apply_filter: true
    
  wellfound:
    enabled: true
    search_url: "https://wellfound.com/jobs"
```

This completes the setup guide. The agent should now be ready to run autonomously and handle job applications across multiple platforms.