import os.path
import logging
from datetime import datetime
from typing import Dict, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Sheets API scope
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class GoogleSheetsReporter:
    """
    Handles reporting of application results to a Google Sheet.
    """
    def __init__(self, spreadsheet_id: str, sheet_name: str, credentials_path: str = 'google_credentials.json'):
        """
        Initializes the reporter and handles authentication.
        
        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID
            sheet_name: The name of the sheet within the spreadsheet
            credentials_path: Path to the Google credentials JSON file
        """
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.credentials_path = credentials_path
        self.token_path = 'token.json'
        self.logger = logging.getLogger(__name__)
        
        # Initialize Google Sheets service
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize Google Sheets service with proper authentication."""
        try:
            creds = self._get_credentials()
            if creds:
                self.service = build('sheets', 'v4', credentials=creds)
                self.logger.info("Google Sheets service initialized successfully")
            else:
                self.logger.error("Failed to obtain Google Sheets credentials")
        except Exception as e:
            self.logger.error(f"Error initializing Google Sheets service: {str(e)}")
            self.service = None

    def _get_credentials(self) -> Optional[Credentials]:
        """
        Gets user credentials for the Google Sheets API, handling the OAuth2 flow.
        
        Returns:
            Credentials object if successful, None otherwise
        """
        creds = None
        
        try:
            # Check if token file exists and load existing credentials
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                self.logger.debug("Loaded existing credentials from token.json")
            
            # If there are no valid credentials available, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        self.logger.info("Refreshed expired Google credentials")
                    except Exception as e:
                        self.logger.warning(f"Failed to refresh credentials: {str(e)}")
                        creds = None
                
                # If refresh failed or no credentials, start OAuth flow
                if not creds:
                    if not os.path.exists(self.credentials_path):
                        self.logger.error(f"Google credentials file not found: {self.credentials_path}")
                        self.logger.error("Please download credentials from Google Cloud Console and save as google_credentials.json")
                        return None
                    
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_path, SCOPES
                        )
                        # Try to run local server, fallback to console flow if needed
                        try:
                            creds = flow.run_local_server(port=0, open_browser=True)
                            self.logger.info("Completed OAuth2 flow via local server")
                        except Exception as e:
                            self.logger.warning(f"Local server OAuth failed: {str(e)}, trying console flow")
                            creds = flow.run_console()
                            self.logger.info("Completed OAuth2 flow via console")
                        
                    except Exception as e:
                        self.logger.error(f"OAuth2 flow failed: {str(e)}")
                        return None
                
                # Save the credentials for future use
                if creds:
                    try:
                        with open(self.token_path, 'w') as token:
                            token.write(creds.to_json())
                        self.logger.info("Saved new credentials to token.json")
                    except Exception as e:
                        self.logger.warning(f"Failed to save credentials: {str(e)}")
            
            return creds
            
        except Exception as e:
            self.logger.error(f"Error getting Google credentials: {str(e)}")
            return None

    def _ensure_headers(self) -> bool:
        """
        Ensures the sheet has proper headers. Creates them if they don't exist.
        
        Returns:
            True if headers are present/created successfully, False otherwise
        """
        if not self.service:
            return False
            
        try:
            # Check if sheet exists and has headers
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:F1"
            ).execute()
            
            values = result.get('values', [])
            expected_headers = ['Date', 'Platform', 'Job Title', 'Company', 'Job URL', 'Status']
            
            # If no headers or incorrect headers, add them
            if not values or values[0] != expected_headers:
                self.logger.info("Adding/updating headers to Google Sheet")
                body = {
                    'values': [expected_headers]
                }
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A1:F1",
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                self.logger.info("Headers added successfully")
            
            return True
            
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.error(f"Spreadsheet not found: {self.spreadsheet_id}")
            elif e.resp.status == 403:
                self.logger.error("Permission denied. Please share the spreadsheet with your service account")
            else:
                self.logger.error(f"HTTP error ensuring headers: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error ensuring headers: {str(e)}")
            return False

    def append_applications(self, summary: dict) -> bool:
        """
        Appends successfully applied jobs to the specified Google Sheet.
        
        Args:
            summary: Dictionary containing platform results with applied jobs
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            self.logger.warning("Google Sheets service not available, skipping reporting")
            return False
        
        try:
            # Ensure headers exist
            if not self._ensure_headers():
                self.logger.error("Failed to ensure sheet headers")
                return False
            
            # Extract all applied jobs from the summary
            rows_to_add = []
            
            platform_results = summary.get('platform_results', [])
            if not platform_results:
                self.logger.info("No platform results found in summary")
                return True
            
            for platform_result in platform_results:
                platform = platform_result.get('platform', 'Unknown')
                applied_jobs = platform_result.get('applied_jobs', [])
                
                for job in applied_jobs:
                    # Format date
                    applied_date = job.get('applied_date', '')
                    if applied_date:
                        try:
                            # Parse the date and format it consistently
                            date_obj = datetime.strptime(applied_date, '%Y-%m-%d %H:%M:%S')
                            formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                        except ValueError:
                            # If parsing fails, use the original date
                            formatted_date = applied_date
                    else:
                        formatted_date = datetime.now().strftime('%Y-%m-%d %H:%M')
                    
                    # Create row data
                    row = [
                        formatted_date,
                        platform.title(),
                        job.get('title', 'Unknown Title'),
                        job.get('company', 'Unknown Company'),
                        job.get('url', ''),
                        'Applied'
                    ]
                    rows_to_add.append(row)
            
            if not rows_to_add:
                self.logger.info("No applied jobs to report to Google Sheets")
                return True
            
            # Append all rows in a single batch operation
            body = {
                'values': rows_to_add
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:F",
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            updates = result.get('updates', {})
            updated_rows = updates.get('updatedRows', 0)
            
            self.logger.info(f"Successfully reported {updated_rows} job applications to Google Sheets")
            return True
            
        except HttpError as e:
            if e.resp.status == 429:
                self.logger.warning("Google Sheets API rate limit exceeded, retrying...")
                # Simple retry after rate limit
                import time
                time.sleep(1)
                return self.append_applications(summary)
            else:
                self.logger.error(f"Google Sheets HTTP error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error appending applications to Google Sheets: {str(e)}")
        
        return False

    def test_connection(self) -> bool:
        """
        Tests the connection to Google Sheets API.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.service:
            return False
            
        try:
            # Try to get spreadsheet metadata
            self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            self.logger.info("Google Sheets connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Google Sheets connection test failed: {str(e)}")
            return False