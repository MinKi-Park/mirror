from tkinter import *
import locale
import threading
import traceback
import feedparser
import sys
import math
import calendarManipulated
import googleCalendar

from PIL import Image, ImageTk
from contextlib import contextmanager

import PIL.Image
from io import BytesIO
if sys.version_info[0] == 2:
    import urllib
    urlopen = urllib.urlopen
else:
    import urllib.request
    urlopen = urllib.request.urlopen
import os
import time
try:
    from key import _KEY
except:
    _KEY = ''

_EARTHPIX = 268435456  # Number of pixels in half the earth's circumference at zoom = 21
_DEGREE_PRECISION = 4  # Number of decimal places for rounding coordinates
_TILESIZE = 640  # Larget tile we can grab without paying
_GRABRATE = 4  # Fastest rate at which we can download tiles without paying

_pixrad = _EARTHPIX / math.pi

WIDTH = 800
HEIGHT = 500

LATITUDE = 37.5111999512
LONGITUDE = 126.974098206
ZOOM = 15
MAPTYPE = 'roadmap'

LOCALE_LOCK = threading.Lock()

ui_locale = '' # e.g. 'fr_FR' fro French, '' as default
time_format = 12 # 12 or 24
date_format = "%b %d, %Y" # check python doc for strftime() for options
news_country_code = 'kr'
weather_api_token = '<TOKEN>' # create account at https://darksky.net/dev/
weather_lang = 'en' # see https://darksky.net/dev/docs/forecast for full list of language parameters values
weather_unit = 'us' # see https://darksky.net/dev/docs/forecast for full list of unit parameters values
latitude = None # Set this if IP location lookup does not work for you (must be a string)
longitude = None # Set this if IP location lookup does not work for you (must be a string)
xlarge_text_size = 94
large_text_size = 48
medium_text_size = 28
small_text_size = 18

def _new_image(width, height):
    return PIL.Image.new('RGB', (width, height))


def _roundto(value, digits):
    return int(value * 10 ** digits) / 10. ** digits


def _pixels_to_degrees(pixels, zoom):
    return pixels * 2 ** (21 - zoom)


def _grab_tile(lat, lon, zoom, maptype, _TILESIZE, sleeptime):
    urlbase = 'https://maps.googleapis.com/maps/api/staticmap?center=%f,%f&zoom=%d&maptype=%s&size=%dx%d&format=jpg'
    urlbase += _KEY

    specs = lat, lon, zoom, maptype, _TILESIZE, _TILESIZE

    filename = 'mapscache/' + ('%f_%f_%d_%s_%d_%d' % specs) + '.jpg'

    tile = None

    if os.path.isfile(filename):
        tile = PIL.Image.open(filename)

    else:
        url = urlbase % specs

        result = urlopen(url).read()
        tile = PIL.Image.open(BytesIO(result))
        if not os.path.exists('mapscache'):
            os.mkdir('mapscache')
        tile.save(filename)
        time.sleep(sleeptime)  # Choke back speed to avoid maxing out limit

    return tile


def _pix_to_lon(j, lonpix, ntiles, _TILESIZE, zoom):
    return math.degrees((lonpix + _pixels_to_degrees(((j) - ntiles / 2) * _TILESIZE, zoom) - _EARTHPIX) / _pixrad)


def _pix_to_lat(k, latpix, ntiles, _TILESIZE, zoom):
    return math.degrees(math.pi / 2 - 2 * math.atan(
        math.exp(((latpix + _pixels_to_degrees((k - ntiles / 2) * _TILESIZE, zoom)) - _EARTHPIX) / _pixrad)))


