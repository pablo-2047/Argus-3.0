# core_utils/spotify_utils.py
"""
Spotify Integration for ARGUS
Full control: Play, pause, skip, volume, search, playlists

Requires: pip install spotipy
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging
import database

# === CONFIGURATION ===
SPOTIFY_SCOPE = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing,playlist-read-private"

def get_spotify_client():
    """
    Creates authenticated Spotify client.
    
    Setup (one-time):
    1. Go to: https://developer.spotify.com/dashboard
    2. Create an app
    3. Get Client ID and Secret
    4. Set Redirect URI: http://localhost:8888/callback
    5. Save credentials in database
    """
    client_id = database.load_profile_setting('SPOTIFY_CLIENT_ID')
    client_secret = database.load_profile_setting('SPOTIFY_CLIENT_SECRET')
    redirect_uri = 'http://localhost:8888/callback'
    
    if not client_id or not client_secret:
        return None, "Spotify not configured. Run setup first."
    
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=SPOTIFY_SCOPE,
            cache_path='.spotify_cache'
        ))
        return sp, None
    except Exception as e:
        return None, f"Spotify auth failed: {e}"


# === PLAYBACK CONTROL ===

def play_music(query: str = None):
    """
    Plays music. If query provided, searches and plays.
    Otherwise, resumes playback.
    
    Examples:
        play_music()  # Resume
        play_music("Bohemian Rhapsody")  # Search and play
        play_music("playlist chill vibes")  # Play playlist
    """
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        if query:
            # Search for track/album/playlist
            if 'playlist' in query.lower():
                # Search playlists
                playlist_name = query.lower().replace('playlist', '').strip()
                results = sp.search(q=playlist_name, type='playlist', limit=1)
                
                if results['playlists']['items']:
                    playlist = results['playlists']['items'][0]
                    sp.start_playback(context_uri=playlist['uri'])
                    return {
                        "success": True,
                        "action": "playing_playlist",
                        "name": playlist['name']
                    }
            else:
                # Search tracks
                results = sp.search(q=query, type='track', limit=1)
                
                if results['tracks']['items']:
                    track = results['tracks']['items'][0]
                    sp.start_playback(uris=[track['uri']])
                    return {
                        "success": True,
                        "action": "playing_track",
                        "name": track['name'],
                        "artist": track['artists'][0]['name']
                    }
            
            return {"error": f"No results found for '{query}'"}
        
        else:
            # Resume playback
            sp.start_playback()
            return {"success": True, "action": "resumed"}
    
    except spotipy.exceptions.SpotifyException as e:
        if 'NO_ACTIVE_DEVICE' in str(e):
            return {"error": "No active Spotify device. Open Spotify on your phone/PC first."}
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def pause_music():
    """Pauses current playback."""
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        sp.pause_playback()
        return {"success": True, "action": "paused"}
    except Exception as e:
        return {"error": str(e)}


def skip_track(direction='next'):
    """
    Skips to next or previous track.
    direction: 'next' or 'previous'
    """
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        if direction == 'next':
            sp.next_track()
        else:
            sp.previous_track()
        
        return {"success": True, "action": f"skipped_{direction}"}
    except Exception as e:
        return {"error": str(e)}


def set_volume(level: int):
    """
    Sets volume (0-100).
    """
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        level = max(0, min(100, level))  # Clamp 0-100
        sp.volume(level)
        return {"success": True, "volume": level}
    except Exception as e:
        return {"error": str(e)}


def get_current_track():
    """
    Gets currently playing track info.
    """
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        current = sp.current_playback()
        
        if not current or not current['is_playing']:
            return {"playing": False}
        
        track = current['item']
        return {
            "playing": True,
            "track": track['name'],
            "artist": track['artists'][0]['name'],
            "album": track['album']['name'],
            "progress_ms": current['progress_ms'],
            "duration_ms": track['duration_ms'],
            "volume": current['device']['volume_percent']
        }
    except Exception as e:
        return {"error": str(e)}


def shuffle(enable: bool = True):
    """Toggles shuffle mode."""
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        sp.shuffle(enable)
        return {"success": True, "shuffle": enable}
    except Exception as e:
        return {"error": str(e)}


def repeat(mode: str = 'context'):
    """
    Sets repeat mode.
    mode: 'track', 'context', 'off'
    """
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        sp.repeat(mode)
        return {"success": True, "repeat": mode}
    except Exception as e:
        return {"error": str(e)}


def get_user_playlists():
    """Gets user's playlists."""
    sp, error = get_spotify_client()
    if error:
        return {"error": error}
    
    try:
        playlists = sp.current_user_playlists(limit=50)
        return {
            "playlists": [
                {
                    "name": p['name'],
                    "tracks": p['tracks']['total'],
                    "uri": p['uri']
                }
                for p in playlists['items']
            ]
        }
    except Exception as e:
        return {"error": str(e)}


