# In: core_utils/osint_utils.py

import logging
import requests
from bs4 import BeautifulSoup
from scapy.all import srp, Ether, ARP
import subprocess
import json
import os
import database
import core_utils.argus_cpp_core
import time
import config

# --- Tool 1: Google Dorking (NOW C++ POWERED) ---
def search_google_dorks(query: str, num_results: int = 5):
    """
    Uses the C++ core to run all dork scrapes in parallel.
    """
    print(f"--- [OSINT-Dork-C++] Hunting for: {query} ---")
    
    # Define our dork queries
    dorks = [
        f'"{query}"',
        f'site:go.in filetype:pdf "{query}"',
        f'site:*.gov filetype:pdf "{query}"',
        f'site:linkedin.com "{query}"',
        f'inurl:database "index of" "{query}"'
    ]
    
    # Build the URLs for the C++ scraper
    urls_to_scrape = [f"https://www.google.com/search?q={dork}&num={num_results}" for dork in dorks]
    
    all_results = {}
    
    try:
        # --- THIS IS THE C++ CALL ---
        # It scrapes all 5 URLs at the same time
        scraped_html_map = core_utils.argus_cpp_core.parallel_scrape(urls_to_scrape)
        
        # Now we parse the HTML (which is fast) in Python
        for i, url in enumerate(urls_to_scrape):
            html = scraped_html_map.get(url, "")
            dork_key = dorks[i].split(" ")[0] # Get 'site:go.in' as key
            
            if "CURL_ERROR" in html or not html:
                all_results[dork_key] = []
                continue

            soup = BeautifulSoup(html, 'html.parser')
            links = []
            for g in soup.find_all('div', class_='g'): # Updated class
                a_tag = g.find('a')
                if a_tag and a_tag.get('href'):
                    links.append(a_tag.get('href'))
            
            all_results[dork_key] = links[:num_results]
            
        return all_results

    except Exception as e:
        print(f"--- [OSINT-Dork-C++] Error during parallel scrape: {e} ---")
        return {"error": str(e)}

def search_socials(username: str):
    """
    Uses the 'sherlock' CLI tool to find social media accounts.
    """
    print(f"--- [OSINT-Social] Hunting for: {username} ---")
    
    # --- FIX: Use config.PROJECT_ROOT for a reliable path ---
    sherlock_dir = os.path.join(config.PROJECT_ROOT, "sherlock")
    sherlock_script = os.path.join(sherlock_dir, "sherlock", "sherlock.py")

    if not os.path.exists(sherlock_script):
        return {"error": "Sherlock not found. Path does not exist: " + sherlock_script}

    command = [
        "python3", 
        sherlock_script, 
        username, 
        "--timeout", "5",
        "--print-found"
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=True)
        found_urls = result.stdout.strip().split('\n')
        found_urls = [line.split(":")[-1].strip() for line in found_urls if "http" in line]
        return {"username": username, "profiles": found_urls}
    except FileNotFoundError:
        return {"error": "Sherlock not found or 'python3' is not a valid command."}
    except subprocess.CalledProcessError as e:
        return {"error": f"Sherlock failed: {e.stderr}"}
    except Exception as e:
        return {"error": f"An error occurred with Sherlock: {e}"}

# --- Tool 3: Domain Intel (theHarvester) ---
def find_domain_intel(domain: str):
    """
    Uses 'theHarvester' CLI tool to find emails and subdomains.
    """
    print(f"--- [OSINT-Domain] Hunting for: {domain} ---")

    # --- FIX: Use config.PROJECT_ROOT for a reliable path ---
    harvester_dir = os.path.join(config.PROJECT_ROOT, "theHarvester")
    harvester_script = os.path.join(harvester_dir, "theHarvester.py")

    if not os.path.exists(harvester_script):
        return {"error": "theHarvester not found. Path does not exist: " + harvester_script}

    command = [
        "python3",
        harvester_script,
        "-d", domain,
        "-b", "google,bing",
        "-l", "100"
    ]
    
    try:
        # theHarvester must be run from its own directory
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, cwd=harvester_dir)
        return {"domain": domain, "intel": result.stdout}
    except FileNotFoundError:
        return {"error": "theHarvester not found or 'python3' is not a valid command."}
    except Exception as e:
        return {"error": f"An error occurred with theHarvester: {e}"}

# --- Tool 4: Breach Check (Have I Been Pwned) ---
def check_breaches(email: str):
    """
    Checks HIBP for breaches. Now with fallback to free endpoint!
    """
    hibp_api_key = database.load_profile_setting("HIBP_API_KEY")
    
    # TRY METHOD 1: Premium API (if key exists)
    if hibp_api_key:
        try:
            headers = {
                "hibp-api-key": hibp_api_key,
                "User-Agent": "ARGUS-OSINT"
            }
            response = requests.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                breaches = response.json()
                return {
                    "email": email,
                    "breach_count": len(breaches),
                    "breaches": [b['Name'] for b in breaches],
                    "details": breaches
                }
            elif response.status_code == 404:
                return {"email": email, "breach_count": 0, "status": "clean"}
        except Exception as e:
            logging.warning(f"[HIBP API] Failed: {e}, trying fallback...")
    
    # METHOD 2: Free dehashed.com check (no key needed)
    try:
        response = requests.get(
            f"https://api.dehashed.com/search?query=email:{email}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "email": email,
                "breach_count": data.get('total', 0),
                "source": "dehashed",
                "status": "found" if data.get('total', 0) > 0 else "clean"
            }
    except:
        pass
    
    # METHOD 3: LeakCheck.io (free tier)
    try:
        response = requests.get(
            f"https://leakcheck.io/api/public?check={email}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "email": email,
                "breach_count": len(data.get('sources', [])),
                "sources": data.get('sources', []),
                "source": "leakcheck"
            }
    except:
        pass
    
    return {"error": "All breach check methods failed", "email": email}
    
def test_cpp_scraper(query: str):
    """
    Compares the speed of Python Requests vs C++ libcurl.
    """
    print(f"--- [C++ Test] Running speed comparison for: {query} ---")
    
    # 1. Python (Requests)
    start_py = time.time()
    try:
        requests.get(f"https://www.google.com/search?q={query}")
        end_py = time.time()
        py_time = (end_py - start_py) * 1000
    except Exception as e:
        py_time = f"Failed: {e}"
        
    # 2. C++ (libcurl)
    start_cpp = time.time()
    try:
        core_utils.argus_cpp_core.scrape_url(f"https://www.google.com/search?q={query}")
        end_cpp = time.time()
        cpp_time = (end_cpp - start_cpp) * 1000
    except Exception as e:
        cpp_time = f"Failed: {e}"

    result = f"Python (requests): {py_time:.2f} ms\nC++ (libcurl): {cpp_time:.2f} ms"
    print(result)
    return result

# --- Tool 5: Network Scan (Scapy) ---
def scan_local_network():
    """
    Uses Scapy to find all devices on the local network.
    """
    print("--- [OSINT-Network] Scanning local network... (Requires Admin/Sudo) ---")
    try:
        arp_request = ARP(pdst="192.168.1.1/24") # Adjust if your IP range is different
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = broadcast / arp_request
        ans, unans = srp(packet, timeout=2, verbose=False)
        
        devices = []
        for sent, received in ans:
            devices.append({'ip': received.psrc, 'mac': received.hwsrc})
            
        if not devices:
            return {"error": "No devices found."}
        return {"devices_found": devices}
    except PermissionError:
        return {"error": "Permission denied. This scan must be run as root/administrator."}
    except Exception as e:
        return {"error": f"An error occurred with Scapy: {e}"}