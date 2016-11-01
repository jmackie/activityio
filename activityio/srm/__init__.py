"""
Decode Schoberer Rad Messtechnik (SRM) power files.

This code was adapted largely from the GoldenCheetah code base [1]_.

Rainer Clasen [2]_, developer of the `srmio` utility, was also kind enough to
provide a file format specification. This specification, though incomplete, can
be found in the '_references' directory of this subpackage.


.. [1] https://github.com/GoldenCheetah/GoldenCheetah/blob/master/src/FileIO/SrmRideFile.cpp
.. [2] https://github.com/rclasen

"""
from activityio.srm._reading import read_and_format as read
from activityio.srm._reading import gen_records
