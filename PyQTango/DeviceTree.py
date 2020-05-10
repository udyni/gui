# -*- coding: utf-8 -*-
"""
@author: Michele Devetta <michele.devetta@cnr.it>
"""

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from .CommonTree import TreeItem, DeviceItem, ServerItem
import PyTango as PT
from .TangoUtil import getAllRegisteredDevices


class BaseDeviceTreeModel(QtCore.QAbstractItemModel):
    """ Base tree model for devices
    """

    def __init__(self, dev_list, label="", parent=None):
        # Base constructor
        QtCore.QAbstractItemModel.__init__(self, parent)
        self.rootItem = TreeItem(label)
        self.setupTree(dev_list)

    def setupTree(self, dev_list):
        pass

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return None

        if role == QtCore.Qt.DecorationRole:
            if type(index.internalPointer()) == DeviceItem:
                return QtGui.QIcon(QtGui.QPixmap(":/icons/images/gear.png"));

        elif role == QtCore.Qt.DisplayRole:
            item = index.internalPointer()
            return item.getName()

        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        if type(index.internalPointer()) == TreeItem:
            return QtCore.Qt.ItemIsEnabled
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.rootItem.getName()
        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
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

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()


class DeviceTreeModel(BaseDeviceTreeModel):

    def setupTree(self, dev_list):
        dev_dict = {}
        for d in dev_list:
            # Split device names
            (sys, sub, dev) = d['device'].split("/")

            if sys in dev_dict:
                if sub in dev_dict[sys]:
                    if dev in dev_dict[sys][sub]:
                        # Duplicate device
                        print("Skipping duplicate device {0}".format(d['device']))
                    else:
                        dev_dict[sys][sub][dev] = d
                else:
                    dev_dict[sys][sub] = {}
                    dev_dict[sys][sub][dev] = d
            else:
                dev_dict[sys] = {}
                dev_dict[sys][sub] = {}
                dev_dict[sys][sub][dev] = d

        # Now we have a list of devices, we can populate the tree
        sys = list(dev_dict.keys())
        sys.sort()

        for k1 in sys:
            # Create sys obj
            sysobj = TreeItem(k1, self.rootItem)

            # Get subsystems keys
            subsys = list(dev_dict[k1].keys())
            subsys.sort()
            for k2 in subsys:
                # Create sub-sys obj
                subobj = TreeItem(k2, sysobj)

                # Scan list of devices
                devices = list(dev_dict[k1][k2].keys())
                devices.sort()
                for d in devices:
                    subobj.appendChild(DeviceItem(d, dev_dict[k1][k2][d], subobj))

                # Add child to parent
                sysobj.appendChild(subobj)

            # Add child to parent
            self.rootItem.appendChild(sysobj)


class DeviceByServerTreeModel(BaseDeviceTreeModel):

    def setupTree(self, dev_list):
        srv_dict = {}
        for d in dev_list:
            # Split server instance
            (srv, inst) = d['server'].split("/")
            cls = d['class']
            dev = d['device']

            if srv in srv_dict:
                if inst in srv_dict[srv]:
                    if cls in srv_dict[srv][inst]:
                        if dev in srv_dict[srv][inst][cls]:
                            # Duplicate device
                            print("Skipping duplicate device {0}".format(dev))
                        else:
                            srv_dict[srv][inst][cls][dev] = d
                    else:
                        srv_dict[srv][inst][cls] = {}
                        srv_dict[srv][inst][cls][dev] = d
                else:
                    srv_dict[srv][inst] = {}
                    srv_dict[srv][inst][cls] = {}
                    srv_dict[srv][inst][cls][dev] = d
            else:
                srv_dict[srv] = {}
                srv_dict[srv][inst] = {}
                srv_dict[srv][inst][cls] = {}
                srv_dict[srv][inst][cls][dev] = d

        # Now we have a list of devices, we can populate the tree
        srv = list(srv_dict.keys())
        srv.sort()

        for k1 in srv:
            # Create srv obj
            srvobj = TreeItem(k1, self.rootItem)

            inst = list(srv_dict[k1].keys())
            inst.sort()
            for k2 in inst:
                # Create inst obj
                instobj = ServerItem(k2, "{0}/{1}".format(k1, k2), srvobj)

                cls = list(srv_dict[k1][k2].keys())
                cls.sort()
                for k3 in cls:
                    # Skip DServer in server view
                    if k3 == 'DServer':
                        continue
                    # Create cls obj
                    clsobj = TreeItem(k3, instobj)
                    # Scan list of devices
                    devices = list(srv_dict[k1][k2][k3].keys())
                    devices.sort()
                    for d in devices:
                        clsobj.appendChild(DeviceItem(d, srv_dict[k1][k2][k3][d], clsobj))

                    # Add child to parent
                    instobj.appendChild(clsobj)

                # Add child to parent
                srvobj.appendChild(instobj)

            # Add child to parent
            self.rootItem.appendChild(srvobj)


