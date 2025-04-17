from qtpy import QtWidgets
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.manager import QtKernelManager
from IPython.lib import guisupport


class ConsoleWidget(RichJupyterWidget):

    def __init__(self, *args, **kwargs):
        super(ConsoleWidget, self).__init__(*args, **kwargs)
        self.font_size = 10
        kernel_manager = QtKernelManager(kernel_name='python3')
        kernel_manager.start_kernel()
        # kernel_manager.kernel.gui = 'qt'
        kernel_client = kernel_manager.client()
        kernel_client.start_channels()

        self.kernel_manager=kernel_manager
        self.kernel_client=kernel_client
        # self.execute_on_complete_input=True

        def stop():
            kernel_client.stop_channels()
            kernel_manager.shutdown_kernel()
            guisupport.get_app_qt().exit()

        self.exit_requested.connect(stop)


    def push_vars(self, variableDict):
        """
        Given a dictionary containing name / value pairs, push those variables
        to the Jupyter console widget
        """
        self.kernel_manager.kernel.shell.push(variableDict)

    def clear(self):
        """
        Clears the terminal
        """
        self._control.clear()

        # self.kernel_manager


    def print_text(self, text):
        """
        Prints some plain text to the console
        """
        self._append_plain_text(text)

    # def _execute(self, command, hidden):
    #     return super(ConsoleWidget, self)._execute(command, hidden)

    def execute_command(self, command, hidden=True, interactive=True):
        """
        Execute a command in the frame of the console widget
        """
        # self._execute(command, hidden)
        # self.kernel_client.
        self.kernel_client.execute(command, hidden, interactive)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    widget = ConsoleWidget()
    widget.execute_command('from bluesky_queueserver_api.zmq import REManagerAPI')
    widget.show()
    app.exec_()