from os import path
from pydm import Display
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication
import pyqtgraph as pg
from epics import Motor
import numpy as np


class ASWAXS_Collector(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(ASWAXS_Collector, self).__init__(parent=parent, args=args, macros=None)
        self.ui.PyDMTabWidget.setCurrentIndex(1)


    def ui_filename(self):
        return 'ui/ASWAXS_Collector.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())








