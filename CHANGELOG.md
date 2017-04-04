# Change Log

## [0.0.3] - 2017-04-04
### Added
- Direct `pytz` dependency.
- More general exception catching in `ActivityData.__getitem__` so as not to interfere with the parent method.
- **Tests!**
- An `ewa` (exponentially weighted average) function to the tools module, which returns a callable intended for `pandas.DataFrame.rolling().apply()`.
- `ActivityData.recording_time()` for calculating actual time spent *in* an activity.

### Changed
- Type definitions now have their own subpackage rather than just a module.
- Refactored some of the reading process for xml file types.

### Removed
- `ActivityData.resample_1hz()` as it was overkill. Call the `pandas` API instead.

### Fixed
- `ActivityData.gradient()` dropping the index.
- Syntax error in the command line interface.
- FIT file timestamp handling. You can also now localise them by passing in a timezone string. (Closes #1)
- TCX file timestamp handling. They no longer expect fractional seconds by default. (Closes #2)

## [0.0.2] - 2016-11-02
### Added
- Support for GPX files.
- Command line interface (see `aio -h`).

### Removed
- Non-code files from package directories.

### Fixed
- `activityio._util.xml` was clobbering the standard library package in some cases, so was renamed to `activityio._util.xml_reading`

## [0.0.1] - 2016-11-01
### Added
- First commit and package pushed to PyPI.
