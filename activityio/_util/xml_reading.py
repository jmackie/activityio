#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Some useful functions for parsing XML file types.

Note we need to name this `xml_reading` so as not to clobber the standard
library package.

"""
from xml.etree.cElementTree import iterparse

def gen_nodes(file_path, node_names, *, with_root=False):
    """Efficiently iterate over specific nodes of an XML document.

    http://effbot.org/zone/element-iterparse.htm
    """
    context = iter(iterparse(file_path, events=('start', 'end')))
    event, root = next(context)  # get the root element

    if with_root:
        yield root

    for event, element in context:
        if event == 'end' and sans_ns(element.tag) in node_names:
            yield element
            root.clear()


def sans_ns(tag):
    """Remove the namespace prefix from a tag."""
    return tag.split('}')[-1]
