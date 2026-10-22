"""
Congress.gov API client for retrieving roll call vote data.
"""

import requests
import time
import random
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from .models import RollCallData
from .exceptions import APIError, RateLimitExceeded, ValidationError
from .logging_config import get_logger


class CongressAPIClient:
    """Client for interacting with the Congress.gov API."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.congress.gov/v3/",
                 request_delay: float = 0.05):
        """
        Initialize the Congress API client.
        
        Args:
            api_key: Congress.gov API key
            base_url: Base URL for the Congress.gov API
            request_delay: Seconds to pause before each request
        """
        self.api_key = api_key
        self.base_url = base_url
        self.request_delay = request_delay
        self.session = requests.Session()
        self.logger = get_logger('congress_api')
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'RCV-Votes/1.0.0 (MB Public Affairs)',
            'Accept': 'application/json'
        })
    
    def list_house_vote_numbers(self, congress: int, session: int) -> Optional[List[int]]:
        """
        List every roll call number in a session using the paginated list endpoint.
        
        This replaces probing numbers one at a time until errors stop, and lets the
        program know exactly which roll calls exist.
        
        Args:
            congress: Congress number (e.g., 118)
            session: Session number (1 or 2)
            
        Returns:
            Sorted roll call numbers (empty if the session has no votes), or None if the
            response was not in the expected format and the caller should fall back
            to probing.
            
        Raises:
            APIError: If the API request fails (RateLimitExceeded if rate limited)
        """
        url = urljoin(self.base_url, f"house-vote/{congress}/{session}")
        page_size = 250
        offset = 0
        numbers: List[int] = []
        
        while True:
            params = {'api_key': self.api_key, 'format': 'json', 'limit': page_size, 'offset': offset}
            
            try:
                response = self._make_request_with_retry(url, params)
                data = response.json()
            except requests.exceptions.RequestException as e:
                raise APIError(f"Failed to list votes: {e}") from e
            except APIError as e:
                if e.status_code == 404 and offset == 0:
                    return []  # Session does not exist (yet)
                raise
            
            items = data.get('houseRollCallVotes') if isinstance(data, dict) else None
            if not isinstance(items, list):
                self.logger.warning("Vote list response not in expected format")
                return None
            
            total = data.get('pagination', {}).get('count') if isinstance(data.get('pagination'), dict) else None
            
            if not items:
                if offset == 0 and isinstance(total, int) and total > 0:
                    return None  # Count says votes exist but none were listed
                break
            
            for item in items:
                number = item.get('rollCallNumber') if isinstance(item, dict) else None
                if isinstance(number, int):
                    numbers.append(number)
            
            offset += len(items)
            if len(items) < page_size or (isinstance(total, int) and offset >= total):
                break
        
        self.logger.debug(f"Congress {congress} Session {session} has {len(numbers)} roll call votes")
        return sorted(set(numbers))
    
    def get_roll_call(self, congress: int, session: int, vote_number: int) -> RollCallData:
        """
        Get a specific House roll call vote, including every member's vote.
        
        Args:
            congress: Congress number (e.g., 118)
            session: Session number (1 or 2)
            vote_number: Roll call vote number
            
        Returns:
            Roll call metadata and a mapping of Bioguide ID to raw vote
            
        Raises:
            APIError: If the API request fails (status_code 404 if the vote does not exist)
            ValidationError: If the response data is invalid
        """
        endpoint = f"house-vote/{congress}/{session}/{vote_number}/members"
        url = urljoin(self.base_url, endpoint)
        
        params = {'api_key': self.api_key}
        
        try:
            self.logger.debug(f"Requesting vote data for Congress {congress}, Session {session}, Vote {vote_number}")
            
            response = self._make_request_with_retry(url, params)
            roll_call = self._parse_roll_call_response(response.json())
            
            self.logger.debug(f"Retrieved {len(roll_call.votes)} member votes for vote {vote_number}")
            
            return roll_call
            
        except requests.exceptions.RequestException as e:
            raise APIError(f"Failed to retrieve vote data: {e}") from e
    
    def get_member_bioguide_ids(self, congress: int, state: str, district: int,
                                last_name: str) -> List[str]:
        """
        Resolve a House member to Bioguide ID(s) using last name, state, and district.
        
        The House roll call vote endpoint does not include district, so the member is
        identified through the Members endpoint, which does. More than one person can
        represent a district within a single congress (for example after a special
        election), so the last name is used to pick the right one.
        
        Args:
            congress: Congress number (e.g., 118)
            state: Two-letter state abbreviation
            district: House district number
            last_name: Member's last name
            
        Returns:
            List of matching Bioguide IDs (empty if no member matches)
            
        Raises:
            APIError: If the API request fails
        """
        endpoint = f"member/congress/{congress}/{state.upper()}/{district}"
        url = urljoin(self.base_url, endpoint)
        params = {'api_key': self.api_key, 'format': 'json', 'limit': 250}
        
        try:
            self.logger.debug(f"Looking up member for Congress {congress}, {state.upper()}-{district}")
            response = self._make_request_with_retry(url, params)
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise APIError(f"Failed to look up member: {e}") from e
        except APIError as e:
            if e.status_code == 404:
                return []
            raise
        
        members = data.get('members', []) if isinstance(data, dict) else []
        target = last_name.strip().lower()
        bioguide_ids = []
        
        for member in members:
            # Names are formatted "Last, First" (e.g., "Thompson, Mike")
            name = member.get('name', '') or ''
            member_last_name = name.split(',')[0].strip().lower()
            bioguide_id = member.get('bioguideId')
            if bioguide_id and member_last_name == target:
                bioguide_ids.append(bioguide_id)
        
        self.logger.debug(f"Resolved {last_name} {state.upper()}-{district} in Congress {congress} to {bioguide_ids}")
        return bioguide_ids
    
    @staticmethod
    def _safe_json(response: requests.Response) -> Optional[Any]:
        """Decode a JSON body, returning None if there is no body or it is not JSON."""
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None
    
    def _log_rate_limit_headers(self, response: requests.Response) -> None:
        """Log remaining request quota when the API reports it."""
        remaining = response.headers.get('X-RateLimit-Remaining')
        if remaining is None:
            return
        self.logger.debug(f"API requests remaining: {remaining}")
        try:
            if int(remaining) <= 25:
                self.logger.warning(f"Only {remaining} API requests remaining in the current rate limit window")
        except ValueError:
            pass
    
    def _make_request_with_retry(self, url: str, params: Dict[str, Any], 
                                max_retries: int = 3) -> requests.Response:
        """
        Make HTTP request with exponential backoff retry logic.
        
        Args:
            url: Request URL
            params: Request parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            HTTP response object
            
        Raises:
            RateLimitExceeded: If still rate limited after all retries
            APIError: If the request fails
        """
        for attempt in range(max_retries):
            if self.request_delay:
                time.sleep(self.request_delay)
            
            try:
                response = self.session.get(url, params=params, timeout=30)
                self._log_rate_limit_headers(response)
                
                # Check for rate limiting
                if response.status_code == 429:
                    try:
                        retry_after = int(response.headers.get('Retry-After', 60))
                    except ValueError:
                        retry_after = 60
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Rate limited, waiting {retry_after}s before retry")
                        time.sleep(retry_after)
                        continue
                    raise RateLimitExceeded("Rate limit exceeded after all retries", response.status_code)
                
                # Check for vote not found (this is expected when we reach the end)
                if response.status_code == 404:
                    raise APIError("Not found", 404, self._safe_json(response))
                
                # Check for other client/server errors
                if response.status_code >= 400:
                    error_data = self._safe_json(response)
                    error_msg = f"API request failed with status {response.status_code}"
                    if isinstance(error_data, dict) and 'error' in error_data:
                        error_msg += f": {error_data['error']}"
                    raise APIError(error_msg, response.status_code, error_data)
                
                return response
                
            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    self.logger.warning(f"Request timeout, retrying in {wait_time:.1f}s (attempt {attempt + 1})")
                    time.sleep(wait_time)
                else:
                    raise APIError(f"Request timed out after {max_retries} attempts") from e
            
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    self.logger.warning(f"Connection error, retrying in {wait_time:.1f}s (attempt {attempt + 1})")
                    time.sleep(wait_time)
                else:
                    raise APIError(f"Connection failed after {max_retries} attempts") from e
        
        raise APIError("Unexpected error in request retry logic")
    
    def _parse_roll_call_response(self, response_data: Dict[str, Any]) -> RollCallData:
        """
        Parse an API response into roll call data.
        
        Args:
            response_data: Raw API response data
            
        Returns:
            Parsed roll call with a Bioguide ID to vote mapping
            
        Raises:
            ValidationError: If response format is invalid
        """
        if not isinstance(response_data, dict):
            raise ValidationError("API response must be a dictionary")
        
        # Handle both possible field names in the API response
        if 'houseRollCallMemberVotes' in response_data:
            roll_call_votes = response_data['houseRollCallMemberVotes']
        elif 'houseRollCallVoteMemberVotes' in response_data:
            roll_call_votes = response_data['houseRollCallVoteMemberVotes']
        else:
            raise ValidationError("API response missing expected vote data field")
        
        # Handle both list and single object formats
        if isinstance(roll_call_votes, list):
            if not roll_call_votes:
                raise ValidationError("API response vote data is empty")
            vote_info = roll_call_votes[0]
        else:
            vote_info = roll_call_votes
        
        if not isinstance(vote_info, dict):
            raise ValidationError("API response vote data has unexpected format")
        
        # Only fields the program actually uses are required. Legislation fields are
        # optional because some votes (quorum calls, etc.) have no legislation.
        required_fields = ['congress', 'rollCallNumber', 'sessionNumber',
                           'sourceDataURL', 'startDate', 'voteQuestion']
        for field_name in required_fields:
            if field_name not in vote_info:
                raise ValidationError(f"Vote metadata missing required field: {field_name}")
        
        if 'results' not in vote_info or not isinstance(vote_info['results'], list):
            raise ValidationError("Vote data missing member results")
        
        votes: Dict[str, str] = {}
        for member_vote in vote_info['results']:
            if not isinstance(member_vote, dict) or 'bioguideID' not in member_vote or 'voteCast' not in member_vote:
                raise ValidationError("Member vote data missing bioguideID or voteCast")
            votes[member_vote['bioguideID']] = member_vote['voteCast']
        
        return RollCallData(
            congress=vote_info['congress'],
            session_number=vote_info['sessionNumber'],
            roll_call_number=vote_info['rollCallNumber'],
            legislation_type=vote_info.get('legislationType', ''),
            legislation_number=vote_info.get('legislationNumber', ''),
            source_data_url=vote_info['sourceDataURL'],
            start_date=vote_info['startDate'],
            vote_question=vote_info['voteQuestion'],
            votes=votes
        )
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.session.close()
