# -*- coding: utf-8 -*-
"""
@author: Michele Devetta <michele.devetta@cnr.it>
"""

import PyTango as PT
import concurrent.futures


def getAllRegisteredDevices(dbhost=None, port=10000):
    """ Get all registered devices
        For each device return a dict with ('device': <Device>, 'server': <Server>, 'class': <Class>)
    """
    if dbhost is not None:
        db = PT.Database(dbhost, port)
    else:
        db = PT.Database()

    # Scan all registered servers
    servers = db.get_server_list()

    dev = []
    for s in servers:
        # Scan classes registered in each server
        devices = db.get_device_class_list(s)
        devices = zip(*[devices[i::2] for i in range(2)])

        for d in devices:
            dev.append( {'device': d[0], 'server': s, 'class': d[1]} )
    return dev


def __check_alive(dev):
    try:
        d = PT.DeviceProxy(dev['device'])
        d.ping()
        dev['alive'] = True
        return dev
    except PT.DevFailed:
        dev['alive'] = False
        return dev


def checkDevicesAreLive(dev_list):
    """ Check if the devices specified in the list of dict are live. Add an alive field to the dicts.
    """
    out = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
        # Start the load operations and mark each future with its URL
        future_to_devs = [executor.submit(__check_alive, d) for d in dev_list]
        for future in concurrent.futures.as_completed(future_to_devs):
            try:
                dev = future.result()
                out.append(dev)
            except Exception:
                # Skip failed device
                pass
    return out


def getAllLiveDevices(dbhost=None, port=10000):
    """ Get all live devices
        For each device return a tuple with (Device, Server, Class)
    """
    devices = getAllRegisteredDevices(dbhost, port)
    devices = checkDevicesAreLive(devices)
    alive = []
    for d in devices:
        if d['alive']:
            del d['alive']
            alive.append(d)
    return alive


def getAllLiveAttributes(dbhost=None, port=10000):
    """ Get all attributes from live devices
    """
    live_dev = getAllLiveDevices(dbhost, port)

    attr_list = []
    for d in live_dev:
        try:
            dev = PT.DeviceProxy(d['device'])
            attrs = dev.get_attribute_list()
            for a in attrs:
                conf = dev.get_attribute_config(a)
                attr_list.append({'attribute': d['device'] + "/" + a, 'data_format': conf.data_format, 'data_type': conf.data_type})
        except PT.DevFailed:
            pass
    return attr_list


def getAllLiveDevicesByClass(class_list, dbhost=None, port=10000):
    """ Get all live devices for the classes given in class_list
    """
    if dbhost is not None:
        db = PT.Database(dbhost, port)
    else:
        db = PT.Database()

    devs = []
    for cl in class_list:
        datum = db.get_device_exported_for_class(cl)
        for d in datum.value_string:
            devs.append({'device': d})

    return checkDevicesAreLive(devs)

