#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""

Udyni Browser

Convenient interface to launch Python GUIs

Created on Tue May  9 17:27:24 2017

@author: Michele Devetta

Dependencies:
- PyQt5
- python-xlib
- ewmh to be installed through pip
- python-psutil

"""

import sys
import os
## Add import paths
sys.path.insert(1, os.path.join(sys.path[0], '../Icons'))

import re
import time
import psutil
import shlex
import subprocess
import xml.etree.ElementTree as ET
try:
    from ewmh import EWMH
    import Xlib
    has_ewmh = True
except ImportError as e:
    print("WARNING: failed load EWMH (Error was: {:})".format(e))
    has_ewmh = False

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from Ui_udynibrowser import Ui_UdyniBrowser


class TreeItem(object):
    """ General tree item class
    """
    def __init__(self, parent=None):
        """ Constructor
        """
        self._parent = parent
        self.children = []
        self.cols = 3

    def child(self, row):
        # Get a child
        return self.children[row]

    def childCount(self):
        # Return the number of children
        return len(self.children)

    def columnCount(self):
        # Only one column in categories
        return self.cols

    def parent(self):
        return self._parent

    def row(self):
        if self._parent:
            return self._parent.children.index(self)
        return 0

    # Probably to remove!
    def getEWMH(self):
        if self._parent is not None:
            return self._parent.getEWMH()
        else:
            return None


class ProcessTree(TreeItem):
    """
    Process tree root
    """
    def __init__(self, configuration, parent=None):
        """ Constructor
        Get the XML configuration as a string
        """
        # Parent constructor
        super().__init__(parent)

        # Parse configuration
        root = ET.fromstring(configuration)

        # Extract items
        for c in list(root):
            if c.tag == 'category':
                self.children.append(CategoryItem(c, self))
            elif c.tag == 'program':
                self.children.append(ProgramItem(c, self))
            else:
                # Unknown tag
                pass

        # Initialize interface to X server
        if has_ewmh:
            self.ewmh = EWMH()
        else:
            self.ewmh = None

    def getEWMH(self):
        return self.ewmh

    def data(self, column):
        sections = ['Program', 'PID', 'Status']
        if column < len(sections):
            return sections[column]
        return None

    def parent(self):
        return None

    def row(self):
        return 0


class CategoryItem(TreeItem):
    """
    Tree item that represent a category
    This type can have children
    """
    def __init__(self, data, parent=None):
        """ Constructor
        """
        # Parent constructor
        super().__init__(parent)

        # Catergory name
        self.name = data.get('name')

        # Catergory status
        if data.get('status').lower() == 'expanded':
            self.expanded = True
        else:
            self.expanded = False

        # Add childrens
        for c in list(data):
            if c.tag == 'category':
                self.children.append(CategoryItem(c, self))
            elif c.tag == 'program':
                self.children.append(ProgramItem(c, self))
            else:
                # Unknown tag
                pass

    def data(self, column):
        if column == 0:
            return self.name
        else:
            return None


class ProgramItem(TreeItem):
    """
    Tree item that represent a program
    This type cannot have children
    """
    def __init__(self, data, parent=None):
        """ Constructor
        """
        # Parent constructor
        super().__init__(parent)

        # Command line
        self.cmdline = shlex.split(data.get('executable'))
        if not os.path.exists(self.cmdline[0]):
            # Cannot find executable. Try to reinterpret path relative to the browser script
            newpath = os.path.dirname(os.path.realpath(__file__)) + os.path.sep + self.cmdline[0]
            if os.path.exists(newpath):
                self.cmdline[0] = newpath

        if self.cmdline[0].find("python") != -1:
            # Check python script
            if not os.path.exists(self.cmdline[1]):
                # Cannot find executable. Try to reinterpret path relative to the browser script
                newpath = os.path.dirname(os.path.realpath(__file__)) + os.path.sep + self.cmdline[1]
                newpath = os.path.abspath(newpath)
                if os.path.exists(newpath):
                    self.cmdline[1] = newpath

        self.name = data.text.strip()
        self.pid = None       # Generic PID (also for programs started externally)
        self.process = None   # Popen object, to avoid zombies
        self.status = "Not running"

    def checkRunning(self):
        """ Check if the process is running and update the list of open windows
        """
        pname = os.path.split(self.cmdline[0])[-1]
        for p in psutil.process_iter():
            # Skip system processes without a command line
            if not len(p.cmdline()):
                continue

            # If the PID match and the process is a zombie we should wait on it
            if p.pid == self.pid and p.status() == "zombie":
                if self.process is not None:
                    self.process.wait()
                    self.process = None
                    self.pid = None
                # We can go on searching for a new instance
                continue

            #if p.name() == pname:
            if str(p.cmdline()).find(pname) != -1:
                # Special case for python panels
                if pname == "python" or pname == "python3":

                    # We should check that the running script is the right one
                    if len(self.cmdline) < 2 or len(p.cmdline()) < 2:
                        continue

                    if os.path.split(self.cmdline[1])[-1] != os.path.split(p.cmdline()[1])[-1]:
                        # Not the right process
                        continue

                # Special case for Tango java utilities
                elif len(p.children()) > 0 and p.children()[0].name() == "java":
                    # We should use the java child process
                    p = p.children()[0]

                # Process found
                if self.pid is not None:
                    if p.pid != self.pid:
                        if not psutil.pid_exists(self.pid):
                            # Original process died. We can use this new one
                            self.pid = p.pid
                            self.process = None
                            self.status = "Running"
                            return

                        else:
                            # We may have found another instance of the same process
                            continue

                    else:
                        # We found the process. It's still up and running
                        self.status = "Running"
                        return

                else:
                    # Found a new instance
                    self.pid = p.pid
                    self.status = "Running"
                    return

        # If we arrived here then the process was not found
        self.pid = None
        self.status = "Not running"

    def isRunning(self):
        """ Return True if the PID is not None
        """
        if self.pid is not None:
            return True
        else:
            return False

    def setFocus(self):
        """ If the process is running put focus on its window, otherwise does nothing
        """
        if self.pid is not None and len(self.children) > 0:
            self.children[0].setFocus()

    def startProcess(self):
        """ If the process is not running, start it. Otherwise does nothing.
        """
        if self.pid is None:
            # Start process
            self.pid = -1 # Just to be sure that we cannot start the process twice
            try:
                self.process = subprocess.Popen(self.cmdline, start_new_session=True, stderr=subprocess.PIPE)
                time.sleep(0.5)
                self.process.poll()
                if self.process.returncode is not None:
                    # Process ended
                    if self.process.returncode < 0:
                        raise OSError("Process ended by signal {0:d}".fromat(self.process.returncode))
                    else:
                        msg = "\n".join([l.decode('utf-8') for l in self.process.stderr.readlines()]).strip()
                        raise OSError("Return code: {0:d}, Error: {1:s}".format(self.process.returncode, msg))

            except Exception as e:
                # Start failed
                QtWidgets.QMessageBox.critical(None, "Failed to start {0}".format(self.name), "{0!s}".format(e))
                self.pid = None
                return


            # Check if we started a java program
            c = psutil.Process(self.process.pid).children()
            if len(c) > 0 and c[0].name() == "java":
                self.pid = c[0].pid
            else:
                self.pid = self.process.pid

    def data(self, column):
        if column == 0:
            return self.name
        elif column == 1:
            return self.pid
        elif column == 2:
            return self.status
        else:
            return None

    def clearWindows(self):
        """ Remove all children windows
        """
        self.children = []

    def getWindowList(self):
        """ Return a list of windows
        """
        wlist = []
        if self.getEWMH() is not None:
            for w in self.getEWMH().getClientList():
                try:
                    if self.getEWMH().getWmPid(w) == self.pid:
                        wlist.append(w)
                except Xlib.error.BadWindow:
                    pass

        return wlist

    def appendWindow(self, w):
        """ Append a new window
        """
        self.children.append(WindowItem(w, self))


class WindowItem(TreeItem):
    """
    Tree item that represent a program window
    This type cannot have children
    """
    def __init__(self, window, parent=None):
        """ Constructor
        """
        # Parent constructor
        super().__init__(parent)

        # Window
        self.win = window

    def setFocus(self):
        """ If the process is running put focus on its window, otherwise does nothing
        """
        if self.getEWMH() is not None:
            self.getEWMH().setActiveWindow(self.win)
            self.getEWMH().display.flush()

    def data(self, column):
        if column == 0:
            try:
                return self.win.get_wm_name()
            except:
                return "Bad window"
        else:
            return None


class UdyniTreeModel(QtCore.QAbstractItemModel):
    """
    Program tree model
    """
    def __init__(self, conf_tree, parent=None):
        """ Constructor
        Get tree of categories and programs
        """
        # Parent constructor
        QtCore.QAbstractItemModel.__init__(self, parent)

        # Store tree
        self.tree = conf_tree

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return 3

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role == QtCore.Qt.DisplayRole:
            return item.data(index.column())

        elif role == QtCore.Qt.BackgroundRole:
            if type(item) == ProgramItem and item.isRunning():
                return QtGui.QColor(204, 229, 255)

        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        """ Header data
        """
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.tree.data(section)
        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.tree
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.tree:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.tree
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def expandChildren(self, node, view):
        # Traverse the entire tree and expand nodes
        for i in range(self.rowCount(node)):
            ind = self.index(i, 0, node)
            if type(ind.internalPointer()) == CategoryItem:
                if ind.internalPointer().expanded:
                    view.expand(ind)
                self.expandChildren(ind, view)

    def updateNode(self, index):
        """ Update windows in the model
        """
        obj = index.internalPointer()

        progs = 0
        windows = 0

        if type(obj) == ProgramItem:
            # Check if the process is running
            obj.checkRunning()

            # Remove all windows
            if self.hasChildren(index):
                    # Delete windows
                    self.beginRemoveRows(index, 0, self.rowCount(index)-1)
                    obj.clearWindows()
                    self.endRemoveRows()

            # If the process is still running re-add them all
            if obj.isRunning():
                progs += 1
                # Check windows
                wins = obj.getWindowList()
                windows += len(wins)
                if len(wins) > 0:
                    self.beginInsertRows(index, 0, len(wins)-1)
                    for w in wins:
                        obj.appendWindow(w)
                    self.endInsertRows()

        else:
            # Should be a category
            if self.hasChildren(index):
                for row in range(self.rowCount(index)):
                    (p, w) = self.updateNode(self.index(row, 0, index))
                    progs += p
                    windows += w

        return (progs, windows)


class BrowserDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):

        if index.isValid():
            obj = index.internalPointer()
            option = QtWidgets.QStyleOptionViewItem(option)

            if type(obj) == WindowItem:
                option.palette.setColor(QtGui.QPalette.Text, QtGui.QColor(QtCore.Qt.gray))

            elif type(obj) == ProgramItem:
                if index.column() == 0:
                    option.font.setBold(True)

        QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)


class UdyniBrowser(QtWidgets.QMainWindow, Ui_UdyniBrowser):
    """
    Main class
    """
    def __init__(self, parent=None):
        """
        Constructor
        """
        # Parent constructor
        QtWidgets.QMainWindow.__init__(self, parent)

        # Get scaling factor for HiDPI
        design_dpi = 95
        current_dpi = app.primaryScreen().physicalDotsPerInch()
        self.scaling = float(current_dpi) / float(design_dpi)
        if self.scaling > 1.8:
            self.scaling = 1.8
        elif self.scaling < 1.1:
            self.scaling = 1.0

        # Create GUI
        self.setupUi(self)
        self.inhibith_resize = True
        self.setup_fonts_and_scaling()
        self.inhibith_resize = False

        # Create category tree
        configfile = os.path.dirname(os.path.realpath(__file__)) + "/browserconfig.xml"
        with open(configfile) as f:
            data = f.read()
            f.close()
        self.tree = ProcessTree(data, self)

        # Create model
        self.model = UdyniTreeModel(self.tree, self)

        # Apply model to TreeView
        self.browser.setModel(self.model)
        self.model.expandChildren(QtCore.QModelIndex(), self.browser)
        sz = self.browser.size()
        self.browser.header().resizeSection(0, int(sz.width() * 0.5))
        self.browser.header().resizeSection(1, int(sz.width() * 0.1))
        self.browser.setItemDelegate(BrowserDelegate(self.browser))

        # Start timer
        self.timerId = self.startTimer(1000)

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

    def scale_widget(self, widget, scaling):
        sz = widget.size()
        ps = widget.pos()
        widget.resize(int(sz.width() * scaling), int(sz.height() * scaling))
        widget.move(QtCore.QPoint(int(ps.x() * scaling), int(ps.y() * scaling)))

    @QtCore.pyqtSlot(QtCore.QTimerEvent)
    def timerEvent(self, ev):
        """ Timer event. Trigger the update of the browser model
        """
        # Update model
        (p, w) = self.model.updateNode(self.browser.rootIndex())
        # Refresh view
        self.browser.clicked.emit(QtCore.QModelIndex())
        # Update statusbar
        self.statusbar.showMessage("{:d} programs running, for {:} total windows controlled".format(p, w), 1000)

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, event):
        """ Handle the resize event of the window. """
        if event.size().isValid() and event.oldSize().isValid():
            w = event.size().width()
            h = event.size().height()
            dw = w - event.oldSize().width()
            dh = h - event.oldSize().height()

            print("Resized window to ({:d}, {:d})".format(w, h))

            sz = self.browser.size()
            self.browser.resize(sz.width() + dw, sz.height() + dh)

            ps = self.closeButton.pos()
            self.closeButton.move(QtCore.QPoint(ps.x() + dw, ps.y() + dh))

        else:
            QtWidgets.QMainWindow.resizeEvent(self, event)

    @QtCore.pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, ev):
        """ Catch close event
        """
        self.killTimer(self.timerId)
        ev.accept()

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_browser_doubleClicked(self, index):
        """
        Slot to catch double clicks on the tree
        """
        if index.isValid():
            obj = index.internalPointer()
            if type(obj) == ProgramItem:
                if obj.isRunning():
                    obj.setFocus()
                else:
                    obj.startProcess()
            elif type(obj) == WindowItem:
                obj.setFocus()

    @QtCore.pyqtSlot()
    def on_closeButton_released(self):
        self.close()


if __name__ == '__main__':

    # Start main app
    app = QtWidgets.QApplication(sys.argv)

    w = UdyniBrowser()
    w.show()

    # Start event loop
    sys.exit(app.exec_())
