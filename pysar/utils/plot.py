############################################################
# Program is part of PySAR                                 #
# Copyright(c) 2018, Zhang Yunjun                          #
# Author:  Zhang Yunjun, 2018                              #
############################################################
# Recommend import:
#     from pysar.utils import plot as pp


import os
import warnings
import datetime
import numpy as np
from scipy import ndimage

import matplotlib as mpl
from matplotlib import ticker, dates as mdates, lines as mlines, pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LightSource
from matplotlib.offsetbox import AnchoredText
from matplotlib.patheffects import withStroke
from mpl_toolkits.axes_grid1 import make_axes_locatable
from mpl_toolkits.basemap import Basemap, cm, pyproj

from pysar.utils import ptime, readfile, network as pnet, utils as ut
from pysar.objects import timeseriesKeyNames


mplColors = ['#1f77b4',
             '#ff7f0e',
             '#2ca02c',
             '#d62728',
             '#9467bd',
             '#8c564b',
             '#e377c2',
             '#7f7f7f',
             '#bcbd22',
             '#17becf']

min_figsize_single = 6.0       # default min size in inch, for single plot
max_figsize_single = 10.0      # default min size in inch, for single plot
# default size in inch, for multiple subplots
default_figsize_multi = [15.0, 8.0]
max_figsize_height = 8.0       # max figure size in vertical direction in inch


############################################ Class Begein ###############################################
class BasemapExt(Basemap):
    """
    Extend Basemap class to add drawscale(), because Basemap.drawmapscale() do not support 'cyl' projection.
    """

    def draw_scale_bar(self, lat_c, lon_c, distance, ax=None, font_size=12, yoffset=None, color='k'):
        """draw a simple map scale from x1,y to x2,y in map projection coordinates, label it with actual distance
        ref_link: http://matplotlib.1069221.n5.nabble.com/basemap-scalebar-td14133.html
        Parameters: lat_c/lon_c : float, longitude and latitude of scale bar center, in degree
                    distance    : float, distance of scale bar, in m
                    yoffset     : float, optional, scale bar length at two ends, in degree
        Example:    m.drawscale(33.06, 131.18, 2000)
        """
        gc = pyproj.Geod(a=self.rmajor, b=self.rminor)
        if distance > 1000.0:
            distance = np.rint(distance/1000.0)*1000.0
        lon_c2, lat_c2, az21 = gc.fwd(lon_c, lat_c, 90, distance)
        length = np.abs(lon_c - lon_c2)
        lon0 = lon_c - length/2.0
        lon1 = lon_c + length/2.0
        if not yoffset:
            yoffset = 0.1*length

        self.plot([lon0, lon1], [lat_c, lat_c], color=color)
        self.plot([lon0, lon0], [lat_c, lat_c+yoffset], color=color)
        self.plot([lon1, lon1], [lat_c, lat_c+yoffset], color=color)
        if not ax:
            ax = plt.gca()
        if distance < 1000.0:
            ax.text(lon0+0.5*length, lat_c+yoffset*3, '%d m' % (distance),
                    verticalalignment='top', horizontalalignment='center', fontsize=font_size, color=color)
        else:
            ax.text(lon0+0.5*length, lat_c+yoffset*3, '%d km' % (distance/1000.0),
                    verticalalignment='top', horizontalalignment='center', fontsize=font_size, color=color)

    def draw_lalo_label(self, geo_box, ax=None, lalo_step=None, labels=[1, 0, 0, 1], font_size=12, color='k'):
        """Auto draw lat/lon label/tick based on coverage from geo_box
        Inputs:
            geo_box : 4-tuple of float, defining UL_lon, UL_lat, LR_lon, LR_lat coordinate
            labels  : list of 4 int, positions where the labels are drawn as in [left, right, top, bottom]
                      default: [1,0,0,1]
            ax      : axes object the labels are drawn
            draw    : bool, do not draw if False
        Outputs:

        Example:
            geo_box = (128.0, 37.0, 138.0, 30.0)
            m.draw_lalo_label(geo_box)
        """
        lats, lons, step = self.auto_lalo_sequence(geo_box, lalo_step=lalo_step)

        digit = np.int(np.floor(np.log10(step)))
        fmt = '%.'+'%d' % (abs(min(digit, 0)))+'f'
        # Change the 2 lines below for customized label
        #lats = np.linspace(31.55, 31.60, 2)
        #lons = np.linspace(130.60, 130.70, 3)

        # Plot x/y tick without label
        if not ax:
            ax = plt.gca()
        ax.tick_params(which='both', direction='in', labelsize=font_size,
                       bottom=True, top=True, left=True, right=True)

        ax.set_xticks(lons)
        ax.set_yticks(lats)
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        # ax.xaxis.tick_top()

        # Plot x/y label
        labels_lat = np.multiply(labels, [1, 1, 0, 0])
        labels_lon = np.multiply(labels, [0, 0, 1, 1])
        self.drawparallels(lats, fmt=fmt, labels=labels_lat, linewidth=0.05,
                           fontsize=font_size, color=color, textcolor=color)
        self.drawmeridians(lons, fmt=fmt, labels=labels_lon, linewidth=0.05,
                           fontsize=font_size, color=color, textcolor=color)

    def auto_lalo_sequence(self, geo_box, lalo_step=None, max_tick_num=4, step_candidate=[1, 2, 3, 4, 5]):
        """Auto calculate lat/lon label sequence based on input geo_box
        Inputs:
            geo_box        : 4-tuple of float, defining UL_lon, UL_lat, LR_lon, LR_lat coordinate
            max_tick_num   : int, rough major tick number along the longer axis
            step_candidate : list of int, candidate list for the significant number of step
        Outputs:
            lats/lons : np.array of float, sequence of lat/lon auto calculated from input geo_box
            lalo_step : float, lat/lon label step
        Example:
            geo_box = (128.0, 37.0, 138.0, 30.0)
            lats, lons, step = m.auto_lalo_sequence(geo_box)
        """
        max_lalo_dist = max([geo_box[1]-geo_box[3], geo_box[2]-geo_box[0]])

        if not lalo_step:
            # Initial tick step
            lalo_step = ut.round_to_1(max_lalo_dist/max_tick_num)

            # Final tick step - choose from candidate list
            digit = np.int(np.floor(np.log10(lalo_step)))
            lalo_step_candidate = [i*10**digit for i in step_candidate]
            distance = [(i - max_lalo_dist/max_tick_num) ** 2
                        for i in lalo_step_candidate]
            lalo_step = lalo_step_candidate[distance.index(min(distance))]
        print('label step - '+str(lalo_step)+' degree')

        # Auto tick sequence
        digit = np.int(np.floor(np.log10(lalo_step)))
        lat_major = np.ceil(geo_box[3]/10**(digit+1))*10**(digit+1)
        lats = np.unique(np.hstack((np.arange(lat_major, lat_major-10.*max_lalo_dist, -lalo_step),
                                    np.arange(lat_major, lat_major+10.*max_lalo_dist, lalo_step))))
        lats = np.sort(lats[np.where(np.logical_and(lats >= geo_box[3], lats <= geo_box[1]))])

        lon_major = np.ceil(geo_box[0]/10**(digit+1))*10**(digit+1)
        lons = np.unique(np.hstack((np.arange(lon_major, lon_major-10.*max_lalo_dist, -lalo_step),
                                    np.arange(lon_major, lon_major+10.*max_lalo_dist, lalo_step))))
        lons = np.sort(lons[np.where(np.logical_and(lons >= geo_box[0], lons <= geo_box[2]))])

        return lats, lons, lalo_step


