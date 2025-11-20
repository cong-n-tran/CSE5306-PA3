#!/bin/sh
set -e

NODE_INDEX=${NODE_INDEX:-1}
CLUSTER_SIZE=${CLUSTER_SIZE:-5}
BASE_NAME=${BASE_NAME:-raft}

NODE_ID="${BASE_NAME}${NODE_INDEX}"
PORT="${PORT:-50051}"

PEERS=""
for i in $(seq 1 $CLUSTER_SIZE); do
  if [ "$i" != "$NODE_INDEX" ]; then
    p="${BASE_NAME}${i}:${PORT}"
    PEERS="${PEERS}${p},"
  fi
done

PEERS="${PEERS%,}"  # remove trailing comma

export NODE_ID PORT PEERS

echo "Starting Raft node: $NODE_ID"
echo "Peers: $PEERS"

exec python raft_server.py
