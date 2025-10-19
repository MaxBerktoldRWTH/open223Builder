import sys
from open223Builder.core import DiagramApplication, QApplication

app = QApplication(sys.argv)
diagram_app = DiagramApplication()
diagram_app.show()

sys.exit(app.exec_())

