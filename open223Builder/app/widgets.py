from PyQt5.QtWidgets import (
    QFormLayout, QLabel, QLineEdit, QPushButton, QComboBox, QDialog, QDoubleSpinBox,
)

import open223Builder.enumerations as enums
from open223Builder.library import connection_point_library
from open223Builder.app.dialogs import RelationshipDialog, AddPropertyDialog, AddConnectionPointDialog
from open223Builder.app.items import *


class BasePropertyPanel(QFormLayout):
    def __init__(self):
        super().__init__()

        self.label = QLineEdit()
        self.label.setPlaceholderText("Enter label")
        self.label.editingFinished.connect(self.on_label_changed)
        self.addRow(QLabel("<b>rdfs.label:</b>"), self.label)

        self.comment = QLineEdit()
        self.comment.setPlaceholderText("Enter comment")
        self.comment.editingFinished.connect(self.on_comment_changed)
        self.addRow(QLabel("<b>rdfs.comment:</b>"), self.comment)

        self.selected_items = []

    def on_label_changed(self):
        if not self.selected_items: return
        new_label = str(self.label.text())
        scene = self.selected_items[0].scene()

        command = ChangeAttributeCommand(self.selected_items, 'label', new_label)
        push_command_to_scene(scene, command)

    def on_comment_changed(self):
        if not self.selected_items: return
        new_comment = str(self.comment.text())
        scene = self.selected_items[0].scene()

        command = ChangeAttributeCommand(self.selected_items, 'comment', new_comment)
        push_command_to_scene(scene, command)

    def _hide(self):
        for i in range(self.rowCount()):
            row_widget = self.itemAt(i, QFormLayout.SpanningRole)
            if row_widget and row_widget.widget():
                row_widget.widget().hide()
                continue

            label_item = self.itemAt(i, QFormLayout.LabelRole)
            field_item = self.itemAt(i, QFormLayout.FieldRole)

            if label_item and label_item.widget():
                label_item.widget().hide()
            if field_item and field_item.widget():
                field_item.widget().hide()

    def _show(self):
        for i in range(self.rowCount()):
            row_widget = self.itemAt(i, QFormLayout.SpanningRole)
            if row_widget and row_widget.widget():
                row_widget.widget().show()
                continue

            label_item = self.itemAt(i, QFormLayout.LabelRole)
            field_item = self.itemAt(i, QFormLayout.FieldRole)

            if label_item and label_item.widget():
                label_item.widget().show()
            if field_item and field_item.widget():
                field_item.widget().show()


