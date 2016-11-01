# activityio: Exercise data handling library

Exercise/activity data has become a prolific resource, but applying any kind of sophisticated analyses is made difficult by the variety of file formats. This `python` library is intended to munge a number of these formats and present the data in a predictable and useable form. Moreover, the API is both closely intertwined with, and an extension of, the awesome [`pandas`](https://github.com/pandas-dev/pandas) library.

## Installation

The package is available on PyPI:

```
pip install activityio
```

## Example usage

There is a `read` function at the top-level of `activityio` that dispatches the appropriate reader based on file extension:

```pycon
>>> import activityio as aio
>>> data = aio.read('example.srm')
```

But you can also use sub-packages explicitly:

```pycon
>>> from activityio import srm
>>> data = srm.read('example.srm')
```

`data` is a subclass of the `pandas.DataFrame` and provides some neat additional functionality. Most notably, certain columns are "magic" in that they return specific `pandas.Series` subclasses. These subclasses make unit-switching easy, and provide other useful methods.

```pycon
>>> type(data)
<class 'activityio._util.types.ActivityData'>

>>> data.head(5)
          lap    dist  pwr   speed  temp  alt  cad  hr
time                                                  
00:00:00    1   5.611    0   5.611  26.8  530    0   0
00:00:01    1  10.999    0   5.388  26.8  530    0   0
00:00:02    1  25.054    0  14.055  27.1  532    0   0
00:00:03    1  42.609    0  17.555  27.1  532    0   0
00:00:04    1  59.414    0  16.805  27.3  532    0   0

>>> data.normpwr()
279.40584154170227

>>> type(data.speed)
<class 'activityio._util.types.Speed'>
>>> data.speed.base_unit
'm/s'
>>> data.speed.kph.mean()  # use a different unit
41.045473986415516

>>> data.dist.base_unit
'm'
>>> data.dist.miles[-1]
101.17480453266764

>>> data.alt.base_unit
'm'
>>> data.alt.ascent.sum()
1779.0
```

But note that you lose this functionality if you go changing column names:

```pycon
>>> data = data.rename(columns={'alt': 'altitude'})
>>> type(data.altitude)
<class 'pandas.core.series.Series'>
```

## API Notes

The main package is composed of sub-packages that contain the reading logic for the file format after which they're named. (e.g. `activityio.fit` is for parsing ANT/Garmin FIT files.) 

The ultimate logic is defined in a `_reading` module, which provides two functions: `gen_records` and `read_and_format`. 

+ `gen_records` is a generator function for iterating over the data-points in a file. The rows of the data table if you like. A "record" is a dictionary object.
+ `read_and_format` uses the above generator to return an `ActivityData` object.

`read_and_format` is available at the top-level of a sub-package as `read`; so reading in a file looks like `srm.read('path_to_file.srm')`. `gen_records` is imported as the same name.

There are also some `tools` provided in a separate module. These are just some nice extras. 

## Testing

All the readers have been tested extensively on my machine using a bank of files that I am not able to share. I will implement some simpler tests at some point that I can push to this repo.
