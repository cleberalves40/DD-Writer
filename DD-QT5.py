import math
import os
import signal
import sys
import time

from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dd_writer import (
    estimate_remaining_seconds,
    list_devices,
    parse_dd_transferred_bytes,
    validate_write,
    write_image,
)


class DdThread(QThread):
    progress = pyqtSignal(int)
    eta = pyqtSignal(object)
    result = pyqtSignal(str)

    def __init__(self, image_path, device_path):
        super().__init__()
        self.image_path = image_path
        self.device_path = device_path
        self.process = None
        self.cancelled = False

    def run(self):
        output_lines = []
        try:
            if self.cancelled:
                self.result.emit("Operation cancelled.")
                return
            self.process, image_size = write_image(
                self.image_path, self.device_path
            )
            started_at = time.monotonic()
            if self.cancelled:
                self.stop()
            for line in self.process.stderr:
                output_lines.append(line.strip())
                output_lines = output_lines[-3:]
                transferred = parse_dd_transferred_bytes(line)
                if transferred is not None:
                    progress = min(99, int(transferred * 100 / image_size))
                    self.progress.emit(progress)
                    remaining = estimate_remaining_seconds(
                        image_size, transferred, time.monotonic() - started_at
                    )
                    if remaining is not None:
                        self.eta.emit(remaining)
            return_code = self.process.wait()
            if self.cancelled:
                self.eta.emit(None)
                self.result.emit("Operation cancelled.")
            elif return_code == 0:
                self.progress.emit(100)
                self.eta.emit("Completed")
                self.result.emit("Image successfully written.")
            else:
                self.eta.emit(None)
                detail = "\n".join(line for line in output_lines if line)
                self.result.emit(
                    f"Failed to write image (exit code {return_code})."
                    + (f"\n{detail}" if detail else "")
                )
        except (OSError, RuntimeError, ValueError) as error:
            self.eta.emit(None)
            self.result.emit(str(error))

    def stop(self):
        self.cancelled = True
        if self.process and self.process.poll() is None:
            if sys.platform.startswith("freebsd"):
                self.process.terminate()
                return
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                self.process.terminate()


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.image_path = None
        self.dd_thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("DD Image Writer")
        main_layout = QVBoxLayout()

        self.image_label = QLabel("No image selected")
        main_layout.addWidget(self.image_label)
        load_button = QPushButton("Select image")
        load_button.clicked.connect(self.open_image_file_dialog)
        main_layout.addWidget(load_button)

        device_layout = QHBoxLayout()
        self.device_combo = QComboBox()
        device_layout.addWidget(self.device_combo)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.populate_devices)
        device_layout.addWidget(refresh_button)
        main_layout.addLayout(device_layout)

        button_layout = QHBoxLayout()
        self.write_button = QPushButton("Write image")
        self.write_button.clicked.connect(self.start_writing)
        button_layout.addWidget(self.write_button)
        self.abort_button = QPushButton("Cancel")
        self.abort_button.clicked.connect(self.abort_writing)
        self.abort_button.setEnabled(False)
        button_layout.addWidget(self.abort_button)
        main_layout.addLayout(button_layout)

        self.status_label = QLabel()
        main_layout.addWidget(self.status_label)
        self.eta_label = QLabel("ETA: --")
        main_layout.addWidget(self.eta_label)
        self.eta_seconds = None
        self.eta_updated_at = None
        self.eta_timer = QTimer(self)
        self.eta_timer.setInterval(1000)
        self.eta_timer.timeout.connect(self.refresh_eta)
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)

        self.setLayout(main_layout)
        self.setGeometry(300, 300, 460, 220)
        self.populate_devices()
        self.show()

    def open_image_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select an image file",
            "",
            "Image Files (*.img *.iso);;All Files (*)",
        )
        if file_name:
            self.image_path = file_name
            self.image_label.setText(file_name)

    def populate_devices(self):
        self.device_combo.clear()
        try:
            devices = list_devices()
        except (OSError, RuntimeError) as error:
            self.status_label.setText(f"Could not list disks: {error}")
            return

        for device in devices:
            size_gib = device.size_bytes / (1024 ** 3)
            label = f"{device.path} - {device.description} ({size_gib:.1f} GiB)"
            self.device_combo.addItem(label, device.path)
        self.status_label.setText(
            "No unmounted external disks found."
            if not devices
            else "System and mounted disks are hidden."
        )

    def start_writing(self):
        if not self.image_path:
            QMessageBox.warning(self, "DD Image Writer", "Select an image first.")
            return
        device_path = self.device_combo.currentData()
        if not device_path:
            QMessageBox.warning(self, "DD Image Writer", "Select an available disk.")
            return
        try:
            image_size, device = validate_write(self.image_path, device_path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "DD Image Writer", str(error))
            self.populate_devices()
            return

        size_gib = image_size / (1024 ** 3)
        answer = QMessageBox.warning(
            self,
            "Erase selected disk?",
            f"This permanently erases all data on {device.path} "
            f"({device.description}).\n\nImage size: {size_gib:.2f} GiB",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return

        self.progress_bar.setValue(0)
        self.eta_label.setText("ETA: --")
        self.write_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.dd_thread = DdThread(self.image_path, device_path)
        self.dd_thread.progress.connect(self.progress_bar.setValue)
        self.dd_thread.eta.connect(self.update_eta)
        self.dd_thread.result.connect(self.show_message)
        self.dd_thread.finished.connect(self.operation_finished)
        self.dd_thread.start()

    def abort_writing(self):
        if self.dd_thread and self.dd_thread.isRunning():
            self.status_label.setText("Cancelling write...")
            self.abort_button.setEnabled(False)
            self.dd_thread.stop()

    def operation_finished(self):
        self.write_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.populate_devices()

    def update_eta(self, estimate):
        if estimate == "Completed":
            self.eta_timer.stop()
            self.eta_seconds = None
            self.eta_updated_at = None
            self.eta_label.setText("Completed")
            return
        if estimate is None:
            self.eta_timer.stop()
            self.eta_seconds = None
            self.eta_updated_at = None
            self.eta_label.setText("ETA: --")
            return

        self.eta_seconds = max(0.0, float(estimate))
        self.eta_updated_at = time.monotonic()
        self.refresh_eta()
        if not self.eta_timer.isActive():
            self.eta_timer.start()

    def refresh_eta(self):
        if self.eta_updated_at is None:
            return
        remaining = max(
            0,
            math.ceil(
                self.eta_seconds - (time.monotonic() - self.eta_updated_at)
            ),
        )
        self.eta_label.setText(f"ETA: {remaining // 60}m {remaining % 60:02d}s")

    def show_message(self, message):
        QMessageBox.information(self, "DD Operation", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    sys.exit(app.exec_())