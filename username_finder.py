# core_utils/username_finder.py
"""
Discovers usernames from real names using multiple strategies
"""

import requests
from bs4 import BeautifulSoup
import re
import logging

def find_usernames_from_name(full_name: str):
    """
    Given a real name, tries to discover associated usernames.
    
    Strategy:
    1. Google dork for social profiles
    2. Check common username patterns
    3. LinkedIn/GitHub profile scraping
    
    Args:
        full_name: "John Doe" or "John Michael Doe"
    
    Returns:
        dict: {
            'likely_usernames': [...],
            'social_profiles_found': {...}
        }
    """
    results = {
        'likely_usernames': set(),
        'social_profiles_found': {}
    }
    
    # === STRATEGY 1: Google Dorking ===
    # Search: "John Doe" site:instagram.com OR site:twitter.com
    google_results = _google_search_profiles(full_name)
    results['social_profiles_found'].update(google_results)
    
    # === STRATEGY 2: Common Username Patterns ===
    # Generate likely usernames from name
    name_parts = full_name.lower().split()
    if len(name_parts) >= 2:
        first = name_parts[0]
        last = name_parts[-1]
        
        patterns = [
            f"{first}{last}",           # johndoe
            f"{first}.{last}",          # john.doe
            f"{first}_{last}",          # john_doe
            f"{first}{last[0]}",        # johnd
            f"{first[0]}{last}",        # jdoe
            f"{last}{first}",           # doejohn
            f"{first}{last}123",        # johndoe123
            f"{first}_{last}_",         # john_doe_
        ]
        
        results['likely_usernames'].update(patterns)
    
    # === STRATEGY 3: Email Pattern Detection ===
    # If you have an email, extract username part
    # (This would be a separate function)
    
    # === STRATEGY 4: Pipl.com API (Paid) ===
    # Professional people search engine
    # (Implementation if API key available)
    
    return {
        'likely_usernames': list(results['likely_usernames']),
        'social_profiles_found': results['social_profiles_found']
    }

def _google_search_profiles(name: str):
    """
    Searches Google for social profiles of a person.
    """
    profiles = {}
    
    # Build search query
    query = f'"{name}" site:instagram.com OR site:twitter.com OR site:linkedin.com OR site:github.com'
    
    try:
        # Use DuckDuckGo (no rate limits)
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = ddgs.text(keywords=query, max_results=10)
            
            for result in results:
                url = result['href']
                
                # Extract username from URL
                if 'instagram.com' in url:
                    match = re.search(r'instagram\.com/([^/\?]+)', url)
                    if match:
                        profiles['instagram'] = match.group(1)
                
                elif 'twitter.com' in url or 'x.com' in url:
                    match = re.search(r'(?:twitter|x)\.com/([^/\?]+)', url)
                    if match:
                        profiles['twitter'] = match.group(1)
                
                elif 'linkedin.com/in' in url:
                    match = re.search(r'linkedin\.com/in/([^/\?]+)', url)
                    if match:
                        profiles['linkedin'] = match.group(1)
                
                elif 'github.com' in url:
                    match = re.search(r'github\.com/([^/\?]+)', url)
                    if match:
                        profiles['github'] = match.group(1)
    
    except Exception as e:
        logging.error(f"[UsernameFinder] Search failed: {e}")
    
    return profiles

def smart_dossier_search(query: str):
    """
    Smart search that determines if input is name or username.
    
    If it looks like a name (has spaces), find usernames first.
    If it looks like a username, search directly.
    """
    # Check if query looks like a username (no spaces, possibly numbers)
    if ' ' not in query and not query.replace('_', '').replace('.', '').isalpha():
        # Looks like username - search directly
        return {'type': 'username', 'value': query}
    
    # Looks like a name - find usernames first
    username_results = find_usernames_from_name(query)
    
    return {
        'type': 'name',
        'original_query': query,
        'discovered_usernames': username_results['likely_usernames'],
        'found_profiles': username_results['social_profiles_found']
    }

# === INTEGRATION WITH DOSSIER SYSTEM ===

def enhanced_dossier_builder(query: str):
    """
    Enhanced dossier that handles both names and usernames.
    """
    # Step 1: Determine query type
    smart_result = smart_dossier_search(query)
    
    if smart_result['type'] == 'name':
        # Found a name - show user the discovered usernames
        report = {
            'query_type': 'Real Name',
            'original_name': query,
            'discovered_usernames': smart_result['discovered_usernames'],
            'confirmed_profiles': smart_result['found_profiles']
        }
        
        # Ask user which username to investigate
        return {
            'status': 'username_selection_needed',
            'report': report,
            'next_step': 'User should select a username to investigate'
        }
    
    else:
        # Username provided - run full Sherlock scan
        return {
            'status': 'ready_for_sherlock',
            'username': query
        }

# === TEST ===
if __name__ == "__main__":
    # Test 1: Real name
    print("=== Test 1: Real Name ===")
    result = find_usernames_from_name("Hammad Khan")
    print(f"Likely usernames: {result['likely_usernames']}")
    print(f"Found profiles: {result['social_profiles_found']}")
    
    # Test 2: Smart search
    print("\n=== Test 2: Smart Search ===")
    result = smart_dossier_search("John Doe")
    print(result)
    
    print("\n=== Test 3: Username Search ===")
    result = smart_dossier_search("darkphoenix007")
    print(result)