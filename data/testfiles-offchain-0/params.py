"""
Parameters for benchmark.py
"""
from base64 import b64encode
import random
import numpy as np


numNodes = 5							# number of nodes including masternode, currently up to 6
# labels = list(map(str, range(numNodes)))
labels = ["read-only",
				  "send-only",  	# labels for the nodes (for plotting)
				  "average",
				  "receive-only",
				  "idle"]

# txpm = np.random.random_integers(0, 5, (numNodes, numNodes))
# for i in range(numNodes):
# 	txpm[i][i] = 0

txpm = [[0, 0, 0, 0, 0],    # matrix of transactions per minute
		    [0, 0, 4, 4, 0],    # column: number of transactions node receives from peers / min
		    [0, 0, 0, 4, 0],    # row: number of transactions sent to other nodes per minute
		    [0, 0, 0, 0, 0],
		    [0, 0, 0, 0, 0]]

offchain = True							# whether stream items are published offchain or onchain
diskSpaceDetailed = True 		# whether to measure detailed disk usage by nodes
masterSubAll = True 				# whether master node should subscribe to all streams

txSize = 128 								# KB, shared transaction size (1.53KB would be the average)
sigma = 1500								# ms, shared standard deviation of time between transaction, MUST BE NONZERO
testDuration = 600					# min, duration until test terminates
plotDuration = [0, 365]			# days, duration for which approximate values are plotted (if 0, actual test data)
measureDelay = 5						# s, time between measurements

"""
If setting up a local network in docker containers:
"""
host = "redacted" 																# host address on which docker containers are running

if offchain:
	directory = "data/testfiles-offchain"						# directory in which to store results
	networkPorts = [7557, 7558, 7559, 7560, 7561]		# exposed network ports of host
	rpcPorts = [8002, 8003, 8004, 8005, 8006] 			# exposed rpc ports of host
	containerName = "node-off"											# name of docker-containers + number, e.g. node-off0
else:
	directory = "data/testfiles-onchain"
	networkPorts = [7567, 7568, 7569, 7570, 7571]
	rpcPorts = [8012, 8013, 8014, 8015, 8016]
	containerName = "node-on"

chain = {
	"master": { 										# specify parameters for blockchain here, e.g.
		"PARAM_ANYONE_CAN_CONNECT": "anyone-can-connect|true",
	    "PARAM_ANYONE_CAN_MINE": "anyone-can-mine|true"
	},
	"all" : { 											# parameters are shared across nodes
		"CHAINNAME": "chain1",
        "NETWORK_PORT": 7557,
        "RPC_PORT": 8002,
        "RPC_USER": "multichainrpc",
        "RPC_PASSWORD": "violetunicorn",
        "RPC_ALLOW_IP": "0.0.0.0/0.0.0.0"
	}
}

streamName = "stream"									# basis, sender-receiver will be appended, e.g. stream0-1

header = {'Authorization': 'Basic ' + b64encode(bytes(chain["all"]["RPC_USER"] +
          ":" + chain["all"]["RPC_PASSWORD"], "utf-8")).decode("ascii")}
