# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 14:41:50 2014

@author: wyrdmeister
"""

import sys
import os
## Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '../Icons'))

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtWidgets import QFileDialog

from Ui_spectrumviewer import Ui_SpectrumViewer
from Ui_spectrumviewer_setscale import Ui_SpectrumViewer_SetScale

import re
import h5py as h5
import time
import datetime
import numpy as np
import PyTango as PT

# Matplotlib stuff
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure


class NavigationToolbar(NavigationToolbar2QT):
    toolitems = [t for t in NavigationToolbar2QT.toolitems if t[0] not in ('Subplots', )]


class SpectrumViewer_Setscale(QtWidgets.QDialog, Ui_SpectrumViewer_SetScale):
    def __init__(self, x, y, scaling=1.0, parent=None):
        # Parent constructors
        QtWidgets.QDialog.__init__(self, parent)

        # Setup Ui
        self.setupUi(self)

        # Scale only if factor is more than 1.1
        self.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.scale_widget(self, scaling)

        sz = self.size()
        self.setMinimumSize(sz)
        self.setMaximumSize(sz)

        members = dir(self)
        for m in members:
            if issubclass(type(getattr(self, m)), QtWidgets.QWidget):
                self.scale_widget(getattr(self, m), scaling)

        self.min_wl.setText("{0:.1f}".format(x[0]))
        self.max_wl.setText("{0:.1f}".format(x[1]))
        self.min_counts.setText("{0:.1f}".format(y[0]))
        self.max_counts.setText("{0:.1f}".format(y[1]))

    def scale_widget(self, widget, scaling):
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))


class SpectrumViewer(QtWidgets.QMainWindow, Ui_SpectrumViewer):

    """ Spectrometer GUI main window. """

    # Tango change event signal
    tango_event = QtCore.pyqtSignal(PT.EventData)

    def __init__(self, parent=None):
        # Parent constructors
        QtWidgets.QMainWindow.__init__(self, parent)

        # Tango device
        self.dev = None
        self.dev_state = None
        self.ev_id = []

        # Get scaling factor for HiDPI
        design_dpi = 95
        app = QtWidgets.QApplication.instance()
        if app is not None:
            current_dpi = app.primaryScreen().physicalDotsPerInch()
            self.scaling = float(current_dpi) / float(design_dpi)
            if self.scaling > 1.8:
                self.scaling = 1.8
            elif self.scaling < 1.1:
                self.scaling = 1.0
        else:
            self.scaling = 1.0

        # Build UI
        self.setupUi(self)
        self.inhibith_resize = True
        self.setup_fonts_and_scaling()
        self.inhibith_resize = False

        # Setup canvas for spectrum
        self.spec_fig = Figure()
        self.spec_canvas = FigureCanvas(self.spec_fig)
        self.spec_canvas.setParent(self)
        self.cid = self.spec_fig.canvas.mpl_connect('button_press_event', self.add_or_move_marker)
        self.marker_on = False
        self.marker_delta = False
        self.spec_cursor.setText("")

        # Toolbar
        self.spec_toolbar = NavigationToolbar(self.spec_canvas, self)

        # Add autoscale button
        self.spec_autoscale = QtWidgets.QPushButton()
        self.spec_autoscale.setGeometry(QtCore.QRect(0, 0, 27*self.scaling, 27*self.scaling))
        self.spec_autoscale.setText("")
        autoscale_icon = QtGui.QIcon()
        autoscale_icon.addPixmap(QtGui.QPixmap(":/buttons/autoscale.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.spec_autoscale.setIcon(autoscale_icon)
        self.spec_autoscale.setIconSize(QtCore.QSize(20*self.scaling, 20*self.scaling))
        self.spec_autoscale.setCheckable(True)
        self.spec_autoscale.setObjectName("spec_autoscale")
        self.spec_autoscale.setToolTip("Enable vertical autoscale")
        self.spec_toolbar.addWidget(self.spec_autoscale)

        # Add set scale button
        self.spec_setscale = QtWidgets.QPushButton()
        self.spec_setscale.setGeometry(QtCore.QRect(0, 0, 27*self.scaling, 27*self.scaling))
        self.spec_setscale.setText("")
        scale_icon = QtGui.QIcon()
        scale_icon.addPixmap(QtGui.QPixmap(":/buttons/setscale.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.spec_setscale.setIcon(scale_icon)
        self.spec_setscale.setIconSize(QtCore.QSize(20*self.scaling, 20*self.scaling))
        self.spec_setscale.setObjectName("spec_autoscale")
        self.spec_setscale.setToolTip("Set plot limits")
        self.spec_setscale.released.connect(self.on_spec_setscale_released)
        self.spec_toolbar.addWidget(self.spec_setscale)

        # Add restore scale button
        self.spec_restore = QtWidgets.QPushButton()
        self.spec_restore.setGeometry(QtCore.QRect(0, 0, 27*self.scaling, 27*self.scaling))
        self.spec_restore.setText("")
        restore_icon = QtGui.QIcon()
        restore_icon.addPixmap(QtGui.QPixmap(":/buttons/expand.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.spec_restore.setIcon(restore_icon)
        self.spec_restore.setIconSize(QtCore.QSize(20*self.scaling, 20*self.scaling))
        self.spec_restore.setObjectName("spec_autoscale")
        self.spec_restore.setToolTip("Restore plot limits")
        self.spec_restore.released.connect(self.on_spec_restore_released)
        self.spec_toolbar.addWidget(self.spec_restore)

        # Add delta cursors button
        self.spec_delta = QtWidgets.QPushButton()
        self.spec_delta.setGeometry(QtCore.QRect(0, 0, 27*self.scaling, 27*self.scaling))
        self.spec_delta.setText("")
        delta_icon = QtGui.QIcon()
        delta_icon.addPixmap(QtGui.QPixmap(":/buttons/delta.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.spec_delta.setIcon(delta_icon)
        self.spec_delta.setIconSize(QtCore.QSize(20*self.scaling, 20*self.scaling))
        self.spec_delta.setCheckable(True)
        self.spec_delta.setObjectName("spec_delta")
        self.spec_delta.setToolTip("Enable delta cursor")
        self.spec_delta.released.connect(self.on_spec_delta_released)
        self.spec_toolbar.addWidget(self.spec_delta)

        # Layout
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.spec_canvas)
        vbox.addWidget(self.spec_toolbar)
        self.spectrum_area.setLayout(vbox)
        self.spectrum_plot = None
        self.last_spectrum_update = 0
        self.wl = None

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Populate spectrometer selector
        spec_list = self.get_spec_list()
        if len(spec_list) > 0:
            for i in range(len(spec_list)):
                self.spec_sel.insertItem(i, spec_list[i])
            self.spec_sel.setCurrentIndex(0)
        else:
            QtWidgets.QMessageBox.critical(self, "No spectrometer found", "No spectrometer found")
            exit(0)

        # Add event filter
        self.spec_int.installEventFilter(self)
        self.spec_setpoint.installEventFilter(self)

    def setup_fonts_and_scaling(self):
        # Setup font size and scaling on hidpi
        if self.scaling > 1.1:
            # Scale only if factor is more than 1.1
            self.scale_widget(self, self.scaling)
            members = dir(self)
            for m in members:
                if issubclass(type(getattr(self, m)), QtWidgets.QPushButton):
                    self.scale_widget(getattr(self, m), self.scaling)
                    if not getattr(self, m).icon().isNull():
                        # Scale icon
                        ratio = 20.0 / 27.0
                        psz = getattr(self, m).size()
                        getattr(self, m).setIconSize(QtCore.QSize(int(psz.width()*ratio), int(psz.height()*ratio)))

                elif issubclass(type(getattr(self, m)), QtWidgets.QWidget):
                    self.scale_widget(getattr(self, m), self.scaling)

            # Scale matplotlib fonts
            matplotlib.rcParams['font.size'] = int(matplotlib.rcParams['font.size'] * self.scaling)

        # Scale fonts of spectrometer information
        nf = QtGui.QFont()
        nf.setPointSize(app.font().pointSize() - 1)
        self.spec_model_l.setFont(nf)
        self.spec_model.setFont(nf)
        self.spec_serial_l.setFont(nf)
        self.spec_serial.setFont(nf)
        self.spec_firmware_l.setFont(nf)
        self.spec_firmware.setFont(nf)

    def scale_widget(self, widget, scaling):
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))

    # Event filter to catch focusIn and focusOut from QLineEdit with units
    def eventFilter(self, source, event):
        if source is self.spec_int:
            if event.type() == QtCore.QEvent.FocusIn:
                self.spec_int.setText(self.spec_int.text()[:-3])
            elif event.type() == QtCore.QEvent.FocusOut:
                self.spec_int.setText(self.spec_int.text() + " ms")
        elif source is self.spec_setpoint:
            if event.type() == QtCore.QEvent.FocusIn:
                self.spec_setpoint.setText(self.spec_setpoint.text()[:-3])
            elif event.type() == QtCore.QEvent.FocusOut:
                self.spec_setpoint.setText(self.spec_setpoint.text() + " °C")
        return QtWidgets.QMainWindow.eventFilter(self, source, event)

    def get_spec_list(self):
        # Get list of active spectrometers
        try:
            db = PT.Database();
            spec_list = list(db.get_device_exported_for_class("OOSpectrometer").value_string)
            spec_list += list(db.get_device_exported_for_class("AvantesSpectrometer").value_string)

            # Check that devices are alive
            out_list = []
            for spec in spec_list:
                try:
                    dev = PT.DeviceProxy(spec)
                    dev.ping()
                    out_list.append(spec)
                except PT.DevFailed:
                    print("Skipping dead device {0}".format(spec))
            return list(out_list)

        except PT.DevFailed as e:
            print("Failed to get the list of spectrometers (Error: {:})".format(e.args[0].desc))
            return []

    def close_spectrometer(self):
        # Close the old one
        if self.dev and len(self.ev_id) > 0:
            for ev in self.ev_id:
                try:
                    self.dev.unsubscribe_event(ev)
                except PT.DevFailed as e:
                    print("Failed to unsubscribe event {0:d} (Error: {1!s})".format(ev, e.args[0].desc))
        self.dev = None
        self.ev_id = []
        self.spec_fig.clear()
        self.spectrum_plot = None

    def open_spectrometer(self, device):
        # Create new DeviceProxy
        print("Device: ", device)
        self.dev = PT.DeviceProxy(device)
        self.dev.ping()
        self.wl = self.dev.Wavelength

        # Update model, serial and firmware version
        self.spec_model.setText(self.dev.Model)
        self.spec_serial.setText(self.dev.SerialNumber)
        self.spec_firmware.setText(self.dev.FirmwareVersion)

        # List of attributes to subscribe for change events
        attr = ['BoxcarWidth', 'enableBackgroundSubtraction', 'enableElectricalDarkCorrection', 'enableNLCorrection', 'IntegrationTime', 'ScansToAverage', 'Spectrum', 'State']

        # Check if TEC is available
        al = self.dev.attribute_list_query()
        tec = False
        for a in al:
            if a.name.lower() == "enabletec":
                tec = True
                break
        if not tec:
            self.spec_tec.setChecked(False)
            self.spec_tec.setDisabled(True)
            self.spec_tectemp.setText("N.A.")
            self.spec_setpoint.setDisabled(True)
            self.spec_setpoint.setText("")
        else:
            self.spec_tec.setDisabled(False)
            self.spec_setpoint.setDisabled(False)
            attr.append("EnableTEC")
            attr.append("TECSetPoint")
            attr.append("TECTemperature")

        # Subscribe events for the new spectrometer
        self.ev_id = []
        for a in attr:
            evid = self.dev.subscribe_event(a, PT.EventType.CHANGE_EVENT, self.event_callback)
            self.ev_id.append(evid)

    @QtCore.pyqtSlot(int)
    def on_spec_sel_currentIndexChanged(self, index):
        print("Index {:d}".format(index))
        if index < 0:
            return

        try:
            # Close old spectrometer
            self.close_spectrometer()
            # Opem new spectrometer
            self.open_spectrometer(self.spec_sel.itemText(index))

        except PT.DevFailed as e:
            self.close_spectrometer()
            PT.Except.print_exception(e)

    def event_callback(self, event):
        """ Event callback
        """
        self.tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, ev):
        """ TANGO Event handler
        """
        if ev.err:
            self.spec_status.setText("Fault")
            self.spec_status.setStyleSheet("background-color:red; color:white; border: 1px solid #AAAAAA; border-radius: 5px;")

        else:
            attr_name = ev.attr_value.name.lower()

            if attr_name == 'boxcarwidth':
                if not self.spec_boxcar.hasFocus():
                    self.spec_boxcar.setText("{0:d}".format(ev.attr_value.value))

            elif attr_name == 'enablebackgroundsubtraction':
                self.spec_bkgsub.setChecked(ev.attr_value.value)

            elif attr_name == 'enableelectricaldarkcorrection':
                if ev.attr_value.value:
                    self.spec_dark.setCheckState(QtCore.Qt.Checked)
                else:
                    self.spec_dark.setCheckState(QtCore.Qt.Unchecked)

            elif attr_name == 'enablenlcorrection':
                if ev.attr_value.value:
                    self.spec_nl.setCheckState(QtCore.Qt.Checked)
                else:
                    self.spec_nl.setCheckState(QtCore.Qt.Unchecked)

            elif attr_name == 'integrationtime':
                if not self.spec_int.hasFocus():
                    self.spec_int.setText("{0:.2f} ms".format(ev.attr_value.value))

            elif attr_name == 'scanstoaverage':
                if not self.spec_avg.hasFocus():
                    self.spec_avg.setText("{0:d}".format(ev.attr_value.value))

            elif attr_name == 'enabletec':
                self.spec_tec.setChecked(ev.attr_value.value)

            elif attr_name == 'tectemperature':
                self.spec_tectemp.setText("{0:.1f} °C".format(ev.attr_value.value))

            elif attr_name == 'tecsetpoint':
                if not self.spec_setpoint.hasFocus():
                    self.spec_setpoint.setText("{0:.1f} °C".format(ev.attr_value.value))

            elif attr_name == 'spectrum':
                #refresh = int(self.refresh_rate.itemText(self.refresh_rate.currentIndex()))
                if (time.time() - self.last_spectrum_update) > 0.2:
                    self.last_spectrum_update = time.time()

                    sp = ev.attr_value.value
                    fwhm = self.getFWHM(self.wl, sp)
                    self.spec_bw.setText("{0:.1f}".format(fwhm[1] - fwhm[0]))

                    if self.spectrum_plot is None:
                        self.spectrum_plot = self.spec_fig.add_subplot(111)
                        self.spectrum_plot.plot(self.wl, sp)
                        # FWHM position
                        yl = self.spectrum_plot.get_ylim()
                        self.spectrum_plot.plot([fwhm[0], fwhm[0]], yl, 'r')
                        self.spectrum_plot.plot([fwhm[1], fwhm[1]], yl, 'r')
                        ## NOTE: workaround for tight_layout not working after first spectrum
                        self.got_first = True
                        ##=============================

                    else:
                        self.spectrum_plot.lines[0].set_data(self.wl, sp)
                        if self.spec_autoscale.isChecked():
                            #self.spectrum_plot.set_xlim([min(self.wl), max(self.wl)])
                            self.spectrum_plot.set_ylim([min(sp), max(sp)*1.1])
                        # FWHM position
                        yl = self.spectrum_plot.get_ylim()
                        self.spectrum_plot.lines[1].set_data([fwhm[0], fwhm[0]], yl)
                        self.spectrum_plot.lines[2].set_data([fwhm[1], fwhm[1]], yl)
                        ## NOTE: workaround for tight_layout not working after first spectrum
                        if self.got_first:
                            self.spec_fig.tight_layout()
                            self.got_first = False
                        ##=============================

                    # Redraw canvas
                    self.spec_canvas.draw()

            elif attr_name == 'state':
                self.dev_state = ev.attr_value.value
                if ev.attr_value.value in (PT.DevState.ON, PT.DevState.RUNNING):
                    self.spec_status.setText("Running")
                    self.spec_status.setStyleSheet("background-color:darkgreen; color:white; border: 1px solid #AAAAAA; border-radius: 5px;")
                elif ev.attr_value.value in (PT.DevState.OFF, PT.DevState.STANDBY):
                    self.spec_status.setText("Offline")
                    self.spec_status.setStyleSheet("background-color:white; color:black; border: 1px solid #AAAAAA; border-radius: 5px;")
                elif ev.attr_value.value in (PT.DevState.FAULT, PT.DevState.ALARM):
                    self.spec_status.setText("Fault")
                    self.spec_status.setStyleSheet("background-color:red; color:white; border: 1px solid #AAAAAA; border-radius: 5px;")
                else: # Unexpected state
                    self.spec_status.setText("Unknown")
                    self.spec_status.setStyleSheet("background-color:red; color:white; border: 1px solid #AAAAAA; border-radius: 5px;")

            else:
                # Unexpected event
                print("Got an unexpected event from attribute {:}".format(ev.attr_name))

    def add_or_move_marker(self, event):
        if event.inaxes is not None and event.button == 1 and not event.dblclick:
            if not self.marker_on:
                # Pop overlays
                overlays = self.pop_overlays()
                # Add marker
                yl = self.spectrum_plot.get_ylim()
                self.spectrum_plot.plot([event.xdata, event.xdata], yl, 'g')
                self.add_overlays(overlays)
                self.marker_on = True

            elif self.marker_on and self.spec_delta.isChecked() and not self.marker_delta:
                # Pop overlays
                overlays = self.pop_overlays()
                # Add marker
                yl = self.spectrum_plot.get_ylim()
                self.spectrum_plot.plot([event.xdata, event.xdata], yl, 'g')
                self.add_overlays(overlays)
                self.marker_delta = True

            elif self.marker_on:
                # Move last cursor
                yl = self.spectrum_plot.get_ylim()
                plot_id = 3
                if self.marker_delta:
                    # Check nearest
                    d1 = abs(event.xdata - self.spectrum_plot.lines[3].get_xdata()[0])
                    d2 = abs(event.xdata - self.spectrum_plot.lines[4].get_xdata()[0])
                    if d1 > d2:
                        plot_id = 4
                self.spectrum_plot.lines[plot_id].set_data([event.xdata, event.xdata], yl)

            # Update legend
            if self.marker_delta:
                c = []
                c.append(self.spectrum_plot.lines[3].get_xdata()[0])
                c.append(self.spectrum_plot.lines[4].get_xdata()[0])
                c.sort()
                self.spec_cursor.setText("\u0394 {0:.1f} nm".format(c[1] - c[0]))
            else:
                self.spec_cursor.setText("{0:.1f} nm".format(event.xdata))

            # Redraw canvas
            self.spec_canvas.draw()

    def pop_overlays(self):
        # Pop overlays if needed
        overlays = None
        keep = 3
        if self.marker_on:
            keep += 1
            if self.marker_delta:
                keep += 1
        if len(self.spectrum_plot.lines) > keep:
            overlays = self.spectrum_plot.lines[keep:]
            while len(self.spectrum_plot.lines) > keep:
                self.spectrum_plot.lines.pop()
        return overlays

    def add_overlays(self, overlays):
        if overlays is not None:
            for o in overlays:
                self.spectrum_plot.lines.append(o)

    @QtCore.pyqtSlot()
    def on_spec_avg_editingFinished(self):
        """ Set number of scans to average. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                self.dev.ScansToAverage = int(self.spec_avg.text())
            except PT.DevFailed as e:
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the number of scans to average (Error: {:})".format(e.args[0].desc))


    @QtCore.pyqtSlot()
    def on_spec_int_editingFinished(self):
        """ Set integration time. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                value = self.spec_int.text()
                if len(value) > 3 and value[-2:] == "ms":
                    value = value[:-3]
                self.dev.IntegrationTime = float(value)
            except PT.DevFailed as e:
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the integration time (Error: {:})".format(e.args[0].desc))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Bad value", "Failed to set the integration time (Error: {:})".format(e))

    @QtCore.pyqtSlot()
    def on_spec_setpoint_editingFinished(self):
        """ Set TEC setpoint. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                value = self.spec_setpoint.text()
                if len(value) > 3 and value[-2:] == "°C":
                    value = value[:-3]
                self.dev.TECSetpoint = float(value)
            except PT.DevFailed as e:
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the integration time (Error: {:})".format(e.args[0].desc))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Bad value", "Failed to set the integration time (Error: {:})".format(e))

    @QtCore.pyqtSlot()
    def on_spec_boxcar_editingFinished(self):
        """ Set number of scans to average. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                self.dev.BoxcarWidth = int(self.spec_boxcar.text())
            except PT.DevFailed as e:
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the boxcar width (Error: {:})".format(e.args[0].desc))

    @QtCore.pyqtSlot(int)
    def on_spec_dark_stateChanged(self, state):
        """ Enable/disable electrical dark correction. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                if state == QtCore.Qt.Checked:
                    self.dev.enableElectricalDarkCorrection = True
                else:
                    self.dev.enableElectricalDarkCorrection = False
            except PT.DevFailed as e:
                self.spec_nl.toggle()
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the dark correction (Error: {:})".format(e.args[0].desc))

    @QtCore.pyqtSlot(int)
    def on_spec_nl_stateChanged(self, state):
        """ Enable/disable NL correction. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                if state == QtCore.Qt.Checked:
                    self.dev.enableNLCorrection = True
                else:
                    self.dev.enableNLCorrection = False
            except PT.DevFailed as e:
                self.spec_nl.toggle()
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the NL correction (Error: {:})".format(e.args[0].desc))


    #
    # Pushbuttons callbacks
    #
    @QtCore.pyqtSlot()
    def on_spec_rescan_released(self):
        """ Connect to spectrometer TANGO device. """
        # Get an updated list of spectrometrs
        spec_list = self.get_spec_list()
        current_spectrometer = self.spec_sel.itemText(self.spec_sel.currentIndex())
        print("Current spectrometer: {:}".format(current_spectrometer))

        if self.dev:
            self.close_spectrometer()

        # Clear all elements
        self.spec_sel.clear()

        if len(spec_list) > 0:
            for i in range(len(spec_list)):
                self.spec_sel.insertItem(i, spec_list[i])
            if current_spectrometer in spec_list:
                self.spec_sel.setCurrentIndex(spec_list.index(current_spectrometer))
            else:
                self.spec_sel.setCurrentIndex(0)

    @QtCore.pyqtSlot()
    def on_spec_bkg_released(self):
        """ Acquire background. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                self.dev.storeBackground()
            except PT.DevFailed as e:
                QtGui.QMessageBox.critical(self, "Failed to store background", "Failed to store the background spectrum (Error: {:})".format(e.args[0].desc))

    @QtCore.pyqtSlot()
    def on_spec_bkgsub_released(self):
        """ Enable/disable background subtraction. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                if self.spec_bkgsub.isChecked():
                    self.dev.enableBackgroundSubtraction = True
                else:
                    self.dev.enableBackgroundSubtraction = False
            except PT.DevFailed as e:
                self.spec_bkgsub.setChecked(self.dev.enableBackgroundSubtraction)
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the background subtraction (Error: {:})".format(e.args[0].desc))

    @QtCore.pyqtSlot()
    def on_spec_tec_released(self):
        """ Enable/disable background subtraction. """
        if self.dev is not None and self.dev_state != PT.DevState.FAULT:
            try:
                if self.spec_tec.isChecked():
                    self.dev.enableTEC = True
                else:
                    self.dev.enableTEC = False
            except PT.DevFailed as e:
                self.spec_bkgsub.setChecked(self.dev.enableTEC)
                QtWidgets.QMessageBox.critical(self, "Failed to set value", "Failed to set the background subtraction (Error: {:})".format(e.args[0].desc))

    @QtCore.pyqtSlot()
    def on_add_overlay_released(self):
        """ Add overlay to spectrum plot. """
        if self.spectrum_plot is not None:
            x = self.spectrum_plot.lines[0].get_xdata()
            y = self.spectrum_plot.lines[0].get_ydata()
            self.spectrum_plot.plot(x, y)

    @QtCore.pyqtSlot()
    def on_clear_overlay_released(self):
        """ Clear all overlays. """
        pop_overlays()

    @QtCore.pyqtSlot()
    def on_pb_exit_released(self):
        """ Close main windows. """
        if self.dev:
            try:
                self.close_spectrometer()
            except PT.DevFailed:
                # Ignore exceptions
                pass
        self.close()

    @QtCore.pyqtSlot()
    def on_save_spec_released(self):
        """ Save spectrum """
        if not self.dev or self.dev.State == PT.DevState.FAULT:
            return

        file_types = []
        file_types.append('HDF5 file (*.h5)')
        file_types.append('CSV file (*.csv)')
        file_types.append('Text file (*.dat)')
        file_types.append('OOIBASE file (*.Master.Scope)')
        file_types.append('All files (*)')
        file_handlers = []
        file_handlers.append(self.save_h5_spectrum)
        file_handlers.append(self.save_csv_spectrum)
        file_handlers.append(self.save_dat_spectrum)
        file_handlers.append(self.save_ooibase_spectrum)
        file_handlers.append(self.save_gen_spectrum)
        # Open pick file dialog
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, ext = QFileDialog.getSaveFileName(self, "Save spectrum","",";;".join(file_types), options=options)
        # Call handler
        if filename:
            file_handlers[file_types.index(ext)](filename)

    def save_h5_spectrum(self, filename):
        if re.match(".*\.h5$", filename) is None:
            filename += ".h5"

        with h5.File(filename, "w") as f:
            wl = self.spectrum_plot.lines[0].get_xdata()
            spec = self.spectrum_plot.lines[0].get_ydata()
            now = datetime.datetime.now()

            f.create_dataset("wavelength", data=wl)
            f.create_dataset("spectrum", data=spec)
            f['spectrum'].attrs.create("Spectrometer model", self.dev.Model)
            f['spectrum'].attrs.create("Spectrometer serial", self.dev.SerialNumber)
            f['spectrum'].attrs.create("Boxcar width", self.dev.BoxcarWidth)
            f['spectrum'].attrs.create("Averages", self.dev.ScansToAverage)
            f['spectrum'].attrs.create("Integration time", self.dev.IntegrationTime)
            f['spectrum'].attrs.create("Electrical dark subtraction", self.dev.enableElectricalDarkCorrection)
            f['spectrum'].attrs.create("Detector NL correction", self.dev.enableNLCorrection)
            f['spectrum'].attrs.create("Date", now.strftime("%Y-%m-%d, %H:%M:%S"))
            f['spectrum'].attrs.create("Timestamp", now.timestamp())

    def save_csv_spectrum(self, filename):
        if re.match(".*\.csv$", filename) is None:
            filename += ".csv"

        with open(filename, 'wt') as f:
            wl = self.spectrum_plot.lines[0].get_xdata()
            spec = self.spectrum_plot.lines[0].get_ydata()
            for w, s in zip(wl, spec):
                f.write("{0:.2f},{1:.3f}\n".format(w, s))

    def save_dat_spectrum(self, filename):
        if re.match(".*\.dat$", filename) is None:
            filename += ".dat"
        self.save_gen_spectrum(filename)

    def save_gen_spectrum(self, filename):
        with open(filename, 'wt') as f:
            wl = self.spectrum_plot.lines[0].get_xdata()
            spec = self.spectrum_plot.lines[0].get_ydata()
            for w, s in zip(wl, spec):
                f.write("{0:.2f}\t{1:.3f}\n".format(w, s))

    def save_ooibase_spectrum(self, filename):
        if re.match(".*\.Master\.Scope$", filename) is None:
            filename += ".Master.Scope"

        with open(filename, 'wt') as f:
            wl = self.spectrum_plot.lines[0].get_xdata()
            spec = self.spectrum_plot.lines[0].get_ydata()

            f.write("OOIBase32 Version 2.0.6.3 Data File\n")
            f.write("++++++++++++++++++++++++++++++++++++\n")
            now = datetime.datetime.now()
            f.write("Date: {0}\n".format(now.strftime("%m-%d-%Y, %H:%M:%S")))
            f.write("User: Valued Ocean Optics Customer\n")
            f.write("Spectrometer Serial Number: {0}\n".format(self.dev.SerialNumber))
            f.write("Spectrometer Channel: Master\n")
            f.write("Integration Time (msec): {0:d}\n".format(int(self.dev.IntegrationTime)))
            f.write("Spectra Averaged: {0:d}\n".format(int(self.dev.ScansToAverage)))
            f.write("Boxcar Smoothing: {0:d}\n".format(int(self.dev.BoxcarWidth)))
            f.write("Correct for Electrical Dark: {0}\n".format("Enabled" if self.dev.enableElectricalDarkCorrection else "Disabled"))
            f.write("Time Normalized: Disabled\n")
            f.write("Dual-beam Reference: Disabled\n")
            f.write("Reference Channel: Master\n")
            f.write("Temperature: Not acquired\n")
            f.write("Spectrometer Type: {0}\n".format(self.dev.Model))
            f.write("ADC Type: {0}\n".format(self.dev.Model))
            f.write("Number of Pixels in File: {0:d}\n".format(len(wl)))
            f.write("Graph Title:\n")
            f.write(">>>>>Begin Spectral Data<<<<<\n")
            for w, s in zip(wl, spec):
                f.write("{0:.2f}\t{1:.3f}\n".format(w, s))
            f.write(">>>>>End Spectral Data<<<<<\n")

    @QtCore.pyqtSlot()
    def on_spec_delta_released(self):
        """ Close main windows. """
        if not self.spec_delta.isChecked() and self.marker_delta:
            # Remove second cursor
            overlays = self.pop_overlays()
            if len(self.spectrum_plot.lines) == 5:
                self.spectrum_plot.lines.pop()
            else:
                print("ERROR: missing line for second cursor")
            self.marker_delta = False
            # Update label
            self.spec_cursor.setText("{0:.1f} nm".format(self.spectrum_plot.lines[3].get_xdata()[0]))
            self.add_overlays(overlays)

    @QtCore.pyqtSlot()
    def on_spec_setscale_released(self):
        dlg = SpectrumViewer_Setscale(self.spectrum_plot.get_xlim(), self.spectrum_plot.get_ylim(), self.scaling, self)
        res = dlg.exec_()
        if res == 1:
            # Pressed ok. get values
            try:
                xmin = float(dlg.min_wl.text())
                xmax = float(dlg.max_wl.text())
                self.spectrum_plot.set_xlim([xmin, xmax])
            except ValueError:
                pass

            try:
                ymin = float(dlg.min_counts.text())
                ymax = float(dlg.max_counts.text())
                self.spectrum_plot.set_ylim([ymin, ymax])
            except ValueError:
                pass

    @QtCore.pyqtSlot()
    def on_spec_restore_released(self):
        if self.spectrum_plot is not None:
            xmin = np.min(self.spectrum_plot.lines[0].get_xdata())
            xmax = np.max(self.spectrum_plot.lines[0].get_xdata())
            self.spectrum_plot.set_xlim([xmin, xmax])
            ymin = np.min(self.spectrum_plot.lines[0].get_ydata())
            ymax = np.max(self.spectrum_plot.lines[0].get_ydata())
            self.spectrum_plot.set_ylim([ymin, ymax])

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, event):
        """ Handle the resize event of the window. """
        if event.size().isValid() and event.oldSize().isValid() and not self.inhibith_resize:
            w = event.size().width()
            h = event.size().height()
            dw = w - event.oldSize().width()
            dh = h - event.oldSize().height()

            print("Resized window to ({:d}, {:d})".format(w, h))

            sz = self.spectrum_area.size()
            self.spectrum_area.resize(sz.width() + dw, sz.height() + dh)
            self.spec_fig.tight_layout()

            ps = self.save_spec.pos()
            self.save_spec.move(QtCore.QPoint(ps.x() + dw, ps.y() + dh))

            ps = self.pb_exit.pos()
            self.pb_exit.move(QtCore.QPoint(ps.x() + dw, ps.y() + dh))

            ps = self.bw_frame.pos()
            self.bw_frame.move(QtCore.QPoint(ps.x(), ps.y() + dh))

        else:
            QtWidgets.QMainWindow.resizeEvent(self, event)

    def getFWHM(self, wl, sp):
        """ Compute the FWHM width of the spectrum. """
        # ID of maximum value
        max_id = np.argmax(sp)
        if max_id == 0:
            return (np.nan, np.nan)
        # FWHM threshold
        fwhm_th = (np.max(sp) +  np.min(sp)) / 2
        # Absolute value of spectrum minus threshold
        sp_abs = np.abs(sp - fwhm_th)
        # Local minima (before and after the maximum)
        x1 = np.argmin(sp_abs[0:max_id])
        x2 = np.argmin(sp_abs[max_id:]) + max_id

        return (wl[x1], wl[x2])


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    if app.primaryScreen().physicalDotsPerInch() > 120:
        app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True) # Enable HiDpi
    ui = SpectrumViewer()
    ui.show()
    ret = app.exec_()
    sys.exit(ret)