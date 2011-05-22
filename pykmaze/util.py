#-----------------------------------------------------------------------------
# Communicate w/ a Decathlon Keymaze 500/700 devices
#-----------------------------------------------------------------------------
# @author Emmanuel Blot <manu.blot@gmail.com> (c) 2009
# @license MIT License, see LICENSE file
#-----------------------------------------------------------------------------

import time

def hexdump(data):
    """Convert a binary buffer into a hexadecimal representation.
    """
    LOGFILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or \
                       '.' for x in range(256)])
    src = ''.join(data)
    length = 16
    result=[]
    for i in xrange(0, len(src), length):
       s = src[i:i+length]
       hexa = ' '.join(["%02x"%ord(x) for x in s])
       printable = s.translate(LOGFILTER)
       result.append("%06x   %-*s   %s\n" % \
                     (i, length*3, hexa, printable))
    return ''.join(result)

def inttime(dt):
    return int(time.mktime(dt.timetuple()))