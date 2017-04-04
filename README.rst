==========================================
activityio: Exercise data handling library
==========================================

Exercise/activity data has become a prolific resource, but applying any kind of sophisticated analyses is made difficult by the variety of file formats. This ``python`` library is intended to munge a number of these formats and present the data in a predictable and useable form. Moreover, the API is both closely intertwined with, and an extension of, the awesome `Pandas library <https://github.com/pandas-dev/pandas>`_.

Stability
---------
Please note this package is still very much an *alpha* release, so **breaking changes** are likely.

Installation
------------

The package is available on PyPI::

	$ pip install activityio


Example Usage
-------------

There is a ``read`` function at the top-level of ``activityio`` that dispatches the appropriate reader based on file extension:

>>> import activityio as aio
>>> data = aio.read('example.srm')

**NOTE** substitute ``'example.srm'`` with a path to your own activity file.

But you can also call sub-packages directly:

>>> from activityio import srm
>>> data = srm.read('example.srm')

``data`` in the above example is a subclass of the ``pandas.DataFrame`` and provides some neat additional functionality. Most notably, certain columns are "magic" in that they return specific ``pandas.Series`` subclasses. These subclasses make unit-switching easy, and provide other useful methods:

>>> type(data)
<class 'activityio._types.activitydata.ActivityData'>

>>> data.head(5)
          temp  lap   dist  alt  cad  pwr  speed  hr
time
00:00:00  26.1    1  1.027   67    0    0  1.027  71
00:00:01  26.1    1  2.721   67    0    0  1.694  71
00:00:02  26.2    1  4.415   67    0    0  1.694  71
00:00:03  26.2    1  6.331   67    0    0  1.916  71
00:00:04  26.2    1  8.469   67    0    0  2.138  75

>>> data.normpwr()
249.54104255943844

>>> type(data.speed)
<class 'activityio._types.columns.Speed'>

>>> data.speed.base_unit
'm/s'
>>> data.speed.kph.mean()  # use a different unit
38.485063801685477

>>> data.dist.base_unit
'm'
>>> data.dist.miles[-1]
134.78580023361226

>>> data.alt.base_unit
'm'
>>> data.alt.ascent.sum()
1898.0
```

But **NOTE** you lose this functionality if you go changing column names

>>> data = data.rename(columns={'alt': 'altitude'})
>>> type(data.altitude)
<class 'pandas.core.series.Series'>

API Notes
---------

The main package is composed of sub-packages that contain the reading logic for the file format after which they're named. (e.g. ``activityio.fit`` is for parsing ANT/Garmin FIT files.)

The ultimate logic is defined in a ``_reading`` module, which provides two functions: ``gen_records`` and ``read_and_format``.

+ ``gen_records`` is a generator function for iterating over the data-points in a file. The rows of the data table if you like. A "record" is a dictionary object.
+ ``read_and_format`` uses the above generator to return an ``ActivityData`` object.

``read_and_format`` is available at the top-level of a sub-package aliased as ``read``; so reading in a file looks like ``srm.read('path_to_file.srm')``. ``gen_records`` is imported under the same name.

There are also some useful ``tools`` provided in module by the same name.
