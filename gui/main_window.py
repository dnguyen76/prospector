from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class EntrepriseSearchApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prospector V2")
        self.resize(900, 700)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Prospector V2 - architecture initialisée"))
        self.setLayout(layout)