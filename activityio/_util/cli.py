#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from functools import partial
from importlib import import_module
from os import path, listdir

import activityio


VALID_FORMATS = tuple(d for d in listdir(path.dirname(activityio.__file__))
                      if not d.startswith('_') and not d.endswith('py'))


def main():

    # Argument handling
    # -----------------
    parser = ArgumentParser(description='parse an activity file')

    parser.add_argument('input',
                        type=str,
                        help='raw file to read')
    parser.add_argument('--output',
                        type=str,
                        metavar='filename',
                        default=None,
                        help='optional; file to write to')
    parser.add_argument('--format',
                        type=str,
                        default=None,
                        help='optional; format of the file',
                        choices=VALID_FORMATS)

    file_path, output, fmt = parser.parse_args()

    # Script begins
    # -------------
    if fmt is None:
        fmt = path.splitext(file_path)[-1][1:]

    module = import_module('activityio.' + fmt)
    data = module.read(file_path)
    write = partial(data.to_csv,
                    na_rep='NA', index_label='time', encoding='utf-8')
    if output is None:
        csv = write()
        print(csv)
    else:
        write(output)

    return 0


if __name__ == '__main__':
    main()
