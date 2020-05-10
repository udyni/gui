# -*- coding: utf-8 -*-
"""
@author: Michele Devetta <michele.devetta@cnr.it>
"""

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from .CommonTree import TreeItem, DeviceItem, AttributeItem
import PyTango as PT
from .DeviceTree import DeviceTreeModel
from .TangoUtil import getAllLiveAttributes

class AttributeTreeModel(DeviceTreeModel):

    def __init__(self, attr_list, label="", parent=None):
        # Parent constructor
        QtCore.QAbstractItemModel.__init__(self, parent)
        self.rootItem = TreeItem(label)

        attr_dict = {}
        for d in attr_list:
            # Split device names
            (sys, sub, dev, attr) = d['attribute'].split("/")

            if sys in attr_dict:
                if sub in attr_dict[sys]:
                    if dev in attr_dict[sys][sub]:
                        if attr in attr_dict[sys][sub][dev]:
                            # Duplicate attribute
                            print("Skipping duplicate attribute {0}".format(d['attribute']))
                        else:
                            attr_dict[sys][sub][dev][attr] = d
                    else:
                        attr_dict[sys][sub][dev] = {}
                        attr_dict[sys][sub][dev][attr] = d
                else:
                    attr_dict[sys][sub] = {}
                    attr_dict[sys][sub][dev] = {}
                    attr_dict[sys][sub][dev][attr] = d
            else:
                attr_dict[sys] = {}
                attr_dict[sys][sub] = {}
                attr_dict[sys][sub][dev] = {}
                attr_dict[sys][sub][dev][attr] = d

        # Now we have a list of devices, we can populate the tree
        sys = list(attr_dict.keys())
        sys.sort()

        for k1 in sys:
            # Create sys obj
            sysobj = TreeItem(k1, self.rootItem)

            # Get subsystems keys
            subsys = list(attr_dict[k1].keys())
            subsys.sort()
            for k2 in subsys:
                # Create sub-sys obj
                subobj = TreeItem(k2, sysobj)

                # Scan list of devices
                devices = list(attr_dict[k1][k2].keys())
                devices.sort()
                for d in devices:
                    devobj = DeviceItem(d, {}, subobj)

                    # Scan list of attributes
                    attributes = list(attr_dict[k1][k2][d].keys())
                    attributes.sort()
                    for a in attributes:
                        devobj.appendChild(AttributeItem(a, attr_dict[k1][k2][d][a], devobj))

                    # Append child to parent
                    subobj.appendChild(devobj)

                # Add child to parent
                sysobj.appendChild(subobj)

            # Add child to parent
            self.rootItem.appendChild(sysobj)

    def data(self, index, role):
        if not index.isValid():
            return None

        if role == QtCore.Qt.DecorationRole:
            item = index.internalPointer()
            if type(item) == AttributeItem:
                if item.getDataFormat() == PT.AttrDataFormat.SCALAR:
                    return QtGui.QIcon(QtGui.QPixmap(":/icons/images/scalar.svg"));
                elif item.getDataFormat() == PT.AttrDataFormat.SPECTRUM:
                    return QtGui.QIcon(QtGui.QPixmap(":/icons/images/spectrum.png"));
                elif item.getDataFormat() == PT.AttrDataFormat.SPECTRUM:
                    return QtGui.QIcon(QtGui.QPixmap(":/icons/images/image.png"));
                elif item.getDataFormat() == PT.AttrDataFormat.FMT_UNKNOWN:
                    return QtGui.QIcon(QtGui.QPixmap(":/icons/images/genattr.png"));

        return super().data(index, role)


class QBaseAttributeTree(QtWidgets.QTreeView):
    def __init__(self, attr_list, resize=False, label="", parent=None):
        """ Constructor
        """
        # Parent constructor
        QtWidgets.QTreeView.__init__(self, parent)

        # Model
        self.model = AttributeTreeModel(attr_list, label=label, parent=self)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)

        # Initialize model
        self.setModel(self.model)

        # Auto-resize
        if resize and parent is not None:
            self.resize(parent.size())

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


class QAttributeTree(QBaseAttributeTree):

    def __init__(self, dbhost=None, port=10000, resize=False, label="", parent=None):
        """ Constructor
        """
        # Get attribute list)
        attr_list = getAllLiveAttributes()

        # Common parent constructor
        QBaseAttributeTree.__init__(self, attr_list, resize=resize, label=label, parent=parent)


class QArchivedAttributeTree(QBaseAttributeTree):

    def __init__(self, extractor, resize=False, label="", parent=None):
        """ Constructor
        """
        # Get attribute list
        attrs = extractor.GetAttNameAll()
        attr_list = []
        for a in attrs:
            try:
                ap = PT.AttributeProxy(a)
                conf = ap.get_config()
                attr_list.append({'attribute': a, 'data_format': conf.data_format, 'data_type': conf.data_type})
            except PT.DevFailed:
                attr_list.append({'attribute': a})

        # Common parent constructor
        QBaseAttributeTree.__init__(self, attr_list, resize=resize, label=label, parent=parent)
