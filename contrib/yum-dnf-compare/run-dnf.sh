#!/bin/bash

set -e
set -u
set -o pipefail

HERE=$(dirname "$0")
PATH=$HERE/../../bin:$PATH
PYTHONPATH=$HERE/../../:${PYTHONPATH:-}
export PATH PYTHONPATH

CONF=$1
LOG=${CONF%%.conf}.log
ARCH=$(head -n1 "$LOG" | tr ' ' '\n' | grep -- '--arch=')

CMD=(pungi-gather "--config=$CONF" "$ARCH" $(head -n1 "$LOG" | tr ' ' '\n' | grep '^--\(selfhosting\|fulltree\|greedy\|multilib\)'))

echo "${CMD[@]}"
if [ $# -le 1 ] || [ "$2" != "--interactive" ]; then
    exec >"$LOG.dnf"
fi
exec 2>&1

exec "${CMD[@]}"
