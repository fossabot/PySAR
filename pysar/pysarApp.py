#!/usr/bin/env python3
############################################################
# Project: PySAR                                           #
# Purpose: Python Module for InSAR Time Series Analysis    #
# Author: Zhang Yunjun, Heresh Fattahi                     #
# Created: July 2013                                       #
# Copyright (c) 2013-2018, Zhang Yunjun, Heresh Fattahi    #
############################################################


import os
import sys
import glob
import time
import argparse
import warnings
import shutil
import subprocess

import h5py
import numpy as np

import version
from pysar.utils import readfile, writefile, utils as ut
from pysar.objects import ifgramStack
from pysar.defaults.auto_path import autoPath
from pysar import subset, save_hdfeos5 as hdfeos5


##########################################################################
TEMPLATE = """# vim: set filetype=cfg:
##------------------------ pysarApp_template.txt ------------------------##
########## 1. Load Data (--load to exit after this step)
## auto - automatic path pattern for Univ of Miami file structure
## load_data.py -H to check more details and example inputs.
pysar.load.processor      = auto  #[isce,roipac,gamma,], auto for isce
pysar.load.updateMode     = auto  #[yes / no], auto for yes, skip re-loading if HDF5 files are complete
pysar.load.compression    = auto  #[gzip / lzf / no], auto for no [recommended].
##---------interferogram datasets:
pysar.load.unwFile        = auto  #[path2unw_file]
pysar.load.corFile        = auto  #[path2cor_file]
pysar.load.connCompFile   = auto  #[path2conn_file]
pysar.load.intFile        = auto  #[path2int_file]
##---------geometry datasets:
pysar.load.demFile        = auto  #[path2hgt_file]
pysar.load.lookupYFile    = auto  #[path2lat_file]]
pysar.load.lookupXFile    = auto  #[path2lon_file]
pysar.load.incAngleFile   = auto  #[path2los_file]
pysar.load.headAngleFile  = auto  #[path2los_file]
pysar.load.shadowMaskFile = auto  #[path2shadow_file]
pysar.load.bperpFile      = auto  #[path2bperp_file]

## 1.1 Subset (optional)
## if both yx and lalo are specified, use lalo option unless a) no lookup file AND b) dataset is in radar coord
pysar.subset.yx       = auto    #[1800:2000,700:800 / no], auto for no
pysar.subset.lalo     = auto    #[31.5:32.5,130.5:131.0 / no], auto for no


## 1.3 Reference in Space
## reference all interferograms to one common point in space
## auto - randomly select a pixel with coherence > minCoherence
pysar.reference.yx            = auto   #[257,151 / auto]
pysar.reference.lalo          = auto   #[31.8,130.8 / auto]
pysar.reference.coherenceFile = auto   #[filename], auto for avgSpatialCoherence.h5
pysar.reference.minCoherence  = auto   #[0.0-1.0], auto for 0.85, minimum coherence for auto method
pysar.reference.maskFile      = auto   #[filename / no], auto for mask.h5


## 1.4 Unwrapping Error Correction (optional and not recommended)
## unwrapping error correction based on the following two methods:
## a. phase closure (Fattahi, 2015, PhD Thesis)
## b. connecting bridge
pysar.unwrapError.method   = auto   #[bridging / phase_closure / no], auto for no
pysar.unwrapError.maskFile = auto   #[filename / no], auto for no
pysar.unwrapError.ramp     = auto   #[plane / quadratic], auto for plane
pysar.unwrapError.yx       = auto   #[y1_start,x1_start,y1_end,x1_end;y2_start,...], auto for none


########## 2. Network Inversion
## 2.1 Modify Network (optional)
## 2.1.1 Coherence-based network modification = MST + Threshold, by default
## 1) calculate a average coherence value for each interferogram using spatial coherence and input mask (with AOI)
## 2) find a minimum spanning tree (MST) network with inverse of average coherence as weight (keepMinSpanTree)
## 3) for all interferograms except for MST's, exclude those with average coherence < minCoherence.
pysar.network.coherenceBased  = auto  #[yes / no], auto for no, exclude interferograms with coherence < minCoherence
pysar.network.keepMinSpanTree = auto  #[yes / no], auto for yes, keep interferograms in Min Span Tree network
pysar.network.minCoherence    = auto  #[0.0-1.0], auto for 0.5
pysar.network.maskFile        = auto  #[file name, no], auto for mask.h5, no for all pixels
pysar.network.maskAoi.yx      = auto  #[y0:y1,x0:x1 / no], auto for no, area of interest for coherence calculation
pysar.network.maskAoi.lalo    = auto  #[lat0:lat1,lon0:lon1 / no], auto for no - use the whole area

## 2.1.2 Network modification based on temporal/perpendicular baselines, date etc.
pysar.network.tempBaseMax     = auto  #[1-inf, no], auto for no, maximum temporal baseline in days
pysar.network.perpBaseMax     = auto  #[1-inf, no], auto for no, maximum perpendicular spatial baseline in meter
pysar.network.referenceFile   = auto  #[date12_list.txt / Modified_unwrapIfgram.h5 / no], auto for no
pysar.network.excludeDate     = auto  #[20080520,20090817 / no], auto for no
pysar.network.excludeIfgIndex = auto  #[1:5,25 / no], auto for no, list of ifg index (start from 0)
pysar.network.startDate       = auto  #[20090101 / no], auto for no
pysar.network.endDate         = auto  #[20110101 / no], auto for no


## 2.2 Invert network of interferograms into time series using weighted least sqaure (WLS) estimator.
## mask options for unwrapPhase of each interferogram before inversion:
## 1) coherence        - mask out pixels with spatial coherence < maskThreshold [Recommended]
## 2) connectComponent - mask out pixels with False/0 value
## 3) no               - no masking.
## weighting options for least square inversion:
## 1) fim  - WLS, use Fisher Information Matrix as weight (Seymour & Cumming, 1994, IGARSS). [Recommended]
## 2) var  - WLS, use inverse of covariance as weight (Guarnieri & Tebaldini, 2008, TGRS)
## 3) coh  - WLS, use coherence as weight (Perissin & Wang, 2012, IEEE-TGRS)
## 4) sbas - LS/SVD, uniform weight (Berardino et al., 2002, TGRS)
## Temporal coherence is calculated and used to generate final mask (Pepe & Lanari, 2006, IEEE-TGRS)
pysar.networkInversion.weightFunc    = auto #[fim / var / coh / sbas], auto for fim
pysar.networkInversion.maskDataset   = auto #[coherence / connectComponent / no], auto for no
pysar.networkInversion.maskThreshold = auto #[0-1], auto for 0.4
pysar.networkInversion.waterMaskFile = auto #[filename / no], auto for no
pysar.networkInversion.residualNorm  = auto #[L2 ], auto for L2, norm minimization solution
pysar.networkInversion.minTempCoh    = auto #[0.0-1.0], auto for 0.7, min temporal coherence for mask
pysar.networkInversion.minNumPixel   = auto #[int > 0], auto for 100, min number of pixels in mask above


########## Local Oscillator Drift (LOD) Correction (for Envisat only)
## reference: Marinkovic and Larsen, 2013, Proc. LPS
## correct LOD if input dataset comes from Envisat
## skip this step for all the other satellites.


########## 3. Tropospheric Delay Correction (optional and recommended)
## correct tropospheric delay using the following methods:
## a. pyaps - use weather re-analysis data (Jolivet et al., 2011, GRL, need to install PyAPS)
## b. height_correlation - correct stratified tropospheric delay (Doin et al., 2009, J Applied Geop)
## c. base_trop_cor - (not recommend) baseline error and stratified tropo simultaneously (Jo et al., 2010, Geo J)
pysar.troposphericDelay.method       = auto  #[pyaps / height_correlation / base_trop_cor / no], auto for pyaps
pysar.troposphericDelay.weatherModel = auto  #[ERA / MERRA / NARR], auto for ECMWF, for pyaps method
pysar.troposphericDelay.weatherDir   = auto  #[path2directory], auto for "./../WEATHER"
pysar.troposphericDelay.polyOrder    = auto  #[1 / 2 / 3], auto for 1, for height_correlation method
pysar.troposphericDelay.looks        = auto  #[1-inf], auto for 8, for height_correlation, number of looks applied to
                                             #interferogram for empirical estimation of topography correlated atmosphere.


########## 4. Topographic Residual (DEM Error) Correction (optional and recommended)
## reference: Fattahi and Amelung, 2013, IEEE-TGRS
## Specify stepFuncDate option if you know there are sudden displacement jump in your area,
## i.e. volcanic eruption, or earthquake, and check timeseriesStepModel.h5 afterward for their estimation.
pysar.topographicResidual               = auto  #[yes / no], auto for yes
pysar.topographicResidual.polyOrder     = auto  #[1-inf], auto for 2, poly order of temporal deformation model
pysar.topographicResidual.stepFuncDate  = auto  #[20080529,20100611 / no], auto for no, date of step jump
pysar.topographicResidual.excludeDate   = auto  #[20070321 / txtFile / no], auto for no, date exlcuded for error estimation
pysar.topographicResidual.phaseVelocity = auto  #[yes / no], auto for no - phase, use phase velocity for error estimation


## 4.1 Phase Residual Root Mean Square
## calculate the deramped Root Mean Square (RMS) for each epoch of timeseries residual from DEM error inversion
## To get rid of long wavelength component in space, a ramp is removed for each epoch.
## Recommendation: quadratic for whole image, plane for local/small area
pysar.residualRms.maskFile        = auto  #[filename / no], auto for maskTempCoh.h5, mask for ramp estimation
pysar.residualRms.ramp            = auto  #[quadratic / plane / no], auto for quadratic
pysar.residualRms.threshold       = auto  #[0.0-inf], auto for 0.02, minimum RMS in meter for exclude date(s)


## 4.2 Select Reference Date
## reference all timeseries to one date in time
## minRMS - choose date with minimum residual RMS using value from step 8.1
## no     - do not change the default reference date (1st date)
pysar.reference.date = auto   #[reference_date.txt / 20090214 / minRMS / no], auto for minRMS


########## 5. Phase Ramp Removal (optional)
## remove phase ramp for each epoch, useful to check localized deformation, i.e. volcanic, land subsidence, etc.
## [plane, quadratic, plane_range, plane_azimuth, quadratic_range, quadratic_azimuth, baseline_cor, base_trop_cor]
pysar.deramp          = auto  #[no / plane / quadratic], auto for no - no ramp will be removed
pysar.deramp.maskFile = auto  #[filename / no], auto for maskTempCoh.h5, mask file for ramp estimation


########## 6. Velocity Inversion
## estimate linear velocity from timeseries, and from tropospheric delay file if exists.
pysar.velocity.excludeDate = auto   #[exclude_date.txt / 20080520,20090817 / no], auto for exclude_date.txt
pysar.velocity.startDate   = auto   #[20070101 / no], auto for no
pysar.velocity.endDate     = auto   #[20101230 / no], auto for no


########## 7. Post-processing (geocode, output to Google Earth, HDF-EOS5, etc.)
## 7.1 Geocode
pysar.geocode              = auto  #[yes / no], auto for yes
pysar.geocode.SNWE         = auto  #[-1.2,0.5,-92,-91 / no ], auto for no, output coverage in S N W E in degree 
pysar.geocode.latStep      = auto  #[0.0-90.0 / None], auto for None, output resolution in degree
pysar.geocode.lonStep      = auto  #[0.0-180.0 / None], auto for None - calculate from lookup file
pysar.geocode.interpMethod = auto  #[nearest], auto for nearest, interpolation method
pysar.geocode.fillValue    = auto  #[np.nan, 0, ...], auto for np.nan, fill value for outliers.


## 7.2 Export to other formats
pysar.save.hdfEos5         = auto   #[yes / no], auto for no, save timeseries to HDF-EOS5 format
pysar.save.hdfEos5.update  = auto   #[yes / no], auto for no, put XXXXXXXX as endDate in output filename
pysar.save.hdfEos5.subset  = auto   #[yes / no], auto for no, put subset range info   in output filename
pysar.save.kml     = auto   #[yes / no], auto for yes, save geocoded velocity to Google Earth KMZ file


## 7.3 Plot
pysar.plot = auto   #[yes / no], auto for yes, plot files generated by pysarApp default processing to PIC folder
"""

