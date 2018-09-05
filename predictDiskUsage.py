"""
Analyzes all test measurements in data/ to try and learn how disk space
grows in relation to tx size and # tx

The goal is to predict the growth of disk space for any node given a matrix of transactions
and their size (constant for all tx), i.e. a function of disk space (KB)/time (s)

We use the following as features (for each node):
- # tx sent per minute * tx size
- # tx received per minute * tx size
- # tx in the network, neither sent nor received * tx size

The target is the coefficient that describes the slope of the linear function of
of disk space (KB)/time (s) - we learn it with simple linear regression from the test data

We weigh each node (i.e. data point) by the length of the test as a rough indicator
of the accuracy of the data

Lastly, we run linear regression on these features and targets to find the optimal coefficients,
where linreg was chosen rather arbitrarily. Other models may be interesting.

Assumes reasonable size of test set
"""

from math import ceil
import os
import random
import string

from sklearn import linear_model
from sklearn.metrics import mean_squared_error, r2_score
import numpy as np
import pandas as pd
import importlib.util

from helpers import *

# which predictions to show
APPROX = not True
LINREG = True

# for training the lin reg model on past data
OFFCHAIN = True          # whether to calculate coefficients for offchain or onchain
MINTESTSET = 5           # minimum size of test set for linear regression
TESTRATIO = 0.2          # ratio of test set to total elements
txSize = 1.53            # if model should only train on specific transaction size, otherwise None

# transactoins per year by party name for approximate prediction
tx = {
    "Purple Unicorn": 10000,
    "Red Horse": 50000,
    "Orange Donkey" : 3000
}


def predictApproxDU(tx):
    """
    Approximately calculates expected disk use of nodes according to the following formula,
    in which:
    tx = size of a transaction
    spy = # tx sent per year by node
    rpy = # tx received per year by node
    txpy = # total tx sent by any node in network per year

    offchain: growth of disk usage per year = 2 * spy * tx + rpy * tx +  0.4KB * txpy
    onchain: growth of disk usage per year = txpy * tx * 1.1

    Fairly accurate with large tx (i.e tx >= 64 KB) to around +/- 10%
    """

    # matrix of transactions
    labels, txpm = getTxpm(tx)

    # offchain accommodates source data (i.e. items stored locally by the sender)
    txpmOff = np.multiply(np.sum(txpm, axis=1), 2) + np.sum(txpm, axis=0)
    txpmOn = np.sum(txpm)

    # from transactions per minute to GB per year
    conversionRate = params.txSize * (60 * 24 * 365.23) / (1024 * 1024)

    # size of just items stored on disk
    GBpyOffBasic = np.multiply(txpmOff, conversionRate)
    GBpyOnBasic = txpmOn * conversionRate
    print ("GB per year onchain basic (shared): ", round(GBpyOnBasic, 2))
    print ("GB per year per node offchain basic: ", np.round_(GBpyOffBasic, 2))

    # adjustments for metadata etc.
    GBpyOff = np.add(GBpyOffBasic, 2)
    GBpyOn = GBpyOnBasic * 1.1

    print ("GB per year onchain (shared): ", round(GBpyOn, 2))
    print ("GB per year per node offchain: ", np.around(GBpyOff, 2))


def getData(params, directory):
    """
    Returns matrix of features, targets, and weights for all nodes in the given directory

    Features (X) are tx sent pm, tx received pm, and all other tx, all multiplied by txSize
    Targets (Y) are linear regression coefficients for each node
    Weights (w) are the test durations
    """
    txpm = np.array(params.txpm)

    # set node specific features
    txSentPerMin = np.sum(txpm, axis=1)
    txRecePerMin = np.sum(txpm, axis=0)
    allTx = np.full((params.numNodes,), np.sum(txpm))
    otherTx = np.subtract(np.subtract(allTx, txSentPerMin), txRecePerMin)

    # read in measurements
    data = pd.read_csv(directory + "/measurements.csv", header=None).values
    n, m = data.shape[0], data.shape[1]
    time = data[:, 0].reshape(n, 1)

    if params.offchain:
        centerTime = 90
    else:
        centerTime = 600

    startrow = round(centerTime / params.measureDelay)

    # get coefficients for linear regression
    coefs = []
    for i in range(1, m):
        column = data[:, i].reshape(n, 1)
        regr = linear_model.LinearRegression()
        regr.fit(time[startrow:, :], column[startrow:, :])
        coefs.append(regr.coef_[0][0])

    # if master node is subscribed to all streams, it is an outlier and should not be counted
    if params.masterSubAll:
        num = 1
    else:
        num = 0

    X = params.txSize * np.vstack((txSentPerMin, txRecePerMin, otherTx)).T[num:]
    Y = np.array(coefs[2 + num:])
    w = np.full((m - 3 - num,), data[-1, 0])

    data = np.hstack((np.hstack((X, Y.reshape(X.shape[0], 1))), w.reshape(X.shape[0], 1)))

    return data


def learnFunction(data):
    """
    Given accumulated data from past test runs, prints best coefficients as well as mse and var
    """

    # so that train and test will be random-ish
    np.random.shuffle(data)

    # split data into features, targets, and weights
    X, Y, w = np.hsplit(data, [3, 4])
    Y, w = Y.reshape(Y.shape[0],), w.reshape(w.shape[0],)
    print ("Number of elements: ", X.shape[0])

    # split the data into training/testing sets
    cut = min(MINTESTSET, ceil(TESTRATIO * data.shape[0]))
    X_train, X_test = X[:-cut], X[cut:]
    Y_train, Y_test = Y[:-cut], Y[cut:]
    w = w[:-cut]

    # train the model
    regr = linear_model.LinearRegression()
    regr.fit(X_train, Y_train, w)

    # make predictions using the testing set
    y_pred = regr.predict(X_test)

    coeffs = [round(elem, 5) for elem in regr.coef_]
    print("Coeff for tx sent/min * tx size: ", coeffs[0])
    print("Coeff for tx received/min * tx size: ", coeffs[1])
    print("Coeff for total other tx/min * tx size: ", coeffs[2])
    print("Mean squared error: ", mean_squared_error(Y_test, y_pred))
    print("Variance score: ", r2_score(Y_test, y_pred))


def predictFromData():

    # whether onchain or offchain
    if OFFCHAIN:
        direc = "data/testfiles-offchain"
    else:
        direc = "data/testfiles-onchain"

    # if given a value, only learn coefficients for #tx, using data from given txSize
    print (direc)
    print ("txSize:", txSize)

    # initialize initial row (with weight 0)
    data = np.zeros((1,5))

    for i in range(1, 20):

        directory = direc + "-" + str(i)

        # check if directory exists
        if os.path.isdir(directory):

            # import params from the given directory
            spec = importlib.util.spec_from_file_location("params.py", directory + "/params.py")
            params = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(params)

            if txSize == None or txSize == params.txSize:
                datap = getData(params, directory)
                data = np.vstack((data, datap))

    learnFunction(data)


def main():

    if LINREG:
        print ("\nPredictions from past data:")
        predictFromData()

    if APPROX:
        print ("\nPredictions based on rough formula:")
        predictApproxDU(tx)


if __name__ == "__main__":
    main()