# === SMART FEATURES ===

def play_mood_music(mood: str):
    """
    Plays music based on mood.
    mood: 'happy', 'sad', 'energetic', 'chill', 'focus', 'sleep'
    """
    mood_playlists = {
        'happy': 'Happy Hits',
        'sad': 'Life Sucks',
        'energetic': 'Beast Mode',
        'chill': 'Chill Vibes',
        'focus': 'Deep Focus',
        'sleep': 'Peaceful Piano',
        'workout': 'Workout Motivation',
        'party': 'Party Hits'
    }
    
    playlist_query = mood_playlists.get(mood.lower(), mood)
    return play_music(f"playlist {playlist_query}")


def play_by_genre(genre: str):
    """
    Plays music by genre.
    genre: 'rock', 'pop', 'jazz', 'classical', 'hip hop', etc.
    """
    return play_music(f"{genre} music")


def smart_play(command: str):
    """
    Smart interpreter for natural language commands.
    
    Examples:
        "play something energetic" → play_mood_music('energetic')
        "play rock music" → play_by_genre('rock')
        "play bohemian rhapsody" → play_music('bohemian rhapsody')
    """
    command_lower = command.lower()
    
    # Mood detection
    moods = ['happy', 'sad', 'energetic', 'chill', 'focus', 'sleep', 'workout', 'party']
    for mood in moods:
        if mood in command_lower:
            return play_mood_music(mood)
    
    # Genre detection
    genres = ['rock', 'pop', 'jazz', 'classical', 'hip hop', 'rap', 'country', 'electronic', 'metal']
    for genre in genres:
        if genre in command_lower:
            return play_by_genre(genre)
    
    # Artist detection
    if 'by' in command_lower:
        # "play something by coldplay"
        artist = command_lower.split('by')[-1].strip()
        return play_music(artist)
    
    # Default: search for the query
    return play_music(command)


# === SETUP FUNCTION ===

def setup_spotify():
    """
    Interactive setup for Spotify credentials.
    """
    print("=== SPOTIFY SETUP ===")
    print("1. Go to: https://developer.spotify.com/dashboard")
    print("2. Create an app (any name)")
    print("3. Copy Client ID and Client Secret")
    print("4. In app settings, add Redirect URI: http://localhost:8888/callback")
    print()
    
    client_id = input("Enter Client ID: ").strip()
    client_secret = input("Enter Client Secret: ").strip()
    
    database.save_profile_setting('SPOTIFY_CLIENT_ID', client_id)
    database.save_profile_setting('SPOTIFY_CLIENT_SECRET', client_secret)
    
    print("\n✅ Spotify configured!")
    print("Now say: 'Argus, play some music'")
    print("\nFirst time will open browser for authorization. Click 'Agree'.")


# === TEST ===
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'setup':
        setup_spotify()
    else:
        print("Testing Spotify integration...")
        
        # Test current track
        current = get_current_track()
        print(f"Current track: {current}")
        
        # Test playlists
        playlists = get_user_playlists()
        print(f"Your playlists: {playlists}")