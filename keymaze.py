#-----------------------------------------------------------------------------
# Communicate w/ a Decathlon Keymaze 500/700 devices
#-----------------------------------------------------------------------------
# @author Emmanuel Blot <manu.blot@gmail.com> (c) 2009
# @license MIT License, see LICENSE file
# @note The communication protocol here has been fully reverse-engineered from 
#       the serial data stream initiated from the Windows (c) GUI application.
#       It is likely to be incomplete or not fully understood. Support for 
#       Keymaze 700 is uncertain, as it has not been tested. Feedback is 
#       warmly welcomed
#-----------------------------------------------------------------------------

from util import hexdump, inttime
import datetime
import struct
import sys
import time
try:
    import serial
except ImportError:
    print >> sys.stderr, "Missing serial module"
    sys.exit(1)

class KeymazePort(object):
    """Interface w/ the Keymaze device, through a serial stream which is itself
    encapsulated into USB packets, thanks to a PL-2303 Prolific Serial-to-USB
    chip, embedded within the provided data cable
    """
    
    KM_BAUDRATE = 57600
    NMEA_BAUDRATE = 4800
    
    CMD_PREFIX = 0x02
    FW_PREFIX = 0x11
    
    CMD_TP_DIR = 0x78
    CMD_TP_GET_HDR = 0x80
    CMD_TP_GET_NEXT = 0x81
    CMD_INFO_GET = 0x85
    ACK_TP_GET_NONE = 0x8a
    
    # Note: device use big-endian encoding
    TP_CAT_FMT = '3B3BBIIHHBB2h3H'  # 31
    TP_HDR_FMT = 'IIIHHBBI'         # 22
    TP_ENT_FMT = 'iihHHB'           # 15
    INFO_FMT = '12s13x17s11sBBxBxBxBxBx3x3B16x' 
    
    def __init__(self, log, portname):
        self.log = log
        try:
            try:
                from serialext import SerialExpander
                serialclass = SerialExpander.serialclass(portname)
            except ImportError:
                print "No pyftdi"
                serialclass = serial.Serial
            self._port = serialclass(port=portname,
                                     baudrate=self.KM_BAUDRATE)
            if not self._port.isOpen:
                self._port.open()
        except serial.serialutil.SerialException:
            raise AssertionError('Cannot open device "%s"' % portname)
        if not self._port.isOpen():
            raise AssertionError('Cannot open device "%s"' % portname)
        self._port.setRTS(level=0)
        self._port.setDTR(level=0)
        self._drain()
            
    def close(self):
        if self._port and self._port.isOpen:
            self._port.close()
    
    def get_information(self):
        """Obtaint the device information"""
        (resp, ack) = self._request_device(self.CMD_INFO_GET)
        (name,sn,user,gender,age,x1,weight,x2,height,y,m,d) = \
            struct.unpack('>%s' % self.INFO_FMT, resp)
        name = name[:name.find('\0')]
        sn = sn[:sn.find('\0')]
        user = user[:user.find('\0')]
        info = { 'name' : name,
                 'serialnumber' : sn,
                 'user' : user,
                 'gender' : gender and 'female' or 'male',
                 'age' : age,
                 'weight' : weight,
                 'height' : height,
                 'birthday' : datetime.date(1792+y,1+m,d) }
        return info
            
    def get_trackpoint_catalog(self):
        """Obtain the catalog of all stored trackpoints ('activities')"""
        (resp, ack) = self._request_device(self.CMD_TP_DIR)
        trackpoints = []
        start = 0
        while start < len(resp):
            # New catatalog entry
            end = start+struct.calcsize('>%s' % self.TP_CAT_FMT)
            if end > len(resp):
                raise AssertionError('Missing data in response %d / %d' % \
                                        end, len(resp))
            # there are 6 trailing bytes whose signification is yet to be
            # discovered, decoded here into the silent variable '_'
            (yy,mm,dd,hh,mn,ss,lap,dtime,dst,kcal,mspd,mhr,ahr,cmi,cmd,
             _,track,idx) = \
                struct.unpack('>%s' % self.TP_CAT_FMT, resp[start:end])
            if lap > 1:
                raise AssertionError('Multi-lap entries not supported')
            dtime /= 10
            lap_hour = dtime//3600
            dtime -= lap_hour*3600
            lap_min = dtime//60
            dtime -= lap_min*60
            lap_sec = int(lap_min)
            tp = { 'start': inttime(datetime.datetime(2000+yy,mm,dd,hh,mn,ss)),
                   'time' : 3600*lap_hour+60*lap_min+lap_sec,
                   'distance': dst,
                   'kcal' : kcal,
                   'maxspeed' : mspd,
                   'maxheart' : mhr,
                   'avgheart' : ahr,
                   'cmlplus' : cmi,
                   'cmlmin' : cmd,
                   'track': track,
                   'id': idx }
            trackpoints.append(tp) 
            start = end
        return trackpoints
        
    def get_trackpoints(self, track):
        """Obtain the trackpoints of an activity"""
        (resp, ack) = self._request_device(self.CMD_TP_GET_HDR, 
                                           struct.pack('>HH', 1, track))
        trackpoints = []
        start = 0
        # New catatalog entry
        end = start+struct.calcsize('>%s%s' % (self.TP_CAT_FMT, 
                                               self.TP_HDR_FMT))
        if end > len(resp):
            raise AssertionError('Missing data in response %d / %d' % \
                                    (end, len(resp)))
        # there are 6 trailing bytes whose signification is yet to be
        # discovered, decoded here into the silent variable '_'
        (yy,mm,dd,hh,mn,ss,lap,dtime,dst,kcal,mspd,mhr,ahr,cmi,cmd,_,
         track,idx,stop,ttime,tdst,tkcal,tmspd,tmhr,tahr,count) = \
            struct.unpack('>%s%s' % (self.TP_CAT_FMT, self.TP_HDR_FMT), 
                          resp[start:end])
        if lap > 1:
            raise AssertionError('Multi-lap entries not supported')
        lap_sec = dtime//10
        lap_msec = (dtime-lap_sec*10)*100
        tp = { 'start': datetime.datetime(2000+yy,mm,dd,hh,mn,ss),
               'time' : datetime.timedelta(0, lap_sec, 0, lap_msec),
               'distance': dst,
               'kcal' : kcal,
               'maxspeed' : mspd,
               'maxheart' : mhr,
               'avgheart' : ahr,
               'cmlplus' : cmi,
               'cmlmin' : cmd,
               'count' : count,
               'points' : []}
        rem_tp = count
        print 'Points: %d' % count
        while rem_tp > 0:
            (resp, ack) = self._request_device(self.CMD_TP_GET_NEXT,
                                               accept=[self.ACK_TP_GET_NONE,
                                                       self.CMD_TP_GET_HDR])
            if ack == self.ACK_TP_GET_NONE:
                # no more point
                return tp
            start = 0
            end = start+struct.calcsize('>%s' % self.TP_CAT_FMT)
            header = struct.unpack('>%s' % self.TP_CAT_FMT, resp[start:end])
            entry_len = struct.calcsize('>%s' % self.TP_ENT_FMT)
            start = end
            points = []
            while start+entry_len <= len(resp):
                (x,y,z,s,h,d) = struct.unpack('>%s' % self.TP_ENT_FMT, 
                                              resp[start:start+entry_len])
                points.append((x,y,z,s,h,d))
                rem_tp -= 1
                start += entry_len
            tp['points'].extend(points)
            pc = (50*(count-rem_tp))/count
            progress = '%s%s: %d%%' % ('+'*pc, '.'*(50-pc), 2*pc)
            print 'TP: ', progress, '\r', 
            sys.stdout.flush()
            if start < len(resp):
                self.log.error("Remaining bytes: %s" % hexdump(resp[start:]))
        print ''
        return tp

    def _request_device(self, command, params='', accept=[], debug=False):
        req = struct.pack('>BHB', self.CMD_PREFIX, 1+len(params), command)
        req += params
        req += struct.pack('>B', self._calc_checksum(req[1:]))
        self._port.timeout = 2
        resp_h = None
        accept.append(command)
        for knock in range(4):
            self._drain()
            if debug:
                self.log.debug("Write:\n%s" % hexdump(req))
            self._port.write(req)
            resp_h = self._port.read(3)
            if len(resp_h) < 3:
                continue
            (cmd, resp_len) = struct.unpack('>BH', resp_h)
            if cmd not in accept:
                self.log.error('Unexpected response %s' % hexdump(resp_h))
                self._drain()
                continue
            break
        if not resp_h:
            raise AssertionError('No answer from device')
        if len(resp_h) < 3:
            raise AssertionError('Communication error')
        if debug:
            self.log.debug('%d bytes to receive' % resp_len)
        resp = self._port.read(resp_len)
        cksum = self._port.read(1)
        if debug:
            self.log.debug("Read:\n%s" % hexdump(resp))
        self._port.timeout = 1
        if not len(cksum):
            raise AssertionError('Communication error')
        rcksum = ord(cksum)
        dcksum = self._calc_checksum(resp_h[1:], resp)
        if rcksum != dcksum:
            raise AssertionError('Comm. error, checksum error 0x%02x/0x%02x' \
                                    % (rcksum, dcksum))
        return (resp, cmd)
    
    def _calc_checksum(self, *args):
        """Compute the (NMEA) checksum for an outgoing packet"""
        cksum = 0x0
        for data in args:
            for b in data:
                cksum ^= ord(b)
        return cksum

    def _drain(self):
        """Drain the serial RX FIFO to remove all received bytes"""
        timeout = self._port.timeout
        while True:
            try:
                time.sleep(0.01)
                rem = self._port.inWaiting()
            except IOError:
                rem = 0
            for ch in range(rem):
                self._port.read()
            if not rem:
                break
        # restore timeout
        self._port.timeout = timeout