EXAMPLE = """example:
  pysarApp.py
  pysarApp.py  SanAndreasT356EnvD.template
  pysarApp.py  SanAndreasT356EnvD.template  --load-data
  pysarApp.py  SanAndreasT356EnvD.template  --dir ~/insarlab/SanAndreasT356EnvD/PYSAR

  # Generate template file: pysarApp_template.txt
  pysarApp.py -g
  pysarApp.py SanAndreasT356EnvD.template -g

  # Show template content:
  load_data.py -H #Show example input template for ISCE/ROI_PAC/GAMMA products
"""

UM_FILE_STRUCT = """
    scratch/                 # $SCRATCHDIR defined in environmental variable
        SanAndreasT356EnvD/  # my_projectName, same as the basename of template file
            DEM/             # DEM file(s) (for topographic phase and geocode)
            DOWNLOAD/        # (optional) Data downloaded from agencies
            PROCESS/         # Interferograms processed by ROI_PAC, Gamma, ISCE, ... 
            PYSAR/           # PySAR work directory for time series analysis
                subset/      # PySAR subset
            RAW/             # (optional) Raw SAR data untared from DOWNLOAD directory
            SLC/             # (optional) SLC SAR data after focusing from RAW directory
            WEATHER/         # Weather data (e.g. PyAPS products)
                ECMWF/
                MERRA/
"""


