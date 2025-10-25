"""
Configuration Template for Congress.gov API

Instructions:
1. Create a .env file in the project root directory
2. Add your Congress.gov API key to the .env file:
   CONGRESS_API_KEY=your_actual_api_key_here
3. Get your API key from: https://api.congress.gov/sign-up/
4. Install python-dotenv: pip install python-dotenv

Example .env file contents:
# Congress.gov API Configuration
CONGRESS_API_KEY=your_actual_api_key_here
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_congress_api_key():
    """
    Retrieve the Congress.gov API key from environment variables.
    
    Returns:
        str: The API key
        
    Raises:
        ValueError: If the API key is not found in environment variables
    """
    api_key = os.getenv('CONGRESS_API_KEY')
    
    if not api_key or api_key == 'your_actual_api_key_here':
        raise ValueError(
            "CONGRESS_API_KEY environment variable is required. "
            "Please set it in your .env file. "
            "Get your API key from: https://api.congress.gov/sign-up/"
        )
    
    return api_key

# Example usage:
if __name__ == "__main__":
    try:
        key = get_congress_api_key()
        print("API key loaded successfully!")
    except ValueError as e:
        print(f"Error: {e}")