############################################ Plot Utilities #############################################
def discrete_cmap(N, base_cmap=None):
    """Create an N-bin discrete colormap from the specified input map
    Reference: https://gist.github.com/jakevdp/91077b0cae40f8f8244a
    """

    # Note that if base_cmap is a string or None, you can simply do
    #    return plt.cm.get_cmap(base_cmap, N)
    # The following works for string, None, or a colormap instance:

    base = plt.cm.get_cmap(base_cmap)
    color_list = base(np.linspace(0, 1, N))
    cmap_name = base.name + str(N)
    return base.from_list(cmap_name, color_list, N)


def add_inner_title(ax, title, loc, size=None, **kwargs):
    if size is None:
        size = dict(size=plt.rcParams['legend.fontsize'])
    at = AnchoredText(title, loc=loc, prop=size,
                      pad=0., borderpad=0.5,
                      frameon=False, **kwargs)
    ax.add_artist(at)
    at.txt._text.set_path_effects([withStroke(foreground="w", linewidth=3)])
    return at


def auto_figure_title(fname, datasetNames=[], inps_dict=None):
    """Get auto figure title from meta dict and input options
    Parameters: fname : str, input file name
                datasetNames : list of str, optional, dataset to read for multi dataset/group files
                inps_dict : dict, optional, processing attributes, including:
                    ref_date
                    pix_box
                    wrap
                    opposite
    Returns:    fig_title : str, output figure title
    Example:    'geo_velocity.h5' = auto_figure_title('geo_velocity.h5', None, vars(inps))
                '101020-110220_ECMWF_demErr_quadratic' = auto_figure_title('timeseries_ECMWF_demErr_quadratic.h5', '110220')
    """
    if not datasetNames:
        datasetNames = []
    if isinstance(datasetNames, str):
        datesetNames = [datasetNames]

    atr = readfile.read_attribute(fname)
    k = atr['FILE_TYPE']
    num_pixel = int(atr['WIDTH']) * int(atr['LENGTH'])

    if k == 'ifgramStack':
        if len(datasetNames) == 1:
            fig_title = datasetNames[0]
            if 'unwCor' in fname:
                fig_title += '_unwCor'
        else:
            fig_title = datasetNames[0].split('-')[0]

    elif len(datasetNames) == 1 and k in timeseriesKeyNames:
        if 'ref_date' in inps_dict.keys():
            ref_date = inps_dict['ref_date']
        elif 'REF_DATE' in atr.keys():
            ref_date = atr['REF_DATE']
        else:
            ref_date = None

        if not ref_date:
            fig_title = datasetNames[0]
        else:
            fig_title = '{}_{}'.format(ref_date, datasetNames[0])

        try:
            ext = os.path.splitext(fname)[1]
            processMark = os.path.basename(fname).split(
                'timeseries')[1].split(ext)[0]
            fig_title += processMark
        except:
            pass
    elif k == 'geometry':
        if len(datasetNames) == 1:
            fig_title = datasetNames[0]
        elif datasetNames[0].startswith('bperp'):
            fig_title = 'bperp'
        else:
            fig_title = os.path.splitext(os.path.basename(fname))[0]
    else:
        fig_title = os.path.splitext(os.path.basename(fname))[0]

    if 'pix_box' in inps_dict.keys():
        box = inps_dict['pix_box']
        if (box[2] - box[0]) * (box[3] - box[1]) < num_pixel:
            fig_title += '_sub'

    if 'wrap' in inps_dict.keys() and inps_dict['wrap']:
        fig_title += '_wrap'

    if 'opposite' in inps_dict.keys() and inps_dict['opposite']:
        fig_title += '_oppo'

    return fig_title


def auto_flip_direction(metadata):
    """Check flip left-right and up-down based on attribute dict, for radar-coded file only"""
    # default value
    flip_lr = False
    flip_ud = False

    # auto flip for file in radar coordinates
    if 'Y_FIRST' not in metadata.keys() and 'ORBIT_DIRECTION' in metadata.keys():
        print('{} orbit'.format(metadata['ORBIT_DIRECTION']))
        if metadata['ORBIT_DIRECTION'].lower().startswith('a'):
            flip_ud = True
        else:
            flip_lr = True
    return flip_lr, flip_ud