def fetchTiles(latitude, longitude, zoom, maptype, radius_meters=None, default_ntiles=4):
    latitude = _roundto(latitude, _DEGREE_PRECISION)
    longitude = _roundto(longitude, _DEGREE_PRECISION)

    # https://groups.google.com/forum/#!topic/google-maps-js-api-v3/hDRO4oHVSeM
    pixels_per_meter = 2 ** zoom / (156543.03392 * math.cos(math.radians(latitude)))

    # number of tiles required to go from center latitude to desired radius in meters
    ntiles = default_ntiles if radius_meters is None else int(
        round(2 * pixels_per_meter / (_TILESIZE / 2. / radius_meters)))

    lonpix = _EARTHPIX + longitude * math.radians(_pixrad)

    sinlat = math.sin(math.radians(latitude))
    latpix = _EARTHPIX - _pixrad * math.log((1 + sinlat) / (1 - sinlat)) / 2

    bigsize = ntiles * _TILESIZE
    bigimage = _new_image(bigsize, bigsize)

    for j in range(ntiles):
        lon = _pix_to_lon(j, lonpix, ntiles, _TILESIZE, zoom)
        for k in range(ntiles):
            lat = _pix_to_lat(k, latpix, ntiles, _TILESIZE, zoom)
            tile = _grab_tile(lat, lon, zoom, maptype, _TILESIZE, 1. / _GRABRATE)
            bigimage.paste(tile, (j * _TILESIZE, k * _TILESIZE))

    west = _pix_to_lon(0, lonpix, ntiles, _TILESIZE, zoom)
    east = _pix_to_lon(ntiles - 1, lonpix, ntiles, _TILESIZE, zoom)

    north = _pix_to_lat(0, latpix, ntiles, _TILESIZE, zoom)
    south = _pix_to_lat(ntiles - 1, latpix, ntiles, _TILESIZE, zoom)

    return bigimage, (north, west), (south, east)


class GooMPy(object):

    def __init__(self, width, height, latitude, longitude, zoom, maptype, radius_meters=None, default_ntiles=4):
        self.lat = latitude
        self.lon = longitude

        self.width = width
        self.height = height

        self.zoom = zoom
        self.maptype = maptype
        self.radius_meters = radius_meters

        self.winimage = _new_image(self.width, self.height)

        self._fetch()

        halfsize = int(self.bigimage.size[0] / 2)
        self.leftx = halfsize
        self.uppery = halfsize

        self._update()

    def getImage(self):
        return self.winimage

    def move(self, dx, dy):
        self.leftx = self._constrain(self.leftx, dx, self.width)
        self.uppery = self._constrain(self.uppery, dy, self.height)
        self._update()

    def _fetch_and_update(self):
        self._fetch()
        self._update()

    def _fetch(self):
        self.bigimage, self.northwest, self.southeast = fetchTiles(self.lat, self.lon, self.zoom, self.maptype,
                                                                   self.radius_meters)

    def _update(self):
        self.winimage.paste(self.bigimage, (-self.leftx, -self.uppery))

    def _constrain(self, oldval, diff, dimsize):
        newval = oldval + diff
        return newval if newval > 0 and newval < self.bigimage.size[0] - dimsize else oldval


@contextmanager
def setlocale(name): #thread proof function to work with locale
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)

icon_lookup = {
    'clear-day': "assets/Sun.png",  # clear sky day
    'wind': "assets/Wind.png",   #wind
    'cloudy': "assets/Cloud.png",  # cloudy day
    'partly-cloudy-day': "assets/PartlySunny.png",  # partly cloudy day
    'rain': "assets/Rain.png",  # rain day
    'snow': "assets/Snow.png",  # snow day
    'snow-thin': "assets/Snow.png",  # sleet day
    'fog': "assets/Haze.png",  # fog day
    'clear-night': "assets/Moon.png",  # clear sky night
    'partly-cloudy-night': "assets/PartlyMoon.png",  # scattered clouds night
    'thunderstorm': "assets/Storm.png",  # thunderstorm
    'tornado': "assests/Tornado.png",    # tornado
    'hail': "assests/Hail.png"  # hail
}

