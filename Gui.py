import sys
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QWidget,
                               QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
                               QComboBox, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox)

import OutOfTime

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

# Main settings window
class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('OutOfTime Settings')

        # Target
        self.target_label = QLabel('Target process name:')
        self.target_edit = QLineEdit()

        # Timeout
        self.timeout_label = QLabel('Timeout (seconds):')
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 86400)
        self.timeout_spin.setValue(3600)

        # Interval
        self.interval_label = QLabel('Interval (seconds):')
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setValue(10.0)

        # Remind
        self.remind_label = QLabel('Remind seconds before timeout:')
        self.remind_spin = QSpinBox()
        self.remind_spin.setRange(0, 86400)
        self.remind_spin.setValue(300)

        # Log level
        self.log_label = QLabel('Log level:')
        self.log_combo = QComboBox()
        self.log_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.log_combo.setCurrentText('INFO')

        # Start/Stop buttons
        self.start_button = QPushButton('Start')
        self.stop_button = QPushButton('Stop')
        self.stop_button.setEnabled(False)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.target_label)
        layout.addWidget(self.target_edit)

        layout.addWidget(self.timeout_label)
        layout.addWidget(self.timeout_spin)

        layout.addWidget(self.interval_label)
        layout.addWidget(self.interval_spin)

        layout.addWidget(self.remind_label)
        layout.addWidget(self.remind_spin)

        layout.addWidget(self.log_label)
        layout.addWidget(self.log_combo)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_button)
        btn_layout.addWidget(self.stop_button)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # Connect signals
        self.start_button.clicked.connect(self.start_monitor)
        self.stop_button.clicked.connect(self.stop_monitor)

    def start_monitor(self):
        target = self.target_edit.text().strip()
        if not target:
            QMessageBox.warning(self, 'Invalid Input', 'Please enter a target process name.')
            return

        timeout = int(self.timeout_spin.value())
        interval = float(self.interval_spin.value())
        remind = int(self.remind_spin.value())
        log_level = self.log_combo.currentText()

        try:
            thread = OutOfTime.start_monitor(target=target, timeout=timeout, interval=interval, remind=remind, log_level=log_level)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to start monitor: {e}')
            tray.showMessage('OutOfTime', f'Failed to start monitor: {e}')
            return

        if thread is None:
            tray.showMessage('OutOfTime', 'Monitor is already running')
        else:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            tray.showMessage('OutOfTime', f'Monitor started for {target}')

    def stop_monitor(self):
        ok = OutOfTime.stop_monitor()
        if ok:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            tray.showMessage('OutOfTime', 'Monitor stopped')
        else:
            tray.showMessage('OutOfTime', 'Monitor did not stop cleanly')


# Create the icon and system tray object
icon = QIcon('clock.png')  # Replace with your icon path
tray = QSystemTrayIcon()
tray.setIcon(icon)
tray.setVisible(True)

# Create the settings window instance
settings_window = SettingsWindow()

# Create the context menu with actions
menu = QMenu()
start_action = QAction('Start')
stop_action = QAction('Stop')
settings_action = QAction('Settings')
quit_action = QAction('Quit')

start_action.triggered.connect(settings_window.start_monitor)
stop_action.triggered.connect(settings_window.stop_monitor)
settings_action.triggered.connect(lambda: settings_window.show())

def quit_app():
    # Attempt to stop monitor before quitting
    OutOfTime.stop_monitor()
    tray.setVisible(False)
    app.quit()

quit_action.triggered.connect(quit_app)

menu.addAction(start_action)
menu.addAction(stop_action)
menu.addAction(settings_action)
menu.addSeparator()
menu.addAction(quit_action)

# Apply the menu and run
tray.setContextMenu(menu)

# Show initial message
tray.showMessage('OutOfTime', 'Application started. Use the settings to start monitoring.')

# If run directly, show the settings window for convenience
settings_window.show()

sys.exit(app.exec())
