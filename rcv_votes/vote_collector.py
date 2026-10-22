"""
Vote collector that orchestrates API calls and web scraping to gather complete vote data.
"""

import time
from typing import List, Optional, Set, Tuple

from .models import (VoteRecord, RollCallData, MemberSearchCriteria, CollectionResult,
                     VoteFailure, normalize_vote_cast, VOTE_NOT_ON_ROLL)
from .congress_api import CongressAPIClient
from .web_scraper import ClerkHouseGovScraper
from .vote_cache import VoteCache
from .exceptions import APIError, RateLimitExceeded, ValidationError
from .logging_config import get_logger, log_operation_start, log_operation_success, log_operation_error


# Outcomes of collecting a single roll call
_OK = "ok"
_MISSING = "missing"
_FAILED = "failed"


class VoteCollector:
    """Collects and processes roll call votes for congress members."""
    
    # When the vote list endpoint is unavailable, stop probing after this many
    # consecutive missing or failed roll call numbers
    MAX_CONSECUTIVE_PROBE_MISSES = 5
    
    def __init__(self, api_client: CongressAPIClient, web_scraper: ClerkHouseGovScraper,
                 cache: Optional[VoteCache] = None):
        """
        Initialize the vote collector.
        
        Args:
            api_client: Congress.gov API client
            web_scraper: Web scraper for clerk.house.gov
            cache: Optional on-disk cache of roll call data
        """
        self.api_client = api_client
        self.web_scraper = web_scraper
        self.cache = cache
        self.logger = get_logger('vote_collector')
        self._reset_run_state()
    
    def _reset_run_state(self) -> None:
        """Reset per-run counters and failure tracking."""
        self._failures: List[VoteFailure] = []
        self._cache_hits = 0
        self._api_calls = 0
    
    def collect_member_votes(self, search_criteria: MemberSearchCriteria,
                             correlation_id: str) -> CollectionResult:
        """
        Collect every House roll call vote in the specified congress, recording the
        target member's vote (Yea, Nay, Present, Not Voting, or Not on Roll) for each.
        
        Individual roll calls that fail are recorded and skipped rather than aborting the
        run. If the API rate limit is exhausted, collection stops and everything gathered
        so far is returned; completed roll calls are cached, so re-running resumes cheaply.
        
        Args:
            search_criteria: Member search criteria (name, state, district, congress number)
            correlation_id: Unique ID for tracking this operation
            
        Returns:
            Collection result with one vote record per roll call (chronological), any
            failures, cache/API call counts, and the reason for stopping early if any.
            Records are empty if the member never appears on any roll call.
        """
        operation = f"collect_votes_{search_criteria.last_name}_{search_criteria.state}"
        log_operation_start(self.logger, operation, correlation_id, 
                          member=search_criteria.last_name,
                          state=search_criteria.state,
                          district=search_criteria.district,
                          congress=search_criteria.congress)
        
        start_time = time.time()
        self._reset_run_state()
        records: List[VoteRecord] = []
        aborted_reason: Optional[str] = None
        
        try:
            congress = search_criteria.congress
            self.logger.info(f"Processing Congress {congress} for {search_criteria.last_name} "
                             f"({search_criteria.state}-{search_criteria.district})")
            
            # Resolve the member's Bioguide ID(s) for this congress via name, state, district
            bioguide_ids = self.api_client.get_member_bioguide_ids(
                congress, search_criteria.state, search_criteria.district, search_criteria.last_name
            )
            if not bioguide_ids:
                self.logger.warning(
                    f"No member named {search_criteria.last_name} found for "
                    f"{search_criteria.state}-{search_criteria.district} in Congress {congress}"
                )
            else:
                self._collect_congress_votes(congress, set(bioguide_ids), records)
                self.logger.info(f"Collected {len(records)} roll calls for Congress {congress}")
        
        except RateLimitExceeded as e:
            aborted_reason = (f"API rate limit reached; collection stopped early. "
                              f"Re-run the same command later to resume from the cache. ({e})")
            self.logger.error(aborted_reason)
        
        except Exception as e:
            log_operation_error(self.logger, operation, correlation_id, e,
                              votes_collected=len(records))
            raise
        
        # If the member never appears on any roll call, the name/state/district/congress
        # inputs are almost certainly wrong; return nothing rather than a file
        # full of "Not on Roll" rows.
        if records and all(v.vote_cast == VOTE_NOT_ON_ROLL for v in records):
            self.logger.warning(
                f"{search_criteria.last_name} ({search_criteria.state}-{search_criteria.district}) "
                f"does not appear on any of the {len(records)} roll calls collected"
            )
            records = []
        
        duration = time.time() - start_time
        log_operation_success(self.logger, operation, correlation_id, duration,
                            total_votes=len(records),
                            failures=len(self._failures),
                            cache_hits=self._cache_hits,
                            api_calls=self._api_calls,
                            congress=search_criteria.congress)
        
        return CollectionResult(
            records=records,
            failures=list(self._failures),
            cache_hits=self._cache_hits,
            api_calls=self._api_calls,
            aborted_reason=aborted_reason
        )
    
    def _collect_congress_votes(self, congress: int, bioguide_ids: Set[str],
                                records: List[VoteRecord]) -> None:
        """
        Collect all roll call votes in a specific congress, appending to records.
        
        Args:
            congress: Congress number
            bioguide_ids: Bioguide ID(s) identifying the target member
            records: List to append vote records to (so partial progress survives an abort)
        """
        # Iterate through sessions (typically 1 and 2)
        for session in [1, 2]:
            self.logger.debug(f"Processing Congress {congress}, Session {session}")
            
            before = len(records)
            self._collect_session_votes(congress, session, bioguide_ids, records)
            
            if len(records) > before:
                self.logger.debug(f"Found {len(records) - before} votes in Congress {congress}, Session {session}")
    
    def _collect_session_votes(self, congress: int, session: int, bioguide_ids: Set[str],
                               records: List[VoteRecord]) -> None:
        """
        Collect all roll call votes in a specific congress session, appending to records.
        
        Uses the API's vote list to know exactly which roll calls exist. If the list
        cannot be used, falls back to probing roll call numbers from 1 until several
        consecutive numbers are missing.
        
        Args:
            congress: Congress number
            session: Session number (1 or 2)
            bioguide_ids: Bioguide ID(s) identifying the target member
            records: List to append vote records to
        """
        numbers = self._get_roll_call_numbers(congress, session)
        
        if numbers is not None:
            self.logger.debug(f"Congress {congress}, Session {session}: {len(numbers)} roll calls listed")
            for number in numbers:
                self._collect_roll_call(congress, session, number, bioguide_ids, records, expect_exists=True)
            return
        
        # Fallback: probe sequentially until the end of the session
        self.logger.warning(f"Falling back to probing roll call numbers for Congress {congress}, Session {session}")
        number = 1
        misses = 0
        while misses < self.MAX_CONSECUTIVE_PROBE_MISSES:
            outcome = self._collect_roll_call(congress, session, number, bioguide_ids, records, expect_exists=False)
            misses = misses + 1 if outcome in (_MISSING, _FAILED) else 0
            number += 1
    
    def _get_roll_call_numbers(self, congress: int, session: int) -> Optional[List[int]]:
        """
        Get the roll call numbers in a session from the API's vote list.
        
        Returns:
            Roll call numbers, or None if the list is unavailable (caller should probe)
            
        Raises:
            RateLimitExceeded: If the API rate limit is exhausted
        """
        try:
            self._api_calls += 1
            return self.api_client.list_house_vote_numbers(congress, session)
        except RateLimitExceeded:
            raise
        except APIError as e:
            self.logger.warning(f"Could not list votes for Congress {congress}, Session {session}: {e}")
            return None
    
    def _collect_roll_call(self, congress: int, session: int, number: int, bioguide_ids: Set[str],
                           records: List[VoteRecord], expect_exists: bool) -> str:
        """
        Collect a single roll call and append its record.
        
        Any failure other than hitting the rate limit is recorded and does not stop the run.
        
        Args:
            congress: Congress number
            session: Session number
            number: Roll call number
            bioguide_ids: Bioguide ID(s) identifying the target member
            records: List to append the vote record to
            expect_exists: True if the roll call is known to exist, so a 404 is a failure
                rather than the end of the session
                
        Returns:
            _OK, _MISSING (not found while probing), or _FAILED
            
        Raises:
            RateLimitExceeded: If the API rate limit is exhausted
        """
        try:
            roll_call, scraped = self._load_roll_call(congress, session, number)
            
            # The target member's raw vote; absent if they were not on this roll call
            raw_vote = next((roll_call.votes[b] for b in bioguide_ids if b in roll_call.votes), None)
            vote_cast = normalize_vote_cast(raw_vote) if raw_vote is not None else VOTE_NOT_ON_ROLL
            
            # Prefer the scraped question, otherwise the API's
            question = scraped.get('question') or roll_call.vote_question
            
            # Date comes from the API start date (e.g., "2023-01-03T12:28:00-05:00")
            date = roll_call.start_date.split('T')[0]
            
            record = VoteRecord(
                congress=roll_call.congress,
                date=date,
                roll_call_number=roll_call.roll_call_number,
                legislation=roll_call.legislation,
                vote_cast=vote_cast,
                question=question,
                bill_title=scraped.get('bill_title', ''),
                roll_call_vote_url=self._generate_roll_call_url(roll_call.source_data_url)
            )
            records.append(record)
            
            self.logger.debug(f"Collected vote {number}: {roll_call.legislation} - {vote_cast}")
            return _OK
        
        except RateLimitExceeded:
            raise
        
        except APIError as e:
            if e.status_code == 404 and not expect_exists:
                self.logger.debug(f"Vote {number} not found (Congress {congress}, Session {session})")
                return _MISSING
            self._record_failure(congress, session, number, str(e))
            return _FAILED
        
        except Exception as e:
            # Unexpected problems with one roll call should not discard the rest of the run
            self._record_failure(congress, session, number, f"{type(e).__name__}: {e}")
            return _FAILED
    
    def _record_failure(self, congress: int, session: int, number: int, reason: str) -> None:
        """Log and remember a roll call that could not be collected."""
        self.logger.error(f"Failed to collect Congress {congress}, Session {session}, Vote {number}: {reason}")
        self._failures.append(VoteFailure(congress, session, number, reason))
    
    def _load_roll_call(self, congress: int, session: int, number: int) -> Tuple[RollCallData, dict]:
        """
        Get a roll call's data and scraped details, using the cache where possible.
        
        Returns:
            Tuple of (roll call data, scraped details dict with 'question' and 'bill_title')
        """
        entry = self.cache.get(congress, session, number) if self.cache else None
        roll_call: Optional[RollCallData] = None
        
        if entry is not None:
            try:
                roll_call = RollCallData.from_dict(entry)
                self._cache_hits += 1
            except (KeyError, TypeError, ValueError) as e:
                self.logger.warning(f"Ignoring malformed cache entry for vote {number}: {e}")
                entry = None
        
        if roll_call is None:
            self._api_calls += 1
            roll_call = self.api_client.get_roll_call(congress, session, number)
            entry = roll_call.to_dict()
            if self.cache:
                self.cache.put(congress, session, number, entry)
        
        scraped = entry.get('scraped')
        if not isinstance(scraped, dict):
            details = self.web_scraper.extract_vote_details(roll_call.source_data_url)
            scraped = {'question': details.question, 'bill_title': details.bill_title}
            
            # Only cache successful scrapes so failed ones are retried on the next run
            if details.question and self.cache:
                entry['scraped'] = scraped
                self.cache.put(congress, session, number, entry)
            elif not details.question:
                self.logger.debug(f"Vote {number}: Used API data only (scraping found no details)")
        
        return roll_call, scraped
    
    def _generate_roll_call_url(self, source_data_url: str) -> str:
        """
        Generate roll call vote URL from source data URL.
        
        Example:
        Input: https://clerk.house.gov/evs/2025/roll055.xml
        Output: https://clerk.house.gov/Votes/202555
        
        Args:
            source_data_url: Source data URL from API
            
        Returns:
            Generated roll call vote URL, or the source URL if it is not in the expected format
        """
        try:
            return self.web_scraper.generate_rcv_url(source_data_url)
        except ValidationError:
            return source_data_url