class ConnectableProperties(BasePropertyPanel):

    def _setup_advanced_controls(self):

        self.add_connection_button = QPushButton("Add Connection Point")
        self.add_connection_button.clicked.connect(self._on_add_connection_clicked)
        self.addRow("", self.add_connection_button)

        self.manage_relationships_btn = QPushButton("Manage Relationships...")
        self.manage_relationships_btn.clicked.connect(self._on_manage_relationships)
        self.addRow("", self.manage_relationships_btn)

        self.add_property_button = QPushButton("Add Property")
        self.add_property_button.clicked.connect(self._on_add_property_clicked)
        self.addRow("", self.add_property_button)

    def _on_add_property_clicked(self):

        if not self.selected_items or len(self.selected_items) != 1:
            return

        connectable = self.selected_items[0]
        dialog = AddPropertyDialog(connectable)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            property_data = dialog.get_property_data()

            command = AddPropertyCommand(connectable, property_data)
            scene = connectable.scene()
            push_command_to_scene(scene, command)

    def update_properties(self, selection: Selection):

        equipment_selection = Selection([
            item for item in selection.getConnectable
            if not isinstance(item, (DomainSpace, PhysicalSpace))
        ])

        if equipment_selection.isEmpty:
            self._hide()

            if hasattr(self, 'add_property_button'): self.add_property_button.hide()

            self.selected_items = []
            return

        self._show()

        if hasattr(self, 'add_property_button'): self.add_property_button.show()

        self.selected_items = equipment_selection

        if len(equipment_selection) == 1:
            self.update_single_connectable(equipment_selection.last)
        else:
            self.update_multiple_connectable(equipment_selection)

    def update_single_connectable(self, item: ConnectableItem):

        self.instance_uri.setText(to_label(item.inst_uri))
        self.type_uri.setText(to_label(item.type_uri))
        self.position.setText(f"{item.x():.1f}, {item.y():.1f}")
        self.rotation.setText(f"{item.rotation()}")
        self.label.setText(f'{item.label}')

        role_index = self.role.findData(str(item.role))
        self.role.blockSignals(True)
        self.role.setCurrentIndex(role_index if role_index != -1 else 0)
        self.role.blockSignals(False)

        self.add_connection_button.setEnabled(True)
        self.manage_relationships_btn.setEnabled(True)
        self.rotate_90_button.setEnabled(True)
        self.rotation.setEnabled(True)
        self.role.setEnabled(True)

        if hasattr(self, 'add_property_button'): self.add_property_button.setEnabled(True)

    def update_multiple_connectable(self, items):

        self.instance_uri.setText("Multiselection")
        self.type_uri.setText("Multiselection")
        self.position.setText("Multiselection")
        self.rotation.clear();
        self.rotation.setPlaceholderText("Multiselection")
        self.label.clear();
        self.label.setPlaceholderText("Multiselection")

        self.role.blockSignals(True);
        self.role.setCurrentIndex(0);
        self.role.blockSignals(False)
        self.role.setEnabled(True)

        self.add_connection_button.setEnabled(False)
        self.manage_relationships_btn.setEnabled(False)
        self.rotate_90_button.setEnabled(True)
        self.rotation.setEnabled(True)

        if hasattr(self, 'add_property_button'): self.add_property_button.setEnabled(False)

    def _on_manage_relationships(self):

        if not self.selected_items or len(self.selected_items) != 1:
            return

        item = self.selected_items[0]
        scene = item.scene()
        if not scene: return

        view = scene.views()[0] if scene.views() else None
        if hasattr(view, "_show_relationship_dialog"):
            view._show_relationship_dialog(item)

        else:

            dialog = RelationshipDialog(item, scene)
            dialog.exec_()

    def __init__(self):
        super().__init__()
        self._setup_standard_properties()
        self._setup_rotation_controls()
        self._setup_advanced_controls()
        self._hide()

    def _setup_standard_properties(self):
        self.instance_uri = QLabel("No entity selected")
        self.addRow(QLabel("<b>instance:</b>"), self.instance_uri)

        self.type_uri = QLabel("No entity selected")
        self.addRow(QLabel("<b>rdfs.type:</b>"), self.type_uri)

        self.position = QLabel("No entity selected")
        self.addRow(QLabel("<b>viz.position:</b>"), self.position)

        self._setup_role_selector()

    def _setup_role_selector(self):
        self.role = QComboBox()
        self.role.addItem("Please select role", userData=None)
        for role_uri in enums.roles:
            self.role.addItem(to_label(role_uri), userData=str(role_uri))
        self.role.currentIndexChanged.connect(self._on_role_changed)
        self.addRow(QLabel("<b>s223.hasRole:</b>"), self.role)

    def _setup_rotation_controls(self):
        self.rotation = QLineEdit()
        self.rotation.setPlaceholderText("Enter degrees")
        self.rotation.editingFinished.connect(self._on_rotation_changed)
        self.addRow(QLabel("<b>viz.rotation:</b>"), self.rotation)

        self.rotate_90_button = QPushButton("Rotate 90°")
        self.rotate_90_button.clicked.connect(self._on_rotate_90_clicked)
        self.addRow("", self.rotate_90_button)

    def _on_rotation_changed(self):
        try:
            rotation = float(self.rotation.text())
        except ValueError:
            return

        if not self.selected_items:
            return

        old_rotations = [item.rotation() for item in self.selected_items]
        new_rotations = [rotation for _ in self.selected_items]

        scene = self.selected_items[0].scene()
        if scene:
            command = RotateCommand(self.selected_items, old_rotations, new_rotations)
            push_command_to_scene(scene, command)

    def _on_rotate_90_clicked(self):
        if not self.selected_items:
            return

        old_rotations = [item.rotation() for item in self.selected_items]
        new_rotations = [item.rotation() + 90 for item in self.selected_items]

        scene = self.selected_items[0].scene()

        command = RotateCommand(self.selected_items, old_rotations, new_rotations)
        push_command_to_scene(scene, command)

        if len(self.selected_items) == 1:
            self.rotation.setText(f"{self.selected_items[0].rotation()}")

    def _on_add_connection_clicked(self):
        if not self.selected_items or len(self.selected_items) != 1:
            return

        connectable = self.selected_items[0]
        dialog = AddConnectionPointDialog(connectable)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            data = dialog.get_connection_point_data()

            cp = ConnectionPoint(
                connectable=connectable,
                position=(data['position_x'], data['position_y']),
                medium=data['medium'],
                type_uri=data['type_uri']
            )

            command = AddConnectionPointCommand(cp)

            scene = connectable.scene()
            if scene and hasattr(scene.views()[0], 'command_history'):
                push_command_to_scene(scene, command)

    def _on_role_changed(self, index):
        if not self.selected_items:
            return

        role_str = self.role.itemData(index)
        role_uri = None if role_str is None else rdflib.URIRef(role_str)

        if role_uri is None:
            return

        for item in self.selected_items:
            item.role = role_uri


