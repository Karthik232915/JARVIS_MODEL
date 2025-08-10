import os
import pickle
import datetime
import logging
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO)
SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('calendar', 'v3', credentials=creds)
    return service

def create_calendar_event(summary, start_time, duration_hours=1):
    service = get_calendar_service()
    start = start_time.isoformat()
    end = (start_time + datetime.timedelta(hours=duration_hours)).isoformat()
    event = {
        'summary': summary,
        'start': {'dateTime': start, 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end, 'timeZone': 'Asia/Kolkata'},
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    logging.info(f"Event created: {event.get('htmlLink')}")

if __name__ == "__main__":
    # Example: create event for tomorrow at 10 AM
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    event_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    create_calendar_event("Meeting", event_time, duration_hours=1)