def auto_row_col_num(subplot_num, data_shape, fig_size, fig_num=1):
    """Get optimal row and column number given figure size number of subplots
    Parameters: subplot_num : int, total number of subplots
                data_shape : list of 2 float, data size in pixel in row and column direction of each plot
                fig_size : list of 2 float, figure window size in inches
                fig_num : int, number of figure windows, optional, default = 1.
    Returns:    row_num : number of subplots in row    direction per figure
                col_num : number of subplots in column direction per figure
    """
    subplot_num_per_fig = int(np.ceil(float(subplot_num) / float(fig_num)))

    data_shape_ratio = float(data_shape[0]) / float(data_shape[1])
    num_ratio = fig_size[1] / fig_size[0] / data_shape_ratio
    row_num = np.sqrt(subplot_num_per_fig * num_ratio)
    col_num = np.sqrt(subplot_num_per_fig / num_ratio)
    while np.rint(row_num) * np.rint(col_num) < subplot_num_per_fig:
        if row_num % 1 > col_num % 1:
            row_num += 0.5
        else:
            col_num += 0.5
    row_num = int(np.rint(row_num))
    col_num = int(np.rint(col_num))
    return row_num, col_num


def check_colormap_input(metadata, colormap=None, datasetName=None):
    gray_dataset_key_words = ['coherence', 'temporal_coherence', 'connectComponent',
                              '.cor', '.mli', '.slc', '.amp', '.ramp']
    if not colormap:
        if any(i in gray_dataset_key_words for i in [metadata['FILE_TYPE'], str(datasetName).split('-')[0]]):
            colormap = 'gray'
        else:
            colormap = 'jet'
    print('colormap: '+colormap)

    # Modified hsv colormap by H. Fattahi
    if colormap == 'hsv':
        cdict1 = {'red':   ((0.0, 0.0, 0.0),
                            (0.5, 0.0, 0.0),
                            (0.6, 1.0, 1.0),
                            (0.8, 1.0, 1.0),
                            (1.0, 0.5, 0.5)),
                  'green': ((0.0, 0.0, 0.0),
                            (0.2, 0.0, 0.0),
                            (0.4, 1.0, 1.0),
                            (0.6, 1.0, 1.0),
                            (0.8, 0.0, 0.0),
                            (1.0, 0.0, 0.0)),
                  'blue':  ((0.0, 0.5, .5),
                            (0.2, 1.0, 1.0),
                            (0.4, 1.0, 1.0),
                            (0.5, 0.0, 0.0),
                            (1.0, 0.0, 0.0),)
                  }
        colormap = LinearSegmentedColormap('BlueRed1', cdict1)
    else:
        colormap = plt.get_cmap(colormap)
    return colormap


def auto_adjust_xaxis_date(ax, datevector, fontSize=12, every_year=1):
    """Adjust X axis
    Input:
        ax : matplotlib figure axes object
        datevector : list of float, date in years
                     i.e. [2007.013698630137, 2007.521917808219, 2007.6463470319634]
    Output:
        ax  - matplotlib figure axes object
        dss - datetime.date object, xmin
        dee - datetime.date object, xmax
    """
    # Min/Max
    ts = datevector[0]  - 0.2;  ys=int(ts);  ms=int((ts - ys) * 12.0)
    te = datevector[-1] + 0.3;  ye=int(te);  me=int((te - ye) * 12.0)
    if ms > 12:   ys = ys + 1;   ms = 1
    if me > 12:   ye = ye + 1;   me = 1
    if ms < 1:    ys = ys - 1;   ms = 12
    if me < 1:    ye = ye - 1;   me = 12
    dss = datetime.date(ys, ms, 1)
    dee = datetime.date(ye, me, 1)
    ax.set_xlim(dss, dee)

    # Label/Tick format
    ax.fmt_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M:%S')
    ax.xaxis.set_major_locator(mdates.YearLocator(every_year))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())

    # Label font size
    for tick in ax.xaxis.get_major_ticks():
        tick.label.set_fontsize(fontSize)
    # fig2.autofmt_xdate()     #adjust x overlap by rorating, may enble again
    return ax, dss, dee


def auto_adjust_yaxis(ax, dataList, fontSize=12, ymin=None, ymax=None):
    """Adjust Y axis
    Input:
        ax       : matplot figure axes object
        dataList : list of float, value in y axis
        fontSize : float, font size
        ymin     : float, lower y axis limit
        ymax     : float, upper y axis limit
    Output:
        ax
    """
    # Min/Max
    dataRange = max(dataList) - min(dataList)
    if ymin is None:
        ymin = min(dataList) - 0.1*dataRange
    if ymax is None:
        ymax = max(dataList) + 0.1*dataRange
    ax.set_ylim([ymin, ymax])
    # Tick/Label setting
    #xticklabels = plt.getp(ax, 'xticklabels')
    #yticklabels = plt.getp(ax, 'yticklabels')
    #plt.setp(yticklabels, 'color', 'k', fontsize=fontSize)
    #plt.setp(xticklabels, 'color', 'k', fontsize=fontSize)

    return ax


####################################### Plot ################################################
def plot_coherence_history(ax, date12List, cohList, plot_dict={}):
    """Plot min/max Coherence of all interferograms for each date"""
    # Figure Setting
    if not 'fontsize'    in plot_dict.keys():   plot_dict['fontsize']    = 12
    if not 'linewidth'   in plot_dict.keys():   plot_dict['linewidth']   = 2
    if not 'markercolor' in plot_dict.keys():   plot_dict['markercolor'] = 'orange'
    if not 'markersize'  in plot_dict.keys():   plot_dict['markersize']  = 16
    if not 'disp_title'  in plot_dict.keys():   plot_dict['disp_title']  = True
    if not 'every_year'  in plot_dict.keys():   plot_dict['every_year']  = 1

    # Get date list
    date12List = ptime.yyyymmdd_date12(date12List)
    m_dates = [date12.split('_')[0] for date12 in date12List]
    s_dates = [date12.split('_')[1] for date12 in date12List]
    dateList = sorted(ptime.yyyymmdd(list(set(m_dates + s_dates))))

    dates, datevector = ptime.date_list2vector(dateList)
    bar_width = ut.most_common(np.diff(dates).tolist())*3/4
    x_list = [i-bar_width/2 for i in dates]

    coh_mat = pnet.coherence_matrix(date12List, cohList)

    ax.bar(x_list, np.nanmax(coh_mat, axis=0), bar_width.days, label='Max Coherence')
    ax.bar(x_list, np.nanmin(coh_mat, axis=0), bar_width.days, label='Min Coherence')

    if plot_dict['disp_title']:
        ax.set_title('Coherence History of All Related Interferograms')

    ax = auto_adjust_xaxis_date(ax, datevector, plot_dict['fontsize'],
                                every_year=plot_dict['every_year'])[0]
    ax.set_ylim([0.0, 1.0])

    ax.set_xlabel('Time [years]', fontsize=plot_dict['fontsize'])
    ax.set_ylabel('Coherence', fontsize=plot_dict['fontsize'])
    ax.legend(loc='lower right')

    return ax


