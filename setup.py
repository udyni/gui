#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 17 22:18:29 2020

@author: Michele Devetta
"""

modules = {
        'ArchivingViewer': ['archivingviewer.py', 'Ui_archivingviewer.py'],
        'Compressor': ['compressor.py', 'Ui_compressor.py'],
        'CryostarGUI': ['cryostar.py', 'Ui_cryostar.py'],
        'DryVacGUI': ['dryvac.py', 'Ui_dryvac.py'],
        'Icons': ['__init__.py', 'icons_rc.py'],
        'LaserCamera': ['camerasetup.py', 'reference.py', 'lasercamera.py', 'Ui_lasercamera.py', 'Ui_camerasetup.py', 'Ui_reference.py'],
        'PyQTango': ['AttributeTree.py', 'CommonTree.py', 'DeviceTree.py', '__init__.py', 'PyQTango_rc.py', 'TangoUtil.py', 'QAttribute.py', 'QCommandExecuter.py', 'QStatusLed.py'],
        'SpectrumViewer': ['spectrumviewer.py', 'Ui_spectrumviewer_setscale.py', 'Ui_spectrumviewer.py'],
        'UdyniBrowser': ['browserconfig.xml', 'udynibrowser.py', 'Ui_udynibrowser.py']
}

GUI_UPDATER = "./gui_updater"
DESTINATION = "/var/data/tango/bin/gui"


def clean_dir(path):
    for el in os.listdir(path):
        fullpath = os.path.join(path, el)
        if os.path.isfile(fullpath):
            print("Removing", fullpath)
            os.remove(fullpath)


if __name__ == "__main__":
    import os
    import shutil
    import stat

    if not os.path.exists(GUI_UPDATER):
        print("This script should be executed inside the main folder of the GUI git tree")
        exit(-1)

    if not os.path.exists(DESTINATION):
        print("This script should be executed on the main Udyni server to install GUIs")
        exit(-1)

    # Exec gui_updater
    os.system(GUI_UPDATER)

    # Copy files
    for gui, files in modules.items():
        if len(files) > 0:
            gui_path = os.path.join(DESTINATION, gui)
            if os.path.exists(gui_path):
                clean_dir(gui_path)
            else:
                os.mkdir(gui_path)

            for f in files:
                print("Copying", f, "to", gui_path)
                shutil.copy(os.path.join(".", gui, f), gui_path)
                os.chmod(os.path.join(gui_path, f), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
