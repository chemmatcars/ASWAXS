from os import path
from pydm import Display
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication
import pyqtgraph as pg
from epics import Motor
import numpy as np


class ScanPlotter(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(ScanPlotter, self).__init__(parent=parent, args=args, macros=None)


    def ui_filename(self):
        return 'ui/ScanPlotter.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())








