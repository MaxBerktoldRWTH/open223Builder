import sys

from PyQt5.QtWidgets import QApplication
from open223Builder.app.window import DiagramApplication


if __name__ == "__main__":

    app = QApplication(sys.argv)
    diagram_app = DiagramApplication()
    diagram_app.show()

    sys.exit(app.exec_())

