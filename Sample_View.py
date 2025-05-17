import os.path
from os import path
from pydm import Display
import cv2
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication, QWidget
from PyQt5 import uic
from PyQt5.QtGui import QCloseEvent
import pyqtgraph as pg
from epics import Motor, PV
import numpy as np
import paramiko
from pydm.widgets.frame import PyDMFrame
import time
import atexit
import socket
from tempfile import TemporaryFile
import subprocess

class Sample_View(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(Sample_View, self).__init__(parent=parent, args=args, macros=None)
        self.image_width = self.ui.PyDMImageView.imageWidth
        self.ui.PyDMImageView.process_image = self.process_image
        self.viewBox = self.ui.PyDMImageView.getView()
        self.positionPlot = self.ui.positionPlot
        self.ui.tabWidget.setCurrentIndex(0)
        # self.positionPlot.setLabels(left='Sp_Y (mm)', bottom='Sp_X (mm)')
        # self.positionPlot.addLegend()
        with open('./Data/camera_calib.txt', 'r') as fh:
            line=fh.readlines()
            self.cf=float(line[1].strip().split('=')[1])
        self.ui.cfLineEdit.setText(f'{self.cf:.6f}')
        # self.cf = float(self.ui.cfLineEdit.text())
        self.zmotor = Motor("15IDD:m7")
        self.xmotor = Motor('15IDD:m19')
        self.ymotor = Motor('15IDD:m18')
        self.detAcquire = PV('Teslong:cam1:Acquire')
        self.detAcquire.put(1)
        self.roisize = int(self.ui.roiSizeLineEdit.text())
        self.offsetFactor = 1. / 3.3538
        self.calibrationFlag = False
        self.init_signals()

        self.centerXLine = pg.InfiniteLine(pos=self.image_width / 2, angle=90, pen=pg.mkPen('r'), movable=False)
        self.viewBox.addItem(self.centerXLine)
        self.centerYLine = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen('r'), movable=False)
        self.viewBox.addItem(self.centerYLine)
        self.cursorXLine = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('b'))
        self.cursorYLine = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen('b'))
        self.calibrationPoints = pg.ScatterPlotItem()
        self.viewBox.addItem(self.cursorXLine, ignoreBounds = True)
        self.viewBox.addItem(self.cursorYLine, ignoreBounds = True)
        self.viewBox.addItem(self.calibrationPoints)
        self.calibrationPoints.hide()
        self.cursorXLine.hide()
        self.cursorYLine.hide()

        self.positions = []
        self.position_labels = [self.ui.SpX_PyDMLabel, self.ui.SpY_PyDMLabel, self.ui.CMIR_PyDMLabel]
        self.chan = [label.channel for label in self.position_labels]
        atexit.register(self.stopAcquire)

    def stopAcquire(self):
        self.detAcquire.put(0)


    def ui_filename(self):
        return 'ui/Sample_View.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def init_signals(self):
        self.viewBox.scene().sigMouseMoved.connect(self.image_mouse_moved)
        self.viewBox.scene().sigMouseClicked.connect(self.mouse_clicked)
        self.ui.cfLineEdit.returnPressed.connect(self.cfChanged)
        self.ui.positionListWidget.itemDoubleClicked.connect(self.moveOnListClicked)
        self.ui.addPositionPushButton.clicked.connect(self.addPosition)
        self.ui.removePositionsPushButton.clicked.connect(self.removePositions)
        self.ui.moveUpPushButton.clicked.connect(self.moveUp)
        self.ui.moveDownPushButton.clicked.connect(self.moveDown)
        self.ui.savePositionsPushButton.clicked.connect(self.savePositions)
        self.ui.openPositionsPushButton.clicked.connect(self.openPositions)
        self.ui.calcOffsetPushButton.clicked.connect(self.calcROI)
        self.ui.centerXPushButton.clicked.connect(self.centerX)
        self.ui.centerYPushButton.clicked.connect(self.centerY)
        self.ui.roiSizeLineEdit.returnPressed.connect(self.roiSizeChanged)
        self.ui.blenderInterpolatePushButton.clicked.connect(self.blenderInterpolate)
        self.ui.calibratePushButton.clicked.connect(self.openCalibration)


    def openCalibration(self):
        self.calibrationPos=[[0,0],[1,1]]
        self.calibrationWidget = PyDMFrame()
        self.calibrationWidget = uic.loadUi('ui/Calibrate.ui',self.calibrationWidget)
        self.calibrationFlag = True
        self.calibrationPoints.show()
        self.calibrationWidget.firstPosPushButton.clicked.connect(lambda x: self.selectPos(pos=1))
        self.calibrationWidget.secondPosPushButton.clicked.connect(lambda x: self.selectPos(pos=2))
        self.calibrationWidget.calibratePushButton.clicked.connect(self.calibrate)
        self.calibrationWidget.show()

    def selectPos(self, pos=1):
        self.chosenPosition = pos

    def calibrate(self):
        try:
            knownDistance = float(self.calibrationWidget.knownDistanceLineEdit.text())
        except Exception as e:
            QMessageBox.critical(self,'Value Error', f'{e}')
            return
        distance = np.sqrt((self.pos1[0]-self.pos2[0])**2+(self.pos1[1]-self.pos2[1])**2)
        self.cf = np.round(knownDistance/distance,6)
        with open('./Data/camera_calib.txt', 'w') as fh:
            fh.write(f'#Calibration saved on {time.asctime()}\n')
            fh.write(f'cf={self.cf:.6f}')
        self.cfLineEdit.setText(f'{self.cf:.6f}')
        self.calibrationFlag = False
        self.calibrationPoints.hide()
        self.calibrationWidget.close()



    def moveOnListClicked(self, item):
        row = self.ui.positionListWidget.row(item)
        newX = self.positions[row][self.chan[0]]
        newY = self.positions[row][self.chan[1]]
        newZ = self.positions[row][self.chan[2]]
        self.ui.SpX_PyDMLineEdit.setText('%.3f' % newX)
        self.ui.SpY_PyDMLineEdit.setText('%.3f' % newY)
        self.ui.CMIR_PyDMLineEdit.setText('%.3f' % newZ)
        self.ui.SpX_PyDMLineEdit.send_value()
        self.ui.SpY_PyDMLineEdit.send_value()
        self.ui.CMIR_PyDMLineEdit.send_value()

    def roiSizeChanged(self):
        try:
            self.roisize = int(self.roiSizeLineEdit.text())
        except:
            QMessageBox.warning(self, 'Value error', 'Please use integer only')
            self.roiSizeLineEdit.setText(float(self.roisize))



    def process_image(self, image):
        """
        Convert the 1D ArrayData to RGB and Gray image
        :param image:
        :return:
        """
        image = np.array(image, dtype=np.uint8)
        if image.ndim==3:
            timage = image.reshape((self.image_height, self.image_width, 3))
        else:
            self.image_height = int(image.size / self.image_width / 3)
            self.centerYLine.setValue(self.image_height / 2)
            timage = image.reshape((self.image_height, self.image_width, 3))
            self.imageCenterX = int(self.image_width / 2)
            self.imageCenterY = int(self.image_height / 2)
        image = cv2.cvtColor(timage, cv2.COLOR_BGR2GRAY)
        self.image = image
        self.focusParameter()
        return timage

    def focusParameter(self):
        """
        Calculates and updates the focus parameter
        :return:
        """
        fp = cv2.Laplacian(self.image, cv2.CV_64F).var()
        self.ui.focusParameterLabel.setText('%.3f' % fp)
        return fp

    def image_mouse_moved(self, pos):
        """
        Updates the curson position reading the mouse position
        """
        coords = self.ui.PyDMImageView.getImageItem().mapFromScene(pos)
        self.x = int(coords.x())
        self.y = int(coords.y())
        if 0 < self.x < self.image_width and 0 < self.y < self.image_height:
            self.ui.cursorPosLabel.setText('X=%4d, Y=%4d, Z=%4d' % (self.x, self.y, self.image[self.y, self.x]))
            self.cursorXLine.setValue(self.x)
            self.cursorYLine.setValue(self.y)
            self.cursorXLine.show()
            self.cursorYLine.show()
        else:
            self.cursorXLine.hide()
            self.cursorYLine.hide()

    def mouse_clicked(self, event):
        """
        Move the sample to the mouse clicked positon
        :param event:
        :return:
        """
        if event._double and self.ui.clickMoveCheckBox.isChecked():
            if 0 < self.x < self.image_width and 0 < self.y < self.image_height:
                newX = float(self.ui.SpX_PyDMLineEdit.text()) - self.cf * (self.x - self.image_width / 2 - 1)
                newY = float(self.ui.SpY_PyDMLineEdit.text()) + self.cf * (self.y - self.image_height / 2 + 1)
                self.ui.SpX_PyDMLineEdit.setText('%.3f' % newX)
                self.ui.SpY_PyDMLineEdit.setText('%.3f' % newY)
                self.ui.SpX_PyDMLineEdit.send_value()
                self.ui.SpY_PyDMLineEdit.send_value()
                while self.xmotor.MOVN or self.ymotor.MOVN:
                    QApplication.processEvents()
            if self.autoAdd2ListCheckBox.isChecked():
                self.addPosition()
        elif self.calibrationFlag:
            if self.chosenPosition == 1:
                self.calibrationWidget.firstPosLineEdit.setText(f'x: {self.x}, y: {self.y}')
                self.pos1 = [self.x, self.y]
                self.calibrationPos[0] = self.pos1
                self.calibrationPoints.setData(pos = self.calibrationPos, size = 10 ,symbol = 'o', pen=pg.mkPen(color='red'))
            else:
                self.calibrationWidget.secondPosLineEdit.setText(f'x: {self.x}, y: {self.y}')
                self.pos2 = [self.x, self.y]
                self.calibrationPos[1] = self.pos2
                self.calibrationPoints.setData(pos=self.calibrationPos, size = 10, symbol = 'o', pen=pg.mkPen(color='red'))
        else:
            pass

    def calcROI(self):
        roi1 = self.image[self.imageCenterY - self.roisize:self.imageCenterY,
               self.imageCenterX - self.roisize:self.imageCenterX]
        roi2 = self.image[self.imageCenterY - self.roisize:self.imageCenterY,
               self.imageCenterX:self.imageCenterX + self.roisize]
        roi3 = self.image[self.imageCenterY:self.imageCenterY + self.roisize,
               self.imageCenterX:self.imageCenterX + self.roisize]
        roi4 = self.image[self.imageCenterY:self.imageCenterY + self.roisize,
               self.imageCenterX - self.roisize:self.imageCenterX]
        int_max = np.max([roi1.max(), roi2.max(), roi3.max(), roi4.max()])
        roi1 = np.abs(roi1 - int_max)
        roi2 = np.abs(roi2 - int_max)
        roi3 = np.abs(roi3 - int_max)
        roi4 = np.abs(roi4 - int_max)
        int_max = np.max([roi1.max(), roi2.max(), roi3.max(), roi4.max()])
        thresh = 0.1 * int_max

        roi1sum = np.sum(np.where(roi1 > thresh, 1, 0))
        roi2sum = np.sum(np.where(roi2 > thresh, 1, 0))
        roi3sum = np.sum(np.where(roi3 > thresh, 1, 0))
        roi4sum = np.sum(np.where(roi4 > thresh, 1, 0))
        right = roi2sum + roi3sum
        left = roi1sum + roi4sum
        diffhroi = right - left
        top = roi1sum + roi2sum
        bottom = roi3sum + roi4sum
        diffvroi = top - bottom
        totalroi = (left + right)
        self.x_offset = diffhroi * self.offsetFactor / totalroi
        self.y_offset = diffvroi * self.offsetFactor / totalroi
        label = 'Offset: X= %.6f, Y = %.6f' % (self.x_offset, self.y_offset)
        self.ui.offsetLabel.setText(label)

    def centerX(self):
        self.calcROI()
        if abs(self.x_offset) > 0.005:
            newX = float(self.ui.SpX_PyDMLineEdit.text()) - self.x_offset
            self.ui.SpX_PyDMLineEdit.setText('%.3f' % newX)
            self.ui.SpX_PyDMLineEdit.send_value()
        while self.xmotor.MOVN == 1:
            print('moving')
            QApplication.processEvents()
        self.calcROI()

    def centerY(self):
        self.calcROI()
        if abs(self.y_offset) > 0.005:
            newY = float(self.ui.SpY_PyDMLineEdit.text()) - self.y_offset
            self.ui.SpY_PyDMLineEdit.setText('%.3f' % newY)
            self.ui.SpY_PyDMLineEdit.send_value()
        while self.ymotor.MOVN == 1:
            print('moving')
            QApplication.processEvents()

        self.calcROI()

    def cfChanged(self):
        """
        Changes the Calibration factor
        :return:
        """
        try:
            self.cf = float(self.ui.cfLineEdit.text())
            with open('./Data/camera_calib.txt', 'r') as fh:
                fh.write(f'#Calibration saved on {time.asctime()}\n')
                fh.write(f'cf={self.cf:.6f}')
        except:
            QMessageBox.warning(self, 'Value Error', 'Enter numbers only')
            self.ui.cfLineEdit.setText('%.5f' % self.cf)

    def addPosition(self):
        """
        Add a position in the location after the last selected position
        :return:
        """
        values = [label.value for label in self.position_labels]
        if len(self.ui.positionListWidget.selectedItems()) == 0:
            tpos = {}
            for i in range(len(self.chan)):
                tpos[self.chan[i]] = np.round(values[i], decimals=3)
            self.positions.append(tpos)
        else:
            loc = self.ui.positionListWidget.row(self.ui.positionListWidget.selectedItems()[-1]) + 1
            tpos = {}
            for i in range(len(self.chan)):
                tpos[self.chan[i]] = np.round(values[i], decimals=3)
            self.positions.insert(loc, tpos)
        self.update_positionListWidget(self.positions)

    def removePositions(self):
        """
        Removes selected positions from self.positions list and updates the self.positionListWidget
        :return:
        """
        selectedRows = [self.ui.positionListWidget.row(item) for item in self.ui.positionListWidget.selectedItems()]
        selectedRows.sort(reverse=True)
        for row in selectedRows:
            self.positions.pop(row)
        self.update_positionListWidget(self.positions)

    def update_positionListWidget(self, positions):
        """
        Updates the positionListWidget with values in the self.positions
        :param positions:
        :return:
        """
        self.positionListWidget.clear()
        labels = ['%d:%s' % (i, pos) for i, pos in enumerate(positions)]
        self.ui.positionListWidget.addItems(labels)
        self.plotPositions()

    def moveUp(self):
        """
        Move selected positions in the list by 1 position UP
        :return:
        """
        selectedRows = [self.ui.positionListWidget.row(item) for item in self.ui.positionListWidget.selectedItems()]
        for row in selectedRows:
            self.positions.insert(row - 1, self.positions.pop(row))
        self.update_positionListWidget(self.positions)

    def moveDown(self):
        """
        Move selected positions in the list by 1 position DOWN
        :return:
        """
        selectedRows = [self.ui.positionListWidget.row(item) for item in self.ui.positionListWidget.selectedItems()]
        for row in selectedRows:
            self.positions.insert(row + 1, self.positions.pop(row))
        self.update_positionListWidget(self.positions)

    def savePositions(self):
        """
        Save positions in a file
        :return:
        """
        fname = QFileDialog.getSaveFileName(self, 'Save positions as', filter='Position Files (*.pos)')[0]
        if fname != '':
            positions = self.positions2Array()
            header = ''
            for ch in self.chan:
                header = header + ch + ' '
            np.savetxt(fname, positions, fmt='%.3f', header=header)

    def openPositions(self):
        """
        Open and import positions from a file
        :return:
        """
        fname = QFileDialog.getOpenFileName(self, 'Save positions as', filter='Position Files (*.pos)')[0]
        if fname != '':
            self.positions = []
            with open(fname, 'r') as fh:
                lines = fh.readlines()
                channels = lines[0][1:].strip().split()
                for line in lines[1:]:
                    values = line.strip().split()
                    tpos = {}
                    for i, ch in enumerate(channels):
                        tpos[ch] = np.round(float(values[i]), 3)
                    self.positions.append(tpos)
            self.update_positionListWidget(self.positions)

    def plotPositions(self):
        pos = self.positions2Array()
        self.positionPlot.add_data(pos[:, 0], pos[:, 1], name='Sample Positions')
        self.positionPlot.Plot(['Sample Positions'])
        # try:
        #     self.scatterPlot.setData(pos[:, 0], pos[:, 1])
        # except:
        #     self.scatterPlot = self.positionPlot.plot(pos[:, 0], pos[:, 1], symbol='o', name='Sample Positions')
        #     self.scatterPlot.setCurveClickable(True)
        #     self.scatterPlot.sigPointsClicked.connect(self.pointsClicked)

    # def pointsClicked(self, points, event):
    #     print(dir(points))

    def positions2Array(self):
        positions = []
        for pos in self.positions:
            positions.append([value for key, value in pos.items()])
        positions = np.array(positions)
        return positions


    def blenderInterpolate(self):
        localMount = self.ui.localMountLineEdit.text()
        chemmat92Mount = self.ui.chemmat92MountLineEdit.text()
        try:
            spacing = eval(self.ui.interpSpacingLineEdit.text())
        except ValueError as e:
            QMessageBox.warning(self, "Value error", f"{e}")
            return
        # ifname = '/chemdata/Data/ASWAXS/Software/ASWAXS/Data/test_positions.pos'
        # ofname = '/chemdata/Data/ASWAXS/Software/ASWAXS/Data/test.csv'
        positions = self.positions2Array()
        header = ''
        for ch in self.chan:
            header = header + ch + ' '

        np.savetxt('./Data/temp.pos', positions, fmt='%.3f', header=header)
        lifname = os.path.abspath('./Data/temp.pos')
        print(f'temp path is {lifname}')
        # lifname = QFileDialog.getOpenFileName(self, "Open input file", "Select the file for input", "Input Files (*.pos)")[0]
        if os.path.exists(lifname):
            ifname = lifname.replace(localMount, chemmat92Mount)
            print(f'local mount is {localMount}')
            ifname = ifname.replace('\\', '/')
            print(f'server temp path is {ifname}')
            lofname = QFileDialog.getSaveFileName(self, "Save output as", "./Data", "Output Files (*.csv *.txt)")[0]
            if lofname != "":
                if os.path.splitext(lofname)[1] == "":
                    lofname += "*.csv"
                ofname = lofname.replace(localMount, chemmat92Mount)
        os.remove(lifname)
        hostname = "164.54.169.92"
        username = "chem_epics"
        key_filename = '/home/chem_epics/.ssh/mykey'
        port = 22  # Default SSH port
        if socket.gethostbyaddr(socket.gethostname())[2][0] != hostname:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(
                paramiko.AutoAddPolicy())  # Automatically add the host key (for testing purposes only)

            try:
                client.connect(hostname, port=port, username=username, key_filename=key_filename)
                print(f"Connected to {hostname}")
            except Exception as e:
                print(f"Connection error: {e}")
                exit()
            # command = f"python /home/chem_epics/chemdata2/Data/ASWAXS/Software/ASWAXS/Scripts/Run_Blender.py {ifname} {ofname} {spacing:0.2f}"
            command = f'blender --background --python /home/chem_epics/chemdata2/Data/ASWAXS/Software/ASWAXS/Scripts/Blender_Macro.py {ifname} {ofname} {spacing:0.2f}'

            try:
                stdin, stdout, stderr = client.exec_command(command)

                # Read output
                output = stdout.read().decode("utf-8")
                error = stderr.read().decode("utf-8")

                print("Output:")
                print(output)
                if error:
                    print("Error:")
                    print(error)
            except Exception as e:
                print(f"Command execution error: {e}")
            finally:
                client.close()
                print("Connection closed")
        else:
            command = ['blender', '--background --python', '/home/chem_epics/chemdata2/Data/ASWAXS/Software/ASWAXS/Scripts/Blender_Macro.py', ifname, ofname, f'{spacing}']
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            print(stdout.decode())

        data = np.loadtxt(lofname, comments='#', delimiter=',')
        self.positionPlot.add_data(data[:, 0], data[:, 1], name='Interpolated Positions')
        self.positionPlot.Plot(['Sample Positions', 'Interpolated Positions'])










