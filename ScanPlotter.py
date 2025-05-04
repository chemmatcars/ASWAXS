from os import path
from pydm import Display
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication
from PyQt5.QtCore import pyqtSignal
import threading
import copy
import numpy as np

from bluesky_kafka import RemoteDispatcher
from kafka import KafkaConsumer

class ScanPlotter(Display):
    scan_started = pyqtSignal(dict)
    event_received = pyqtSignal(dict)
    scan_stopped = pyqtSignal(dict)

    def __init__(self, parent=None, args=None, macros=None):
        super(ScanPlotter, self).__init__(parent=parent, args=args, macros=None)
        self.init_signals()
        self.kafka_dispatcher_thread = threading.Thread(target=self.start_kafka_dispatcher)
        self.kafka_dispatcher_thread.daemon = True
        self.kafka_dispatcher_thread.start()
        self.live_started = False
        self.liveData={}
        self.live_XAxis = 'None'
        self.live_norm = 'None'
        self.live_YAxis = []


    def ui_filename(self):
        return 'ui/ScanPlotter.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def init_signals(self):
        self.scan_started.connect(self.scan_start)
        self.event_received.connect(self.event_receipt)
        self.scan_stopped.connect(self.scan_stop)
        self.ui.live_XAxisComboBox.currentTextChanged.connect(self.live_XAxisChanged)
        self.ui.live_normComboBox.currentTextChanged.connect(self.live_normChanged)
        self.ui.live_YAxisListWidget.itemSelectionChanged.connect(self.live_YAxisChanged)

    def start_kafka_dispatcher(self):
        self.kafka_dispatcher = RemoteDispatcher(['bluesky_aswaxs'],
                                                 '164.54.169.92:9092',
                                                 'qt-plot-widget',
                                                 {'auto.offset.reset':'latest'})
        self.kafka_dispatcher.subscribe(self.monitor_kafka_message)
        self.kafka_dispatcher.start()

    def monitor_kafka_message(self, name, doc):
        if name == 'start':
            self.scan_started.emit(doc)
        elif name == 'event':
            self.event_received.emit(doc)
        else:
            self.scan_stopped.emit(doc)

    def scan_start(self, doc):
        self.liveData = {'time':[]}
        self.live_started = True
        print('scan started')

    def event_receipt(self, doc):
        self.liveData['time'].append(doc['time'])
        for key, value in doc['data'].items():
            try:
                self.liveData[key].append(value)
            except:
                self.liveData[key] = [value]
        if self.live_started:
            self.xKeys = list(self.liveData.keys())
            self.normKeys = self.xKeys + ['None']
            self.yKeys = copy.copy(self.xKeys)
            self.ui.live_XAxisComboBox.currentTextChanged.disconnect()
            self.ui.live_normComboBox.currentTextChanged.disconnect()
            self.ui.live_YAxisListWidget.itemSelectionChanged.disconnect()
            self.ui.live_XAxisComboBox.clear()
            self.ui.live_normComboBox.clear()
            self.ui.live_YAxisListWidget.clear()
            self.ui.live_XAxisComboBox.addItems(self.xKeys)
            self.ui.live_normComboBox.addItems(self.normKeys)
            self.ui.live_YAxisListWidget.addItems(self.yKeys)
            if self.live_XAxis == 'None' or self.live_XAxis not in self.xKeys:
                self.live_XAxisComboBox.setCurrentIndex(0)
            else:
                self.live_XAxisComboBox.setCurrentText(self.live_XAxis)
            self.live_XAxis = self.live_XAxisComboBox.currentText()
            if self.live_norm == 'None' or self.live_norm not in self.normKeys:
                self.live_normComboBox.setCurrentText('None')
            else:
                self.live_normComboBox.setCurrentText(self.live_norm)
            self.live_norm = self.live_normComboBox.currentText()
            if self.live_YAxis == [] or not set(self.live_YAxis).issubset(set(self.yKeys)):
                self.live_YAxisListWidget.item(0).setSelected(True)
            else:
                for key in self.live_YAxis:
                    for row, x in enumerate(self.yKeys):
                        if x == key:
                            self.live_YAxisListWidget.item(row).setSelected(True)
                            break
            self.live_YAxis = [item.text() for item in self.live_YAxisListWidget.selectedItems()]
            self.ui.live_XAxisComboBox.currentTextChanged.connect(self.live_XAxisChanged)
            self.ui.live_normComboBox.currentTextChanged.connect(self.live_normChanged)
            self.ui.live_YAxisListWidget.itemSelectionChanged.connect(self.live_YAxisChanged)
            self.live_started = False
        self.updateLivePlot()

    def live_XAxisChanged(self, text):
        self.live_XAxis = text
        self.updateLivePlot()

    def live_normChanged(self, text):
        self.live_norm = text
        self.updateLivePlot()

    def live_YAxisChanged(self):
        self.live_YAxis = []
        for item in self.live_YAxisListWidget.selectedItems():
            self.live_YAxis.append(item.text())

    def updateLivePlot(self):
        plot_keys = []
        for key in self.live_YAxis:
            if self.live_norm != 'None':
                plot_keys.append(f'{key}_normalized')
                self.live_scanPlotWidget.add_data(np.array(self.liveData[self.live_XAxis]),
                                                  np.array(self.liveData[key])/np.array(self.liveData[self.live_norm]), name = plot_keys[-1])
            else:
                plot_keys.append(key)
                self.live_scanPlotWidget.add_data(self.liveData[self.live_XAxis],
                                                  self.liveData[key], name = f'{key}')
        self.live_scanPlotWidget.Plot(plot_keys)

    def scan_stop(self, doc):
        pass










