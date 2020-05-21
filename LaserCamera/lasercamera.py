#!/usr/bin/env python3
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

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtWidgets import QFileDialog

from Ui_lasercamera import Ui_LaserCamera
from camerasetup import CameraSetup
from reference import ReferencePanel

import re
import h5py as h5
import time
import datetime
import numpy as np
import cv2
import PyTango as PT
from scipy.optimize import curve_fit
import threading


# Matplotlib stuff
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse


class NavigationToolbar(NavigationToolbar2QT):
    toolitems = [t for t in NavigationToolbar2QT.toolitems if t[0] not in ('Subplots', 'Back', 'Forward')]


class EventSimulator(threading.Thread):
    """ Simulator for image events
    """

    def __init__(self, parent, img_attr):
        """ Init thread and start
        """
        threading.Thread.__init__(self)
        self.img_attr = img_attr
        self.parent = parent
        self._terminate = False
        self.start()

    def run(self):
        """ Main loop
        """
        while not self._terminate:
            s = time.time()

            # Create an image with noise 100x120
            x = np.arange(100)
            y = np.arange(120)
            xx, yy = np.meshgrid(x, y)
            self.parent.gf.last_x0 = 20*np.random.rand()+40
            self.parent.gf.last_y0 = 20*np.random.rand()+40
            image = self.parent.gf.gaussian_2D(xx, yy, 10, 100, self.parent.gf.last_x0, self.parent.gf.last_y0, 10, 10)
            image += 10 * np.random.rand(*image.shape) - 5
            image = np.uint16(image)

            for a in self.img_attr:
                # Push fake events (just populate attributes that are really used by the handler)
                ev = PT.EventData()
                ev.attr_name = a
                val = PT.DeviceAttribute()
                val.name = a
                val.value = image
                ev.attr_value = val
                ev.err = False
                self.parent.tango_event.emit(ev)

            # Sleep to have a burst of events every 0.5s
            e = time.time() - s
            if e < 0.5:
                time.sleep(0.5 - e)

    def terminate(self):
        """ Terminate event simulator
        """
        self._terminate = True


class GaussFitter(object):

    def __init__(self):
        self.last_x0 = 0
        self.last_y0 = 0

    def initial_guess(self, x, y):
        baseline = np.min(y)
        maximum = np.max(y) - baseline
        id_max = np.argmax(y)
        mean = x[id_max]
        # FWHM = 2 * sqrt(2 * log(2)) * sigma
        y_fwhm = np.abs(y - baseline - maximum/2)
        fwhm_id1 = np.argmin(y_fwhm[0:id_max])
        fwhm_id2 = id_max + np.argmin(y_fwhm[id_max:])
        fwhm = x[fwhm_id2] - x[fwhm_id1]
        sigma = fwhm / 2 / np.sqrt(2 * np.log(2))
        return (baseline, maximum, mean, sigma)

    def fit(self, x, y):
        guess = self.initial_guess(x, y)
        popt, pcov = curve_fit(self.gaussian_1D, x, y, guess)
        return popt

    def gaussian_1D(self, x, baseline, maximum, mean, sigma):
        """ 1D gaussian function
        """
        return baseline + maximum * np.exp( -np.power(x - mean, 2) / (2 * np.power(sigma, 2)))

    def gaussian_2D_angle(self, x, y, baseline, maximum, mean_x, mean_y, sigma_x, sigma_y, theta):
        """ 2D gaussian function with rotation
        """
        a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
        b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
        c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
        g = baseline + maximum * np.exp( - (a * ((x - mean_x)**2) + 2 * b * (x - mean_y) * (y - mean_y) + c * ((y - mean_y)**2)) )
        return g

    def gaussian_2D(self, x, y, baseline, maximum, mean_x, mean_y, sigma_x, sigma_y):
        return baseline + maximum * np.exp( - ( (x - mean_x)**2 / (2 * sigma_x**2) + (y - mean_y)**2 / (2 * sigma_y**2) ) )

    def gaussian_2D_model(self, X, baseline, maximum, mean_x, mean_y, sigma_x, sigma_y):
        """ 2D gaussian model
        """
        x, y = X
        g = self.gaussian_2D(x, y, baseline, maximum, mean_x, mean_y, sigma_x, sigma_y)
        return g.ravel()

    def fit_2d(self, x, y, z):
        # Get h and v profiles to estimate mean and sigma
        v = np.sum(z, axis=1) / z.shape[1]
        h = np.sum(z, axis=0) / z.shape[0]
        gh = self.initial_guess(x, h)
        gv = self.initial_guess(y, v)
        # Get baseline by comapring corners of the image
        corners = np.mean(z[0:10,0:10])                      # Up left
        corners = np.append(corners, np.mean(z[0:10,-10:]))  # Up right
        corners = np.append(corners, np.mean(z[-10:,0:10]))  # Down left
        corners = np.append(corners, np.mean(z[-10:,-10:]))  # Down right
        baseline = np.mean(corners[corners <= np.median(corners)])
        # Get maximum
        maximum = np.max(z) - baseline
        # Compose initial guess
        guess = (baseline, maximum, gh[2], gv[2], gh[3], gv[3])
        # Lower and upper bounds
        lower_l = (0, maximum * 0.8, gh[2] * 0.8, gv[2] * 0.8, gh[3] * 0.8, gv[3] * 0.8)
        upper_l = (np.max(corners), maximum * 1.2, gh[2] * 1.2, gv[2] * 1.2, gh[3] * 1.2, gv[3] * 1.2)
        xx, yy = np.meshgrid(x, y)
        try:
            #popt, pcov = curve_fit(self.gaussian_2D_model, (xx, yy), z.ravel(), guess, maxfev=10000)
            popt, pcov = curve_fit(self.gaussian_2D_model, (xx, yy), z.ravel(), guess, bounds=(lower_l, upper_l), max_nfev=10000)
            return popt
        except RuntimeError:
            print("[D] Fit failed")
            return guess


