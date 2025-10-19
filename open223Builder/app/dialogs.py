from typing import Union

from PyQt5.QtWidgets import (
    QGraphicsScene, QWidget, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QDialog, QDoubleSpinBox, QTabWidget, QGroupBox, QListWidget,
    QListWidgetItem
)

from open223Builder.library import (
    connection_point_library
)

import open223Builder.enumerations as enums
from open223Builder.app.items import *


class AddPropertyDialog(QDialog):
    def __init__(self, parent_item: Union[ConnectableItem, ConnectionPoint], parent=None):
        super().__init__(parent)
        self.parent_item = parent_item
        self.setWindowTitle(f"Add Property to {type(parent_item).__name__}")
        self.setMinimumWidth(350)

        layout = QFormLayout(self)

        self.property_type = QComboBox()

        self.property_type.addItem("Property", userData=S223.Property)
        self.property_type.addItem("Observable Property", userData=S223.ObservableProperty)
        self.property_type.addItem("Actuatable Property", userData=S223.ActuatableProperty)
        self.property_type.addItem("Enumerable Property", userData=S223.EnumerableProperty)
        self.property_type.addItem("Quantifiable Property", userData=S223.QuantifiableProperty)
        self.property_type.addItem("Quantifiable Observable", userData=S223.QuantifiableObservableProperty)
        self.property_type.addItem("Quantifiable Actuatable", userData=S223.QuantifiableActuatableProperty)
        self.property_type.addItem("Enumerated Observable", userData=S223.EnumeratedObservableProperty)
        self.property_type.addItem("Enumerated Actuatable", userData=S223.EnumeratedActuatableProperty)

        self.identifier = QLineEdit("P")
        self.identifier.setMaxLength(1)

        self.aspect = QComboBox()
        self.aspect.addItem("Select aspect", userData=None)
        for aspect in enums.aspects:
            self.aspect.addItem(to_label(aspect), userData=aspect)

        self.medium = QComboBox()
        from src.library import medium_library
        for medium_uri in medium_library:
            self.medium.addItem(to_label(medium_uri), userData=medium_uri)

        self.unit = QComboBox()
        self.unit.addItem("Select Unit", userData=None)
        for unit_uri in enums.units:
            self.unit.addItem(to_label(unit_uri), userData=unit_uri)

        self.quantity_kind = QComboBox()
        self.quantity_kind.addItem("Select Quantity Kind", userData=None)
        for qk_uri in enums.quantity_kinds: self.quantity_kind.addItem(to_label(qk_uri), userData=qk_uri)

        self.external_reference = QLineEdit()
        self.internal_reference = QLineEdit()
        self.value = QLineEdit()
        self.label_edit = QLineEdit()
        self.comment_edit = QLineEdit()

        layout.addRow("Property Type:", self.property_type)
        layout.addRow("Identifier (letter):", self.identifier)
        layout.addRow("Label:", self.label_edit)
        layout.addRow("Comment:", self.comment_edit)
        layout.addRow("Aspect:", self.aspect)
        layout.addRow("Medium:", self.medium)

        layout.addRow("QUDT Unit:", self.unit)
        layout.addRow("QUDT Quantity Kind:", self.quantity_kind)

        layout.addRow("External Reference:", self.external_reference)
        layout.addRow("Internal Reference:", self.internal_reference)
        layout.addRow("Value:", self.value)

        button_box = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_box.addWidget(self.add_button)
        button_box.addWidget(self.cancel_button)
        layout.addRow("", button_box)
        self.setLayout(layout)

    def get_property_data(self):
        """Return dictionary with property configuration."""
        return {
            'property_type': self.property_type.currentData(),
            'identifier': self.identifier.text() or "P",
            'position_x': 0,
            'position_y': 0,
            'label': self.label_edit.text(),
            'comment': self.comment_edit.text(),
            'aspect': self.aspect.currentData(),
            'medium': self.medium.currentData(),
            'unit': self.unit.currentData(),
            'quantity_kind': self.quantity_kind.currentData(),
            'external_reference': self.external_reference.text(),
            'internal_reference': self.internal_reference.text(),
            'value': self.value.text()
        }


