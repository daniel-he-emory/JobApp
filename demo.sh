#!/bin/bash
# JobApp Demonstration Script
# Shows all the ways to visualize the system working

echo "🚀 JobApp Autonomous Agent - Demonstration"
echo "========================================="

# Activate virtual environment
source job_agent_env/bin/activate

echo ""
echo "📋 1. DRY RUN - See what the agent would do without applying"
echo "-----------------------------------------------------------"
echo "Command: ./run.sh --config test_config.yaml --dry-run --verbose --max-apps 2"
echo ""
echo "This shows:"
echo "  ✓ Configuration validation"
echo "  ✓ Platform connection simulation"
echo "  ✓ Job search simulation"
echo "  ✓ Application workflow simulation"
echo "  ✓ Email verification simulation"
echo "  ✓ Database operations"
echo ""
read -p "Press Enter to run dry-run demo..."

./run.sh --config test_config.yaml --dry-run --verbose --max-apps 2

echo ""
echo "📊 2. DATABASE INSPECTION - See stored applications"
echo "--------------------------------------------------"
echo "Command: sqlite3 data/job_applications.db"
echo ""
echo "Useful queries:"
echo "  SELECT * FROM applied_jobs ORDER BY applied_date DESC LIMIT 5;"
echo "  SELECT platform, COUNT(*) FROM applied_jobs GROUP BY platform;"
echo "  SELECT * FROM applied_jobs WHERE status='applied';"
echo ""

if [ -f "data/job_applications.db" ]; then
    echo "Current database contents:"
    sqlite3 data/job_applications.db "SELECT COUNT(*) as total_applications FROM applied_jobs;"
    sqlite3 data/job_applications.db "SELECT platform, COUNT(*) as count FROM applied_jobs GROUP BY platform;"
else
    echo "No database found yet - run the agent first to create it"
fi

echo ""
echo "📁 3. LOG FILE MONITORING - Real-time activity"
echo "---------------------------------------------"
echo "Command: tail -f logs/job_agent.log"
echo ""
echo "Shows real-time:"
echo "  ✓ Login attempts and success/failure"
echo "  ✓ Job search results and filtering"
echo "  ✓ Application submission steps"
echo "  ✓ Email verification processing"
echo "  ✓ Error handling and retries"
echo ""

if [ -f "logs/job_agent.log" ]; then
    echo "Latest log entries:"
    tail -5 logs/job_agent.log
else
    echo "No log file found yet - run the agent first to create it"
fi

echo ""
echo "🌐 4. BROWSER VISUALIZATION - Watch the automation"
echo "------------------------------------------------"
echo "Set browser.headless: false in config to see:"
echo "  ✓ LinkedIn login and navigation"
echo "  ✓ Job search and filtering"
echo "  ✓ Application form filling"
echo "  ✓ Email verification handling"
echo ""

echo ""
echo "📈 5. GOOGLE SHEETS INTEGRATION - Track applications"
echo "--------------------------------------------------"
echo "Configure Google Sheets to see:"
echo "  ✓ Real-time application tracking"
echo "  ✓ Date, platform, job title, company"
echo "  ✓ Application URLs and status"
echo ""

echo ""
echo "🎯 QUICK TEST COMMANDS:"
echo "======================"
echo ""
echo "# Test with fake credentials (dry-run):"
echo "./run.sh --config test_config.yaml --dry-run --verbose"
echo ""
echo "# Test with real credentials (1 application):"
echo "./run.sh --config my_config.yaml --max-apps 1 --verbose"
echo ""
echo "# Test specific platform:"
echo "./run.sh --platforms linkedin --max-apps 1 --verbose"
echo ""
echo "# Monitor in real-time:"
echo "tail -f logs/job_agent.log"
echo ""
echo "# Check database:"
echo "sqlite3 data/job_applications.db 'SELECT * FROM applied_jobs;'"
echo ""

echo "🎉 Ready to test! Use the commands above to see the system in action."