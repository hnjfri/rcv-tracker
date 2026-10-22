"""
On-disk cache for roll call vote data.

A roll call vote does not change once it has been recorded, and each API response
contains every member's vote, so the cache is keyed by roll call (not by member).
Looking up a different legislator, or re-running after an interruption, reuses
cached roll calls instead of making new requests.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .logging_config import get_logger


class VoteCache:
    """File-based cache storing one JSON file per roll call vote."""
    
    def __init__(self, directory: str = "cache", refresh: bool = False):
        """
        Initialize the cache.
        
        Args:
            directory: Directory for cache files (created on first write)
            refresh: If True, ignore existing cache entries on read (entries are
                still written, replacing old ones)
        """
        self.directory = Path(directory)
        self.refresh = refresh
        self.logger = get_logger('vote_cache')
    
    def _path(self, congress: int, session: int, roll_call_number: int) -> Path:
        return self.directory / str(congress) / str(session) / f"{roll_call_number}.json"
    
    def get(self, congress: int, session: int, roll_call_number: int) -> Optional[Dict[str, Any]]:
        """
        Read a cached roll call.
        
        Returns:
            The cached dictionary, or None if absent, unreadable, or refresh is on
        """
        if self.refresh:
            return None
        
        path = self._path(congress, session, roll_call_number)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            self.logger.warning(f"Ignoring unreadable cache file {path}: {e}")
            return None
    
    def put(self, congress: int, session: int, roll_call_number: int, data: Dict[str, Any]) -> None:
        """
        Write a roll call to the cache. Failures are logged and never raised,
        since the cache is an optimization and not required for correctness.
        """
        path = self._path(congress, session, roll_call_number)
        tmp_path = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, separators=(',', ':'))
            os.replace(tmp_path, path)  # Atomic: no half-written files if interrupted
        except OSError as e:
            self.logger.warning(f"Could not write cache file {path}: {e}")
