"""
Iff executed as main file, will ask for a directory within data/ and plot the measurements therein

Plots total multichain disk usage for all nodes against time, plus the total tx and chain size,
for time periods specified within the params.py file in the directory

If detailed disk space data exists, will also plot size of all multichain subfolders plus
total tx and chain size against time for each node. Only real test data.

Is called by benchmark.py after test ends
"""

import csv
import importlib.util

from sklearn import linear_model
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from helpers import *


def plotResults(directory):
    """
    Plots measurements with transaction volume and disk space usage on y-axis against time
    """

    # import params of that test run
    spec = importlib.util.spec_from_file_location("params.py", directory + "/params.py")
    params = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(params)

    if params.offchain:
        centerTime = 90
    else:
        centerTime = 600

    startrow = round(centerTime / params.measureDelay)

    # read in data from measurements and format for linear regression / plotting
    data = pd.read_csv(directory + "/measurements.csv", header=None).values
    n, m = data.shape[0], data.shape[1]
    time = data[:, 0].reshape(n, 1)

    # set labels for plot
    labels = ["chain size", "total size items"]
    labels += params.labels

    for plotDuration in params.plotDuration:

        # figure out what units to use for disk space and time
        if plotDuration == 0:
            timeUnit, timeConversionRate = getTime(time[-1])
            sizeUnit, sizeConversionRate = getSize(np.amax(data[-1, 1:]))
        else:
            endTime = plotDuration * (60 * 60 * 24)
            timeUnit, timeConversionRate = getTime(endTime)
            sizeUnit, sizeConversionRate = getSize(np.amax(data[-1, 1:]) * endTime / params.testDuration)

        fig = plt.figure()
        ax = fig.add_subplot(111)

        finalTally = []

        for i in range(1, m):

            column = data[:, i].reshape(n, 1)

            # plot actually measured data for the test duration
            if plotDuration == 0:
                ax.plot(time * timeConversionRate, (column - column[startrow]) * sizeConversionRate, "-", label=labels[i-1], alpha=0.4)
                ax.axvline(x = time[startrow] * timeConversionRate, alpha=0.5)

            # train linear regression model on measured data and plot the approximate values for given time
            else:
                regr = linear_model.LinearRegression()
                regr.fit(time[startrow:, :], column[startrow:, :])
                # print("Coefficients for " + labels[i-1] + ": \n", regr.coef_)

                timeEX = np.linspace(centerTime, endTime, num=500).reshape(500, 1)
                columnEX = regr.predict(timeEX)

                ax.plot(timeEX * timeConversionRate, columnEX * sizeConversionRate, "-", label=labels[i-1], alpha=0.4)
                print (labels[i-1], round(columnEX[-1][0] * sizeConversionRate, 2))
                finalTally.append(round(columnEX[-1][0] * sizeConversionRate, 2))

        print (finalTally)
        ax.set_xlabel("time elapsed in " + timeUnit)
        ax.set_ylabel(r"$\delta$ diskspace in " + sizeUnit)
        ax.legend(loc=0)

        fig.savefig(directory + "/plot-" + str(plotDuration) + ".png")


def prepDetailedData(directory, i):
    """
    Takes raw data string accumulated from the test and processes it so it can be read by pandas
    Writes out results in "diskspace0split.csv" etc.
    """
    data = pd.read_csv(directory + "/diskspace" + str(i) + ".csv", header=None).values

    with open(directory + "/diskspace" + str(i) + "split.csv", "w") as outfile:
        wr = csv.writer(outfile, quoting=csv.QUOTE_ALL)

        # get the header
        header = ["time"]
        firstRow = data[0][1].replace('\r\n','\t').split("\t")
        for j in range(len(firstRow)):
            if j % 2 == 1:
                header.append(firstRow[j][18:])

        wr.writerow(header)

        for row in data:
            raw = row[1].replace('\r\n','\t').split("\t")
            newRow = [row[0]]
            for j in range(len(raw)):
                if j % 2 == 0 and j < len(raw) - 1:
                    newRow.append(float(raw[j]))
            wr.writerow(newRow)


def plotDetailed(params, directory, i):
    """
    Plots detailed disk usage data for a given node by subfolders within the chain folder
    """

    if params.offchain:
        centerTime = 90
    else:
        centerTime = 600

    startrow = round(centerTime / params.measureDelay)

    df = pd.read_csv(directory + "/diskspace" + str(i) + "split.csv", header=0)
    data = df.values
    labels = list(df)

    n, m = data.shape[0], data.shape[1]
    time = data[:, 0].reshape(n, 1)

    fig = plt.figure()
    ax = fig.add_subplot(111)

    timeUnit, timeConversionRate = getTime(time[-1])
    sizeUnit, sizeConversionRate = getSize(np.amax(data[-1, 1:]))

    for j in range(1, m):
        if "stream" not in labels[j]:
            column = data[:, j].reshape(n, 1)
            ax.plot(time * timeConversionRate, (column - column[startrow]) * sizeConversionRate, "-", label=labels[j], alpha=1)

    items = pd.read_csv(directory + "/measurements.csv", header=None).values[:n, 2].reshape(n, 1)
    ax.plot(time * timeConversionRate, (items - items[startrow]) * sizeConversionRate, "-", label="items", alpha=1)

    chainSize = pd.read_csv(directory + "/measurements.csv", header=None).values[:n, 1].reshape(n, 1)
    ax.plot(time * timeConversionRate, (chainSize - chainSize[startrow]) * sizeConversionRate, "-", label="chainSize", alpha=1)

    ax.set_xlabel("time elapsed in " + timeUnit)
    ax.set_ylabel(r"$\delta$ diskspace in " + sizeUnit)
    ax.legend(loc=0)

    fig.savefig(directory + "/diskspace" + str(i) + ".png")


def plotResultsDetailed(directory):

    # import params of that test run
    spec = importlib.util.spec_from_file_location("params.py", directory + "/params.py")
    params = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(params)

    # to account for earlier runs in which diskSpaceDetailed didn't exist
    try:
        if params.diskSpaceDetailed:
            for i in range(params.numNodes):
                prepDetailedData(directory, i)
                plotDetailed(params, directory, i)
    except AttributeError:
        pass


def main():

    # get directory
    offc = input("Offchain? y or n: ")
    num = input("Directory number: ")
    if offc == "y":
        direc = "data/testfiles-offchain"
    else:
        direc = "data/testfiles-onchain"

    plotResults(direc + "-" + num)
    plotResultsDetailed(direc + "-" + num)

if __name__ == "__main__":
    main()
