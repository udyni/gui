# -*- coding: utf-8 -*-
"""
@author: Michele Devetta <michele.devetta@cnr.it>
"""

import PyTango as PT

class TreeItem(object):
    def __init__(self, name, parent=None):
        self.parentItem = parent
        self.name = name
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 1

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

    def getName(self):
        return self.name


class DeviceItem(TreeItem):
    def __init__(self, name, device, parent=None):
        # Parent constructor
        TreeItem.__init__(self, name, parent)
        self.device = device

    def getDevice(self):
        return self.device


class AttributeItem(TreeItem):
    def __init__(self, name, attribute, parent=None):
        # Parent constructor
        TreeItem.__init__(self, name, parent)
        self.attribute = attribute
        #self.info = self.attribute.get_config()

    def getAttribute(self):
        return self.attribute

    def getDataFormat(self):
        if 'data_format' in self.attribute:
            return self.attribute['data_format']
        else:
            return  PT.AttrDataFormat.FMT_UNKNOWN


class ServerItem(TreeItem):
    def __init__(self, name, instance, parent=None):
        # Parent constructor
        TreeItem.__init__(self, name, parent)
        self.instance = instance

    def getInstance(self):
        return self.instance