def create_parser():
    parser = argparse.ArgumentParser(description='Time Series Analysis Routine',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=EXAMPLE)

    parser.add_argument('templateFileCustom', nargs='?',
                        help='custom template with option settings.\n' +
                             "It's equivalent to None if default pysarApp_template.txt is input.")
    parser.add_argument('--dir', dest='workDir',
                        help='PySAR working directory, default is:\n' +
                             'a) current directory, or\n' +
                             'b) $SCRATCHDIR/projectName/PYSAR, if meets the following 3 requirements:\n' +
                             '    1) autoPath = True in pysar/defaults/auto_path.py\n' +
                             '    2) environmental variable $SCRATCHDIR exists\n' +
                             '    3) input custom template with basename same as projectName\n')
    parser.add_argument('-g', dest='generate_template', action='store_true',
                        help='Generate default template (and merge with custom template), then exit.')
    parser.add_argument('-H', dest='print_example_template', action='store_true',
                        help='Print/Show the example template file for routine processing.')
    parser.add_argument('--version', action='store_true', help='print version number')

    parser.add_argument('--reset', action='store_true',
                        help='Reset files attributes to re-run pysarApp.py after loading data by:\n' +
                             '    1) removing ref_y/x/lat/lon for unwrapIfgram.h5 and coherence.h5\n' +
                             '    2) set DROP_IFGRAM=no for unwrapIfgram.h5 and coherence.h5')
    parser.add_argument('--load-data', dest='load_dataset', action='store_true',
                        help='Step 1. Load/check dataset, then exit')
    parser.add_argument('--modify-network', dest='modify_network', action='store_true',
                        help='Step 4. Modify the network, then exit')
    parser.add_argument('--invert-network', dest='invert_network', action='store_true',
                        help='Step 5. Inverse network of interferograms into time-series, then exit')
    return parser


def cmd_line_parse(iargs=None):
    """Command line parser."""
    parser = create_parser()
    inps = parser.parse_args(args=iargs)

    if inps.print_example_template:
        raise SystemExit(TEMPLATE)

    if (inps.templateFileCustom 
            and os.path.basename(inps.templateFileCustom) == 'pysarApp_template.txt'):
        inps.templateFileCustom = None
    return inps


def copy_aux_file(inps):
    # for Univ of Miami
    fileList = ['PROCESS/unavco_attributes.txt',
                'PROCESS/bl_list.txt',
                'SLC/summary*slc.jpg']
    try:
        projectDir = os.path.join(os.getenv('SCRATCHDIR'), inps.projectName)
        fileList = ut.get_file_list([os.path.join(projectDir, i) for i in fileList],
                                    abspath=True)
        for file in fileList:
            if ut.update_file(os.path.basename(file), file, check_readable=False):
                shutil.copy2(file, inps.workDir)
                print('copy {} to work directory'.format(os.path.basename(file)))
    except:
        pass
    return inps


