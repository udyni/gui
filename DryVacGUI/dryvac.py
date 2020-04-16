#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 13 13:16:03 2015

@author: wyrdmeister
"""

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from Ui_dryvac import Ui_DryVacGUI

import time
import PyTango as PT


class DryVacGUI(QtWidgets.QMainWindow, Ui_DryVacGUI):

    # Tango change event signal
    tango_event = QtCore.pyqtSignal(PT.EventData)

    """ Constructor
    """
    def __init__(self, parent=None):
        # Parent constructors
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

        # Open Tango device
        self.dev = PT.DeviceProxy("udyni/vacuum/mainpump01")
        self.dev.ping()

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Subscribe all the relevant events
        self.dev.subscribe_event("FreqSetpoint", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("Frequency", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("Current", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("Voltage", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("Power", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("Temperature", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("Pressure", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("EnablePurge", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("EnableBallast", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("CompressedAir", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("WaterValve", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("State", PT.EventType.CHANGE_EVENT, self.event_callback)

        # Start timer
        self.timer_id = self.startTimer(1000)

        print("Init done!")

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

    def event_callback(self, event):
        """ Event callback
        """
        if not event.err:
            self.tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, event):
        if event.attr_value.name == "FreqSetpoint":
            pass
        elif event.attr_value.name == "Frequency":
            self.freq.setText(u"{0:.2f}".format(event.attr_value.value))
        elif event.attr_value.name == "Current":
            self.current.setText(u"{0:.2f}".format(event.attr_value.value))
        elif event.attr_value.name == "Voltage":
            self.voltage.setText(u"{0:.2f}".format(event.attr_value.value))
        elif event.attr_value.name == "Power":
            self.power.setText(u"{0:.2f}".format(event.attr_value.value))
        elif event.attr_value.name == "Temperature":
            self.temperature.setText(u"{0:d}".format(int(event.attr_value.value)))
        elif event.attr_value.name == "Pressure":
            self.pressure.setText(u"{0:.2E}".format(event.attr_value.value))
        elif event.attr_value.name == "EnablePurge":
            if event.attr_value.value:
                self.purge.setChecked(True)
            else:
                self.purge.setChecked(False)
        elif event.attr_value.name == "EnableBallast":
            if event.attr_value.value:
                self.ballast.setChecked(True)
            else:
                self.ballast.setChecked(False)
        elif event.attr_value.name == "CompressedAir":
            if event.attr_value.value:
                self.comp_air.setChecked(True)
            else:
                self.comp_air.setChecked(False)
        elif event.attr_value.name == "WaterValve":
            if event.attr_value.value == PT.DevState.CLOSE:
                self.watervalve.setText(u"Water close")
                self.watervalve.setStyleSheet("border: 1px solid black; background-color: white; color: black")
            elif event.attr_value.value == PT.DevState.OPEN:
                self.watervalve.setText(u"Water open")
                self.watervalve.setStyleSheet("border: 1px solid black; background-color: darkgreen; color: white")
            elif event.attr_value.value == PT.DevState.MOVING:
                self.watervalve.setText(u"Moving...")
                self.watervalve.setStyleSheet("border: 1px solid black; background-color: blue; color: white")
            else:
                self.watervalve.setText(u"Cooling error")
                self.watervalve.setStyleSheet("border: 1px solid black; background-color: orange; color: black")
        elif event.attr_value.name == "State":
            if event.attr_value.value == PT.DevState.RUNNING:
                self.status.setText(u"Running")
                self.status.setStyleSheet("border: 1px solid black; background-color: darkgreen; color: white")
            elif event.attr_value.value == PT.DevState.STANDBY:
                self.status.setText(u"Standby")
                self.status.setStyleSheet("border: 1px solid black; background-color: white; color: black")
            elif event.attr_value.value == PT.DevState.ALARM:
                self.status.setText(u"Alarm")
                self.status.setStyleSheet("border: 1px solid black; background-color: orange; color: black")
            elif event.attr_value.value == PT.DevState.FAULT:
                self.status.setText(u"Fault")
                self.status.setStyleSheet("border: 1px solid black; background-color: red; color: white")
            else:
                self.status.setText(u"Unknown")
                self.status.setStyleSheet("border: 1px solid black; background-color: red; color: white")

    @QtCore.pyqtSlot(QtCore.QTimerEvent)
    def timerEvent(self, event):
        """ Timer event
        """
        # Get data
        try:
            # Read setpoint
            if not self.freq_sp.hasFocus():
                self.freq_sp.setText(u"{0:d}".format(int(self.dev.FreqSetpoint)))

        except PT.DevFailed as e:
            print("Tango Exception: {0:}".format(e))
        except Exception as e:
            print("Generic exception: {0:}".format(e))

    @QtCore.pyqtSlot()
    def on_freq_sp_editingFinished(self):
        try:
            value = int(self.freq_sp.text())
            if value < 0 or value > 120:
                 QtWidgets.QMessageBox.critical(self, "Bad value", "The given value is not valid. Should be between 0 and 120")
            else:
                print("Value changed: {0:d}".format(value))
                self.dev.FreqSetpoint = value
                time.sleep(0.1)
                if value != self.dev.FreqSetpoint:
                    QtWidgets.QMessageBox.critical(self, "Setpoint failed", "Failed to set frequency setpoint")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Set failed", "Failed to set frequency (Error: {0!s})".format(e.args[0].desc))
        except ValueError:
            QtWidgets.QMessageBox.critical(self, "Bad value", "The given value is not a valid number")

    @QtCore.pyqtSlot(bool)
    def on_purge_clicked(self, checked):
        try:
            self.dev.EnablePurge = checked
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Set failed", "Failed to set purge (Error: {0!s})".format(e.args[0].desc))

    @QtCore.pyqtSlot(bool)
    def on_ballast_clicked(self, checked):
        try:
            self.dev.EnableBallast = checked
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Set failed", "Failed to set ballast (Error: {0!s})".format(e.args[0].desc))

    @QtCore.pyqtSlot()
    def on_bn_start_released(self):
        """ Start pump. """
        try:
            self.dev.Start()
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Set failed", "Failed to start pump (Error: {0!s})".format(e.args[0].desc))


    @QtCore.pyqtSlot()
    def on_bn_stop_released(self):
        """ Stop pump. """
        try:
            self.dev.Stop()
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Stop failed", "Failed to stop pump (Error: {0!s})".format(e.args[0].desc))

    @QtCore.pyqtSlot()
    def on_bn_reset_released(self):
        """ Close main windows. """
        try:
            self.dev.Reset()
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Reset failed", "Failed reset pump (Error: {0!s})".format(e.args[0].desc))

    @QtCore.pyqtSlot()
    def on_bn_exit_released(self):
        """ Close main windows. """
        self.close()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ui = DryVacGUI()
    ui.show()
    ret = app.exec_()
    sys.exit(ret)