class PropertyProperties(BasePropertyPanel):

    def __init__(self):
        super().__init__()

        self.instance_uri = QLabel("No property selected")
        self.addRow(QLabel("<b>instance:</b>"), self.instance_uri)

        self.property_type = QComboBox()

        for p_type in Property.allowed_types:
            self.property_type.addItem(to_label(p_type), userData=str(p_type))
        self.property_type.currentIndexChanged.connect(self.on_property_type_changed)
        self.addRow(QLabel("<b>Property Type:</b>"), self.property_type)

        self.identifier = QLineEdit()
        self.identifier.setMaxLength(1)
        self.identifier.editingFinished.connect(self.on_identifier_changed)
        self.addRow(QLabel("<b>Identifier (Letter):</b>"), self.identifier)

        self.aspect = QComboBox()
        self.aspect.addItem("Select aspect", userData=None)
        for aspect_uri in enums.aspects:
            self.aspect.addItem(to_label(aspect_uri), userData=str(aspect_uri))
        self.aspect.currentIndexChanged.connect(self.on_aspect_changed)
        self.addRow(QLabel("<b>Aspect:</b>"), self.aspect)

        self.medium = QComboBox()
        self.medium.addItem("Select medium", userData=None)
        for medium_uri in medium_library:
            self.medium.addItem(to_label(medium_uri), userData=str(medium_uri))
        self.medium.currentIndexChanged.connect(self.on_medium_changed)
        self.addRow(QLabel("<b>Medium:</b>"), self.medium)

        self.unit = QComboBox()
        self.unit.addItem("Select Unit", userData=None)
        for unit_uri in enums.units:
            self.unit.addItem(to_label(unit_uri), userData=str(unit_uri))
        self.unit.currentIndexChanged.connect(self.on_unit_changed)
        self.addRow(QLabel("<b>QUDT Unit:</b>"), self.unit)

        self.quantity_kind = QComboBox()
        self.quantity_kind.addItem("Select Quantity Kind", userData=None)
        for qk_uri in enums.quantity_kinds:
            self.quantity_kind.addItem(to_label(qk_uri), userData=str(qk_uri))
        self.quantity_kind.currentIndexChanged.connect(self.on_quantity_kind_changed)
        self.addRow(QLabel("<b>QUDT Quantity Kind:</b>"), self.quantity_kind)

        self.external_reference = QLineEdit()
        self.external_reference.editingFinished.connect(self.on_external_reference_changed)
        self.addRow(QLabel("<b>External Reference:</b>"), self.external_reference)

        self.internal_reference = QLineEdit()
        self.internal_reference.editingFinished.connect(self.on_internal_reference_changed)
        self.addRow(QLabel("<b>Internal Reference:</b>"), self.internal_reference)

        self.value = QLineEdit()
        self.value.editingFinished.connect(self.on_value_changed)
        self.addRow(QLabel("<b>Value:</b>"), self.value)

        self._hide()

    def update_properties(self, selection: Selection):

        properties = selection.getProperty

        if not properties:
            self._hide()
            self.selected_items = []
            return

        self._show()
        self.selected_items = properties

        if len(properties) == 1:
            self.update_single_property(properties[0])
        else:
            self.update_multiple_properties(properties)

    def update_single_property(self, item: Property):

        self.instance_uri.setText(to_label(item.inst_uri))
        self.label.setText(item.label)
        self.label.setPlaceholderText("Enter label")
        self.comment.setText(item.comment)
        self.comment.setPlaceholderText("Enter comment")

        self.property_type.blockSignals(True)
        index = self.property_type.findData(str(item.property_type))
        self.property_type.setCurrentIndex(index if index != -1 else 0)
        self.property_type.setEnabled(True)
        self.property_type.blockSignals(False)

        self.identifier.setText(item.identifier)
        self.identifier.setEnabled(True)

        self.aspect.blockSignals(True)
        index = self.aspect.findData(str(item.aspect))
        self.aspect.setCurrentIndex(index if index != -1 else 0)
        self.aspect.setEnabled(True)
        self.aspect.blockSignals(False)

        self.medium.blockSignals(True)
        index = self.medium.findData(str(item.medium))
        self.medium.setCurrentIndex(index if index != -1 else 0)
        self.medium.setEnabled(True)
        self.medium.blockSignals(False)

        self.unit.blockSignals(True)
        index = self.unit.findData(str(item.unit))
        self.unit.setCurrentIndex(index if index != -1 else 0)
        self.unit.setEnabled(True)
        self.unit.blockSignals(False)

        self.quantity_kind.blockSignals(True)
        index = self.quantity_kind.findData(str(item.quantity_kind))
        self.quantity_kind.setCurrentIndex(index if index != -1 else 0)
        self.quantity_kind.setEnabled(True)
        self.quantity_kind.blockSignals(False)

        self.external_reference.setText(item.external_reference)
        self.external_reference.setEnabled(True)
        self.internal_reference.setText(item.internal_reference or "")
        self.internal_reference.setEnabled(True)
        self.value.setText(str(item.value))
        self.value.setEnabled(True)

    def update_multiple_properties(self, items: Selection):

        self.instance_uri.setText("Multiselection")
        self.label.setText("")
        self.label.setPlaceholderText("Multiselection")
        self.comment.setText("")
        self.comment.setPlaceholderText("Multiselection")

        self.property_type.blockSignals(True)
        self.property_type.setCurrentIndex(-1)
        self.property_type.setEnabled(True)
        self.property_type.blockSignals(False)

        self.identifier.setText("")
        self.identifier.setPlaceholderText("Multi")
        self.identifier.setEnabled(True)

        self.aspect.blockSignals(True)
        self.aspect.setCurrentIndex(-1)
        self.aspect.setEnabled(True)
        self.aspect.blockSignals(False)

        self.medium.blockSignals(True)
        self.medium.setCurrentIndex(-1)
        self.medium.setEnabled(True)
        self.medium.blockSignals(False)

        self.unit.blockSignals(True)
        self.unit.setCurrentIndex(-1)
        self.unit.setEnabled(True)
        self.unit.blockSignals(False)

        self.quantity_kind.blockSignals(True)
        self.quantity_kind.setCurrentIndex(-1)
        self.quantity_kind.setEnabled(True)
        self.quantity_kind.blockSignals(False)

        self.external_reference.setText("")
        self.external_reference.setPlaceholderText("Multiselection")
        self.external_reference.setEnabled(True)
        self.internal_reference.setText("")
        self.internal_reference.setPlaceholderText("Multiselection")
        self.internal_reference.setEnabled(True)
        self.value.setText("")
        self.value.setPlaceholderText("Multiselection")
        self.value.setEnabled(True)

    def on_unit_changed(self, index):
        if not self.selected_items:
            return
        new_unit = self.unit.itemData(index)
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'unit', rdflib.URIRef(new_unit))
        push_command_to_scene(scene, command)

    def on_quantity_kind_changed(self, index):
        if not self.selected_items:
            return
        new_qk = self.quantity_kind.itemData(index)
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'quantity_kind', rdflib.URIRef(new_qk))
        push_command_to_scene(scene, command)

    def on_property_type_changed(self, index):

        if not self.selected_items:
            return
        new_type = self.property_type.itemData(index)

        if new_type is None:
            return
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'property_type', rdflib.URIRef(new_type))
        push_command_to_scene(scene, command)

    def on_identifier_changed(self):
        if not self.selected_items: return
        new_id = self.identifier.text()[:1] or "P"
        scene = self.selected_items[0].scene()

        command = ChangeAttributeCommand(self.selected_items, 'identifier', new_id,
                                         update_func=lambda item: item.update())
        push_command_to_scene(scene, command)

        if len(self.selected_items) == 1:
            self.identifier.setText(new_id)

    def on_aspect_changed(self, index):
        if not self.selected_items: return
        new_aspect = self.aspect.itemData(index)
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'aspect', new_aspect)
        push_command_to_scene(scene, command)

    def on_medium_changed(self, index):
        if not self.selected_items: return
        new_medium = self.medium.itemData(index)
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'medium', new_medium)
        push_command_to_scene(scene, command)

    def on_external_reference_changed(self):
        if not self.selected_items: return
        new_ref = self.external_reference.text()
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'external_reference', new_ref)
        push_command_to_scene(scene, command)

    def on_internal_reference_changed(self):
        if not self.selected_items: return
        new_ref = self.internal_reference.text()
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'internal_reference', new_ref)
        push_command_to_scene(scene, command)

    def on_value_changed(self):
        if not self.selected_items: return
        new_val = self.value.text()
        scene = self.selected_items[0].scene()
        command = ChangeAttributeCommand(self.selected_items, 'value', new_val)
        push_command_to_scene(scene, command)


