=========
 PyKMaze
=========

Abstract
~~~~~~~~
 
Geonaute Keymaze 500/700 GPS watch devices are shipped with a Windows-only 
application software.

Pykmaze alleviates this issue and allows to transfer data from/to the device 
with any host.

Features
~~~~~~~~

Pykmaze is a pure Python command-line application that does not offer a 
graphical interface as the original application software does, but nevertheless
allows to download recorded tracks and upload waypoints.

Its produces and reads Google Earth .KML file, so that tracks and waypoints may
be observed and edited with the Google Earth application.

Important notice
----------------
The Keymaze 500/700 protocol has been reverse-engineered from scratch. Pykmaze
code is not based on published information and may fail to comply with the 
communication protocol the Keymaze device expects.

Use it at your own risk.

Supported devices
~~~~~~~~~~~~~~~~~

Although it seems that Keymaze 500 and 700 share the same communication 
protocol, no test has been run with Keymaze 700 GPS devices yet. It seems that
the Geonaute device is a rebranded GlobalSat GH-615B device, so pykmaze might
also be able to communicate with these devices.

Pykmaze is not compatible with earlier devices such as Keymaze 300 that may 
use a different communication protocol. Check out the gpsd4_ project 
if you're looking for Keymaze 300 device support. Both projects are fully 
unrelated.

For now, pykmaze has been successfully run on an Intel Mac OS X Snow Leopard 
64-bit host. It should run fine on any Linux host.

.. _gpsd4: http://gpsd4.tuxfamily.org
