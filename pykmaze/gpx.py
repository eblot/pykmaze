#-----------------------------------------------------------------------------
# Communicate w/ a Decathlon Keymaze 500/700 devices
#-----------------------------------------------------------------------------
# @author Emmanuel Blot <manu.blot@gmail.com> (c) 2009
# @license MIT License, see LICENSE file
#-----------------------------------------------------------------------------

from pkg_resources import find_distributions
import os
import sys
import time
import xml.etree.ElementTree as ET


class GpxDoc(object):
    """Importer/Exporter for Topografix GPX file format
    """
    def __init__(self, name, startime):
        self.linestyles = {}
        self.root = ET.Element('gpx')
        self.root.set('version', '1.0')
        #path = get_module_path(sys.modules[__name__])
        #path = "./"
        #dist = find_distributions(path, only=True)
        #dist.get_metadata('PKG-INFO')
        #pykmaze_ver = get_pkginfo(core).get('version', VERSION)
        pykmaze_ver = "v1.0"
        self.root.set('creator', 
                      'PyKmaze %s - http://pykmaze.googlecode.com' % \
                      pykmaze_ver)
        self.root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        self.root.set('xmlns', 'http://www.topografix.com/GPX/1/0')
        self.root.set('xsi:schemaLocation', 
                      'http://www.topografix.com/GPX/1/0 '
                      'http://www.topografix.com/GPX/1/0/gpx.xsd')
        doctime = ET.SubElement(self.root, 'time')
        doctime.text = self._mktime(time.time())
        self._time = 10.0*startime
        self._bounds = { 'minlat' : 180.0,
                         'minlon' : 90.0,
                         'maxlat' : -180.0,
                         'maxlon' : -90.0 }
        self.track = ET.SubElement(self.root, 'trk')
        ET.SubElement(self.track, 'name').text = name
        ET.SubElement(self.track, 'number').text = '1'
    
    def _updateBounds(self, lat, lon):
        if lat < self._bounds['minlat']:
            self._bounds['minlat'] = lat
        if lat > self._bounds['maxlat']:
            self._bounds['maxlat'] = lat
        if lon < self._bounds['minlon']:
            self._bounds['minlon'] = lon
        if lon > self._bounds['maxlon']:
            self._bounds['maxlon'] = lon
    
    @classmethod
    def _mktime(cls, timestamp):
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp))

    def add_trackpoints(self, trackpoint, zoffset=0, extrude=True, 
                        tessellate=True):
        if isinstance(trackpoint, tuple):
            trackpoint = [trackpoint]
        segment = ET.SubElement(self.track, 'trkseg')
        for tp in trackpoint:
            trkpt = ET.SubElement(segment, 'trkpt')
            trkpt.set('lat', str(tp[0]))
            trkpt.set('lon', str(tp[1]))
            ET.SubElement(trkpt, 'ele').text = str(float(tp[2]+zoffset))
            self._time += tp[5]
            curtime = int(self._time//10)
            ET.SubElement(trkpt, 'time').text = self._mktime(curtime)
            ET.SubElement(trkpt, 'sym').text = 'Waypoint'
            self._updateBounds(tp[0], tp[1])
            
    def write(self, out):
        out.write('<?xml version="1.0" encoding="UTF-8"?>')
        bounds = ET.SubElement(self.root, 'bounds')
        for b in self._bounds:
            bounds.set(b, str(self._bounds[b]))
        out.write(ET.tostring(self.root))