def check_obsolete_default_template(template_file='./pysarApp_template.txt'):
    """Update pysarApp_template.txt file if it's obsolete, a.k.a. lack new option names"""
    obsolete_template = False
    current_dict = readfile.read_template(template_file)
    latest_dict = readfile.read_template(TEMPLATE)
    for key in latest_dict.keys():
        if key not in current_dict.keys():
            obsolete_template = True

    if obsolete_template:
        print('obsolete default template detected, update to the latest template options.')
        with open(template_file, 'w') as f:
            f.write(TEMPLATE)
        template_file = ut.update_template_file(template_file, current_dict)
    else:
        print('default template file exists: '+template_file)
    return template_file


def read_template(inps):
    print('\n**********  Read Template File  **********')
    # default template
    inps.templateFile = os.path.join(inps.workDir, 'pysarApp_template.txt')
    if not os.path.isfile(inps.templateFile):
        print('generate default template file: '+inps.templateFile)
        with open(inps.templateFile, 'w') as f:
            f.write(TEMPLATE)
    else:
        inps.templateFile = check_obsolete_default_template(inps.templateFile)

    # custom template
    templateCustom = None
    if inps.templateFileCustom:
        # Copy custom template file to work directory
        if ut.update_file(os.path.basename(inps.templateFileCustom),
                          inps.templateFileCustom, check_readable=False):
            shutil.copy2(inps.templateFileCustom, inps.workDir)
            print('copy {} to work directory'.format(os.path.basename(inps.templateFileCustom)))

        # Read custom template
        print('read custom template file: '+inps.templateFileCustom)
        templateCustom = readfile.read_template(inps.templateFileCustom)
        # correct some loose type errors
        for key in templateCustom.keys():
            if templateCustom[key].lower() in ['default']:
                templateCustom[key] = 'auto'
            elif templateCustom[key].lower() in ['n', 'off', 'false']:
                templateCustom[key] = 'no'
            elif templateCustom[key].lower() in ['y', 'on', 'true']:
                templateCustom[key] = 'yes'
        for key in ['pysar.deramp', 'pysar.troposphericDelay.method']:
            if key in templateCustom.keys():
                templateCustom[key] = templateCustom[key].lower().replace('-', '_')
        if 'processor' in templateCustom.keys():
            templateCustom['pysar.load.processor'] = templateCustom['processor']

        # Update default template with custom input template
        print('update default template based on input custom template')
        inps.templateFile = ut.update_template_file(inps.templateFile, templateCustom)

    if inps.generate_template:
        raise SystemExit('Exit as planned after template file generation.')

    print('read default template file: '+inps.templateFile)
    template = readfile.read_template(inps.templateFile)
    template = ut.check_template_auto_value(template)

    # Get existing files name: unavco_attributes.txt
    try:
        inps.unavcoMetadataFile = ut.get_file_list('unavco_attribute*txt', abspath=True)[0]
    except:
        inps.unavcoMetadataFile = None
        print('No UNAVCO attributes file found.')

    return inps, template, templateCustom


