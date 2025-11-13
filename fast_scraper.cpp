#define NOMINMAX
#include <iostream>
#include <string>
#include <vector>
#include <curl/curl.h>
#include <tbb/parallel_for_each.h> // <-- NEW: TBB include
#include <tbb/concurrent_vector.h> // <-- NEW: Thread-safe vector
#include <map>
#include <regex>
#include <fstream>
#include <nlohmann/json.hpp>

// This struct will hold a URL and its resulting HTML
struct ScrapeJob {
    std::string url;
    std::string result_html;
};

// This WriteCallback is the same as before
size_t WriteCallback(void* contents, size_t size, size_t nmemb, std::string* userp) {
    userp->append((char*)contents, size * nmemb);
    return size * nmemb;
}

// This scrape_url function is the same, but we'll modify it slightly
// to be called by our parallel function
void scrape_url(ScrapeJob& job) { // <-- NEW: Takes a ScrapeJob struct
    CURL* curl;
    CURLcode res;
    std::string readBuffer;

    curl = curl_easy_init();
    if (curl) {
        curl_easy_setopt(curl, CURLOPT_URL, job.url.c_str());
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L); // 5 second timeout

        res = curl_easy_perform(curl);
        curl_easy_cleanup(curl);

        if (res == CURLE_OK) {
            job.result_html = readBuffer;
        } else {
            job.result_html = "CURL_ERROR: " + std::string(curl_easy_strerror(res));
        }
    } else {
        job.result_html = "CURL_INIT_ERROR";
    }
}


// --- NEW: The Parallel Dorker Function ---
// This function takes a list of URLs and scrapes them all at once.
std::map<std::string, std::string> parallel_scrape(const std::vector<std::string>& urls) {
    
    // 1. Create a list of "jobs" for TBB to process
    tbb::concurrent_vector<ScrapeJob> jobs;
    for (const auto& url : urls) {
        jobs.push_back({url, ""});
    }

    // 2. This is the magic: TBB's parallel_for_each
    // It runs the 'scrape_url' function on every job in the 'jobs' list
    // using as many CPU cores as possible.
    tbb::parallel_for_each(jobs.begin(), jobs.end(), [](ScrapeJob& job) {
        scrape_url(job);
    });

    // 3. Collect the results into a map to return to Python
    std::map<std::string, std::string> results;
    for (const auto& job : jobs) {
        results[job.url] = job.result_html;
    }
    
    return results;
}
struct SherlockJob {
    std::string site_name;
    std::string url;
    bool found;
};

// This is a specialized scrape function for Sherlock
// It doesn't need the HTML, it just needs to know if the page exists (HTTP 200)
void check_sherlock_url(SherlockJob& job) {
    CURL* curl;
    CURLcode res;
    long http_code = 0;

    curl = curl_easy_init();
    if (curl) {
        curl_easy_setopt(curl, CURLOPT_URL, job.url.c_str());
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36");
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        
        // We don't want the body, just the headers (much faster)
        curl_easy_setopt(curl, CURLOPT_NOBODY, 1L);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);

        res = curl_easy_perform(curl);
        
        if (res == CURLE_OK) {
            // Get the HTTP response code
            curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
            
            // 200 OK means the page exists and the username is taken
            if (http_code == 200) {
                job.found = true;
            } else {
                job.found = false;
            }
        } else {
            job.found = false; // Any curl error means it's not found
        }
        curl_easy_cleanup(curl);
    } else {
        job.found = false;
    }
}

// This is the new function we will call from Python
std::map<std::string, std::string> load_sherlock_sites() {
    std::ifstream file("sherlock_sites.json");
    nlohmann::json j;
    file >> j;
    
    std::map<std::string, std::string> sites;
    for (auto& [name, info] : j.items()) {
        sites[name] = info["url"];
    }
    return sites;
}

    // 1. Create the job list
    tbb::concurrent_vector<SherlockJob> jobs;
    for (const auto& site_template : sites_to_check) {
        std::string url = site_template;
        url.replace(url.find("{username}"), 10, username); // Replace {username}
        jobs.push_back({site_template, url, false});
    }

    // 2. Run all checks in parallel using TBB
    tbb::parallel_for_each(jobs.begin(), jobs.end(), [](SherlockJob& job) {
        check_sherlock_url(job);
    });

    // 3. Collect only the URLs that were found
    std::vector<std::string> results;
    for (const auto& job : jobs) {
        if (job.found) {
            results.push_back(job.url);
        }
    }
    
    return results;
}
struct HarvesterResults {
    std::vector<std::string> emails;
    std::vector<std::string> subdomains;
};

// This is the new function we will call from Python
HarvesterResults parallel_harvester(const std::string& domain) {
    
    // 1. Define the dork queries for harvesting
    std::vector<std::string> dorks = {
        // Google Dorks
        "site:google.com \"@" + domain + "\"",
        // Bing Dorks
        "\"@" + domain + "\"",
        // Find subdomains
        "site:*." + domain
    };

    // 2. Build the full URLs to scrape
    std::vector<std::string> urls_to_scrape;
    for (const auto& dork : dorks) {
        // We'll just use Google for this example. We can add Bing, etc. later.
        urls_to_scrape.push_back("https://www.google.com/search?q=" + dork + "&num=50");
    }

    // 3. Run all scrapes in parallel using our existing function!
    std::map<std::string, std::string> scraped_html_map = parallel_scrape(urls_to_scrape);

    HarvesterResults final_results;
    
    // 4. Define regex patterns for emails and subdomains
    std::regex email_regex(R"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})");
    std::regex subdomain_regex(R"(([a-zA-Z0-9.-]+\.)" + domain + ")");

    // 5. Process the HTML results
    for (const auto& pair : scraped_html_map) {
        std::string html = pair.second;
        if (html.find("CURL_ERROR") != std::string::npos) continue;

        // Find emails
        std::sregex_iterator email_iter(html.begin(), html.end(), email_regex);
        std::sregex_iterator end;
        while (email_iter != end) {
            std::string email = email_iter->str();
            // A simple check to only get emails from the target domain
            if (email.find(domain) != std::string::npos) {
                final_results.emails.push_back(email);
            }
            ++email_iter;
        }

        // Find subdomains
        std::sregex_iterator sub_iter(html.begin(), html.end(), subdomain_regex);
        while (sub_iter != end) {
            final_results.subdomains.push_back(sub_iter->str());
            ++sub_iter;
        }
    }
    
    return final_results;
}