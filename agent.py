from dotenv import load_dotenv
from prompt import AGENT_INSTRUCTION, AGENT_RESPONSE

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext
from livekit.agents.llm import ToolError
from livekit.plugins import google, noise_cancellation
import datetime
import os
import shutil
import subprocess
import sys
import logging
from pathlib import Path
import googleapiclient.discovery
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import requests
import json
import webbrowser

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'  # Path to Google API credentials JSON
TOKEN_FILE = 'token.pickle'  # Stores OAuth tokens

def get_calendar_service():
    """Initialize Google Calendar API service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
    return googleapiclient.discovery.build('calendar', 'v3', credentials=creds)

# Spotify API setup
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_BASE = 'https://api.spotify.com/v1'

def get_spotify_access_token():
    """Get Spotify access token using client credentials."""
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ToolError("Spotify client ID or secret not set in environment variables.")
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    response = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise ToolError(f"Failed to get Spotify access token: {response.text}")

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=AGENT_INSTRUCTION)

    @function_tool()
    async def get_current_datetime(self, context: RunContext) -> str:
        """Get the current date, time, month, and year."""
        try:
            now = datetime.datetime.now()
            formatted_datetime = now.strftime("%Y-%m-%d %H:%M:%S (Month: %B, Year: %Y)")
            logger.info(f"Retrieved current datetime: {formatted_datetime}")
            return formatted_datetime
        except Exception as e:
            logger.error(f"Failed to get datetime: {str(e)}")
            raise ToolError(f"Failed to get datetime: {str(e)}")

    @function_tool()
    async def open_application(self, context: RunContext, app_name: str) -> str:
        """Open an installed application on the computer by name."""
        try:
            if sys.platform == 'darwin':  # macOS
                app_map = {
                    'brave': 'Brave Browser',
                    'canva': 'Canva',
                    'whatsapp': 'WhatsApp',
                    'vscode': 'Visual Studio Code',
                    'spotify': 'Spotify',
                    'adobe premiere pro': 'Adobe Premiere Pro 2020',
                    'adobe photoshop': 'Adobe Photoshop CC 2019',
                    'adobe illustrator': 'Adobe Illustrator 2022',
                    'davinci resolve': 'DaVinci Resolve',
                    'adobe after effects': 'Adobe After Effects 2020',
                    'cursor': 'Cursor',
                }
                executable = app_map.get(app_name.lower(), app_name)
                subprocess.Popen(['open', '-a', executable])
                logger.info(f"Opened application {app_name} on macOS")
                return f"Successfully opened {app_name}."
            elif sys.platform == 'win32':  # Windows
                app_map = {
                    'notepad': 'notepad.exe',
                    'calculator': 'calc.exe',
                    'brave': r'"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"',
                    'canva': r'"C:\Users\%USERNAME%\AppData\Local\Programs\Canva\Canva.exe"',
                    'whatsapp': r'"C:\Users\%USERNAME%\AppData\Local\WhatsApp\WhatsApp.exe"',
                    'vscode': r'"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe"',
                    'spotify': r'"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe"',
                    'adobe premiere pro': r'"C:\Program Files\Adobe\Adobe Premiere Pro 2020\Adobe Premiere Pro.exe"',
                    'adobe photoshop': r'"C:\Program Files\Adobe\Adobe Photoshop CC 2019\Photoshop.exe"',
                    'adobe illustrator': r'"C:\Program Files\Adobe\Adobe Illustrator 2022\Support Files\Contents\Windows\Illustrator.exe"',
                    'davinci resolve': r'"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"',
                    'adobe after effects': r'"C:\Program Files\Adobe\Adobe After Effects 2020\Support Files\AfterFX.exe"',
                    'cursor': r'"C:\Users\%USERNAME%\AppData\Local\Programs\Cursor\Cursor.exe"',
                }
                executable = app_map.get(app_name.lower(), app_name)
                subprocess.Popen(executable, shell=True)
                logger.info(f"Opened application {app_name} on Windows")
                return f"Successfully opened {app_name}."
            else:  # Linux/other
                app_map = {
                    'brave': 'brave-browser',
                    'canva': 'canva',
                    'whatsapp': 'whatsapp-for-linux',
                    'vscode': 'code',
                    'spotify': 'spotify',
                    'adobe premiere pro': 'adobe-premiere-pro',
                    'adobe photoshop': 'adobe-photoshop',
                    'adobe illustrator': 'adobe-illustrator',
                    'davinci resolve': 'davinci-resolve',
                    'adobe after effects': 'adobe-after-effects',
                    'cursor': 'cursor',
                }
                executable = app_map.get(app_name.lower(), app_name)
                subprocess.Popen([executable])
                logger.info(f"Opened application {app_name} on Linux/other")
                return f"Successfully opened {app_name}."
        except Exception as e:
            logger.error(f"Failed to open {app_name}: {str(e)}")
            raise ToolError(f"Failed to open {app_name}: {str(e)}")

    @function_tool()
    async def open_brave_url(self, context: RunContext, url: str) -> str:
        """Open a specific URL in Brave browser."""
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', '-a', 'Brave Browser', url])
            elif sys.platform == 'win32':
                brave_path = r'"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"'
                subprocess.Popen(f'{brave_path} {url}', shell=True)
            else:  # Linux/other
                subprocess.Popen(['brave-browser', url])
            logger.info(f"Opened URL {url} in Brave")
            return f"Successfully opened {url} in Brave."
        except Exception as e:
            logger.error(f"Failed to open URL {url} in Brave: {str(e)}")
            raise ToolError(f"Failed to open URL {url} in Brave: {str(e)}")

    @function_tool()
    async def create_directory(self, context: RunContext, path: str) -> str:
        """Create a new folder (directory) at the specified path."""
        try:
            path_obj = Path(path)
            if path_obj.exists():
                logger.info(f"Directory {path} already exists")
                return f"Directory {path} already exists."
            path_obj.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory at {path}")
            return f"Successfully created directory at {path}."
        except PermissionError:
            logger.error(f"Permission denied: Cannot create directory at {path}")
            raise ToolError(f"Permission denied: Cannot create directory at {path}.")
        except Exception as e:
            logger.error(f"Failed to create directory at {path}: {str(e)}")
            raise ToolError(f"Failed to create directory at {path}: {str(e)}")

    @function_tool()
    async def rename_directory(self, context: RunContext, old_path: str, new_name: str) -> str:
        """Rename a folder (directory) from old_path to new_name. new_name should be the new folder name (not a full path)."""
        try:
            old_path_obj = Path(old_path)
            if not old_path_obj.exists():
                logger.error(f"Directory {old_path} does not exist")
                raise ToolError(f"Directory {old_path} does not exist.")
            if not old_path_obj.is_dir():
                logger.error(f"Path {old_path} is not a directory")
                raise ToolError(f"Path {old_path} is not a directory.")
            new_path_obj = old_path_obj.parent / new_name
            if new_path_obj.exists():
                logger.error(f"Directory {new_path_obj} already exists")
                raise ToolError(f"Directory {new_path_obj} already exists.")
            old_path_obj.rename(new_path_obj)
            logger.info(f"Renamed directory from {old_path} to {new_path_obj}")
            return f"Successfully renamed directory from {old_path} to {new_path_obj}."
        except PermissionError:
            logger.error(f"Permission denied: Cannot rename directory {old_path} to {new_name}")
            raise ToolError(f"Permission denied: Cannot rename directory {old_path} to {new_name}.")
        except Exception as e:
            logger.error(f"Failed to rename directory from {old_path} to {new_name}: {str(e)}")
            raise ToolError(f"Failed to rename directory from {old_path} to {new_name}: {str(e)}")

    @function_tool()
    async def delete_file(self, context: RunContext, path: str) -> str:
        """Delete a file at the specified path."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                logger.error(f"File {path} does not exist")
                raise ToolError(f"File {path} does not exist.")
            if not path_obj.is_file():
                logger.error(f"Path {path} is not a file")
                raise ToolError(f"Path {path} is not a file.")
            path_obj.unlink()
            logger.info(f"Deleted file at {path}")
            return f"Successfully deleted file at {path}."
        except PermissionError:
            logger.error(f"Permission denied: Cannot delete file at {path}")
            raise ToolError(f"Permission denied: Cannot delete file at {path}.")
        except Exception as e:
            logger.error(f"Failed to delete file at {path}: {str(e)}")
            raise ToolError(f"Failed to delete file at {path}: {str(e)}")

    @function_tool()
    async def delete_directory(self, context: RunContext, path: str) -> str:
        """Delete a folder (directory) at the specified path."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                logger.error(f"Directory {path} does not exist")
                raise ToolError(f"Directory {path} does not exist.")
            if not path_obj.is_dir():
                logger.error(f"Path {path} is not a directory")
                raise ToolError(f"Path {path} is not a directory.")
            shutil.rmtree(path_obj)
            logger.info(f"Deleted directory at {path}")
            return f"Successfully deleted directory at {path}."
        except PermissionError:
            logger.error(f"Permission denied: Cannot delete directory at {path}")
            raise ToolError(f"Permission denied: Cannot delete directory at {path}.")
        except Exception as e:
            logger.error(f"Failed to delete directory at {path}: {str(e)}")
            raise ToolError(f"Failed to delete directory at {path}: {str(e)}")

    @function_tool()
    async def locate_file_or_folder(self, context: RunContext, name: str) -> str:
        """Locate a file or folder by name on the computer."""
        try:
            search_paths = [
                Path.home(),  # User's home directory
                Path.home() / 'Documents',
                Path.home() / 'Downloads',
                Path.home() / 'Desktop',
            ]
            found_paths = []
            for search_path in search_paths:
                for root, dirs, files in os.walk(search_path):
                    if name in dirs or name in files:
                        found_paths.append(str(Path(root) / name))
            if not found_paths:
                logger.info(f"No file or folder named {name} found")
                return f"No file or folder named {name} found."
            logger.info(f"Found {name} at: {', '.join(found_paths)}")
            return f"Found {name} at: {', '.join(found_paths)}."
        except Exception as e:
            logger.error(f"Failed to locate {name}: {str(e)}")
            raise ToolError(f"Failed to locate {name}: {str(e)}")

    @function_tool()
    async def spotify_control(self, context: RunContext, action: str) -> str:
        """Control Spotify with actions: play, pause, next, previous."""
        try:
            access_token = get_spotify_access_token()
            headers = {'Authorization': f'Bearer {access_token}'}
            if action.lower() == 'play':
                response = requests.put(f'{SPOTIFY_API_BASE}/me/player/play', headers=headers)
            elif action.lower() == 'pause':
                response = requests.put(f'{SPOTIFY_API_BASE}/me/player/pause', headers=headers)
            elif action.lower() == 'next':
                response = requests.post(f'{SPOTIFY_API_BASE}/me/player/next', headers=headers)
            elif action.lower() == 'previous':
                response = requests.post(f'{SPOTIFY_API_BASE}/me/player/previous', headers=headers)
            else:
                logger.error(f"Invalid Spotify action: {action}")
                raise ToolError(f"Invalid Spotify action: {action}")
            if response.status_code in [200, 204]:
                logger.info(f"Spotify action {action} executed successfully")
                return f"Spotify action {action} executed successfully."
            else:
                logger.error(f"Failed to execute Spotify action {action}: {response.text}")
                raise ToolError(f"Failed to execute Spotify action {action}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to execute Spotify action {action}: {str(e)}")
            raise ToolError(f"Failed to execute Spotify action {action}: {str(e)}")

    @function_tool()
    async def spotify_search_and_play(self, context: RunContext, song_name: str) -> str:
        """Search for a song on Spotify and play it."""
        try:
            access_token = get_spotify_access_token()
            headers = {'Authorization': f'Bearer {access_token}'}
            params = {'q': song_name, 'type': 'track', 'limit': 1}
            response = requests.get(f'{SPOTIFY_API_BASE}/search', headers=headers, params=params)
            if response.status_code == 200:
                tracks = response.json().get('tracks', {}).get('items', [])
                if not tracks:
                    logger.info(f"No tracks found for {song_name}")
                    return f"No tracks found for {song_name}."
                track_uri = tracks[0]['uri']
                play_response = requests.put(
                    f'{SPOTIFY_API_BASE}/me/player/play',
                    headers=headers,
                    json={'uris': [track_uri]}
                )
                if play_response.status_code in [200, 204]:
                    logger.info(f"Playing song {song_name} on Spotify")
                    return f"Playing song {song_name} on Spotify."
                else:
                    logger.error(f"Failed to play song {song_name}: {play_response.text}")
                    raise ToolError(f"Failed to play song {song_name}: {play_response.text}")
            else:
                logger.error(f"Failed to search for song {song_name}: {response.text}")
                raise ToolError(f"Failed to search for song {song_name}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to search and play song {song_name}: {str(e)}")
            raise ToolError(f"Failed to search and play song {song_name}: {str(e)}")

    @function_tool()
    async def create_calendar_event(self, context: RunContext, summary: str, start_time: str, end_time: str, description: str = '') -> str:
        """Create a Google Calendar event."""
        try:
            service = get_calendar_service()
            event = {
                'summary': summary,
                'description': description,
                'start': {'dateTime': start_time, 'timeZone': 'UTC'},
                'end': {'dateTime': end_time, 'timeZone': 'UTC'},
            }
            event_result = service.events().insert(calendarId='primary', body=event).execute()
            logger.info(f"Created calendar event: {summary}")
            return f"Successfully created event: {event_result['summary']} (ID: {event_result['id']})"
        except Exception as e:
            logger.error(f"Failed to create calendar event {summary}: {str(e)}")
            raise ToolError(f"Failed to create calendar event {summary}: {str(e)}")

    @function_tool()
    async def delete_calendar_event(self, context: RunContext, event_id: str) -> str:
        """Delete a Google Calendar event by ID."""
        try:
            service = get_calendar_service()
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            logger.info(f"Deleted calendar event with ID: {event_id}")
            return f"Successfully deleted calendar event with ID: {event_id}."
        except Exception as e:
            logger.error(f"Failed to delete calendar event with ID {event_id}: {str(e)}")
            raise ToolError(f"Failed to delete calendar event with ID {event_id}: {str(e)}")

async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        llm=google.beta.realtime.RealtimeModel(
            model="gemini-2.0-flash-exp",
            voice="Puck",
            temperature=0.8,
            instructions=AGENT_INSTRUCTION,
        ),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.generate_reply(
        instructions=AGENT_RESPONSE
    )

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))