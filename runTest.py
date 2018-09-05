"""
Takes parameters defined in params and uses templates to set up a multichain network
in docker containers according to specs, and to create and run a Jmeter testplan.

Writes chain size, size of all items, and disk space for each node by time to a csv
plots results + their approximate continuation (linear regression.)

Saves csv + plots + params in new directory under data/

"""

from math import ceil
import copy
import csv
import os
import random
import string
import subprocess
import time
import xml.etree.ElementTree as ET

import numpy as np
import yaml

from helpers import *
import params
import plotDiskUsage


def writeYamlFile():
    """
    Takes masternode and slavenode as defined in docker-compose-template.yml and the number of nodes n
    Outputs docker-compose.yml file for a multichain network with masternode and n-1 slave nodes
    as specified by the parameters in params.py
    """

    # load docker-compose template
    basis = yaml.load(open("templates/docker-compose-template.yml"))
    compose = {"version": "2", "services": {}}

    # add master and slave nodes with proper environment and port mappings
    for i in range(params.numNodes):

        if i == 0:
            node = basis["masternode"].copy()
            node["environment"] = {**node["environment"], **params.chain["master"]}
        else:
            node = basis["slavenode"].copy()
            node["environment"]["MASTER_NODE"] = params.containerName + str(0)
            node["links"] = [params.containerName + str(0)]
            node["depends_on"] = [params.containerName + str(0)]

        node["container_name"] = params.containerName + str(i)
        node["environment"] = {**node["environment"], **params.chain["all"]}
        node["ports"] = [str(params.networkPorts[i]) + ":" + str(params.chain["all"]["NETWORK_PORT"]),
                         str(params.rpcPorts[i])     + ":" + str(params.chain["all"]["RPC_PORT"])]

        compose["services"][params.containerName + str(i)] = node

    # create the docker-compose file
    with open("docker-compose.yml", "w") as outfile:
        yaml.dump(compose, outfile, default_flow_style=False)


def startNodes():
    """
    Builds the images and brings the network up as defined in docker-compose.yml as a background process
    Masternode sends empty transactions to  avoid "Error no unspent transaction outputs"
    """
    subprocess.call("docker-compose down", shell=True)
    subprocess.call("docker-compose build", shell=True)
    subprocess.call("docker-compose up -d", shell=True)

    # give multichain network time to initialize properly
    time.sleep(30)

    # masternode sends empty transactions to all other sender nodes
    print ("Activating nodes ...")
    for i in range(1, params.numNodes):
        if sum(params.txpm[i]) > 0:
            address = post(i, {"method": "getaddresses"}).json()["result"][0]
            sendEmpty = {"method": "send", "params": [address, 0]}
            post(0, sendEmpty)


def createStreams():
    """
    Creates relevant paired streams, where sender and receiver roles are fixed
    Subscribes relevant nodes (as well as masternode, if so desired)
    """
    print ("Creating streams now ...")

    for sender in range(params.numNodes):
        for receiver in range(params.numNodes):
            if params.txpm[sender][receiver] > 0 and sender != receiver:

                # masternode creates new stream named after sender and receiver
                streamName = params.streamName + str(sender) + "-" + str(receiver)
                create = {"method": "create", "params": ["stream", streamName, True]}
                post(0, create); time.sleep(7)

                # sender and receiver (and possibly masternode) subscribe to stream
                subscribe = {"method": "subscribe", "params": [streamName]}
                if params.masterSubAll:
                    post(0, subscribe)
                post(sender, subscribe); post(receiver, subscribe); time.sleep(2)

    print ("Finished creating streams. Sleeping for 30 s.")
    time.sleep(30)


def createDirectory():
    """
    Creates a directory in data/ to store measurements, plots, etc. in
    """
    i = 0
    while os.path.isdir(params.directory + "-" + str(i)):
        i += 1
    directory = params.directory + "-" + str(i)
    subprocess.call("mkdir " + directory, shell=True)
    print ("Created ", directory)
    return directory


