"""
Vote collector that orchestrates API calls and web scraping to gather complete vote data.
"""

import time
import re
from typing import List, Dict, Any, Generator, Tuple
from dataclasses import asdict

from .models import VoteRecord, APIVoteData, MemberSearchCriteria
from .congress_api import CongressAPIClient
from .web_scraper import ClerkHouseGovScraper
from .exceptions import APIError, ScrapingError, ValidationError
from .logging_config import get_logger, log_operation_start, log_operation_success, log_operation_error


class VoteCollector:
    """Collects and processes roll call votes for congress members."""
    
    def __init__(self, api_client: CongressAPIClient, web_scraper: ClerkHouseGovScraper):
        """
        Initialize the vote collector.
        
        Args:
            api_client: Congress.gov API client
            web_scraper: Web scraper for clerk.house.gov
        """
        self.api_client = api_client
        self.web_scraper = web_scraper
        self.logger = get_logger('vote_collector')
    
    def collect_member_votes(self, search_criteria: MemberSearchCriteria, 
                           correlation_id: str, max_votes: int = None) -> List[VoteRecord]:
        """
        Collect all votes for a congress member across specified congress sessions.
        
        Args:
            search_criteria: Member search criteria (name, state, congress numbers)
            correlation_id: Unique ID for tracking this operation
            max_votes: Maximum number of votes to collect (for testing)
            
        Returns:
            List of complete vote records for the member
        """
        operation = f"collect_votes_{search_criteria.last_name}_{search_criteria.state}"
        log_operation_start(self.logger, operation, correlation_id, 
                          member=search_criteria.last_name,
                          state=search_criteria.state,
                          congresses=search_criteria.congress_numbers)
        
        start_time = time.time()
        all_votes = []
        
        try:
            for congress in search_criteria.congress_numbers:
                if max_votes and len(all_votes) >= max_votes:
                    break
                    
                self.logger.info(f"Processing Congress {congress} for {search_criteria.last_name} ({search_criteria.state})")
                
                congress_votes = self._collect_congress_votes(
                    congress, search_criteria.last_name, search_criteria.state, correlation_id, max_votes - len(all_votes) if max_votes else None
                )
                
                all_votes.extend(congress_votes)
                
                self.logger.info(f"Found {len(congress_votes)} votes for Congress {congress}")
                
                if max_votes and len(all_votes) >= max_votes:
                    all_votes = all_votes[:max_votes]
                    self.logger.info(f"Reached maximum vote limit of {max_votes}, stopping collection")
                    break
            
            duration = time.time() - start_time
            log_operation_success(self.logger, operation, correlation_id, duration,
                                total_votes=len(all_votes),
                                congresses_processed=len(search_criteria.congress_numbers))
            
            return all_votes
            
        except Exception as e:
            duration = time.time() - start_time
            log_operation_error(self.logger, operation, correlation_id, e,
                              votes_collected=len(all_votes))
            raise
    
    def _collect_congress_votes(self, congress: int, last_name: str, state: str, 
                               correlation_id: str, max_votes: int = None) -> List[VoteRecord]:
        """
        Collect all votes for a member in a specific congress.
        
        Args:
            congress: Congress number
            last_name: Member's last name
            state: Member's state abbreviation
            correlation_id: Operation tracking ID
            max_votes: Maximum number of votes to collect
            
        Returns:
            List of vote records for the congress
        """
        congress_votes = []
        
        # Iterate through sessions (typically 1 and 2)
        for session in [1, 2]:
            if max_votes and len(congress_votes) >= max_votes:
                break
                
            self.logger.debug(f"Processing Congress {congress}, Session {session}")
            
            session_votes = self._collect_session_votes(
                congress, session, last_name, state, correlation_id, max_votes - len(congress_votes) if max_votes else None
            )
            
            congress_votes.extend(session_votes)
            
            if session_votes:
                self.logger.debug(f"Found {len(session_votes)} votes in Congress {congress}, Session {session}")
        
        return congress_votes
    
    def _collect_session_votes(self, congress: int, session: int, last_name: str, 
                              state: str, correlation_id: str, max_votes: int = None) -> List[VoteRecord]:
        """
        Collect all votes for a member in a specific congress session.
        
        Args:
            congress: Congress number
            session: Session number (1 or 2)
            last_name: Member's last name
            state: Member's state abbreviation
            correlation_id: Operation tracking ID
            max_votes: Maximum number of votes to collect
            
        Returns:
            List of vote records for the session
        """
        session_votes = []
        vote_number = 1
        consecutive_failures = 0
        max_consecutive_failures = 5  # Stop after 5 consecutive 404s
        
        while consecutive_failures < max_consecutive_failures:
            if max_votes and len(session_votes) >= max_votes:
                self.logger.debug(f"Reached maximum vote limit of {max_votes} for session")
                break
                
            try:
                # Get vote data from API
                api_vote_data = self.api_client.get_house_vote_members(congress, session, vote_number)
                
                # Find the target member's vote
                member_vote = self._find_member_vote(api_vote_data, last_name, state)
                
                if member_vote:
                    # Get additional details from web scraping (always returns valid data, even if empty)
                    scraped_details = self.web_scraper.extract_vote_details(member_vote.source_data_url)
                    
                    # Use scraped question if available, otherwise fall back to API question
                    question = scraped_details.question if scraped_details.question else member_vote.vote_question
                    
                    # Use scraped date if available, otherwise extract from start_date
                    date = scraped_details.date
                    if date == "1900-01-01":  # Fallback date was used
                        # Try to extract date from API start_date (e.g., "2023-01-03T12:28:00-05:00")
                        try:
                            api_date = member_vote.start_date.split('T')[0]  # Get YYYY-MM-DD part
                            if re.match(r'^\d{4}-\d{2}-\d{2}$', api_date):
                                date = api_date
                        except:
                            pass  # Keep fallback date
                    
                    # Generate roll call vote URL from source data URL
                    roll_call_vote_url = self._generate_roll_call_url(member_vote.source_data_url)
                    
                    # Create complete vote record (with empty strings for missing data)
                    vote_record = VoteRecord(
                        congress=member_vote.congress,
                        date=date,
                        roll_call_number=member_vote.roll_call_number,
                        legislation=member_vote.legislation,
                        vote_cast=member_vote.vote_cast,
                        question=question,
                        bill_title=scraped_details.bill_title,
                        roll_call_vote_url=roll_call_vote_url
                    )
                    
                    session_votes.append(vote_record)
                    
                    self.logger.debug(f"Collected vote {vote_number}: {member_vote.legislation} - {member_vote.vote_cast}")
                    
                    # Log if we had to use fallback data
                    if not scraped_details.question and not scraped_details.bill_title:
                        self.logger.debug(f"Vote {vote_number}: Used API data only (scraping found no additional details)")
                    elif not scraped_details.question or not scraped_details.bill_title:
                        self.logger.debug(f"Vote {vote_number}: Partial scraping success")
                
                # Reset failure counter on successful API call
                consecutive_failures = 0
                vote_number += 1
                
                # Small delay to be respectful to the API
                time.sleep(0.1)
                
            except APIError as e:
                if e.status_code == 404:
                    # Vote not found - this is expected when we reach the end
                    consecutive_failures += 1
                    vote_number += 1
                    
                    if consecutive_failures >= max_consecutive_failures:
                        self.logger.debug(f"Reached end of votes for Congress {congress}, Session {session} "
                                        f"(vote {vote_number - max_consecutive_failures})")
                        break
                else:
                    # Other API errors should be logged and may indicate a real problem
                    self.logger.error(f"API error for Congress {congress}, Session {session}, Vote {vote_number}: {e}")
                    consecutive_failures += 1
                    vote_number += 1
                    
                    if consecutive_failures >= max_consecutive_failures:
                        self.logger.warning(f"Too many consecutive API errors, stopping session {session}")
                        break
        
        return session_votes
    
    def _find_member_vote(self, api_vote_data: List[APIVoteData], last_name: str, 
                         state: str) -> APIVoteData:
        """
        Find the target member's vote in the API response data.
        
        Args:
            api_vote_data: List of all member votes from API
            last_name: Target member's last name
            state: Target member's state abbreviation
            
        Returns:
            The target member's vote data, or None if not found
        """
        for vote_data in api_vote_data:
            if vote_data.validate_for_member(last_name, state):
                return vote_data
        
        return None
    
    def _generate_roll_call_url(self, source_data_url: str) -> str:
        """
        Generate roll call vote URL from source data URL.
        
        Example:
        Input: https://clerk.house.gov/evs/2025/roll055.xml
        Output: https://clerk.house.gov/Votes/202555
        
        Args:
            source_data_url: Source data URL from API
            
        Returns:
            Generated roll call vote URL
        """
        try:
            # Extract year and roll call number from URL
            # Expected format: https://clerk.house.gov/evs/YYYY/rollXXX.xml
            pattern = r'https://clerk\.house\.gov/evs/(\d{4})/roll(\d+)\.xml'
            match = re.search(pattern, source_data_url)
            
            if match:
                year = match.group(1)
                roll_number = match.group(2).zfill(3)  # Ensure 3 digits with leading zeros
                
                # Generate RCV URL: https://clerk.house.gov/Votes/{year}{rollNumber}
                return f"https://clerk.house.gov/Votes/{year}{roll_number}"
            else:
                # Fallback: return the source URL if pattern doesn't match
                return source_data_url
                
        except Exception as e:
            self.logger.warning(f"Failed to generate roll call URL from {source_data_url}: {e}")
            return source_data_url
