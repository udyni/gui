#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 10 22:21:29 2020

@author: Michele Devetta <michele.devetta@cnr.it>
"""

import sys
import os
## Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '../Icons'))

from PyQt5 import QtCore
from PyQt5 import QtWidgets

import PyTango as PT

from Ui_compressor import Ui_Compressor


class Compressor(QtWidgets.QMainWindow, Ui_Compressor):

    """ HE compressor control """

    # Tango change event signal
    tango_event = QtCore.pyqtSignal(PT.EventData)

    def __init__(self, debug=False, parent=None):
        # Parent constructors
        QtWidgets.QMainWindow.__init__(self, parent)

        # Debug flag
        self.debug_enabled = debug

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
        self.setup_fonts_and_scaling()


        self.position.blockSignals(True)
        self.velocity.blockSignals(True)
        self.acceleration.blockSignals(True)

        # Set minimum and maximum
        self.position.setMinimum(int(-2**28))
        self.position.setMaximum(int(2**28))
        self.position.setSingleStep(1)
        self.velocity.setMinimum(16.0)
        self.velocity.setMaximum(5000.0)
        self.velocity.setSingleStep(1.0)
        self.acceleration.setMinimum(49.0)
        self.acceleration.setMaximum(1518.0)
        self.acceleration.setSingleStep(1.0)

        self.position.blockSignals(False)
        self.velocity.blockSignals(False)
        self.acceleration.blockSignals(False)

        # Setup device
        try:
            self.dev = PT.DeviceProxy("udyni/laser/compressor")
            self.dev.ping()
        except PT.DevFailed:
            QtWidgets.QMessageBox.critical(self, "Device not found", "Cannot connect to the compressor control device")
            app.quit()

        # Value changed flags
        self.position_vc = False
        self.velocity_vc = False
        self.acceleration_vc = False

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Subscribe events
        try:
            self.ev_id = []
            for a in ['Position', 'Velocity', 'Acceleration', 'Temperature', 'Voltage', 'State']:
                ev = self.dev.subscribe_event(a, PT.EventType.CHANGE_EVENT, self.event_callback)
                self.ev_id.append(ev)

        except PT.DevFailed as e:
            self.error("Failed to subscribe events. Error: {0!s}".format(e.args[0].desc))
            QtWidgets.QMessageBox.critical(self, "Failed to connect", "Failed to connecto to device events")
            app.quit()

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

        # Set title dimension
        app = QtWidgets.QApplication.instance()
        df = app.font()
        self.title.setStyleSheet("font-size: {0:d}pt; font-weight: bold".format(int(df.pointSize()*1.5)));

    def scale_widget(self, widget, scaling):
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))

    def event_callback(self, event):
        """ Event callback
        """
        self.tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, ev):
        """ TANGO Event handler
        """
        if ev.err:
            self.error("Event error ({0!s})".format(ev.errors[0].desc))

        else:
            self.debug("Got event from {0}".format(ev.attr_value.name))
            attr_name = ev.attr_value.name.lower()
            attr_value = ev.attr_value.value

            if attr_name == "state":
                base_style = "border-radius: 2px; border: 1px solid; border-color: black; "
                if attr_value == PT.DevState.OFF:
                    self.state.setText("Off")
                    self.state.setStyleSheet(base_style + "background-color: white; color: black")

                elif attr_value == PT.DevState.STANDBY:
                    self.state.setText("Standby")
                    self.state.setStyleSheet(base_style + "background-color: yellow; color: black")

                elif attr_value == PT.DevState.MOVING:
                    self.state.setText("Moving")
                    self.state.setStyleSheet(base_style + "background-color: blue; color: black")

                elif attr_value == PT.DevState.FAULT:
                    self.state.setText("Fault")
                    self.state.setStyleSheet(base_style + "background-color: red; color: white")

                else:
                    self.state.setText("UNKN")
                    self.state.setStyleSheet(base_style + "background-color: gray; color: black")

            elif attr_name == "position":
                if self.position_vc:
                    self.position.setStyleSheet("color: red")
                else:
                    self.position.blockSignals(True)
                    self.position.setValue(attr_value)
                    self.position.blockSignals(False)

            elif attr_name == "velocity":
                if self.velocity_vc:
                    self.velocity.setStyleSheet("color: red")
                else:
                    self.velocity.blockSignals(True)
                    self.velocity.setValue(attr_value)
                    self.velocity.blockSignals(False)

            elif attr_name == "acceleration":
                if self.acceleration_vc:
                    self.acceleration.setStyleSheet("color: red")
                else:
                    self.acceleration.blockSignals(True)
                    self.acceleration.setValue(attr_value)
                    self.acceleration.blockSignals(False)

            elif attr_name == "temperature":
                self.temperature.setText("{0:.1f} °C".format(attr_value))

            elif attr_name == "voltage":
                self.voltage.setText("{0:.1f} V".format(attr_value))

            else:
                self.debug("Unexpected attribute '{0}'".format(attr_name))

    ##
    ## Position
    ##
    @QtCore.pyqtSlot(float)
    def on_position_valueChanged(self, value):
        self.position_vc = True
        self.position_c.setDisabled(False)
        self.position_r.setDisabled(False)
        self.position.setStyleSheet("color: darkgreen")

    @QtCore.pyqtSlot()
    def on_position_c_released(self):
        self.position.blockSignals(True)
        try:
            self.dev.Position = self.position.value()
            self.position_vc = False
            self.position_c.setDisabled(True)
            self.position_r.setDisabled(True)
            self.position.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set position", e.args[0].desc)
        self.position.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_position_r_released(self):
        self.position.blockSignals(True)
        try:
            self.position.setValue(self.dev.Position)
            self.position_vc = False
            self.position_c.setDisabled(True)
            self.position_r.setDisabled(True)
            self.position.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore position", e.args[0].desc)
        self.position.blockSignals(False)

    ##
    ## Velocity
    ##
    @QtCore.pyqtSlot(float)
    def on_velocity_valueChanged(self, value):
        self.velocity_vc = True
        self.velocity_c.setDisabled(False)
        self.velocity_r.setDisabled(False)
        self.velocity.setStyleSheet("color: darkgreen")

    @QtCore.pyqtSlot()
    def on_velocity_c_released(self):
        self.velocity.blockSignals(True)
        try:
            self.dev.Velocity = self.velocity.value()
            self.velocity_vc = False
            self.velocity_c.setDisabled(True)
            self.velocity_r.setDisabled(True)
            self.velocity.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set velocity", e.args[0].desc)
        self.velocity.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_velocity_r_released(self):
        self.velocity.blockSignals(True)
        try:
            self.velocity.setValue(self.dev.Velocity)
            self.velocity_vc = False
            self.velocity_c.setDisabled(True)
            self.velocity_r.setDisabled(True)
            self.velocity.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore velocity", e.args[0].desc)
        self.velocity.blockSignals(False)

    ##
    ## Acceleration
    ##
    @QtCore.pyqtSlot(float)
    def on_acceleration_valueChanged(self, value):
        self.acceleration_vc = True
        self.acceleration_c.setDisabled(False)
        self.acceleration_r.setDisabled(False)
        self.acceleration.setStyleSheet("color: darkgreen")

    @QtCore.pyqtSlot()
    def on_acceleration_c_released(self):
        self.acceleration.blockSignals(True)
        try:
            self.dev.Acceleration = self.acceleration.value()
            self.acceleration_vc = False
            self.acceleration_c.setDisabled(True)
            self.acceleration_r.setDisabled(True)
            self.acceleration.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set acceleration", e.args[0].desc)
        self.acceleration.blockSignals(False)

    @QtCore.pyqtSlot()
    def on_acceleration_r_released(self):
        self.acceleration.blockSignals(True)
        try:
            self.acceleration.setValue(self.dev.Acceleration)
            self.acceleration_vc = False
            self.acceleration_c.setDisabled(True)
            self.acceleration_r.setDisabled(True)
            self.acceleration.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to restore acceleration", e.args[0].desc)
        self.acceleration.blockSignals(False)


    def move_button(self, delta):
        try:
            self.dev.Position = self.dev.position + delta
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to move device", e.args[0].desc)

    @QtCore.pyqtSlot()
    def on_minus_1_released(self):
        self.move_button(-1)

    @QtCore.pyqtSlot()
    def on_minus_10_released(self):
        self.move_button(-10)

    @QtCore.pyqtSlot()
    def on_minus_100_released(self):
        self.move_button(-100)

    @QtCore.pyqtSlot()
    def on_minus_1000_released(self):
        self.move_button(-1000)

    @QtCore.pyqtSlot()
    def on_plus_1_released(self):
        self.move_button(1)

    @QtCore.pyqtSlot()
    def on_plus_10_released(self):
        self.move_button(10)

    @QtCore.pyqtSlot()
    def on_plus_100_released(self):
        self.move_button(100)

    @QtCore.pyqtSlot()
    def on_plus_1000_released(self):
        self.move_button(1000)

    @QtCore.pyqtSlot()
    def on_pb_stop_released(self):
        """ Stop button
        """
        try:
            self.dev.Stop()
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to stop device", e.args[0].desc)

    @QtCore.pyqtSlot()
    def on_pb_gohome_released(self):
        """ Go home button
        """
        try:
            self.dev.goHome()
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to go home", e.args[0].desc)

    @QtCore.pyqtSlot()
    def on_pb_sethome_released(self):
        """ Set home button
        """
        try:
            self.dev.setHome()
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set home", e.args[0].desc)

    @QtCore.pyqtSlot()
    def on_pb_close_released(self):
        """ Close button
        """
        self.close()

    def debug(self, message):
        if self.debug_enabled:
            print("[D]", message)

    def error(self, message):
        print("[E]", message)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    debug = False
    if len(sys.argv):
        if "--debug" in sys.argv:
            debug = True
    ui = Compressor(debug=debug)
    ui.show()
    ret = app.exec_()
    sys.exit(ret)