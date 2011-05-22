#!/usr/bin/env python

#-----------------------------------------------------------------------------
# Communicate w/ a Decathlon Keymaze 500/700 devices
#-----------------------------------------------------------------------------
# @author Emmanuel Blot <manu.blot@gmail.com> (c) 2009
# @license MIT License, see LICENSE file
#-----------------------------------------------------------------------------

from __future__ import with_statement
from optparse import OptionParser
from db import KeymazeCache
from keymaze import KeymazePort
import datetime
import logging
import math
import os
import re
import time
import sys

def show_trackpoints_catalog(cat):
    sorted_cat = list(cat)
    sorted_cat.sort(key=lambda e: e['id'])
    print " #   Day         Start  End    Duration  Distance  AltMin   AltMax"
    for tpent in sorted_cat:
        stime = time.localtime(tpent['start'])
        print ' %02d  %s  %s  %s    %s  %6.2fkm %s  %s' % \
            (tpent['id']+1,
             time.strftime('%Y-%m-%d', stime),
             time.strftime('%H:%M', stime),
             time.strftime('%H:%M', 
                           time.localtime(tpent['start']+tpent['time'])),
             tpent['duration'] and \
                time.strftime('%Hh%Mm', 
                              time.localtime(tpent['duration']-3600)) or
                '     -',
             tpent['distance']/1000.0,
             tpent['altmin'] and '%6dm' % tpent['altmin'] or '      -', 
             tpent['altmax'] and '%6dm' % tpent['altmax'] or '      -')

def parse_trim(trim_times):
    tcre = re.compile(r'^(?P<r>[+-])?'
                      r'(?:(?P<h>\d\d):(?=\d\d:))?'
                      r'(?:(?P<m>\d\d):)?'
                      r'(?P<s>\d\d)$')
    values = []
    for trim in trim_times:
        mo = tcre.match(trim)
        if not mo:
            raise AssertionError('Invalid trim format "%s"' % trim)
        seconds = 60*int(mo.group('h') or 0)
        seconds = 60*(seconds + int(mo.group('m') or 0))
        seconds += int(mo.group('s') or 0)
        values.append((mo.group('r'), seconds))
    return values

def trim_trackpoints(track, tp, trims):
    if not trims:
        return tp
    start = track['start']
    end = start + track['time']
    if len(trims) > 1:
        tstart = trims[0]
        tend = trims[1]
    else:
        tstart = trims[0]
        tend = ('', 0)
    if tstart[0] == '+':
        t_start = start+tstart[1]
    elif tstart[0] == '-':
        t_start = end-tstart[1]
    else:
        # not yet implemented
        t_start = start
    if tend[0] == '+':
        t_end = start+tend[1]
    elif tend[0] == '-':
        t_end = end-tend[1]
    else:
        # not yet implemented
        t_end = end
    ttp = []
    pt = start*10
    t_start *= 10
    t_end *= 10
    for p in tp:
        pt += p[-1] # delta
        if t_start <= pt <= t_end:
            ttp.append(p)
    return ttp
    
def haversine(pt1, pt2):
    (lat1, lon1) = map(math.radians, pt1[0:2])
    (lat2, lon2) = map(math.radians, pt2[0:2])
    R = 6371.0*1000 # m
    # Mean radius        6,371.0 km
    # Equatorial radius  6,378.1 km
    # Polar radius       6,356.8 km
    dlat = lat2-lat1
    dlon = lon2-lon1 
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2) * math.sin(dlon/2) 
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) 
    d = R * c
    return d
    
def cartesian(point):
    lat = math.radians(point[0])
    lon = math.radians(point[1])
    R = 6371.0*1000 # m
    h = R + point[2]
    x = h * math.cos(lat) * math.cos(lon)
    y = h * math.cos(lat) * math.sin(lon)
    z = h * math.sin(lat)
    return (x,y,z)

def dotproduct(a,b):
    return sum((a[0]*b[0],a[1]*b[1],a[2]*b[2]))
    
def delta(c1, c2, c3):
    (x1,y1,z1) = c1
    (x2,y2,z2) = c2
    (x3,y3,z3) = c3
    u = ((x2-x1),(y2-y1),(z2-z1))
    v = ((x3-x2),(y3-y2),(z3-z2))
    uv = dotproduct(u,v)
    lu = math.sqrt(dotproduct(u,u))
    lv = math.sqrt(dotproduct(v,v))
    try:
        theta = math.degrees(math.acos(uv/(lu*lv)))
    except ZeroDivisionError:
        theta = 0
    return (lu, theta, lv)

def optimize(points, angle=0):
    tpoints = [(tp[0]/1000000.0, tp[1]/1000000.0, tp[2], tp[3], tp[4], tp[5]) \
        for tp in points]
    if angle == 0:
        return tpoints
    queue = [tpoints[0], tpoints[0]]
    opt = list(queue)
    for tp in tpoints:
        # d = haversine(last[1], tp)
        da = delta(cartesian(queue[0]), cartesian(queue[1]), cartesian(tp))
        queue.pop(0)
        queue.append(tp)
        #print da
        if da[1] > angle:
            opt.append(tp)
    return opt


