"""
Decode the Flexible and Interoperable data Transfer (FIT) protocol [1]_.

This subpackage is really a leaner, and somewhat meaner, py3k version of
the python-fitparse package [2]_. The protocol itself is described extensively
in the FIT SDK materials [1]_.

The reading internals---i.e. the protocol implementation---are in the
`_protocol` module. This relies, in turn, on a data module (`_profile`)
wrangled from the "Profile.xlsx" file that comes with the FIT SDK. Do not
try to read this module. It is thoroughly disgusting. The development
version of this package includes the subdirectory "_make_profile" which
better exposes the logic for this module. Read that instead.


.. [1] https://www.thisisant.com/resources/fit
.. [2] https://github.com/dtcooper/python-fitparse/tree/ng

"""
from activityio.fit._reading import read_and_format as read
from activityio.fit._reading import gen_records
