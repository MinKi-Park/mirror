from __future__ import print_function
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from tkinter import *
from datetime import *
import datetime

class GoogleCalendar(Frame):
    def __init__(self, parent, *args, **kwargs) :
        Frame.__init__(self, parent, *args, **kwargs)
        self.config(bg='black')
        # Setup the Calendar API
        SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
        store = file.Storage('credentials.json')
        creds = store.get()
        if not creds or creds.invalid:
            flow = client.flow_from_clientsecrets('client_secret.json', SCOPES)
            creds = tools.run_flow(flow, store)
        service = build('calendar', 'v3', http=creds.authorize(Http()))

        yesterday = (datetime.datetime.utcnow()-timedelta(1)).isoformat() + 'Z' # 'Z' indicates UTC time
        morrow = (datetime.datetime.utcnow() + timedelta(1)).isoformat() + 'Z'
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='primary', timeMin=yesterday, timeMax=morrow,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
        for event in events:
            FONTSIZE = 8
            if datetime.datetime.today().strftime('%Y-%m-%d') == event['start'].get('dateTime', event['start'].get('date')) :
                FONTSIZE = 12
            label = ScheduleLine(self, event, FONTSIZE)
            label.pack(side=TOP, anchor=S)

class ScheduleLine(Frame):
    def __init__(self, parent, event, fontsize):
        Frame.__init__(self, parent, bg='black')

        self.eventConcat = event['start'].get('dateTime', event['start'].get('date')) + event['summary'] + event['description'] + event['location']
        self.eventLbl = Label(self, text=self.eventConcat, fg="white", bg="black", font=(None, fontsize))
        self.eventLbl.pack(side=LEFT, anchor=N)