def plot_network(ax, date12List, dateList, pbaseList, plot_dict={}, date12List_drop=[], print_msg=True):
    """Plot Temporal-Perp baseline Network
    Inputs
        ax : matplotlib axes object
        date12List : list of string for date12 in YYYYMMDD_YYYYMMDD format
        dateList   : list of string, for date in YYYYMMDD format
        pbaseList  : list of float, perp baseline, len=number of acquisition
        plot_dict   : dictionary with the following items:
                      fontsize
                      linewidth
                      markercolor
                      markersize

                      cohList : list of float, coherence value of each interferogram, len = number of ifgrams
                      disp_min/max :  float, min/max range of the color display based on cohList
                      colormap : string, colormap name
                      coh_thres : float, coherence of where to cut the colormap for display
                      disp_title : bool, show figure title or not, default: True
                      disp_drop: bool, show dropped interferograms or not, default: True
    Output
        ax : matplotlib axes object
    """

    # Figure Setting
    if not 'fontsize'    in plot_dict.keys():   plot_dict['fontsize']    = 12
    if not 'linewidth'   in plot_dict.keys():   plot_dict['linewidth']   = 2
    if not 'markercolor' in plot_dict.keys():   plot_dict['markercolor'] = 'orange'
    if not 'markersize'  in plot_dict.keys():   plot_dict['markersize']  = 16

    # For colorful display of coherence
    if not 'cohList'     in plot_dict.keys():  plot_dict['cohList']    = None
    if not 'cbar_label'  in plot_dict.keys():  plot_dict['cbar_label'] = 'Average Spatial Coherence'
    if not 'disp_min'    in plot_dict.keys():  plot_dict['disp_min']   = 0.2
    if not 'disp_max'    in plot_dict.keys():  plot_dict['disp_max']   = 1.0
    if not 'colormap'    in plot_dict.keys():  plot_dict['colormap']   = 'RdBu'
    if not 'disp_title'  in plot_dict.keys():  plot_dict['disp_title'] = True
    if not 'coh_thres'   in plot_dict.keys():  plot_dict['coh_thres']  = None
    if not 'disp_drop'   in plot_dict.keys():  plot_dict['disp_drop']  = True
    if not 'every_year'  in plot_dict.keys():  plot_dict['every_year'] = 1

    cohList = plot_dict['cohList']
    disp_min = plot_dict['disp_min']
    disp_max = plot_dict['disp_max']
    coh_thres = plot_dict['coh_thres']
    transparency = 0.7

    # Date Convert
    dateList = ptime.yyyymmdd(sorted(dateList))
    dates, datevector = ptime.date_list2vector(dateList)
    tbaseList = ptime.date_list2tbase(dateList)[0]

    ## maxBperp and maxBtemp
    date12List = ptime.yyyymmdd_date12(date12List)
    ifgram_num = len(date12List)
    pbase12 = np.zeros(ifgram_num)
    tbase12 = np.zeros(ifgram_num)
    for i in range(ifgram_num):
        m_date, s_date = date12List[i].split('_')
        m_idx = dateList.index(m_date)
        s_idx = dateList.index(s_date)
        pbase12[i] = pbaseList[s_idx] - pbaseList[m_idx]
        tbase12[i] = tbaseList[s_idx] - tbaseList[m_idx]
    if print_msg:
        print('max perpendicular baseline: {:.2f} m'.format(np.max(np.abs(pbase12))))
        print('max temporal      baseline: {} days'.format(np.max(tbase12)))

    ## Keep/Drop - date12
    date12List_keep = sorted(list(set(date12List) - set(date12List_drop)))
    idx_date12_keep = [date12List.index(i) for i in date12List_keep]
    idx_date12_drop = [date12List.index(i) for i in date12List_drop]
    if not date12List_drop:
        plot_dict['disp_drop'] = False

    ## Keep/Drop - date
    m_dates = [i.split('_')[0] for i in date12List_keep]
    s_dates = [i.split('_')[1] for i in date12List_keep]
    dateList_keep = ptime.yyyymmdd(sorted(list(set(m_dates + s_dates))))
    dateList_drop = sorted(list(set(dateList) - set(dateList_keep)))
    idx_date_keep = [dateList.index(i) for i in dateList_keep]
    idx_date_drop = [dateList.index(i) for i in dateList_drop]

    # Ploting
    # ax=fig.add_subplot(111)
    # Colorbar when conherence is colored
    if cohList is not None:
        data_min = min(cohList)
        data_max = max(cohList)
        # Normalize
        normalization = False
        if normalization:
            cohList = [(coh-data_min) / (data_min-data_min) for coh in cohList]
            disp_min = data_min
            disp_max = data_max

        if print_msg:
            print('showing coherence')
            print(('colormap: '+plot_dict['colormap']))
            print(('display range: '+str([disp_min, disp_max])))
            print(('data    range: '+str([data_min, data_max])))

        splitColormap = True
        if splitColormap:
            # Use lower/upper part of colormap to emphasis dropped interferograms
            if not coh_thres:
                # Find proper cut percentage so that all keep pairs are blue and drop pairs are red
                cohList_keep = [cohList[i] for i in idx_date12_keep]
                cohList_drop = [cohList[i] for i in idx_date12_drop]
                if cohList_drop:
                    coh_thres = max(cohList_drop)
                else:
                    coh_thres = min(cohList_keep)
            if coh_thres < disp_min:
                disp_min = 0.0
                if print_msg:
                    print('data range exceed orginal display range, set new display range to: [0.0, %f]' % (disp_max))
            c1_num = np.ceil(200.0 * (coh_thres - disp_min) / (disp_max - disp_min)).astype('int')
            coh_thres = c1_num / 200.0 * (disp_max-disp_min) + disp_min
            cmap = plt.get_cmap(plot_dict['colormap'])
            colors1 = cmap(np.linspace(0.0, 0.3, c1_num))
            colors2 = cmap(np.linspace(0.6, 1.0, 200 - c1_num))
            cmap = LinearSegmentedColormap.from_list('truncate_RdBu', np.vstack((colors1, colors2)))
            if print_msg:
                print(('color jump at '+str(coh_thres)))
        else:
            cmap = plt.get_cmap(plot_dict['colormap'])

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", "3%", pad="3%")
        norm = mpl.colors.Normalize(vmin=disp_min, vmax=disp_max)
        cbar = mpl.colorbar.ColorbarBase(cax, cmap=cmap, norm=norm)
        cbar.set_label(plot_dict['cbar_label'], fontsize=plot_dict['fontsize'])

        # plot low coherent ifgram first and high coherence ifgram later
        cohList_keep = [cohList[date12List.index(i)] for i in date12List_keep]
        date12List_keep = [x for _, x in sorted(zip(cohList_keep, date12List_keep))]

    # Dot - SAR Acquisition
    if idx_date_keep:
        x_list = [dates[i] for i in idx_date_keep]
        y_list = [pbaseList[i] for i in idx_date_keep]
        ax.plot(x_list, y_list, 'ko', alpha=0.7,
                ms=plot_dict['markersize'], mfc=plot_dict['markercolor'])
    if idx_date_drop:
        x_list = [dates[i] for i in idx_date_drop]
        y_list = [pbaseList[i] for i in idx_date_drop]
        ax.plot(x_list, y_list, 'ko', alpha=0.7,
                ms=plot_dict['markersize'], mfc='gray')

    ## Line - Pair/Interferogram
    # interferograms dropped
    if plot_dict['disp_drop']:
        for date12 in date12List_drop:
            date1, date2 = date12.split('_')
            idx1 = dateList.index(date1)
            idx2 = dateList.index(date2)
            x = np.array([dates[idx1], dates[idx2]])
            y = np.array([pbaseList[idx1], pbaseList[idx2]])
            if cohList is not None:
                coh = cohList[date12List.index(date12)]
                coh_idx = (coh - disp_min) / (disp_max - disp_min)
                ax.plot(x, y, '--', lw=plot_dict['linewidth'],
                        alpha=transparency, c=cmap(coh_idx))
            else:
                ax.plot(x, y, '--', lw=plot_dict['linewidth'],
                        alpha=transparency, c='k')

    # interferograms kept
    for date12 in date12List_keep:
        date1, date2 = date12.split('_')
        idx1 = dateList.index(date1)
        idx2 = dateList.index(date2)
        x = np.array([dates[idx1], dates[idx2]])
        y = np.array([pbaseList[idx1], pbaseList[idx2]])
        if cohList is not None:
            coh = cohList[date12List.index(date12)]
            coh_idx = (coh - disp_min) / (disp_max - disp_min)
            ax.plot(x, y, '-', lw=plot_dict['linewidth'],
                    alpha=transparency, c=cmap(coh_idx))
        else:
            ax.plot(x, y, '-', lw=plot_dict['linewidth'],
                    alpha=transparency, c='k')

    if plot_dict['disp_title']:
        ax.set_title('Interferogram Network', fontsize=plot_dict['fontsize'])

    # axis format
    ax = auto_adjust_xaxis_date(ax, datevector, plot_dict['fontsize'],
                                every_year=plot_dict['every_year'])[0]
    ax = auto_adjust_yaxis(ax, pbaseList, plot_dict['fontsize'])
    ax.set_xlabel('Time [years]', fontsize=plot_dict['fontsize'])
    ax.set_ylabel('Perp Baseline [m]', fontsize=plot_dict['fontsize'])

    # Legend
    if plot_dict['disp_drop']:
        solid_line = mlines.Line2D([], [], color='k', ls='solid', label='Interferograms')
        dash_line = mlines.Line2D([], [], color='k', ls='dashed', label='Interferograms dropped')
        ax.legend(handles=[solid_line, dash_line])

    return ax