##########################################################################
def main(iargs=None):
    start_time = time.time()
    inps = cmd_line_parse(iargs)
    if inps.version:
        raise SystemExit(version.version_description)

    #########################################
    # Initiation
    #########################################
    print(version.logo)

    # Project Name
    inps.projectName = None
    if inps.templateFileCustom:
        inps.templateFileCustom = os.path.abspath(inps.templateFileCustom)
        inps.projectName = os.path.splitext(os.path.basename(inps.templateFileCustom))[0]
        print('Project name: '+inps.projectName)

    # Work directory
    if not inps.workDir:
        if autoPath and 'SCRATCHDIR' in os.environ and inps.projectName:
            inps.workDir = os.path.join(os.getenv('SCRATCHDIR'), inps.projectName, 'PYSAR')
        else:
            inps.workDir = os.getcwd()
    inps.workDir = os.path.abspath(inps.workDir)
    if not os.path.isdir(inps.workDir):
        os.makedirs(inps.workDir)
    os.chdir(inps.workDir)
    print("Go to work directory: "+inps.workDir)

    copy_aux_file(inps)

    inps, template, templateCustom = read_template(inps)

    #########################################
    # Loading Data
    #########################################
    print('\n**********  Load Data  **********')
    loadCmd = 'load_data.py --template {}'.format(inps.templateFile)
    if inps.projectName:
        loadCmd += ' --project {}'.format(inps.projectName)
    print(loadCmd)
    status = subprocess.Popen(loadCmd, shell=True).wait()
    os.chdir(inps.workDir)

    print('-'*50)
    inps, atr = ut.check_loaded_dataset(inps.workDir, inps)

    # Add template options into HDF5 file metadata
    # if inps.templateFileCustom:
    #    atrCmd = 'add_attribute.py {} {}'.format(inps.stackFile, inps.templateFileCustom)
    #    print(atrCmd)
    #    status = subprocess.Popen(atrCmd, shell=True).wait()
    #ut.add_attribute(inps.stackFile, template)

    if inps.load_dataset:
        raise SystemExit('Exit as planned after loading/checking the dataset.')

    if inps.reset:
        print('Reset dataset attributtes for a fresh re-run.\n'+'-'*50)
        # Reset reference pixel
        refPointCmd = 'reference_point.py {} --reset'.format(inps.stackFile)
        print(refPointCmd)
        status = subprocess.Popen(refPointCmd, shell=True).wait()
        # Reset network modification
        networkCmd = 'modify_network.py {} --reset'.format(inps.stackFile)
        print(networkCmd)
        status = subprocess.Popen(networkCmd, shell=True).wait()

    #########################################
    # Generating Aux files
    #########################################
    print('\n**********  Generate Auxiliary Files  **********')
    # Initial mask (pixels with valid unwrapPhase or connectComponent in ALL interferograms)
    inps.maskFile = 'mask.h5'
    if ut.update_file(inps.maskFile, inps.stackFile):
        maskCmd = 'generate_mask.py {} --nonzero -o {}'.format(inps.stackFile,
                                                               inps.maskFile)
        print(maskCmd)
        status = subprocess.Popen(maskCmd, shell=True).wait()

    # Average spatial coherence
    inps.avgSpatialCohFile = 'avgSpatialCoherence.h5'
    if ut.update_file(inps.avgSpatialCohFile, inps.stackFile):
        avgCmd = 'temporal_average.py {} --dataset coherence -o {}'.format(inps.stackFile,
                                                                           inps.avgSpatialCohFile)
        print(avgCmd)
        status = subprocess.Popen(avgCmd, shell=True).wait()

    #########################################
    # Referencing Interferograms in Space
    #########################################
    print('\n**********  Select Reference Point  **********')
    refPointCmd = 'reference_point.py {} -t {} -c {}'.format(inps.stackFile,
                                                             inps.templateFile,
                                                             inps.avgSpatialCohFile)
    print(refPointCmd)
    status = subprocess.Popen(refPointCmd, shell=True).wait()
    if status is not 0:
        raise Exception('Error while finding reference pixel in space.\n')

    ############################################
    # Unwrapping Error Correction (Optional)
    #    based on the consistency of triplets
    #    of interferograms
    ############################################
    if template['pysar.unwrapError.method']:
        print('\n**********  Unwrapping Error Correction  **********')
        outName = '{}_unwCor.h5'.format(os.path.splitext(inps.stackFile)[0])
        unwCmd = 'unwrap_error.py {} --mask {} --template {}'.format(inps.stackFile,
                                                                     inps.maskFile,
                                                                     inps.templateFile)
        print(unwCmd)
        if ut.update_file(outName, inps.stackFile):
            print('This might take a while depending on the size of your data set!')
            status = subprocess.Popen(unwCmd, shell=True).wait()
            if status is not 0:
                raise Exception('Error while correcting phase unwrapping errors.\n')
        inps.stackFile = outName

    #########################################
    # Network Modification (Optional)
    #########################################
    print('\n**********  Modify Network  **********')
    networkCmd = 'modify_network.py {} -t {}'.format(inps.stackFile,
                                                     inps.templateFile)
    print(networkCmd)
    status = subprocess.Popen(networkCmd, shell=True).wait()
    if status is not 0:
        raise Exception('Error while modifying the network of interferograms.\n')

    # Plot network colored in spatial coherence
    print('--------------------------------------------------')
    plotCmd = 'plot_network.py {} --template {} --nodisplay'.format(inps.stackFile,
                                                                    inps.templateFile)
    print(plotCmd)
    inps.cohSpatialAvgFile = '{}_coherence_spatialAverage.txt'.format(
        os.path.splitext(os.path.basename(inps.stackFile))[0])
    if ut.update_file('Network.pdf', check_readable=False, inFile=[inps.stackFile,
                                                                   inps.cohSpatialAvgFile,
                                                                   inps.templateFile]):
        status = subprocess.Popen(plotCmd, shell=True).wait()

    if inps.modify_network:
        raise SystemExit('Exit as planned after network modification.')

    #########################################
    # Inversion of Interferograms
    ########################################
    print('\n**********  Invert Network of Interferograms into Time-series  **********')
    invCmd = 'ifgram_inversion.py {} --template {}'.format(inps.stackFile,
                                                           inps.templateFile)
    print(invCmd)
    inps.timeseriesFile = 'timeseries.h5'
    inps.tempCohFile = 'temporalCoherence.h5'
    if ut.update_file(inps.timeseriesFile, inps.stackFile):
        status = subprocess.Popen(invCmd, shell=True).wait()
        if status is not 0:
            raise Exception('Error while inverting network interferograms into timeseries')

    print('\n--------------------------------------------')
    print('Update Mask based on Temporal Coherence ...')
    inps.maskFile = 'maskTempCoh.h5'
    inps.minTempCoh = template['pysar.networkInversion.minTempCoh']
    maskCmd = 'generate_mask.py {} -m {} -o {}'.format(inps.tempCohFile,
                                                       inps.minTempCoh,
                                                       inps.maskFile)
    print(maskCmd)
    if ut.update_file(inps.maskFile, inps.tempCohFile):
        status = subprocess.Popen(maskCmd, shell=True).wait()
        if status is not 0:
            raise Exception('Error while generating mask file from temporal coherence.')

    if inps.invert_network:
        raise SystemExit('Exit as planned after network inversion.')

    # check number of pixels selected in mask file for following analysis
    min_num_pixel = float(template['pysar.networkInversion.minNumPixel'])
    msk = readfile.read(inps.maskFile)[0]
    num_pixel = np.sum(msk != 0.)
    print('number of pixels selected: {}'.format(num_pixel))
    if num_pixel < min_num_pixel:
        msg = "Not enought coherent pixels selected (minimum of {}). ".format(int(min_num_pixel))
        msg += "Try the following:\n"
        msg += "1) Check the reference pixel and make sure it's not in areas with unwrapping errors\n"
        msg += "2) Check the network and make sure it's fully connected without subsets"
        raise RuntimeError(msg)
    del msk


    ##############################################
    # LOD (Local Oscillator Drift) Correction
    #   for Envisat data in radar coord only
    ##############################################
    if atr['PLATFORM'].lower().startswith('env'):
        print('\n**********  Local Oscillator Drift Correction for Envisat  **********')
        outName = os.path.splitext(inps.timeseriesFile)[0]+'_LODcor.h5'
        lodCmd = 'local_oscilator_drift.py {} {} -o {}'.format(inps.timeseriesFile,
                                                               inps.geomFile,
                                                               outName)
        print(lodCmd)
        if ut.update_file(outName, [inps.timeseriesFile, inps.geomFile]):
            status = subprocess.Popen(lodCmd, shell=True).wait()
            if status is not 0:
                raise Exception('Error while correcting Local Oscillator Drift.\n')
        inps.timeseriesFile = outName

    ##############################################
    # Tropospheric Delay Correction (Optional)
    ##############################################
    print('\n**********  Tropospheric Delay Correction  **********')
    inps.tropPolyOrder = template['pysar.troposphericDelay.polyOrder']
    inps.tropModel     = template['pysar.troposphericDelay.weatherModel']
    inps.tropMethod    = template['pysar.troposphericDelay.method']
    try:
        fileList = [os.path.join(inps.workDir, 'INPUTS/{}.h5'.format(inps.tropModel))]
        inps.tropFile = ut.get_file_list(fileList)[0]
    except:
        inps.tropFile = None

    if inps.tropMethod:
        # Check Conflict with base_trop_cor
        if template['pysar.deramp'] == 'base_trop_cor':
            msg = """
            Method Conflict: base_trop_cor is in conflict with {} option!
            base_trop_cor applies simultaneous ramp removal AND tropospheric correction.
            IGNORE base_trop_cor input and continue pysarApp.py.
            """
            warnings.warn(msg)
            template['pysar.deramp'] = False

        fbase = os.path.splitext(inps.timeseriesFile)[0]
        # Call scripts
        if inps.tropMethod == 'height_correlation':
            outName = '{}_tropHgt.h5'.format(fbase)
            print('tropospheric delay correction with height-correlation approach')
            tropCmd = ('tropcor_phase_elevation.py {t} -d {d} -p {p}'
                       ' -m {m} -o {o}').format(t=inps.timeseriesFile,
                                                d=inps.geomFile,
                                                p=inps.tropPolyOrder,
                                                m=inps.maskFile,
                                                o=outName)
            print(tropCmd)
            if ut.update_file(outName, inps.timeseriesFile):
                status = subprocess.Popen(tropCmd, shell=True).wait()
                if status is not 0:
                    raise Exception('Error while correcting tropospheric delay.\n')
            inps.timeseriesFile = outName

        elif inps.tropMethod == 'pyaps':
            inps.weatherDir = template['pysar.troposphericDelay.weatherDir']
            outName = '{}_{}.h5'.format(fbase, inps.tropModel)
            print(('Atmospheric correction using Weather Re-analysis dataset'
                   ' (PyAPS, Jolivet et al., 2011)'))
            print('Weather Re-analysis dataset: '+inps.tropModel)
            tropCmd = ('tropcor_pyaps.py -f {t} --model {m} --dem {d}'
                       ' -i {i} -w {w}').format(t=inps.timeseriesFile,
                                                m=inps.tropModel,
                                                d=inps.geomFile,
                                                i=inps.geomFile,
                                                w=inps.weatherDir)
            print(tropCmd)
            if ut.update_file(outName, inps.timeseriesFile):
                if inps.tropFile:
                    tropCmd = 'diff.py {} {} -o {}'.format(inps.timeseriesFile,
                                                           inps.tropFile,
                                                           outName)
                    print('--------------------------------------------')
                    print('Use existed tropospheric delay file: {}'.format(inps.tropFile))
                    print(tropCmd)
                status = subprocess.Popen(tropCmd, shell=True).wait()
                if status is not 0:
                    print('\nError while correcting tropospheric delay, try the following:')
                    print('1) Check the installation of PyAPS')
                    print('   http://earthdef.caltech.edu/projects/pyaps/wiki/Main')
                    print('   Try in command line: python -c "import pyaps"')
                    print('2) Use other tropospheric correction method, height-correlation, for example')
                    print('3) or turn off the option by setting pysar.troposphericDelay.method = no.\n')
                    raise RuntimeError()
            inps.timeseriesFile = outName
        else:
            print('No atmospheric delay correction.')

    # Grab tropospheric delay file
    try:
        fileList = [os.path.join(inps.workDir, 'INPUTS/{}.h5'.format(inps.tropModel))]
        inps.tropFile = ut.get_file_list(fileList)[0]
    except:
        inps.tropFile = None

    ##############################################
    # Topographic (DEM) Residuals Correction (Optional)
    ##############################################
    print('\n**********  Topographic Residual (DEM error) Correction  **********')
    outName = os.path.splitext(inps.timeseriesFile)[0]+'_demErr.h5'
    topoCmd = 'dem_error.py {} -g {} -t {} -o {}'.format(inps.timeseriesFile,
                                                         inps.geomFile,
                                                         inps.templateFile,
                                                         outName)
    print(topoCmd)
    inps.timeseriesResFile = None
    if template['pysar.topographicResidual']:
        if ut.update_file(outName, inps.timeseriesFile):
            status = subprocess.Popen(topoCmd, shell=True).wait()
            if status is not 0:
                raise Exception('Error while correcting topographic phase residual.\n')
        inps.timeseriesFile = outName
        inps.timeseriesResFile = 'timeseriesResidual.h5'
    else:
        print('No correction for topographic residuals.')

    ##############################################
    # Timeseries Residual Standard Deviation
    ##############################################
    print('\n**********  Timeseries Residual Root Mean Square  **********')
    if inps.timeseriesResFile:
        rmsCmd = 'timeseries_rms.py {} -t {}'.format(inps.timeseriesResFile,
                                                     inps.templateFile)
        print(rmsCmd)
        status = subprocess.Popen(rmsCmd, shell=True).wait()
        if status is not 0:
            raise Exception('Error while calculating RMS of time series phase residual.\n')
    else:
        print('No timeseries residual file found! Skip residual RMS analysis.')

    ##############################################
    # Reference in Time
    ##############################################
    print('\n**********  Select Reference Date  **********')
    if template['pysar.reference.date']:
        outName = '{}_refDate.h5'.format(os.path.splitext(inps.timeseriesFile)[0])
        refCmd = 'reference_date.py {} -t {} -o {}'.format(inps.timeseriesFile,
                                                           inps.templateFile,
                                                           outName)
        print(refCmd)
        if ut.update_file(outName, inps.timeseriesFile):
            status = subprocess.Popen(refCmd, shell=True).wait()
            if status is not 0:
                raise Exception('Error while changing reference date.\n')
        inps.timeseriesFile = outName
    else:
        print('No reference change in time.')

    ##############################################
    # Phase Ramp Correction (Optional)
    ##############################################
    print('\n**********  Remove Phase Ramp  **********')
    inps.derampMaskFile = template['pysar.deramp.maskFile']
    inps.derampMethod = template['pysar.deramp']
    if inps.derampMethod:
        print('Phase Ramp Removal method: {}'.format(inps.derampMethod))
        if inps.geocoded and inps.derampMethod in ['baseline_cor', 'base_trop_cor']:
            warnings.warn(('dataset is in geo coordinates,'
                           ' can not apply {} method').format(inps.derampMethod))
            print('skip deramping and continue.')

        # Get executable command and output name
        derampCmd = None
        fbase = os.path.splitext(inps.timeseriesFile)[0]
        if inps.derampMethod in ['plane', 'quadratic', 'plane_range', 'quadratic_range',
                                 'plane_azimuth', 'quadratic_azimuth']:
            outName = '{}_{}.h5'.format(fbase, inps.derampMethod)
            derampCmd = 'remove_ramp.py {} -s {} -m {} -o {}'.format(inps.timeseriesFile,
                                                                     inps.derampMethod,
                                                                     inps.derampMaskFile,
                                                                     outName)

        elif inps.derampMethod == 'baseline_cor':
            outName = '{}_baselineCor.h5'.format(fbase)
            derampCmd = 'baseline_error.py {} {}'.format(inps.timeseriesFile,
                                                         inps.maskFile)

        elif inps.derampMethod in ['base_trop_cor', 'basetropcor', 'baselinetropcor']:
            print('Joint estimation of Baseline error and tropospheric delay')
            print('\t[height-correlation approach]')
            outName = '{}_baseTropCor.h5'.format(fbase)
            derampCmd = ('baseline_trop.py {t} {d} {p}'
                         ' range_and_azimuth {m}').format(t=inps.timeseriesFile,
                                                          d=inps.geomFile,
                                                          p=inps.tropPolyOrder,
                                                          m=inps.maskFile)
        else:
            warnings.warn('Unrecognized phase ramp method: {}'.format(template['pysar.deramp']))

        # Execute command
        if derampCmd:
            print(derampCmd)
            if ut.update_file(outName, inps.timeseriesFile):
                status = subprocess.Popen(derampCmd, shell=True).wait()
                if status is not 0:
                    raise Exception('Error while removing phase ramp for time-series.\n')
            inps.timeseriesFile = outName
    else:
        print('No phase ramp removal.')

    #############################################
    # Velocity and rmse maps
    #############################################
    print('\n**********  Estimate Velocity  **********')
    inps.velFile = 'velocity.h5'
    velCmd = 'timeseries2velocity.py {} -t {} -o {}'.format(inps.timeseriesFile,
                                                            inps.templateFile,
                                                            inps.velFile)
    print(velCmd)
    if ut.update_file(inps.velFile, [inps.timeseriesFile, inps.templateFile]):
        status = subprocess.Popen(velCmd, shell=True).wait()
        if status is not 0:
            raise Exception('Error while estimating linear velocity from time-series.\n')

    # Velocity from Tropospheric delay
    if inps.tropFile:
        suffix = os.path.splitext(os.path.basename(inps.tropFile))[0].title()
        inps.tropVelFile = '{}{}.h5'.format(os.path.splitext(inps.velFile)[0], suffix)
        velCmd = 'timeseries2velocity.py {} -t {} -o {}'.format(inps.tropFile,
                                                                inps.templateFile,
                                                                inps.tropVelFile)
        print(velCmd)
        if ut.update_file(inps.tropVelFile, [inps.tropFile, inps.templateFile]):
            status = subprocess.Popen(velCmd, shell=True).wait()

    ############################################
    # Post-processing
    # Geocodeing --> Masking --> KMZ & HDF-EOS5
    ############################################
    print('\n**********  Post-processing  **********')
    if template['pysar.save.hdfEos5'] is True and template['pysar.geocode'] is False:
        print('Turn ON pysar.geocode to be able to save to HDF-EOS5 format.')
        template['pysar.geocode'] = True

    # Geocoding
    if not inps.geocoded:
        if template['pysar.geocode'] is True:
            print('\n--------------------------------------------')
            geo_dir = os.path.abspath('./GEOCODE')
            if not os.path.isdir(geo_dir):
                os.makedirs(geo_dir)
                print('create directory: {}'.format(geo_dir))
            geoCmd = ('geocode.py {v} {c} {t} {g} -l {l} -t {e}'
                      ' --outdir {d} --update').format(v=inps.velFile,
                                                       c=inps.tempCohFile,
                                                       t=inps.timeseriesFile,
                                                       g=inps.geomFile,
                                                       l=inps.lookupFile,
                                                       e=inps.templateFile,
                                                       d=geo_dir)
            print(geoCmd)
            status = subprocess.Popen(geoCmd, shell=True).wait()
            if status is not 0:
                raise Exception('Error while geocoding.\n')
            else:
                inps.velFile        = os.path.join(geo_dir, 'geo_'+os.path.basename(inps.velFile))
                inps.tempCohFile    = os.path.join(geo_dir, 'geo_'+os.path.basename(inps.tempCohFile))
                inps.timeseriesFile = os.path.join(geo_dir, 'geo_'+os.path.basename(inps.timeseriesFile))
                inps.geomFile       = os.path.join(geo_dir, 'geo_'+os.path.basename(inps.geomFile))
                inps.geocoded = True

            # generate mask based on geocoded temporal coherence
            print('\n--------------------------------------------')
            outName = os.path.join(geo_dir, 'geo_maskTempCoh.h5')
            genCmd = 'generate_mask.py {} -m {} -o {}'.format(inps.tempCohFile,
                                                              inps.minTempCoh,
                                                              outName)
            print(genCmd)
            if ut.update_file(outName, inps.tempCohFile):
                status = subprocess.Popen(genCmd, shell=True).wait()
            inps.maskFile = outName

    # mask velocity file
    if inps.velFile and inps.maskFile:
        outName = '{}_masked.h5'.format(os.path.splitext(inps.velFile)[0])
        maskCmd = 'mask.py {} -m {} -o {}'.format(inps.velFile,
                                                  inps.maskFile,
                                                  outName)
        print(maskCmd)
        if ut.update_file(outName, [inps.velFile, inps.maskFile]):
            status = subprocess.Popen(maskCmd, shell=True).wait()
        try:
            inps.velFile = glob.glob(outName)[0]
        except:
            inps.velFile = None

    # Save to Google Earth KML file
    if inps.geocoded and inps.velFile and template['pysar.save.kml'] is True:
        print('\n--------------------------------------------')
        print('creating Google Earth KMZ file for geocoded velocity file: ...')
        outName = '{}.kmz'.format(os.path.splitext(os.path.basename(inps.velFile))[0])
        kmlCmd = 'save_kml.py {} -o {}'.format(inps.velFile, outName)
        print(kmlCmd)
        if ut.update_file(outName, inps.velFile, check_readable=False):
            status = subprocess.Popen(kmlCmd, shell=True).wait()
            if status is not 0:
                raise Exception('Error while generating Google Earth KMZ file.')

    #############################################
    # Save Timeseries to HDF-EOS5 format
    #############################################
    if template['pysar.save.hdfEos5'] is True:
        print('\n**********  Save Time-series in HDF-EOS5 Format  **********')
        if not inps.geocoded:
            warnings.warn('Dataset is in radar coordinates, skip saving to HDF-EOS5 format.')
        else:
            # Add attributes from custom template to timeseries file
            if templateCustom is not None:
                ut.add_attribute(inps.timeseriesFile, templateCustom)

            # Save to HDF-EOS5 format
            print('--------------------------------------------')
            hdfeos5Cmd = ('save_hdfeos5.py {t} -c {c} -m {m} -g {g}'
                          ' -t {e}').format(t=inps.timeseriesFile,
                                            c=inps.tempCohFile,
                                            m=inps.maskFile,
                                            g=inps.geomFile,
                                            e=inps.templateFile)
            print(hdfeos5Cmd)
            SAT = hdfeos5.get_mission_name(atr)
            try:
                inps.hdfeos5File = ut.get_file_list('{}_*.he5'.format(SAT))[0]
            except:
                inps.hdfeos5File = None
            if ut.update_file(inps.hdfeos5File, [inps.timeseriesFile,
                                                 inps.tempCohFile,
                                                 inps.maskFile,
                                                 inps.geomFile]):
                status = subprocess.Popen(hdfeos5Cmd, shell=True).wait()
                if status is not 0:
                    raise Exception('Error while generating HDF-EOS5 time-series file.\n')

    #############################################
    # Plot Figures
    #############################################
    inps.plotShellFile = os.path.join(os.path.dirname(__file__), '../sh/plot_pysarApp.sh')
    plotCmd = './'+os.path.basename(inps.plotShellFile)
    inps.plot = template['pysar.plot']
    if inps.plot is True:
        print('\n**********  Plot Results / Save to PIC  **********')
        # Copy to workding directory if not existed yet.
        if not os.path.isfile(plotCmd):
            print('copy {} to work directory: {}'.format(inps.plotShellFile, inps.workDir))
            shutil.copy2(inps.plotShellFile, inps.workDir)

    if inps.plot and os.path.isfile(plotCmd):
        print(plotCmd)
        status = subprocess.Popen(plotCmd, shell=True).wait()
        print('\n'+'-'*50)
        print('For better figures:')
        print('  1) Edit parameters in plot_pysarApp.sh and re-run this script.')
        print('  2) Play with view.py, tsview.py and save_kml.py for more advanced/customized figures.')
        if status is not 0:
            raise Exception('Error while plotting data files using {}'.format(plotCmd))

    #############################################
    # Time                                      #
    #############################################
    m, s = divmod(time.time()-start_time, 60)
    print('\ntime used: {:02.0f} mins {:02.1f} secs'.format(m, s))
    print('\n###############################################')
    print('End of PySAR processing!')
    print('################################################\n')


###########################################################################################
if __name__ == '__main__':
    main()
