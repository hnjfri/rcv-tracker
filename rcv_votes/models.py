"""
Data models for RCV Votes application.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

from .exceptions import ValidationError


@dataclass
class VoteRecord:
    """Represents a single vote record for a congress member."""
    congress: int
    date: str  # YYYY-MM-DD format
    roll_call_number: int
    legislation: str  # e.g., "HR758"
    vote_cast: str  # e.g., "Yea", "Nay", "Present"
    question: str  # e.g., "On Motion to Suspend the Rules and Pass"
    bill_title: str  # e.g., "Mail Traffic Deaths Reporting Act"
    roll_call_vote_url: str  # e.g., "https://clerk.house.gov/Votes/202555"
    
    def __post_init__(self):
        """Validate data after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate all fields meet requirements."""
        if not isinstance(self.congress, int) or self.congress < 1:
            raise ValidationError("Congress number must be a positive integer", "congress", str(self.congress))
        
        # Validate date format (YYYY-MM-DD)
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', self.date):
            raise ValidationError("Date must be in YYYY-MM-DD format", "date", self.date)
        
        if not isinstance(self.roll_call_number, int) or self.roll_call_number < 1:
            raise ValidationError("Roll call number must be a positive integer", "roll_call_number", str(self.roll_call_number))
        
        if not isinstance(self.legislation, str):
            raise ValidationError("Legislation must be a string", "legislation", self.legislation)
        
        if not self.vote_cast or not isinstance(self.vote_cast, str):
            raise ValidationError("Vote cast must be a non-empty string", "vote_cast", self.vote_cast)
        
        if not isinstance(self.question, str):
            raise ValidationError("Question must be a string", "question", self.question)
        
        if not isinstance(self.bill_title, str):
            raise ValidationError("Bill title must be a string", "bill_title", self.bill_title)
        
        if not isinstance(self.roll_call_vote_url, str):
            raise ValidationError("Roll call vote URL must be a string", "roll_call_vote_url", self.roll_call_vote_url)


@dataclass
class APIVoteData:
    """Raw vote data from Congress.gov API."""
    congress: int
    identifier: int
    legislation_number: str
    legislation_type: str
    legislation_url: str
    bio_guide_id: str
    first_name: str
    last_name: str
    vote_cast: str
    vote_party: str
    vote_state: str
    result: str
    roll_call_number: int
    session_number: int
    source_data_url: str
    start_date: str
    update_date: str
    vote_question: str
    vote_type: str
    
    @property
    def legislation(self) -> str:
        """Get concatenated legislation string."""
        if self.legislation_type and self.legislation_number:
            return f"{self.legislation_type}{self.legislation_number}"
        return "Non-Legislative"
    
    def validate_for_member(self, target_last_name: str, target_state: str) -> bool:
        """Check if this vote record matches the target member."""
        return (self.last_name.lower() == target_last_name.lower() and 
                self.vote_state.upper() == target_state.upper())


@dataclass
class ScrapedVoteDetails:
    """Vote details scraped from clerk.house.gov."""
    question: str
    bill_title: str
    date: str  # YYYY-MM-DD format
    
    def __post_init__(self):
        """Validate scraped data."""
        if not isinstance(self.question, str):
            raise ValidationError("Question must be a string", "question", self.question)
        
        if not isinstance(self.bill_title, str):
            raise ValidationError("Bill title must be a string", "bill_title", self.bill_title)
        
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', self.date):
            raise ValidationError("Date must be in YYYY-MM-DD format", "date", self.date)


@dataclass
class MemberSearchCriteria:
    """Search criteria for a congress member."""
    last_name: str
    state: str
    congress_numbers: List[int]
    
    def __post_init__(self):
        """Validate search criteria."""
        if not self.last_name or not isinstance(self.last_name, str):
            raise ValidationError("Last name must be a non-empty string", "last_name", self.last_name)
        
        if not self.state or not isinstance(self.state, str) or len(self.state) != 2:
            raise ValidationError("State must be a 2-letter abbreviation", "state", self.state)
        
        if not self.congress_numbers or not isinstance(self.congress_numbers, list):
            raise ValidationError("Congress numbers must be a non-empty list", "congress_numbers", str(self.congress_numbers))
        
        for congress in self.congress_numbers:
            if not isinstance(congress, int) or congress < 1:
                raise ValidationError("All congress numbers must be positive integers", "congress_numbers", str(congress))
        
        # Clean up data
        self.last_name = self.last_name.strip()
        self.state = self.state.strip().upper()