def plot_perp_baseline_hist(ax, dateList, pbaseList, plot_dict={}, dateList_drop=[]):
    """ Plot Perpendicular Spatial Baseline History
    Inputs
        ax : matplotlib axes object
        dateList : list of string, date in YYYYMMDD format
        pbaseList : list of float, perp baseline 
        plot_dict : dictionary with the following items:
                    fontsize
                    linewidth
                    markercolor
                    markersize
                    disp_title : bool, show figure title or not, default: True
                    every_year : int, number of years for the major tick on xaxis
        dateList_drop : list of string, date dropped in YYYYMMDD format
                          e.g. ['20080711', '20081011']
    Output:
        ax : matplotlib axes object
    """
    # Figure Setting
    if not 'fontsize'    in plot_dict.keys():   plot_dict['fontsize']    = 12
    if not 'linewidth'   in plot_dict.keys():   plot_dict['linewidth']   = 2
    if not 'markercolor' in plot_dict.keys():   plot_dict['markercolor'] = 'orange'
    if not 'markersize'  in plot_dict.keys():   plot_dict['markersize']  = 16
    if not 'disp_title'  in plot_dict.keys():   plot_dict['disp_title']  = True
    if not 'every_year'  in plot_dict.keys():   plot_dict['every_year']  = 1
    transparency = 0.7

    # Date Convert
    dateList = ptime.yyyymmdd(dateList)
    dates, datevector = ptime.date_list2vector(dateList)

    # Get index of date used and dropped
    # dateList_drop = ['20080711', '20081011']  # for debug
    idx_keep = list(range(len(dateList)))
    idx_drop = []
    for i in dateList_drop:
        idx = dateList.index(i)
        idx_keep.remove(idx)
        idx_drop.append(idx)

    # Plot
    # ax=fig.add_subplot(111)

    # Plot date used
    if idx_keep:
        x_list = [dates[i] for i in idx_keep]
        y_list = [pbaseList[i] for i in idx_keep]
        ax.plot(x_list, y_list, '-ko', alpha=transparency, lw=plot_dict['linewidth'],
                ms=plot_dict['markersize'], mfc=plot_dict['markercolor'])

    # Plot date dropped
    if idx_drop:
        x_list = [dates[i] for i in idx_drop]
        y_list = [pbaseList[i] for i in idx_drop]
        ax.plot(x_list, y_list, 'ko', alpha=transparency,
                ms=plot_dict['markersize'], mfc='gray')

    if plot_dict['disp_title']:
        ax.set_title('Perpendicular Baseline History', fontsize=plot_dict['fontsize'])

    # axis format
    ax = auto_adjust_xaxis_date(ax, datevector, plot_dict['fontsize'],
                                every_year=plot_dict['every_year'])[0]
    ax = auto_adjust_yaxis(ax, pbaseList, plot_dict['fontsize'])
    ax.set_xlabel('Time [years]', fontsize=plot_dict['fontsize'])
    ax.set_ylabel('Perpendicular Baseline [m]', fontsize=plot_dict['fontsize'])

    return ax