class AddConnectionPointDialog(QDialog):
    def __init__(self, connectable: ConnectableItem, parent=None):
        super().__init__(parent)
        self.connectable = connectable
        self.setWindowTitle("Add Connection Point")
        self.setMinimumWidth(300)

        layout = QFormLayout(self)

        self.position_x = QDoubleSpinBox()
        self.position_x.setRange(0.0, 1.0)
        self.position_x.setSingleStep(0.1)
        self.position_x.setValue(0.5)
        self.position_x.setDecimals(2)

        self.position_y = QDoubleSpinBox()
        self.position_y.setRange(0.0, 1.0)
        self.position_y.setSingleStep(0.1)
        self.position_y.setValue(0.5)
        self.position_y.setDecimals(2)

        self.medium = QComboBox()
        for medium_uri in medium_library:
            self.medium.addItem(to_label(medium_uri), userData=medium_uri)

        self.type_uri = QComboBox()
        for connection in connection_point_library:
            self.type_uri.addItem(to_label(connection), userData=connection)

        layout.addRow("Relative X Position (0-1):", self.position_x)
        layout.addRow("Relative Y Position (0-1):", self.position_y)
        layout.addRow("Medium:", self.medium)
        layout.addRow("Connection Type:", self.type_uri)

        button_box = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        button_box.addWidget(self.add_button)
        button_box.addWidget(self.cancel_button)
        layout.addRow("", button_box)

        self.setLayout(layout)

    def get_connection_point_data(self):
        return {
            'position_x': self.position_x.value(),
            'position_y': self.position_y.value(),
            'medium': self.medium.currentData(),
            'type_uri': self.type_uri.currentData()
        }


