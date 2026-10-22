# Roll Call Vote (RCV) Tracker

A Python application that uses the Congress.gov API to pull every House roll call vote in one or more congresses and report how a specified member voted on each one, including votes the member missed.

## Features

- Retrieves every House roll call vote in the requested congresses from Congress.gov API
- Records the specified member's vote on each roll call: Yea, Nay, Present, or Not Voting
- Flags missed votes in a dedicated column so they can be filtered in a spreadsheet
- Scrapes additional vote details from clerk.house.gov
- Supports multiple Congress sessions in a single run
- Caches roll call data on disk so reruns and additional legislators avoid repeat API requests
- Keeps going when individual roll calls fail, and reports exactly what is missing
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
./rcv <last_name> <state> <district> <congress_number> [congress_number ...]
```

### Arguments

- `last_name`: Last name of the congress member
- `state`: Two-letter state abbreviation (e.g., CA, NY, TX)
- `district`: House district number (e.g., 04 or 4)
- `congress_number`: One or more Congress numbers to search (e.g., 118 119)

### Example

```bash
./rcv Thompson CA 04 118 119
```

This will:
1. Find every House roll call vote in Congress sessions 118 and 119
2. Identify the member with last name "Thompson" from California's 4th district (CA-04) on each roll call and record how they voted (including Not Voting)
3. Extract vote details including question and bill title
4. Save results to `outputs/Thompson_YYYYMMDD.csv`, one row per roll call

## Recent Updates

- Roll call data is now cached in `cache/` (one small JSON file per roll call). The cache is not tied to a legislator, so running a second member for the same congress makes almost no API requests, and a run that is interrupted resumes where it left off. Delete `cache/` or set `RCV_REFRESH=true` to refetch.
- The roll calls in each session are now taken from the API's vote list instead of probing numbers until requests fail. If the list is unavailable the program falls back to probing.
- A roll call that fails (bad response, server error) no longer aborts the run. Failures are listed at the end and the CSV is saved with a `_PARTIAL` suffix. If the API rate limit is reached, collection stops, everything gathered is saved as `_PARTIAL`, and re-running the same command finishes the rest from the cache.
- The vote date now comes from the API rather than the scraped page. The clerk page is only used for the question and bill title.
- The run summary shows how many roll calls came from the cache and how many API requests were made.
- Removed unused code: unused API fields and imports, the unused `config_template.py`, and the testing-only vote limit parameter.
- Members are now identified by last name, state, and district (for example, `Thompson CA 04`). The district is resolved to a Bioguide ID for each congress through the Congress.gov Members endpoint, because the roll call vote data does not include district. A congress in which no member with that last name served that district is skipped with a warning.
- The program now collects every House roll call vote in the requested congresses, not only the ones the member voted on. Missed votes appear as "Not Voting" and are flagged in the new "Missed Vote" column.
- Removed the temporary 10-vote testing limit from the command line script, so a run now processes every roll call. Expect runs to take much longer, since each roll call requires an API request and a page fetch from clerk.house.gov.

## Output

The program creates CSV files in the `outputs/` directory with one row per roll call vote, whether or not the member voted. The file has the following columns:

1. **Congress** - Congress number (e.g., 118)
2. **Date** - Vote date in YYYY-MM-DD format
3. **Roll Call Number** - Roll call vote number
4. **Legislation** - Legislation identifier (e.g., "HR758") or "Non-Legislative" for procedural votes
5. **Vote Cast** - How the member voted: "Yea", "Nay", "Present", or "Not Voting" (see below)
6. **Missed Vote** - "Yes" if Vote Cast is "Not Voting", otherwise "No". Filter this column to see every vote the member missed.
7. **Question** - The question being voted on
8. **Bill Title** - Title of the bill or resolution (may be empty for non-legislative votes)
9. **Roll Call Vote URL** - Direct link to the House clerk's vote page

### Vote Cast Values

The API's "Aye" and "Yea" are both reported as "Yea", and "No" and "Nay" as "Nay". The values are:

- **Yea** - voted yes
- **Nay** - voted no
- **Present** - voted present
- **Not Voting** - listed on the roll call but did not vote (absent). These rows have Missed Vote = "Yes".
- **Not on Roll** - the member does not appear on that roll call at all (for example, before being sworn in or after leaving office, or during a vacancy). These rows have Missed Vote = "No" because the member was not eligible to vote.

If the member does not appear on any roll call in the requested congresses, no file is written and the program reports that no votes were found.

### Output File Naming

Files are named: `{LastName}_{YYYYMMDD}.csv`

Example: `Thompson_20251025.csv`

## Environment Variables

- `CONGRESS_API_KEY` (Required): Your Congress.gov API key
- `JSON_LOGS` (Optional): Set to 'true' for structured JSON logging
- `VERBOSE` (Optional): Set to 'true' for debug-level logging
- `RCV_REFRESH` (Optional): Set to 'true' to ignore cached roll calls and fetch them again

## Error Handling

The application includes comprehensive error handling for:

- Invalid command line arguments
- Missing or invalid API keys
- API rate limiting and network errors
- Web scraping failures (continues with partial data)
- File I/O errors
- Missing or incomplete vote data (includes all roll calls with empty fields when data unavailable)

## Architecture

The application follows SOLID principles and uses dependency injection:

- **Models**: Data structures with validation for vote records and API responses
- **API Client**: Congress.gov API interaction with retry logic, rate limit handling, and the vote list
- **Vote Cache**: On-disk cache of roll call data, shared across legislators
- **Web Scraper**: Extracts additional details from clerk.house.gov with multiple fallback patterns
- **Vote Collector**: Iterates over every roll call in each congress, records the member's vote on each, and generates roll call URLs
- **CSV Exporter**: Handles output file generation with all 9 columns
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
├── rcv_votes/                  # Main package
│   ├── __init__.py
│   ├── exceptions.py           # Custom exceptions
│   ├── models.py              # Data models
│   ├── logging_config.py      # Logging configuration
│   ├── congress_api.py        # Congress.gov API client
│   ├── vote_cache.py          # On-disk roll call cache
│   ├── web_scraper.py         # Web scraping functionality
│   ├── vote_collector.py      # Vote collection orchestration
│   ├── csv_exporter.py        # CSV export functionality
│   └── container.py           # Dependency injection container
├── cache/                     # Cached roll call data (created automatically)
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
   - Verify the state abbreviation and district number are correct
   - Ensure the member served during the specified Congress sessions
   - The member must have represented that district in the requested congress (districts can change between congresses after redistricting)
   - The member must appear on at least one roll call in the requested congresses

3. **Rate limiting errors**
   - The application includes automatic retry logic with exponential backoff
   - If the limit is still hit, the run stops and saves a `_PARTIAL` file. Wait for the limit to reset and re-run the same command; cached roll calls are not requested again

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
