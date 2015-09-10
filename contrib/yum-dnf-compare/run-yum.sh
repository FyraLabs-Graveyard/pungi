#!/bin/sh

set -e
set -o pipefail
set -u

export LANG=C

HERE=$(dirname "$0")
PATH=$HERE/../../bin:$PATH
PYTHONPATH=$HERE/../../
export PATH PYTHONPATH

CONF="$1"
LOG=${CONF%%.conf}.log

tempdir=$(mktemp -d)
trap 'rm -rf $tempdir' EXIT

cmd=$(head -n1 "$LOG" | cut -d' ' -f2- | sed "s@--\(destdir\|cachedir\)=\(/[^/ ]*\)*@--\1=$tempdir/\1@g" | sed 's/^pungi3/pungi/' | sed "s@--config=/\([^/]*/\)*work/[^/]*/pungi/\([^ ]*\)@--config=$1@g")

echo "$cmd"
if [ $# -le 1 ] || [ "$2" != "--interactive" ]; then
    exec >"$LOG.yum"
fi
exec 2>&1

$cmd
