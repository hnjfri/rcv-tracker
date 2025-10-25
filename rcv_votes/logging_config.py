"""
Centralized logging configuration for RCV Votes application.
"""

import logging
import sys
import json
import os
from typing import Optional


def configure_logging(verbose: bool = False, json_logs: bool = False) -> logging.Logger:
    """
    Centralized logger configuration.
    
    Args:
        verbose: Enable debug level logging
        json_logs: Output structured JSON logs instead of human-readable format
        
    Returns:
        Configured logger instance
    """
    # Single root logger namespace
    logger = logging.getLogger('rcv_votes')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Clear any existing handlers to prevent duplicates
    logger.handlers.clear()
    logger.propagate = False
    
    # Console handler for human-readable output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING if not verbose else logging.DEBUG)
    
    # Configure formatter based on output type
    if json_logs:
        console_handler.setFormatter(JsonFormatter())
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    logger.addHandler(console_handler)
    
    return logger


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        payload = {
            'timestamp': self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            'logger': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra context if present
        if hasattr(record, 'operation'):
            payload['operation'] = record.operation
        if hasattr(record, 'context'):
            payload['context'] = record.context
        if hasattr(record, 'correlation_id'):
            payload['correlation_id'] = record.correlation_id
        if hasattr(record, 'duration'):
            payload['duration'] = record.duration
        if hasattr(record, 'status'):
            payload['status'] = record.status
            
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a specific module.
    
    Args:
        name: Module name (will be prefixed with 'rcv_votes.')
        
    Returns:
        Logger instance for the module
    """
    return logging.getLogger(f'rcv_votes.{name}')


def log_operation_start(logger: logging.Logger, operation: str, correlation_id: str, **context) -> None:
    """Log the start of an operation with context."""
    logger.info(f"Starting {operation}", extra={
        'operation': operation,
        'correlation_id': correlation_id,
        'context': context,
        'status': 'started'
    })


def log_operation_success(logger: logging.Logger, operation: str, correlation_id: str, 
                         duration: float, **context) -> None:
    """Log successful completion of an operation."""
    logger.info(f"Completed {operation} in {duration:.2f}s", extra={
        'operation': operation,
        'correlation_id': correlation_id,
        'duration': duration,
        'status': 'success',
        'context': context
    })


def log_operation_error(logger: logging.Logger, operation: str, correlation_id: str, 
                       error: Exception, **context) -> None:
    """Log operation failure with error details."""
    logger.error(f"Failed {operation}: {error}", extra={
        'operation': operation,
        'correlation_id': correlation_id,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'status': 'error',
        'context': context
    })
