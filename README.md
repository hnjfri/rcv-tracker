# Roll Call Vote (RCV) Tracker

A Python application that uses the Congress.gov API to pull roll call votes for specified members of Congress across multiple congressional sessions.

## Features

- Retrieves roll call votes from Congress.gov API
- Scrapes additional vote details from clerk.house.gov
- Supports multiple Congress sessions in a single run
- Exports results to CSV format with proper date formatting
- Comprehensive error handling and logging
- Follows SOLID principles and dependency injection patterns

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Congress.gov API Key

1. Visit https://api.congress.gov/sign-up/
2. Sign up for a free API key
3. Create a `.env` file in the project root:

```bash
echo "CONGRESS_API_KEY=your_actual_api_key_here" > .env
```

Replace `your_actual_api_key_here` with your actual API key.

### 3. Make Script Executable

The script should already be executable, but if needed:

```bash
chmod +x rcv
```

## Usage

```bash
./rcv <last_name> <state> <congress_number> [congress_number ...]
```

### Arguments

- `last_name`: Last name of the congress member
- `state`: Two-letter state abbreviation (e.g., CA, NY, TX)
- `congress_number`: One or more Congress numbers to search (e.g., 118 119)

### Example

```bash
./rcv Thompson CA 118 119
```

This will:
1. Search for all roll call votes by a member with last name "Thompson" from California (CA)
2. Look through Congress sessions 118 and 119
3. Extract vote details including question and bill title
4. Save results to `outputs/Thompson_YYYYMMDD.csv`

## Output

The program creates CSV files in the `outputs/` directory with the following columns:

1. **Congress** - Congress number (e.g., 118)
2. **Date** - Vote date in YYYY-MM-DD format
3. **Roll Call Number** - Roll call vote number
4. **Legislation** - Legislation identifier (e.g., "HR758") or "Non-Legislative" for procedural votes
5. **Vote Cast** - How the member voted (e.g., "Yea", "Nay", "Present")
6. **Question** - The question being voted on
7. **Bill Title** - Title of the bill or resolution (may be empty for non-legislative votes)
8. **Roll Call Vote URL** - Direct link to the House clerk's vote page

### Output File Naming

Files are named: `{LastName}_{YYYYMMDD}.csv`

Example: `Thompson_20251025.csv`

## Environment Variables

- `CONGRESS_API_KEY` (Required): Your Congress.gov API key
- `JSON_LOGS` (Optional): Set to 'true' for structured JSON logging
- `VERBOSE` (Optional): Set to 'true' for debug-level logging

## Error Handling

The application includes comprehensive error handling for:

- Invalid command line arguments
- Missing or invalid API keys
- API rate limiting and network errors
- Web scraping failures (continues with partial data)
- File I/O errors
- Missing or incomplete vote data (includes all votes with empty fields when data unavailable)

## Architecture

The application follows SOLID principles and uses dependency injection:

- **Models**: Data structures with validation for vote records and API responses
- **API Client**: Congress.gov API interaction with retry logic and rate limiting
- **Web Scraper**: Extracts additional details from clerk.house.gov with multiple fallback patterns
- **Vote Collector**: Orchestrates data collection workflow and generates roll call URLs
- **CSV Exporter**: Handles output file generation with all 8 columns
- **Container**: Dependency injection and configuration management

## Logging

The application uses structured logging with:

- Console output for user feedback
- Detailed logs for debugging and monitoring
- Correlation IDs for tracking operations
- Performance metrics and error tracking

## Development

### Project Structure

```
rcv-votes/
├── rcv                          # Main CLI script
├── requirements.txt             # Python dependencies
├── .env                        # API key configuration (create this)
├── config_template.py          # Configuration helper
├── rcv_votes/                  # Main package
│   ├── __init__.py
│   ├── exceptions.py           # Custom exceptions
│   ├── models.py              # Data models
│   ├── logging_config.py      # Logging configuration
│   ├── congress_api.py        # Congress.gov API client
│   ├── web_scraper.py         # Web scraping functionality
│   ├── vote_collector.py      # Vote collection orchestration
│   ├── csv_exporter.py        # CSV export functionality
│   └── container.py           # Dependency injection container
└── outputs/                   # Generated CSV files (created automatically)
```

### Adding New Features

1. Follow the existing patterns for error handling and logging
2. Use dependency injection through the ApplicationContainer
3. Add comprehensive data validation
4. Include appropriate type hints
5. Follow the established naming conventions

## Troubleshooting

### Common Issues

1. **"CONGRESS_API_KEY environment variable is required"**
   - Make sure you've created the `.env` file with your API key
   - Verify the API key is correct and not the placeholder text

2. **"No votes found for [Member]"**
   - Check the spelling of the member's last name
   - Verify the state abbreviation is correct
   - Ensure the member served during the specified Congress sessions

3. **Rate limiting errors**
   - The application includes automatic retry logic with exponential backoff
   - If persistent, try running with fewer Congress sessions at once

4. **Web scraping warnings**
   - The program continues running and includes partial data when scraping fails
   - Empty fields in CSV indicate data that could not be scraped
   - All votes are still included in the output

5. **Permission errors on output directory**
   - Ensure you have write permissions in the project directory
   - The `outputs/` directory will be created automatically if it doesn't exist

### Getting Help

For issues or questions:
1. Check the console output for specific error messages
2. Enable verbose logging: `VERBOSE=true ./rcv ...`
3. Review the generated log files for detailed error information
