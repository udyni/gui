#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic GUI to control SmarAct devices

Created on Mon Jun 14 13:38:34 2021

@author: Michele Devetta <michele.devetta@cnr.it>
"""

import sys
import os
import PyTango as PT
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui

# Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '..'))
sys.path.insert(1, os.path.join(sys.path[0], '../Icons'))

from Ui_smaract import Ui_SmarActControl
from PyQTango import QDigitDial


class SmarActControl(QtWidgets.QMainWindow, Ui_SmarActControl):

    # Tango change event signal
    tango_event = QtCore.pyqtSignal(PT.EventData)

    def __init__(self, parent=None):
        # Parent constructor
        QtWidgets.QMainWindow.__init__(self, parent)

        self.dev = None
        self.evid = []

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

        # Value
        self.value = QDigitDial("6.3f", self.position)
        self.value.valueChangeSignal.connect(self.onValueChangeEvent)
        sz = self.value.size()
        self.position.resize(sz.width(), sz.height())

        self.setup_fonts_and_scaling()

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Populate device list
        self.update_device_list()

    @QtCore.pyqtSlot(float, float)
    def onValueChangeEvent(self, value, old_value):
        if self.dev is not None:
            try:
                self.dev.Position = value
            except PT.DevFailed as e:
                print("Failed to set position (Error: {0!s})".format(e.args[0].desc))
                self.value.setWriteValue(old_value)
        else:
            self.value.setWriteValue(old_value)

    def event_callback(self, event):
        """ Event callback
        """
        self.tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, event):
        """ Event handler
        """
        if not event.err:
            if event.attr_value.name.lower() == "position":
                self.value.setValue(event.attr_value.value)

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

    def update_device_list(self):
        while self.devices.count() > 0:
            self.devices.removeItem(0)

        db = PT.Database()
        datum = db.get_device_exported_for_class("SmarActPositioner")
        for dev in datum.value_string:
            try:
                # Check if direct control is forbidden
                nodc = bool(db.get_device_property(dev, 'no_direct_control')['no_direct_control'])
                if not nodc:
                    dp = PT.DeviceProxy(dev)
                    dp.ping()
                    self.devices.addItem(dev)
            except PT.DevFailed:
                print("Device '{0}' is not reachable".format(dev))

    @QtCore.pyqtSlot(int)
    def on_devices_currentIndexChanged(self, devid):
        print("Current device: {0}")
        if self.dev is not None:
            if len(self.evid):
                for e in self.evid:
                    try:
                        self.dev.unsubscribe_event(e)
                    except PT.DevFailed:
                        pass
            self.dev = None
            self.evid = []
        self.dev = PT.DeviceProxy(self.devices.currentText())
        self.evid.append(self.dev.subscribe_event("Position", PT.EventType.CHANGE_EVENT, self.event_callback))
        self.is_cal.setTangoAttribute(self.dev.name() + "/IsCalibrated")
        self.is_ref.setTangoAttribute(self.dev.name() + "/IsReferenced")
        self.state.setTangoAttribute(self.dev.name() + "/State")
        self.value.setWriteValue(self.value.value())

    @QtCore.pyqtSlot()
    def on_pb_calibrate_released(self):
        if self.dev is not None:
            self.dev.Calibrate()

    @QtCore.pyqtSlot()
    def on_pb_reference_released(self):
        if self.dev is not None:
            self.dev.Reference()

    @QtCore.pyqtSlot()
    def on_pb_reset_released(self):
        if self.dev is not None:
            self.value.setWriteValue(self.value.value())

    @QtCore.pyqtSlot()
    def on_pb_stop_released(self):
        if self.dev is not None:
            self.dev.Stop()

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

            ps = self.close_button.pos()
            self.close_button.move(QtCore.QPoint(ps.x() + dw, ps.y() + dh))

        else:
            QtWidgets.QMainWindow.resizeEvent(self, event)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ui = SmarActControl()
    ui.show()
    ret = app.exec_()
    sys.exit(ret)
