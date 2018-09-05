#!/bin/bash -x

echo "Sleep for 15 seconds so the master node has initialised"
sleep 15

echo "Setup /root/.multichain/multichain.conf"
mkdir -p /root/.multichain/
cat << EOF > /root/.multichain/multichain.conf
rpcuser=$RPC_USER
rpcpassword=$RPC_PASSWORD
rpcallowip=$RPC_ALLOW_IP
rpcport=$RPC_PORT
EOF

echo "Start the chain"
multichaind $CHAINNAME@$MASTER_NODE:$NETWORK_PORT -daemon
sleep 5

echo "Change the config file"
multichain-cli $CHAINNAME stop
sleep 5
cp /root/.multichain/multichain.conf /root/.multichain/$CHAINNAME

multichaind -txindex -shrinkdebugfilesize $CHAINNAME

