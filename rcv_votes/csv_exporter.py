"""
CSV export functionality for vote records.
"""

import csv
import os
from pathlib import Path
from typing import List
from datetime import datetime

from .models import VoteRecord
from .exceptions import ValidationError
from .logging_config import get_logger


class CSVExporter:
    """Exports vote records to CSV format."""
    
    def __init__(self, output_directory: str = "outputs"):
        """
        Initialize the CSV exporter.
        
        Args:
            output_directory: Directory to save CSV files (default: "outputs")
        """
        self.output_directory = Path(output_directory)
        self.logger = get_logger('csv_exporter')
        
        # Ensure output directory exists
        self.output_directory.mkdir(exist_ok=True)
    
    def export_votes(self, vote_records: List[VoteRecord], member_last_name: str) -> str:
        """
        Export vote records to CSV file.
        
        Args:
            vote_records: List of vote records to export
            member_last_name: Last name of the congress member (for filename)
            
        Returns:
            Path to the created CSV file
            
        Raises:
            ValidationError: If input data is invalid
        """
        if not vote_records:
            raise ValidationError("Cannot export empty vote records list")
        
        if not member_last_name or not isinstance(member_last_name, str):
            raise ValidationError("Member last name must be a non-empty string")
        
        # Generate filename with today's date
        today = datetime.now().strftime("%Y%m%d")
        filename = f"{member_last_name}_{today}.csv"
        file_path = self.output_directory / filename
        
        self.logger.info(f"Exporting {len(vote_records)} vote records to {file_path}")
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Define CSV columns as specified in requirements
                fieldnames = [
                    'Congress',
                    'Date', 
                    'Roll Call Number',
                    'Legislation',
                    'Vote Cast',
                    'Question',
                    'Bill Title',
                    'Roll Call Vote URL'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write vote records
                for vote_record in vote_records:
                    row = {
                        'Congress': vote_record.congress,
                        'Date': vote_record.date,
                        'Roll Call Number': vote_record.roll_call_number,
                        'Legislation': vote_record.legislation,
                        'Vote Cast': vote_record.vote_cast,
                        'Question': vote_record.question,
                        'Bill Title': vote_record.bill_title,
                        'Roll Call Vote URL': vote_record.roll_call_vote_url
                    }
                    
                    writer.writerow(row)
            
            self.logger.info(f"Successfully exported vote records to {file_path}")
            
            return str(file_path)
            
        except IOError as e:
            raise ValidationError(f"Failed to write CSV file: {e}") from e
        except Exception as e:
            raise ValidationError(f"Unexpected error during CSV export: {e}") from e
    
    def validate_output_directory(self) -> bool:
        """
        Validate that the output directory is writable.
        
        Returns:
            True if directory is writable, False otherwise
        """
        try:
            # Try to create a test file
            test_file = self.output_directory / ".write_test"
            test_file.touch()
            test_file.unlink()  # Remove test file
            return True
        except (OSError, PermissionError):
            return False
