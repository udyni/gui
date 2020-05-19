# -*- coding: utf-8 -*-
"""
Created on Tue May 12 11:13:29 2020

@author: Michele Devetta <michele.devetta@cnr.it>
"""

import re
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui

from .PyQTango_rc import qInitResources
qInitResources()

import PyTango as PT


class QAttribute(QtWidgets.QWidget):

    # Internal Tango change event signal
    __tango_event = QtCore.pyqtSignal(PT.EventData)

    # Dev-state style
    __devstate_style_common = "border-radius:3px;border: 1px solid black;"
    __devstate_style = {PT.DevState.ALARM: "background-color: rgb(255, 140, 0);color: rgb(0, 0, 0);",        # Black on orange
                        PT.DevState.CLOSE: "background-color: rgb(255, 255, 255);color: rgb(0, 0, 0);",      # Black on white
                        PT.DevState.DISABLE: "background-color: rgb(255, 0, 255);color: rgb(0, 0, 0);",      # Black on magenta
                        PT.DevState.EXTRACT: "background-color: rgb(0, 255, 0);color: rgb(0, 0, 0);",        # Black on green
                        PT.DevState.FAULT: "background-color: rgb(255, 0, 0);color: rgb(0, 0, 0);",          # White on red
                        PT.DevState.INIT: "background-color: rgb(204, 204, 122);color: rgb(0, 0, 0);",       # Black on beige
                        PT.DevState.INSERT: "background-color: rgb(255, 255, 255);color: rgb(0, 0, 0);",     # Black on white
                        PT.DevState.MOVING: "background-color: rgb(128, 160, 255);color: rgb(0, 0, 0);",     # While on light blue
                        PT.DevState.OFF: "background-color: rgb(255, 255, 255);color: rgb(0, 0, 0);",        # Black on white
                        PT.DevState.ON: "background-color: rgb(0, 255, 0);color: rgb(0, 0, 0);",             # Black on green
                        PT.DevState.OPEN: "background-color: rgb(0, 255, 0);color: rgb(0, 0, 0);",           # Black on green
                        PT.DevState.RUNNING: "background-color: rgb(0, 125, 0);color: rgb(255, 255, 255);",  # White on dark green
                        PT.DevState.STANDBY: "background-color: rgb(255, 255, 0);color: rgb(0, 0, 0);",      # Black on yellow
                        PT.DevState.UNKNOWN: "background-color: rgb(155, 155, 155);color: rgb(0, 0, 0);"}    # Black on grey


    def __init__(self, parent=None):
        # Parent constructor
        QtWidgets.QWidget.__init__(self, parent)

        self.attr = None
        self.evid = None

        # Connect event to slot
        self.__tango_event.connect(self.event_handler)

        # Create layout
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.w_value = None
        self.w_value_c = False
        self.c_button = None
        self.r_button = None
        self.__unit = None
        self.__enum_labels = None
        self.__cfg = None

    def __del__(self):
        # Destructor to unsubcribe from Tango events
        if self.attr is not None:
            self.__unsubscribe()

    def shutdown(self):
        if self.attr is not None and self.evid is not None:
            self.attr.unsubscribe_event(self.evid)

    def __unsubscribe(self):
        try:
            if self.evid is not None:
                self.attr.unsubscribe_event(self.evid)
            self.evid = None
        except Exception as e:
            print("Error unsubscribing!", e)

    def label(self):
        if self.__cfg is not None:
            return self.__cfg.label
        else:
            return ""

    def tangoAttribute(self):
        if self.attr is not None:
            return self.attr.name()
        else:
            return None

    def setTangoAttribute(self, attr_name):
        if self.attr is not None:
            self.__unsubscribe()
            self.attr = None

        if attr_name == "":
            # Clearing widget
            self.__cleanWidget()
        else:
            print("[D] Setting up attribute", attr_name)
            try:
                self.attr = PT.AttributeProxy(attr_name)
                self.attr.ping()
                self.setupWidget()
                self.evid = self.attr.subscribe_event(PT.EventType.CHANGE_EVENT, self.event_callback)
            except PT.DevFailed as e:
                # TODO error
                print("[E] Failed to setup attribute '{0}'. Error: {1!s}".format(attr_name, e.args[0].desc))

    def __cleanWidget(self):
        # Clean layout
        if self.w_value is not None:
            if isinstance(self.w_value, QtWidgets.QLineEdit):
                self.w_value.textChanged.disconnect()
            elif isinstance(self.w_value, QtWidgets.QCheckBox):
                self.w_value.stateChanged.disconnect()
            elif isinstance(self.w_value, QtWidgets.QSpinBox) or isinstance(self.w_value, QtWidgets.QDoubleSpinBox):
                self.w_value.valueChanged.disconnect()
            elif isinstance(self.w_value, QtWidgets.QComboBox):
                self.w_value.currentIndexChanged.disconnect()
            self.layout.removeWidget(self.w_value)
            self.w_value = None
            self.w_value_c = False
        if self.c_button is not None:
            self.c_button.released.disconnect()
            self.layout.removeWidget(self.c_button)
            self.c_button = None
        if self.r_button is not None:
            self.r_button.released.disconnect()
            self.layout.removeWidget(self.r_button)
            self.r_button = None
        self.__unit = None
        self.__enum_labels = None

    def setupWidget(self):
        # Clear widget
        self.__cleanWidget()

        # Read attribute config
        self.__cfg = self.attr.get_config()

        if self.__cfg.data_type == PT.CmdArgType.DevPipeBlob or self.__cfg.data_type == PT.CmdArgType.DevEncoded:
            # Unsupported data type
            raise NotImplementedError("Attribute data type not supported")

        if self.__cfg.data_format == PT.AttrDataFormat.SCALAR:

            if self.__cfg.writable == PT.AttrWriteType.READ:
                # Read only. We just add a read-only QLineEdit, QCheckbox or QLabel
                if self.__isNumeric(self.__cfg.data_type) or self.__cfg.data_type == PT.CmdArgType.DevString:
                    # QLineEdit
                    self.w_value = QtWidgets.QLineEdit(self)
                    self.w_value.setReadOnly(True)
                    self.w_value.setObjectName(self.__cfg.name)

                elif self.__cfg.data_type == PT.CmdArgType.DevBoolean:
                    # Put checkbox
                    self.w_value = QtWidgets.QCheckBox(self)
                    self.w_value.setText("")
                    self.w_value.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
                    self.w_value.setFocusPolicy(QtCore.Qt.NoFocus);

                elif self.__cfg.data_type == PT.CmdArgType.DevState:
                    # QLabelsizeHint
                    self.w_value = QtWidgets.QLabel(self)
                    self.w_value.setText(str(PT.DevState.UNKNOWN))
                    self.w_value.setStyleSheet(self.__devstate_style_common+self.__devstate_style[PT.DevState.UNKNOWN])
                    self.w_value.setObjectName(self.__cfg.name)

                elif self.__cfg.data_type == PT.CmdArgType.DevEnum:
                    # QLineEdit
                    self.__enum_labels = self.__cfg.enum_labels
                    self.w_value = QtWidgets.QLineEdit(self)
                    self.w_value.setReadOnly(True)
                    self.w_value.setObjectName(self.__cfg.name)

                else:
                    raise NotImplementedError("Unexpected data type '{0!s}'".format(self.__cfg.data_type))

                # Common widget config
                self.w_value.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                self.w_value.setObjectName(self.__cfg.name)

            elif self.__cfg.writable == PT.AttrWriteType.READ_WRITE:
                # Read-write. If a numeric type and min and max are specified we
                # can use a QSpinbox. Otherwise a QLineEdit of a checkbox for bool
                # For QSpinBox and QLineEdit we also add confirm and reject pushbuttons
                minimum = self.__check_value(self.__cfg.min_value, self.__cfg.data_type)
                maximum = self.__check_value(self.__cfg.max_value, self.__cfg.data_type)

                if self.__isNumeric(self.__cfg.data_type):
                    if minimum is not None and maximum is not None:
                        # QSpinbox
                        if self.__cfg.data_type == PT.CmdArgType.DevDouble or self.__cfg.data_type == PT.CmdArgType.DevFloat:
                            self.w_value = QtWidgets.QDoubleSpinBox(self)
                            step = 0.1
                            if self.__cfg.format != "":
                                m = re.match("%(\d*)\.(\d+)[ef]+", self.__cfg.format)
                                if m is not None:
                                    try:
                                        n = int(m.groups()[1])
                                        while n > 1:
                                            step /= 10.0
                                            n -= 1
                                    except ValueError:
                                        pass
                            self.w_value.setSingleStep(step)
                        else:
                            self.w_value = QtWidgets.QSpinBox(self)
                            self.w_value.setSingleStep(1)
                        self.w_value.setRange(minimum, maximum)
                        if self.__cfg.unit != "":
                            self.w_value.setSuffix(self.__cfg.unit)
                    else:
                        # QLineEdit
                        self.w_value = QtWidgets.QLineEdit(self)
                        self.__unit = self.__cfg.unit
                    self.c_button = self.__create_pushbutton(self.__cfg.name, self, 'c', self.size().height())
                    self.r_button = self.__create_pushbutton(self.__cfg.name, self, 'r', self.size().height())

                elif self.__cfg.data_type == PT.CmdArgType.DevBoolean:
                    # Put checkbox
                    self.w_value = QtWidgets.QCheckBox(self)
                    self.w_value.setText("")

                elif self.__cfg.data_type == PT.CmdArgType.DevState:
                    # Doesn't make much sense...
                    raise NotImplementedError("Writable DevState is not supported")

                elif self.__cfg.data_type == PT.CmdArgType.DevEnum:
                    # QComboBox
                    self.w_value = QtWidgets.QComboBox(self)
                    self.w_value.addItems(self.__cfg.enum_labels)
                    self.c_button = self.__create_pushbutton(self.__cfg.name, self, 'c', self.size().height())
                    self.r_button = self.__create_pushbutton(self.__cfg.name, self, 'r', self.size().height())

                elif self.__cfg.data_type == PT.CmdArgType.DevString:
                    # QLineEdit
                    self.w_value = QtWidgets.QLineEdit(self)
                    self.c_button = self.__create_pushbutton(self.__cfg.name, self, 'c', self.size().height())
                    self.r_button = self.__create_pushbutton(self.__cfg.name, self, 'r', self.size().height())

                else:
                    raise NotImplementedError("Unexpected data type '{0!s}'".format(self.__cfg.data_type))

                # Common widget config
                self.w_value.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                self.w_value.setObjectName(self.__cfg.name)

                # Connect signals
                if isinstance(self.w_value, QtWidgets.QLineEdit):
                    self.w_value.textChanged.connect(self.on_textChanged)
                elif isinstance(self.w_value, QtWidgets.QCheckBox):
                    self.w_value.stateChanged.connect(self.on_stateChanged)
                elif isinstance(self.w_value, QtWidgets.QSpinBox):
                    self.w_value.valueChanged.connect(self.on_valueChanged_int)
                elif isinstance(self.w_value, QtWidgets.QDoubleSpinBox):
                    self.w_value.valueChanged.connect(self.on_valueChanged_float)
                elif isinstance(self.w_value, QtWidgets.QComboBox):
                    self.w_value.currentIndexChanged.connect(self.on_currentIndexChanged)

            elif self.__cfg.writable == PT.AttrWriteType.READ_WITH_WRITE:
                raise NotImplementedError("READ_WITH_WRITE attributes are not yet implemented")

            elif self.__cfg.writable == PT.AttrWriteType.WRITE:
                raise NotImplementedError("Only WRITE attributes are not yet implemented")

        elif self.__cfg.data_format == PT.AttrDataFormat.SPECTRUM:
            raise NotImplementedError("Spectrum attributes are not yet implemented")

        elif self.__cfg.data_format == PT.AttrDataFormat.IMAGE:
            raise NotImplementedError("Image attributes are not yet implemented")

        # Add widgets to layout
        self.layout.addWidget(self.w_value)
        if self.c_button is not None:
            self.c_button.released.connect(self.on_pb_c_released)
            self.layout.addWidget(self.c_button)
        if self.r_button is not None:
            self.r_button.released.connect(self.on_pb_r_released)
            self.layout.addWidget(self.r_button)

    def event_callback(self, event):
        # Tango event callback
        self.__tango_event.emit(event)

    @QtCore.pyqtSlot(PT.EventData)
    def event_handler(self, ev):
        # Event handler slot
        if ev.err:
            print("[E] {0!s}".format(ev.errors[0].desc))
            return

        if ev.attr_value.name.lower() != self.attr.name().lower():
            print("[E] Attribute name does not match! ({0} != {1})".format(ev.attr_value.name, self.attr.name()))
            return

        print("[D] Got event")

        # Get attribute value
        attr_value = ev.attr_value.value

        if self.__cfg.data_format == PT.AttrDataFormat.SCALAR:

            if self.__cfg.writable == PT.AttrWriteType.READ_WRITE and self.w_value_c:
                # Value has changed. We set text red
                self.w_value.setStyleSheet("color: red;")
                return

            # We have to update the value
            if isinstance(self.w_value, QtWidgets.QLineEdit):
                self.w_value.blockSignals(True)
                if self.__isNumeric(self.__cfg.data_type):
                    self.w_value.setText(self.__format_value(self.__cfg.format, attr_value))

                elif self.__cfg.data_type == PT.CmdArgType.DevEnum:
                    self.w_value.setText(str(self.__enum_labels[attr_value]))
                else:
                    self.w_value.setText(str(attr_value))
                self.w_value.blockSignals(False)

            elif isinstance(self.w_value, QtWidgets.QSpinBox) or isinstance(self.w_value, QtWidgets.QDoubleSpinBox):
                self.w_value.blockSignals(True)
                self.w_value.setValue(attr_value)
                self.w_value.blockSignals(False)

            elif isinstance(self.w_value, QtWidgets.QCheckBox):
                # Put checkbox
                if attr_value:
                    self.w_value.setCheckState(QtCore.Qt.Checked)
                else:
                    self.w_value.setCheckState(QtCore.Qt.Unchecked)

            elif isinstance(self.w_value, QtWidgets.QComboBox):
                self.w_value.blockSignals(True)
                self.w_value.setCurrentIndex(attr_value)
                self.w_value.blockSignals(False)

            elif isinstance(self.w_value, QtWidgets.QLabel):
                if self.__cfg.data_type == PT.CmdArgType.DevState:
                    self.w_value.setText(str(attr_value))
                    self.w_value.setStyleSheet(self.__devstate_style_common+self.__devstate_style[attr_value])

        elif self.__cfg.data_format == PT.AttrDataFormat.SPECTRUM:
            print("[E] Events for spectrum attributes are not supported")
            return

        elif self.__cfg.data_format == PT.AttrDataFormat.IMAGE:
            print("[E] Events for image attributes are not supported")
            return

    def __format_value(self, cfg_fmt, value):
        fmt = "{0"
        if cfg_fmt != "":
            m = re.match("%(\d*)\.?(\d*)([diufegx]+)", cfg_fmt)
            if m is not None:
                w = m.groups()[0]
                p = m.groups()[1]
                t = m.groups()[2]

                if t in ('d', 'i', 'u'):
                    fmt += ":d"
                elif t in ['f', 'e', 'g']:
                    fmt += ':'
                    if w != "":
                        fmt += "{0:d}".format(int(w))
                    if p != "":
                        fmt += ".{0:d}".format(int(p))
                    fmt += m.groups()[2]
                elif t == 'x':
                    fmt = "0x" + fmt +'x'
                else:
                    fmt += "!s"
            else:
                fmt += "!s"
        else:
            fmt += "!s"
        fmt += '}'
        return fmt.format(value)

    def __isNumeric(self, data_type):
        __numeric_types = (PT.CmdArgType.DevInt,
                           PT.CmdArgType.DevLong,
                           PT.CmdArgType.DevLong64,
                           PT.CmdArgType.DevShort,
                           PT.CmdArgType.DevUChar,
                           PT.CmdArgType.DevULong,
                           PT.CmdArgType.DevULong64,
                           PT.CmdArgType.DevUShort,
                           PT.CmdArgType.DevDouble,
                           PT.CmdArgType.DevFloat)
        return data_type in __numeric_types

    def __check_value(self, value, data_type):
        if data_type == PT.CmdArgType.DevBoolean:
            return bool(value)
        elif data_type == PT.CmdArgType.DevDouble or data_type == PT.CmdArgType.DevFloat:
            try:
                return float(value)
            except ValueError:
                return None
        elif data_type == PT.CmdArgType.DevEnum:
            try:
                return int(value)
            except ValueError:
                return None
        elif data_type in (PT.CmdArgType.DevInt,
                           PT.CmdArgType.DevLong,
                           PT.CmdArgType.DevLong64,
                           PT.CmdArgType.DevShort,
                           PT.CmdArgType.DevUChar,
                           PT.CmdArgType.DevULong,
                           PT.CmdArgType.DevULong64,
                           PT.CmdArgType.DevUShort):
            try:
                return int(value)
            except ValueError:
                return None
        elif data_type == PT.CmdArgType.DevState:
            if type(value) == PT.DevState:
                return value
            else:
                return None
        elif data_type == PT.CmdArgType.DevString:
            return str(value)
        else:
            return None

    def __create_pushbutton(self, name, parent, action, sz):
        pb = QtWidgets.QPushButton(parent)
        pb.setEnabled(False)
        pb.setGeometry(QtCore.QRect(0, 0, sz, sz))
        pb.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        pb.setText("")
        icon = QtGui.QIcon()
        if action == 'c':
            icon.addPixmap(QtGui.QPixmap(":/icons/images/confirm.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        else:
            icon.addPixmap(QtGui.QPixmap(":/icons/images/reject.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        pb.setIcon(icon)
        pb.setObjectName(name + "_" + action)
        return pb

    @QtCore.pyqtSlot()
    def on_pb_c_released(self):
        # Confirm
        try:
            if isinstance(self.w_value, QtWidgets.QLineEdit):
                val = self.__check_value(self.w_value.text(), self.__cfg.data_type)
                if val is None:
                    raise ValueError("Bad value")
                else:
                    self.attr.write(val)
            elif isinstance(self.w_value, QtWidgets.QSpinBox) or isinstance(self.w_value, QtWidgets.QDoubleSpinBox):
                self.attr.write(self.w_value.value())
            elif isinstance(self.w_value, QtWidgets.QComboBox):
                self.attr.write(self.w_value.currentIndex())
            self.w_value_c = False
            self.c_button.setDisabled(True)
            self.r_button.setDisabled(True)
            self.w_value.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set attribute", e.args[0].desc)
        except ValueError:
            QtWidgets.QMessageBox.critical(self, "Value error", "Failed to convert value")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Exception", str(e))

    @QtCore.pyqtSlot()
    def on_pb_r_released(self):
        # Reject
        self.w_value.blockSignals(True)
        try:
            value = self.attr.read().value
            if isinstance(self.w_value, QtWidgets.QLineEdit):
                if self.__isNumeric(self.__cfg.data_type):
                    self.w_value.setText(self.__format_value(self.__cfg.format, value))
                else:
                    self.w_value.setText(str(value))
            elif isinstance(self.w_value, QtWidgets.QSpinBox) or isinstance(self.w_value, QtWidgets.QDoubleSpinBox):
                self.w_value.setValue(value)
            elif isinstance(self.w_value, QtWidgets.QComboBox):
                self.w_value.setCurrentIndex(value)
            self.w_value_c = False
            self.c_button.setDisabled(True)
            self.r_button.setDisabled(True)
            self.w_value.setStyleSheet("")
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to set attribute", e.args[0].desc)
        except ValueError:
            QtWidgets.QMessageBox.critical(self, "Value error", "Failed to convert value")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Exception", str(e))
        self.w_value.blockSignals(False)

    @QtCore.pyqtSlot(str)
    def on_textChanged(self, text):
        self.w_value_c = True
        self.c_button.setDisabled(False)
        self.r_button.setDisabled(False)
        self.w_value.setStyleSheet("color: darkgreen;")

    @QtCore.pyqtSlot(int)
    def on_stateChanged(self, state):
        if state == QtCore.Qt.Checked:
            self.attr.write(True)
        else:
            self.attr.write(False)

    @QtCore.pyqtSlot(int)
    def on_valueChanged_int(self, value):
        self.w_value_c = True
        self.c_button.setDisabled(False)
        self.r_button.setDisabled(False)
        self.w_value.setStyleSheet("color: darkgreen;")

    @QtCore.pyqtSlot(float)
    def on_valueChanged_float(self, value):
        self.w_value_c = True
        self.c_button.setDisabled(False)
        self.r_button.setDisabled(False)
        self.w_value.setStyleSheet("color: darkgreen;")

    @QtCore.pyqtSlot(int)
    def on_currentIndexChanged(self, index):
        self.w_value_c = True
        self.c_button.setDisabled(False)
        self.r_button.setDisabled(False)
        self.w_value.setStyleSheet("color: darkgreen;")
