# core_utils/app_utils.py

# This is a placeholder for the send_to_ui function.
# main.py will set this variable when it initializes.
send_to_ui = None
# Add to core_utils/app_utils.py

APP_REGISTRY = {
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "gmail": "https://mail.google.com",
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "notion": "https://notion.so",
    "spotify": "https://open.spotify.com",
    "discord": "https://discord.com/app",
    "twitter": "https://twitter.com",
    "reddit": "https://reddit.com",
    "linkedin": "https://linkedin.com",
    "facebook": "https://facebook.com",
    "instagram": "https://instagram.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai"
}

def open_app_web(name_or_url: str):
    """
    Smart web app opener.
    If name matches registry, use that URL.
    Otherwise, treat as direct URL.
    """
    name_lower = name_or_url.lower()
    
    if name_lower in APP_REGISTRY:
        url = APP_REGISTRY[name_lower]
        title = name_lower.capitalize()
    else:
        # Assume it's a URL
        url = name_or_url
        if not url.startswith('http'):
            url = 'https://' + url
        title = url.split('/')[2]  # Extract domain
    
    return open_webview(url, title)

def open_webview(url: str, title: str = "WebView"):
    """
    Tells the Electron UI to spawn a new panel 
    and load a specific URL into it.
    """
    if not send_to_ui:
        print("--- [AppUtils] Error: send_to_ui not initialized. ---")
        return "Error: UI communication is not set up."
        
    print(f"--- [AppUtils] Spawning WebView for: {url} ---")
    
    # We send a specific command that renderer.js will listen for.
    send_to_ui("webview_spawn", {
        "type": "webview",
        "title": title,
        "url": url
    })
    return f"Opening {title} in the interface."


def open_overlay(suggestions: list, target_app: str = "Notepad"):
    """
    Tells the Electron UI to spawn a separate, 
    transparent overlay window.
    """
    if not send_to_ui:
        print("--- [AppUtils] Error: send_to_ui not initialized. ---")
        return "Error: UI communication is not set up."

    print(f"--- [AppUtils] Spawning Overlay for: {target_app} ---")
    
    send_to_ui("overlay_spawn", {
        "type": "overlay",
        "title": f"ARGUS: {target_app}",
        "suggestions": suggestions
    })
    return "Overlay deployed."