#!/bin/bash

# Thin wrapper to run all tests
for t in $(dirname $0)/test_*
do
    $t
done
