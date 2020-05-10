#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tango Archiving Viewer

@author: Michele Devetta (michele.devetta@cnr.it)
"""

import sys
import os
## Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '..'))
sys.path.insert(1, os.path.join(sys.path[0], '../Icons'))

import time
import datetime
import numpy as np
import PyTango as PT
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from Ui_archivingviewer import Ui_ArchivingViewer

from PyQTango import QArchivedAttributeTree, DeviceItem, AttributeItem

# Matplotlib stuff
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure

class NavigationToolbar(NavigationToolbar2QT):
    pass
    #toolitems = [t for t in NavigationToolbar2QT.toolitems if t[0] not in ('Subplots', )]



class ArchivingViewer(QtWidgets.QMainWindow, Ui_ArchivingViewer):

    def __init__(self, parent=None):
        # Parent constructor
        QtWidgets.QMainWindow.__init__(self, parent)

        # Get scaling factor for HiDPI
        design_dpi = 95
        current_dpi = app.primaryScreen().physicalDotsPerInch()
        self.scaling = float(current_dpi) / float(design_dpi)
        if self.scaling > 1.8:
            self.scaling = 1.8
        elif self.scaling < 1.1:
            self.scaling = 1.0

        # Init gui
        self.setupUi(self)
        self.setup_fonts_and_scaling()

        # Set begin/end date radio button checked
        self.choose_be.setChecked(True)

        # Connect to HDBExtractor
        try:
            self.extractor = PT.DeviceProxy("archiving/hdb/hdbextractor.1")
            self.extractor.ping()
        except PT.DevFailed:
            QtWidgets.QMessageBox.critical(None, "Extractor not available", "HDB extractor is not available")
            exit(-1)

        # Add items to minutes combobox
        self.span_minutes.addItem("00", 0)
        self.span_minutes.addItem("15", 15)
        self.span_minutes.addItem("30", 30)
        self.span_minutes.addItem("45", 45)

        # Initialize dates
        now = QtCore.QDateTime.currentDateTime()
        self.begin_date.setDateTime(now.addSecs(-3600))
        self.end_date.setDateTime(now)

        # Create splitter
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, parent=self.splitter_area)
        self.splitter.resize(self.splitter_area.size())

        # Create attribute tree
        self.tree = QArchivedAttributeTree(self.extractor, resize=False, label="Archived attributes")
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.tree.expandAll()

        # Setup canvas for spectrum
        self.spec_fig = Figure()
        self.spec_canvas = FigureCanvas(self.spec_fig)
        self.spec_canvas.setParent(self)
        self.plot_ax = None
        self.plot_data = []

        # Toolbar
        self.spec_toolbar = NavigationToolbar(self.spec_canvas, self)

        # Layout
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.spec_canvas)
        vbox.addWidget(self.spec_toolbar)
        plot_area = QtWidgets.QWidget()
        plot_area.setLayout(vbox)

        # Add to splitter
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(plot_area)


    def setup_fonts_and_scaling(self):
        # Setup font size and scaling on hidpi
        if self.scaling > 1.1:
            # Scale only if factor is more than 1.1
            self.scale_widget(self, self.scaling)
            members = dir(self)
            for m in members:
                if issubclass(type(getattr(self, m)), QtWidgets.QWidget):
                    self.scale_widget(getattr(self, m), self.scaling)

    def scale_widget(self, widget, scaling):
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))


    @QtCore.pyqtSlot(bool)
    def on_choose_be_toggled(self, checked):
        if checked:
            self.span_days.setDisabled(True)
            self.span_hours.setDisabled(True)
            self.span_minutes.setDisabled(True)
            if not self.end_now.isChecked():
                self.end_date.setDisabled(False)
            self.end_now.setDisabled(False)
            self.begin_date.setDisabled(False)

    @QtCore.pyqtSlot(bool)
    def on_choose_per_toggled(self, checked):
        if checked:
            self.span_days.setDisabled(False)
            self.span_hours.setDisabled(False)
            self.span_minutes.setDisabled(False)
            self.end_date.setDisabled(True)
            self.end_now.setDisabled(True)
            self.begin_date.setDisabled(False)

    @QtCore.pyqtSlot(bool)
    def on_choose_last_toggled(self, checked):
        if checked:
            self.span_days.setDisabled(False)
            self.span_hours.setDisabled(False)
            self.span_minutes.setDisabled(False)
            self.begin_date.setDisabled(True)
            self.end_date.setDisabled(True)
            self.end_now.setDisabled(True)

    @QtCore.pyqtSlot(int)
    def on_end_now_stateChanged(self, state):
        if state == QtCore.Qt.Checked:
            self.end_date.setDisabled(True)
        else:
            self.end_date.setDisabled(False)

    @QtCore.pyqtSlot()
    def on_refresh_released(self):
        # First extract data from database
        if self.choose_be.isChecked():
            # Begin and end date
            start = self.begin_date.dateTime().toPyDateTime()
            if self.end_now.isChecked():
                end = datetime.datetime.now()
            else:
                end = self.end_date.dateTime().toPyDateTime()

        elif self.choose_per.isChecked():
            # Begin and time span
            start = self.begin_date.dateTime().toPyDateTime()
            delta = datetime.timedelta(days=self.span_days.value(), hours=self.span_hours.value(), minutes=self.span_minutes.currentData())
            end = start + delta

        elif self.choose_last.isChecked():
            end = datetime.datetime.now()
            delta = datetime.timedelta(days=self.span_days.value(), hours=self.span_hours.value(), minutes=self.span_minutes.currentData())
            start = end - delta

        else:
            return

        print("Start date: {0}".format(start.strftime("%Y-%m-%d %H:%M:%S")))
        print("End date: {0}".format(end.strftime("%Y-%m-%d %H:%M:%S")))

        # Get selected attributes
        indexes = self.tree.selectionModel().selectedIndexes()

        attr_to_plot = []

        for i in indexes:
            obj = i.internalPointer()
            if type(obj) == AttributeItem:
                attr_to_plot.append(obj.getAttribute())

            elif type(obj) == DeviceItem:
                nc = obj.childCount()
                for i in range(nc):
                    a = obj.child(i)
                    if type(a) == AttributeItem:
                        attr_to_plot.append(a.getAttribute())

        print("Attributes to plot:")
        for i in range(len(attr_to_plot)):
            print("[{0:d}] {1}... ".format(i, attr_to_plot[i]['attribute']), end='')

            count = 0
            while True:
                # Try twice because often the command timeout the first time
                try:
                    data = self.extractor.ExtractBetweenDates([attr_to_plot[i]['attribute'], start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")])
                    if len(data[0]):
                        attr_to_plot[i]['tdata'] = data[0]
                        attr_to_plot[i]['ydata'] = np.float64(data[1])
                    else:
                        attr_to_plot[i] = None
                    print("fetched {0:d} points!".format(len(data[0])))
                    break

                except PT.DevFailed:
                    time.sleep(1)
                    count += 1
                    if count >= 2:
                        print("fetch failed!")
                        attr_to_plot[i] = None
                        break

        self.spec_fig.clear()
        self.plot_ax = None
        self.plot_data = []
        self.plot_ax = self.spec_fig.add_subplot(111)
        for a in attr_to_plot:
            if a is not None:
                y = a['ydata']
                if self.smooth_en.isChecked():
                    try:
                        y = self.smooth(y, int(self.smooth_len.text()));
                    except:
                        pass
                self.plot_ax.plot(a['tdata'], y)
                self.plot_data.append(y)
        self.spec_fig.tight_layout()
        self.spec_canvas.draw()

    def smooth(self, x, window_len=11, window='hanning'):
        """smooth the data using a window with requested size.

        This method is based on the convolution of a scaled window with the signal.
        The signal is prepared by introducing reflected copies of the signal
        (with the window size) in both ends so that transient parts are minimized
        in the begining and end part of the output signal.

        input:
            x: the input signal
            window_len: the dimension of the smoothing window; should be an odd integer
            window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
                flat window will produce a moving average smoothing.

        output:
            the smoothed signal

        example:

        t=linspace(-2,2,0.1)
        x=sin(t)+randn(len(t))*0.1
        y=smooth(x)

        see also:

        numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
        scipy.signal.lfilter

        TODO: the window parameter could be the window itself if an array instead of a string
        NOTE: length(output) != length(input), to correct this: return y[(window_len/2-1):-(window_len/2)] instead of just y.
        """

        if x.ndim != 1:
            raise ValueError("smooth only accepts 1 dimension arrays.")

        if x.size < window_len:
            raise ValueError("Input vector needs to be bigger than window size.")

        if window_len<3:
            return x

        if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
            raise ValueError ("Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'")

        s=np.r_[x[window_len-1:0:-1],x,x[-2:-window_len-1:-1]]
        if window == 'flat': #moving average
            w=np.ones(window_len,'d')
        else:
            w=eval('np.'+window+'(window_len)')

        y=np.convolve(w/w.sum(), s, mode='valid')

        l = window_len-1
        return y[l//2:-(l-l//2)]

    @QtCore.pyqtSlot(int)
    def on_smooth_en_stateChanged(self, state):
        if state == QtCore.Qt.Checked:
            try:
                wlen = int(self.smooth_len.text())
            except:
                wlen = 11
            for i in range(len(self.plot_ax.lines)):
                try:
                    self.plot_ax.lines[i].set_ydata(self.smooth(self.plot_data[i], wlen))
                except:
                    pass
        else:
            for i in range(len(self.plot_ax.lines)):
                self.plot_ax.lines[i].set_ydata(self.plot_data[i])
        self.spec_canvas.draw()

    @QtCore.pyqtSlot()
    def on_smooth_len_editingFinished(self):
        """ Set number of scans to average. """
        if self.plot_ax is not None and self.smooth_en.isChecked():
            try:
                wlen = int(self.smooth_len.text())
            except:
                wlen = 11
            for i in range(len(self.plot_ax.lines)):
                try:
                    self.plot_ax.lines[i].set_ydata(self.smooth(self.plot_data[i], wlen))
                except:
                    pass
            self.spec_canvas.draw()

    @QtCore.pyqtSlot()
    def on_close_button_released(self):
        """ Close main windows. """
        self.close()

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, event):
        """ Handle the resize event of the window. """
        if event.size().isValid() and event.oldSize().isValid():
            w = event.size().width()
            h = event.size().height()
            dw = w - event.oldSize().width()
            dh = h - event.oldSize().height()

            print("Resized window to ({:d}, {:d})".format(w, h))

            sz = self.date_controls.size()
            self.date_controls.resize(sz.width() + dw, sz.height())

            sz = self.splitter_area.size()
            self.splitter_area.resize(sz.width() + dw, sz.height() + dh)
            self.splitter.resize(self.splitter_area.size())
            self.spec_fig.tight_layout()

            ps = self.close_button.pos()
            self.close_button.move(QtCore.QPoint(ps.x() + dw, ps.y() + dh))

        else:
            QtWidgets.QMainWindow.resizeEvent(self, event)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ui = ArchivingViewer()
    ui.show()
    ret = app.exec_()
    sys.exit(ret)
