#!/bin/sh

export PYTHONPATH=$(pwd)/../:$PYTHONPATH
export PATH=$(pwd)/../bin:$PATH

mkdir -p _composes

pungi-koji \
--target-dir=_composes \
--old-composes=_composes \
--config=data/dummy-pungi.conf \
--test "$@"
