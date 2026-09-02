import subprocess
import urllib.parse
from pathlib import Path
import webbrowser

# Browser Paths
brave_path = Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe")
chrome_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
msedge_path = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

spotify_path = Path(r"C:\Users\rohit\AppData\Roaming\Spotify\Spotify.exe")

# Website Dictionary
websites = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "facebook": "https://www.facebook.com",
    "reddit": "https://www.reddit.com",
    "spotify": "https://open.spotify.com"
}


def open_website(site):
    site = site.lower()

    if site in websites:
        from . import ui
        ui.assistant_message(f"Opening {site}...")
        webbrowser.open(websites[site])
    else:
        from . import ui
        ui.assistant_message("Website not found.")


def open_chrome():
    try:
        from . import ui

        if brave_path.exists():
            ui.assistant_message("Opening Brave Browser...")
            subprocess.Popen([str(brave_path)])

        elif chrome_path.exists():
            ui.assistant_message("Opening Google Chrome...")
            subprocess.Popen([str(chrome_path)])

        elif msedge_path.exists():
            ui.assistant_message("Opening Microsoft Edge...")
            subprocess.Popen([str(msedge_path)])

        else:
            ui.assistant_message("No browser found.")

    except Exception as err:
        from . import ui
        ui.assistant_message(str(err))


def open_youtube():
    open_website("youtube")


def open_youtube_search(query: str):
    query = str(query).strip()
    if not query:
        open_youtube()
        return

    query_text = urllib.parse.quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={query_text}"

    from . import ui
    ui.assistant_message(f"Searching YouTube for: {query}")
    webbrowser.open(url)


def open_spotify():
    try:
        from . import ui

        if spotify_path.exists():
            ui.assistant_message("Opening Spotify...")
            subprocess.Popen([str(spotify_path)])

        else:
            open_website("spotify")

    except Exception as err:
        from . import ui
        ui.assistant_message(str(err))


def google_search(query):
    query = query.replace(" ", "+")

    url = f"https://www.google.com/search?q={query}"

    from . import ui
    ui.assistant_message(f"Searching Google for: {query}")

    webbrowser.open(url)