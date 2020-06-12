#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 10 22:21:29 2020

@author: Michele Devetta <michele.devetta@cnr.it>
"""

import sys
import os
## Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '..'))
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

        # Setup device
        self.temp_dev = None
        self.temp_attr = ['RP_SxDown', 'RP_DxDown', 'RP_SxUp', 'RP_AMB', 'RP_DxUp', 'RG_Dx', 'RG_Sx', 'RG_AMB']
        self.temp_widgets = [self.sm_ld, self.sm_rd, self.sm_lu, self.sm_amb, self.sm_ru, self.lg_r, self.lg_l, self.lg_amb]
        self.temp_values = {}
        try:
            self.dev = PT.DeviceProxy("udyni/laser/compressor")
            self.dev.ping()
        except PT.DevFailed:
            QtWidgets.QMessageBox.critical(self, "Device not found", "Cannot connect to the compressor control device")
            app.quit()

        # Configure attributes
        self.position.setTangoAttribute(self.dev.name() + "/Position")
        self.velocity.setTangoAttribute(self.dev.name() + "/Velocity")
        self.acceleration.setTangoAttribute(self.dev.name() + "/Acceleration")

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Subscribe events
        try:
            self.ev_id = []
            for a in ['Temperature', 'Voltage', 'State']:
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

            elif attr_name == "temperature":
                self.temperature.setText("{0:.1f} °C".format(attr_value))

            elif attr_name == "voltage":
                self.voltage.setText("{0:.1f} V".format(attr_value))

            else:
                for a in self.temp_attr:
                    if attr_name == a.lower():
                        # Found
                        t = attr_value - 273.15
                        if a not in self.temp_values:
                            self.temp_values[a] = t
                        else:
                            self.temp_values[a] = 0.9 * self.temp_values[a] + 0.1 * t
                        self.temp_widgets[self.temp_attr.index(a)].setText("{0:.1f} °C".format(self.temp_values[a]))
                        break
                else:
                    self.debug("Unexpected attribute '{0}'".format(attr_name))

    @QtCore.pyqtSlot(int)
    def on_tabs_currentChanged(self, index):
        if index == 0:
            # Move grating tab (unsubscribe from temperatures)
            if self.temp_dev is not None:
                for ev in self.temp_evid:
                    self.temp_dev.unsubscribe_event(ev)
                self.temp_evid = []
                self.temp_dev = None

        elif index == 1:
            # Temperature tab
            try:
                self.temp_dev = PT.DeviceProxy("udyni/monitoring/pitemp1")
                self.temp_dev.ping()
                self.temp_evid = []
                for a in self.temp_attr:
                    self.temp_evid.append(self.temp_dev.subscribe_event(a, PT.EventType.CHANGE_EVENT, self.event_callback))
            except PT.DevFailed as e:
                QtWidgets.QMessageBox.critical(self, "Failed to connect to temperature monitor", e.args[0].desc)
                self.sm_lu.setText("N.A.")
                self.sm_ld.setText("N.A.")
                self.sm_ru.setText("N.A.")
                self.sm_rd.setText("N.A.")
                self.sm_amb.setText("N.A.")
                self.lg_l.setText("N.A.")
                self.lg_r.setText("N.A.")
                self.lg_amb.setText("N.A.")
                self.temp_dev = None
                self.temp_evid = []
                self.temp_values = {}
        else:
            self.error("Unexpected index: {0:d}".format(index))

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