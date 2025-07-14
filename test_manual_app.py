#!/usr/bin/env python3
"""
Test manual application reporting to Google Sheets
"""
from datetime import datetime
from utils.google_sheets_reporter import GoogleSheetsReporter
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


def test_manual_application():
    """Test adding a manual application to Google Sheets"""

    # Create a sample application summary
    test_summary = {
        'platform_results': [
            {
                'platform': 'linkedin',
                'applied_jobs': [
                    {
                        'job_id': 'test123',
                        'title': 'Solutions Engineer',
                        'company': 'Test Company Inc.',
                        'url': 'https://linkedin.com/jobs/test123',
                        'applied_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                ]
            }
        ]
    }

    print("📝 Testing manual application entry...")
    print(
        f"Test job: {test_summary['platform_results'][0]['applied_jobs'][0]['title']} at {test_summary['platform_results'][0]['applied_jobs'][0]['company']}")

    try:
        # Initialize Google Sheets reporter
        reporter = GoogleSheetsReporter(
            spreadsheet_id='1nY5Q6_JroKLly_OBA8FRYUSzR1rzGXX8u5XupbR-oTI',
            sheet_name='Job Applications'
        )

        # Test connection
        if reporter.test_connection():
            print("✅ Google Sheets connection successful!")

            # Try to add the test application
            if reporter.append_applications(test_summary):
                print("🎉 Successfully added test application to Google Sheets!")
                print("Check your Google Sheet to see the entry.")
            else:
                print("❌ Failed to add application to Google Sheets")
        else:
            print("❌ Google Sheets connection failed")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    test_manual_application()
