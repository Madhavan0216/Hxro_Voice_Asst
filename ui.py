from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt


class JarvisUI(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS")
        self.setStyleSheet("background-color: black; color: cyan;")

        self.setMinimumSize(800, 120)

        self.label = QLabel("Jarvis Online")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 24px;")
        self.label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

    def update_text(self, text: str) -> None:
        self.label.setText(text)