class DomainSpaceProperties(BasePropertyPanel):
    def __init__(self):
        super().__init__()

        self.instance_uri = QLabel("No domain space selected")
        self.addRow(QLabel("<b>instance:</b>"), self.instance_uri)

        self.type_uri = QLabel("s223:DomainSpace")
        self.addRow(QLabel("<b>rdfs:type:</b>"), self.type_uri)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(DomainSpace.MIN_SIZE, 5000)
        self.width_spin.setSingleStep(10)
        self.width_spin.setDecimals(0)
        self.width_spin.valueChanged.connect(self._on_size_changed)
        self.addRow(QLabel("<b>Width:</b>"), self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(DomainSpace.MIN_SIZE, 5000)
        self.height_spin.setSingleStep(10)
        self.height_spin.setDecimals(0)
        self.height_spin.valueChanged.connect(self._on_size_changed)
        self.addRow(QLabel("<b>Height:</b>"), self.height_spin)

        self.domain = QComboBox()
        self.domain.addItem("Please select domain", userData=None)
        for domain_uri in enums.domains:
            self.domain.addItem(to_label(domain_uri), userData=str(domain_uri))
        self.domain.currentIndexChanged.connect(self._on_domain_changed)
        self.addRow(QLabel("<b>s223.hasDomain:</b>"), self.domain)

        self._hide()

    def update_properties(self, selection: Selection):
        domain_spaces = selection.getDomainSpace

        if not domain_spaces:
            self._hide()
            self.selected_items = []
            return

        self._show()
        self.selected_items = domain_spaces

        if len(domain_spaces) == 1:
            self.update_single_domain_space(domain_spaces[0])
        else:
            self.update_multiple_domain_spaces(domain_spaces)

    def update_single_domain_space(self, item: DomainSpace):
        self.instance_uri.setText(to_label(item.inst_uri))
        self.label.setText(item.label)
        self.label.setPlaceholderText("Enter label")

        self.width_spin.blockSignals(True)
        self.width_spin.setValue(item.width)
        self.width_spin.setEnabled(True)
        self.width_spin.blockSignals(False)

        self.height_spin.blockSignals(True)
        self.height_spin.setValue(item.height)
        self.height_spin.setEnabled(True)
        self.height_spin.blockSignals(False)

        self.domain.blockSignals(True)
        role_str = str(item.role) if item.role else None
        index = self.domain.findData(role_str)
        self.domain.setCurrentIndex(index if index != -1 else 0)
        self.domain.setEnabled(True)
        self.domain.blockSignals(False)

    def update_multiple_domain_spaces(self, items):
        self.instance_uri.setText("Multiselection")
        self.label.setText("")
        self.label.setPlaceholderText("Multiselection")

        self.width_spin.blockSignals(True)
        self.width_spin.setValue(0)
        self.width_spin.setEnabled(False)
        self.width_spin.blockSignals(False)

        self.height_spin.blockSignals(True)
        self.height_spin.setValue(0)
        self.height_spin.setEnabled(False)
        self.height_spin.blockSignals(False)

        self.domain.blockSignals(True)
        self.domain.setCurrentIndex(-1)
        self.domain.setEnabled(True)
        self.domain.blockSignals(False)

    def _on_size_changed(self):

        if not self.selected_items or len(self.selected_items) != 1:
            return

        item = self.selected_items[0]
        new_width = self.width_spin.value()
        new_height = self.height_spin.value()

        if new_width == item.width and new_height == item.height:
            return

        scene = item.scene()
        if scene:
            old_size = (item.width, item.height)
            new_size = (new_width, new_height)

            command = ResizeCommand(item, old_size, new_size)
            push_command_to_scene(scene, command)

    def _on_domain_changed(self, index):
        if not self.selected_items:
            return

        domain_str = self.domain.itemData(index)
        new_domain = rdflib.URIRef(domain_str) if domain_str else None

        scene = self.selected_items[0].scene()
        if scene:
            command = ChangeAttributeCommand(self.selected_items, 'domain', new_domain)
            push_command_to_scene(scene, command)


class ConnectionProperties(BasePropertyPanel):
    def __init__(self):
        super().__init__()

        self.instance_uri = QLabel("No entity selected")
        self.addRow(QLabel("<b>instance:</b>"), self.instance_uri)

        self.type_uri = QComboBox()
        for connection_uri in connection_library:
            self.type_uri.addItem(to_label(connection_uri), userData=str(connection_uri))
        self.type_uri.currentIndexChanged.connect(self.on_type_uri_changed)
        self.addRow(QLabel("<b>rdfs.type:</b>"), self.type_uri)

        self.medium = QComboBox()
        for medium_uri in medium_library:
            self.medium.addItem(to_label(medium_uri), userData=str(medium_uri))
        self.medium.currentIndexChanged.connect(self.on_medium_changed)
        self.addRow(QLabel("<b>s223.hasMedium:</b>"), self.medium)

        self.source_uri = QLabel("No entity selected")
        self.addRow(QLabel("<b>s223.connectsAt:</b>"), self.source_uri)

        self.target_uri = QLabel("No entity selected")
        self.addRow(QLabel("<b>s223.connectsAt:</b>"), self.target_uri)

        self._hide()

    def update_properties(self, selection: Selection):
        if selection.isEmpty or not selection.onlyConnection:
            self._hide()
            return

        self._show()
        self.selected_items = selection.getConnection

        if len(self.selected_items) == 1:
            self.update_single_connection(self.selected_items[0])
        else:
            self.update_multiple_connections(self.selected_items)

    def on_type_uri_changed(self, index):
        if not Selection(self.selected_items).onlyConnection:
            return

        new_type_uri_str = self.type_uri.itemData(index)
        if new_type_uri_str is None:
            return

        new_type_uri = rdflib.URIRef(new_type_uri_str)

        scene = self.selected_items[0].scene()
        if scene and hasattr(scene.views()[0], 'command_history'):
            command = ChangeConnectionTypeCommand(self.selected_items, new_type_uri)
            push_command_to_scene(scene, command)

    def on_medium_changed(self, index):
        if not Selection(self.selected_items).onlyConnection:
            return

        new_medium_str = self.medium.itemData(index)
        if new_medium_str is None:
            return

        new_medium = rdflib.URIRef(new_medium_str)

        scene = self.selected_items[0].scene()
        if scene and hasattr(scene.views()[0], 'command_history'):
            command = ChangeConnectionMediumCommand(self.selected_items, new_medium)
            push_command_to_scene(scene, command)

    def update_single_connection(self, connection: Connection):
        self.instance_uri.setText(to_label(connection.inst_uri))

        medium_index = self.medium.findData(str(connection.source.medium))
        if medium_index != -1:
            self.medium.setCurrentIndex(medium_index)

        type_uri_index = self.type_uri.findData(str(connection.type_uri))
        if type_uri_index != -1:
            self.type_uri.setCurrentIndex(type_uri_index)

        self.source_uri.setText(to_label(connection.source.inst_uri))
        self.target_uri.setText(to_label(connection.target.inst_uri))

    def update_multiple_connections(self, connections):
        self.instance_uri.setText("Multiselection")
        self.source_uri.setText("Multiselection")
        self.target_uri.setText("Multiselection")

        self.type_uri.blockSignals(True)
        self.type_uri.setCurrentIndex(-1)
        self.type_uri.blockSignals(False)

        self.medium.blockSignals(True)
        self.medium.setCurrentIndex(-1)
        self.medium.blockSignals(False)


class ConnectionPointProperties(BasePropertyPanel):

    def __init__(self):
        super().__init__()

        self.instance_uri = QLabel("No entity selected")
        self.addRow(QLabel("<b>instance:</b>"), self.instance_uri)

        self.type_uri = QComboBox()
        for connection in connection_point_library:
            self.type_uri.addItem(to_label(connection), userData=str(connection))
        self.type_uri.currentIndexChanged.connect(self.on_type_uri_changed)
        self.addRow(QLabel("<b>rdfs.type:</b>"), self.type_uri)

        self.connected_to = QLabel("No entity selected")
        self.addRow(QLabel("<b>s223.connectsThrough:</b>"), self.connected_to)

        self.medium = QComboBox()
        for medium_uri in medium_library:
            self.medium.addItem(to_label(medium_uri), userData=str(medium_uri))
        self.medium.currentIndexChanged.connect(self.on_medium_changed)
        self.addRow(QLabel("<b>s223.hasMedium:</b>"), self.medium)

        self.position_x = QDoubleSpinBox()
        self.position_x.setRange(0.0, 1.0)
        self.position_x.setSingleStep(0.1)
        self.position_x.setDecimals(2)
        self.position_x.valueChanged.connect(self.on_position_changed)
        self.addRow(QLabel("<b>viz.position_x:</b>"), self.position_x)

        self.position_y = QDoubleSpinBox()
        self.position_y.setRange(0.0, 1.0)
        self.position_y.setSingleStep(0.1)
        self.position_y.setDecimals(2)
        self.position_y.valueChanged.connect(self.on_position_changed)
        self.addRow(QLabel("<b>viz.position_y</b>"), self.position_y)

        self.add_property_button = QPushButton("Add Property")
        self.add_property_button.clicked.connect(self._on_add_property_clicked)
        self.addRow("", self.add_property_button)

        self._hide()

    def update_properties(self, selection: Selection):
        connection_points_selection = selection.getConnectionPoint

        if connection_points_selection.isEmpty:
            self._hide()

            self.add_property_button.hide()

            self.selected_items = []
            return

        self._show()

        self.add_property_button.show()

        self.selected_items = connection_points_selection

        if len(self.selected_items) == 1:
            self.update_single_point(self.selected_items[0])
        else:
            self.update_multiple_points(self.selected_items)

    def update_single_point(self, item: ConnectionPoint):
        self.instance_uri.setText(to_label(item.inst_uri))
        self.label.setText(item.label)
        self.comment.setText(item.comment)

        index = self.type_uri.findData(str(item.type_uri))
        self.type_uri.blockSignals(True)
        self.type_uri.setCurrentIndex(index if index != -1 else 0)
        self.type_uri.blockSignals(False)

        self.medium.blockSignals(True)
        if item.medium is None:
            self.medium.setCurrentIndex(0)
        else:
            index = self.medium.findData(str(item.medium))
            self.medium.setCurrentIndex(index if index != -1 else 0)
        self.medium.blockSignals(False)

        self.position_x.blockSignals(True)
        self.position_y.blockSignals(True)
        self.position_x.setValue(item.relative_x)
        self.position_y.setValue(item.relative_y)
        self.position_x.blockSignals(False)
        self.position_y.blockSignals(False)
        self.position_x.setDisabled(False)
        self.position_y.setDisabled(False)

        has_connection = item.connected_to is not None
        self.type_uri.setDisabled(has_connection)
        self.medium.setDisabled(has_connection)

        if has_connection:
            self.connected_to.setText(to_label(item.connected_to.inst_uri))
        else:
            self.connected_to.setText("No connection")

        self.add_property_button.setEnabled(True)

    def update_multiple_points(self, connection_points):
        self.instance_uri.setText("Multiselection")
        self.label.setText("")
        self.label.setPlaceholderText("Multiselection")
        self.comment.setText("")
        self.comment.setPlaceholderText("Multiselection")

        self.type_uri.blockSignals(True)
        self.type_uri.setCurrentIndex(-1)
        self.type_uri.blockSignals(False)
        self.type_uri.setDisabled(False)

        self.medium.blockSignals(True)
        self.medium.setCurrentIndex(-1)
        self.medium.blockSignals(False)
        self.medium.setDisabled(False)

        self.position_x.blockSignals(True)
        self.position_y.blockSignals(True)
        self.position_x.setValue(0.0)
        self.position_y.setValue(0.0)
        self.position_x.blockSignals(False)
        self.position_y.blockSignals(False)
        self.position_x.setDisabled(True)
        self.position_y.setDisabled(True)

        self.connected_to.setText("N/A")

        self.add_property_button.setEnabled(False)

    def _on_add_property_clicked(self):

        if not self.selected_items or len(self.selected_items) != 1:
            return

        connection_point = self.selected_items[0]

        dialog = AddPropertyDialog(connection_point)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            property_data = dialog.get_property_data()

            command = AddPropertyCommand(connection_point, property_data)
            scene = connection_point.scene()
            push_command_to_scene(scene, command)

    def on_type_uri_changed(self, index):
        if not self.selected_items:
            return

        type_uri_str = self.type_uri.itemData(index)
        if type_uri_str is None:
            return

        type_uri = rdflib.URIRef(type_uri_str)

        scene = self.selected_items[0].scene()
        if scene and hasattr(scene.views()[0], 'command_history'):
            class ChangeConnectionPointTypeCommand(Command):
                def __init__(self, points, new_type_uri):
                    self.points = [p for p in points if p.connected_to is None]
                    self.new_type_uri = new_type_uri
                    self.old_type_uris = [p.type_uri for p in self.points]

                def _execute(self):
                    for point in self.points:
                        point.type_uri = self.new_type_uri

                def _undo(self):
                    for i, point in enumerate(self.points):
                        point.type_uri = self.old_type_uris[i]

            command = ChangeConnectionPointTypeCommand(self.selected_items, type_uri)
            push_command_to_scene(scene, command)

    def on_medium_changed(self, index):
        if not self.selected_items:
            return

        medium_str = self.medium.itemData(index)
        if medium_str is None:
            return

        medium = rdflib.URIRef(medium_str)

        scene = self.selected_items[0].scene()
        if scene and hasattr(scene.views()[0], 'command_history'):
            class ChangeConnectionPointMediumCommand(Command):
                def __init__(self, points, new_medium):
                    self.points = [p for p in points if p.connected_to is None]
                    self.new_medium = new_medium
                    self.old_media = [p.medium for p in self.points]

                def _execute(self):
                    for point in self.points:
                        point.medium = self.new_medium

                def _undo(self):
                    for i, point in enumerate(self.points):
                        point.medium = self.old_media[i]

            command = ChangeConnectionPointMediumCommand(self.selected_items, medium)
            push_command_to_scene(scene, command)

    def on_position_changed(self):
        if not self.selected_items or len(self.selected_items) != 1:
            return

        item = self.selected_items[0]
        new_x = self.position_x.value()
        new_y = self.position_y.value()

        scene = item.scene()
        if scene and hasattr(scene.views()[0], 'command_history'):
            class ChangeConnectionPointPositionCommand(Command):
                def __init__(self, point, new_x, new_y):
                    self.point = point
                    self.new_x = new_x
                    self.new_y = new_y
                    self.old_x = point.relative_x
                    self.old_y = point.relative_y

                def _execute(self):
                    self.point.set_relative_position(self.new_x, self.new_y)

                def _undo(self):
                    self.point.set_relative_position(self.old_x, self.old_y)

            command = ChangeConnectionPointPositionCommand(item, new_x, new_y)
            push_command_to_scene(scene, command)


class SystemProperties(BasePropertyPanel):
    def __init__(self):
        super().__init__()

        self.instance_uri = QLabel("No system selected")
        self.addRow(QLabel("<b>instance:</b>"), self.instance_uri)

        self.type_uri = QLabel("s223:System")
        self.addRow(QLabel("<b>rdfs:type:</b>"), self.type_uri)

        self.member_count = QLabel("0")
        self.addRow(QLabel("<b>s223:hasMember (Count):</b>"), self.member_count)

        self.role = QComboBox()
        self.role.addItem("Please select role", userData=None)
        for role_uri in enums.roles:
            self.role.addItem(to_label(role_uri), userData=str(role_uri))
        self.role.currentIndexChanged.connect(self._on_role_changed)
        self.addRow(QLabel("<b>s223.hasDomain:</b>"), self.role)

        self._hide()

    def update_properties(self, selection: Selection):
        if selection.isEmpty or not all(isinstance(item, SystemItem) for item in selection):
            self._hide()
            self.selected_items = []
            return

        self._show()
        self.selected_items = selection

        if len(selection) == 1:
            self.update_single_system(selection[0])
        else:
            self.update_multiple_systems(selection)

    def update_single_system(self, item: SystemItem):
        self.instance_uri.setText(to_label(item.inst_uri))
        self.label.setText(item.label)
        self.label.setPlaceholderText("Enter label")
        self.member_count.setText(str(len(item.members)))

        self.role.blockSignals(True)
        if item.role is None:
            self.role.setCurrentIndex(0)
        else:
            role_index = self.role.findData(str(item.role))
            if role_index != -1:
                self.role.setCurrentIndex(role_index)
            else:
                self.role.setCurrentIndex(0)
        self.role.blockSignals(False)

    def update_multiple_systems(self, items: Selection):
        self.instance_uri.setText("Multiselection")
        self.label.setText("")
        self.label.setPlaceholderText("Multiselection")
        self.member_count.setText("Multiselection")
        self.role.setCurrentIndex(0)

    def _on_role_changed(self, index):
        if not self.selected_items:
            return

        role_str = self.role.itemData(index)
        role_uri = None if role_str is None else rdflib.URIRef(role_str)

        if role_uri is None:
            return

        for item in self.selected_items:
            item.role = role_uri


class PhysicalSpaceProperties(BasePropertyPanel):
    def __init__(self):
        super().__init__()

        self.instance_uri = QLabel("No physical space selected")
        self.addRow(QLabel("<b>instance:</b>"), self.instance_uri)

        self.type_uri = QLabel("s223:PhysicalSpace")
        self.addRow(QLabel("<b>rdfs:type:</b>"), self.type_uri)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(PhysicalSpace.MIN_SIZE, 5000)
        self.width_spin.setSingleStep(10)
        self.width_spin.setDecimals(0)
        self.width_spin.valueChanged.connect(self._on_size_changed)
        self.addRow(QLabel("<b>Width:</b>"), self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(PhysicalSpace.MIN_SIZE, 5000)
        self.height_spin.setSingleStep(10)
        self.height_spin.setDecimals(0)
        self.height_spin.valueChanged.connect(self._on_size_changed)
        self.addRow(QLabel("<b>Height:</b>"), self.height_spin)

        self.domain_count = QLabel("0")
        self.addRow(QLabel("<b>s223:encloses (Count):</b>"), self.domain_count)

        self.contained_count = QLabel("0")
        self.addRow(QLabel("<b>s223:contains (Count):</b>"), self.contained_count)

        self.role = QComboBox()
        self.role.addItem("Please select role", userData=None)
        for role_uri in enums.roles:
            self.role.addItem(to_label(role_uri), userData=str(role_uri))
        self.role.currentIndexChanged.connect(self._on_role_changed)
        self.addRow(QLabel("<b>s223.hasRole:</b>"), self.role)

        self.manage_relationships_btn = QPushButton("Manage Relationships...")
        self.manage_relationships_btn.clicked.connect(self._on_manage_relationships)
        self.addRow("", self.manage_relationships_btn)

        self._hide()

    def update_properties(self, selection: Selection):
        physical_spaces = selection.getPhysicalSpace

        if not physical_spaces:
            self._hide()
            self.selected_items = []
            return

        self._show()
        self.selected_items = physical_spaces

        if len(physical_spaces) == 1:
            self.update_single_space(physical_spaces[0])
        else:
            self.update_multiple_spaces(physical_spaces)

    def update_single_space(self, item: PhysicalSpace):

        self.instance_uri.setText(to_label(item.inst_uri))
        self.label.setText(item.label)
        self.label.setPlaceholderText("Enter label")

        self.width_spin.blockSignals(True)
        self.width_spin.setValue(item.width)
        self.width_spin.setEnabled(True)
        self.width_spin.blockSignals(False)

        self.height_spin.blockSignals(True)
        self.height_spin.setValue(item.height)
        self.height_spin.setEnabled(True)
        self.height_spin.blockSignals(False)

        self.domain_count.setText(str(len(item.enclosed_domain_spaces)))
        self.contained_count.setText(str(len(item.contained_items)))

        self.role.blockSignals(True)
        role_str = str(item.role) if item.role else None
        index = self.role.findData(role_str)
        self.role.setCurrentIndex(index if index != -1 else 0)
        self.role.setEnabled(True)
        self.role.blockSignals(False)

        self.manage_relationships_btn.setEnabled(True)

    def update_multiple_spaces(self, items: Selection):

        self.instance_uri.setText("Multiselection")
        self.label.setText("")
        self.label.setPlaceholderText("Multiselection")
        self.domain_count.setText("N/A")
        self.contained_count.setText("N/A")

        self.width_spin.blockSignals(True)
        self.width_spin.setValue(0)
        self.width_spin.setEnabled(False)
        self.width_spin.blockSignals(False)

        self.height_spin.blockSignals(True)
        self.height_spin.setValue(0)
        self.height_spin.setEnabled(False)
        self.height_spin.blockSignals(False)

        self.role.blockSignals(True)
        self.role.setCurrentIndex(0)
        self.role.setEnabled(True)
        self.role.blockSignals(False)

        self.manage_relationships_btn.setEnabled(False)

    def _on_size_changed(self):
        if not self.selected_items or len(self.selected_items) != 1:
            return

        item = self.selected_items[0]
        new_width = self.width_spin.value()
        new_height = self.height_spin.value()

        if new_width == item.width and new_height == item.height:
            return

        scene = item.scene()
        if scene:
            old_size = (item.width, item.height)
            new_size = (new_width, new_height)

            command = ResizeCommand(item, old_size, new_size)
            push_command_to_scene(scene, command)

    def _on_role_changed(self, index):
        if not self.selected_items:
            return

        role_str = self.role.itemData(index)
        new_role = rdflib.URIRef(role_str) if role_str else None

        scene = self.selected_items[0].scene()
        if scene:
            command = ChangeAttributeCommand(self.selected_items, 'role', new_role)
            push_command_to_scene(scene, command)

    def _on_manage_relationships(self):
        if not self.selected_items or len(self.selected_items) != 1:
            return

        physical_space = self.selected_items[0]
        scene = physical_space.scene()
        if not scene:
            return

        view = scene.views()[0] if scene.views() else None
        if hasattr(view, "_show_relationship_dialog"):
            view._show_relationship_dialog(physical_space)
        else:

            dialog = RelationshipDialog(physical_space, scene)
            if dialog.exec_() == QDialog.Accepted:
                commands_to_push = dialog.get_commands()
                if commands_to_push:
                    compound_command = CompoundCommand("Manage Relationships")
                    for cmd in commands_to_push:
                        compound_command.add_command(cmd)

                    push_command_to_scene(scene, compound_command)
                self.update_single_space(physical_space)
