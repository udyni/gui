# -*- coding: utf-8 -*-
"""
Cryostar control GUI

Created on Wed Nov 29 11:40:23 2017

@author: Michele Devetta <michele.devetta@mail.polimi.it>
"""

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from Ui_cryostar import Ui_Cryostar

import PyTango as PT


class CryostarGUI(QtWidgets.QMainWindow, Ui_Cryostar):

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
        self.dev = PT.DeviceProxy("udyni/laser/cryo")

        # Get enum labels
        self.pump_status_labels = self.dev.get_attribute_config("pump_status").enum_labels
        self.vacuum_status_labels = self.dev.get_attribute_config("vacuum_status").enum_labels
        self.compressor_status_labels = self.dev.get_attribute_config("compressor_status").enum_labels
        self.temperature_status_labels = self.dev.get_attribute_config("temperature_status").enum_labels

        # Open water valve device
        db = PT.Database()
        prp = db.get_device_property("udyni/laser/cryo", "water_valve")
        self.water = PT.DeviceProxy(prp['water_valve'][0])

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Subscribe all the relevant events
        self.dev.subscribe_event("pressure", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("temperature", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("delta", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("pump_status", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("vacuum_status", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("compressor_status", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.dev.subscribe_event("temperature_status", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.water.subscribe_event("State", PT.EventType.CHANGE_EVENT, self.event_callback)
        self.water.subscribe_event("WaterFlow", PT.EventType.CHANGE_EVENT, self.event_callback)

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
        self.tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, event):
        """ Event handler
        """
        if not event.err:
            if event.device.name() == self.dev.name():
                # Event from Cryo controller
                if event.attr_value.name.lower() == "pressure":
                    self.pressure.setText("{:6.2e}".format(event.attr_value.value))

                elif event.attr_value.name.lower() == "temperature":
                    self.temperature.setText("{:d}".format(event.attr_value.value))

                elif event.attr_value.name.lower() == "delta":
                    self.delta.setText("{:d}".format(event.attr_value.value))

                elif event.attr_value.name.lower() == "pump_status":
                    self.pump_status.setText(self.pump_status_labels[event.attr_value.value])

                elif event.attr_value.name.lower() == "vacuum_status":
                    self.vacuum_status.setText(self.vacuum_status_labels[event.attr_value.value])

                elif event.attr_value.name.lower() == "compressor_status":
                    self.compressor_status.setText(self.compressor_status_labels[event.attr_value.value])
                    if event.attr_value.value == 2:
                        self.pb_start.setDisabled(True)
                        self.pb_stop.setDisabled(False)
                    else:
                        self.pb_start.setDisabled(False)
                        self.pb_stop.setDisabled(True)

                elif event.attr_value.name.lower() == "temperature_status":
                    self.temperature_status.setText(self.temperature_status_labels[event.attr_value.value])

                else:
                    print("Event from unexpected attribute '{:}'".format(event.attr_name))

            elif event.device.name() == self.water.name():
                # Event from water valve
                if event.attr_value.name.lower() == "state":
                    if event.attr_value.value == PT.DevState.OPEN:
                        self.water_status.setText("OPEN")
                        self.water_status.setStyleSheet("border-radius:4px;border:1px solid darkgray;background-color:darkgreen;color:white")
                    elif event.attr_value.value == PT.DevState.CLOSE:
                        self.water_status.setText("CLOSE")
                        self.water_status.setStyleSheet("border-radius:4px;border:1px solid darkgray;background-color:gray;color:black")
                    else:
                        self.water_status.setText("FAULT")
                        self.water_status.setStyleSheet("border-radius:4px;border:1px solid darkgray;background-color:red;color:white")
                elif event.attr_value.name.lower() == "waterflow":
                    self.water_flow.setText("{:4.2f}".format(event.attr_value.value))
                else:
                    print("Event from unexpected attribute '{:}'".format(event.attr_name))

            else:
                # Event from unexpected device
                print("Event from unexpected device '{:}'".format(event.device.name()))

        else:
            # Event error
            if event.errors[0].reason == "API_EventTimeout":
                # A device failed
                print("Device {:} is offline".format(event.device.name()))

            else:
                # Other event error
                print("Event error: {:} (Origin: {:})".format(event.errors[0].desc, event.errors[0].origin))

    @QtCore.pyqtSlot()
    def on_pb_start_released(self):
        """ Start cryo """
        self.dev.startCompressor()

    @QtCore.pyqtSlot()
    def on_pb_stop_released(self):
        """ Start cryo """
        self.dev.stopCompressor()

    @QtCore.pyqtSlot()
    def on_pb_close_released(self):
        """ Close main windows. """
        self.close()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ui = CryostarGUI()
    ui.show()
    ret = app.exec_()
    sys.exit(ret)
