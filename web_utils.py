import sys
from duckduckgo_search import DDGS

# Ensure you have the library installed:
# pip install duckduckgo-search
# (It might be 'ddgs', depending on your version)

def search_web(query: str, max_results: int = 5):
    """
    Performs a direct web search using DuckDuckGo.
    No proxies are used.
    
    Args:
        query (str): The search query.
        max_results (int): The maximum number of results to return.

    Returns:
        str: A formatted string of search results, or an error message.
    """
    print(f"--- [WebUtils] Searching for: '{query}'")
    
    try:
        # We initialize DDGS directly with a timeout
        with DDGS(timeout=10) as ddgs:
            results = ddgs.text(keywords=query, max_results=max_results)
            
            if not results:
                print("--- [WebUtils] No results found.")
                return "No web results found for that query."
            
            # Format the results cleanly for the LLM
            formatted_results = []
            for i, res in enumerate(results):
                # We only want the title, snippet (body), and URL
                formatted_results.append(
                    f"Result {i+1}:\n"
                    f"  Title: {res['title']}\n"
                    f"  Snippet: {res['body']}\n"
                    f"  URL: {res['href']}\n"
                )
            
            print("--- [WebUtils] Search complete. Returning results.")
            return "\n".join(formatted_results)

    except Exception as e:
        print(f"--- [WebUtils] Error during web search: {e}", file=sys.stderr)
        return f"Sorry, an error occurred during the web search: {e}"

# --- This part runs only if you execute this file directly ---
# --- (e.g., python web_utils.py) ---
if __name__ == "__main__":
    print("--- Testing web_utils.py ---")
    
    test_query = "What is the curriculum for Mechanical Engineering at NIT Silchar?"
    
    search_results = search_web(test_query)
    
    print("\n--- Test Results ---")
    print(search_results)
    
    print("\n--- Testing a failed search ---")
    # This query is designed to be hard to find
    search_results = search_web("asdlkfjhasdlkfjhasdlfkjh")
    print(search_results)
    