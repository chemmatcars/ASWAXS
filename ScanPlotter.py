from os import path, remove

from event_model import SCHEMA_NAMES
from pydm import Display
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication, QWidget
from PyQt5.QtCore import pyqtSignal
from PyQt5 import uic
import threading
import copy
import numpy as np
import sys
import pathlib
import databroker
from apstools.callbacks import SpecWriterCallback


from bluesky_kafka import RemoteDispatcher

class ScanPlotter(QWidget):
    scan_started = pyqtSignal(dict)
    event_received = pyqtSignal(dict)
    scan_stopped = pyqtSignal(dict)

    def __init__(self, parent=None):
        super(ScanPlotter, self).__init__(parent=parent)
        self.ui = uic.loadUi('ui/ScanPlotter.ui', self)
        self.init_signals()
        self.kafka_dispatcher_thread = threading.Thread(target=self.start_kafka_dispatcher)
        self.kafka_dispatcher_thread.daemon = True
        self.kafka_dispatcher_thread.start()
        self.DB_XAxis = 'None'
        self.DB_norm = 'None'
        self.DB_YAxis = []
        self.live_started = False
        self.liveData={}
        self.live_XAxis = 'None'
        self.live_norm = 'None'
        self.live_YAxis = []
        self.dbCatalog = databroker.catalog['CATALOG_NAME']
        self.expDir = path.abspath('./Data/')
        # self.specWriter = SpecWriterCallback()
        self.startExperiment(expDir=self.expDir)



    def init_signals(self):
        self.ui.newExperimentPushButton.clicked.connect(lambda x: self.startExperiment(expDir = None))
        self.ui.loadExperimentPushButton.clicked.connect(lambda x: self.loadExperiment(expDir = None))
        self.ui.DB_scanListWidget.itemSelectionChanged.connect(self.DBItemSelectionChanged)
        self.ui.DB_XAxisComboBox.currentTextChanged.connect(self.DB_XAxisChanged)
        self.ui.DB_normComboBox.currentTextChanged.connect(self.DB_normChanged)
        self.ui.DB_YAxisListWidget.itemSelectionChanged.connect(self.DB_YAxisChanged)

        self.scan_started.connect(self.scan_start)
        self.event_received.connect(self.event_receipt)
        self.scan_stopped.connect(self.scan_stop)
        self.ui.live_XAxisComboBox.currentTextChanged.connect(self.live_XAxisChanged)
        self.ui.live_normComboBox.currentTextChanged.connect(self.live_normChanged)
        self.ui.live_YAxisListWidget.itemSelectionChanged.connect(self.live_YAxisChanged)

    def startExperiment(self, expDir = None):
        if expDir is None:
            self.expDir = QFileDialog.getExistingDirectory(self, 'Start new experimental directory')
            if path.exists(path.join(self.expDir, 'expRecord.txt')):
                QMessageBox.warning(self,'Directory Error', 'This is an exiting experimental directory. Create a new experimental '
                                                            'directory to start a new experiments')
                self.startExperiment(expDir = None)
            else:
                self.expfh = open(path.join(self.expDir, 'expRecord.txt'),'w')
                self.experimentFolderLineEdit.setText(f'{self.expDir}')
                self.scan_num = 0
        else:
            self.expDir = expDir
            self.experimentFolderLineEdit.setText(self.expDir)
            self.expfh = open(path.join(self.expDir, 'expRecord.txt'), 'w')
            self.scan_num = 0
        # specFile=path.join(self.expDir, 'expRecord.spec')
        # if path.exists(specFile):
        #     remove(specFile)
        # self.specWriter.newfile(filename = specFile, scan_id=True)

    def loadExperiment(self, expDir = None):
        if expDir is None:
            self.expDir = QFileDialog.getExistingDirectory(self, 'Start new experimental directory')
        else:
            self.expDir = expDir
        self.ui.DB_scanListWidget.itemSelectionChanged.disconnect()
        if path.exists(path.join(self.expDir, 'expRecord.txt')):
            with open(path.join(self.expDir, 'expRecord.txt'), 'r') as fh:
                lines = fh.readlines()
                if len(lines)>0:
                    self.DB_scanListWidget.clear()
                    for line in lines:
                        self.DB_scanListWidget.addItem(line.strip())
                    self.scan_num = len(lines)
                else:
                    self.scan_num = 0
            self.ui.DB_scanListWidget.itemSelectionChanged.connect(self.DBItemSelectionChanged)
            self.expfh = open(path.join(self.expDir, 'expRecord.txt'), 'a')
            self.ui.experimentFolderLineEdit.setText(self.expDir)

        else:
            self.expDir = self.ui.experimentFolderLineEdit.text()
        # self.specWriter.usefile(filename=path.join(self.expDir, 'expRecord.spec'))


    def DBItemSelectionChanged(self):
        if len(self.ui.DB_scanListWidget.selectedItems())>0:
            self.ui.DB_XAxisComboBox.currentTextChanged.disconnect()
            self.ui.DB_normComboBox.currentTextChanged.disconnect()
            self.ui.DB_YAxisListWidget.itemSelectionChanged.disconnect()
            self.dbData = {}
            self.dbKeys = []
            items = self.ui.DB_scanListWidget.selectedItems()
            dbKey, uid = items[0].text().split(':')
            run = self.dbCatalog[uid.strip()]
            self.dbData[dbKey] = {'data': run.primary.read()}
            self.dbData[dbKey]['metadata'] = run.metadata
            colKeys = self.dbData[dbKey]['data'].keys()
            self.DBcolKeys = list(colKeys)
            self.ui.DB_XAxisComboBox.clear()
            self.ui.DB_normComboBox.clear()
            self.ui.DB_YAxisListWidget.clear()
            self.ui.DB_XAxisComboBox.addItems(self.DBcolKeys)
            self.ui.DB_normComboBox.addItems(self.DBcolKeys+['None'])
            self.ui.DB_YAxisListWidget.addItems(self.DBcolKeys)
            self.dbKeys.append(dbKey)
            for item  in items[1:]:
                dbKey, uid = item.text().split(':')
                run = self.dbCatalog[uid.strip()]
                data = run.primary.read()
                if data.keys() == colKeys:
                    self.dbData[dbKey]={'data':data}
                    self.dbData[dbKey]['metadata'] = run.metadata
                    self.dbKeys.append(dbKey)
                else:
                    QMessageBox.warning(self, 'Data Error', f'Data in {dbKey} is different from all other selected '
                                                            f'data and hence wont be selected and plotted')
            self.ui.DB_XAxisComboBox.currentTextChanged.connect(self.DB_XAxisChanged)
            self.ui.DB_normComboBox.currentTextChanged.connect(self.DB_normChanged)
            self.ui.DB_YAxisListWidget.itemSelectionChanged.connect(self.DB_YAxisChanged)

            if self.DB_XAxis == 'None' or self.DB_XAxis not in self.DBcolKeys:
                self.DB_XAxisComboBox.setCurrentIndex(0)
            else:
                self.DB_XAxisComboBox.setCurrentText(self.DB_XAxis)
            self.DB_XAxis = self.DB_XAxisComboBox.currentText()
            if self.DB_norm == 'None' or self.DB_norm not in self.DBcolKeys+['None']:
                self.DB_normComboBox.setCurrentText('None')
            else:
                self.DB_normComboBox.setCurrentText(self.DB_norm)
            self.DB_norm = self.DB_normComboBox.currentText()
            if self.DB_YAxis == [] or not set(self.DB_YAxis).issubset(set(self.DBcolKeys)):
                self.DB_YAxisListWidget.item(0).setSelected(True)
            else:
                for key in self.DB_YAxis:
                    for row, x in enumerate(self.DBcolKeys):
                        if x == key:
                            self.DB_YAxisListWidget.item(row).setSelected(True)
                            break
            self.DB_YAxis = [item.text() for item in self.DB_YAxisListWidget.selectedItems()]
            self.updateDBPlot()

    def updateDBPlot(self):
        try:
            self.DB_scanPlotWidget.remove_data(self.plot_keys)
        except:
            pass
        self.plot_keys = []
        for dataKey in self.dbKeys:
            for key in self.DB_YAxis:
                if self.DB_norm != 'None':
                    self.plot_keys.append(f'{dataKey}:{key}_normalized')
                    self.DB_scanPlotWidget.add_data(self.dbData[dataKey]['data'][self.DB_XAxis].values,
                                                      self.dbData[dataKey]['data'][key].values /
                                                      self.dbData[dataKey]['data'][self.DB_norm].values,
                                                      name = self.plot_keys[-1])
                else:
                    self.plot_keys.append(f'{dataKey}:{key}')
                    self.DB_scanPlotWidget.add_data(self.dbData[dataKey]['data'][self.DB_XAxis],
                                                      self.dbData[dataKey]['data'][key], name = self.plot_keys[-1])
        self.DB_scanPlotWidget.Plot(self.plot_keys)


    def DB_XAxisChanged(self):
        self.DB_XAxis = self.DB_XAxisComboBox.currentText()
        self.updateDBPlot()

    def DB_normChanged(self):
        self.DB_norm = self.DB_normComboBox.currentText()
        self.updateDBPlot()

    def DB_YAxisChanged(self):
        self.DB_YAxis = [item.text()  for item in self.DB_YAxisListWidget.selectedItems()]
        self.updateDBPlot()



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
        elif name == 'stop':
            self.scan_stopped.emit(doc)
        else:
            pass#print(f'{name}: {doc}')
        # self.specWriter.receiver(name, doc)

    def scan_start(self, doc):
        self.liveData = {'time':[]}
        self.live_started = True
        self.scan_uid = doc['uid']
        self.scan_num += 1
        # print(f'S {self.scan_num}: {self.scan_uid}')

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
                plot_keys.append(f'{key}')
                self.live_scanPlotWidget.add_data(self.liveData[self.live_XAxis],
                                                  self.liveData[key], name = plot_keys[-1])
        self.live_scanPlotWidget.Plot(plot_keys)

    def scan_stop(self, doc):
        self.expfh.write(f'S {self.scan_num}: {self.scan_uid}\n')
        self.expfh.flush()
        self.DB_scanListWidget.addItem(f'S {self.scan_num}: {self.scan_uid}')




if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = ScanPlotter()
    w.show()
    sys.exit(app.exec_())






