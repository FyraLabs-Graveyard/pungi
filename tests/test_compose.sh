#!/bin/sh

set -e

PYTHONPATH=$(pwd)/../:$PYTHONPATH
PATH=$(pwd)/../bin:$PATH
export PYTHONPATH PATH

mkdir -p _composes

pungi-koji \
--target-dir=_composes \
--old-composes=_composes \
--config=data/dummy-pungi.conf \
--test "$@"

# Run this to create unified ISOs for the just created compose
#pungi-create-unified-isos _composes/latest-DP-1/
