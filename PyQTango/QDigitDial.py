# -*- coding: utf-8 -*-
"""
Created on Tue May 12 11:13:29 2020

@author: Michele Devetta <michele.devetta@cnr.it>
"""

import math
import re
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui

from .PyQTango_rc import qInitResources
qInitResources()


class QDoubleClickLabel(QtWidgets.QLabel):
    doubleClickSignal = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    @QtCore.pyqtSlot(QtGui.QMouseEvent)
    def mouseDoubleClickEvent(self, event):
        evps = event.pos()
        sz = self.size()
        if evps.x() > 0 and evps.x() < sz.width() and evps.y() > 0 and evps.y() < sz.height():
            self.doubleClickSignal.emit()


class QArrowButton(QtWidgets.QLabel):

    # Direction flag
    UP = 0
    DOWN = 1

    # OnClick signal
    clickSignal = QtCore.pyqtSignal(int)

    def __init__(self, direction, parent=None):
        QtWidgets.QLabel.__init__(self, parent)

        # Setup icons
        self.direction = direction
        if self.direction == self.UP:
            self.off_pic = QtGui.QPixmap(":/icons/images/arrow_up.png")
            self.on_pic = QtGui.QPixmap(":/icons/images/arrow_up_on.png")
            self.press_pic = QtGui.QPixmap(":/icons/images/arrow_up_press.png")
        else:
            self.off_pic = QtGui.QPixmap(":/icons/images/arrow_down.png")
            self.on_pic = QtGui.QPixmap(":/icons/images/arrow_down_on.png")
            self.press_pic = QtGui.QPixmap(":/icons/images/arrow_down_press.png")

        # Set widget default size
        self.resize(78, 78)

        # Enable mouse tracking
        self.setMouseTracking(True)

        # Enable pixmap scaling
        self.setScaledContents(True)

        # Set default icon
        self.setPixmap(self.off_pic)

    def __check_t(self, x, y):
        if self.direction == self.UP:
            if y < 57 * float(self.height()) / 78 and y > self.m1 * x + self.c1 and y > self.m2 * x + self.c2:
                return True
            else:
                return False
        else:
            if y > 24 * float(self.height()) / 78 and y < self.m1 * x + self.c1 and y < self.m2 * x + self.c2:
                return True
            else:
                return False

    @QtCore.pyqtSlot(QtGui.QMouseEvent)
    def mousePressEvent(self, event):
        ps = event.pos()
        if self.__check_t(ps.x(), ps.y()):
            self.setPixmap(self.press_pic)
        else:
            self.setPixmap(self.off_pic)

    @QtCore.pyqtSlot(QtGui.QMouseEvent)
    def mouseReleaseEvent(self, event):
        ps = event.pos()
        if self.__check_t(ps.x(), ps.y()):
            self.setPixmap(self.on_pic)
            # Emit clicked signal
            self.clickSignal.emit(self.direction)

    @QtCore.pyqtSlot(QtGui.QMouseEvent)
    def mouseMoveEvent(self, event):
        ps = event.pos()
        if self.__check_t(ps.x(), ps.y()):
            self.setPixmap(self.on_pic)
        else:
            self.setPixmap(self.off_pic)

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, event):
        if event.size().isValid():
            w = event.size().width()
            h = event.size().height()
            # Update lines
            if self.direction == self.UP:
                self.m1 = float(54 - 19) / float(12 - 39) * float(h) / float(w)
                self.m2 = float(54 - 19) / float(67 - 39) * float(h) / float(w)
                self.c1 = 54 * float(h) / 78 - self.m1 * 12 * float(w) / 78
                self.c2 = 54 * float(h) / 78 - self.m2 * 67 * float(w) / 78
            else:
                self.m1 = float(24 - 58) / float(12 - 39) * float(h) / float(w)
                self.m2 = float(24 - 58) / float(67 - 39) * float(h) / float(w)
                self.c1 = 24 * float(h) / 78 - self.m1 * 12 * float(w) / 78
                self.c2 = 24 * float(h) / 78 - self.m2 * 67 * float(w) / 78

        else:
            QtWidgets.QLabel.resizeEvent(self, event)


