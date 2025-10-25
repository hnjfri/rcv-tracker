"""
Congress.gov API client for retrieving roll call vote data.
"""

import requests
import time
import random
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from .models import APIVoteData
from .exceptions import APIError, ValidationError
from .logging_config import get_logger


class CongressAPIClient:
    """Client for interacting with the Congress.gov API."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.congress.gov/v3/"):
        """
        Initialize the Congress API client.
        
        Args:
            api_key: Congress.gov API key
            base_url: Base URL for the Congress.gov API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.logger = get_logger('congress_api')
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'RCV-Votes/1.0.0 (MB Public Affairs)',
            'Accept': 'application/json'
        })
    
    def get_house_vote_members(self, congress: int, session: int, vote_number: int) -> List[APIVoteData]:
        """
        Get member votes for a specific House roll call vote.
        
        Args:
            congress: Congress number (e.g., 118)
            session: Session number (1 or 2)
            vote_number: Roll call vote number
            
        Returns:
            List of vote data for all members
            
        Raises:
            APIError: If the API request fails
            ValidationError: If the response data is invalid
        """
        endpoint = f"house-vote/{congress}/{session}/{vote_number}/members"
        url = urljoin(self.base_url, endpoint)
        
        params = {'api_key': self.api_key}
        
        try:
            self.logger.debug(f"Requesting vote data for Congress {congress}, Session {session}, Vote {vote_number}")
            
            response = self._make_request_with_retry(url, params)
            
            # Parse response
            vote_data = self._parse_vote_response(response.json())
            
            self.logger.debug(f"Retrieved {len(vote_data)} member votes for vote {vote_number}")
            
            return vote_data
            
        except requests.exceptions.RequestException as e:
            raise APIError(f"Failed to retrieve vote data: {e}") from e
    
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
            APIError: If all retry attempts fail
        """
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Rate limited, waiting {retry_after}s before retry")
                        time.sleep(retry_after)
                        continue
                    else:
                        raise APIError("Rate limit exceeded after all retries", response.status_code)
                
                # Check for vote not found (this is expected when we reach the end)
                if response.status_code == 404:
                    raise APIError("Vote not found", 404, response.json() if response.content else None)
                
                # Check for other client/server errors
                if response.status_code >= 400:
                    error_data = response.json() if response.content else None
                    error_msg = f"API request failed with status {response.status_code}"
                    if error_data and 'error' in error_data:
                        error_msg += f": {error_data['error']}"
                    raise APIError(error_msg, response.status_code, error_data)
                
                response.raise_for_status()
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
    
    def _parse_vote_response(self, response_data: Dict[str, Any]) -> List[APIVoteData]:
        """
        Parse API response and extract vote data.
        
        Args:
            response_data: Raw API response data
            
        Returns:
            List of parsed vote data objects
            
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
        if not isinstance(roll_call_votes, list):
            roll_call_votes = [roll_call_votes]
        
        if not isinstance(roll_call_votes, list) or not roll_call_votes:
            raise ValidationError("houseRollCallMemberVotes must be a non-empty list")
        
        # Extract vote information from the first vote record (metadata is the same for all)
        vote_info = roll_call_votes[0]
        
        # Validate core required fields (some votes like quorum calls may not have legislation info)
        core_required_fields = [
            'congress', 'rollCallNumber', 'sessionNumber', 'sourceDataURL', 
            'startDate', 'updateDate', 'voteQuestion', 'voteType', 'result', 'identifier'
        ]
        
        for field in core_required_fields:
            if field not in vote_info:
                raise ValidationError(f"Vote metadata missing required field: {field}")
        
        # Handle optional legislation fields (not present in quorum calls, etc.)
        legislation_number = vote_info.get('legislationNumber', '')
        legislation_type = vote_info.get('legislationType', '')
        legislation_url = vote_info.get('legislationUrl', '')
        
        # Extract member results
        if 'results' not in vote_info or not isinstance(vote_info['results'], list):
            raise ValidationError("Vote data missing member results")
        
        vote_data_list = []
        
        for member_vote in vote_info['results']:
            # Validate member vote data
            member_required_fields = ['bioguideID', 'firstName', 'lastName', 'voteCast', 'voteParty', 'voteState']
            
            for field in member_required_fields:
                if field not in member_vote:
                    raise ValidationError(f"Member vote data missing required field: {field}")
            
            # Create APIVoteData object
            vote_data = APIVoteData(
                congress=vote_info['congress'],
                identifier=vote_info['identifier'],
                legislation_number=legislation_number,
                legislation_type=legislation_type,
                legislation_url=legislation_url,
                bio_guide_id=member_vote['bioguideID'],
                first_name=member_vote['firstName'],
                last_name=member_vote['lastName'],
                vote_cast=member_vote['voteCast'],
                vote_party=member_vote['voteParty'],
                vote_state=member_vote['voteState'],
                result=vote_info['result'],
                roll_call_number=vote_info['rollCallNumber'],
                session_number=vote_info['sessionNumber'],
                source_data_url=vote_info['sourceDataURL'],
                start_date=vote_info['startDate'],
                update_date=vote_info['updateDate'],
                vote_question=vote_info['voteQuestion'],
                vote_type=vote_info['voteType']
            )
            
            vote_data_list.append(vote_data)
        
        return vote_data_list
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.session.close()
