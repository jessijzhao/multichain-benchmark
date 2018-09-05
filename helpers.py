import numpy as np
import requests
import os
import importlib.util
import params


def post(node, data):
    """
    Streamlines http post requests for local networks
    """
    return requests.post(params.host + ":" + str(params.rpcPorts[node]), headers=params.header, json=data)


def getSize(maxSize):
    """
    Finds appropriate unit for disk space and returns its name and the conversion rate from KB
    """
    if maxSize > 1 * (1024 * 1024):
        return "GB", 1 / (1024 * 1024)
    elif maxSize > 10 * 1024:
        return "MB", 1 / 1024
    else:
        return "KB", 1


def getTime(maxTime):
    """
    Finds appropriate unit for time and returns its name and the conversion rate from s
    """
    if maxTime > 5 * (60 * 60 * 24 * 365.23):
        return "years", 1 / (60 * 60 * 24 * 365.23)
    elif maxTime > 10 * (60 * 60 * 24 * 30.44):
        return "months", 1 / (60 * 60 * 24 * 30.44)
    elif maxTime > 10 * (60 * 60 * 24 * 7):
        return "weeks", 1 / (60 * 60 * 24 * 7)
    elif maxTime > 10 * (60 * 60 * 24):
        return "days", 1 / (60 * 60 * 24)
    elif maxTime > 10 * (60 * 60):
        return "hours", 1 / (60 * 60)
    elif maxTime > 10 * 60:
        return "min", 1 / 60
    else:
        return "seconds", 1


def convertYearToMin(x):
    return x / (60 * 24 * 365.23)

def getTxpm(tx):
    """
    Takes a dict with party names as keys and transactions per year as values
    Returns list of labels and a transaction matrix txpm
    """
    numParts = len(tx)

    txpy = np.zeros((numParts, numParts))
    sends, receivs, labels = [], [], []

    for key in tx:
        sends.append(tx[key])
        receivs.append(tx[key])
        labels.append(key)
    receivs.append(0)

    txpy = np.hstack((txpy, np.array([sends]).reshape(numParts, 1)))
    txpy = np.vstack((txpy, np.array(receivs)))

    convert = np.vectorize(convertYearToMin)

    return labels, convert(txpy)


def searchData():
    """
    Small helper function to search data for certain tx sizes or other values
    """

    txSize = int(input("txsize: "))     # which txSize to search for in KB, set to False if all
    txpm = [[0, 0, 0, 0, 0],            # which txpm to search for, set to False if all
            [0, 0, 4, 4, 0],
            [0, 0, 0, 4, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0]]

    print ("txSize:", txSize)
    print ("txpm:", txpm)

    for i in range(1, 20):

        for direc in ["data/testfiles-offchain", "data/testfiles-onchain"]:
            directory = direc + "-" + str(i)

            if os.path.isdir(directory):

                # import params from the given directory
                spec = importlib.util.spec_from_file_location("params.py", directory + "/params.py")
                params = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(params)

                if not txSize or txSize == params.txSize:
                    if not txpm or txpm == params.txpm:
                        print (directory)
