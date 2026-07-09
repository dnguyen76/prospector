import sys
from PyQt6.QtWidgets import QApplication

from gui.main_window import EntrepriseSearchApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Prospector V2")
    window = EntrepriseSearchApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()