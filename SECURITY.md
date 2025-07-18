# Security Configuration Guide

## 🔐 Environment Variables Setup

This application uses environment variables to securely manage sensitive credentials. **Never commit API keys or passwords to the repository.**

### Required Environment Variables

Set these environment variables before running the application:

```bash
# Google Gemini API Key (required for AI features)
export GOOGLE_API_KEY="your_google_api_key_here"

# Optional: Database encryption key
export DB_ENCRYPTION_KEY="your_encryption_key_here"
```

### Setting Environment Variables

#### Linux/macOS:
```bash
# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export GOOGLE_API_KEY="your_key_here"' >> ~/.bashrc
source ~/.bashrc
```

#### Windows:
```cmd
# Set environment variable
setx GOOGLE_API_KEY "your_key_here"
```

#### Using .env file (local development):
Create a `.env` file in the project root (already in .gitignore):
```
GOOGLE_API_KEY=your_key_here
```

## 🛡️ Security Best Practices

### 1. API Key Management
- **Never** commit API keys to git
- Use environment variables or secure key management services
- Rotate API keys regularly
- Use least-privilege access principles

### 2. Configuration Security
- The `config/config.yaml` file uses `${VARIABLE_NAME}` placeholders for secrets
- Local config overrides should use `.gitignore`d files
- Production deployments should use secure secret management

### 3. Git Security
- Always review commits for secrets before pushing
- Use tools like `git-secrets` or `pre-commit` hooks
- The `.gitignore` file is configured to prevent common secret files

### 4. Credential Files
These files are automatically ignored by git:
- `google_credentials.json` - Google OAuth credentials
- `token.json` - Google API tokens
- `.env*` - Environment variable files
- `config/*.local` - Local configuration overrides

## 🚨 What to Do If Secrets Are Exposed

If you accidentally commit secrets:

1. **Immediately** rotate/revoke the exposed credentials
2. Remove secrets from the repository (this commit does that)
3. Update environment variables with new credentials
4. Consider using `git filter-branch` to remove from history if needed

## 📝 Getting API Keys

### Google Gemini API Key:
1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a new API key
3. Set it as an environment variable (never in code)

### Google Sheets API:
1. Enable Google Sheets API in Google Cloud Console
2. Create OAuth2 credentials
3. Download credentials to `google_credentials.json`
4. The app handles OAuth flow automatically

## ✅ Verification

To verify your setup is secure:
```bash
# Check that no secrets are in your config
grep -r "AIza\|sk-" config/ || echo "✅ No API keys found in config"

# Verify environment variables are set
echo "GOOGLE_API_KEY set: ${GOOGLE_API_KEY:+YES}" 
```

Remember: **Security is everyone's responsibility!** 🔐