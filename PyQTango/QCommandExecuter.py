# -*- coding: utf-8 -*-
"""
Created on Tue May 12 11:13:29 2020

@author: Michele Devetta <michele.devetta@cnr.it>
"""

import time
import numpy as np
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui

from .PyQTango_rc import qInitResources
qInitResources()

import PyTango as PT



class QCommandExecuter(QtWidgets.QWidget):

    def __init__(self, parent=None):
        # Parent constructor
        QtWidgets.QWidget.__init__(self, parent)

        self.attr = None
        self.evid = None

        # Create layout
        self.selector = QtWidgets.QComboBox(self)
        self.selector.setObjectName("executor_selector")
        self.selector.currentIndexChanged.connect(self.on_index_changed)
        self.arg = QtWidgets.QLineEdit(self)
        self.arg.setObjectName("executor_arg")
        self.arg.setDisabled(True)
        self.execute = QtWidgets.QPushButton(self)
        self.execute.setObjectName("executor_button")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/icons/images/execute.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.execute.setIcon(icon)
        self.execute.setDisabled(True)
        self.execute.released.connect(self.on_released)
        self.desc = QtWidgets.QLabel(self)
        self.desc.setObjectName("executor_desc")
        self.results = QtWidgets.QTextEdit(self)
        self.results.setObjectName("executor_results")

        hlayout = QtWidgets.QHBoxLayout()
        hlayout.addWidget(self.selector)
        hlayout.addWidget(self.arg)
        hlayout.addWidget(self.execute)
        vlayout = QtWidgets.QVBoxLayout()
        vlayout.addLayout(hlayout)
        vlayout.addWidget(self.desc)
        vlayout.addWidget(self.results)
        self.setLayout(vlayout)

        sz = self.execute.size()
        self.execute.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.execute.resize(sz.height(), sz.height())

        self.__dev = None
        self.__cmd_info  = None

    def device(self):
        if self.__dev is not None:
            self.__dev.name()
        else:
            return None

    def __cleanWidget(self):
        self.selector.blockSignals(True)
        while self.selector.count() > 0:
            self.selector.removeItem(0)
        self.selector.blockSignals(False)

    def setDevice(self, device):
        self.__cleanWidget()
        try:
            self.__dev = PT.DeviceProxy(device)
            self.__dev.ping()
        except PT.DevFailed:
            print("Device not available")
            self.execute.setDisabled(True)
            self.arg.setDisabled(True)
            self.__dev = None

        cmd_list = list(self.__dev.get_command_list())
        cmd_list.sort()
        self.selector.addItems(cmd_list)
        self.execute.setDisabled(False)

    @QtCore.pyqtSlot(int)
    def on_index_changed(self, index):
        if self.__dev:
            self.__cmd_info = self.__dev.get_command_config(self.selector.currentText())
            idesc = self.__cmd_info.in_type_desc if self.__cmd_info.in_type_desc != 'Uninitialised' else 'None'
            itype = self.__cmd_info.in_type
            odesc = self.__cmd_info.out_type_desc if self.__cmd_info.out_type_desc != 'Uninitialised' else 'None'
            otype = self.__cmd_info.out_type
            msg = "Input: {0} (type: {1!s})\nOutput: {2} (type: {3!s})".format(idesc, itype, odesc, otype)
            self.desc.setText(msg)
            if itype == PT.CmdArgType.DevVoid:
                self.arg.setDisabled(True)
            else:
                self.arg.setDisabled(False)

    @QtCore.pyqtSlot()
    def on_released(self):
        s = time.time()
        try:
            if self.__cmd_info.in_type != PT.CmdArgType.DevVoid:
                try:
                    val = self.__check_arg(self.arg.text(),self.__cmd_info.in_type)
                except ValueError as e:
                    QtWidgets.QMessageBox.critical(self, "Bad argument", str(e))
                    return
                except NotImplementedError as e:
                    QtWidgets.QMessageBox.critical(self, "Not implemented", str(e))
                    return
                rsp = self.__dev.command_inout(self.selector.currentText(), val)
            else:
                rsp = self.__dev.command_inout(self.selector.currentText())
            t = int((time.time() - s) * 1000.0)

            rsp = "Command: {0}/{1}\nDuration: {2:d} msec\nResult: {3!s}".format(self.__dev.name(), self.selector.currentText(), t, rsp)
        except PT.DevFailed as e:
            rsp = str(e.args[0].desc)
        self.results.setText(rsp)

    def __check_arg(self, arg, data_type):
        if data_type == PT.CmdArgType.DevBoolean:
            val = bool(arg)

        elif data_type == PT.CmdArgType.DevDouble:
            val = float(arg)
            if arg < np.np.finfo(np.float64).min or arg > np.finfo(np.float64).max:
                raise ValueError("Out of range")
            val = np.float64(val)

        elif data_type == PT.CmdArgType.DevFloat:
            val = float(arg)
            if arg < np.finfo(np.float32).min or arg > np.finfo(np.float32).max:
                raise ValueError("Out of range")
            val = np.float32(val)

        elif data_type == PT.CmdArgType.DevShort:
            val = int(arg)
            if arg < np.iinfo(np.int16).min or arg > np.iinfo(np.int16).max:
                raise ValueError("Out of range")
            val = np.int16(val)

        elif data_type == PT.CmdArgType.DevInt or data_type == PT.CmdArgType.DevLong:
            val = int(arg)
            if arg < np.iinfo(np.int32).min or arg > np.iinfo(np.int32).max:
                raise ValueError("Out of range")
            val = np.int32(val)

        elif data_type == PT.CmdArgType.DevLong64:
            val = int(arg)
            if arg < np.iinfo(np.int64).min or arg > np.iinfo(np.int64).max:
                raise ValueError("Out of range")
            val = np.int64(val)

        elif data_type == PT.CmdArgType.DevUChar:
            val = int(arg)
            if arg < np.iinfo(np.uint8).min or arg > np.iinfo(np.uint8).max:
                raise ValueError("Out of range")
            val = np.uint8(val)

        elif data_type == PT.CmdArgType.DevUShort:
            val = int(arg)
            if arg < np.iinfo(np.uint16).min or arg > np.iinfo(np.uint16).max:
                raise ValueError("Out of range")
            val = np.uint16(val)

        elif data_type == PT.CmdArgType.DevULong:
            val = int(arg)
            if arg < np.iinfo(np.uint32).min or arg > np.iinfo(np.uint32).max:
                raise ValueError("Out of range")
            val = np.uint32(val)

        elif data_type == PT.CmdArgType.DevULong64:
            val = int(arg)
            if arg < np.iinfo(np.uint64).min or arg > np.iinfo(np.uint64).max:
                raise ValueError("Out of range")
            val = np.uint64(val)

        elif data_type == PT.CmdArgType.DevState:
            raise NotImplementedError("DevState argument not supported")

        elif data_type == PT.CmdArgType.DevString:
            val = str(arg)

        elif data_type == PT.CmdArgType.DevPipeBlob:
            raise NotImplementedError("DevPipeBlob argument not supported")

        elif data_type == PT.CmdArgType.DevEncoded:
            raise NotImplementedError("DevEncoded argument not supported")

        elif data_type == PT.CmdArgType.DevEnum:
            raise NotImplementedError("DevEnum argument not supported")

        elif data_type == PT.CmdArgType.DevVarBooleanArray:
            lst = self.__check_array(arg)
            val = []
            for v in lst:
                val.append(bool(v))

        elif data_type == PT.CmdArgType.DevVarCharArray:
            pass

        elif data_type == PT.CmdArgType.DevVarDoubleArray:
            lst = self.__check_array(arg)
            val = []
            for v in lst:
                val.append(bool(v))

        elif data_type == PT.CmdArgType.DevVarDoubleStringArray:
            raise NotImplementedError("DevVarDoubleStringArray argument not supported")

        elif data_type == PT.CmdArgType.DevVarFloatArray:
            pass

        elif data_type == PT.CmdArgType.DevVarLong64Array:
            pass

        elif data_type == PT.CmdArgType.DevVarLongArray:
            pass

        elif data_type == PT.CmdArgType.DevVarLongStringArray:
            raise NotImplementedError("DevVarLongStringArray argument not supported")

        elif data_type == PT.CmdArgType.DevVarShortArray:
            pass

        elif data_type == PT.CmdArgType.DevVarStateArray:
            pass

        elif data_type == PT.CmdArgType.DevVarStringArray:
            pass

        elif data_type == PT.CmdArgType.DevVarULong64Array:
            pass

        elif data_type == PT.CmdArgType.DevVarULongArray:
            pass

        elif data_type == PT.CmdArgType.DevVarUShortArray:
            pass

        elif data_type == PT.CmdArgType.DevVoid:
            val = None

        return val

    def __check_array(self, arg):
        if arg[0] != '[':
            arg = '[' + arg
        if arg[-1] != ']':
            arg = arg + ']'
        return eval(arg)