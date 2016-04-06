#!/usr/bin/python
# -*- coding: utf-8 -*-


# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


"""
Simple profiler that collects time spent in functions
or code blocks and also call counts.


Usage
=====

@Profiler("label1")
def func():
    ...

or

with Profiler("label2"):
    ...


To print profiling data, run:
Profiler.print_results()
"""


import functools
import time


class Profiler(object):
    _data = {}

    def __init__(self, name):
        self.name = name
        self._data.setdefault(name, {"time": 0, "calls": 0})

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, ty, val, tb):
        delta = time.time() - self.start
        self._data[self.name]["time"] += delta
        self._data[self.name]["calls"] += 1

    def __call__(self, func):
        @functools.wraps(func)
        def decorated(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorated

    @classmethod
    def print_results(cls):
        print "Profiling results:"
        results = cls._data.items()
        results.sort(lambda x, y: cmp(x[1]["time"], y[1]["time"]), reverse=True)
        for name, data in results:
            print "  %6.2f %5d %s" % (data["time"], data["calls"], name)
