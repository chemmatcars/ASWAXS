from os import path
from pydm import Display
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication
from PyQt5.QtCore import pyqtSignal
import threading

from bluesky_kafka import RemoteDispatcher
from kafka import KafkaConsumer

class ScanPlotter(Display):
    scan_started = pyqtSignal(dict)
    event_received = pyqtSignal(dict)
    scan_stopped = pyqtSignal(dict)

    def __init__(self, parent=None, args=None, macros=None):
        super(ScanPlotter, self).__init__(parent=parent, args=args, macros=None)
        self.kafka_dispatcher_thread = threading.Thread(target=self.start_kafka_dispatcher)
        self.kafka_dispatcher_thread.daemon = True
        self.kafka_dispatcher_thread.start()
        self.init_signals()


    def ui_filename(self):
        return 'ui/ScanPlotter.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def init_signals(self):
        self.scan_started.connect(self.scan_start)
        self.event_received.connect(self.event_receipt)
        self.scan_stopped.connect(self.scan_stop)

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
        print(f'start: {doc}')

    def event_receipt(self, doc):
        print(f'event: {doc}')

    def scan_stop(self, doc):
        print(f'stop: {doc}')










