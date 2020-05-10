# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 14:41:50 2014

@author: Michele Devetta <michele.devetta@cnr.it>
"""

import sys
import os
## Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '..'))
sys.path.insert(1, os.path.join(sys.path[0], '../Icons'))

import time
import numpy as np

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from Ui_camerasetup import Ui_CameraSetup

import PyTango as PT
from PyQTango import TangoUtil

# Matplotlib stuff
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class CameraSetup(QtWidgets.QDialog, Ui_CameraSetup):
    """ Configure camera
    """

    # Tango change event signal
    tango_event = QtCore.pyqtSignal(PT.EventData)

    def __init__(self, camera, scaling=1.0, parent=None):
        """ Constructor. Initialize dialog
        """
        # Parent construcor
        QtWidgets.QDialog.__init__(self, parent)

        # Store scaling
        self.scaling = scaling

        # Build UI
        self.setupUi(self)
        self.setup_fonts_and_scaling()

        # Get DB
        self.db = PT.Database()

        # Camera
        self.dev = None
        self.ev_id = []
        self.dev_ready = False

        # Setup canvas for spectrum
        self.fig = Figure()
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setParent(self)
        self.image_plot = None
        self.image_last = 0
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.canvas)
        self.image_area.setLayout(vbox)

        # Get camera classes
        prop = self.db.get_property("LaserCamera", "CameraClasses")
        if len(prop['CameraClasses']):
            classes = prop['CameraClasses']
        else:
            classes = ['BaslerGigE']

        # Find all available cameras
        devs = TangoUtil.getAllLiveDevicesByClass(classes)
        # Close if no device found
        if not len(devs):
            raise RuntimeError("No camera available")

        # Populate camera select combo box
        for d in devs:
            if d['alive']:
                self.cam_select.addItem(d['device'])

        # Set current item
        if camera in devs:
            self.cam_select.setCurrentIndex(devs.index(camera))
        else:
            self.cam_select.setCurrentIndex(0)

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Setup camera
        self.setup_camera(self.cam_select.currentText())

        # Connect currentIndexChanged slot
        self.cam_select.currentIndexChanged.connect(self.change_camera)

    def setup_fonts_and_scaling(self):
        """ Scale GUI if needed
        """
        # Setup font size and scaling on hidpi
        if self.scaling > 1.1:
            # Scale only if factor is more than 1.1
            self.scale_widget(self, self.scaling)
            members = dir(self)
            for m in members:
                if issubclass(type(getattr(self, m)), QtWidgets.QWidget):
                    self.scale_widget(getattr(self, m), self.scaling)

    def scale_widget(self, widget, scaling):
        """ Scale a single widget
        """
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))

    @QtCore.pyqtSlot(int)
    def change_camera(self, index):
        """ Change current camera
        """
        if self.dev is not None and self.dev.name() == self.cam_select.currentText():
            return
        self.setup_camera(self.cam_select.currentText())


    def close_camera(self):
        """ Close the current camera and unsubscribe events
        """
        if self.dev is not None:
            # Close previous camera
            for ev in self.ev_id:
                try:
                    self.dev.unsubscribe_event(ev)
                except PT.DevFailed as e:
                    print("[E] Error unsubscribing event ({0!s})".format(e.args[0].desc))
            self.dev = None
            self.ev_id = []
            self.dev_ready = False

    def setup_camera(self, device):
        """ Setup a new camera for the dialog
        """
        self.close_camera()
        try:
            self.dev = PT.DeviceProxy(device)

            # Populate spinboxes
            self.set_spinbox_minmax(self.exposure, "ExposureTime")
            self.set_spinbox_minmax(self.gain, "Gain")
            self.set_spinbox_minmax(self.autoexposure_brightness, "AutoBrightnessTarget")
            self.set_spinbox_minmax(self.autoexposure_min, "AutoExposureLowerLimit")
            self.set_spinbox_minmax(self.autoexposure_max, "AutoExposureUpperLimit")

            # Value changed flags
            self.exposure_vc = False
            self.gain_vc = False
            self.autoexposure_brightness_vc = False
            self.autoexposure_min_vc = False
            self.autoexposure_max_vc = False

            # Populate comboboxes
            self.populate_combobox(self.trigger_src, "TriggerSource")
            self.populate_combobox(self.pixelformat, "PixelFormat")
            self.populate_combobox(self.autoexposure, "AutoExposure")

            # Subscribe events
            self.ev_id.append(self.dev.subscribe_event("ExposureTime", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("Gain", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("EnableTrigger", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("TriggerSource", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("PixelFormat", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("AutoExposure", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("AutoBrightnessTarget", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("AutoExposureLowerLimit", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("AutoExposureUpperLimit", PT.EventType.CHANGE_EVENT, self.event_callback))
            self.ev_id.append(self.dev.subscribe_event("Image", PT.EventType.CHANGE_EVENT, self.event_callback))

            # Set device ready flag
            self.dev_ready = True

        except PT.DevFailed as e:
            print("[E] Error setting up camera ({0!s})".format(e.args[0].desc))
            if self.isVisible():
                self.reject()
            else:
                raise RuntimeError("Failed to setup camera")

    def populate_combobox(self, widget, attribute):
        """ Add elements to combobox
        """
        att_conf = self.dev.get_attribute_config(attribute)
        widget.clear()
        widget.addItems(att_conf.enum_labels)

    def set_spinbox_minmax(self, widget, attribute):
        """ Set minimum and maximum of a spinbox
        """
        att_conf = self.dev.get_attribute_config(attribute)
        if type(widget) == QtWidgets.QSpinBox:
            widget.setMinimum(int(att_conf.min_value))
            widget.setMaximum(int(att_conf.max_value))
        elif type(widget) == QtWidgets.QDoubleSpinBox:
            widget.setMinimum(float(att_conf.min_value))
            widget.setMaximum(float(att_conf.max_value))
        widget.setSuffix(att_conf.unit)

    def event_callback(self, event):
        """ Event callback
        """
        self.tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, ev):
        """ TANGO Event handler
        """
        if ev.err:
            print("[E] {0!s}".format(ev.errors[0].desc))

        else:
            print("Got event from {0}".format(ev.attr_value.name))
            attr_name = ev.attr_value.name.lower()

            if attr_name == 'exposuretime':
                if self.exposure_vc:
                    self.exposure.setStyleSheet("color: red")
                else:
                    self.gain.blockSignals(True)
                    self.exposure.setValue(ev.attr_value.value)
                    self.gain.blockSignals(False)

            elif attr_name == 'gain':
                if self.gain_vc:
                    self.gain.setStyleSheet("color: red")
                else:
                    self.gain.blockSignals(True)
                    self.gain.setValue(ev.attr_value.value)
                    self.gain.blockSignals(False)

            elif attr_name == 'enabletrigger':
                self.trigger_en.setChecked(bool(ev.attr_value.value))

            elif attr_name == 'triggersource':
                self.trigger_src.setCurrentIndex(ev.attr_value.value)

            elif attr_name == 'pixelformat':
                self.pixelformat.setCurrentIndex(ev.attr_value.value)

            elif attr_name == 'autoexposure':
                self.autoexposure.setCurrentIndex(ev.attr_value.value)

            elif attr_name == 'autobrightnesstarget':
                if self.autoexposure_brightness_vc:
                    self.autoexposure_brightness.setStyleSheet("color: red")
                else:
                    self.autoexposure_brightness.blockSignals(True)
                    self.autoexposure_brightness.setValue(ev.attr_value.value)
                    self.autoexposure_brightness.blockSignals(False)

            elif attr_name == 'autoexposurelowerlimit':
                if self.autoexposure_min_vc:
                    self.autoexposure_min.setStyleSheet("color: red")
                else:
                    self.autoexposure_min.blockSignals(True)
                    self.autoexposure_min.setValue(ev.attr_value.value)
                    self.autoexposure_min.blockSignals(False)

            elif attr_name == 'autoexposureupperlimit':
                if self.autoexposure_max_vc:
                    self.autoexposure_max.setStyleSheet("color: red")
                else:
                    self.autoexposure_max.blockSignals(True)
                    self.autoexposure_max.setValue(ev.attr_value.value)
                    self.autoexposure_max.blockSignals(False)

            elif attr_name == 'image':
                if time.time() - self.image_last > 0.5:
                    img = ev.attr_value.value
                    if self.image_plot is None:
                        self.image_plot = self.fig.add_subplot(111)
                        self.image_plot.axis('Off')
                        self.image_plot.imshow(img, cmap='jet')
                        self.fig.tight_layout()
                    else:
                        self.image_plot.images[0].set_array(img)
                        self.image_plot.images[0].set_clim([np.min(img), np.max(img)])
                    self.image_last = time.time()
                    self.canvas.draw()

    def accept(self):
        """ Intercept accept() to close camera
        """
        self.close_camera()
        QtWidgets.QDialog.accept(self)

    def reject(self):
        """ Intercept reject() to close camera
        """
        self.close_camera()
        QtWidgets.QDialog.reject(self)

    ##
    ## ExposureTime
    ##
    @QtCore.pyqtSlot(float)
    def on_exposure_valueChanged(self, value):
        if self.dev_ready:
            self.exposure_vc = True
            self.exposure_c.setDisabled(False)
            self.exposure_r.setDisabled(False)
            self.exposure.setStyleSheet("color: darkgreen")

    @QtCore.pyqtSlot()
    def on_exposure_c_released(self):
        self.exposure.blockSignals(True)
        try:
            self.dev.ExposureTime = self.exposure.value()
            self.exposure_vc = False
            self.exposure_c.setDisabled(True)
            self.exposure_r.setDisabled(True)
            self.exposure.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set ExposureTime", e.args[0].desc)
        self.exposure.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_exposure_r_released(self):
        self.exposure.blockSignals(True)
        try:
            self.exposure.setValue(self.dev.ExposureTime)
            self.exposure_vc = False
            self.exposure_c.setDisabled(True)
            self.exposure_r.setDisabled(True)
            self.exposure.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore ExposureTime", e.args[0].desc)
        self.exposure.blockSignals(False)

    ##
    ## Gain
    ##
    @QtCore.pyqtSlot(float)
    def on_gain_valueChanged(self, value):
        if self.dev_ready:
            self.gain_vc = True
            self.gain_c.setDisabled(False)
            self.gain_r.setDisabled(False)
            self.gain.setStyleSheet("color: darkgreen")

    @QtCore.pyqtSlot()
    def on_gain_c_released(self):
        self.gain.blockSignals(True)
        try:
            self.dev.Gain = self.gain.value()
            self.gain_vc = False
            self.gain_c.setDisabled(True)
            self.gain_r.setDisabled(True)
            self.gain.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set Gain", e.args[0].desc)
        self.gain.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_gain_r_released(self):
        self.gain.blockSignals(True)
        try:
            self.gain.setValue(self.dev.Gain)
            self.gain_vc = False
            self.gain_c.setDisabled(True)
            self.gain_r.setDisabled(True)
            self.gain.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore Gain", e.args[0].desc)
        self.gain.blockSignals(False)

    ##
    ## PixelFormat
    ##
    @QtCore.pyqtSlot(int)
    def on_pixelformat_currentIndexChanged(self, index):
        if self.dev_ready:
            try:
                self.dev.PixelFormat = index
            except PT.DevFailed as e:
                self.pixelformat.blockSignals(True)
                try:
                    self.pixelformat.setCurrentIndex(self.dev.PixelFormat)
                except PT.DevFailed:
                    self.pixelformat.setDisable(True)
                self.pixelformat.blockSignals(False)
                QtWidgets.QMessageBox.critical(self, "Failed to set pixel format", "Failed to set pixel format (Error: {0!s})".format(e.args[0].desc))

    ##
    ## TriggerSource
    ##
    @QtCore.pyqtSlot(int)
    def on_trigger_src_currentIndexChanged(self, index):
        if self.dev_ready:
            try:
                self.dev.TriggerSource = index
            except PT.DevFailed as e:
                self.trigger_src.blockSignals(True)
                try:
                    self.trigger_src.setCurrentIndex(self.dev.TriggerSource)
                except PT.DevFailed:
                    self.trigger_src.setDisable(True)
                self.trigger_src.blockSignals(False)
                QtWidgets.QMessageBox.critical(self, "Failed to set trigger source", "Failed to set trigger source (Error: {0!s})".format(e.args[0].desc))

    ##
    ## EnableTrigger
    ##
    @QtCore.pyqtSlot(int)
    def on_trigger_en_stateChanged(self, state):
        if self.dev_ready:
            try:
                if state == QtCore.Qt.Checked:
                    self.dev.EnableTrigger = True
                else:
                    self.dev.EnableTrigger = False
            except PT.DevFailed as e:
                self.trigger_en.blockSignals(True)
                try:
                    self.trigger_en.setChecked(self.dev.EnableTrigger)
                except PT.DevFailed:
                    self.trigger_en.setDisable(True)
                self.trigger_en.blockSignals(False)
                op = "en" if state == QtCore.Qt.Checked else "dis"
                QtWidgets.QMessageBox.critical(self, "Failed to {0}able trigger".format(op), "Failed to {0}able trigger (Error: {1!s})".format(op, e.args[0].desc))

    ##
    ## AutoExposure
    ##
    @QtCore.pyqtSlot(int)
    def on_autoexposure_currentIndexChanged(self, index):
        if self.dev_ready:
            try:
                self.dev.AutoExposure = index
            except PT.DevFailed as e:
                self.autoexposure.blockSignals(True)
                try:
                    self.autoexposure.setCurrentIndex(self.dev.AutoExposure)
                except PT.DevFailed:
                    self.autoexposure.setDisable(True)
                self.autoexposure.blockSignals(False)
                QtWidgets.QMessageBox.critical(self, "Failed to set auto exposure", "Failed to set auto exposure (Error: {0!s})".format(e.args[0].desc))

    ##
    ## AutoBrightnessTarget
    ##
    @QtCore.pyqtSlot(int)
    def on_autoexposure_brightness_valueChanged(self, value):
        if self.dev_ready:
            self.autoexposure_brightness_vc = True
            self.autoexposure_brightness_c.setDisabled(False)
            self.autoexposure_brightness_r.setDisabled(False)
            self.autoexposure_brightness.setStyleSheet("color: darkgreen")

    @QtCore.pyqtSlot()
    def on_autoexposure_brightness_c_released(self):
        self.autoexposure_brightness.blockSignals(True)
        try:
            self.dev.AutoBrightnessTarget = self.autoexposure_brightness.value()
            self.autoexposure_brightness_vc = False
            self.autoexposure_brightness_c.setDisabled(True)
            self.autoexposure_brightness_r.setDisabled(True)
            self.autoexposure_brightness.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set AutoBrightnessTarget", e.args[0].desc)
        self.autoexposure_brightness.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_autoexposure_brightness_r_released(self):
        self.autoexposure_brightness.blockSignals(True)
        try:
            self.autoexposure_brightness.setValue(self.dev.AutoBrightnessTarget)
            self.autoexposure_brightness_vc = False
            self.autoexposure_brightness_c.setDisabled(True)
            self.autoexposure_brightness_r.setDisabled(True)
            self.autoexposure_brightness.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore AutoBrightnessTarget", e.args[0].desc)
        self.autoexposure_brightness.blockSignals(False)

    ##
    ## AutoExposureLowerLimit
    ##
    @QtCore.pyqtSlot(float)
    def on_autoexposure_min_valueChanged(self, value):
        if self.dev_ready:
            self.autoexposure_min_vc = True
            self.autoexposure_min_c.setDisabled(False)
            self.autoexposure_min_r.setDisabled(False)
            self.autoexposure_min.setStyleSheet("color: darkgreen")

    @QtCore.pyqtSlot()
    def on_autoexposure_min_c_released(self):
        self.autoexposure_min.blockSignals(True)
        try:
            self.dev.AutoExposureLowerLimit = self.autoexposure_min.value()
            self.autoexposure_min_vc = False
            self.autoexposure_min_c.setDisabled(True)
            self.autoexposure_min_r.setDisabled(True)
            self.autoexposure_min.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set AutoExposureLowerLimit", e.args[0].desc)
        self.autoexposure_min.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_autoexposure_min_r_released(self):
        self.autoexposure_min.blockSignals(True)
        try:
            self.autoexposure_min.setValue(self.dev.AutoExposureLowerLimit)
            self.autoexposure_min_vc = False
            self.autoexposure_min_c.setDisabled(True)
            self.autoexposure_min_r.setDisabled(True)
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore AutoExposureLowerLimit", e.args[0].desc)
        self.autoexposure_min.blockSignals(False)

    ##
    ## AutoExposureUpperLimit
    ##
    @QtCore.pyqtSlot(float)
    def on_autoexposure_max_valueChanged(self, value):
        if self.dev_ready:
            self.autoexposure_max_vc = True
            self.autoexposure_max_c.setDisabled(False)
            self.autoexposure_max_r.setDisabled(False)
            self.autoexposure_max.setStyleSheet("color: darkgreen")


    @QtCore.pyqtSlot()
    def on_autoexposure_max_c_released(self):
        self.autoexposure_max.blockSignals(True)
        try:
            self.dev.AutoExposureUpperLimit = self.autoexposure_max.value()
            self.autoexposure_max_vc = False
            self.autoexposure_max_c.setDisabled(True)
            self.autoexposure_max_r.setDisabled(True)
            self.autoexposure_max.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set AutoExposureUpperLimit", e.args[0].desc)
        self.autoexposure_max.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_autoexposure_max_r_released(self):
        self.autoexposure_max.blockSignals(True)
        try:
            self.autoexposure_max.setValue(self.dev.AutoExposureUpperLimit)
            self.autoexposure_max_vc = False
            self.autoexposure_max_c.setDisabled(True)
            self.autoexposure_max_r.setDisabled(True)
            self.autoexposure_max.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore AutoExposureUpperLimit", e.args[0].desc)
        self.autoexposure_max.blockSignals(False)
