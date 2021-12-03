#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 13 13:16:03 2015

@author: Michele Devetta
"""

import sys
import os
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui
import PyTango as PT

# Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '..'))
sys.path.insert(1, os.path.join(sys.path[0], '../Icons'))
from Ui_cooling import Ui_CoolingGUI


class CoolingGUI(QtWidgets.QMainWindow, Ui_CoolingGUI):

    # Tango change event signal
    tango_event = QtCore.pyqtSignal(PT.EventData)

    def __init__(self, parent=None):
        """ Constructor
        """
        # Parent constructors
        QtWidgets.QMainWindow.__init__(self, parent)

        # Get app
        app = QtWidgets.QApplication.instance()

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

        # Open Tango devices for control
        self.valve_xuv = PT.DeviceProxy("udyni/cooling/valve_14")
        self.valve_vmi = PT.DeviceProxy("udyni/cooling/valve_15")
        self.ev_xuv = self.valve_xuv.subscribe_event("State", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.ev_vmi = self.valve_vmi.subscribe_event("State", PT.EventType.CHANGE_EVENT, self.event_callback)

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Setup QAttributes
        self.status_evo1.setTangoAttribute("udyni/cooling/valve_11/State")
        self.status_evo2.setTangoAttribute("udyni/cooling/valve_10/State")
        self.status_cryo.setTangoAttribute("udyni/cooling/valve_12/State")
        self.status_dryvac.setTangoAttribute("udyni/cooling/valve_13/State")
        self.status_tp_xuv.setTangoAttribute("udyni/cooling/valve_14/State")
        self.status_tp_vmi.setTangoAttribute("udyni/cooling/valve_15/State")
        self.chiller_temp.setTangoAttribute("udyni/cooling/chiller/Temperature")
        self.chiller_3way.setTangoAttribute("udyni/cooling/chiller/PercentOutput")
        self.chiller_fan.setTangoAttribute("udyni/cooling/chiller/FanSpeed")
        self.chiller_motor.setTangoAttribute("udyni/cooling/chiller/MotorCurrent")
        self.chiller_state.setTangoAttribute("udyni/cooling/chiller/State")

    def setup_fonts_and_scaling(self):
        # Setup font size and scaling on hidpi
        if self.scaling > 1.1:
            # Scale only if factor is more than 1.1
            self.scale_widget(self, self.scaling)
            members = dir(self)
            for m in members:
                if issubclass(type(getattr(self, m)), QtWidgets.QWidget):
                    self.scale_widget(getattr(self, m), self.scaling)

        sz = self.size()
        self.setFixedSize(sz)

    def event_callback(self, event):
        """ Event callback
        """
        self.tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, event):
        """ Event handler
        """
        if not event.err:
            if event.attr_value.name.lower() == "state":
                st = event.attr_value.value
                if event.device.name() == self.valve_xuv.name():
                    bt = self.bn_water_xuv
                elif event.device.name() == self.valve_vmi.name():
                    bt = self.bn_water_vmi
                else:
                    # Unexpected device
                    bt = None

                if bt is not None:
                    if st == PT.DevState.OPEN:
                        bt.setDisabled(False)
                        bt.setText("Close")
                    elif st == PT.DevState.CLOSE:
                        bt.setDisabled(False)
                        bt.setText("Open")
                    else:
                        bt.setDisabled(True)
                        bt.setText("N.A.")
            else:
                # Unexpected attribute
                pass
        else:
            # Error
            pass

    @QtCore.pyqtSlot()
    def on_bn_water_xuv_released(self):
        self.open_close_valve(self.valve_xuv)

    @QtCore.pyqtSlot()
    def on_bn_water_vmi_released(self):
        self.open_close_valve(self.valve_vmi)

    def open_close_valve(self, device):
        try:
            state = device.State()
            if state == PT.DevState.OPEN:
                device.Close()
            elif state == PT.DevState.CLOSE:
                device.Open()
            else:
                QtWidgets.QMessageBox.critical(self, QtCore.QString("Error!"), QtCore.QString("Cannot operate the valve!"))
        except IndexError as e:
            print("Non-existent valve: {:}".format(e))
        except PT.DevFailed as e:
            print("Tango exception: {:}".format(e))

    @QtCore.pyqtSlot()
    def on_bn_exit_released(self):
        """ Close main windows. """
        self.close()

    @QtCore.pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, event):
        try:
            self.valve_xuv.unsubscribe_event(self.ev_xuv)
            self.valve_vmi.unsubscribe_event(self.ev_vmi)
        except PT.DevFailed:
            pass
        event.accept()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ui = CoolingGUI()
    ui.show()
    ret = app.exec_()
    sys.exit(ret)