def plot_coherence_matrix(ax, date12List, cohList, date12List_drop=[], plot_dict={}):
    """Plot Coherence Matrix of input network

    if date12List_drop is not empty, plot KEPT pairs in the upper triangle and
                                           ALL  pairs in the lower triangle.
    """
    # Figure Setting
    if not 'fontsize'    in plot_dict.keys():   plot_dict['fontsize']    = 12
    if not 'linewidth'   in plot_dict.keys():   plot_dict['linewidth']   = 2
    if not 'markercolor' in plot_dict.keys():   plot_dict['markercolor'] = 'orange'
    if not 'markersize'  in plot_dict.keys():   plot_dict['markersize']  = 16
    if not 'disp_title'  in plot_dict.keys():   plot_dict['disp_title']  = True
    if not 'cbar_label'  in plot_dict.keys():   plot_dict['cbar_label']  = 'Coherence'

    date12List = ptime.yyyymmdd_date12(date12List)
    coh_mat = pnet.coherence_matrix(date12List, cohList)

    if date12List_drop:
        # Date Convert
        m_dates = [i.split('_')[0] for i in date12List]
        s_dates = [i.split('_')[1] for i in date12List]
        dateList = sorted(list(set(m_dates + s_dates)))
        # Set dropped pairs' value to nan, in upper triangle only.
        for date12 in date12List_drop:
            idx1, idx2 = [dateList.index(i) for i in date12.split('_')]
            coh_mat[idx1, idx2] = np.nan

    # Show diagonal value as black, to be distinguished from un-selected interferograms
    diag_mat = np.diag(np.ones(coh_mat.shape[0]))
    diag_mat[diag_mat == 0.] = np.nan
    im = ax.imshow(diag_mat, cmap='gray_r', vmin=0.0, vmax=1.0, interpolation='nearest')
    im = ax.imshow(coh_mat, cmap='jet', vmin=0.0, vmax=1.0, interpolation='nearest')

    date_num = coh_mat.shape[0]
    if date_num < 30:
        tick_list = list(range(0, date_num, 5))
    else:
        tick_list = list(range(0, date_num, 10))
    ax.get_xaxis().set_ticks(tick_list)
    ax.get_yaxis().set_ticks(tick_list)
    ax.set_xlabel('Image Number', fontsize=plot_dict['fontsize'])
    ax.set_ylabel('Image Number', fontsize=plot_dict['fontsize'])

    if plot_dict['disp_title']:
        ax.set_title('Coherence Matrix')

    # Colorbar
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", "3%", pad="3%")
    cbar = plt.colorbar(im, cax=cax)
    cbar.set_label(plot_dict['cbar_label'], fontsize=plot_dict['fontsize'])

    # Legend
    if date12List_drop:
        ax.plot([], [], label='Upper: used ifgrams')
        ax.plot([], [], label='Lower: all ifgrams')
        ax.legend(handlelength=0)

    return ax


def prepare_dem_background(dem, inps_dict=dict()):
    """Prepare to plot DEM on background
    Parameters: dem : 2D np.int16 matrix, dem data
                inps_dict : dict with the following 4 items:
                    'disp_dem_shade'    : bool,  True/False
                    'disp_dem_contour'  : bool,  True/False
                    'dem_contour_step'  : float, 200.0
                    'dem_contour_smooth': float, 3.0
    Returns:    dem_shade : 3D np.array in size of (length, width, 4)
                dem_contour : 2D np.array in size of (length, width)
                dem_contour_sequence : 1D np.array
    Examples:   dem = readfile.read('INPUTS/geometryRadar.h5')[0]
                dem_shade, dem_contour, dem_contour_seq = pp.prepare_dem_background(dem=dem)
    """
    if not inps_dict:
        inps_dict['disp_dem_shade'] = True
        inps_dict['disp_dem_contour'] = True
        inps_dict['dem_contour_step'] = 200.0
        inps_dict['dem_contour_smooth'] = 3.0

    dem_shade = None
    dem_contour = None
    dem_contour_sequence = None

    if inps_dict['disp_dem_shade']:
        ls = LightSource(azdeg=315, altdeg=45)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            dem_shade = ls.shade(dem, vert_exag=1.0, cmap=plt.cm.gray,
                                 vmin=-5000, vmax=np.nanmax(dem)+2000)
        dem_shade[np.isnan(dem_shade[:, :, 0])] = np.nan
        print('show shaded relief DEM')

    if inps_dict['disp_dem_contour']:
        dem_contour = ndimage.gaussian_filter(dem,
                                              sigma=inps_dict['dem_contour_smooth'],
                                              order=0)
        dem_contour_sequence = np.arange(-6000, 9000, inps_dict['dem_contour_step'])
        print('show contour in step of {} m with smoothing factor of {}'.format(inps_dict['dem_contour_step'],
                                                                                inps_dict['dem_contour_smooth']))
    return dem_shade, dem_contour, dem_contour_sequence


