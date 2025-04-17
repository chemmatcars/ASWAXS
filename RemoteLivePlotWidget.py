# RemoteLivePlotWidget.py

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from bluesky.callbacks.zmq import RemoteDispatcher
from bluesky.callbacks import LivePlot
from bluesky.utils import install_qt_kicker
import threading
import sys


class RemoteLivePlotWidget(QWidget):
    def __init__(self, address=['164.54.169.16', '5567'], y='det', x='motor', parent=None):
        super().__init__(parent)

        self.address = address
        self.x = x
        self.y = y

        # Set up the figure and canvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # Set up LivePlot
        self.live_plot = LivePlot(y=self.y, x=self.x, ax=self.ax)

        # Install qt kicker (required for matplotlib/reactivity)
        install_qt_kicker()

        # Start the dispatcher in a thread
        self.dispatcher = RemoteDispatcher(self.address)
        self.dispatcher.subscribe(self.live_plot)
        self.dispatcher_thread = threading.Thread(target=self.dispatcher.start)
        self.dispatcher_thread.daemon = True
        self.dispatcher_thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RemoteLivePlotWidget()
    window.show()
    app.exec_()