class QSingleDigitDial(QtWidgets.QWidget):

    valueChangeSignal = QtCore.pyqtSignal(float)
    doubleClickSignal = QtCore.pyqtSignal()

    def __init__(self, step, parent=None):
        # Parent constructor
        QtWidgets.QWidget.__init__(self, parent)

        # Store step
        self._step = float(step)

        # Setup widgets
        self.resize(78, 216)
        self._up = QArrowButton(QArrowButton.UP, self)
        self._up.move(0, 0)
        self._up.clickSignal.connect(self.onClickEvent)
        self._value = QDoubleClickLabel(self)
        self._value.resize(78, 55)
        self._value.move(0, 98)
        self._value.setText("0")
        self._value.setAlignment(QtCore.Qt.AlignCenter)
        self._value.setStyleSheet("text-align: center; font-size: 45px; font-weight:bold; color: black; ")
        self._value.doubleClickSignal.connect(self.onDoubleClickEvent)
        self._write_value = QDoubleClickLabel(self)
        self._write_value.resize(78, 40)
        self._write_value.move(0, 68)
        self._write_value.setText("0")
        self._write_value.setAlignment(QtCore.Qt.AlignCenter)
        self._write_value.setStyleSheet("text-align: center; font-size: 30px; font-weight:bold; color: darkred; ")
        self._write_value.doubleClickSignal.connect(self.onDoubleClickEvent)
        self._down = QArrowButton(QArrowButton.DOWN, self)
        self._down.move(0, 138)
        self._down.clickSignal.connect(self.onClickEvent)

    def setValue(self, val):
        if val >= 0 and val <= 9:
            self._value.setText("{0:d}".format(val))
        else:
            raise ValueError("Value must be between 0 and 9")

    def value(self):
        return int(self._value.text())

    def setWriteValue(self, val):
        if val >= 0 and val <= 9:
            self._write_value.setText("{0:d}".format(val))
        else:
            raise ValueError("Value must be between 0 and 9")

    def writeValue(self):
        return int(self._write_value.text())

    def step(self):
        return self._step

    @QtCore.pyqtSlot(int)
    def onClickEvent(self, direction):
        if direction == QArrowButton.UP:
            self.valueChangeSignal.emit(self._step)
        else:
            self.valueChangeSignal.emit(-self._step)

    @QtCore.pyqtSlot()
    def onDoubleClickEvent(self):
        self.doubleClickSignal.emit()

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, event):
        if event.size().isValid() and event.oldSize().isValid():
            w = event.size().width()
            h = event.size().height()
            dw = w - event.oldSize().width()
            dh = h - event.oldSize().height()

            if dh > 0:
                d = int(dh / 3)
                dl = int(dh - d * 2)

                sz = self._up.size()
                self._up.resize(sz.width() + d, sz.height() + d)
                ps = self._up.pos()
                self._up.move(ps.x() + int(dw / 2), ps.y())

                sz = self._value.size()
                self._value.resize(sz.width() + dw, sz.height() + dl)
                ps = self._value.pos()
                self._value.move(ps.x(), ps.y() + d)

                sz = self._write_value.size()
                self._write_value.resize(sz.width() + dw, sz.height() + dl)
                ps = self._write_value.pos()
                self._write_value.move(ps.x(), ps.y() + d)

                sz = self._down.size()
                self._down.resize(sz.width() + d, sz.height() + d)
                ps = self._down.pos()
                self._down.move(ps.x() + int(dw / 2), ps.y() + d + dl)

        else:
            QtWidgets.QWidget.resizeEvent(self, event)