if __name__ == '__main__':
    dbname = 'pykmaze.sqlite'
    dbpath = 'HOME' in os.environ and os.environ['HOME'] or '.'
    if sys.platform.lower() in ('darwin'):
        dbpath = os.path.join(dbpath, 'Library', 'Application Support', 
                              'Pykmaze', dbname)
    else:
        dbpath = os.path.join(dbpath, '.pykmaze', dbname)
    modes = ('default', 'air')
    usage = 'Usage: %prog [options]\n' \
            '   Keymaze 500-700 communicator'
    optparser = OptionParser(usage=usage)
    optparser.add_option('-p', '--port', dest='port',
                         default='/dev/cu.usbserial',
                         help='Serial port name')
    optparser.add_option('-k', '--kml', dest='kml',
                         help='Export to KML, output file name')
    optparser.add_option('-K', '--kmz', dest='kmz',
                         help='Export to KMZ, output file name')
    optparser.add_option('-x', '--gpx', dest='gpx',
                         help='Export to GPX, output file name')
    optparser.add_option('-T', '--trim', dest='trim',
                         help='Trim a track start[,end] with [+-]hh:mm:ss')
    optparser.add_option('-z', '--zoffset', dest='zoffset', default='0',
                         help='Offset to add on z-axis (meters)')
    optparser.add_option('-s', '--storage', dest='storage', 
                         default=dbpath,
                         help='Specify path for data storage (default: %s)' \
                                % dbpath)
    optparser.add_option('-o', '--offline', dest='offline', 
                         action='store_true',
                         help='Offline (used cached information)')
    optparser.add_option('-S', '--sync', dest='sync', 
                         action='store_true',
                         help='Load all new tracks from device')
    optparser.add_option('-f', '--force', dest='force', 
                         action='store_true',
                         help='Force reload from device')
    optparser.add_option('-i', '--info', dest='info', 
                         action='store_true',
                         help='Show owner information')
    optparser.add_option('-c', '--catalog', dest='catalog', 
                         action='store_true',
                         help='Show track catalog')
    optparser.add_option('-t', '--track', dest='track', 
                         help='Retrieve trackpoint for specified track')
    optparser.add_option('-m', '--mode', dest='mode', choices=modes,
                         help='Use show mode among [%s]' % ','.join(modes),
                         default=modes[0])
    
    (options, args) = optparser.parse_args(sys.argv[1:])
    
    log = logging.getLogger('pykmaze')
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)
    
    try:
        if options.force and options.offline:
            raise AssertionError('Force and offline modes are mutually '
                                 'exclusive')
        keymaze = None
        if not options.offline:
            keymaze = KeymazePort(log, options.port)
        elif options.sync:
            raise AssertionError('Cannot sync from device in offline mode')
        cache = KeymazeCache(log, options.storage, keymaze)

        info = cache.get_information()

        if options.info:
            print ' Device: %s' % info['name']
            print ' Owner:  %s' % info['user']
            print ' S/N:    %s' % info['serialnumber']
            print ''
        
        device = cache.get_device(info['serialnumber'])
        
        tpcat = cache.get_trackpoint_catalog(device)
        
        if options.sync:
            reload_cache = False
            for tp in tpcat:
                if None in (tp['altmin'], tp['altmax']):
                    log.info('Should load sync track %d from device' % \
                             (int(tp['id'])+1))
                    cache.get_trackpoints(device, tp['track'])
                    reload_cache = True
            if reload_cache:
                tpcat = cache.get_trackpoint_catalog(device)
                    
        if options.catalog:
            show_trackpoints_catalog(tpcat)
            print ''
        
        if options.track:
            tracks = []
            if options.track in ['all']:
                if options.kml or options.kmz or options.gpx:
                    raise AssertionError('Cannot export several tracks')
                tracks = [tp['track'] for tp in tpcat]
                log.debug('Tracks %s' % tracks)
            else:
                for tp in tpcat:
                    track = int(options.track)-1
                    if int(tp['id']) == track: 
                        tracks = [tp['track']]
                        break
                if not tracks:
                    raise AssertionError('Track "%s" does not exist' % \
                                         options.track)
            tpoints = []
            for track in tracks:
                log.info('Recovering trackpoints for track %u' % track)
                tpoints = cache.get_trackpoints(device, track)
            if len(tracks) == 1:
                km = options.kml or options.kmz
                if km:
                    from kml import KmlDoc
                if options.gpx:
                    from gpx import GpxDoc
                    
                if km or options.gpx:
                    track_info = filter(lambda x: x['track'] == track, 
                                        tpcat)[0]
                    if options.trim:
                        trims = parse_trim(options.trim.split(','))
                        log.info('All points: %d' % len(tpoints))
                        tpoints = trim_trackpoints(track_info, tpoints, trims)
                        log.info('Filtered points: %d' % len(tpoints))
                    optpoints = optimize(tpoints, 0)
                    log.info('Count: %u, opt: %u', 
                              len(tpoints), len(optpoints))
                if km:
                    kml = KmlDoc(os.path.splitext(os.path.basename(km))[0])
                    kml.add_trackpoints(optpoints, int(options.zoffset), 
                                        extrude='air' not in options.mode)
                if options.kmz:
                    import zipfile
                    import cStringIO as StringIO
                    out = StringIO.StringIO()
                    kml.write(out)
                    out.write('\n')
                    z = zipfile.ZipFile(options.kmz, 'w', 
                                        zipfile.ZIP_DEFLATED)
                    z.writestr('doc.kml', out.getvalue())
                if options.kml:
                    with open(options.kml, 'wt') as out:
                        kml.write(out)
                        out.write('\n')
                
                if options.gpx:
                    gpx = GpxDoc(os.path.splitext( \
                                 os.path.basename(options.gpx))[0],
                                 track_info['start'])
                    gpx.add_trackpoints(optpoints, int(options.zoffset))
                    with open(options.gpx, 'wt') as out:
                        gpx.write(out)
                        out.write('\n')
                        
    except AssertionError, e:
        print >> sys.stderr, 'Error: %s' % e[0]