class DeviceByClassTreeModel(BaseDeviceTreeModel):

    def setupTree(self, dev_list):
        cls_dict = {}
        for d in dev_list:
            # Split server instance
            cls = d['class']
            dev = d['device']

            if cls in cls_dict:
                if dev in cls_dict:
                    # Duplicate device
                    print("Skipping duplicate device {0}".format(dev))
                else:
                    cls_dict[cls][dev] = d
            else:
                cls_dict[cls] = {}
                cls_dict[cls][dev] = d

        # Now we have a list of devices, we can populate the tree
        cls = list(cls_dict.keys())
        cls.sort()

        for k1 in cls:
            # Create cls obj
            clsobj = TreeItem(k1, self.rootItem)
            clsobj.appendChild(TreeItem("Properties", clsobj))
            devobj = TreeItem("Devices", clsobj)

            devices = list(cls_dict[k1].keys())
            devices.sort()
            for d in devices:
                devobj.appendChild(DeviceItem(d, cls_dict[k1][d], devobj))

            clsobj.appendChild(devobj)
            self.rootItem.appendChild(clsobj)


class QDeviceTree(QtWidgets.QTreeView):

    ByDevice = 0
    ByServer = 1
    ByClass  = 2

    def __init__(self, dbhost=None, port=10000, resize=False, label="", structure=0, parent=None, dev_list=None):
        """ Constructor
        """
        # Parent constructor
        QtWidgets.QTreeView.__init__(self, parent)

        # Auto-resize
        if resize and parent is not None:
            self.resize(parent.size())

        # Connect to Tango database
        if dbhost is None:
            self.db = PT.Database()

        else:
            self.db = PT.Database(dbhost, port)

        # Get device list
        if dev_list is None:
            dev_list = getAllRegisteredDevices()

        # Model
        if structure == self.ByServer:
            self.model = DeviceByServerTreeModel(dev_list, label=label, parent=self)
        elif structure == self.ByClass:
            self.model = DeviceByClassTreeModel(dev_list, label=label, parent=self)
        else:
            self.model = DeviceTreeModel(dev_list, label=label, parent=self)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)

        # Initialize model
        self.setModel(self.model)

        style = """
QTreeView::branch:has-siblings:!adjoins-item {
    border-image: url(:/icons/images/vline.png) 0;
}

QTreeView::branch:has-siblings:adjoins-item {
    border-image: url(:/icons/images/branch-more.png) 0;
}

QTreeView::branch:!has-children:!has-siblings:adjoins-item {
    border-image: url(:/icons/images/branch-end.png) 0;
}

QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {
    border-image: none;
    image: url(:/icons/images/branch-closed.png);
}

QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings  {
    border-image: none;
    image: url(:/icons/images/branch-open.png);
}
"""
#        QtWidgets.qApp.setStyleSheet(style)
        self.setStyleSheet(style)
