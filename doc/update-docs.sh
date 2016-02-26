#!/bin/bash

# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0

git clone https://pagure.io/pungi.git /tmp/pungi
pushd /tmp/pungi/doc
make html
popd

git clone ssh://git@pagure.io/docs/pungi.git /tmp/pungi-doc
pushd /tmp/pungi-doc
git checkout 4.0
git rm -fr ./*
cp -r /tmp/pungi/doc/_build/html/* ./
git add .
git commit -s -m "update rendered pungi docs"
git push origin 4.0
popd

rm -rf  /tmp/pungi/ /tmp/pungi-doc/
