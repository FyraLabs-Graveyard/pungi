#!/bin/sh

export PYTHONPATH=$(pwd)/pmd:$(pwd)/../
export PATH=$(pwd)/../bin:$PATH

mkdir -p _composes

pungi-koji \
--target-dir=_composes \
--old-composes=_composes \
--config=dummy-pungi.conf \
--test