class RelationshipDialog(QDialog):
    def __init__(self, item: Union[PhysicalSpace, ConnectableItem], scene: QGraphicsScene, parent=None):
        super().__init__(parent)
        self.item = item
        self.scene = scene
        self.setWindowTitle(f"Manage Relationships for '{item.label or to_label(item.inst_uri)}'")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # --- Store initial states ---
        # Contains relationship
        self.initial_contained_items = set(getattr(self.item, 'contained_items', set()))

        # Encloses relationship (only for PhysicalSpace)
        self.initial_enclosed_uris = set(getattr(self.item, 'enclosed_domain_spaces', set()))

        # Physical Location relationship (only for Equipment)
        self.initial_physical_location_uri = getattr(self.item, 'physical_location_uri', None)
        # This will hold the URI selected *in the dialog* for physical location
        self.selected_physical_location_uri: Optional[rdflib.URIRef] = self.initial_physical_location_uri

        # Observation Location relationship (only for Equipment)
        self.initial_observation_location_uri = getattr(self.item, 'observation_location_uri', None)
        # This will hold the URI selected *in the dialog* for observation location
        self.selected_observation_location_uri: Optional[rdflib.URIRef] = self.initial_observation_location_uri

        # --- Maps for list widgets (used to map graphics items to list items) ---
        self.available_contain_map = {}  # item -> list_item
        self.contained_map = {}  # item -> list_item
        self.available_domains_map = {}  # item -> list_item
        self.enclosed_domains_map = {}  # item -> list_item
        self.available_physical_spaces_map = {}  # item -> list_item
        self.available_observation_locations_map = {}  # item -> list_item

        # --- Setup UI ---
        self._setup_ui()
        self._populate_lists()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- Tab 1: Contains ---
        # This tab is always present
        self.contains_widget = QWidget()
        contains_layout = QHBoxLayout(self.contains_widget)

        available_group = QGroupBox("Available Items")
        available_layout = QVBoxLayout(available_group)
        self.available_contain_list = QListWidget()
        self.available_contain_list.setSelectionMode(QListWidget.ExtendedSelection)
        available_layout.addWidget(self.available_contain_list)

        button_layout_contains = QVBoxLayout()
        button_layout_contains.addStretch()
        self.add_contains_btn = QPushButton(">>")
        self.remove_contains_btn = QPushButton("<<")
        button_layout_contains.addWidget(self.add_contains_btn)
        button_layout_contains.addWidget(self.remove_contains_btn)
        button_layout_contains.addStretch()

        contained_group = QGroupBox("Contained Items")
        contained_layout = QVBoxLayout(contained_group)
        self.contained_list = QListWidget()
        self.contained_list.setSelectionMode(QListWidget.ExtendedSelection)
        contained_layout.addWidget(self.contained_list)

        contains_layout.addWidget(available_group)
        contains_layout.addLayout(button_layout_contains)
        contains_layout.addWidget(contained_group)
        self.tabs.addTab(self.contains_widget, "Contains")

        # Connect signals for Contains tab
        self.add_contains_btn.clicked.connect(self._move_items_to_contained)
        self.remove_contains_btn.clicked.connect(self._move_items_to_available_contain)

        # --- Tab 2: Encloses (Conditional for PhysicalSpace) ---
        if isinstance(self.item, PhysicalSpace):
            self.encloses_widget = QWidget()
            encloses_layout = QHBoxLayout(self.encloses_widget)

            available_domains_group = QGroupBox("Available Domain Spaces")
            available_domains_layout = QVBoxLayout(available_domains_group)
            self.available_domains_list = QListWidget()
            self.available_domains_list.setSelectionMode(QListWidget.ExtendedSelection)
            available_domains_layout.addWidget(self.available_domains_list)

            domain_button_layout = QVBoxLayout()
            domain_button_layout.addStretch()
            self.add_encloses_btn = QPushButton(">>")
            self.remove_encloses_btn = QPushButton("<<")
            domain_button_layout.addWidget(self.add_encloses_btn)
            domain_button_layout.addWidget(self.remove_encloses_btn)
            domain_button_layout.addStretch()

            enclosed_group = QGroupBox("Enclosed Domain Spaces")
            enclosed_layout = QVBoxLayout(enclosed_group)
            self.enclosed_domains_list = QListWidget()
            self.enclosed_domains_list.setSelectionMode(QListWidget.ExtendedSelection)
            enclosed_layout.addWidget(self.enclosed_domains_list)

            encloses_layout.addWidget(available_domains_group)
            encloses_layout.addLayout(domain_button_layout)
            encloses_layout.addWidget(enclosed_group)
            self.tabs.addTab(self.encloses_widget, "Encloses (Domain Spaces)")

            # Connect signals for Encloses tab
            self.add_encloses_btn.clicked.connect(self._move_items_to_enclosed)
            self.remove_encloses_btn.clicked.connect(self._move_items_to_available_domains)

        # Define helper variable for clarity
        is_equipment = isinstance(self.item, ConnectableItem) and not isinstance(self.item, DomainSpace)

        # --- Tab 3: Physical Location (Conditional for Equipment) ---
        if is_equipment:
            self.physical_location_widget = QWidget()
            location_layout = QVBoxLayout(self.physical_location_widget)

            # Group for available spaces
            available_spaces_group = QGroupBox("Available Physical Spaces")
            available_spaces_layout = QVBoxLayout(available_spaces_group)
            self.available_physical_spaces_list = QListWidget()
            self.available_physical_spaces_list.setSelectionMode(QListWidget.SingleSelection)  # Single selection
            available_spaces_layout.addWidget(self.available_physical_spaces_list)
            location_layout.addWidget(available_spaces_group)

            # Group for current location and controls
            controls_group = QGroupBox("Set Physical Location")
            controls_layout = QFormLayout(controls_group)
            self.current_location_label = QLabel("None")
            self.current_location_label.setWordWrap(True)
            self.set_location_btn = QPushButton("Set Selected as Physical Location")
            self.clear_location_btn = QPushButton("Clear Physical Location")
            controls_layout.addRow("Current Location:", self.current_location_label)
            controls_layout.addRow(self.set_location_btn)
            controls_layout.addRow(self.clear_location_btn)
            location_layout.addWidget(controls_group)

            self.tabs.addTab(self.physical_location_widget, "Physical Location")

            # Connect signals for Physical Location tab
            self.set_location_btn.clicked.connect(self._set_physical_location)
            self.clear_location_btn.clicked.connect(self._clear_physical_location)
            self.available_physical_spaces_list.currentItemChanged.connect(self._update_location_button_state)
            # Initial button state set in _populate_lists

        # --- Tab 4: Observation Location (Conditional for Equipment) ---
        if is_equipment:
            self.observation_location_widget = QWidget()
            obs_loc_layout = QVBoxLayout(self.observation_location_widget)

            # Group for available locations
            available_obs_loc_group = QGroupBox("Available Observation Locations (Connectable, Connection, CP)")
            available_obs_loc_layout = QVBoxLayout(available_obs_loc_group)
            self.available_observation_locations_list = QListWidget()
            self.available_observation_locations_list.setSelectionMode(QListWidget.SingleSelection)  # Single selection
            available_obs_loc_layout.addWidget(self.available_observation_locations_list)
            obs_loc_layout.addWidget(available_obs_loc_group)

            # Group for current location and controls
            obs_loc_controls_group = QGroupBox("Set Observation Location")
            obs_loc_controls_layout = QFormLayout(obs_loc_controls_group)
            self.current_observation_location_label = QLabel("None")
            self.current_observation_location_label.setWordWrap(True)
            self.set_observation_location_btn = QPushButton("Set Selected as Observation Location")
            self.clear_observation_location_btn = QPushButton("Clear Observation Location")
            obs_loc_controls_layout.addRow("Current Observation Target:",
                                           self.current_observation_location_label)  # Changed label slightly
            obs_loc_controls_layout.addRow(self.set_observation_location_btn)
            obs_loc_controls_layout.addRow(self.clear_observation_location_btn)
            obs_loc_layout.addWidget(obs_loc_controls_group)

            self.tabs.addTab(self.observation_location_widget, "Observation Location")

            # Connect signals for Observation Location tab
            self.set_observation_location_btn.clicked.connect(self._set_observation_location)
            self.clear_observation_location_btn.clicked.connect(self._clear_observation_location)
            self.available_observation_locations_list.currentItemChanged.connect(
                self._update_observation_location_button_state)
            # Initial button state set in _populate_lists

        # --- OK/Cancel Buttons ---
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        button_box.addStretch()
        button_box.addWidget(self.ok_button)
        button_box.addWidget(self.cancel_button)

        layout.addWidget(self.tabs)
        layout.addLayout(button_box)

        # Connect OK/Cancel
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def _populate_lists(self):
        # Clear all lists and maps first
        self.available_contain_list.clear()
        self.contained_list.clear()
        self.available_contain_map.clear()
        self.contained_map.clear()

        if hasattr(self, 'available_domains_list'):
            self.available_domains_list.clear()
            self.enclosed_domains_list.clear()
            self.available_domains_map.clear()
            self.enclosed_domains_map.clear()

        if hasattr(self, 'available_physical_spaces_list'):
            self.available_physical_spaces_list.clear()
            self.available_physical_spaces_map.clear()

        if hasattr(self, 'available_observation_locations_list'):
            self.available_observation_locations_list.clear()
            self.available_observation_locations_map.clear()

        # --- Populate Contains List ---
        is_physical_container = isinstance(self.item, PhysicalSpace)
        for scene_item in self.scene.items():
            if scene_item == self.item: continue  # Skip self

            valid_contain_candidate = False
            # Check for valid containment relationship type and prevent cycles
            if is_physical_container and isinstance(scene_item, PhysicalSpace):
                parent = self.item.parentItem();
                is_ancestor = False
                while parent:
                    if parent == scene_item: is_ancestor = True; break
                    parent = parent.parentItem()
                if not is_ancestor: valid_contain_candidate = True
            elif not is_physical_container and isinstance(self.item, ConnectableItem) and \
                    isinstance(scene_item, ConnectableItem) and not isinstance(scene_item,
                                                                               (DomainSpace, PhysicalSpace)):
                # Equipment containing Equipment (excluding Domain/Physical)
                parent = self.item.parentItem();
                is_ancestor = False
                while parent:
                    if parent == scene_item: is_ancestor = True; break
                    parent = parent.parentItem()
                if not is_ancestor: valid_contain_candidate = True

            if valid_contain_candidate:
                # Ensure item has necessary attributes before creating label
                if hasattr(scene_item, 'label') and hasattr(scene_item, 'type_uri') and hasattr(scene_item, 'inst_uri'):
                    label = scene_item.label or f"{to_label(scene_item.type_uri)} ({to_label(scene_item.inst_uri)})"
                    list_item = QListWidgetItem(label)
                    list_item.setData(Qt.UserRole, scene_item)  # Store the actual item

                    if scene_item in self.initial_contained_items:
                        self.contained_list.addItem(list_item)
                        self.contained_map[scene_item] = list_item
                    else:
                        self.available_contain_list.addItem(list_item)
                        self.available_contain_map[scene_item] = list_item
                else:
                    print(f"Warning: Skipping item {scene_item} in contains list population - missing attributes.")

        # --- Populate Encloses List (if PhysicalSpace) ---
        if isinstance(self.item, PhysicalSpace) and hasattr(self, 'available_domains_list'):
            for scene_item in self.scene.items():
                # Ensure item has necessary attributes
                if isinstance(scene_item, DomainSpace) and hasattr(scene_item, 'label') and hasattr(scene_item,
                                                                                                    'inst_uri'):
                    label = scene_item.label or f"Domain ({to_label(scene_item.inst_uri)})"
                    list_item = QListWidgetItem(label)
                    list_item.setData(Qt.UserRole, scene_item)
                    if scene_item.inst_uri in self.initial_enclosed_uris:
                        self.enclosed_domains_list.addItem(list_item)
                        self.enclosed_domains_map[scene_item] = list_item
                    else:
                        self.available_domains_list.addItem(list_item)
                        self.available_domains_map[scene_item] = list_item
                elif isinstance(scene_item, DomainSpace):
                    print(
                        f"Warning: Skipping DomainSpace {scene_item} in encloses list population - missing attributes.")

        # --- Populate Physical Location List (if Equipment) ---
        is_equipment = isinstance(self.item, ConnectableItem) and not isinstance(self.item, DomainSpace)
        if is_equipment and hasattr(self, 'available_physical_spaces_list'):
            current_location_item = None
            for scene_item in self.scene.items():
                # Ensure item has necessary attributes
                if isinstance(scene_item, PhysicalSpace) and hasattr(scene_item, 'label') and hasattr(scene_item,
                                                                                                      'inst_uri'):
                    label = scene_item.label or f"Space ({to_label(scene_item.inst_uri)})"
                    list_item = QListWidgetItem(label)
                    list_item.setData(Qt.UserRole, scene_item)  # Store item
                    self.available_physical_spaces_list.addItem(list_item)
                    self.available_physical_spaces_map[scene_item] = list_item

                    # Check if this is the currently assigned location (using the temporary selected_uri)
                    if self.selected_physical_location_uri == scene_item.inst_uri:
                        current_location_item = scene_item
                        # We select based on the *current* selection in the dialog, not initial state
                        self.available_physical_spaces_list.setCurrentItem(
                            list_item)  # Use setCurrentItem for single selection
                elif isinstance(scene_item, PhysicalSpace):
                    print(
                        f"Warning: Skipping PhysicalSpace {scene_item} in physical location list population - missing attributes.")

            # Update the current location label based on the *current* selection in the dialog
            if current_location_item:
                label = current_location_item.label or f"Space ({to_label(current_location_item.inst_uri)})"
                self.current_location_label.setText(label)
            else:
                self.current_location_label.setText("None")
            self._update_location_button_state()  # Update button state after population

        # --- Populate Observation Location List (if Equipment) ---
        if is_equipment and hasattr(self, 'available_observation_locations_list'):
            current_obs_loc_item = None
            for scene_item in self.scene.items():
                # Target can be Connectable, Connection, or ConnectionPoint
                if isinstance(scene_item, (ConnectableItem, Connection, ConnectionPoint)):
                    # Skip self if it happens to be a target type (e.g., ConnectableItem)
                    if scene_item == self.item:
                        continue

                    # Ensure item has necessary attributes before creating label
                    if hasattr(scene_item, 'label') and hasattr(scene_item, 'type_uri') and hasattr(scene_item,
                                                                                                    'inst_uri'):
                        # Create a descriptive label
                        label = f"{scene_item.label or to_label(scene_item.inst_uri)}"
                        if isinstance(scene_item, ConnectableItem):
                            prefix = "Equip"
                        elif isinstance(scene_item, Connection):
                            prefix = "Conn"
                        elif isinstance(scene_item, ConnectionPoint):
                            prefix = "CP"
                        else:
                            prefix = "Item"  # Fallback
                        full_label = f"[{prefix}] {to_label(scene_item.type_uri)}: {label}"

                        list_item = QListWidgetItem(full_label)
                        list_item.setData(Qt.UserRole, scene_item)  # Store the actual graphics item

                        self.available_observation_locations_list.addItem(list_item)
                        self.available_observation_locations_map[scene_item] = list_item

                        # Check if this is the currently assigned *selected* observation location
                        if self.selected_observation_location_uri == scene_item.inst_uri:
                            current_obs_loc_item = scene_item
                            self.available_observation_locations_list.setCurrentItem(list_item)  # Select in list
                    else:
                        print(
                            f"Warning: Skipping item {scene_item} in observation location list population - missing attributes.")

            # Update the current location label based on the *current* selection in the dialog
            if current_obs_loc_item:
                # Recreate the label for consistency
                label = f"{current_obs_loc_item.label or to_label(current_obs_loc_item.inst_uri)}"
                if isinstance(current_obs_loc_item, ConnectableItem):
                    prefix = "Equip"
                elif isinstance(current_obs_loc_item, Connection):
                    prefix = "Conn"
                elif isinstance(current_obs_loc_item, ConnectionPoint):
                    prefix = "CP"
                else:
                    prefix = "Item"
                full_label = f"[{prefix}] {to_label(current_obs_loc_item.type_uri)}: {label}"
                self.current_observation_location_label.setText(full_label)
            else:
                self.current_observation_location_label.setText("None")
            self._update_observation_location_button_state()  # Update button state after population

    def _move_items(self, source_list: QListWidget, target_list: QListWidget,
                    source_map: dict, target_map: dict):
        """Generic helper to move selected items between two QListWidgets and update tracking maps."""
        items_to_move = source_list.selectedItems()
        if not items_to_move:
            return

        # Get the actual graphics items associated with the selected QListWidgetItems
        graphics_items_to_move = [item.data(Qt.UserRole) for item in items_to_move if item.data(Qt.UserRole)]

        # Remove items from source list *by ListWidgetItem reference*
        for list_item in items_to_move:
            source_list.takeItem(source_list.row(list_item))  # Removes item from source list

        # Add items to target list and update maps
        for item_data in graphics_items_to_move:
            if item_data:
                # Create a new QListWidgetItem for the target list (important!)
                # Recreate the label based on the item type
                label = item_data.label or f"{to_label(item_data.type_uri)} ({to_label(item_data.inst_uri)})"
                if isinstance(item_data, PhysicalSpace):
                    pass  # Label already good
                elif isinstance(item_data, DomainSpace):
                    label = f"Domain ({to_label(item_data.inst_uri)})"  # Adjust if needed
                # Add more specific labels if needed

                new_list_item = QListWidgetItem(label)
                new_list_item.setData(Qt.UserRole, item_data)

                target_list.addItem(new_list_item)  # Add QListWidgetItem to target list
                target_map[item_data] = new_list_item  # Update target map (graphics_item -> list_item)
                if item_data in source_map:
                    del source_map[item_data]  # Remove from source map

    # --- Specific Move Actions ---
    def _move_items_to_contained(self):
        self._move_items(self.available_contain_list, self.contained_list,
                         self.available_contain_map, self.contained_map)

    def _move_items_to_available_contain(self):
        self._move_items(self.contained_list, self.available_contain_list,
                         self.contained_map, self.available_contain_map)

    def _move_items_to_enclosed(self):
        if hasattr(self, 'available_domains_list'):
            self._move_items(self.available_domains_list, self.enclosed_domains_list,
                             self.available_domains_map, self.enclosed_domains_map)

    def _move_items_to_available_domains(self):
        if hasattr(self, 'enclosed_domains_list'):
            self._move_items(self.enclosed_domains_list, self.available_domains_list,
                             self.enclosed_domains_map, self.available_domains_map)

    # --- Physical Location Button Handlers ---
    def _update_location_button_state(self):
        """Enable/disable 'Set/Clear Location' button for Physical Location tab."""
        if hasattr(self, 'set_location_btn'):
            selected_list_item = self.available_physical_spaces_list.currentItem()
            is_selected = selected_list_item is not None
            can_set = False
            if is_selected:
                selected_space_item = selected_list_item.data(Qt.UserRole)
                # Enable set button only if selection exists and its URI is different from the current one
                can_set = selected_space_item and (selected_space_item.inst_uri != self.selected_physical_location_uri)
            self.set_location_btn.setEnabled(can_set)

            # Enable clear button only if a location is currently set
            self.clear_location_btn.setEnabled(self.selected_physical_location_uri is not None)

    def _set_physical_location(self):
        """Sets the selected physical space as the current location for Physical Location tab."""
        if hasattr(self, 'available_physical_spaces_list'):
            selected_list_item = self.available_physical_spaces_list.currentItem()
            if selected_list_item:
                selected_space_item = selected_list_item.data(Qt.UserRole)
                if selected_space_item and hasattr(selected_space_item, 'inst_uri'):
                    self.selected_physical_location_uri = selected_space_item.inst_uri
                    label = selected_space_item.label or f"Space ({to_label(selected_space_item.inst_uri)})"
                    self.current_location_label.setText(label)
                    self._update_location_button_state()  # Update button states after setting

    def _clear_physical_location(self):
        """Clears the currently set physical location for Physical Location tab."""
        if hasattr(self, 'current_location_label'):
            self.selected_physical_location_uri = None
            self.current_location_label.setText("None")
            # Deselect item in the list
            self.available_physical_spaces_list.setCurrentItem(None)
            self._update_location_button_state()  # Update button states after clearing

    # --- Observation Location Button Handlers ---
    def _update_observation_location_button_state(self):
        """Enable/disable 'Set/Clear Observation Location' buttons."""
        if hasattr(self, 'set_observation_location_btn'):
            selected_list_item = self.available_observation_locations_list.currentItem()
            is_selected = selected_list_item is not None
            can_set = False
            if is_selected:
                selected_target_item = selected_list_item.data(Qt.UserRole)
                # Enable set button only if selection exists and its URI is different from the current one
                can_set = selected_target_item and (
                            selected_target_item.inst_uri != self.selected_observation_location_uri)
            self.set_observation_location_btn.setEnabled(can_set)

            # Enable clear button only if a location is currently set
            self.clear_observation_location_btn.setEnabled(self.selected_observation_location_uri is not None)

    def _set_observation_location(self):
        """Sets the selected item as the current observation location."""
        if hasattr(self, 'available_observation_locations_list'):
            selected_list_item = self.available_observation_locations_list.currentItem()
            if selected_list_item:
                selected_target_item = selected_list_item.data(Qt.UserRole)
                if selected_target_item and hasattr(selected_target_item, 'inst_uri'):
                    self.selected_observation_location_uri = selected_target_item.inst_uri
                    # Recreate the label for consistency
                    label = f"{selected_target_item.label or to_label(selected_target_item.inst_uri)}"
                    if isinstance(selected_target_item, ConnectableItem):
                        prefix = "Equip"
                    elif isinstance(selected_target_item, Connection):
                        prefix = "Conn"
                    elif isinstance(selected_target_item, ConnectionPoint):
                        prefix = "CP"
                    else:
                        prefix = "Item"
                    full_label = f"[{prefix}] {to_label(selected_target_item.type_uri)}: {label}"
                    self.current_observation_location_label.setText(full_label)
                    self._update_observation_location_button_state()  # Update buttons

    def _clear_observation_location(self):
        """Clears the currently set observation location."""
        if hasattr(self, 'current_observation_location_label'):
            self.selected_observation_location_uri = None
            self.current_observation_location_label.setText("None")
            # Deselect item in the list
            self.available_observation_locations_list.setCurrentItem(None)
            self._update_observation_location_button_state()  # Update buttons

    def get_commands(self) -> List[Command]:
        """
        Compare initial and final states of relationships based on the dialog's
        current state (using the tracking maps) and generate appropriate commands.
        """
        commands = []

        # 1. --- Contains relationship ---
        # Determine the final set of contained items based on the right list's map
        current_contained_items = set(self.contained_map.keys())

        # Find items added (in current set but not initial)
        added_items = current_contained_items - self.initial_contained_items
        for item_to_add in added_items:
            # Ensure the command is valid for the container/contained types
            if (isinstance(self.item, PhysicalSpace) and isinstance(item_to_add, PhysicalSpace)) or \
                    (isinstance(self.item, ConnectableItem) and isinstance(item_to_add,
                                                                           ConnectableItem) and not isinstance(
                        self.item, DomainSpace) and not isinstance(item_to_add, DomainSpace)):
                commands.append(AddContainedItemCommand(self.item, item_to_add))

        # Find items removed (in initial set but not current)
        removed_items = self.initial_contained_items - current_contained_items
        for item_to_remove in removed_items:
            if (isinstance(self.item, PhysicalSpace) and isinstance(item_to_remove, PhysicalSpace)) or \
                    (isinstance(self.item, ConnectableItem) and isinstance(item_to_remove,
                                                                           ConnectableItem) and not isinstance(
                        self.item, DomainSpace) and not isinstance(item_to_remove, DomainSpace)):
                commands.append(RemoveContainedItemCommand(self.item, item_to_remove))

        # 2. --- Encloses relationship (Only if item is PhysicalSpace) ---
        if isinstance(self.item, PhysicalSpace) and hasattr(self, 'enclosed_domains_map'):
            # Determine the final set of enclosed domain space items from the map
            current_enclosed_items = set(self.enclosed_domains_map.keys())
            # Get their URIs
            current_enclosed_uris = {item.inst_uri for item in current_enclosed_items}

            # Find URIs added
            added_domain_uris = current_enclosed_uris - self.initial_enclosed_uris
            # Find URIs removed
            removed_domain_uris = self.initial_enclosed_uris - current_enclosed_uris

            # Generate commands based on the *items* corresponding to the URIs
            for domain_item in current_enclosed_items:
                if domain_item.inst_uri in added_domain_uris:
                    commands.append(AddEnclosedSpaceCommand(self.item, domain_item))

            # Find initial items to generate remove commands
            initial_enclosed_items = {
                item for item in self.available_domains_map.keys() | self.enclosed_domains_map.keys()  # Check both maps
                if isinstance(item, DomainSpace) and item.inst_uri in self.initial_enclosed_uris
            }
            for domain_item in initial_enclosed_items:
                if domain_item.inst_uri in removed_domain_uris:
                    commands.append(RemoveEnclosedSpaceCommand(self.item, domain_item))

        # 3. --- Physical Location relationship (Only if item is Equipment) ---
        is_equipment = isinstance(self.item, ConnectableItem) and not isinstance(self.item, DomainSpace)
        if is_equipment and hasattr(self, 'selected_physical_location_uri'):
            # Compare the final selected URI in the dialog with the initial one
            if self.initial_physical_location_uri != self.selected_physical_location_uri:
                # Use ChangeAttributeCommand to set/clear the URI
                cmd = ChangeAttributeCommand(
                    items=[self.item],  # Command expects a list
                    attribute_name='physical_location_uri',
                    new_value=self.selected_physical_location_uri  # Can be None or a URIRef
                )
                commands.append(cmd)

        # 4. --- Observation Location relationship (Only if item is Equipment) ---
        if is_equipment and hasattr(self, 'selected_observation_location_uri'):
            # Compare the final selected URI in the dialog with the initial one
            if self.initial_observation_location_uri != self.selected_observation_location_uri:
                # Use ChangeAttributeCommand to set/clear the URI
                cmd = ChangeAttributeCommand(
                    items=[self.item],  # Command expects a list
                    attribute_name='observation_location_uri',  # The attribute added to ConnectableItem
                    new_value=self.selected_observation_location_uri  # Can be None or a URIRef
                )
                commands.append(cmd)

        return commands
