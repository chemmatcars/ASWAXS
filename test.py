import sys
import time
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout


class WorkerThread(QThread):
    update_label_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        for i in range(5):
            time.sleep(1)
            self.update_label_signal.emit(f"Processing: {i+1}/5")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.label = QLabel("Not started")
        self.button = QPushButton("Start")
        self.button.clicked.connect(self.start_thread)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.worker_thread = WorkerThread()
        self.worker_thread.update_label_signal.connect(self.update_label)
        self.worker_thread.finished.connect(self.thread_finished)

    def start_thread(self):
        self.label.setText("Started...")
        self.button.setEnabled(False)
        self.worker_thread.start()

    def update_label(self, text):
        self.label.setText(text)

    def thread_finished(self):
         self.label.setText("Finished")
         self.button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
