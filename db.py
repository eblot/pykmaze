#-----------------------------------------------------------------------------
# Communicate w/ a Decathlon Keymaze 500/700 devices
#-----------------------------------------------------------------------------
# @author Emmanuel Blot <manu.blot@gmail.com> (c) 2009
# @license MIT License, see LICENSE file
#-----------------------------------------------------------------------------

import os
import sqlite3


def sqlparams(values):
    return ','.join(['?'] * len(values))


class KeymazeCache(object):
    """
    """
    
    DEVINFO = ('device INTEGER PRIMARY KEY AUTOINCREMENT',
               'serialnumber TEXT UNIQUE',
               'name TEXT',
               'user TEXT',
               'gender TEXT',
               'age INTEGER',
               'weight INTEGER',
               'height INTEGER',
               'birthday INTEGER' )
    
    TRACKINFO = ('device','start','time','distance','kcal','maxspeed',
                 'maxheart','avgheart','cmlplus','cmlmin','track','id')
    
    TRACKPOINT = ('device','track','point','lat','long','alt','speed',
                  'heart','delta')
    
    def __init__(self, log, dbpath, device=None):
        self.log = log
        self.device = device
        create = False
        if not os.path.isfile(dbpath):
            create = True
            if not os.path.isdir(os.path.dirname(dbpath)):
                os.makedirs(os.path.dirname(dbpath))
        self.db = sqlite3.connect(dbpath)
        if create:
            self._initialize()
            
    def _initialize(self):
        self.log.debug("Initialize")
        c = self.db.cursor()
        sql = ','.join(KeymazeCache.DEVINFO)
        c.execute('CREATE TABLE dev_info (%s)' % sql)
        sql = ','.join('%s INTEGER' % it for it in KeymazeCache.TRACKINFO)
        c.execute('CREATE TABLE tp_catalog (%s)' % sql)
        sql = ','.join('%s INTEGER' % it for it in KeymazeCache.TRACKPOINT)
        c.execute('CREATE TABLE tp_points (%s)' % sql)
        self.db.commit()
        
    def get_information(self, sn=None):
        c = self.db.cursor()
        if self.device:
            info = {}
            self.log.debug('Querying device info')
            info = self.device.get_information()
            if not info:
                raise AssertionErrror('Unable to retrieve device information')
            c.execute('SELECT device FROM dev_info WHERE serialnumber=?',
                      (info['serialnumber'], ))
            if not c.fetchone():
                keys = []
                values = []
                for (k,v) in info.items():
                    keys.append(k)
                    values.append(v)
                c.execute('INSERT INTO dev_info (%s) VALUES (%s)' % 
                            (','.join(keys), sqlparams(values)), values)
            self.db.commit()
        info = {}
        c.execute('SELECT * FROM dev_info WHERE device=?', (1,))
        row = c.fetchone()
        if not row:
            raise AssertionError('No device discovered yet')
        for (k,v) in zip([it.split(' ')[0] for it in KeymazeCache.DEVINFO],
                         row):
            info[k] = v
        return info
        
    def get_trackpoint_catalog(self, device):
        c = self.db.cursor()
        c.execute('SELECT start FROM tp_catalog WHERE device=?', 
                  (device,))
        tracks = [row[0] for row in c]
        if self.device:
            self.log.debug('Refresh catalog')
            tpcat = self.device.get_trackpoint_catalog()
            for tp in tpcat:
                if tp['start'] in tracks:
                    continue
                self.log.info('%u is not in cache' % tp['start'])
                values = []
                tp['device'] = device
                for k in self.TRACKINFO:
                    values.append(tp[k])
                c.execute('INSERT INTO tp_catalog VALUES (%s)' % \
                            sqlparams(values), values)    
                self.db.commit()
        c.execute('SELECT %s FROM tp_catalog WHERE device=?' % \
                  ','.join(self.TRACKINFO), (device,))
        tpcat = []
        for row in c.fetchall():
            tp = {}
            for (k,v) in zip(KeymazeCache.TRACKINFO, row):
                tp[k] = v
            cextra = self.db.cursor()
            track = tp['track']
            cextra.execute('SELECT MIN(alt),MAX(alt),SUM(delta) FROM tp_points'
                           ' WHERE device=? AND track=?', (device, track))
            rextra = cextra.fetchone()
            (tp['altmin'], tp['altmax']) = rextra[0:2]
            tp['duration'] = rextra[2] and rextra[2]//10
            tpcat.append(tp)
        return tpcat

    def get_trackpoints(self, device, track):
        c = self.db.cursor()
        c.execute('SELECT track FROM tp_points WHERE device=? AND track=? '
                  'LIMIT 1', (device, track))
        row = c.fetchone()
        if not row:
            self.log.debug('Trackpoint not in cache')
            if not self.device:
                raise AssertionError('Device is not available')
            self._load_trackpoints(device, track)
        c.execute('SELECT %s FROM tp_points WHERE device=? AND track=? '
                  'ORDER BY point' % ','.join(self.TRACKPOINT[3:]), 
                  (device, track))
        return c.fetchall()
        
    def get_device(self, sn):
        c = self.db.cursor()
        c.execute('SELECT device FROM dev_info WHERE serialnumber=?', (sn,))
        row = c.fetchone()
        if not row:
            raise AssertionError('No such device')
        return row[0]

    def _load_trackpoints(self, device, track):
        tpoints = self.device.get_trackpoints(track)
        c = self.db.cursor()
        point = 0
        for tp in tpoints['points']:
            point += 1
            values = [device, track, point]
            values.extend(tp)
            c.execute('INSERT INTO tp_points VALUES (%s)' % sqlparams(values),
                      values)
        self.db.commit()
