"""
Dependency injection container for RCV Votes application.
"""

import os
import uuid
from typing import Optional

from .congress_api import CongressAPIClient
from .web_scraper import ClerkHouseGovScraper
from .vote_collector import VoteCollector
from .csv_exporter import CSVExporter
from .logging_config import configure_logging, get_logger
from .exceptions import ConfigurationError


class ApplicationContainer:
    """
    Centralized composition root for dependency injection.
    
    Constructs and provides shared infrastructure and domain collaborators
    including logger, configuration, API clients, services, and exporters.
    """
    
    def __init__(self, api_key: Optional[str] = None, verbose: bool = False, 
                 json_logs: bool = False, output_directory: str = "outputs"):
        """
        Initialize the application container.
        
        Args:
            api_key: Congress.gov API key (if None, will try to get from environment)
            verbose: Enable debug logging
            json_logs: Use JSON log format
            output_directory: Directory for CSV output files
        """
        self._api_key = api_key
        self._verbose = verbose
        self._json_logs = json_logs
        self._output_directory = output_directory
        
        # Lazy-initialized components
        self._logger = None
        self._api_client = None
        self._web_scraper = None
        self._vote_collector = None
        self._csv_exporter = None
        self._correlation_id = None
    
    @property
    def logger(self):
        """Get configured logger instance."""
        if self._logger is None:
            self._logger = configure_logging(self._verbose, self._json_logs)
        return self._logger
    
    @property
    def correlation_id(self) -> str:
        """Get correlation ID for this session."""
        if self._correlation_id is None:
            self._correlation_id = str(uuid.uuid4())[:8]
        return self._correlation_id
    
    @property
    def api_client(self) -> CongressAPIClient:
        """Get Congress.gov API client."""
        if self._api_client is None:
            api_key = self._get_api_key()
            self._api_client = CongressAPIClient(api_key)
        return self._api_client
    
    @property
    def web_scraper(self) -> ClerkHouseGovScraper:
        """Get web scraper for clerk.house.gov."""
        if self._web_scraper is None:
            self._web_scraper = ClerkHouseGovScraper()
        return self._web_scraper
    
    @property
    def vote_collector(self) -> VoteCollector:
        """Get vote collector service."""
        if self._vote_collector is None:
            self._vote_collector = VoteCollector(
                api_client=self.api_client,
                web_scraper=self.web_scraper
            )
        return self._vote_collector
    
    @property
    def csv_exporter(self) -> CSVExporter:
        """Get CSV exporter."""
        if self._csv_exporter is None:
            self._csv_exporter = CSVExporter(self._output_directory)
        return self._csv_exporter
    
    def _get_api_key(self) -> str:
        """
        Get Congress.gov API key from container or environment.
        
        Returns:
            API key string
            
        Raises:
            ConfigurationError: If API key is not available
        """
        # Use provided API key first
        if self._api_key:
            return self._api_key
        
        # Try to get from environment
        api_key = os.getenv('CONGRESS_API_KEY')
        
        if not api_key or api_key == 'your_actual_api_key_here':
            raise ConfigurationError(
                "CONGRESS_API_KEY environment variable is required. "
                "Please set it in your .env file. "
                "Get your API key from: https://api.congress.gov/sign-up/"
            )
        
        return api_key
    
    def validate_configuration(self) -> None:
        """
        Validate that all required configuration is available.
        
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate API key
        try:
            self._get_api_key()
        except ConfigurationError:
            raise
        
        # Validate output directory
        if not self.csv_exporter.validate_output_directory():
            raise ConfigurationError(
                f"Output directory '{self._output_directory}' is not writable. "
                "Please check permissions or specify a different directory."
            )
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if self._api_client:
            self._api_client.session.close()
        
        if self._web_scraper:
            self._web_scraper.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