class QDigitDial(QtWidgets.QWidget):

    valueChangeSignal = QtCore.pyqtSignal(float, float)

    def __init__(self, f, parent=None):
        # Parent constructor
        QtWidgets.QWidget.__init__(self, parent)

        # Decimal number
        p1 = re.compile(r"(\d+)d")
        # Floating point number
        p2 = re.compile(r"(\d+)\.(\d+)f")

        self.wdg = []
        offset = 0

        # Sign label
        sign = QtWidgets.QLabel(text=" ", parent=self)
        sign.move(offset, 98)
        sign.resize(20, 55)
        sign.setStyleSheet("text-align: center; font-size: 45px; font-weight:bold; color: black; ")
        self.wdg.append(sign)

        wsign = QtWidgets.QLabel(text=" ", parent=self)
        wsign.move(offset, 68)
        wsign.resize(20, 40)
        wsign.setStyleSheet("text-align: center; font-size: 30px; font-weight:bold; color: darkred; ")
        self.wdg.append(wsign)

        offset += 20

        m = p1.match(f)
        if m is not None:
            # Decimal number
            n = int(m.groups()[0])

            for i in range(n):
                w = QSingleDigitDial(math.pow(10, n - i - 1), self)
                w.move(offset, 0)
                offset += 78
                w.valueChangeSignal.connect(self.onValueChangeEvent)
                w.doubleClickSignal.connect(self.onDoubleClickEvent)
                self.wdg.append(w)
            self._value = 0
            self._w_value = 0
            self.datatype = int

        else:
            m = p2.match(f)
            if m is not None:
                # Floating point
                n1 = int(m.groups()[0])
                n2 = int(m.groups()[1])

                for i in range(n1):
                    w = QSingleDigitDial(math.pow(10, n1 - i - 1), self)
                    w.move(offset, 0)
                    offset += 78
                    w.valueChangeSignal.connect(self.onValueChangeEvent)
                    w.doubleClickSignal.connect(self.onDoubleClickEvent)
                    self.wdg.append(w)

                dot = QtWidgets.QLabel(text=".", parent=self)
                dot.setStyleSheet("font-size: 50px; font-weight:bold; color: black; ")
                dot.move(offset, 78)
                dot.resize(20, 60)
                offset += 20
                self.wdg.append(dot)

                for i in range(n2):
                    w = QSingleDigitDial(math.pow(10, -i - 1), self)
                    w.move(offset, 0)
                    offset += 78
                    w.valueChangeSignal.connect(self.onValueChangeEvent)
                    self.wdg.append(w)

                self._value = 0.0
                self._w_value = 0.0
                self.mantissa = n2
                self.datatype = float
            else:
                # Failure
                raise ValueError("Invalid format")

        self.resize(offset, 216)

    @QtCore.pyqtSlot(float)
    def onValueChangeEvent(self, step):
        # Add step
        old = self._w_value
        self._w_value += self.datatype(step)
        self.update_w_value()
        self.valueChangeSignal.emit(self._w_value, old)

    @QtCore.pyqtSlot()
    def onDoubleClickEvent(self):
        if self.datatype is float:
            val, ok = QtWidgets.QInputDialog.getDouble(self, "New position", "Insert new position", value=self.value(), decimals=self.mantissa)
            if ok:
                old = self._w_value
                self.setWriteValue(val)
                self.valueChangeSignal.emit(self._w_value, old)
        else:
            val, ok = QtWidgets.QInputDialog.getInt(self, "New position", "Insert new position", value=self.value())
            if ok:
                old = self._w_value
                self.setWriteValue(val)
                self.valueChangeSignal.emit(self._w_value, old)

    def value(self):
        if self.datatype is int:
            val = 0
        else:
            val = 0.0
        for w in self.wdg[2:]:
            if type(w) == QtWidgets.QLabel:
                continue
            val += w.value() * w.step()
        if self.wdg[0].text() == "-":
            val *= -1
        return val

    def setValue(self, value):
        self._value = value
        self.update_value()

    def writeValue(self):
        if self.datatype is int:
            val = 0
        else:
            val = 0.0
        for w in self.wdg[2:]:
            if type(w) == QtWidgets.QLabel:
                continue
            val += w.writeValue() * w.step()
        if self.wdg[1].text() == "-":
            val *= -1
        return val

    def setWriteValue(self, value):
        self._w_value = value
        self.update_w_value()

    def update_value(self):
        if self.datatype == int:
            txt = "{0:d}".format(self._value)
        elif self.datatype == float:
            fmt = "{{0:.{0:d}f}}".format(self.mantissa)
            txt = fmt.format(self._value)

        # Update value
        self.wdg[0].setText(" ")
        for i in range(-1, -len(self.wdg) - 1, -1):
            if type(self.wdg[i]) == QtWidgets.QLabel:
                continue
            try:
                t = txt[i]
                if t == "-":
                    self.wdg[0].setText("-")
                    continue
                v = int(txt[i])
                self.wdg[i].setValue(v)
            except IndexError:
                self.wdg[i].setValue(0)

    def update_w_value(self):
        if self.datatype == int:
            txt = "{0:d}".format(self._w_value)
        elif self.datatype == float:
            fmt = "{{0:.{0:d}f}}".format(self.mantissa)
            txt = fmt.format(self._w_value)

        # Update value
        self.wdg[1].setText(" ")
        for i in range(-1, -len(self.wdg) - 1, -1):
            if type(self.wdg[i]) == QtWidgets.QLabel:
                continue
            try:
                t = txt[i]
                if t == "-":
                    self.wdg[1].setText("-")
                    continue
                v = int(txt[i])
                self.wdg[i].setWriteValue(v)
            except IndexError:
                self.wdg[i].setWriteValue(0)

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, event):
        if event.size().isValid() and event.oldSize().isValid():
            w = event.size().width()
            h = event.size().height()
            dw = w - event.oldSize().width()
            dh = h - event.oldSize().height()
            # TODO: missing resing code

        else:
            QtWidgets.QWidget.resizeEvent(self, event)
