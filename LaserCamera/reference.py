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
import copy

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from Ui_reference import Ui_Reference

import PyTango as PT
from PyQTango import TangoUtil


class ReferencePanel(QtWidgets.QDialog, Ui_Reference):

    def __init__(self, parent, scaling=1.0):
        """ Initialize panel
        """
        self.parent = parent
        self.scaling = scaling
        QtWidgets.QDialog.__init__(self, parent)

        # Setup UI
        self.setupUi(self)
        self.setup_fonts_and_scaling()

        # Load references from parent
        self.references = copy.deepcopy(self.parent.references)
        self.ref_mod = False

        # Position dialog to the right
        app = QtWidgets.QApplication.instance()
        screen = app.primaryScreen()
        xpos = self.parent.x() + self.parent.frameGeometry().width()
        if xpos + self.frameSize().height() > screen.availableSize().width():
            delta = xpos + self.frameSize().height() - screen.availableSize().width()
            xpos -= delta
        ypos = self.parent.y()
        self.move(QtCore.QPoint(xpos, ypos))

        # Initialize selector
        self.current_attribute = None
        self.view_select.addItems(['Left', 'Right', 'Projection'])

        # Set left if tab view index is 0, projection if is 1
        if self.parent.tabs.currentIndex() == 1:
            self.view_select.setCurrentIndex(2)

    def setup_fonts_and_scaling(self):
        """ Scale GUI if needed
        """
        # Setup font size and scaling on hidpi
        if self.scaling > 1.1:
            # Scale only if factor is more than 1.1
            self.scale_widget(self, self.scaling)
            members = dir(self)
            for m in members:
                if getattr(self, m) is self.parent:
                    continue
                elif issubclass(type(getattr(self, m)), QtWidgets.QWidget):
                    self.scale_widget(getattr(self, m), self.scaling)

    def scale_widget(self, widget, scaling):
        """ Scale a single widget
        """
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))

    @QtCore.pyqtSlot(int)
    def on_view_select_currentIndexChanged(self, index):
        """ Change reference
        """
        self.ask_save()
        if index == 0:
            self.current_attribute = str(self.parent.image_l_select.currentText()).lower()
            if not self.parent.image_bt_reference_l.isChecked():
                self.parent.image_bt_reference_l.setChecked(True)

        elif index == 1:
            self.current_attribute = str(self.parent.image_r_select.currentText()).lower()
            if not self.parent.image_bt_reference_r.isChecked():
                self.parent.image_bt_reference_r.setChecked(True)

        elif index == 2:
            self.current_attribute = str(self.parent.spec_img.currentText()).lower()
            if not self.parent.image_bt_reference_u.isChecked():
                self.parent.image_bt_reference_u.setChecked(True)
            if not self.parent.image_bt_reference_d.isChecked():
                self.parent.image_bt_reference_d.setChecked(True)

        else:
            # This should never happen...
            self.view_select.setCurrentIndex(0)

        # Update fields
        for w in ('x', 'y', 'v', 'h'):
            getattr(self, w).blockSignals(True)

        ref = self.references[self.current_attribute]
        if ref is not None:
            self.x.setValue(ref['x'])
            self.y.setValue(ref['y'])
            self.h.setValue(ref['h'])
            self.v.setValue(ref['v'])
        else:
            self.x.setValue(0)
            self.y.setValue(0)
            self.h.setValue(0)
            self.v.setValue(0)

        for w in ('x', 'y', 'v', 'h'):
            getattr(self, w).blockSignals(False)

    @QtCore.pyqtSlot(float)
    def on_x_valueChanged(self, value):
        if self.references[self.current_attribute] is None:
            self.references[self.current_attribute] = {'x': 0, 'y': 0, 'h': 0, 'v': 0}
        self.references[self.current_attribute]['x'] = value
        self.update_reference()
        self.set_ref_modified()

    @QtCore.pyqtSlot(float)
    def on_y_valueChanged(self, value):
        if self.references[self.current_attribute] is None:
            self.references[self.current_attribute] = {'x': 0, 'y': 0, 'h': 0, 'v': 0}
        self.references[self.current_attribute]['y'] = value
        self.update_reference()
        self.set_ref_modified()

    @QtCore.pyqtSlot(float)
    def on_h_valueChanged(self, value):
        if self.references[self.current_attribute] is None:
            self.references[self.current_attribute] = {'x': 0, 'y': 0, 'h': 0, 'v': 0}
        self.references[self.current_attribute]['h'] = value
        self.update_reference()
        self.set_ref_modified()

    @QtCore.pyqtSlot(float)
    def on_v_valueChanged(self, value):
        if self.references[self.current_attribute] is None:
            self.references[self.current_attribute] = {'x': 0, 'y': 0, 'h': 0, 'v': 0}
        self.references[self.current_attribute]['v'] = value
        self.update_reference()
        self.set_ref_modified()

    def update_reference(self):
        if self.view_select.currentIndex() == 0:
            if self.parent.image_l_ref is None:
                self.parent.image_l_ref = self.parent.draw_reference(self.parent.image_l_ax, self.references[self.current_attribute])
            else:
                self.parent.update_reference(self.parent.image_l_ax, self.parent.image_l_ref, self.references[self.current_attribute])
            self.parent.canvas_l.draw()

        elif self.view_select.currentIndex() == 1:
            if self.parent.image_r_ref is None:
                self.parent.image_r_ref = self.parent.draw_reference(self.parent.image_r_ax, self.references[self.current_attribute])
            else:
                self.parent.update_reference(self.parent.image_r_ax, self.parent.image_r_ref, self.references[self.current_attribute])
            self.parent.canvas_r.draw()

        elif self.view_select.currentIndex() == 2:
            if self.parent.image_u_ref is None:
                self.parent.image_u_ref = self.parent.draw_projection_ref(self.parent.image_u_ax, self.references[self.current_attribute]['x'], 'xkcd:lime green')
            else:
                self.parent.update_projection_ref(self.parent.image_u_ax, self.parent.image_u_ref[0], self.references[self.current_attribute]['x'])

            if self.parent.image_d_ref is None:
                self.parent.image_d_ref = self.parent.draw_projection_ref(self.parent.image_d_ax, self.references[self.current_attribute]['y'], 'xkcd:lime green')
            else:
                self.parent.update_projection_ref(self.parent.image_u_ax, self.parent.image_d_ref[0], self.references[self.current_attribute]['y'])

            self.parent.canvas_u.draw()
            self.parent.canvas_d.draw()

        else:
            return

    def remove_reference(self):
        if self.view_select.currentIndex() == 0:
            if self.parent.image_l_ref is not None:
                if len(self.parent.image_l_ref)> 2:
                    self.parent.image_l_ref[-1].remove()
                self.parent.remove_plot_lines(self.parent.image_l_ax, self.parent.image_l_ref[0:2])
                self.parent.image_l_ref = None
                self.parent.canvas_l.draw()

        elif self.view_select.currentIndex() == 1:
            if self.parent.image_r_ref is not None:
                if len(self.parent.image_r_ref)> 2:
                    self.parent.image_r_ref[-1].remove()
                self.parent.remove_plot_lines(self.parent.image_r_ax, self.parent.image_r_ref[0:2])
                self.parent.image_r_ref = None
                self.parent.canvas_r.draw()

        elif self.view_select.currentIndex() == 2:
            if self.parent.image_u_ref is not None:
                self.parent.remove_plot_lines(self.parent.image_u_ax, self.parent.image_u_ref)
                self.parent.image_u_ref = None
                self.parent.canvas_u.draw()

            if self.parent.image_d_ref is not None:
                self.parent.remove_plot_lines(self.parent.image_d_ax, self.parent.image_d_ref)
                self.parent.image_d_ref = None
                self.parent.canvas_d.draw()

        else:
            return

    @QtCore.pyqtSlot()
    def on_pb_centroid_released(self):
        if self.view_select.currentText() == 'Left':
            attr_name = str(self.parent.image_l_select.currentText()).lower()
        elif self.view_select.currentText() == 'Right':
            attr_name = str(self.parent.image_r_select.currentText()).lower()
        elif self.view_select.currentText() == 'Projection':
            attr_name = str(self.parent.spec_img.currentText()).lower()
        else:
            return

        if not self.parent.any_centroid_on(attr_name) or attr_name not in self.parent.last_centroid:
            QtWidgets.QMessageBox.critical(self, "Cannot get centroid", "To set reference to centroid tracking must be on")
            return
        self.x.setValue(self.parent.last_centroid[attr_name][0])
        self.y.setValue(self.parent.last_centroid[attr_name][1])

    @QtCore.pyqtSlot()
    def on_pb_gauss_released(self):
        if self.view_select.currentText() == 'Left':
            attr_name = str(self.parent.image_l_select.currentText()).lower()
        elif self.view_select.currentText() == 'Right':
            attr_name = str(self.parent.image_r_select.currentText()).lower()
        elif self.view_select.currentText() == 'Projection':
            attr_name = str(self.parent.spec_img.currentText()).lower()
        else:
            return

        if not self.parent.any_centroid_on(attr_name) or attr_name not in self.parent.last_centroid:
            QtWidgets.QMessageBox.critical(self, "Cannot get fit", "To set reference to gauss fit tracking must be on")
            return
        self.x.setValue(self.parent.last_centroid[attr_name][2][0])
        self.y.setValue(self.parent.last_centroid[attr_name][2][1])
        self.h.setValue(self.parent.last_centroid[attr_name][2][2])
        self.v.setValue(self.parent.last_centroid[attr_name][2][3])

    @QtCore.pyqtSlot()
    def on_pb_save_released(self):
        if self.ref_mod:
            self.parent.references[self.current_attribute] = copy.deepcopy(self.references[self.current_attribute])
        self.ref_mod = False
        self.pb_save.setStyleSheet("")

    @QtCore.pyqtSlot()
    def on_pb_reset_released(self):
        self.references[self.current_attribute] = copy.deepcopy(self.parent.references[self.current_attribute])
        if self.references[self.current_attribute] is None:
            self.remove_reference()
        else:
            self.x.setValue(self.references[self.current_attribute]['x'])
            self.y.setValue(self.references[self.current_attribute]['y'])
            self.h.setValue(self.references[self.current_attribute]['h'])
            self.v.setValue(self.references[self.current_attribute]['v'])
        self.ref_mod = False
        self.pb_save.setStyleSheet("")

    def set_ref_modified(self):
        self.ref_mod = True
        self.pb_save.setStyleSheet("color: red")

    def ask_save(self):
        if self.ref_mod:
            ans = QtWidgets.QMessageBox.question(self, "Reference modified", "The reference was modified. Do you want to save it?")
            if ans == QtWidgets.QMessageBox.Yes:
                self.on_pb_save_released()
            else:
                self.on_pb_reset_released()

    def accept(self):
        """ Intercept accept() to delete dialog
        """
        self.ask_save()
        self.parent.setref_panel = None
        QtWidgets.QDialog.accept(self)

    def reject(self):
        """ Intercept reject() to close camera
        """
        self.ask_save()
        self.parent.setref_panel = None
        QtWidgets.QDialog.reject(self)
