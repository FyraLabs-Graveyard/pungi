#!/bin/bash

# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0

git clone https://pagure.io/pungi.git /tmp/pungi
pushd /tmp/pungi/docs
make html
popd

git clone ssh://git@pagure.io/docs/pungi.git /tmp/pungi-doc
pushd /tmp/pungi-doc
git rm -fr ./*
cp -r /tmp/pungi/docs/build/html/* ./
git add .
git commit -s -m "update rendered pungi docs"
git push origin master
popd

rm -rf  /tmp/pungi/ /tmp/pungi-doc/