def writeJmxFile(directory):
    """
    Creates JMeter testplan based on the testplan-template, according to params.py
    """

    tree = ET.parse("templates/testplan.jmx")
    root = tree.getroot()

    # edit user defined parameters to assume value defined in params.py
    variables = root.find('.//elementProp[@name="TestPlan.user_defined_variables"]')[0]

    variables.find('./elementProp[@name="sigma"]')[1].text = str(params.sigma)
    variables.find('./elementProp[@name="numnodes"]')[1].text = str(params.numNodes)
    variables.find('./elementProp[@name="rampupperiod"]')[1].text = str(params.sigma / 1000)
    variables.find('./elementProp[@name="data"]')[1].text = ''.join(random.choices(string.digits, k=ceil(params.txSize*1024)*2-20)) # subtract uuid size

    if params.offchain:
        variables.find('./elementProp[@name="offchain"]')[1].text = "offchain"
    else:
        variables.find('./elementProp[@name="offchain"]')[1].text = ""

    variables.find('./elementProp[@name="protocol"]')[1].text = params.host.split("://", 1)[0]
    variables.find('./elementProp[@name="host"]')[1].text = params.host.split("://", 1)[1]

    # clone the template thread group, edit it, and append to testplan for each node
    threadGroupParent = root[0][1]

    for sender in range(params.numNodes):
        if sum(params.txpm[sender]) > 0:

            threadGroupBase, hashTreeBase = threadGroupParent[0], threadGroupParent[1]
            threadGroup, hashTree = copy.deepcopy(threadGroupBase), copy.deepcopy(hashTreeBase)

            # edit ports, url, path etc. in HTTP Request Default
            defaults = hashTree.find('.//ConfigTestElement')
            threadCSV = hashTree.find('.//CSVDataSet[@testname="Read Receiver Information"]')
            defaults.find('./stringProp[@name="HTTPSampler.port"]').text = str(params.rpcPorts[sender])
            threadCSV.find('./stringProp[@name="filename"]').text = "node" + str(sender) + ".csv"

            # create file with delay, streamname, and loop count for each receiver
            with open(directory + "/node" + str(sender) + ".csv", "w") as outfile:
                wr = csv.writer(outfile)
                for receiver in range(params.numNodes):
                    if params.txpm[sender][receiver] > 0 and sender != receiver:
                        delay = str(round (60 * 1000 / params.txpm[sender][receiver])) # in ms
                        streamName = params.streamName + str(sender) + "-" + str(receiver)
                        loopCount = ceil(params.txpm[sender][receiver] * params.testDuration)
                        wr.writerow([delay, streamName, loopCount])

            # prepend to threadGroupParent
            threadGroupParent.insert(2, threadGroup)
            threadGroupParent.insert(3, hashTree)

    # remove original thread group
    threadGroupParent.remove(threadGroupBase)
    threadGroupParent.remove(hashTreeBase)

    # save a copy of params.py, txpm, and write out the new jmx file
    subprocess.call("cp params.py " + directory + "/", shell=True)
    np.savetxt(directory + "/txpm.txt", params.txpm, delimiter=',')
    tree.write(open(directory + "/benchmark.jmx", "w"), encoding="unicode")


def runTest(directory):
    """
    Starts the JMeter test
    """
    subprocess.Popen("jmeter -n -t " + directory + "/benchmark.jmx", shell=True)


def getMeasurements(directory):
    """
    Writes measured values to csv file. Each row has format
    [elapsed time (s), chain growth (KB), size of items (KB), disk space node0 (KB), disk space node1 (KB), ..., ]
    """

    recentBlock, chainSize, numMeasurements = 0, 0, 0
    tail = min(180, max(0.05 * params.testDuration, 60))
    start = time.time()

    while time.time() < start + 60 * params.testDuration + tail:

        # get time elapsed so far
        elapsed = time.time() - start

        # if there's been a new block, update relative size of blockchain
        height = post(0, {"method": "listblocks", "params": [[-1]]}).json()["result"][0]["height"]
        if recentBlock != height:
            chainSize += post(0, {"method": "getblock", "params": [str(height)]}).json()["result"]["size"] / 1024.
            recentBlock = height

        # count the total number of streamitems published
        itemCount = 0
        if params.masterSubAll:
            lst = post(0, {"method": "liststreams"}).json()["result"]
            for stream in lst:
                itemCount += stream["items"]
        else:
            for sender in range(params.numNodes):
                lst = post(sender, {"method": "liststreams"}).json()["result"]
                for receiver in range(params.numNodes):
                    if params.txpm[sender][receiver] > 0 and sender != receiver:
                        streamName = params.streamName + str(sender) + "-" + str(receiver)
                        stream = next((item for item in lst if item["name"] == streamName))
                        itemCount += stream["items"]

        row = [elapsed, chainSize, itemCount * params.txSize]

        # get total disk space of the chain on each node, and append
        for i in range(params.numNodes):
            cmd = "docker exec -ti " + params.containerName + str(i) + " du -s /root/.multichain/" + params.chain["all"]["CHAINNAME"]
            space = subprocess.check_output(cmd, shell=True).decode("utf-8").split("\t", 1)[0]
            row.append(float(space))

        # note down measurements
        with open(directory + "/measurements.csv", "a") as outfile:
            wr = csv.writer(outfile, quoting=csv.QUOTE_ALL)
            wr.writerow([round(el, 2) for el in row])

        # note down exact disk space usage
        if params.diskSpaceDetailed:
            for i in range(params.numNodes):
                with open(directory + "/diskspace" + str(i) + ".csv", "a") as outfile:
                    wr = csv.writer(outfile, quoting=csv.QUOTE_ALL)
                    cmd = "docker exec -ti " + params.containerName + str(i) + " du /root/.multichain/" + params.chain["all"]["CHAINNAME"]
                    space = subprocess.check_output(cmd, shell=True).decode("utf-8")
                    wr.writerow([elapsed, space])

        # sleep until next measurement
        numMeasurements += 1
        while time.time() < start + numMeasurements * params.measureDelay:
            time.sleep(0.5)


def plotResults(directory):
    """
    Plots measurements with transaction volume and disk space usage on y-axis against time
    """

    # plots total disk usage for each node
    plotDiskUsage.plotResults(directory)

    # creates plot for each node, plots sizes of subfolders in chain folders
    if params.diskSpaceDetailed:
        plotDiskUsage.plotResultsDetailed(directory)


def cleanUp():
    """
    Brings down the network and removes temporary created files
    """
    subprocess.call("docker-compose down", shell=True)
    subprocess.call("rm docker-compose.yml", shell=True)
    subprocess.call("rm jmeter.log", shell=True)


def main():
    writeYamlFile()
    startNodes()
    createStreams()
    directory = createDirectory()
    writeJmxFile(directory)
    runTest(directory)
    getMeasurements(directory)
    plotResults(directory)
    cleanUp()

if __name__ == "__main__":
    main()