class Clock(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')
        # initialize time label
        self.time1 = ''
        self.timeLbl = Label(self, font=('Helvetica', large_text_size), fg="white", bg="black")
        self.timeLbl.pack(side=TOP, anchor=E)
        # initialize day of week
        self.day_of_week1 = ''
        self.dayOWLbl = Label(self, text=self.day_of_week1, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.dayOWLbl.pack(side=TOP, anchor=E)
        # initialize date label
        self.date1 = ''
        self.dateLbl = Label(self, text=self.date1, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.dateLbl.pack(side=TOP, anchor=E)
        self.tick()

    def tick(self):
        with setlocale(ui_locale):
            if time_format == 12:
                time2 = time.strftime('%I:%M %p') #hour in 12h format
            else:
                time2 = time.strftime('%H:%M') #hour in 24h format

            day_of_week2 = time.strftime('%A')
            date2 = time.strftime(date_format)
            # if time string has changed, update it
            if time2 != self.time1:
                self.time1 = time2
                self.timeLbl.config(text=time2)
            if day_of_week2 != self.day_of_week1:
                self.day_of_week1 = day_of_week2
                self.dayOWLbl.config(text=day_of_week2)
            if date2 != self.date1:
                self.date1 = date2
                self.dateLbl.config(text=date2)
            # calls itself every 200 milliseconds
            # to update the time display as needed
            # could use >200 ms, but display gets jerky
            self.timeLbl.after(200, self.tick)

class News(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, *args, **kwargs)
        self.config(bg='black')
        self.title = 'News' # 'News' is more internationally generic
        self.newsLbl = Label(self, text=self.title, font=('Helvetica', medium_text_size), fg="white", bg="black")
        self.newsLbl.pack(side=TOP, anchor=W)
        self.headlinesContainer = Frame(self, bg="black")
        self.headlinesContainer.pack(side=TOP)
        self.get_headlines()

    def get_headlines(self):
        try:
            # remove all children
            for widget in self.headlinesContainer.winfo_children():
                widget.destroy()
            if news_country_code == None:
                headlines_url = "https://news.google.com/news?ned=us&output=rss"
                #headlines_url = "https://news.google.com/gn/news/rss/?ned=kr&gl=KR&hl=ko"
            else:
                headlines_url = "https://news.google.com/news?ned=%s&output=rss" % news_country_code
                #headlines_url = "https://news.google.com/gn/news/rss/?ned=%s&gl=KR&hl=ko" % news_country_code

            feed = feedparser.parse(headlines_url)

            for post in feed.entries[0:5]:
                headline = NewsHeadline(self.headlinesContainer, post.title)
                headline.pack(side=TOP, anchor=W)
        except Exception as e:
            traceback.print_exc()
            print ("Error: %s. Cannot get news." % e)

        self.after(600000, self.get_headlines)

class NewsHeadline(Frame):
    def __init__(self, parent, event_name=""):
        Frame.__init__(self, parent, bg='black')

        image = Image.open("assets/Newspaper.png")
        image = image.resize((25, 25), Image.ANTIALIAS)
        image = image.convert('RGB')
        photo = ImageTk.PhotoImage(image)

        self.iconLbl = Label(self, bg='black', image=photo)
        self.iconLbl.image = photo
        self.iconLbl.pack(side=LEFT, anchor=N)

        self.eventName = event_name
        self.eventNameLbl = Label(self, text=self.eventName, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.eventNameLbl.pack(side=LEFT, anchor=N)

class Calendar(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, bg='black')
        self.title = 'Calendar Events'
        self.calendarLbl = Label(self, text=self.title, font=('Helvetica', medium_text_size), fg="white", bg="black")
        self.calendarLbl.pack(side=TOP, anchor=E)
        self.calendarEventContainer = Frame(self, bg='black')
        self.calendarEventContainer.pack(side=TOP, anchor=E)
        self.get_events()

    def get_events(self):
        #TODO: implement this method
        # reference https://developers.google.com/google-apps/calendar/quickstart/python

        # remove all children
        for widget in self.calendarEventContainer.winfo_children():
            widget.destroy()

        calendar_event = CalendarEvent(self.calendarEventContainer)
        calendar_event.pack(side=TOP, anchor=E)
        pass

class CalendarEvent(Frame):
    def __init__(self, parent, event_name="Event 1"):
        Frame.__init__(self, parent, bg='black')
        self.eventName = event_name
        self.eventNameLbl = Label(self, text=self.eventName, font=('Helvetica', small_text_size), fg="white", bg="black")
        self.eventNameLbl.pack(side=TOP, anchor=E)

class MapView(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent, bg='black')

        self.canvas = Canvas(self, width=WIDTH, height=HEIGHT)

        self.canvas.pack()

        self.bind('<B1-Motion>', self.drag)
        self.bind('<Button-1>', self.click)

        self.label = Label(self.canvas)

        self.zoomlevel = ZOOM

        self.goompy = GooMPy(WIDTH, HEIGHT, LATITUDE, LONGITUDE, ZOOM, MAPTYPE)

        self.restart()

    def reload(self):

        self.coords = None
        self.redraw()

        self['cursor']  = ''

    def restart(self):

        # A little trick to get a watch cursor along with loading
        self['cursor']  = 'watch'
        self.after(1, self.reload)

    def click(self, event):

        self.coords = event.x, event.y

    def drag(self, event):

        self.goompy.move(self.coords[0]-event.x, self.coords[1]-event.y)
        self.image = self.goompy.getImage()
        self.redraw()
        self.coords = event.x, event.y

    def redraw(self):

        self.image = self.goompy.getImage()
        self.image_tk = ImageTk.PhotoImage(self.image)
        self.label['image'] = self.image_tk

        self.label.place(x=0, y=0, width=WIDTH, height=HEIGHT)

        x = int(self.canvas['width']) - 50
        y = int(self.canvas['height']) - 80

class FullscreenWindow:
    MAPEXISTS = False

    def __init__(self):
        self.tk = Tk()
        self.tk.configure(background='black')
        self.topFrameLeft = Frame(self.tk, background='black', width=300, height=300)
        self.topFrameLeft.pack(fill=X, side=LEFT, anchor=NW)
        self.topFrameRight = Frame(self.tk, background='black', width=300, height=300)
        self.topFrameRight.pack(fill=X, side=RIGHT, anchor=NE)
        self.topFrame = Frame(self.tk, background='black')
        self.topFrame.pack(fill=X)

        self.bottomFrame = Frame(self.tk, background='black')
        self.bottomFrame.pack(fill=BOTH, expand = YES)

        self.state = True
        self.tk.attributes("-fullscreen", self.state)
        self.tk.bind("<Return>", self.toggle_fullscreen)
        self.tk.bind("<Escape>", self.end_fullscreen)
        # clock
        self.clock = Clock(self.topFrameRight)
        self.clock.pack(side=RIGHT, anchor=NE, padx=30, pady=30)
        # weather
##        self.weather = Weather(self.topFrame)
##        self.weather.pack(side=LEFT, anchor=N, padx=100, pady=60)
        # news
        self.news = News(self.topFrame)
        self.news.pack(side=TOP, anchor=N, pady=30)
        # calender - removing for now
        self.cal = calendarManipulated.Calendar(self.topFrameLeft, firstweekday=calendarManipulated.calendar.SUNDAY)
        self.cal.pack(side=TOP, anchor=NW, padx=30, pady=30)
        # googleCalendar
        self.schedule = googleCalendar.GoogleCalendar(self.bottomFrame)
        self.schedule.pack(side=BOTTOM, anchor=S, padx=30, pady=30)
        # mapview
        self.button = Button(self.bottomFrame, text="expand a map", command=self.expandMap)
        self.button.pack(side=LEFT, anchor=E, padx=100, pady=60)

    def expandMap(self):
        if self.MAPEXISTS is False :
            self.mapview = MapView(self.bottomFrame)
            self.mapview.pack(side=BOTTOM, anchor=S, padx=100, pady=60)
            self.MAPEXISTS = True
        else :
            self.mapview.pack_forget()
            self.MAPEXISTS = False

    def toggle_fullscreen(self, event=None):
        self.state = self.state  # Just toggling the boolean
        self.tk.attributes("-fullscreen", self.state)
        return "break"

    def end_fullscreen(self, event=None):
        self.state = False
        self.tk.attributes("-fullscreen", False)
        return "break"

if __name__ == '__main__':
    w = FullscreenWindow()
    w.tk.mainloop()
