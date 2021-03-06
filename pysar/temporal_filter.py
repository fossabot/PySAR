#!/usr/bin/env python3
############################################################
# Program is part of PySAR                                 #
# Copyright(c) 2013-2018, Heresh Fattahi, Zhang Yunjun     #
# Author:  Heresh Fattahi, Zhang Yunjun                    #
############################################################


import os
import argparse
import numpy as np
from pysar.objects import timeseries
from pysar.utils import ptime


############################################################
EXAMPLE = """example:
 temporal_filter.py timeseries_ECMWF_demErr_refDate.h5
 temporal_filter.py timeseries_ECMWF_demErr_refDate.h5 -t 0.3
"""


def create_parser():
    parser = argparse.ArgumentParser(description='Smoothing timeseries in time using moving Gaussian window\n' +
                                     '  https://en.wikipedia.org/wiki/Gaussian_blur',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=EXAMPLE)

    parser.add_argument('timeseries_file',
                        help='timeseries file to be smoothed.')
    parser.add_argument('-t', '--time-win', dest='time_win', type=float, default=0.3,
                        help='time window in years (Sigma of the assmued Gaussian distribution.)')
    parser.add_argument('-o', '--outfile', help='Output file name.')
    return parser


def cmd_line_parse(iargs=None):
    parser = create_parser()
    inps = parser.parse_args(args=iargs)
    return inps


############################################################
def main(iargs=None):
    inps = cmd_line_parse(iargs)

    # read timeseries info / data
    obj = timeseries(inps.timeseries_file)
    obj.open()

    tbase = np.array(obj.yearList, np.float32).reshape(-1, 1)
    tbase -= tbase[obj.refIndex]

    ts_data = obj.read().reshape(obj.numDate, -1)

    # Smooth acquisitions / moving window in time one by one
    print('-'*50)
    print('filtering in time Gaussian window with size of {:.1f} years'.format(inps.time_win))
    ts_data_filt = np.zeros(ts_data.shape, np.float32)
    prog_bar = ptime.progressBar(maxValue=obj.numDate)
    for i in range(obj.numDate):
        # Weight from Gaussian (normal) distribution in time
        tbase_diff = tbase[i] - tbase
        weight = np.exp(-0.5 * (tbase_diff**2) / (inps.time_win**2))
        weight /= np.sum(weight)
        # Smooth the current acquisition
        ts_data_filt[i, :] = np.sum(ts_data * weight, axis=0)
        prog_bar.update(i+1, suffix=obj.dateList[i])
    prog_bar.close()
    del ts_data
    ts_data_filt -= ts_data_filt[obj.refIndex, :]
    ts_data_filt = np.reshape(ts_data_filt, (obj.numDate, obj.length, obj.width))

    # write filtered timeseries file
    if not inps.outfile:
        inps.outfile = '{}_tempGaussian.h5'.format(os.path.splitext(inps.timeseries_file)[0])
    obj_out = timeseries(inps.outfile)
    obj_out.write2hdf5(ts_data_filt, refFile=inps.timeseries_file)
    return inps.outfile


############################################################
if __name__ == '__main__':
    main()
