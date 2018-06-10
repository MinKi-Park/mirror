import sys
import math
from PIL import ImageTk
import PIL.Image
import tkinter as tk
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

WIDTH = 800
HEIGHT = 500

LATITUDE = 37.5111999512
LONGITUDE = 126.974098206
ZOOM = 15
MAPTYPE = 'satellite'

class UI(tk.Tk):

    def __init__(self):

        tk.Tk.__init__(self)

        self.geometry('%dx%d+500+500' % (WIDTH,HEIGHT))
        self.title('GooMPy')

        self.canvas = tk.Canvas(self, width=WIDTH, height=HEIGHT)

        self.canvas.pack()

        self.bind("<Key>", self.check_quit)
        self.bind('<B1-Motion>', self.drag)
        self.bind('<Button-1>', self.click)

        self.label = tk.Label(self.canvas)

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

    def check_quit(self, event):

        if ord(event.char) == 27: # ESC
            exit(0)

UI().mainloop()