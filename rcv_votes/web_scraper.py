"""
Web scraper for extracting vote details from clerk.house.gov.
"""

import requests
import re

from .models import ScrapedVoteDetails
from .exceptions import ValidationError
from .logging_config import get_logger


class ClerkHouseGovScraper:
    """Scraper for extracting vote details from clerk.house.gov."""
    
    def __init__(self):
        """Initialize the web scraper."""
        self.session = requests.Session()
        self.logger = get_logger('web_scraper')
        
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def extract_vote_details(self, source_data_url: str) -> ScrapedVoteDetails:
        """
        Extract vote question and bill title from source data URL.
        
        Args:
            source_data_url: URL from Congress API (e.g., https://clerk.house.gov/evs/2025/roll055.xml)
            
        Returns:
            Scraped vote details including question and bill title (empty strings if not found)
        """
        question = ""
        bill_title = ""
        
        try:
            # Generate the RCV URL from source data URL
            rcv_url = self.generate_rcv_url(source_data_url)
            
            self.logger.debug(f"Scraping vote details from: {rcv_url}")
            
            # Fetch the page content
            response = self.session.get(rcv_url, timeout=30)
            response.raise_for_status()
            
            # Extract vote details from HTML (returns empty strings if not found)
            question = self._extract_question(response.text)
            bill_title = self._extract_bill_title(response.text)
            
            self.logger.debug(f"Extracted vote details - Question: '{question[:30]}...', Title: '{bill_title[:30]}...'")
            
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Failed to fetch vote details from {source_data_url}: {e}")
        except Exception as e:
            self.logger.warning(f"Error while scraping vote details from {source_data_url}: {e}")
        
        # Always return a ScrapedVoteDetails object, even with empty fields
        return ScrapedVoteDetails(
            question=question or "",
            bill_title=bill_title or ""
        )
    
    def generate_rcv_url(self, source_data_url: str) -> str:
        """
        Generate RCV URL from source data URL.
        
        Example:
        Input: https://clerk.house.gov/evs/2025/roll055.xml
        Output: https://clerk.house.gov/Votes/202555
        
        Args:
            source_data_url: Source data URL from API
            
        Returns:
            Generated RCV URL
            
        Raises:
            ValidationError: If URL format is invalid
        """
        if not source_data_url or not isinstance(source_data_url, str):
            raise ValidationError("Source data URL must be a non-empty string")
        
        # Extract year and roll call number from URL
        # Expected format: https://clerk.house.gov/evs/YYYY/rollXXX.xml
        pattern = r'https://clerk\.house\.gov/evs/(\d{4})/roll(\d+)\.xml'
        match = re.search(pattern, source_data_url)
        
        if not match:
            raise ValidationError(f"Invalid source data URL format: {source_data_url}")
        
        year = match.group(1)
        roll_number = match.group(2).zfill(3)  # Ensure 3 digits with leading zeros
        
        # Generate RCV URL: https://clerk.house.gov/Votes/{year}{rollNumber}
        rcv_url = f"https://clerk.house.gov/Votes/{year}{roll_number}"
        
        return rcv_url
    
    def _extract_question(self, html_content: str) -> str:
        """
        Extract the vote question from HTML content.
        
        Args:
            html_content: Raw HTML content from the page
            
        Returns:
            Extracted question text, or empty string if not found
        """
        # Try multiple patterns for question extraction
        patterns = [
            r'QUESTION:\s*([^\n\r<]+)',
            r'<b>QUESTION:</b>\s*([^\n\r<]+)',
            r'Question:\s*([^\n\r<]+)',
            r'QUESTION\s*([^\n\r<]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                question = match.group(1).strip()
                if question:
                    return question
        
        # If no question found, return empty string
        return ""
    
    def _extract_bill_title(self, html_content: str) -> str:
        """
        Extract the bill title from HTML content.
        
        Args:
            html_content: Raw HTML content from the page
            
        Returns:
            Extracted bill title, or empty string if not found
        """
        # Try multiple patterns for bill title extraction
        patterns = [
            r'BILL TITLE:\s*([^\n\r<]+)',
            r'<b>BILL TITLE:</b>\s*([^\n\r<]+)',
            r'Bill Title:\s*([^\n\r<]+)',
            r'BILL TITLE\s*([^\n\r<]+)',
            r'Title:\s*([^\n\r<]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                bill_title = match.group(1).strip()
                if bill_title:
                    return bill_title
        
        # If no bill title found, return empty string
        return ""
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.session.close()
