import sys
import subprocess
import time
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QProgressBar,
                             QFileDialog, QLabel, QComboBox, QInputDialog, QLineEdit, QMessageBox, QHBoxLayout)
from PyQt5.QtCore import QThread, pyqtSignal


def list_mac_disks():
    cmd = "diskutil list | grep '/dev/disk' | awk '{print $1}'"
    process = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    disks = process.stdout.split()
    return disks


class DdThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    eta = pyqtSignal(str)

    def __init__(self, image_path, device_path, sudo_password):
        super().__init__()
        self.image_path = image_path
        self.device_path = device_path
        self.sudo_password = sudo_password
        self.start_time = time.time()
        self.process = None

    def run(self):
        cmd = f"echo {self.sudo_password} | sudo -S dd if={self.image_path} of={self.device_path} bs=4m status=progress"
        self.process = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True)

        total_size = subprocess.run(f"stat -f%z {self.image_path}", shell=True, text=True, capture_output=True).stdout.strip()
        total_size = int(total_size)

        while True:
            output = self.process.stderr.readline()
            if self.process.poll() is not None and output == '':
                break
            if output:
                last_line = output.strip()
                if "bytes" in last_line:
                    try:
                        transferred = int(last_line.split()[0])
                        progress = int((transferred / total_size) * 100)
                        self.progress.emit(progress)
                        elapsed_time = time.time() - self.start_time
                        if progress > 0:
                            remaining_time = int((elapsed_time / progress) * (100 - progress))
                            self.eta.emit(f"ETA: {remaining_time // 60}m {remaining_time % 60}s")
                    except ValueError:
                        pass

        self.progress.emit(100)
        self.finished.emit("Image successfully written." if self.process.returncode == 0 else "Failed to write image.")

    def stop(self):
        if self.process:
            self.process.terminate()


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('dd Image Writer for macOS')
        mainLayout = QVBoxLayout()

        btnLoadImage = QPushButton('Select Image', self)
        btnLoadImage.clicked.connect(self.openImageFileDialog)
        mainLayout.addWidget(btnLoadImage)

        self.imageLabel = QLabel('No image selected', self)
        mainLayout.addWidget(self.imageLabel)

        self.deviceCombo = QComboBox(self)
        mainLayout.addWidget(self.deviceCombo)
        self.populateDevices()

        buttonLayout = QHBoxLayout()
        btnWrite = QPushButton('Write Image', self)
        btnWrite.clicked.connect(self.startWriting)
        buttonLayout.addWidget(btnWrite)

        btnAbort = QPushButton('Abort Operation', self)
        btnAbort.clicked.connect(self.abortWriting)
        buttonLayout.addWidget(btnAbort)
        mainLayout.addLayout(buttonLayout)

        self.etaLabel = QLabel('ETA: --', self)
        mainLayout.addWidget(self.etaLabel)

        self.progressBar = QProgressBar(self)
        self.progressBar.setStyleSheet("QProgressBar {border: 2px solid grey; border-radius: 5px; text-align: center;}"
                                       "QProgressBar::chunk {background-color: green; width: 20px;}")
        mainLayout.addWidget(self.progressBar)

        self.setLayout(mainLayout)
        self.setGeometry(300, 300, 350, 200)
        self.show()

    def openImageFileDialog(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Select an Image File", "", 
                                                  "Image Files (*.img);;All Files (*)", options=options)
        if fileName:
            self.imageLabel.setText(f"Selected Image: {fileName}")

    def populateDevices(self):
        devices = list_mac_disks()
        for device in devices:
            self.deviceCombo.addItem(device)

    def startWriting(self):
        image_path = self.imageLabel.text().split(": ")[1]
        device_path = self.deviceCombo.currentText()
        password, okPressed = QInputDialog.getText(self, "Sudo Password", "Enter sudo password:", QLineEdit.Password)
        if okPressed and password:
            self.ddThread = DdThread(image_path, device_path, password)
            self.ddThread.progress.connect(self.updateProgress)
            self.ddThread.finished.connect(self.showMessage)
            self.ddThread.eta.connect(self.updateETA)
            self.ddThread.start()

    def abortWriting(self):
        if hasattr(self, 'ddThread'):
            self.ddThread.stop()

    def updateProgress(self, value):
        self.progressBar.setValue(value)

    def updateETA(self, text):
        self.etaLabel.setText(text)

    def showMessage(self, message):
        QMessageBox.information(self, "DD Operation", message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