class LaserCamera(QtWidgets.QMainWindow, Ui_LaserCamera):

    """ Laser camera GUI main window. """

    # Tango change event signal
    tango_event = QtCore.pyqtSignal(PT.EventData)

    def __init__(self, debug=False, simulation=False, parent=None):
        # Parent constructors
        QtWidgets.QMainWindow.__init__(self, parent)

        # Debug flag
        self.debug_enabled = debug

        # Simulation flag
        self.simulation = simulation

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
        self.tabs.setCurrentIndex(0)
        self.setref_panel = None
        self.references = {}
        self.last_centroid = {}
        self.last_update = {}

        # GaussFitter
        self.gf = GaussFitter()

        # Icons
        track_icon = QtGui.QIcon()
        track_icon.addPixmap(QtGui.QPixmap(":/buttons/target.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        reference_icon = QtGui.QIcon()
        reference_icon.addPixmap(QtGui.QPixmap(":/buttons/reference.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.track_c_icon = QtGui.QIcon()
        self.track_c_icon.addPixmap(QtGui.QPixmap(":/buttons/axis.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.track_e_icon = QtGui.QIcon()
        self.track_e_icon.addPixmap(QtGui.QPixmap(":/buttons/axis_ellipse.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        autoscale_icon = QtGui.QIcon()
        autoscale_icon.addPixmap(QtGui.QPixmap(":/buttons/autoscale.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        gauss_icon = QtGui.QIcon()
        gauss_icon.addPixmap(QtGui.QPixmap(":/buttons/gauss.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)

        # Setup canvas for images
        for pos in ['l', 'r', 'u', 'd']:
            setattr(self, 'fig_'+pos, Figure())
            setattr(self, 'canvas_'+pos, FigureCanvas(getattr(self, 'fig_'+pos)))
            getattr(self, 'canvas_'+pos).setParent(self)
            vbox = QtWidgets.QVBoxLayout()
            vbox.addWidget(getattr(self, 'canvas_'+pos))

            # Toolbar
            toolbar = NavigationToolbar(getattr(self, 'canvas_'+pos), self)

            # Remove current position label
            n = toolbar.layout().count()
            toolbar.layout().takeAt(n - 1)
            toolbar.addSeparator()

            ## Enable centroid
            setattr(self, 'image_bt_tracking_'+pos, QtWidgets.QToolButton())
            obj = getattr(self, 'image_bt_tracking_'+pos)
            obj.setIcon(track_icon)
            obj.setCheckable(True)
            obj.setObjectName('image_bt_tracking_'+pos)
            obj.setToolTip("Enable beam tracking")
            toolbar.addWidget(obj)

            ## Enable reference
            setattr(self, 'image_bt_reference_'+pos, QtWidgets.QToolButton())
            obj = getattr(self, 'image_bt_reference_'+pos)
            obj.setIcon(reference_icon)
            obj.setCheckable(True)
            obj.setObjectName('image_bt_reference_'+pos)
            obj.setToolTip("Enable reference display")
            toolbar.addWidget(obj)

            ## Swap between centroid tracking and ellipse reference
            setattr(self, 'image_bt_swapref_'+pos, QtWidgets.QToolButton())
            obj = getattr(self, 'image_bt_swapref_'+pos)
            obj.setIcon(self.track_c_icon)
            obj.setCheckable(True)
            obj.setObjectName('image_bt_swapref_'+pos)
            obj.setToolTip("Swap between centroid and ellipse reference")
            toolbar.addWidget(obj)

            if pos in ['u', 'd']:
                ## Autoscale
                setattr(self, 'image_bt_autoscale_'+pos, QtWidgets.QToolButton())
                obj = getattr(self, 'image_bt_autoscale_'+pos)
                obj.setIcon(autoscale_icon)
                obj.setCheckable(True)
                obj.setObjectName('image_bt_autoscale_'+pos)
                obj.setToolTip("Enable vertical autoscale")
                toolbar.addWidget(obj)

                ## Gauss fit
                setattr(self, 'image_bt_gauss_'+pos, QtWidgets.QToolButton())
                obj = getattr(self, 'image_bt_gauss_'+pos)
                obj.setIcon(gauss_icon)
                obj.setCheckable(True)
                obj.setObjectName('image_bt_gauss_'+pos)
                obj.setToolTip("Enable gauss fit")
                toolbar.addWidget(obj)

            # Add toolbar to layout
            vbox.addWidget(toolbar)

            # Add layout to plot area
            getattr(self, 'image_'+pos).setLayout(vbox)
            setattr(self, 'image_'+pos+'_ax', None)
            setattr(self, 'image_'+pos+'_plot', None)
            setattr(self, 'image_'+pos+'_tracking', None)
            setattr(self, 'image_'+pos+'_ref', None)
            if pos in ['u', 'd']:
                setattr(self, 'image_'+pos+'_fit', None)

        # Connect event to slot
        self.tango_event.connect(self.event_handler)

        # Tango device
        if not self.simulation:
            self.db = PT.Database()
            prop = self.db.get_property("LaserCamera", "camera")
            self.dev = None
            self.ev_id = {}
            if len(prop['camera']):
                self.setup_camera(prop['camera'][0])
        else:
            self.dev = None
            self.setup_simulator()

        # Connect plot buttons
        for pos in ['l', 'r', 'u', 'd']:
            getattr(self, 'image_bt_tracking_'+pos).toggled.connect(getattr(self, 'on_image_bt_tracking_'+pos+'_toggled'))
            getattr(self, 'image_bt_swapref_'+pos).toggled.connect(getattr(self, 'on_image_bt_swapref_'+pos+'_toggled'))
            getattr(self, 'image_bt_reference_'+pos).toggled.connect(getattr(self, 'on_image_bt_reference_'+pos+'_toggled'))

            if pos in ['u', 'd']:
                getattr(self, 'image_bt_gauss_'+pos).toggled.connect(getattr(self, 'on_image_bt_gauss_'+pos+'_toggled'))

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

            # Scale matplotlib fonts
            matplotlib.rcParams['font.size'] = int(matplotlib.rcParams['font.size'] * self.scaling)

    def scale_widget(self, widget, scaling):
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))

    def close_camera(self):
        if self.dev is not None:
            for attr,ev in self.ev_id.items():
                try:
                    if ev is not None:
                        self.dev.unsubscribe_event(ev)
                except PT.DevFailed as e:
                    self.error("Failed to unsubscribe event ({0!s})".format(e.args[0].desc))
            self.dev = None
            self.ev_id = {}

        if self.simulation and self.sim_thread is not None:
            self.sim_thread.terminate()
            self.sim_thread.join()

        # Clear plots
        for pos in ['l', 'r', 'u', 'd']:
            getattr(self, 'fig_'+pos).clear()
            setattr(self, 'image_'+pos+'_ax', None)
            setattr(self, 'image_'+pos+'_plot', None)
            setattr(self, 'image_'+pos+'_tracking', None)
            setattr(self, 'image_'+pos+'_ref', None)
            if pos in ['u', 'd']:
                setattr(self, 'image_'+pos+'_fit', None)

    def setup_camera(self, device):
        self.close_camera()
        try:
            self.dev = PT.DeviceProxy(device)

            # Find all image attributes
            img_attr = []
            for a in self.dev.get_attribute_list():
                if re.match("^Image.*", a) is not None:
                    img_attr.append(a)
            img_attr.sort()

            for a in img_attr:
                self.ev_id[a] = None

            # Populate combo boxes
            self.image_l_select.blockSignals(True)
            self.image_r_select.blockSignals(True)
            self.spec_img.blockSignals(True)
            self.image_l_select.addItems(img_attr)
            self.image_r_select.addItems(img_attr)
            self.spec_img.addItems(img_attr)
            self.image_l_select.blockSignals(False)
            self.image_r_select.blockSignals(False)
            self.spec_img.blockSignals(False)

            # Try to load references from database
            prop_names = []
            for a in img_attr:
                prop_names.append("{0}:{1}".format(self.dev.name(), a.lower()))
            props = self.db.get_property("LaserCamera", prop_names)
            self.references = {}
            for k, v in props.items():
                self.debug("Property: {0} => {1}".format(k, v))
                (d, a) = k.split(':')
                self.references[a] = None
                if len(v):
                    m = re.match("x=(\d+\.\d+):y=(\d+\.\d+):h=(\d+\.\d+):v=(\d+\.\d+)", v[0])
                    if m is not None:
                        self.references[a] = {}
                        self.references[a]['x'] = float(m.groups()[0])
                        self.references[a]['y'] = float(m.groups()[1])
                        self.references[a]['h'] = float(m.groups()[2])
                        self.references[a]['v'] = float(m.groups()[3])

            # Select images
            if len(img_attr) > 2:
                self.image_l_select.setCurrentIndex(1)
                self.image_r_select.setCurrentIndex(2)
                self.spec_img.setCurrentIndex(1)
            elif len(img_attr) > 1:
                self.image_l_select.setCurrentIndex(1)
                self.image_r_select.setCurrentIndex(1)
                self.spec_img.setCurrentIndex(1)
            else:
                self.image_l_select.setCurrentIndex(0)
                self.image_r_select.setCurrentIndex(0)
                self.spec_img.setCurrentIndex(0)

        except PT.DevFailed as e:
            self.error("Camera setup failed ({0!s})".format(e.args[0].desc))
            self.close_camera()

    def setup_simulator(self):
        img_attr = ['Image_00', 'Image_01']
         # Populate combo boxes
        self.image_l_select.addItems(img_attr)
        self.image_r_select.addItems(img_attr)
        self.image_r_select.setCurrentIndex(1)
        self.spec_img.addItems(img_attr)
        self.sim_thread = EventSimulator(self, img_attr)
        self.references = {}
        for a in img_attr:
            self.references[a.lower()] = None

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

            if attr_name in self.last_update:
                if time.time() - self.last_update[attr_name] < 0.5:
                    return

            self.last_update[attr_name] = time.time()
            img = ev.attr_value.value

            # Compute image centroid if any of the views need it
            if self.any_centroid_on(attr_name):
                centroid = self.compute_centroid(img)
                if centroid is None:
                    self.last_centroid[attr_name] = None
                    self.error("Failed to find a centroid")
                else:
                    self.last_centroid[attr_name] = centroid
            else:
                centroid = None

            ##
            ## LEFT IMAGE
            ##
            if attr_name == self.image_l_select.currentText().lower():

                # Update image
                if self.image_l_ax is None:
                    self.image_l_ax = self.fig_l.add_subplot(111)
                    self.image_l_plot = self.image_l_ax.imshow(img, cmap='jet')
                    self.fig_l.tight_layout()
                else:
                    self.image_l_plot.set_data(img)
                    self.image_l_plot.set_clim([np.min(img), np.max(img)])

                # Check if centroid is enabled
                if self.image_bt_tracking_l.isChecked() and centroid is not None:
                    # Check the type of plot
                    if self.image_bt_swapref_l.isChecked():
                        c_l = centroid[2]
                    else:
                        c_l = centroid[0:2]

                    if self.image_l_tracking is None:
                        # Add a new plot
                        self.image_l_tracking = self.draw_centroid(self.image_l_ax, c_l)

                    else:
                        # Update plot
                        self.update_centroid(self.image_l_ax, self.image_l_tracking, c_l)

                # Update canvas
                self.canvas_l.draw()

            ##
            ## RIGHT IMAGE
            ##
            if attr_name == self.image_r_select.currentText().lower():

                # Update RIGHT
                if self.image_r_ax is None:
                    self.image_r_ax = self.fig_r.add_subplot(111)
                    self.image_r_plot = self.image_r_ax.imshow(img, cmap='jet')
                    self.fig_r.tight_layout()
                else:
                    self.image_r_plot.set_array(img)
                    self.image_r_plot.set_clim([np.min(img), np.max(img)])

                # Check if centroid is enabled
                if self.image_bt_tracking_r.isChecked() and centroid is not None:
                    # Check the type of plot
                    if self.image_bt_swapref_r.isChecked():
                        c_r = centroid[2]
                    else:
                        c_r = centroid[0:2]

                    if self.image_r_tracking is None:
                        # Add a new plot
                        self.image_r_tracking = self.draw_centroid(self.image_r_ax, c_r)

                    else:
                        # Update plot
                        self.update_centroid(self.image_r_ax, self.image_r_tracking, c_r)

                # Update canvas
                self.canvas_r.draw()

            ##
            ## PROJECTIONS
            ##
            # Spectrum view
            if attr_name == self.spec_img.currentText().lower():
                # Update projections
                (v, h) = self.compute_profiles(img)

                # Plot top profile
                if self.image_u_ax is None:
                    self.image_u_ax = self.fig_u.add_subplot(111)
                    self.image_u_ax.set_title("Horizontal profile")
                    self.image_u_plot = self.image_u_ax.plot(h)
                    self.fig_u.tight_layout()
                else:
                    self.image_u_plot[0].set_ydata(h)

                # Check autoscale
                if self.image_bt_autoscale_u.isChecked():
                    self.image_u_ax.set_ylim([np.min(h), np.max(h)])

                # Check if tracking is enabled
                if self.image_bt_tracking_u.isChecked():
                    if self.image_bt_swapref_u.isChecked():
                        pos = centroid[2][0]
                    else:
                        pos = centroid[0]
                    if self.image_u_tracking is None:
                        self.image_u_tracking = self.draw_projection_ref(self.image_u_ax, pos, 'xkcd:sunflower yellow')
                    else:
                        self.update_projection_ref(self.image_u_ax, self.image_u_tracking[0], pos)

                # Check if we have to plot or update gauss fit
                if self.image_bt_gauss_u.isChecked():
                    if self.image_u_fit is None:
                        self.image_u_fit = self.draw_gauss_fit(self.image_u_ax, self.image_u_plot[0])
                    else:
                        self.update_gauss_fit(self.image_u_plot[0], self.image_u_fit[0])

                # Plot bottom profile
                if self.image_d_ax is None:
                    self.image_d_ax = self.fig_d.add_subplot(111)
                    self.image_d_ax.set_title("Vertical profile")
                    self.image_d_plot = self.image_d_ax.plot(v)
                    self.fig_d.tight_layout()
                else:
                    self.image_d_plot[0].set_ydata(v)

                # Check autoscale
                if self.image_bt_autoscale_d.isChecked():
                    self.image_d_ax.set_ylim([np.min(v), np.max(v)])

                # Check if tracking is enabled
                if self.image_bt_tracking_d.isChecked():
                    if self.image_bt_swapref_d.isChecked():
                        pos = centroid[2][1]
                    else:
                        pos = centroid[1]
                    if self.image_d_tracking is None:
                        self.image_d_tracking = self.draw_projection_ref(self.image_d_ax, pos, 'xkcd:sunflower yellow')
                    else:
                        self.update_projection_ref(self.image_d_ax, self.image_d_tracking[0], pos)

                # Check if we have to plot or update gauss fit
                if self.image_bt_gauss_d.isChecked():
                    if self.image_d_fit is None:
                        self.image_d_fit = self.draw_gauss_fit(self.image_d_ax, self.image_d_plot[0])
                    else:
                        self.update_gauss_fit(self.image_d_plot[0], self.image_d_fit[0])

                # Update canvas
                self.canvas_u.draw()
                self.canvas_d.draw()

    def remove_plot_lines(self, ax, lines):
        """ Remove the given list of lines from the given axes
        """
        for line in lines:
            index = ax.lines.index(line)
            del ax.lines[index]

    def any_centroid_on(self, attr_name):
        if str(self.image_l_select.currentText()).lower() == attr_name:
            if self.image_bt_tracking_l.isChecked():
                return True
        if str(self.image_r_select.currentText()).lower() == attr_name:
            if self.image_bt_tracking_r.isChecked():
                return True
        if str(self.spec_img.currentText()).lower() == attr_name:
            if self.image_bt_tracking_u.isChecked() or self.image_bt_tracking_d.isChecked():
                return True
        return False

    def draw_centroid(self, ax, centroid):
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        out = []
        # First plot horizontal
        out += ax.plot(xlim, (centroid[1], centroid[1]), color='xkcd:sunflower yellow', linewidth=2)
        # Second plot vertical
        out += ax.plot((centroid[0], centroid[0]), ylim, color='xkcd:sunflower yellow', linewidth=2)
        if len(centroid) > 2:
            # Draw also ellipse
            e = Ellipse((centroid[0], centroid[1]), centroid[2], centroid[3], angle=0, fill=False, color='xkcd:sunflower yellow', linewidth=2)
            ax.add_patch(e)
            out.append(e)
        return out

    def update_centroid(self, ax, lines, centroid):
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        # First update horizontal
        lines[0].set_data(xlim, (centroid[1], centroid[1]))
        # Second update vertical
        lines[1].set_data((centroid[0], centroid[0]), ylim)
        # Update ellipse
        if len(centroid) > 2:
            if len(lines) > 2:
                lines[2].remove()
            else:
                lines.append(None)
            e = Ellipse((centroid[0], centroid[1]), centroid[2], centroid[3], angle=0, fill=False, color='xkcd:sunflower yellow', linewidth=2)
            ax.add_patch(e)
            lines[2] = e

    def draw_reference(self, ax, ref):
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        out = []
        # First plot horizontal
        out += ax.plot(xlim, (ref['y'], ref['y']), color='xkcd:lime green', linewidth=2)
        # Second plot vertical
        out += ax.plot((ref['x'], ref['x']), ylim, color='xkcd:lime green', linewidth=2)
        if ref['v'] > 0 and ref['h'] > 0:
            # Draw also ellipse
            e = Ellipse((ref['x'], ref['y']), ref['h'], ref['v'], angle=0, fill=False, color='xkcd:lime green', linewidth=2)
            ax.add_patch(e)
            out.append(e)
        return out

    def update_reference(self, ax, lines, ref):
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        # First update horizontal
        lines[0].set_data(xlim, (ref['y'], ref['y']))
        # Second update vertical
        lines[1].set_data((ref['x'], ref['x']), ylim)
        # Update ellipse
        if ref['h'] > 0 and ref['v'] > 0:
            if len(lines) > 2:
                lines[2].remove()
            else:
                lines.append(None)
            e = Ellipse((ref['x'], ref['y']), ref['h'], ref['v'], angle=0, fill=False, color='xkcd:lime green', linewidth=2)
            ax.add_patch(e)
            lines[2] = e
        else:
            if len(lines) > 2:
                lines[2].remove()
                del lines[2]

    def draw_projection_ref(self, ax, pos, color):
        ylim = ax.get_ylim()
        lines = ax.plot((pos, pos), ylim, color=color)
        return lines

    def update_projection_ref(self, ax, line, pos):
        ylim = ax.get_ylim()
        line.set_data((pos, pos), ylim)

    @QtCore.pyqtSlot(bool)
    def on_image_bt_tracking_l_toggled(self, state):
        if not state and self.image_l_tracking is not None:
            if len(self.image_l_tracking) > 2:
                self.image_l_tracking[-1].remove()
            self.remove_plot_lines(self.image_l_ax, self.image_l_tracking[0:2])
            self.image_l_tracking = None
            self.canvas_l.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_tracking_r_toggled(self, state):
        if not state and self.image_r_tracking is not None:
            if len(self.image_r_tracking) > 2:
                self.image_r_tracking[-1].remove()
            self.remove_plot_lines(self.image_r_ax, self.image_r_tracking[0:2])
            self.image_r_tracking = None
            self.canvas_r.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_tracking_u_toggled(self, state):
        if not state and self.image_u_tracking is not None:
            self.remove_plot_lines(self.image_u_ax, self.image_u_tracking)
            self.image_u_tracking = None
            self.canvas_u.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_tracking_d_toggled(self, state):
        if not state and self.image_d_tracking is not None:
            self.remove_plot_lines(self.image_d_ax, self.image_d_tracking)
            self.image_d_tracking = None
            self.canvas_d.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_swapref_l_toggled(self, state):
        if state:
            self.image_bt_swapref_l.setIcon(self.track_e_icon)
        else:
            self.image_bt_swapref_l.setIcon(self.track_c_icon)
            if self.image_l_tracking is not None and len(self.image_l_tracking) > 2:
                self.image_l_tracking[-1].remove()
                del self.image_l_tracking[-1]

    @QtCore.pyqtSlot(bool)
    def on_image_bt_swapref_r_toggled(self, state):
        if state:
            self.image_bt_swapref_r.setIcon(self.track_e_icon)
        else:
            self.image_bt_swapref_r.setIcon(self.track_c_icon)
            if self.image_r_tracking is not None and len(self.image_r_tracking) > 2:
                self.image_r_tracking[-1].remove()
                del self.image_r_tracking[-1]

    @QtCore.pyqtSlot(bool)
    def on_image_bt_swapref_u_toggled(self, state):
        if state:
            self.image_bt_swapref_u.setIcon(self.track_e_icon)
        else:
            self.image_bt_swapref_u.setIcon(self.track_c_icon)

    @QtCore.pyqtSlot(bool)
    def on_image_bt_swapref_d_toggled(self, state):
        if state:
            self.image_bt_swapref_d.setIcon(self.track_e_icon)
        else:
            self.image_bt_swapref_d.setIcon(self.track_c_icon)

    @QtCore.pyqtSlot(bool)
    def on_image_bt_reference_l_toggled(self, state):
        if state:
            attribute = str(self.image_l_select.currentText()).lower()
            if attribute in self.references and self.references[attribute] is not None:
                self.image_l_ref = self.draw_reference(self.image_l_ax, self.references[attribute])
        else:
            if self.image_l_ref is not None:
                if len(self.image_l_ref) > 2:
                    self.image_l_ref[-1].remove()
                self.remove_plot_lines(self.image_l_ax, self.image_l_ref[0:2])
                self.image_l_ref = None
                self.canvas_l.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_reference_r_toggled(self, state):
        if state:
            attribute = str(self.image_r_select.currentText()).lower()
            if attribute in self.references and self.references[attribute] is not None:
                self.image_r_ref = self.draw_reference(self.image_r_ax, self.references[attribute])
        else:
            if self.image_r_ref is not None:
                if len(self.image_r_ref) > 2:
                    self.image_r_ref[-1].remove()
                self.remove_plot_lines(self.image_r_ax, self.image_r_ref[0:2])
                self.image_r_ref = None
                self.canvas_r.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_reference_u_toggled(self, state):
        if state:
            attribute = str(self.spec_img.currentText()).lower()
            if attribute in self.references and self.references[attribute] is not None:
                self.image_u_ref = self.draw_projection_ref(self.image_u_ax, self.references[attribute]['x'], 'xkcd:lime green')
        else:
            if self.image_u_ref is not None:
                self.remove_plot_lines(self.image_u_ax, self.image_u_ref)
                self.image_u_ref = None
                self.canvas_u.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_reference_d_toggled(self, state):
        if state:
            attribute = str(self.spec_img.currentText()).lower()
            if attribute in self.references and self.references[attribute] is not None:
                self.image_d_ref = self.draw_projection_ref(self.image_d_ax, self.references[attribute]['y'], 'xkcd:lime green')
        else:
            if self.image_d_ref is not None:
                self.remove_plot_lines(self.image_d_ax, self.image_d_ref)
                self.image_d_ref = None
                self.canvas_d.draw()

    def draw_gauss_fit(self, ax, plot):
        """ Add gauss fit plot to figure
        """
        x = plot.get_xdata()
        y = plot.get_ydata()
        param = self.gf.fit(x, y)
        fit = self.gf.gaussian_1D(x, *param)
        lines = ax.plot(x, fit, 'r')
        return lines

    def update_gauss_fit(self, plot, line):
        """ Update a gauss fit given the plot and the fit line
        """
        x = plot.get_xdata()
        y = plot.get_ydata()
        param = self.gf.fit(x, y)
        fit = self.gf.gaussian_1D(x, *param)
        line.set_ydata(fit)

    @QtCore.pyqtSlot(bool)
    def on_image_bt_gauss_u_toggled(self, state):
        if state:
            if self.image_u_plot is not None:
                self.image_u_fit = self.draw_gauss_fit(self.image_u_ax, self.image_u_plot[0])
                self.canvas_u.draw()
        else:
            # Remove plot
            if self.image_u_fit is not None:
                self.remove_plot_lines(self.image_u_ax, self.image_u_fit)
                self.image_u_fit = None
                self.canvas_u.draw()

    @QtCore.pyqtSlot(bool)
    def on_image_bt_gauss_d_toggled(self, state):
        if state:
            if self.image_d_plot is not None:
                self.image_d_fit = self.draw_gauss_fit(self.image_d_ax, self.image_d_plot[0])
                self.canvas_d.draw()
        else:
            # Remove plot
            if self.image_d_fit is not None:
                self.remove_plot_lines(self.image_d_ax, self.image_d_fit)
                self.image_d_fit = None
                self.canvas_d.draw()

    def compute_profiles(self, img):
        v = np.sum(img, axis=1) / img.shape[1]
        h = np.sum(img, axis=0) / img.shape[0]
        return (v, h)

    def check_mean(self, c1, c2, c3, c4):
        corners = np.array([c1, c2, c3, c4])
        return np.mean(corners[corners <= np.median(corners)])

    def compute_centroid(self, img):
        """ Compute a centroid from the image
        """
        # Transpose the image if needed
        #img = cv2.transpose(img)

        # Find background (minumum) of the image by taking the value at the four corners
        c1 = np.mean(img[0:10,0:10])  # Up left
        c2 = np.mean(img[0:10,-10:])  # Up right
        c3 = np.mean(img[-10:,0:10])  # Down left
        c4 = np.mean(img[-10:,-10:])  # Down right
        img_min = int(self.check_mean(c1, c2, c3, c4))

        # Find maximum value of the image
        img_max = int(np.max(img))
        self.debug("Centroid: Min = {0:d}, Max = {1:d}".format(img_min, img_max))

        # Check if we have at least some singal
        if np.abs(img_max - img_min) > 10:

            # Compute threshold
            th = int(0.33 * (img_max - img_min))
            self.debug("Centroid: threshold = {0:d}".format(th))

            # Threshold the image
            mask = cv2.inRange(img, th, int(np.max(img)))

            #mask = cv2.GaussianBlur(mask, (5,5),0)
            element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2,2))
            mask = cv2.erode(mask, element, iterations=1)
            mask = cv2.dilate(mask, element, iterations=1)

            # Find contours in the mask and inititalize the current
            # (x,y) of the ball
            cnts = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len(cnts) == 3:
                cnts = cnts[1]
            else:
                cnts = cnts[0]
            self.debug("Centroid: found {0:d} contours".format(len(cnts)))

            # Proceed only if at least one contour is found
            if len(cnts) > 0:
                # Get the contour with the largest area
                c = max(cnts, key=cv2.contourArea)

                # Fit ellipse
                #ellipse = cv2.fitEllipse(c)

                ## Gauss 2D fit
                # Params: baseline, maximum, mean_x, mean_y, sigma_x, sigma_y, theta
                x = np.arange(img.shape[1])
                y = np.arange(img.shape[0])
                params = self.gf.fit_2d(x, y, img)
                ellipse = (params[2], params[3], 2*np.sqrt(2)*params[4], 2*np.sqrt(2)*params[5])
                self.debug("Ellipse: {0!s}".format(ellipse))

                # Create a mask from the single contour
                mask = np.zeros(img.shape, dtype=np.uint8)
                cv2.drawContours(mask, [c], 0, 1, -1)

                # Take the moments to get the centroid (by using the masked image)
                moments = cv2.moments(img * mask)
                if moments['m00'] != 0:
                    centroid_x = (moments['m10']/moments['m00'])
                    centroid_y = (moments['m01']/moments['m00'])
                    return (centroid_x, centroid_y, ellipse)

        return None

    @QtCore.pyqtSlot(int)
    def on_image_l_select_currentIndexChanged(self, index):
        if self.dev is not None:
            a = self.image_l_select.currentText()
            if self.ev_id[a] is None:
                try:
                    self.ev_id[a] = self.dev.subscribe_event(a, PT.EventType.CHANGE_EVENT, self.event_callback)
                except PT.DevFailed as e:
                    self.error("Failed to subscribe to events from attribute '{0}' ({1!s})".format(a, e.args[0].desc))
                except Exception as e:
                    self.error("Exception while subscribing to events from attribute '{0}' ({1!s})".format(a, e))
            else:
                self.debug("Event already subscribed")

    @QtCore.pyqtSlot(int)
    def on_image_r_select_currentIndexChanged(self, index):
        if self.dev is not None:
            a = self.image_r_select.currentText()
            if self.ev_id[a] is None:
                try:
                    self.ev_id[a] = self.dev.subscribe_event(a, PT.EventType.CHANGE_EVENT, self.event_callback)
                except PT.DevFailed as e:
                    self.error("Failed to subscribe to events from attribute '{0}' ({1!s})".format(a, e.args[0].desc))
                except Exception as e:
                    self.error("Exception while subscribing to events from attribute '{0}' ({1!s})".format(a, e))
            else:
                self.debug("Event already subscribed")

    @QtCore.pyqtSlot(int)
    def on_spec_img_currentIndexChanged(self, index):
        if self.dev is not None:
            a = self.spec_img.currentText()
            if self.ev_id[a] is None:
                try:
                    self.ev_id[a] = self.dev.subscribe_event(a, PT.EventType.CHANGE_EVENT, self.event_callback)
                except PT.DevFailed as e:
                    self.error("Failed to subscribe to events from attribute '{0}' ({1!s})".format(a, e.args[0].desc))
                except Exception as e:
                    self.error("Exception while subscribing to events from attribute '{0}' ({1!s})".format(a, e))
            else:
                self.debug("Event already subscribed")

    @QtCore.pyqtSlot(bool)
    def on_ac_save_triggered(self, checked):
        """ Save image
        """
        self.debug("Save Image")

    @QtCore.pyqtSlot(bool)
    def on_ac_setref_triggered(self, checked):
        """ Open set reference panel
        """
        if self.setref_panel is None:
            self.setref_panel = ReferencePanel(self, self.scaling)
            self.setref_panel.show()

    @QtCore.pyqtSlot(bool)
    def on_ac_save_db_triggered(self, checked):
        """ Save references to database
        """
        prop = {}
        if self.simulation:
            dev_name = "simulator"
        else:
            dev_name = self.dev.name()

        for k, v in self.references.items():
            if v is not None:
                prop[dev_name + ":" + k] = "x={0:.2f}:y={1:.2f}:h={2:.2f}:v={3:.2f}".format(v['x'], v['y'], v['h'], v['v'])
        try:
            if self.simulation:
                for k, v in prop.items():
                    print("Setting property '{0}' to '{1}'".format(k, v))
            else:
                self.db.put_property("LaserCamera", prop)
        except PT.DevFailed as e:
            QtWidgets.QMessageBox.critical(self, "Failed to save references", "Error: {0!s}".format(e.args[0].desc))

    @QtCore.pyqtSlot(bool)
    def on_ac_setup_triggered(self, checked):
        """ Configure camera
        """
        try:
            dlg = CameraSetup(self.dev, self.scaling, self)
        except RuntimeError:
            # No camera
            QtWidgets.QMessageBox.critical(self, "No camera", "Cannot find any camera available. Cannot open configuration window")
            return
        ret = dlg.exec_()
        if ret:
            # We may have a new camera
            # TODO: update camera
            pass
        else:
            # We need to restore previous camera settings
            if self.dev is not None:
                # TODO: restore
                pass

    @QtCore.pyqtSlot(bool)
    def on_ac_exit_triggered(self, checked):
        """ Close application
        """
        self.close()

    @QtCore.pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, event):
        self.debug("Closing application")
        reply = QtWidgets.QMessageBox.question(self, 'Message', "Are you sure to quit?", QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.close_camera()
            event.accept()
        else:
            event.ignore()

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, event):
        """ Handle the resize event of the window. """
        if event.size().isValid() and event.oldSize().isValid():
            w = event.size().width()
            h = event.size().height()
            dw = w - event.oldSize().width()
            dh = h - event.oldSize().height()

            self.debug("Resized window to ({:d}, {:d})".format(w, h))

            sz = self.tabs.size()
            self.tabs.resize(sz.width() + dw, sz.height() + dh)

            sz = self.image_l.size()
            self.image_l.resize(sz.width() + dw/2, sz.height() + dh)

            sz = self.image_r.size()
            self.image_r.resize(sz.width() + dw/2, sz.height() + dh)
            ps = self.image_r.pos()
            self.image_r.move(QtCore.QPoint(ps.x() + dw/2, ps.y()))

            sz = self.image_u.size()
            self.image_u.resize(sz.width() + dw, sz.height() + dh/2)

            sz = self.image_d.size()
            self.image_d.resize(sz.width() + dw, sz.height() + dh/2)
            ps = self.image_d.pos()
            self.image_d.move(QtCore.QPoint(ps.x(), ps.y() + dh/2))

        else:
            QtWidgets.QMainWindow.resizeEvent(self, event)

    def debug(self, message):
        if self.debug_enabled:
            print("[D]", message)

    def error(self, message):
        print("[E]", message)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    if app.primaryScreen().physicalDotsPerInch() > 120:
        app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True) # Enable HiDpi
    debug = False
    simulation = False
    if len(sys.argv):
        if "--debug" in sys.argv:
            debug = True
        if "--simulation" in sys.argv:
            simulation = True
    ui = LaserCamera(debug=debug, simulation=simulation)
    ui.show()
    ret = app.exec_()
    sys.exit(ret)