import os.path

from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox, QFileDialog, QMessageBox, QDesktopWidget, QMainWindow, QDialog
from PyQt5.QtCore import pyqtSignal, Qt, QThread
from PyQt5.QtGui import QTextCursor
from pydm import Display
from bluesky_queueserver import bind_plan_arguments
from pandas.core.methods.describe import select_describe_func
from pydm.widgets.frame import PyDMFrame
from bluesky_queueserver_api.zmq import REManagerAPI
from PyQt5.QtCore import QThread, pyqtSignal
from importlib import import_module
import inspect
import threading
import zmq
import json
import time
import lmfit
import copy
import sys
import paramiko



class Bluesky_Client(Display):
    """
    This widget calculates the Energy values at which the f' values are equidistant below the absorption edge of a selected element
    """
    message_received = pyqtSignal(str)
    queue_updated = pyqtSignal(dict, list, list)
    queue_status = pyqtSignal(str)
    history_updated = pyqtSignal()

    def __init__(self, parent=None, args=None, macros=None):
        """
        """
        super(Bluesky_Client, self).__init__(parent=parent, args=args, macros=None)
        self.init_signals()
        #self.importAllAPIs()
        self.success_message = False
        self.queue_items = []
        self.history_items = []
        self.messageTransfer = True
        self.queueMonitoring = True
        self.updateBskyServer()
        time.sleep(2) #Need to sleep before the threads in the previous commands starts properly
        self.startEnv()

    def ui_filename(self):
        return 'ui/Bluesky_Client.ui'

    def ui_filepath(self):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), self.ui_filename())

    def init_signals(self):
        self.ui.restartBskyServerPushButton.clicked.connect(self.restart_re_manager)
        self.ui.bskyServerLineEdit.returnPressed.connect(self.updateBskyServer)
        self.ui.zmqReqSocketLineEdit.returnPressed.connect(self.updateBskyServer)
        self.ui.zmqSubSocketLineEdit.returnPressed.connect(self.updateBskyServer)
        self.ui.openEnvPushButton.clicked.connect(self.startEnv)
        self.ui.closeEnvPushButton.clicked.connect(self.closeEnv)
        self.ui.destroyEnvPushButton.clicked.connect(self.destroyEnv)
        self.ui.updateEnvPushButton.clicked.connect(self.updateEnv)
        self.ui.addPlanPushButton.clicked.connect(lambda x: self.openPlanEditor(role='add'))
        self.ui.removePlanPushButton.clicked.connect(self.removePlansFromQueue)
        self.ui.queueListWidget.itemDoubleClicked.connect(lambda x: self.openPlanEditor(role='modify'))
        self.ui.loadExternalPlansPushButton.clicked.connect(self.loadExternalPlanOrScript)

        self.ui.pauseRMPushButton.clicked.connect(self.pauseRM)
        self.ui.resumeRMPushButton.clicked.connect(self.resumeRM)
        self.ui.stopRMPushButton.clicked.connect(self.stopRM)
        self.ui.abortRMPushButton.clicked.connect(self.abortRM)
        self.ui.haltRMPushButton.clicked.connect(self.haltRM)
        self.ui.resumeRMPushButton.setEnabled(False)
        self.ui.stopRMPushButton.setEnabled(False)
        self.ui.abortRMPushButton.setEnabled(False)
        self.ui.haltRMPushButton.setEnabled(False)

        self.ui.moveUpPushButton.clicked.connect(self.movePlanUp)
        self.ui.moveDownPushButton.clicked.connect(self.movePlanDown)
        self.ui.startQueuePushButton.clicked.connect(self.startQueue)
        self.ui.stopQueuePushButton.clicked.connect(self.stopQueue)

        self.ui.addToQueueTopPushButton.clicked.connect(self.addToQueueTop)
        self.ui.addToQueueBottomPushButton.clicked.connect(self.addToQueueBottom)
        self.ui.clearArchivePushButton.clicked.connect(self.clearArchive)
        self.ui.archivedQueueListWidget.itemDoubleClicked.connect(self.showArchivedPlanInfo)
        self.ui.saveQueuePushButton.clicked.connect(self.saveQueue)
        self.ui.loadQueuePushButton.clicked.connect(self.loadQueue)

        self.ui.queueTabWidget.setCurrentIndex(0)
        self.ui.consoleTabWidget.setCurrentIndex(1)

    def restart_re_manager(self):
        self.messageTransfer = False
        self.queueMonitoring = False
        time.sleep(2)
        self.closeEnv()

        hostname = "164.54.169.92"
        username = "mrinalkb"
        key_filename = '/Users/mrinalkb/.ssh/mykey'
        port = 22  # Default SSH port

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Automatically add the host key (for testing purposes only)

        try:
            client.connect(hostname, port=port, username=username, key_filename = key_filename)
            print(f"Connected to {hostname}")
        except Exception as e:
            print(f"Connection error: {e}")
            exit()
        command = "systemctl --user restart queue-server-aswaxs.service"

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
        self.startEnv()
        self.messageTransfer = True
        self.queueMonitoring = True
        self.updateBskyServer()

    def saveQueue(self):
        fname = QFileDialog.getSaveFileName(self, 'Save queue as','./queues', 'Queue files  (*.queue)')[0]
        if fname != '':
            if os.path.splitext(fname)[1] == '':
                fname += '.queue'
            with open(fname, 'w') as fh:
                fh.write('#File save on %s\n'%time.asctime())
                for item in self.queue_items:
                    txt = str({key: item[key] for key in ['name', 'item_type', 'args', 'kwargs']})
                    fh.write('%s\n'%txt)

    def loadQueue(self):
        fname = QFileDialog.getOpenFileName(self, 'Open queue file', './queues', 'Queue files (*.queue)')[0]
        with open(fname, 'r') as fh:
            lines = fh.readlines()
            qpos = self.queueListWidget.count()
            # print(qpos)
            for line in lines:
                if line[0] != '#':
                    item = eval(line.strip())
                    self.addPlanOrInstr(item['name'], item['item_type'], qpos, item=item)
                    print(qpos)
                    qpos += 1


    def addToQueueTop(self):
        selectedItems = self.ui.archivedQueueListWidget.selectedItems()
        selectedRows = [self.ui.archivedQueueListWidget.row(item) for item in selectedItems]
        newrow=0
        for row in selectedRows:
            item = self.history_items[row]
            newitem = {key:item[key] for key in ['name', 'item_type', 'args', 'kwargs']}
            self.addPlanOrInstr(newitem['name'], newitem['item_type'], newrow, item = newitem)
            newrow += 1

    def addToQueueBottom(self):
        selectedItems = self.ui.archivedQueueListWidget.selectedItems()
        selectedRows = [self.ui.archivedQueueListWidget.row(item) for item in selectedItems]
        for row in selectedRows:
            item = self.history_items[row]
            newitem = {key: item[key] for key in ['name', 'item_type', 'args', 'kwargs']}
            self.addPlanOrInstr(newitem['name'], newitem['item_type'], -1, item = newitem)

    def showArchivedPlanInfo(self, item):
        row = self.ui.archivedQueueListWidget.row(item)
        item = self.history_items[row]
        txt = ''
        for key, value in item.items():
            txt += '%s : %s\n'%(key, str(value))
        QMessageBox.information(self, '%s'%item['name'], txt)



    def movePlanUp(self):
        selectedItems = self.ui.queueListWidget.selectedItems()
        pno = [self.ui.queueListWidget.row(item) for item in selectedItems]
        pno.sort()
        for tno in pno:
            request = {"method": "queue_item_move", "params": {"pos": tno, "pos_dest": max(0,tno-1)}}
            response = self.send_zmq_request(request)

    def movePlanDown(self):
        selectedItems = self.ui.queueListWidget.selectedItems()
        pno = [self.ui.queueListWidget.row(item) for item in selectedItems]
        pno.sort(reverse=True)
        for tno in pno:
            request = {"method": "queue_item_move", "params": {"pos": tno, "pos_dest": min(self.qnum, tno + 1)}}
            response = self.send_zmq_request(request)


    def pauseRM(self):
        request = {"method": "re_pause", "params": {"option": "immediate"}}
        response = self.send_zmq_request(request)
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Plan paused successfully!')
            self.ui.resumeRMPushButton.setEnabled(True)
            self.ui.stopRMPushButton.setEnabled(True)
            self.ui.abortRMPushButton.setEnabled(True)
            self.ui.haltRMPushButton.setEnabled(True)
            self.ui.pauseRMPushButton.setEnabled(False)
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to pause the plan.'))

    def resumeRM(self):
        request = {"method": "re_resume", "params": {}}
        response = self.send_zmq_request(request)
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Plan resumed successfully!')
            self.ui.resumeRMPushButton.setEnabled(False)
            self.ui.stopRMPushButton.setEnabled(False)
            self.ui.abortRMPushButton.setEnabled(False)
            self.ui.haltRMPushButton.setEnabled(False)
            self.ui.pauseRMPushButton.setEnabled(True)
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to resume the plan.'))

    def stopRM(self):
        request = {"method": "re_stop", "params": {}}
        response = self.send_zmq_request(request)
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Plan stopped successfully!')
            self.ui.resumeRMPushButton.setEnabled(False)
            self.ui.stopRMPushButton.setEnabled(False)
            self.ui.abortRMPushButton.setEnabled(False)
            self.ui.haltRMPushButton.setEnabled(False)
            self.ui.pauseRMPushButton.setEnabled(True)
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to stop the plan.'))

    def abortRM(self):
        request = {"method": "re_abort", "params": {}}
        response = self.send_zmq_request(request)
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Plan aborted successfully!')
            self.ui.resumeRMPushButton.setEnabled(False)
            self.ui.stopRMPushButton.setEnabled(False)
            self.ui.abortRMPushButton.setEnabled(False)
            self.ui.haltRMPushButton.setEnabled(False)
            self.ui.pauseRMPushButton.setEnabled(True)
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to stop the plan.'))

    def haltRM(self):
        request = {"method": "re_haltp", "params": {}}
        response = self.send_zmq_request(request)
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Plan halted successfully!')
            self.ui.resumeRMPushButton.setEnabled(False)
            self.ui.stopRMPushButton.setEnabled(False)
            self.ui.abortRMPushButton.setEnabled(False)
            self.ui.haltRMPushButton.setEnabled(False)
            self.ui.pauseRMPushButton.setEnabled(True)
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to halt the plan.'))

    def loadExternalPlanOrScript(self):
        fname = QFileDialog.getOpenFileName(self, 'Load external plans/scripts', dir='./', filter="Plans (*.py)")[0]
        if fname != '':
            with open(fname, 'r') as fh:
                script=fh.read()

            request = {"method": "script_upload", "params":{"script": script, "update_lists": True}}
            response = self.send_zmq_request(request)
            if response.get("success"):
                QMessageBox.information(self, 'Success', 'Loaded external plan/script successfully!')
                self.updatePlanComboBox()
            else:
                QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to load the external plan/script.'))


    def updateBskyServer(self):
        self.bskyServer = self.ui.bskyServerLineEdit.text().strip()
        self.zmqReqSocket = self.ui.zmqReqSocketLineEdit.text().strip()
        self.zmqSubSocket = self.ui.zmqSubSocketLineEdit.text().strip()

        self.zmqReqServer = 'tcp://'+self.bskyServer+':'+self.zmqReqSocket
        self.zmqSubServer = 'tcp://'+self.bskyServer+':'+self.zmqSubSocket
        try:
            self.socket_req.close()
            self.socket_sub.close()
            self.context.term()
        except:
            pass
        self.context = zmq.Context()
        # Socket to talk to server
        self.socket_req = self.context.socket(zmq.REQ)
        self.socket_req.connect(self.zmqReqServer)  # Replace with your Queue server request ZMQ address
        # Socket to subscribe to server messages
        self.socket_sub = self.context.socket(zmq.SUB)
        self.socket_sub.connect(self.zmqSubServer)  # Replace with your Queue server subscription ZMQ address
        self.socket_sub.setsockopt_string(zmq.SUBSCRIBE, "")

        self.message_thread = threading.Thread(target=self.receive_messages)
        self.message_thread.daemon = True
        # self.message_thread = BskyThread(self.socket_sub)
        self.message_received.connect(self.append_message)
        self.message_thread.start()
        # self.message_thread.join()
        self.updatePlanComboBox()

        self.qnum=0
        self.queue_thread = threading.Thread(target=self.monitor_queue)
        self.queue_thread.daemon = True
        self.queue_updated.connect(self.update_queue)
        self.queue_status.connect(self.update_queue_status)
        self.queue_thread.start()
        # self.queue_thread.join()


    def update_queue_status(self, status):
        if status == 'Idle':
            self.ui.queueStatusLabel.setStyleSheet("color: green;")
            self.stopQueuePushButton.setEnabled(False)
            self.startQueuePushButton.setEnabled(True)
        else:
            self.ui.queueStatusLabel.setStyleSheet("color: red;")
            self.startQueuePushButton.setEnabled(False)
            self.stopQueuePushButton.setEnabled(True)
        self.ui.queueStatusLabel.setText(status)
        self.queueStatus=status
        if self.qnum>1:
            self.ui.moveUpPushButton.setEnabled(True)
            self.ui.moveDownPushButton.setEnabled(True)
        else:
            self.ui.moveUpPushButton.setEnabled(False)
            self.ui.moveDownPushButton.setEnabled(False)

    def monitor_queue(self):
        print('Queue monitoring thread started')
        while self.queueMonitoring:
            response1 = self.send_zmq_request({"method": "queue_get", "params": {}})
            items = response1["items"]
            runningItem = response1["running_item"]
            response2 = self.send_zmq_request({"method": "history_get", "params": {}})
            history_items = response2["items"]
            num = len(items)
            if  items != self.queue_items or self.history_items != history_items:
                self.queue_updated.emit(runningItem, items, history_items)
            if runningItem == {}:
                self.runningItemLineEdit.clear()
            self.qnum = num
            if len(response1["running_item"])>0:
                self.queue_status.emit('Running')
            else:
                self.queue_status.emit('Idle')
            self.queue_items = copy.copy(items)
            self.history_items = copy.copy(history_items)
            if len(self.queue_items)>0:
                self.ui.saveQueuePushButton.setEnabled(True)
                self.ui.removePlanPushButton.setEnabled(True)
            else:
                self.ui.saveQueuePushButton.setEnabled(False)
                self.ui.removePlanPushButton.setEnabled(False)
            if len(self.queue_items)<2:
                self.ui.moveUpPushButton.setEnabled(False)
                self.ui.moveDownPushButton.setEnabled(False)
            else:
                self.ui.moveUpPushButton.setEnabled(True)
                self.ui.moveDownPushButton.setEnabled(True)
            if len(self.history_items)>0:
                self.ui.clearArchivePushButton.setEnabled(True)
            else:
                self.ui.clearArchivePushButton.setEnabled(False)
            time.sleep(1.0)
        self.queue_updated.disconnect()
        self.queue_status.disconnect()
        print('Queue monitoring thread killed')

    def update_queue(self, runningItem, items, history_items):
        self.ui.queueListWidget.clear()
        self.ui.archivedQueueListWidget.clear()
        if runningItem != {}:
            txt = ''
            for key in ['name', 'item_type', 'args', 'kwargs']:
                txt += f'{key}:{runningItem[key]}, '
            self.runningItemLineEdit.setText(txt[:-2])

        titems=[]
        for item in items:
            txt =''
            for key in ['name','item_type','args','kwargs']:
                txt += f'{key}:{item[key]}, '
            titems.append(txt[:-2])
        htitems = []
        for item in history_items:
            txt =''
            for key in ['name','item_type','args','kwargs']:
                txt += f'{key}:{item[key]}, '
            htitems.append(txt[:-2])
        self.ui.queueListWidget.addItems(titems)
        self.ui.archivedQueueListWidget.addItems(htitems)

    def clearArchive(self):
        response = self.send_zmq_request({"method": "history_clear", "params": {}})
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Archived plans are deleted!')
            self.archivedQueueListWidget.clear()
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to clear the plans in the archive'))

    def receive_messages(self):
        print('Message transfer thread started')
        while self.messageTransfer:
            message = self.socket_sub.recv_string()
            # Debugging output: print the received message
            #            print("Received message:", message)
            if "Returning current queue and running plan" not in message and "Returning plan history" not in message:
                self.message_received.emit(message)
        self.message_received.disconnect()
        print('Message transfer thread killed')

    def append_message(self, message):
        if 'QS_Console' not in message:
            msg = json.loads(message).get("msg", "")
            self.ui.bskyMessageTextEdit.append(msg)
            self.ui.bskyMessageTextEdit.moveCursor(QTextCursor.End)

    def updatePlanComboBox(self):
        request = {"method": "plans_allowed", "params": {"user_group":"root"}}
        response = self.send_zmq_request(request)
        if response.get('success'):
            self.allowedPlans = response["plans_allowed"]
            request = {"method": "devices_allowed", "params": {"user_group":"root"}}
            response = self.send_zmq_request(request)
            self.allowedDevices = response['devices_allowed']
            self.allowedPlansByNames=list(self.allowedPlans.keys())
            self.allowedDevicesByNames=list(self.allowedDevices.keys())
            self.allowedPlansByNames.sort()
            self.allowedDevicesByNames.sort()
            self.ui.planComboBox.clear()
            self.ui.planComboBox.addItems(self.allowedPlansByNames)
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to get the allowed plans information'))
        # self.ui.consoleWidget.execute_command('RM=REManagerAPI(zmq_control_addr="%s")' % self.zmqReqServer)


    def importAllAPIs(self):
        self.ui.consoleWidget.execute_command('from bluesky_queueserver_api.zmq import REManagerAPI')
        self.ui.consoleWidget.execute_command('from bluesky_queueserver_api import BItem')
        self.ui.consoleWidget.execute_command('from bluesky_queueserver_api import BPlan, BInst, BFunc')
        self.ui.consoleWidget.execute_command('from bluesky_queueserver_api import WaitMonitor')

    def startEnv(self):
        request = {"method": "status", "params": {}}
        response = self.send_zmq_request(request)
        if not response.get('worker_environment_exists'):
            request = {"method": "environment_open"}
            response = self.send_zmq_request(request)
            if response.get("success"):
                if self.success_message:
                    QMessageBox.information(self, 'Success', 'Worker environment opened!')
                self.ui.closeEnvPushButton.setEnabled(True)
                self.ui.openEnvPushButton.setEnabled(False)
                self.ui.destroyEnvPushButton.setEnabled(True)
                self.ui.updateEnvPushButton.setEnabled(True)
            else:
                QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to opened worker environment.'))
        else:
            self.ui.closeEnvPushButton.setEnabled(True)
            self.ui.openEnvPushButton.setEnabled(False)
            self.ui.destroyEnvPushButton.setEnabled(True)
            self.ui.updateEnvPushButton.setEnabled(True)

    def closeEnv(self):
        request = {"method": "status", "params": {}}
        response = self.send_zmq_request(request)
        if response.get('worker_environment_exists'):
            request = {"method": "environment_close"}
            response = self.send_zmq_request(request)
            if response.get("success"):
                if self.success_message:
                    QMessageBox.information(self, 'Success', 'Worker environment closed!')
                self.ui.openEnvPushButton.setEnabled(True)
                self.ui.closeEnvPushButton.setEnabled(False)
                self.ui.destroyEnvPushButton.setEnabled(False)
                self.ui.updateEnvPushButton.setEnabled(False)
            else:
                QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to close the worker environment.'))

    def destroyEnv(self):
        request = {"method": "status", "params": {}}
        response = self.send_zmq_request(request)
        if response.get('worker_environment_exists'):
            request = {"method": "environment_destroy"}
            response = self.send_zmq_request(request)
            if response.get("success"):
                if self.success_message:
                    QMessageBox.information(self, 'Success', 'Worker environment destroyed!')
                self.ui.openEnvPushButton.setEnabled(True)
                self.ui.closeEnvPushButton.setEnabled(False)
                self.ui.destroyEnvPushButton.setEnabled(False)
                self.ui.updateEnvPushButton.setEnabled(False)
            else:
                QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to destroy the worker environment.'))

    def updateEnv(self):
        request = {"method": "status", "params": {}}
        response = self.send_zmq_request(request)
        if not response.get('worker_environment_exists'):
            request = {"method": "environment_update"}
            response = self.send_zmq_request(request)
            if response.get("success"):
                if self.success_message:
                    QMessageBox.information(self, 'Success', 'Worker environment updated!')
            else:
                QMessageBox.critical(self, 'Error', response.get("msg", "Failed to update the worker environment."))

    def updateConsoleOut(self, msg, msg_err):
        txt='Out[%d]: {%s, %s}\n'%(self.plan_counter, str(msg),msg_err)
        # for key,value in msg.items():
        #     txt+='\t%s: %s\n'%(key, value)
        self.ui.zmqConsoleTextEdit.append(txt)
        self.plan_counter+=1

    def send_zmq_request(self, request):
        self.socket_req.send_json(request)
        response = self.socket_req.recv_json()
        return response

    def startQueue(self):
        request = {"method": "queue_start", "params": {}}
        response = self.send_zmq_request(request)
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Plan started successfully!')
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to start plan.'))

    def stopQueue(self):
        request = {"method": "queue_stop", "params": {}}
        response = self.send_zmq_request(request)
        if response.get("success"):
            if self.success_message:
                QMessageBox.information(self, 'Success', 'Plan stopped successfully!')
        else:
            QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to stop plan.'))

    def openPlanEditor(self, role='modify'):
        if len(self.ui.queueListWidget.selectedItems()) > 1:
            QMessageBox.warning(self, 'Selection error', 'Please select only one position in the Queue list '
                                                         'to add the new plan', QMessageBox.Ok)
            return
        self.planEditor = QDialog(parent=self)
        self.planEditor = loadUi('./ui/PlanEditor.ui', self.planEditor)
        qno = self.queueListWidget.currentRow()
        if role == 'modify':
            request = {"method": "queue_item_get", "params": {'pos':qno}}
            response = self.send_zmq_request(request)
            item = response['item']
            planName = item['name']
            planType = item['item_type']
            self.planEditor.planTypeComboBox.clear()
            self.planEditor.planTypeComboBox.addItem(planType)
            self.planEditor.planTypeComboBox.setEnabled(False)
            self.planEditor.addPushButton.setText('Modify')
            self.planEditor.planArgsTextEdit.setText(str({key: item[key] for key in ['args', 'kwargs']}))
        else:
            planName = self.ui.planComboBox.currentText()
            planType = self.planEditor.planTypeComboBox.currentText()
            item = {}
            item['name'] = planName
            item['item_type'] = planType
            try:
                self.loadPlan(fname = './plans/%s.pln'%planName)
            except:
                item['args']=[]
                item['kwargs']={}
                self.planEditor.planArgsTextEdit.setText(str({key: item[key] for key in ['args', 'kwargs']}))
        self.planEditor.setWindowTitle(planName)
        self.planEditor.planHelpTextEdit.setReadOnly(True)

        ## Getting the documentation of the plan or instruction
        for key, values in self.allowedPlans[planName].items():
            if key == 'parameters':
                self.planEditor.planHelpTextEdit.append('%s:'% key)
                # print(values)
                for value in values:
                    for parkey, parvalue in value.items():
                        if parkey == 'name':
                            self.planEditor.planHelpTextEdit.append('\t%s:' % parvalue)
                        else:
                            self.planEditor.planHelpTextEdit.append('\t\t%s: %s'%(parkey, str(parvalue).replace('\n','')))
            else:
                self.planEditor.planHelpTextEdit.append('%s: %s\n' % (key, str(values)))

        self.planEditor.savePlanPushButton.clicked.connect(lambda x:self.savePlan(fname = None))
        self.planEditor.loadPushButton.clicked.connect(lambda x: self.loadPlan(fname=None))
        self.planEditor.executePlanPushButton.clicked.connect(lambda x: self.executeItemOnce (planName, planType))
        if role == 'modify':
            self.planEditor.addPushButton.clicked.connect(lambda x: self.modifyPlan(planName, planType, item))
        else:
            try:
                # akwrgs = eval(self.planEditor.planArgsTextEdit.toPlainText().strip())
                # item = {'name': planName, 'item_type': planType, 'args': akwrgs['args'], 'kwargs': akwrgs['kwargs']}
                # print(item)
                self.planEditor.addPushButton.clicked.connect(lambda x: self.addPlanOrInstr(planName, planType, qno, item = None))
            except SyntaxError as e:
                QMessageBox.critical(self, "Dictionary Error", "%s" % e)
                return
        self.planEditor.show()

    def loadPlan(self, fname = None):
        if fname is None:
            fname = QFileDialog.getOpenFileName(self, "Open plan file", dir="./plans", filter="Plans (*.pln)")[0]
        if fname != '':
            with open(fname, 'r') as fh:
                line=fh.readline()
            self.planEditor.planArgsTextEdit.setText(line.strip())


    def executeItemOnce(self, planName, planType):
        akwrgs = eval(self.planEditor.planArgsTextEdit.toPlainText().strip())
        item={'name': planName, 'item_type': planType, 'args': akwrgs['args'], 'kwargs': akwrgs['kwargs']}
        if type(item) == dict:
            request = {"method": "queue_item_execute", "params": {'item':item, 'user_group':'primary', 'user':'Default User'}}
            response = self.send_zmq_request(request)
            if response.get('success'):
                QMessageBox.information(self, 'Success', 'Plan executed successfully')
            else:
                QMessageBox.critical(self, 'Failed', 'Plan could not be execute: %s'%response.get('msg'))

    def savePlan(self, fname = None, item={}):
        if fname is None:
            fname = QFileDialog.getSaveFileName(self, "Save plan as", dir="./plans", filter="Plans (*.pln)")[0]
        if item == {}:
            akwrgs = eval(self.planEditor.planArgsTextEdit.toPlainText().strip())
            item['args'] = akwrgs['args']
            item['kwargs'] = akwrgs['kwargs']
        if fname!="":
            plan = {key: item[key] for key in ['args', 'kwargs']}
            if os.path.splitext(fname)[1] == '':
                fname = fname+'.pln'
            with open(fname,'w') as fh:
                fh.write(str(plan))

    def addPlanOrInstr(self, planName, planType, qpos, item = None):
        if item is not None:
            item = {'name': planName, 'item_type': planType, 'args': item['args'], 'kwargs': item['kwargs']}
        else:
            akwrgs = eval(self.planEditor.planArgsTextEdit.toPlainText().strip())
            item = {'name': planName, 'item_type': planType, 'args': akwrgs['args'], 'kwargs': akwrgs['kwargs']}
        if type(item) == dict:
            request = {"method": "queue_item_add",
                       "params": {'item': item, 'pos': qpos, 'user_group': 'primary', 'user': 'Default User'}}
            response = self.send_zmq_request(request)
            item = response.get('item')
            if response.get("success"):
                if self.success_message:
                    QMessageBox.information(self, 'Success', '%s: %s added successfully.' % (planType, planName))
                self.savePlan(fname='./plans/%s.pln' % planName, item=item)
                try: # For loading queue from file
                    self.planEditor.close()
                except:
                    pass
            else:
                QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to add the %s: %s to the queue.' % (
                planType, planName)))


    def removePlansFromQueue(self):
        selectedItems=self.ui.queueListWidget.selectedItems()
        selected_uids=[]
        if len(selectedItems)>0:
            for item in selectedItems:
                qno = self.ui.queueListWidget.row(item)
                selected_uids.append(self.queue_items[qno]['item_uid'])
            request = {'method':'queue_item_remove_batch', 'params':{'uids': selected_uids}}
            response = self.send_zmq_request(request)
            if response.get('success'):
                if self.success_message:
                    QMessageBox.information(self, 'Success', 'Selected plans removed from the queue successfully.')
            else:
                QMessageBox.critical(self, 'Error', response.get('msg', 'Failed to remove all selected plans from the queue'))

    def modifyPlan(self, planName, planType, item):
        try:
            akwrgs = eval(self.planEditor.planArgsTextEdit.toPlainText().strip())
        except SyntaxError as e:
            QMessageBox.critical(self, "Dictionary Error", "%s"%e)
            return
        item['args'] = akwrgs['args']
        item['kwargs'] = akwrgs['kwargs']
        if type(item) == dict:
            request = {"method": "queue_item_update", "params": {'item':item, 'user_group':'primary', 'user':'Default User'}}
            response = self.send_zmq_request(request)
            if response.get("success"):
                item = response.get('item')
                txt = ''
                for key in ['name', 'item_type', 'args', 'kwargs']:
                    txt += f'{key}:{item[key]}, '
                self.queueListWidget.selectedItems()[0].setText(txt[:-2])
                if self.success_message:
                    QMessageBox.information(self, 'Success', '%s: %s updated successfully!'%(planType, planName))
                self.savePlan(fname='./plans/%s.pln' % planName, item=item)
                self.planEditor.close()
            else:
                QMessageBox.critical(self, 'Error', response.get("msg", 'Failed to update the %s: %s.'%(planType, planName)))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Bluesky_Client()
    window.show()
    app.exec_()