def plot_dem_background(ax, geo_box=None, dem_shade=None, dem_contour=None, dem_contour_seq=None,
                        dem=None, inps_dict=dict()):
    """Plot DEM as background.
    Parameters: ax : matplotlib.pyplot.Axes or BasemapExt object
                geo_box : tuple of 4 float in order of (E, N, W, S), geo bounding box
                dem_shade : 3D np.array in size of (length, width, 4)
                dem_contour : 2D np.array in size of (length, width)
                dem_contour_sequence : 1D np.array
                dem : 2D np.array of DEM data
                inps_dict : dict with the following 4 items:
                    'disp_dem_shade'    : bool,  True/False
                    'disp_dem_contour'  : bool,  True/False
                    'dem_contour_step'  : float, 200.0
                    'dem_contour_smooth': float, 3.0
    Returns:    ax : matplotlib.pyplot.Axes or BasemapExt object
    Examples:   m = pp.plot_dem_background(m, geo_box=inps.geo_box, dem=dem, inps_dict=vars(inps))
                ax = pp.plot_dem_background(ax=ax, geo_box=None, dem_shade=dem_shade,
                                            dem_contour=dem_contour, dem_contour_seq=dem_contour_seq)
    """
    if all(i is None for i in [dem_shade, dem_contour, dem_contour_seq]) and dem is not None:
        dem_shade, dem_contour, dem_contour_seq = prepare_dem_background(dem, inps_dict=inps_dict)

    if dem_shade is not None:
        # geo coordinates
        if isinstance(ax, BasemapExt) and geo_box is not None:
            ax.imshow(dem_shade, interpolation='spline16', origin='upper')
        # radar coordinates
        elif isinstance(ax, plt.Axes):
            ax.imshow(dem_shade, interpolation='spline16')

    if dem_contour is not None and dem_contour_seq is not None:
        # geo coordinates
        if isinstance(ax, BasemapExt) and geo_box is not None:
            yy, xx = np.mgrid[geo_box[1]:geo_box[3]:dem_contour.shape[0]*1j,
                              geo_box[0]:geo_box[2]:dem_contour.shape[1]*1j]
            ax.contour(xx, yy, dem_contour, dem_contour_seq,
                       origin='upper', colors='black', alpha=0.5, latlon='FALSE')
        # radar coordinates
        elif isinstance(ax, plt.Axes):
            ax.contour(dem_contour, dem_contour_seq,
                       origin='lower', colors='black', alpha=0.5)
    return ax


def plot_colorbar(inps, im, cax):
    # Colorbar Extend
    if not inps.cbar_ext:
        if   inps.disp_min <= inps.data_min and inps.disp_max >= inps.data_max: inps.cbar_ext='neither'
        elif inps.disp_min >  inps.data_min and inps.disp_max >= inps.data_max: inps.cbar_ext='min'
        elif inps.disp_min <= inps.data_min and inps.disp_max <  inps.data_max: inps.cbar_ext='max'
        else:  inps.cbar_ext='both'

    if inps.wrap and 'radian' in inps.disp_unit:
        cbar = plt.colorbar(im, cax=cax, ticks=[-np.pi, 0, np.pi])
        cbar.ax.set_yticklabels([r'-$\pi$', '0', r'$\pi$'])
    else:
        cbar = plt.colorbar(im, cax=cax, extend=inps.cbar_ext)

    if inps.cbar_nbins:
        cbar.locator = ticker.MaxNLocator(nbins=inps.cbar_nbins)
        cbar.update_ticks()

    cbar.ax.tick_params(labelsize=inps.font_size, colors=inps.font_color)

    if not inps.cbar_label:
        cbar.set_label(inps.disp_unit, fontsize=inps.font_size, color=inps.font_color)
    else:
        cbar.set_label(inps.cbar_label, fontsize=inps.font_size, color=inps.font_color)
    return inps, cax


def set_shared_ylabel(axes_list, label, labelpad = 0.01, font_size=12, position='left'):
    """Set a y label shared by multiple axes
    Parameters: axes_list : list of axes in left/right most col direction
                label : string
                labelpad : float, Sets the padding between ticklabels and axis label
                font_size : int
                position : string, 'left' or 'right'
    """

    f = axes_list[0].get_figure()
    f.canvas.draw() #sets f.canvas.renderer needed below

    # get the center position for all plots
    top = axes_list[0].get_position().y1
    bottom = axes_list[-1].get_position().y0

    # get the coordinates of the left side of the tick labels 
    x0 = 1
    x1 = 0
    for ax in axes_list:
        ax.set_ylabel('') # just to make sure we don't and up with multiple labels
        bboxes = ax.yaxis.get_ticklabel_extents(f.canvas.renderer)[0]
        bboxes = bboxes.inverse_transformed(f.transFigure)
        x0t = bboxes.x0
        if x0t < x0:
            x0 = x0t
        x1t = bboxes.x1
        if x1t > x1:
            x1 = x1t
    tick_label_left = x0
    tick_label_right = x1

    # set position of label
    axes_list[-1].set_ylabel(label, fontsize=font_size)
    if position == 'left':
        axes_list[-1].yaxis.set_label_coords(tick_label_left - labelpad,
                                             (bottom + top)/2,
                                             transform=f.transFigure)
    else:
        axes_list[-1].yaxis.set_label_coords(tick_label_right + labelpad,
                                             (bottom + top)/2,
                                             transform=f.transFigure)
    return


def set_shared_xlabel(axes_list, label, labelpad = 0.01, font_size=12, position='top'):
    """Set a y label shared by multiple axes
    Parameters: axes_list : list of axes in top/bottom row direction
                label : string
                labelpad : float, Sets the padding between ticklabels and axis label
                font_size : int
                position : string, 'top' or 'bottom'
    """

    f = axes_list[0].get_figure()
    f.canvas.draw() #sets f.canvas.renderer needed below

    # get the center position for all plots
    left = axes_list[0].get_position().x0
    right = axes_list[-1].get_position().x1

    # get the coordinates of the left side of the tick labels 
    y0 = 1
    y1 = 0
    for ax in axes_list:
        ax.set_xlabel('') # just to make sure we don't and up with multiple labels
        bboxes = ax.yaxis.get_ticklabel_extents(f.canvas.renderer)[0]
        bboxes = bboxes.inverse_transformed(f.transFigure)
        y0t = bboxes.y0
        if y0t < y0:
            y0 = y0t
        y1t = bboxes.y1
        if y1t > y1:
            y1 = y1t
    tick_label_bottom = y0
    tick_label_top = y1

    # set position of label
    axes_list[-1].set_xlabel(label, fontsize=font_size)
    if position == 'top':
        axes_list[-1].xaxis.set_label_coords((left + right) / 2,
                                             tick_label_top + labelpad,
                                             transform=f.transFigure)
    else:
        axes_list[-1].xaxis.set_label_coords((left + right) / 2,
                                             tick_label_bottom - labelpad,
                                             transform=f.transFigure)
    return


