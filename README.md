# multichain-benchmark

Starts a network running MultiChain 2.0 alpha 3, creates and runs a JMeter test in which the nodes publish fixed size data to streams (onchain/offchain), and measures the disk space the chain occupies on each node over time.

Plots actual measurements, as well as their approximate continuation.

Predicts approximate disk usage given a transaction matrix and transactoin size over time.

## Prerequisites
Requires Python 3.x and a number of packages, see [runTest.py](runTest.py) for more details. Docker and JMeter must be installed. Please make sure you have enough free disk space to accommodate the nodes and the chain data they store.

## Running the test
Set the parameters in [params.py](params.py) before running the test. To start, run `python runTest`.

## Data Analysis
Run [plotDiskUsage](plotDiskUsage.py) to visualize test data.
Set parameters in [predictDiskUsage.py](predictDiskUsage.py) and run the file to learn coefficients from past test data.

## Acknowledgments
The MultiChain network is based on [Kunstmaan's implementation](https://github.com/Kunstmaan/docker-multichain), for license see [here](https://github.com/jessijzhao/multichain-benchmark/blob/master/templates/LICENSE).

Thanks goes to Arne Scherrer for mentorship.