def check_disp_unit_and_wrap(metadata, disp_unit=None, wrap=False):
    """Get auto disp_unit for input dataset
    Example:
        if not inps.disp_unit:
            inps.disp_unit = pp.auto_disp_unit(atr)
    """
    if not disp_unit:
        k = metadata['FILE_TYPE']
        disp_unit = metadata['UNIT'].lower()
        if k in ['timeseries', 'velocity'] and disp_unit.split('/')[0].endswith('m'):
            disp_unit = 'cm'
        elif k in ['.mli', '.slc', '.amp']:
            disp_unit = 'dB'

    if wrap:
        if disp_unit.split('/')[0] not in ['radian', 'm', 'cm', 'mm']:
            wrap = False
            print('WARNING: re-wrap is disabled for disp_unit = {}'.format(disp_unit))
        elif disp_unit.split('/')[0] != 'radian':
            disp_unit = 'radian'
            print('change disp_unit = radian due to rewrapping')

    return disp_unit, wrap


def scale_data2disp_unit(data=None, metadata=dict(), disp_unit=None):
    """Scale data based on data unit and display unit
    Inputs:
        data    : 2D np.array
        metadata  : dictionary, meta data
        disp_unit : str, display unit
    Outputs:
        data    : 2D np.array, data after scaling
        disp_unit : str, display unit
    Default data file units in PySAR are:  m, m/yr, radian, 1
    """
    # Initial
    scale = 1.0
    data_unit = metadata['UNIT'].lower().split('/')
    disp_unit = disp_unit.lower().split('/')

    # if data and display unit is the same
    if disp_unit == data_unit:
        return data, metadata['UNIT'], scale

    # Calculate scaling factor  - 1
    # phase unit - length / angle
    if data_unit[0].endswith('m'):
        if   disp_unit[0] == 'mm': scale *= 1000.0
        elif disp_unit[0] == 'cm': scale *= 100.0
        elif disp_unit[0] == 'dm': scale *= 10.0
        elif disp_unit[0] == 'km': scale *= 1/1000.0
        elif disp_unit[0] in ['radians','radian','rad','r']:
            range2phase = -(4*np.pi) / float(metadata['WAVELENGTH'])
            scale *= range2phase
        else:
            print('Unrecognized display phase/length unit: '+disp_unit[0])
            return data, data_unit, scale

        if   data_unit[0] == 'mm': scale *= 0.001
        elif data_unit[0] == 'cm': scale *= 0.01
        elif data_unit[0] == 'dm': scale *= 0.1
        elif data_unit[0] == 'km': scale *= 1000.

    elif data_unit[0] == 'radian':
        phase2range = -float(metadata['WAVELENGTH']) / (4*np.pi)
        if   disp_unit[0] == 'mm': scale *= phase2range * 1000.0
        elif disp_unit[0] == 'cm': scale *= phase2range * 100.0
        elif disp_unit[0] == 'dm': scale *= phase2range * 10.0
        elif disp_unit[0] == 'km': scale *= phase2range * 1/1000.0
        elif disp_unit[0] in ['radians','radian','rad','r']:
            pass
        else:
            print('Unrecognized phase/length unit: '+disp_unit[0])
            return data, data_unit, scale

    # amplitude/coherence unit - 1
    elif data_unit[0] == '1':
        if disp_unit[0] == 'db' and data is not None:
            ind = np.nonzero(data)
            data[ind] = 10*np.log10(np.absolute(data[ind]))
            disp_unit[0] = 'dB'
        else:
            try:
                scale /= float(disp_unit[0])
            except:
                print('Un-scalable display unit: '+disp_unit[0])
    else:
        print('Un-scalable data unit: '+data_unit)

    # Calculate scaling factor  - 2
    if len(data_unit) == 2:
        try:
            disp_unit[1]
            if   disp_unit[1] in ['y','yr','year'  ]: disp_unit[1] = 'year'
            elif disp_unit[1] in ['m','mon','month']: disp_unit[1] = 'mon'; scale *= 12.0
            elif disp_unit[1] in ['d','day'        ]: disp_unit[1] = 'day'; scale *= 365.25
            else: print('Unrecognized time unit for display: '+disp_unit[1])
        except:
            disp_unit.append('year')
        disp_unit = disp_unit[0]+'/'+disp_unit[1]
    else:
        disp_unit = disp_unit[0]

    # Scale input data
    if data is not None:
        data *= scale
    return data, disp_unit, scale


def scale_data4disp_unit_and_rewrap(data, metadata, disp_unit=None, wrap=False):
    """Scale 2D matrix value according to display unit and re-wrapping flag
    Inputs:
        data - 2D np.array
        metadata  - dict, including the following attributes:
               UNIT
               FILE_TYPE
               WAVELENGTH
        disp_unit  - string, optional
        wrap - bool, optional
    Outputs:
        data
        disp_unit
        wrap
    """
    if not disp_unit:
        disp_unit, wrap = check_disp_unit_and_wrap(metadata,
                                                   disp_unit=None,
                                                   wrap=wrap)

    # Data Operation - Scale to display unit
    disp_scale = 1.0
    if not disp_unit == metadata['UNIT']:
        data, disp_unit, disp_scale = scale_data2disp_unit(data,
                                                           metadata=metadata,
                                                           disp_unit=disp_unit)

    # Data Operation - wrap
    if wrap:
        print('re-wrapping data to [-pi, pi]')
        data -= np.round(data/(2*np.pi)) * (2*np.pi)
    return data, disp_unit, disp_scale, wrap
