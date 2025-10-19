import os
import math
import rdflib
import sys
import traceback

from typing import List, Optional, Dict, Union
from rdflib import Literal

from PyQt5.QtSvg import (
    QGraphicsSvgItem, QSvgRenderer,
)
from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView,
    QGraphicsLineItem, QGraphicsRectItem, QTreeWidgetItem, QWidget, QTreeWidget, QFormLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QMainWindow, QDockWidget,
    QApplication, QDialog, QDoubleSpinBox, QMessageBox, QTabWidget, QStyle, QMenu, QFileDialog,
    QGroupBox, QCheckBox, QSpinBox, QFrame, QToolButton, QToolBar, QStatusBar, QListWidget, QListWidgetItem,
    QAbstractItemView,
)
from PyQt5.QtCore import (
    Qt, QPointF, QByteArray, QMimeData, QPoint, QTimer, QRectF, QRect, QObject, pyqtSignal,
)
from PyQt5.QtGui import (
    QPen, QBrush, QColor, QPixmap, QPainter, QDrag, QPainterPath, QDragMoveEvent,
    QDragEnterEvent, QFont
)

from open223Builder.namespaces import S223, VISU, BLDG, RDF, RDFS, QUDT, QUDTQK, short_uuid, to_label
from open223Builder.library import (
    port_library, svg_library, medium_library, connection_library, connection_point_library, connectable_library,
)
import open223Builder.enumerations as enums


def popup(window_title: str, text: str):
    msg = QMessageBox()
    msg.setWindowTitle(window_title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Information)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()


def push_command_to_scene(scene, command: 'Command'):
    if hasattr(scene, 'command_history'):
        return scene.command_history.push(command)

    return None


def find_status_bar(item):
    if isinstance(item, QMainWindow):
        return item.statusBar()
    elif isinstance(item, QWidget):
        return find_status_bar(item.parent())


def save_to_turtle(scene: QGraphicsScene, filepath: str):
    g = rdflib.Graph()
    g.bind("s223", S223)
    g.bind("visu", VISU)
    g.bind("bldg", BLDG)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("qudt", QUDT)  # Bind QUDT namespace
    g.bind("qudtqk", QUDTQK)  # Bind QuantityKind if used explicitly

    processed_uris = set()  # Keep track of URIs whose details have been fully saved

    def add_common_properties(item_uri, item):

        if hasattr(item, "label") and item.label:
            g.add((item_uri, RDFS.label, Literal(item.label, datatype=rdflib.XSD.string)))
        if hasattr(item, "comment") and item.comment:
            g.add((item_uri, RDFS.comment, Literal(item.comment, datatype=rdflib.XSD.string)))
        if hasattr(item, "role") and item.role:
            g.add((item_uri, S223.hasRole, item.role))
        # Add type triple here as well for consistency
        if hasattr(item, "type_uri") and item.type_uri:
            g.add((item_uri, RDF.type, item.type_uri))
        elif isinstance(item, PhysicalSpace):
            g.add((item_uri, RDF.type, S223.PhysicalSpace))
        elif isinstance(item, SystemItem):
            g.add((item_uri, RDF.type, S223.System))

    def save_property_details(prop: Property):
        prop_uri = prop.inst_uri
        if prop_uri in processed_uris:
            return  # Already processed

        g.add((prop_uri, RDF.type, prop.property_type))  # Ensure type is saved
        add_common_properties(prop_uri, prop)

        # Add Property-specific details
        g.add((prop_uri, VISU.positionX, Literal(prop.x(), datatype=rdflib.XSD.float)))
        g.add((prop_uri, VISU.positionY, Literal(prop.y(), datatype=rdflib.XSD.float)))
        g.add((prop_uri, VISU.identifier, Literal(prop.identifier, datatype=rdflib.XSD.string)))

        if prop.aspect:
            g.add((prop_uri, S223.hasAspect, prop.aspect))
        if prop.external_reference:
            g.add((prop_uri, S223.hasExternalReference, Literal(prop.external_reference, datatype=rdflib.XSD.string)))
        if prop.internal_reference:
            g.add((prop_uri, S223.hasInternalReference, Literal(prop.internal_reference, datatype=rdflib.XSD.string)))
        if prop.value:
            g.add((prop_uri, S223.hasValue, Literal(prop.value, datatype=rdflib.XSD.float)))
        if prop.medium:
            g.add((prop_uri, S223.hasMedium, rdflib.URIRef(prop.medium)))
        if prop.unit:
            g.add((prop_uri, QUDT.hasUnit, rdflib.URIRef(prop.unit)))
        if prop.quantity_kind:
            g.add((prop_uri, QUDT.hasQuantityKind, rdflib.URIRef(prop.quantity_kind)))

        processed_uris.add(prop_uri)

    def save_connection_point_details(cp: ConnectionPoint):
        cp_uri = cp.inst_uri
        if cp_uri in processed_uris:
            return  # Already processed

        g.add((cp_uri, RDF.type, cp.type_uri))  # Ensure type is saved
        add_common_properties(cp_uri, cp)  # Save label, comment, role if they exist

        # Link back to parent (ConnectableItem) - Essential relationship
        if cp.connectable:
            g.add((cp_uri, S223.isConnectionPointOf, cp.connectable.inst_uri))

        # Add ConnectionPoint-specific details
        if cp.medium:
            g.add((cp_uri, S223.hasMedium, cp.medium))

        g.add((cp_uri, VISU.relativeX, Literal(cp.relative_x, datatype=rdflib.XSD.float)))
        g.add((cp_uri, VISU.relativeY, Literal(cp.relative_y, datatype=rdflib.XSD.float)))

        # Process properties belonging to this connection point
        if hasattr(cp, "properties"):
            for prop in cp.properties:
                # Add the link from CP to Property
                g.add((cp_uri, S223.hasProperty, prop.inst_uri))
                # Save the property details (will check processed_uris internally)
                save_property_details(prop)

        processed_uris.add(cp_uri)  # Mark as processed

    # --- Main Saving Logic ---

    # Pass 1: Process ConnectableItems (Equipment and DomainSpaces)
    print("Saving: Processing ConnectableItems...")
    for item in scene.items():
        if isinstance(item, ConnectableItem) and item.inst_uri not in processed_uris:
            item_uri = item.inst_uri
            print(f"  Saving ConnectableItem: {item_uri}")
            add_common_properties(item_uri, item)  # Adds RDF.type, label, comment, role

            # Add visual properties
            g.add((item_uri, VISU.positionX, Literal(item.x(), datatype=rdflib.XSD.float)))
            g.add((item_uri, VISU.positionY, Literal(item.y(), datatype=rdflib.XSD.float)))
            g.add((item_uri, VISU.rotation, Literal(item.rotation(), datatype=rdflib.XSD.integer)))
            if isinstance(item, DomainSpace):
                g.add((item_uri, VISU.width, Literal(item.width, datatype=rdflib.XSD.float)))
                g.add((item_uri, VISU.height, Literal(item.height, datatype=rdflib.XSD.float)))

            # Add link to contained items (ConnectableItem -> ConnectableItem)
            if hasattr(item, "contained_items"):
                # Ensure contained items are ConnectableItems (not Domain/Physical)
                valid_contained = [ci for ci in item.contained_items if
                                   isinstance(ci, ConnectableItem) and not isinstance(ci, (DomainSpace, PhysicalSpace))]
                for contained_item in valid_contained:
                    g.add((item_uri, S223.contains, contained_item.inst_uri))

            # Process Connection Points belonging to this item
            if hasattr(item, "connection_points"):
                for cp in item.connection_points:
                    # Add the link from ConnectableItem to ConnectionPoint
                    g.add((item_uri, S223.hasConnectionPoint, cp.inst_uri))
                    # Save the connection point details (checks processed_uris internally)
                    save_connection_point_details(cp)

            # Process Properties belonging directly to this item
            if hasattr(item, "properties"):
                for prop in item.properties:
                    # Add the link from ConnectableItem to Property
                    g.add((item_uri, S223.hasProperty, prop.inst_uri))
                    # Save the property details (checks processed_uris internally)
                    save_property_details(prop)

            processed_uris.add(item_uri)

            if hasattr(item, 'observation_location_uri') and item.observation_location_uri:
                # Check if the target exists in the scene (optional but good practice)
                target_exists = False
                for potential_target in scene.items():
                    if hasattr(potential_target,
                               'inst_uri') and potential_target.inst_uri == item.observation_location_uri:
                        if isinstance(potential_target, (ConnectableItem, Connection, ConnectionPoint)):
                            target_exists = True
                            break
                if target_exists:
                    g.add((item_uri, S223.hasObservationLocation, item.observation_location_uri))
                    print(f"    Added s223:hasObservationLocation: {item_uri} -> {item.observation_location_uri}")
                else:
                    print(f"    Warning: Observation location target {item.observation_location_uri} for {item_uri} not found in scene. Relationship not saved.")

    # Pass 2: Process PhysicalSpaces
    print("Saving: Processing PhysicalSpaces...")
    for item in scene.items():
        if isinstance(item, PhysicalSpace) and item.inst_uri not in processed_uris:
            item_uri = item.inst_uri
            print(f"  Saving PhysicalSpace: {item_uri}")
            add_common_properties(item_uri, item)  # Adds RDF.type, label, comment, role

            # Add visual properties
            g.add((item_uri, VISU.positionX, Literal(item.x(), datatype=rdflib.XSD.float)))
            g.add((item_uri, VISU.positionY, Literal(item.y(), datatype=rdflib.XSD.float)))
            g.add((item_uri, VISU.width, Literal(item.width, datatype=rdflib.XSD.float)))
            g.add((item_uri, VISU.height, Literal(item.height, datatype=rdflib.XSD.float)))

            # Add link to contained items (PhysicalSpace -> PhysicalSpace)
            if hasattr(item, "contained_items"):
                # Ensure contained items are PhysicalSpaces
                valid_contained = [ci for ci in item.contained_items if isinstance(ci, PhysicalSpace)]
                for contained_item in valid_contained:
                    g.add((item_uri, S223.contains, contained_item.inst_uri))

            # Add link to enclosed DomainSpaces
            if hasattr(item, "enclosed_domain_spaces"):
                for domain_space_uri in item.enclosed_domain_spaces:
                    # Ensure the target URI exists and is a DomainSpace? Optional check.
                    g.add((item_uri, S223.encloses, domain_space_uri))

            processed_uris.add(item_uri)  # Mark PhysicalSpace as processed

    # Pass 3: Process Connections
    print("Saving: Processing Connections...")
    for item in scene.items():
        if isinstance(item, Connection) and item.inst_uri not in processed_uris:
            conn_uri = item.inst_uri
            print(f"  Saving Connection: {conn_uri}")
            add_common_properties(conn_uri, item)  # Adds RDF.type, label, comment, role

            # Add connection-specific links
            if item.source and item.target:
                g.add((conn_uri, S223.connectsAt, item.source.inst_uri))
                g.add((conn_uri, S223.connectsAt, item.target.inst_uri))
                # Also add the inverse connectsThrough properties
                g.add((item.source.inst_uri, S223.connectsThrough, conn_uri))
                g.add((item.target.inst_uri, S223.connectsThrough, conn_uri))
            else:
                print(f"Warning: Connection {conn_uri} is missing source or target. Links not saved.")

            processed_uris.add(conn_uri)  # Mark Connection as processed

    # Pass 4: Process Systems
    print("Saving: Processing Systems...")
    for item in scene.items():
        if isinstance(item, SystemItem) and item.inst_uri not in processed_uris:
            sys_uri = item.inst_uri
            print(f"  Saving System: {sys_uri}")
            add_common_properties(sys_uri, item)  # Adds RDF.type, label, comment, role

            # Add links to members
            if hasattr(item, "members"):
                for member in item.members:
                    # Ensure member is a valid type before linking
                    if isinstance(member, ConnectableItem) and not isinstance(member, (DomainSpace, PhysicalSpace)):
                        g.add((sys_uri, S223.hasMember, member.inst_uri))
                    else:
                        print(
                            f"Warning: System {sys_uri} contains invalid member type {type(member)} ({member.inst_uri}). Link not saved.")

            processed_uris.add(sys_uri)  # Mark System as processed

    # Final check: Ensure all CPs and Properties were processed (e.g., if orphaned)
    # This shouldn't be necessary with the current logic but can be a safety check.
    print("Saving: Final check for orphaned CPs/Properties...")
    for item in scene.items():
        if isinstance(item, ConnectionPoint):
            save_connection_point_details(item)  # Will do nothing if already processed
        elif isinstance(item, Property):
            save_property_details(item)  # Will do nothing if already processed

    # --- Serialize the graph ---
    try:
        g.serialize(destination=filepath, format="turtle")
        print(f"Canvas saved successfully to {filepath} with {len(g)} triples.")
    except Exception as e:
        print(f"Error saving canvas to {filepath}: {e}")
        traceback.print_exc()  # Add traceback


def load_from_turtle(scene: QGraphicsScene, filepath: str):
    def replace_uris_in_namespace(graph, namespace_uri):
        namespace_uri = str(namespace_uri)
        new_graph = rdflib.Graph()
        uri_map = {}

        print(f"Replacing URIs in namespace: {namespace_uri}")

        # First pass: build mapping dictionary
        for s, p, o in graph:
            for node in (s, p, o):
                if isinstance(node, rdflib.URIRef) and str(node).startswith(namespace_uri):
                    if node not in uri_map:
                        uri_map[node] = rdflib.URIRef(f"{namespace_uri}{short_uuid()}")
                        print(f"Mapping: {node} -> {uri_map[node]}")

        print(f"Found {len(uri_map)} URIs to replace")

        # Second pass: construct new graph with replaced URIs
        for s, p, o in graph:
            new_graph.add((uri_map.get(s, s), uri_map.get(p, p), uri_map.get(o, o)))

        # Print all replacements
        for k, v in uri_map.items():
            print(f"Replaced {k} with {v}")

        return new_graph

    g = rdflib.Graph()

    try:
        print("Parsing Turtle file...")
        g.parse(filepath, format="turtle")
        print(f"Parsed graph with {len(g)} triples")

        # Replace URIs in the specified namespace
        g = replace_uris_in_namespace(g, BLDG)

        # Re-draw the grid/frame if needed (assuming _draw_grid exists in your Canvas/MainWindow)
        view = scene.views()[0] if scene.views() else None
        if view and hasattr(view, '_draw_grid'):
            QTimer.singleShot(0, view._draw_grid)  # Delay slightly to ensure scene is ready

        created_items = {}  # Stores URI -> QGraphicsItem instance mapping
        connection_points = {}  # Stores URI -> ConnectionPoint instance mapping
        domain_spaces = {}  # Stores URI -> DomainSpace instance mapping (subset of created_items)

        print("First pass: Creating PhysicalSpace and ConnectableItems...")
        components_created = 0

        # --- Pass 1: Create Physical Spaces ---
        for subject, p, o in g.triples((None, RDF.type, S223.PhysicalSpace)):
            print(f"Creating PhysicalSpace: {subject}")
            physical_space = PhysicalSpace(inst_uri=subject)
            x = g.value(subject, VISU.positionX)
            y = g.value(subject, VISU.positionY)
            width = g.value(subject, VISU.width)
            height = g.value(subject, VISU.height)
            if x and y: physical_space.setPos(float(x), float(y))
            if width: physical_space.width = float(width)
            if height: physical_space.height = float(height)
            label = g.value(subject, RDFS.label)
            comment = g.value(subject, RDFS.comment)
            role = g.value(subject, S223.hasRole)
            if label: physical_space.label = str(label)
            if comment: physical_space.comment = str(comment)
            if role: physical_space.role = role
            scene.addItem(physical_space)
            created_items[subject] = physical_space
            components_created += 1

        # --- Pass 1b: Create Connectable Items (Equipment & Domain Spaces) ---
        for subject, p, o in g.triples((None, RDF.type, None)):
            item_type = o
            # Skip if already created, or if it's a type handled in later passes
            if (subject in created_items or
                    item_type == S223.PhysicalSpace or  # Already handled
                    item_type in ConnectionPoint.allowed_types or  # Handled in Pass 3
                    item_type in Connection.allowed_types or  # Handled in Pass 4
                    item_type == S223.System or  # Handled in Pass 7 (NEW)
                    item_type in Property.allowed_types):  # Handled in Pass 6
                continue

            if item_type == S223.DomainSpace:
                print(f"Creating DomainSpace: {subject}")
                connectable = DomainSpace(inst_uri=subject)
                domain_spaces[subject] = connectable  # Keep track specifically
                width = g.value(subject, VISU.width)
                height = g.value(subject, VISU.height)
                if width: connectable.width = float(width)
                if height: connectable.height = float(height)
                # DomainSpace doesn't load default CPs

            elif item_type in svg_library:  # Assume other connectables are equipment with SVGs
                print(f"Creating ConnectableItem (Equipment): {subject} of type {item_type}")
                connectable = ConnectableItem(type_uri=item_type, inst_uri=subject)
                # Load default CPs first, then remove them before adding saved ones
                default_cps = connectable.connection_points.copy()
                for cp in default_cps:
                    # Don't remove from scene here, just from the item's list
                    connectable.connection_points.remove(cp)
                    # We don't add default CPs to the scene initially when loading
            else:
                print(f"Skipping unknown item type: {item_type} for subject {subject}")
                continue  # Skip to next triple if type is not recognized

            # --- Common setup for created ConnectableItem ---
            if connectable:

                obs_loc_uri = g.value(subject, S223.hasObservationLocation)
                if obs_loc_uri and isinstance(obs_loc_uri, rdflib.URIRef):
                    connectable.observation_location_uri = obs_loc_uri
                    print(f"  Found observation location link: {subject} -> {obs_loc_uri}")

                location_uri = g.value(subject, S223.hasPhysicalLocation)
                if location_uri and isinstance(location_uri, rdflib.URIRef):
                    connectable.physical_location_uri = location_uri
                    print(f"  Found physical location link: {subject} -> {location_uri}")

                x = g.value(subject, VISU.positionX)
                y = g.value(subject, VISU.positionY)
                rotation = g.value(subject, VISU.rotation)
                if x and y:
                    connectable.setPos(float(x), float(y))
                if rotation is not None:
                    connectable.setRotation(float(rotation))

                label = g.value(subject, RDFS.label)
                comment = g.value(subject, RDFS.comment)
                role = g.value(subject, S223.hasRole)
                if label:
                    connectable.label = str(label)
                if comment:
                    connectable.comment = str(comment)
                if role:
                    connectable.role = role

                scene.addItem(connectable)
                created_items[subject] = connectable
                components_created += 1

        print(f"Created {components_created} component items (PhysicalSpace, ConnectableItem, DomainSpace)")

        print("Second pass: Processing container relationships (contains, encloses)...")
        relationships_processed = 0
        # --- Pass 2: Process 'contains' (Physical->Physical, Equipment->Equipment) ---
        for subject, p, o in g.triples((None, S223.contains, None)):
            if subject in created_items and o in created_items:
                container = created_items[subject]
                contained = created_items[o]

                # Check for valid containment types
                valid_containment = False
                if isinstance(container, PhysicalSpace) and isinstance(contained, PhysicalSpace):
                    valid_containment = True
                elif isinstance(container, ConnectableItem) and not isinstance(container, DomainSpace) and \
                        isinstance(contained, ConnectableItem) and not isinstance(contained, DomainSpace):
                    # Equipment containing Equipment
                    valid_containment = True

                if valid_containment:
                    # Use the item's add_item method which handles parenting
                    if hasattr(container, 'add_item') and container.add_item(
                            contained):  # Calls contained.setParentItem(container)
                        print(f"Creating 'contains' relationship: {container.inst_uri} contains {contained.inst_uri}")

                        # --- CHANGE ---
                        # REMOVE the explicit position mapping and setting below.
                        # The item 'contained' was placed at its scene coordinates in Pass 1.
                        # Calling add_item -> setParentItem adjusts its internal pos()
                        # relative to the container, preserving the visual scene position.
                        # No further explicit setPos is needed here.
                        #
                        # contained_scene_pos = contained.scenePos() # Not needed now
                        # new_relative_pos = container.mapFromScene(contained_scene_pos) # Not needed now
                        # contained.setPos(new_relative_pos) # REMOVED
                        # --- END CHANGE ---

                        relationships_processed += 1
                    else:
                        print(f"Warning: Failed to add {contained.inst_uri} to {container.inst_uri} via add_item.")
                else:
                    print(
                        f"Warning: Invalid 'contains' relationship between {type(container)} ({subject}) and {type(contained)} ({o})")
            else:
                missing = [str(i) for i in (subject, o) if i not in created_items]
                print(f"Warning: Items not found for 'contains': {missing}")

        # --- Pass 2b: Process 'encloses' (Physical -> Domain) ---
        for subject, p, o in g.triples((None, S223.encloses, None)):
            if subject in created_items and o in domain_spaces:  # Check specific domain_spaces dict
                container = created_items[subject]
                domain_space = domain_spaces[o]
                if isinstance(container, PhysicalSpace):
                    # Use the item's method if it exists, otherwise update the set directly
                    if hasattr(container, 'encloses_domain_space'):
                        container.encloses_domain_space(domain_space)
                    else:
                        container.enclosed_domain_spaces.add(domain_space.inst_uri)  # Fallback
                    print(f"Creating 'encloses' relationship: {container.inst_uri} encloses {domain_space.inst_uri}")
                    container.update()  # Update visual if needed
                    relationships_processed += 1
                else:
                    print(f"Warning: 'encloses' subject {container.inst_uri} is not a PhysicalSpace")
            else:
                missing = []
                if subject not in created_items: missing.append(f"container {subject}")
                if o not in domain_spaces: missing.append(f"domain space {o}")
                print(f"Warning: Items not found for 'encloses': {missing}")
        print(f"Processed {relationships_processed} container relationships")

        print("Third pass: Processing connection points...")
        connection_points_processed = 0
        cp_data = {}  # Temporarily store CP data before creating objects
        # Gather all CP data first
        for subject, p, o in g.triples((None, RDF.type, None)):
            if o in ConnectionPoint.allowed_types:
                parent_uri = g.value(subject, S223.isConnectionPointOf)
                if parent_uri:
                    # Store all relevant data found in the graph
                    cp_data[subject] = {
                        'type_uri': o,
                        'parent_uri': parent_uri,
                        'medium': g.value(subject, S223.hasMedium),
                        'rel_x': g.value(subject, VISU.relativeX),
                        'rel_y': g.value(subject, VISU.relativeY),
                        'label': g.value(subject, RDFS.label),
                        'comment': g.value(subject, RDFS.comment),
                        'role': g.value(subject, S223.hasRole)  # Added role
                    }
                else:
                    print(f"Warning: Connection point {subject} is missing 's223:isConnectionPointOf' parent link.")

        # Now create the CP objects
        for cp_uri, data in cp_data.items():
            parent_uri = data['parent_uri']
            if parent_uri in created_items:
                parent = created_items[parent_uri]
                # Ensure parent is a ConnectableItem (not PhysicalSpace)
                if isinstance(parent, ConnectableItem):
                    medium = data['medium']
                    # Provide defaults if relative positions are missing
                    rel_x = float(data['rel_x']) if data['rel_x'] is not None else 0.5
                    rel_y = float(data['rel_y']) if data['rel_y'] is not None else 0.5

                    print(f"Creating connection point {cp_uri} for {parent_uri} at ({rel_x}, {rel_y})")
                    try:
                        cp = ConnectionPoint(
                            connectable=parent,  # Parent is the ConnectableItem instance
                            medium=medium,
                            type_uri=data['type_uri'],
                            inst_uri=cp_uri,
                            position=(rel_x, rel_y)  # Initial position tuple
                        )
                        # Set attributes from loaded data
                        if data['label']: cp.label = str(data['label'])
                        if data['comment']: cp.comment = str(data['comment'])
                        if data['role']: cp.role = data['role']  # Assuming role is stored directly

                        print(f"Adding connection point {cp_uri} to parent {parent_uri}")

                        if not cp.scene():
                            scene.addItem(cp)

                        cp.update_position()  # Ensure visual position is correct

                        connection_points[cp_uri] = cp  # Store for connection pass
                        connection_points_processed += 1
                    except Exception as e:
                        print(f"Error creating ConnectionPoint {cp_uri}: {e}")
                        traceback.print_exc()
                else:
                    print(
                        f"Parent component {parent_uri} for CP {cp_uri} is not a ConnectableItem (it's a {type(parent)}). Skipping CP.")
            else:
                print(
                    f"Parent component {parent_uri} not found in created_items for connection point {cp_uri}. Skipping CP.")
        print(f"Processed {connection_points_processed} connection points")

        print("Fourth pass: Creating connections...")
        connections_created = 0
        # Iterate through connection types
        for subject, p, o in g.triples((None, RDF.type, None)):
            if o in Connection.allowed_types:
                connects_at_uris = list(g.objects(subject, S223.connectsAt))
                if len(connects_at_uris) >= 2:
                    cp_uri1 = connects_at_uris[0]
                    cp_uri2 = connects_at_uris[1]

                    # Check if both connection points were successfully created
                    if cp_uri1 in connection_points and cp_uri2 in connection_points:
                        source_cp = connection_points[cp_uri1]
                        target_cp = connection_points[cp_uri2]

                        # Check if points are already connected (important for loading)
                        if not source_cp.connected_to and not target_cp.connected_to:
                            # Check if connection is possible (optional, but good practice)
                            if source_cp._connection_is_possible(target_cp):
                                try:
                                    print(f"Creating connection {subject} between {cp_uri1} and {cp_uri2}")
                                    connection = Connection(source=source_cp, target=target_cp, type_uri=o,
                                                            inst_uri=subject)

                                    # Load common properties
                                    label = g.value(subject, RDFS.label)
                                    comment = g.value(subject, RDFS.comment)
                                    role = g.value(subject, S223.hasRole)  # Added role
                                    if label: connection.label = str(label)
                                    if comment: connection.comment = str(comment)
                                    if role: connection.role = role  # Assuming role is stored

                                    scene.addItem(connection)
                                    connections_created += 1
                                except ValueError as ve:
                                    print(
                                        f"Error creating connection {subject}: Invalid connection type or setup - {ve}")
                                except Exception as e:
                                    print(f"Error creating connection {subject}: {e}")
                                    traceback.print_exc()
                            else:
                                print(
                                    f"Warning: Skipping connection {subject}. Connection between {cp_uri1} ({source_cp.type_uri}, {source_cp.medium}) and {cp_uri2} ({target_cp.type_uri}, {target_cp.medium}) is not allowed.")
                        else:
                            connected_uris = []
                            if source_cp.connected_to: connected_uris.append(str(cp_uri1))
                            if target_cp.connected_to: connected_uris.append(str(cp_uri2))
                            print(
                                f"Warning: Cannot create connection {subject} - one or both points ({', '.join(connected_uris)}) already connected.")
                    else:
                        missing_cps = [str(cp) for cp in [cp_uri1, cp_uri2] if cp not in connection_points]
                        print(
                            f"Warning: Skipping connection {subject}. Required connection points not found: {missing_cps}")
                else:
                    print(f"Warning: Connection {subject} has fewer than two 's223:connectsAt' points.")
        print(f"Created {connections_created} connections")

        print("Fifth pass: Mapping all properties and their parent relationships...")
        property_map = {}  # Stores URI -> property data dict
        property_parent_map = {}  # Stores prop_uri -> parent_uri

        # Gather all property data first
        for prop_uri, _, prop_type in g.triples((None, RDF.type, None)):
            if prop_type in Property.allowed_types:
                property_map[prop_uri] = {
                    'uri': prop_uri,
                    'type': prop_type,
                    'label': g.value(prop_uri, RDFS.label),
                    'comment': g.value(prop_uri, RDFS.comment),
                    'role': g.value(prop_uri, S223.hasRole),  # Added role
                    'aspect': g.value(prop_uri, S223.hasAspect),
                    'external_reference': g.value(prop_uri, S223.hasExternalReference),
                    'internal_reference': g.value(prop_uri, S223.hasInternalReference),
                    'value': g.value(prop_uri, S223.hasValue),
                    'medium': g.value(prop_uri, S223.hasMedium),
                    'unit': g.value(prop_uri, QUDT.hasUnit),
                    'quantity_kind': g.value(prop_uri, QUDT.hasQuantityKind),
                    'position_x': g.value(prop_uri, VISU.positionX),
                    'position_y': g.value(prop_uri, VISU.positionY),
                    'identifier': g.value(prop_uri, VISU.identifier),
                    'parent_found': False,  # Flag to track if parent link exists
                    'parent_uri': None
                }
                print('positionX', g.value(prop_uri, VISU.positionX))
                print('positionY', g.value(prop_uri, VISU.positionY))

                # Provide defaults for visual properties if missing
                if property_map[prop_uri]['position_x'] is None:
                    property_map[prop_uri]['position_x'] = 0
                if property_map[prop_uri]['position_y'] is None:
                    property_map[prop_uri]['position_y'] = 0
                if property_map[prop_uri]['identifier'] is None:
                    property_map[prop_uri]['identifier'] = ''

        # Find the parent for each property using s223:hasProperty
        for parent_uri, _, prop_uri in g.triples((None, S223.hasProperty, None)):
            if prop_uri in property_map:
                property_parent_map[prop_uri] = parent_uri
                property_map[prop_uri]['parent_uri'] = parent_uri
                property_map[prop_uri]['parent_found'] = True

        print(
            f"Found {len(property_map)} potential properties, {len(property_parent_map)} with direct s223:hasProperty links.")

        print("Sixth pass: Creating Property instances...")
        properties_created = 0

        # Create Property objects and attach them
        for prop_uri, prop_data in property_map.items():
            if not prop_data['parent_found']:
                print(f"Warning: Property {prop_uri} has no parent with s223:hasProperty relationship. Skipping.")
                continue

            parent_uri = prop_data['parent_uri']
            parent_object = None

            # Find the parent instance (can be ConnectableItem or ConnectionPoint)
            if parent_uri in created_items:
                # Check if it's a ConnectableItem (excluding PhysicalSpace)
                potential_parent = created_items[parent_uri]
                if isinstance(potential_parent, ConnectableItem):
                    parent_object = potential_parent

            elif parent_uri in connection_points:
                parent_object = connection_points[parent_uri]

            if not parent_object:
                print(
                    f"Error: Parent object instance for URI {parent_uri} not found for property {prop_uri}. Skipping.")
                continue

            # Parent object must be ConnectableItem or ConnectionPoint
            if not isinstance(parent_object, (ConnectableItem, ConnectionPoint)):
                print(
                    f"Error: Parent {parent_uri} (type: {type(parent_object)}) is not a valid type (ConnectableItem or ConnectionPoint) for property {prop_uri}. Skipping.")
                continue

            try:
                # print(f"Creating property {prop_uri} for parent {parent_uri}")

                position = QPointF(float(prop_data['position_x']), float(prop_data['position_y']))
                identifier = str(prop_data['identifier'])  # Already defaulted in pass 5

                # Create the Property instance
                prop = Property(
                    parent_item=parent_object,  # The actual QGraphicsItem instance
                    property_type=prop_data['type'],
                    inst_uri=prop_uri,
                    identifier=identifier,
                    unit=prop_data.get('unit'),
                    quantity_kind=prop_data.get('quantity_kind')
                )

                prop.setPos(position)

                # Set other attributes from loaded data
                if prop_data['label']: prop.label = str(prop_data['label'])
                if prop_data['comment']: prop.comment = str(prop_data['comment'])
                if prop_data['role']: prop.role = prop_data['role']  # Assuming role stored directly
                if prop_data['aspect']: prop.aspect = prop_data['aspect']
                if prop_data['external_reference']: prop.external_reference = str(prop_data['external_reference'])
                if prop_data['internal_reference']: prop.internal_reference = str(prop_data['internal_reference'])
                if prop_data['value']: prop.value = str(prop_data['value'])
                if prop_data['medium']: prop.medium = prop_data['medium']
                # QUDT already set via constructor

                # Debug print attributes
                # print(f'  Property {prop_uri} attributes:')
                # print(f'    - label: {prop.label}')
                # print(f'    - comment: {prop.comment}')
                # ... etc ...

                # Add to scene if not already added by parenting
                if parent_object.scene() and not prop.scene():
                    scene.addItem(prop)

                # Ensure position is calculated correctly after adding to scene/parent
                # prop.update_position()

                # parent_class = parent_object.__class__.__name__
                # prop_class = prop.__class__.__name__
                # print(f"  Successfully created {prop_class} {prop_uri} for parent {parent_class} {parent_uri}")
                # print(f"  Property position: relative ({prop.relative_x}, {prop.relative_y}), scene pos: ({prop.scenePos().x()}, {prop.scenePos().y()})")

                properties_created += 1

            except Exception as e:
                print(f"Error creating Property instance {prop_uri}: {e}")
                traceback.print_exc()

        print(f"Created {properties_created} properties")

        # --- Pass 7: Create System Items ---
        print("Seventh pass: Creating System items...")
        systems_created = 0
        for subject, p, o in g.triples((None, RDF.type, S223.System)):
            if subject in created_items:  # Should not happen if logic is correct, but check anyway
                print(
                    f"Warning: System {subject} seems to be already created as another type ({type(created_items[subject])}). Skipping.")
                continue

            print(f"Creating System: {subject}")
            # Create SystemItem instance, initially with no members
            system_item = SystemItem(members=[], inst_uri=subject)

            # Load common properties
            label = g.value(subject, RDFS.label)
            comment = g.value(subject, RDFS.comment)
            role = g.value(subject, S223.hasRole)
            if label: system_item.label = str(label)
            if comment: system_item.comment = str(comment)
            if role: system_item.role = role

            # Find and add members
            members_added_count = 0
            for member_uri in g.objects(subject, S223.hasMember):
                if member_uri in created_items:
                    member_item = created_items[member_uri]
                    # Ensure member is a ConnectableItem and NOT Domain/PhysicalSpace
                    if isinstance(member_item, ConnectableItem) and not isinstance(member_item,
                                                                                   (DomainSpace, PhysicalSpace)):
                        if system_item.add_member(member_item):  # add_member updates the set
                            # print(f"  Added member {member_uri} to system {subject}")
                            members_added_count += 1
                        else:
                            print(f"Warning: Failed to add member {member_uri} to system {subject} (already member?).")
                    else:
                        print(
                            f"Warning: Member {member_uri} for system {subject} is not a valid ConnectableItem type (it's {type(member_item)}). Skipping member.")
                else:
                    print(
                        f"Warning: Member item {member_uri} not found in created_items for system {subject}. Skipping member.")

            print(f"  Added {members_added_count} members to system {subject}")

            # Add the system item to the scene
            scene.addItem(system_item)
            created_items[subject] = system_item  # Add to lookup map

            # Update the bounding rectangle *after* all members are potentially added
            system_item.update_bounding_rect()

            systems_created += 1

        print(f"Created {systems_created} systems")

        print("Performing final updates...")
        # Final updates for items that might depend on others being fully loaded
        for item_uri, item in created_items.items():
            if isinstance(item, ConnectableItem):
                # Ensure CPs and their properties are positioned correctly relative to the final parent state
                item.update_connection_points()
                item.update_properties()  # Update properties attached directly to the connectable
                item.update()  # General Qt update
            elif isinstance(item, PhysicalSpace):
                item.update()  # Update visual state if needed (e.g., for contained/enclosed counts)
            elif isinstance(item, SystemItem):
                item.update_bounding_rect()  # Ensure bounding box is correct

        # Update connections as parent positions might have shifted
        for item in scene.items():
            if isinstance(item, Connection):
                item.update_path()

        scene.update()  # Force a full scene redraw

        print(f"Loading completed successfully")
        return True

    except Exception as e:
        print(f"Error loading diagram from {filepath}: {e}")
        traceback.print_exc()  # Print detailed traceback
        # Optionally clear the scene again on error to avoid partial loads
        # scene.clear()
        # if view and hasattr(view, '_draw_grid'):
        #      QTimer.singleShot(0, view._draw_grid)
        return False


class Command:
    def execute(self):
        try:
            self._execute()
            return True
        except Exception as e:
            print(f"Command execution failed: {e}")
            raise e
            return False

    def undo(self):
        try:
            self._undo()
            return True
        except Exception as e:
            print(f"Command undo failed: {e}")
            return False

    def redo(self):
        return self.execute()

    def _execute(self):
        pass

    def _undo(self):
        pass


class MoveCommand(Command):
    def __init__(self, items, old_position, new_position):
        self.items = Selection(items).getConnectable
        offset = new_position - old_position
        self.new_positions = [item.pos() for item in self.items]
        self.old_positions = [item.pos() - offset for item in self.items]

    def _execute(self):
        for i, item in enumerate(self.items):
            item.setPos(self.new_positions[i])

    def _undo(self):
        for i, item in enumerate(self.items):
            item.setPos(self.old_positions[i])


class RotateCommand(Command):
    def __init__(self, items, old_rotations, new_rotations):
        self.items = items
        self.old_rotations = old_rotations
        self.new_rotations = new_rotations

    def _execute(self):
        for i, item in enumerate(self.items):
            item.setRotation(self.new_rotations[i])

    def _undo(self):
        for i, item in enumerate(self.items):
            item.setRotation(self.old_rotations[i])


class ResizeCommand(Command):
    def __init__(self, item, old_size, new_size):
        self.item = item
        self.old_width, self.old_height = old_size
        self.new_width, self.new_height = new_size

    def _execute(self):
        self.item.prepareGeometryChange()
        self.item.width = self.new_width
        self.item.height = self.new_height

        if hasattr(self.item, 'setTransformOriginPoint'):
            self.item.setTransformOriginPoint(self.item.width / 2, self.item.height / 2)

        if hasattr(self.item, 'update_connection_points'):
            self.item.update_connection_points()
        self.item.update()

    def _undo(self):
        self.item.prepareGeometryChange()
        self.item.width = self.old_width
        self.item.height = self.old_height
        if hasattr(self.item, 'setTransformOriginPoint'):
            self.item.setTransformOriginPoint(self.item.width / 2, self.item.height / 2)
        if hasattr(self.item, 'update_connection_points'):
            self.item.update_connection_points()
        self.item.update()


class AddItemCommand(Command):
    def __init__(self, scene, item):
        self.scene = scene
        self.item = item

    def _execute(self):
        self.scene.addItem(self.item)

    def _undo(self):
        self.scene.removeItem(self.item)


class AddContainedItemCommand(Command):
    def __init__(self, container: Union['PhysicalSpace', 'ConnectableItem'],
                 contained: Union['PhysicalSpace', 'ConnectableItem']):
        self.container = container
        self.contained = contained
        self.previous_parent = contained.parentItem()

        self.original_scene_pos_before_parenting = None
        if contained.scene():
            self.original_scene_pos_before_parenting = contained.scenePos()

    def _execute(self):

        if self.contained.scene() and self.original_scene_pos_before_parenting is None:
            self.original_scene_pos_before_parenting = self.contained.scenePos()

        success = self.container.add_item(self.contained)

        if success and self.contained.scene():
            for item in self.contained.scene().items():
                if isinstance(item, SystemItem) and self.contained in item.members:
                    QTimer.singleShot(0, item.update_bounding_rect)

    def _undo(self):

        pos_in_container = self.contained.pos()

        current_scene_pos = self.container.mapToScene(pos_in_container)

        removed = self.container.remove_item(self.contained)

        if removed:

            if self.contained.scene() and self.contained not in self.contained.scene().items():
                self.contained.scene().addItem(self.contained)

            if self.previous_parent and self.previous_parent != self.container:

                pos_in_original_parent = self.previous_parent.mapFromScene(current_scene_pos)
                self.contained.setParentItem(self.previous_parent)
                self.contained.setPos(pos_in_original_parent)

                if hasattr(self.previous_parent, 'add_item'):
                    self.previous_parent.add_item(self.contained)

            elif self.contained.scene():

                if not self.contained.parentItem():
                    self.contained.setPos(current_scene_pos)

            if self.contained.scene():
                for item in self.contained.scene().items():
                    if isinstance(item, SystemItem) and self.contained in item.members:
                        QTimer.singleShot(0, item.update_bounding_rect)


class RemoveContainedItemCommand(Command):
    def __init__(self, container: Union['PhysicalSpace', 'ConnectableItem'],
                 contained: Union['PhysicalSpace', 'ConnectableItem']):
        self.container = container
        self.contained = contained
        self.previous_parent = contained.parentItem()
        self.original_scene_pos = None

    def _execute(self):

        pos_in_container = self.contained.pos()

        self.original_scene_pos = self.container.mapToScene(pos_in_container)

        removed = self.container.remove_item(self.contained)

        if removed and self.contained.scene():

            self.contained.setPos(self.original_scene_pos)

            if self.contained not in self.contained.scene().items():
                self.contained.scene().addItem(self.contained)

            for item in self.contained.scene().items():
                if isinstance(item, SystemItem) and self.contained in item.members:
                    QTimer.singleShot(0, item.update_bounding_rect)

    def _undo(self):

        current_scene_pos = self.contained.scenePos() if self.contained.scene() else QPointF(0, 0)

        added = self.container.add_item(self.contained)

        if added:

            new_relative_pos = self.container.mapFromScene(current_scene_pos)

            self.contained.setPos(new_relative_pos)

            if self.contained.scene():
                for item in self.contained.scene().items():
                    if isinstance(item, SystemItem) and self.contained in item.members:
                        QTimer.singleShot(0, item.update_bounding_rect)


class RemoveItemCommand(Command):

    def __init__(self, scene, items_to_remove):
        self.scene = scene
        selection = Selection(items_to_remove)

        self.directly_selected = set(items_to_remove)

        self.connectables_selected = set(selection.getConnectable)
        self.cps_selected = set(selection.getConnectionPoint)
        self.props_selected = set(selection.getProperty)
        self.conns_selected = set(selection.getConnection)
        self.systems_selected = set(selection.getSystem)
        self.phys_spaces_selected = set(selection.getPhysicalSpace)

        self.cps_implicit = set()
        self.props_implicit_from_connectable = set()
        for conn in self.connectables_selected:
            self.cps_implicit.update(conn.connection_points)
            self.props_implicit_from_connectable.update(conn.properties)

        self.props_implicit_from_cp = set()
        for cp in self.cps_selected | self.cps_implicit:

            if hasattr(cp, 'properties'):
                self.props_implicit_from_cp.update(cp.properties)

        self.conns_implicit = set()
        for cp in self.cps_selected | self.cps_implicit:
            if cp.connected_to:
                self.conns_implicit.add(cp.connected_to)

        self.all_connectables = self.connectables_selected | self.phys_spaces_selected
        self.all_cps = self.cps_selected | self.cps_implicit
        self.all_props = self.props_selected | self.props_implicit_from_connectable | self.props_implicit_from_cp
        self.all_conns = self.conns_selected | self.conns_implicit
        self.all_systems = self.systems_selected

        self.connection_details = {conn: {'source': conn.source, 'target': conn.target}
                                   for conn in self.all_conns}
        self.property_details = {prop: {'parent': prop.parent_item}
                                 for prop in self.all_props}
        self.cp_details = {cp: {'parent': cp.connectable}
                           for cp in self.all_cps}
        self.system_members = {sys: list(sys.members) for sys in self.all_systems}

        self.parent_details = {item: item.parentItem() for item in
                               self.all_connectables | self.all_cps | self.all_props}

    def _execute(self):

        for item in self.all_systems:
            if item.scene(): self.scene.removeItem(item)
        for item in self.all_conns:
            if item.scene(): item.remove(self.scene)
        for item in self.all_props:
            if item.scene(): item.remove(self.scene)
        for item in self.all_cps:
            if item.scene(): item.remove(self.scene)
        for item in self.all_connectables:
            if item.scene(): item.remove(self.scene)

    def _undo(self):

        restored_parents = set()
        for item in self.all_connectables:

            original_parent = self.parent_details.get(item)
            if item.scene() is None:
                self.scene.addItem(item)

                if original_parent and original_parent.scene():
                    item.setParentItem(original_parent)
                    if hasattr(original_parent, 'add_item'):
                        original_parent.add_item(item)
            restored_parents.add(item)

        for item in self.all_cps:
            parent_connectable = self.cp_details.get(item, {}).get('parent')
            if item.scene() is None and parent_connectable and parent_connectable.scene():
                item.setParentItem(parent_connectable)
                parent_connectable.add_connection_point(item)
                self.scene.addItem(item)
            restored_parents.add(item)

        for item in self.all_props:
            parent_item = self.property_details.get(item, {}).get('parent')
            if item.scene() is None and parent_item and parent_item.scene():
                item.setParentItem(parent_item)
                parent_item.add_property(item)
                self.scene.addItem(item)

        for item, details in self.connection_details.items():
            source = details['source']
            target = details['target']

            if item.scene() is None and source and source.scene() and target and target.scene():

                if source.connected_to is None and target.connected_to is None:
                    item.source = source
                    item.target = target
                    source.connected_to = item
                    target.connected_to = item
                    self.scene.addItem(item)
                    item.update_path()
                else:
                    print(f"Undo Warning: Cannot restore connection {item.inst_uri}, points already connected.")

        for item in self.all_systems:
            if item.scene() is None:
                self.scene.addItem(item)
            item.members.clear()
            original_members = self.system_members.get(item, [])
            for member_item in original_members:
                if member_item.scene():
                    item.add_member(member_item)
            item.update_bounding_rect()


class AddPropertyCommand(Command):

    def __init__(self, parent_item: Union['ConnectableItem', 'ConnectionPoint'], property_data):
        self.parent_item = parent_item
        self.property_data = property_data
        self.property = None

    def _execute(self):
        if not self.property:
            self.property = Property(
                parent_item=self.parent_item,
                property_type=self.property_data['property_type'],
                identifier=self.property_data['identifier']
            )
            try:
                pos = QPointF(self.property_data['position_x'], self.property_data['position_y'])
                self.property.setPos(pos)
            except KeyError:
                raise KeyError(self.property_data)

            self.property.aspect = self.property_data.get('aspect')
            self.property.external_reference = self.property_data.get('external_reference', "")
            self.property.internal_reference = self.property_data.get('internal_reference')

            self.property.unit = self.property_data.get('unit')
            self.property.quantity_kind = self.property_data.get('quantity_kind')

            self.property.value = self.property_data.get('value', "")
            self.property.medium = self.property_data.get('medium')
        else:
            self.parent_item.add_property(self.property)

    def _undo(self):
        if self.property and self.property in self.parent_item.properties:
            self.parent_item.remove_property(self.property)


class MovePropertyCommand(Command):
    def __init__(self, property_item, new_position, old_position):
        self.property = property_item

        self.new_position = new_position
        self.old_position = old_position

    def _execute(self):
        self.property.setPos(self.new_position)

    def _undo(self):
        self.property.setPos(self.old_position)


class AddConnectionCommand(Command):
    def __init__(self, scene, source, target, type_uri=None):
        self.scene = scene
        self.source = source
        self.target = target
        self.type_uri = type_uri or S223.Pipe
        self.connection = None

    def _execute(self):
        if not self.connection:
            self.connection = Connection(
                source=self.source,
                target=self.target,
                type_uri=self.type_uri
            )
        self.scene.addItem(self.connection)

    def _undo(self):
        if self.connection in self.scene.items():
            self.connection.source.connected_to = None
            self.connection.target.connected_to = None
            self.scene.removeItem(self.connection)


class RemoveConnectionCommand(Command):
    def __init__(self, scene, connection):
        self.scene = scene
        self.connection = connection
        self.source = connection.source
        self.target = connection.target
        self.type_uri = connection.type_uri

    def _execute(self):
        self.source.connected_to = None
        self.target.connected_to = None
        self.scene.removeItem(self.connection)

    def _undo(self):
        self.scene.addItem(self.connection)
        self.source.connected_to = self.connection
        self.target.connected_to = self.connection


class AddConnectionPointCommand(Command):
    def __init__(self, connectable, position_x, position_y, medium, type_uri):
        self.connectable: ConnectableItem = connectable
        self.position_x = position_x
        self.position_y = position_y
        self.medium = medium
        self.type_uri = type_uri
        self.connection_point = None

    def _execute(self):
        if not self.connection_point:
            self.connection_point = ConnectionPoint(
                connectable=self.connectable,
                position=(self.position_x, self.position_y),
                medium=self.medium,
                type_uri=self.type_uri
            )
        else:
            self.connectable.add_connection_point(self.connection_point)

    def _undo(self):
        if self.connection_point in self.connectable.connection_points:
            self.connectable.connection_points.remove(self.connection_point)
            if self.connection_point.scene():
                self.connection_point.scene().removeItem(self.connection_point)


class ChangeAttributeCommand(Command):
    def __init__(self, items, attribute_name, new_value, update_func=None):
        self.items = items
        self.attribute_name = attribute_name
        self.new_value = new_value
        self.old_values = [getattr(item, attribute_name) for item in items]
        self.update_func = update_func

    def _execute(self):
        for i, item in enumerate(self.items):
            setattr(item, self.attribute_name, self.new_value)
            if self.update_func:
                self.update_func(item)

    def _undo(self):
        for i, item in enumerate(self.items):
            setattr(item, self.attribute_name, self.old_values[i])
            if self.update_func:
                self.update_func(item)


class ChangeConnectionTypeCommand(Command):
    def __init__(self, connections, new_type_uri):
        self.connections = connections
        self.new_type_uri = new_type_uri
        self.old_type_uris = [conn.type_uri for conn in connections]

    def _execute(self):
        for conn in self.connections:
            conn.type_uri = self.new_type_uri
            conn.update_path()

    def _undo(self):
        for i, conn in enumerate(self.connections):
            conn.type_uri = self.old_type_uris[i]
            conn.update_path()


class ChangeConnectionMediumCommand(Command):
    def __init__(self, connections, new_medium):
        self.connections = connections
        self.new_medium = new_medium
        self.old_media = [(conn.source.medium, conn.target.medium) for conn in connections]

    def _execute(self):
        for conn in self.connections:
            conn.source.medium = self.new_medium
            conn.target.medium = self.new_medium
            conn.update_path()

    def _undo(self):
        for i, conn in enumerate(self.connections):
            conn.source.medium = self.old_media[i][0]
            conn.target.medium = self.old_media[i][1]
            conn.update_path()


class AddContainedSpaceCommand(Command):
    def __init__(self, container: 'PhysicalSpace', contained: 'PhysicalSpace'):
        self.container = container
        self.contained = contained
        self.previous_parent = contained.parentItem()

    def _execute(self):
        self.container.add_physical_space(self.contained)

    def _undo(self):
        self.container.remove_physical_space(self.contained)

        if self.previous_parent and self.previous_parent != self.container:
            self.contained.setParentItem(self.previous_parent)
        elif self.contained.scene():
            pass


class RemoveContainedSpaceCommand(Command):
    def __init__(self, container: 'PhysicalSpace', contained: 'PhysicalSpace'):
        self.container = container
        self.contained = contained
        self.previous_parent = contained.parentItem()

    def _execute(self):
        self.container.remove_physical_space(self.contained)

    def _undo(self):
        self.container.add_physical_space(self.contained)


class AddEnclosedSpaceCommand(Command):
    def __init__(self, container: 'PhysicalSpace', enclosed: 'DomainSpace'):
        self.container = container
        self.enclosed = enclosed
        self.enclosed_uri = enclosed.inst_uri

    def _execute(self):
        self.container.enclosed_domain_spaces.add(self.enclosed_uri)
        self.container.update()

    def _undo(self):
        if self.enclosed_uri in self.container.enclosed_domain_spaces:
            self.container.enclosed_domain_spaces.remove(self.enclosed_uri)
            self.container.update()


class RemoveEnclosedSpaceCommand(Command):
    def __init__(self, container: 'PhysicalSpace', enclosed: 'DomainSpace'):
        self.container = container
        self.enclosed = enclosed
        self.enclosed_uri = enclosed.inst_uri

    def _execute(self):
        if self.enclosed_uri in self.container.enclosed_domain_spaces:
            self.container.enclosed_domain_spaces.remove(self.enclosed_uri)
            self.container.update()

    def _undo(self):
        self.container.enclosed_domain_spaces.add(self.enclosed_uri)
        self.container.update()


class ChangeLabelCommand(Command):
    def __init__(self, items, new_label):
        self.items = items
        self.new_label = new_label
        self.old_label = [item.label for item in items]

    def _execute(self):
        for item in self.items:
            item.label = self.new_label

    def _undo(self):
        for i, item in enumerate(self.items):
            item.label = self.old_label[i]


class CreateSystemCommand(Command):
    def __init__(self, scene, system: 'SystemItem'):
        self.scene = scene
        self.system = system
        self.parent = None

    def _execute(self):
        self.scene.addItem(self.system)
        self.system.update_bounding_rect()

    def _undo(self):
        self.scene.removeItem(self.system)


class CompoundCommand(Command):
    def __init__(self, name="Compound Command"):
        self.commands = []
        self.name = name

    def add_command(self, command):
        self.commands.append(command)

    def _execute(self):
        for command in self.commands:
            command.execute()

    def _undo(self):
        for command in reversed(self.commands):
            command.undo()


class CommandHistory(QObject):
    """Manages undo/redo functionality and signals changes."""
    history_changed = pyqtSignal()

    def __init__(self, max_history=100):
        super().__init__()
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = max_history

    def push(self, command: 'Command'):
        """Executes a command and adds it to the undo stack."""
        if command.execute():
            self.undo_stack.append(command)
            self.redo_stack.clear()

            if len(self.undo_stack) > self.max_history:
                self.undo_stack.pop(0)

            self.history_changed.emit()
            return True
        return False

    def undo(self):
        """Undoes the last command."""
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        if command.undo():
            self.redo_stack.append(command)
            self.history_changed.emit()
            return True

        self.undo_stack.append(command)
        return False

    def redo(self):
        """Redoes the last undone command."""
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        if command.execute():
            self.undo_stack.append(command)
            self.history_changed.emit()
            return True

        self.redo_stack.append(command)
        return False

    def clear(self):
        """Clears both undo and redo stacks."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.history_changed.emit()


class CanvasProperties:
    width: int = 1500
    height: int = 1000
    grid_size: int = 25
    frame_width = 2
    frame_color = Qt.black
    enable_grid: bool = True

    @classmethod
    def snap_to_grid(cls, point: QPointF):
        if not cls.enable_grid or cls.grid_size <= 0:
            return point

        # Directly snap the coordinates of the input point
        snapped_x = round(point.x() / cls.grid_size) * cls.grid_size
        snapped_y = round(point.y() / cls.grid_size) * cls.grid_size

        return QPointF(snapped_x, snapped_y)


class PhysicalSpace(QGraphicsItem):
    HANDLE_SIZE = 10
    MIN_SIZE = 50
    PADDING = 10
    COLOR = QColor(240, 240, 240)
    COLOR_ALPHA = 150
    COLOR_SELECTED = QColor(200, 200, 220)
    COLOR_BORDER = Qt.black

    def __init__(self, inst_uri: rdflib.URIRef = None):
        super().__init__()

        self.inst_uri = inst_uri if inst_uri else BLDG[short_uuid()]
        self.label: str = to_label(self.inst_uri)
        self.comment: str = str()
        self.enclosed_domain_spaces: set = set()
        self.contained_items: set[Union['PhysicalSpace', 'ConnectableItem']] = set()
        self.role: rdflib.URIRef | None = None

        self.width = 200
        self.height = 150

        self.initial_position = None
        self.resizing = False
        self.resize_handle_corner = Qt.BottomRightCorner
        self.resize_start_pos = None
        self.resize_start_rect = None

        self._setup()

    def _setup(self):
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setZValue(2)
        self.setAcceptHoverEvents(True)
        self.setAcceptDrops(True)

    def get_handle_rect(self) -> QRectF:
        """Calculate the rectangle for the resize handle."""
        handle_x = self.width - self.HANDLE_SIZE - self.PADDING / 2
        handle_y = self.height - self.HANDLE_SIZE - self.PADDING / 2
        return QRectF(handle_x, handle_y, self.HANDLE_SIZE, self.HANDLE_SIZE)

    def encloses_domain_space(self, domain_space: 'ConnectableItem') -> bool:
        if isinstance(domain_space, DomainSpace):
            self.enclosed_domain_spaces.add(domain_space.inst_uri)
            self.update()
            return True
        return False

    def remove_enclosed_domain_space(self, domain_space: 'ConnectableItem') -> bool:
        if domain_space.inst_uri in self.enclosed_domain_spaces:
            self.enclosed_domain_spaces.remove(domain_space.inst_uri)
            self.update()
            return True
        return False

    def add_item(self, item: Union['PhysicalSpace', 'ConnectableItem']) -> bool:

        if not isinstance(item, PhysicalSpace):
            print(f"Error: PhysicalSpace '{self.label}' cannot contain item of type {type(item)}.")
            return False

        if item not in self.contained_items:

            parent = self.parentItem()
            while parent:
                if parent == item:
                    print("Error: Cannot create cyclic containment.")
                    return False
                parent = parent.parentItem()

            self.contained_items.add(item)
            item.setParentItem(self)
            self.update()
            return True
        return False

    def remove_item(self, item: Union['PhysicalSpace', 'ConnectableItem']) -> bool:
        if item in self.contained_items:
            self.contained_items.remove(item)
            item.setParentItem(None)

            if self.scene() and item not in self.scene().items():
                self.scene().addItem(item)
            self.update()
            return True
        return False

    def paint(self, painter: QPainter, option, widget=None):

        rect = self.boundingRect()

        pen_color = self.COLOR_BORDER
        pen_width = 1
        fill_color = QColor(self.COLOR)
        fill_color.setAlpha(self.COLOR_ALPHA)

        if self.isSelected():
            pen_color = self.COLOR_SELECTED
            pen_width = 2

            fill_color = QColor(self.COLOR_SELECTED)
            fill_color.setAlpha(self.COLOR_ALPHA + 20)

        pen = QPen(pen_color, pen_width)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill_color))
        painter.drawRect(rect)

        info_text = ""

        if self.contained_items: info_text += f"C:{len(self.contained_items)} "
        if self.enclosed_domain_spaces: info_text += f"E:{len(self.enclosed_domain_spaces)}"
        if info_text:
            info_font = QFont()
            info_font.setPointSize(8)
            painter.setFont(info_font)

            painter.setPen(Qt.black)

            text_rect = QRectF(rect.left() + self.PADDING / 2 + 5,
                               rect.bottom() - self.PADDING / 2 - 20,
                               rect.width() - self.PADDING - 10, 15)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignBottom, info_text.strip())

        if self.isSelected():
            handle_rect = self.get_handle_rect()
            painter.setPen(QPen(Qt.black, 1))
            painter.setBrush(QBrush(Qt.white))
            painter.drawRect(handle_rect)

    def boundingRect(self) -> QRectF:

        return QRectF(0, 0, self.width, self.height)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene() and not self.resizing:
            if CanvasProperties.enable_grid:
                return CanvasProperties.snap_to_grid(value)
            return value
        elif change == QGraphicsItem.ItemPositionHasChanged:

            pass
        elif change == QGraphicsItem.ItemParentHasChanged:

            pass

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        handle_rect = self.get_handle_rect()
        pos_in_item = event.pos()

        if self.isSelected() and handle_rect.contains(pos_in_item) and event.button() == Qt.LeftButton:
            self.resizing = True
            self.resize_start_pos = pos_in_item
            self.resize_start_rect = self.boundingRect()
            self.setCursor(Qt.SizeFDiagCursor)
            event.accept()
        elif event.button() == Qt.LeftButton:
            self.initial_position = self.pos()
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = event.pos() - self.resize_start_pos
            new_width = self.resize_start_rect.width() + delta.x()
            new_height = self.resize_start_rect.height() + delta.y()

            new_width = max(self.MIN_SIZE, new_width)
            new_height = max(self.MIN_SIZE, new_height)

            if new_width != self.width or new_height != self.height:
                self.prepareGeometryChange()
                self.width = new_width
                self.height = new_height

                self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing and event.button() == Qt.LeftButton:
            self.resizing = False
            self.setCursor(Qt.ArrowCursor)
            if self.boundingRect() != self.resize_start_rect:
                scene = self.scene()
                if scene:
                    old_size = (self.resize_start_rect.width(), self.resize_start_rect.height())
                    new_size = (self.width, self.height)

                    command = ResizeCommand(self, old_size, new_size)
                    push_command_to_scene(scene, command)
            self.resize_start_pos = None
            self.resize_start_rect = None
            event.accept()
        elif event.button() == Qt.LeftButton and self.initial_position is not None and not self.resizing:

            if self.pos() != self.initial_position:
                scene = self.scene()
                if scene:
                    items_to_move = [self]

                    command = MoveCommand(items_to_move, self.initial_position, self.pos())
                    push_command_to_scene(scene, command)
            self.initial_position = None
            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event):
        handle_rect = self.get_handle_rect()
        if self.isSelected() and handle_rect.contains(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        source_widget = event.source()
        if isinstance(source_widget, QGraphicsView):
            items = source_widget.scene().selectedItems()
            if items:
                source_item = items[0]

                if isinstance(source_item, PhysicalSpace) and source_item != self:
                    event.accept()
                    return
                elif isinstance(source_item, DomainSpace):
                    event.accept()
                    return
        event.ignore()

    def dragMoveEvent(self, event):

        self.dragEnterEvent(event)

    def dropEvent(self, event):
        source_widget = event.source()
        if isinstance(source_widget, QGraphicsView):
            items = source_widget.scene().selectedItems()
            if items:
                source_item = items[0]
                scene = self.scene()

                if isinstance(source_item, PhysicalSpace) and source_item != self:

                    command = AddContainedItemCommand(self, source_item)
                    if push_command_to_scene(scene, command):
                        event.accept()
                        find_status_bar(scene.views()[0]).showMessage(f"Added '{source_item.label}' to '{self.label}'")
                    else:
                        event.ignore()

                elif isinstance(source_item, DomainSpace):

                    command = AddEnclosedSpaceCommand(self, source_item)
                    if push_command_to_scene(scene, command):
                        event.accept()
                        find_status_bar(scene.views()[0]).showMessage(
                            f"'{self.label}' now encloses '{source_item.label}'")
                    else:
                        event.ignore()
                else:
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()

    def remove(self, scene):

        for child_item in list(self.contained_items):
            self.remove_item(child_item)

        if self.parentItem():

            if isinstance(self.parentItem(), (PhysicalSpace, ConnectableItem)):
                self.parentItem().remove_item(self)
            else:
                self.setParentItem(None)

        if self.scene():
            scene.removeItem(self)


class Property(QGraphicsItem):
    """Represents a property (datapoint) associated with a component or connection point."""

    default_size = 10
    hover_size = 12
    offset_scale = 15

    allowed_types = [
        S223.Property, S223.ObservableProperty, S223.ActuatableProperty,
        S223.EnumerableProperty, S223.QuantifiableProperty,
        S223.QuantifiableObservableProperty, S223.QuantifiableActuatableProperty,
        S223.EnumeratedObservableProperty, S223.EnumeratedActuatableProperty,
    ]

    def __init__(self,

                 parent_item: Union['ConnectableItem', 'ConnectionPoint'],
                 property_type: rdflib.URIRef = None,
                 inst_uri: rdflib.URIRef = None,
                 identifier: str = "P",
                 unit: Optional[rdflib.URIRef] = None,
                 quantity_kind: Optional[rdflib.URIRef] = None,
                 ):
        super().__init__(parent=parent_item)

        if property_type and property_type not in self.allowed_types:
            print(f"Warning: Property type {property_type} not in allowed list. Defaulting to s223:Property.")
            property_type = S223.Property

        self.parent_item = parent_item
        self._property_type = property_type or S223.Property
        self.inst_uri = inst_uri if inst_uri else BLDG[short_uuid()]
        self._label: str = str()
        self._comment: str = str()

        self._aspect = None
        self._external_reference = str()
        self._internal_reference = None
        self._value = int()
        self._medium = None

        self._unit: Optional[rdflib.URIRef] = unit
        self._quantity_kind: Optional[rdflib.URIRef] = quantity_kind

        self._identifier = identifier if identifier else str()

        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(-10)
        self.setAcceptHoverEvents(True)

        parent_item.add_property(self)

        self.initial_position: QPointF = QPointF(0, 0)

    @property
    def property_type(self):
        return self._property_type

    @property_type.setter
    def property_type(self, value):
        if value in self.allowed_types:
            self._property_type = value
        else:
            print(f"Warning: Invalid property type {value}. Keeping {self._property_type}.")

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._label = str(value)

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, value):
        self._comment = str(value)

    @property
    def aspect(self):
        return self._aspect

    @aspect.setter
    def aspect(self, value):
        self._aspect = value

    @property
    def external_reference(self):
        return self._external_reference

    @external_reference.setter
    def external_reference(self, value):
        self._external_reference = str(value)

    @property
    def internal_reference(self):
        return self._internal_reference

    @internal_reference.setter
    def internal_reference(self, value):
        self._internal_reference = str(value)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = str(value)

    @property
    def medium(self):
        return self._medium

    @medium.setter
    def medium(self, value):
        self._medium = value

    @property
    def identifier(self):
        return self._identifier

    @identifier.setter
    def identifier(self, value):
        self._identifier = str(value)[:1] if value else "P"
        self.update()

    @property
    def unit(self) -> Optional[rdflib.URIRef]:
        return self._unit

    @unit.setter
    def unit(self, value: Optional[rdflib.URIRef]):
        if value is None or isinstance(value, rdflib.URIRef):
            self._unit = value
        else:
            print(f"Warning: Invalid type for unit: {type(value)}. Expected URIRef or None.")

    @property
    def quantity_kind(self) -> Optional[rdflib.URIRef]:
        return self._quantity_kind

    @quantity_kind.setter
    def quantity_kind(self, value: Optional[rdflib.URIRef]):
        if value is None or isinstance(value, rdflib.URIRef):
            self._quantity_kind = value
        else:
            print(f"Warning: Invalid type for quantity_kind: {type(value)}. Expected URIRef or None.")

    def boundingRect(self):
        adjust = (self.hover_size - self.default_size) / 2
        return QRectF(-self.default_size / 2 - adjust, -self.default_size / 2 - adjust,
                      self.default_size + 2 * adjust, self.default_size + 2 * adjust)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(QRectF(-self.default_size / 2, -self.default_size / 2,
                               self.default_size, self.default_size))
        return path

    def paint(self, painter, option, widget):

        if self.parent_item:
            parent_center_in_parent_coords = QPointF(0, 0)

            if isinstance(self.parent_item, ConnectableItem):

                parent_rect = self.parent_item.boundingRect()
                parent_center_in_parent_coords = parent_rect.center()
            elif isinstance(self.parent_item, ConnectionPoint):

                cp_rect = self.parent_item.rect()
                parent_center_in_parent_coords = cp_rect.center()

            parent_center_in_property_coords = QPointF(0, 0)
            try:
                parent_center_in_property_coords = self.mapFromItem(
                    self.parent_item, parent_center_in_parent_coords
                )
            except Exception as e:

                pass

            painter.setPen(QPen(Qt.darkGray, 1, Qt.DashLine))
            painter.drawLine(QPointF(0, 0), parent_center_in_property_coords)

        current_size = self.hover_size if option.state & QStyle.State_MouseOver else self.default_size
        ellipse_rect = QRectF(-current_size / 2, -current_size / 2, current_size, current_size)

        if self.isSelected():
            painter.setPen(QPen(Qt.black, 1.5))
            painter.setBrush(QBrush(Qt.lightGray))
        else:
            painter.setPen(QPen(Qt.black, 1))
            painter.setBrush(QBrush(Qt.white))
        painter.drawEllipse(ellipse_rect)

        font = painter.font()
        font.setPointSize(int(current_size * 0.6))
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(ellipse_rect, Qt.AlignCenter, self.identifier)

    def itemChange(self, change, value):

        if change == QGraphicsItem.ItemPositionChange and self.scene() and self.parent_item:
            if CanvasProperties.enable_grid:
                proposed_scene_center_pos = self.parent_item.mapToScene(value)
                snapped_scene_center_pos = CanvasProperties.snap_to_grid(proposed_scene_center_pos)
                corrected_parent_pos = self.parent_item.mapFromScene(snapped_scene_center_pos)
                return corrected_parent_pos
            else:
                return value

        elif change == QGraphicsItem.ItemPositionHasChanged:
            pass

        return super().itemChange(change, value)

    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:
            self.initial_position = self.pos()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.initial_position is not None:

            current_position = self.pos()

            if current_position != self.initial_position:
                scene = self.scene()
                if scene:
                    command = MovePropertyCommand(
                        self,
                        old_position=self.initial_position,
                        new_position=current_position,
                    )
                    push_command_to_scene(scene, command)

            self.initial_position = None

        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.update()
        super().hoverLeaveEvent(event)

    def remove(self, scene):
        """Removes the property from its parent and the scene."""
        if self.parent_item and hasattr(self.parent_item, 'remove_property'):
            self.parent_item.remove_property(self)
        else:

            self.setParentItem(None)
        if self.scene():
            scene.removeItem(self)


class ConnectableItem(QGraphicsSvgItem):

    def __init__(self, type_uri: rdflib.URIRef, inst_uri: rdflib.URIRef = None):

        self.properties: list[Property] = []

        self.type_uri = type_uri
        self.inst_uri = inst_uri if inst_uri else BLDG[short_uuid()]
        self.label: str = ""
        self.comment: str = ""
        self.role: rdflib.URIRef | None = None
        self.contained_items: set['ConnectableItem'] = set()
        self.physical_location_uri: Optional[rdflib.URIRef] = None
        self.observation_location_uri: Optional[rdflib.URIRef] = None

        super().__init__()

        svg_data = svg_library.get(self.type_uri)
        if not svg_data:
            print(f"Warning: No SVG data found for {self.type_uri}. Using fallback.")

            self.renderer = None
            self.width = 50
            self.height = 50

            self.setElementId("")
        else:
            self.renderer = QSvgRenderer(QByteArray(svg_data.encode()))
            self.width = self.renderer.defaultSize().width()
            self.height = self.renderer.defaultSize().height()
            self.setSharedRenderer(self.renderer)

        self.setTransformOriginPoint(self.width / 2, self.height / 2)
        self.setFlags(
            QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setZValue(3)
        self.setScale(1.0)
        self.setAcceptDrops(True)

        self.connection_points: list[ConnectionPoint] = []

        self.initial_position = None

    def __str__(self):
        return f"{self.__class__.__name__}(ports={[str(port) for port in self.connection_points]})"

    def boundingRect(self) -> QRectF:

        if self.renderer:
            return self.renderer.viewBoxF()
        else:

            return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget=None):
        if self.renderer:
            super().paint(painter, option, widget)
        else:

            rect = self.boundingRect()
            painter.setPen(QPen(Qt.black))
            painter.setBrush(QBrush(Qt.lightGray))
            painter.drawRect(rect)

            painter.drawText(rect, Qt.AlignCenter, self.label or to_label(self.type_uri))

    def load_default_connection_points(self):
        print('Loading default connection points for', self.inst_uri)

        ports_data = port_library.get(self.type_uri, [])

        for cp in list(self.connection_points):
            self.remove_connection_point(cp)

        for port_config in ports_data:
            try:

                ConnectionPoint(connectable=self, **port_config)

            except Exception as e:
                print(f"Error creating connection point for {self.inst_uri}: {e} with config {port_config}")

    def add_property(self, property_item: Property):
        """Add a property to this component."""

        if property_item not in self.properties:
            self.properties.append(property_item)

            if property_item.parentItem() != self:
                property_item.setParentItem(self)

            if self.scene() and not property_item.scene():
                self.scene().addItem(property_item)

        return property_item

    def remove_property(self, property_item: Property):
        """Remove a property from this component."""
        if property_item in self.properties:
            self.properties.remove(property_item)

            return True
        return False

    def update_properties(self):
        """Update positions of properties attached directly to this component."""

        parent_width = self.boundingRect().width()
        parent_height = self.boundingRect().height()
        # for prop in self.properties:
        #     prop.update_position()

    def update_connection_points(self):
        """Update the position of connection points and their properties."""

        br = self.boundingRect()
        self.width = br.width()
        self.height = br.height()

        for cp in self.connection_points:
            cp.update_position()
            if cp.connected_to:
                cp.connected_to.update_path()

        self.update_properties()

    def add_connection_point(self, connection_point: 'ConnectionPoint'):
        if connection_point not in self.connection_points:
            self.connection_points.append(connection_point)
            if connection_point.parentItem() != self:
                connection_point.setParentItem(self)
            if self.scene() and not connection_point.scene():
                self.scene().addItem(connection_point)
            connection_point.update_position()
        return connection_point

    def add_item(self, item: 'ConnectableItem') -> bool:
        # Equipment (ConnectableItem) can only contain Equipment (ConnectableItem)
        # Exclude DomainSpace and PhysicalSpace from being contained by Equipment
        if not isinstance(item, ConnectableItem) or isinstance(item, (DomainSpace, PhysicalSpace)):
            print(f"Error: Equipment '{self.label}' cannot contain item of type {type(item)}.")
            return False

        if item != self and item not in self.contained_items:
            # Prevent cyclic containment
            parent = self.parentItem()
            while parent:
                if parent == item:
                    print("Error: Cannot create cyclic containment.")
                    return False
                parent = parent.parentItem()

            self.contained_items.add(item)
            item.setParentItem(self)  # Manage hierarchy visually
            self.update()  # Update visual indicator if any
            return True
        return False

    def remove_item(self, item: 'ConnectableItem') -> bool:
        if item in self.contained_items:
            self.contained_items.remove(item)
            item.setParentItem(None)  # Unparent
            # Ensure the removed item is added back to the scene
            if self.scene() and item not in self.scene().items():
                self.scene().addItem(item)
            self.update()  # Update visual indicator if any
            return True
        return False

    def remove_connection_point(self, connection_point: 'ConnectionPoint'):
        """Removes a connection point from this component and the scene."""
        if connection_point in self.connection_points:
            self.connection_points.remove(connection_point)

            if connection_point.scene():
                connection_point.remove(connection_point.scene())
            return True
        return False

    def itemChange(self, change, value):
        scene = self.scene()

        if change == QGraphicsItem.ItemPositionChange and scene and not getattr(self, 'resizing', False):

            if CanvasProperties.enable_grid:
                origin_in_item_coords = self.transformOriginPoint()
                proposed_top_left_pos = value
                proposed_center_pos = proposed_top_left_pos + origin_in_item_coords
                snapped_center_pos = CanvasProperties.snap_to_grid(proposed_center_pos)
                snapped_top_left_pos = snapped_center_pos - origin_in_item_coords
                new_pos = snapped_top_left_pos
            else:
                new_pos = value

            return new_pos

        elif (change == QGraphicsItem.ItemPositionHasChanged or change == QGraphicsItem.ItemParentHasChanged) and scene:

            QTimer.singleShot(0, self.update_connection_points)

            for sys_item in scene.items():
                if isinstance(sys_item, SystemItem) and self in sys_item.members:
                    QTimer.singleShot(0, sys_item.update_bounding_rect)

        return super().itemChange(change, value)

    def remove(self, scene):
        """Removes the item, its children (contained items, CPs, properties), and cleans up."""

        for child_item in list(self.contained_items):
            self.remove_item(child_item)

        parent = self.parentItem()
        if parent and hasattr(parent, 'remove_item'):

            parent.remove_item(self)
        elif parent:

            self.setParentItem(None)

        for prop in list(self.properties):
            prop.remove(scene)

        for connection_point in list(self.connection_points):
            connection_point.remove(scene)

        for item in scene.items():
            if isinstance(item, SystemItem) and self in item.members:
                item.remove_member(self)

        if self.scene():
            scene.removeItem(self)


class DomainSpace(ConnectableItem):
    HANDLE_SIZE = 10
    MIN_SIZE = 40
    PADDING = 5
    COLOR = QColor(200, 240, 200)
    COLOR_ALPHA = 180
    COLOR_SELECTED = QColor(100, 180, 100)
    COLOR_BORDER = QColor(128, 200, 128)

    def __init__(self, type_uri=S223.DomainSpace, inst_uri=None):

        super().__init__(type_uri=type_uri, inst_uri=inst_uri)

        self.domain: rdflib.URIRef | None = None

        self.renderer = None
        self.width = 150
        self.height = 100
        self.setElementId("")

        self.setTransformOriginPoint(self.width / 2, self.height / 2)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(2.5)

        self.resizing = False
        self.resize_handle_corner = Qt.BottomRightCorner
        self.resize_start_pos = None
        self.resize_start_rect = None

        self.update_connection_points()

    def get_handle_rect(self) -> QRectF:
        """Calculate the rectangle for the resize handle."""

        handle_x = self.width - self.HANDLE_SIZE - self.PADDING
        handle_y = self.height - self.HANDLE_SIZE - self.PADDING
        return QRectF(handle_x, handle_y, self.HANDLE_SIZE, self.HANDLE_SIZE)

    def boundingRect(self) -> QRectF:

        return QRectF(0, 0, self.width, self.height)

    def shape(self) -> QPainterPath:

        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter: QPainter, option, widget=None):

        rect = self.boundingRect().adjusted(self.PADDING, self.PADDING, -self.PADDING, -self.PADDING)

        pen_color = self.COLOR_BORDER
        pen_width = 2
        fill_color = QColor(self.COLOR)
        fill_color.setAlpha(self.COLOR_ALPHA)

        if self.isSelected():
            pen_color = self.COLOR_SELECTED
            pen_width = 3

            fill_color = QColor(self.COLOR_SELECTED)
            fill_color.setAlpha(self.COLOR_ALPHA + 20)

        pen = QPen(pen_color, pen_width)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill_color))
        painter.drawRect(rect)

        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(Qt.black)

        text_rect = rect.adjusted(5, 5, -5, -5)
        label_text = self.label if self.label else "Domain Space"
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, label_text)

        if self.isSelected():
            handle_rect = self.get_handle_rect()
            painter.setPen(QPen(Qt.black, 1))
            painter.setBrush(QBrush(Qt.white))
            painter.drawRect(handle_rect)

    def mousePressEvent(self, event):
        handle_rect = self.get_handle_rect()
        pos_in_item = event.pos()

        if self.isSelected() and handle_rect.contains(pos_in_item) and event.button() == Qt.LeftButton:
            self.resizing = True
            self.resize_start_pos = pos_in_item
            self.resize_start_rect = self.boundingRect()
            self.setCursor(Qt.SizeFDiagCursor)
            event.accept()
        else:

            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = event.pos() - self.resize_start_pos

            new_width = self.resize_start_rect.width() + delta.x()
            new_height = self.resize_start_rect.height() + delta.y()

            new_width = max(self.MIN_SIZE, new_width)
            new_height = max(self.MIN_SIZE, new_height)

            if new_width != self.width or new_height != self.height:
                self.prepareGeometryChange()
                self.width = new_width
                self.height = new_height
                self.setTransformOriginPoint(self.width / 2, self.height / 2)
                self.update_connection_points()
                self.update()

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing and event.button() == Qt.LeftButton:
            self.resizing = False
            self.setCursor(Qt.ArrowCursor)

            if self.boundingRect() != self.resize_start_rect:
                scene = self.scene()
                if scene:
                    old_size = (self.resize_start_rect.width(), self.resize_start_rect.height())
                    new_size = (self.width, self.height)
                    command = ResizeCommand(self, old_size, new_size)
                    push_command_to_scene(scene, command)

            self.resize_start_pos = None
            self.resize_start_rect = None
            event.accept()
        else:

            super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event):
        handle_rect = self.get_handle_rect()
        if self.isSelected() and handle_rect.contains(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and not self.resizing:

            return super().itemChange(change, value)
        elif change == QGraphicsItem.ItemPositionHasChanged:

            self.update_connection_points()

        return super(ConnectableItem, self).itemChange(change, value)

    def add_item(self, item: Union['PhysicalSpace', 'ConnectableItem']) -> bool:
        print(f"Error: DomainSpace cannot contain other items.")

        return False

    def remove_item(self, item: Union['PhysicalSpace', 'ConnectableItem']) -> bool:

        return False

    def dragEnterEvent(self, event):
        event.ignore()

    def dropEvent(self, event):
        event.ignore()


class ConnectionPoint(QGraphicsEllipseItem):
    default_size = 5
    hover_size = 7
    allowed_types = [
        S223.InletConnectionPoint,
        S223.OutletConnectionPoint,
        S223.BidirectionalConnectionPoint,
    ]

    def __init__(
            self,
            connectable: ConnectableItem,
            medium: rdflib.URIRef,
            type_uri: rdflib.URIRef,
            inst_uri: rdflib.URIRef = None,
            position: tuple = (0.5, 0.5),
    ):
        if type_uri not in self.allowed_types:
            raise ValueError(f'Connection type must be one of Inlet, Outlet, or Bidirectional. Not {type_uri}')

        self.connectable = connectable
        self.type_uri = type_uri
        self.inst_uri = inst_uri if inst_uri else BLDG[short_uuid()]
        self.properties: list[Property] = []

        self.label: str = ""
        self.comment: str = ""
        self.relative_x = position[0]
        self.relative_y = position[1]

        super().__init__(
            self.pos_x - self.default_size,
            self.pos_y - self.default_size,
            self.default_size * 2,
            self.default_size * 2,
            parent=connectable,
        )

        self.setPen(QPen(Qt.black, 1))
        self.setBrush(QBrush(Qt.gray))
        self.setZValue(4)
        self.medium = medium
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsScenePositionChanges)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.connected_to = None
        self.temp_connection = None

        connectable.add_connection_point(connection_point=self)

    def __str__(self):
        return f"{self.__class__.__name__}(medium={self.medium}, pos_x={self.pos_x}, pos_y={self.pos_y})"

    @property
    def type_uri(self):
        return self._type_uri

    @type_uri.setter
    def type_uri(self, type_uri: rdflib.URIRef):
        if type_uri not in self.allowed_types:
            raise ValueError(f"Invalid connection point type: {type_uri}")
        self._type_uri = type_uri

    @property
    def medium(self) -> rdflib.URIRef:
        return self._medium

    @medium.setter
    def medium(self, medium: rdflib.URIRef):

        if not (isinstance(medium, rdflib.URIRef) or medium is None):
            raise ValueError(f"Medium must be an URIRef not {type(medium)}")

        self._medium = medium
        self.update_appearance()

    def set_relative_position(self, x: float, y: float):
        self.relative_x = max(0.0, min(1.0, x))
        self.relative_y = max(0.0, min(1.0, y))
        self.update_position()
        if self.connected_to:
            self.connected_to.update_path()

    @property
    def pos_x(self):
        return self.connectable.width * self.relative_x

    @property
    def pos_y(self):
        return self.connectable.height * self.relative_y

    def update_position(self):
        self.setRect(
            self.pos_x - self.default_size,
            self.pos_y - self.default_size,
            self.default_size * 2,
            self.default_size * 2
        )

    def update_appearance(self):
        try:
            color = medium_library[self.medium].get('color')
        except KeyError:
            print(f'Did not find medium {self.medium} in medium_library')
            color = (200, 200, 200)
        medium_color = QColor(*color)
        self.setBrush(QBrush(medium_color))
        self.update()

    def setSize(self, radius: float):
        self.setRect(
            self.pos_x - radius,
            self.pos_y - radius,
            radius * 2,
            radius * 2,
        )
        self.update()

    def hoverEnterEvent(self, event):
        self.setSize(self.hover_size)
        self.update()

    def hoverLeaveEvent(self, event):
        self.setSize(self.default_size)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not event.modifiers() == Qt.ControlModifier:
            scene_pos = self.mapToScene(event.pos())
            self.start_connection(scene_pos)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.temp_connection:
            scene_pos = self.mapToScene(event.pos())
            self.update_temp_connection(scene_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.temp_connection:
            scene_pos = self.mapToScene(event.pos())
            target = self.find_connection_point_at(scene_pos)

            if target and target is not self:
                self.finalize_connection(target)
            else:
                self.cancel_connection()

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def add_property(self, property_item: Property):
        """Add a property to this connection point."""
        if property_item not in self.properties:
            self.properties.append(property_item)

            if property_item.parentItem() != self:
                property_item.setParentItem(self)
            if self.scene() and not property_item.scene():
                self.scene().addItem(property_item)

        return property_item

    def remove_property(self, property_item: Property):
        """Remove a property from this connection point."""
        if property_item in self.properties:
            self.properties.remove(property_item)

            return True
        return False

    def update_properties(self):
        """Update positions of associated properties."""
        for prop in self.properties:
            prop.update_position()

    def start_connection(self, scene_pos):
        if not self.scene() or self.connected_to is not None:
            return

        self.temp_connection = QGraphicsLineItem()
        self.temp_connection.setPen(QPen(Qt.black, 2, Qt.DashLine))

        start_pos = self.mapToScene(QPointF(self.pos_x, self.pos_y))
        self.temp_connection.setLine(start_pos.x(), start_pos.y(), scene_pos.x(), scene_pos.y())

        self.scene().addItem(self.temp_connection)

    def update_temp_connection(self, scene_pos):
        if self.temp_connection:
            start_pos = self.mapToScene(QPointF(self.pos_x, self.pos_y))
            self.temp_connection.setLine(start_pos.x(), start_pos.y(), scene_pos.x(), scene_pos.y())

    def find_connection_point_at(self, scene_pos):
        if not self.scene():
            return None

        items = self.scene().items(scene_pos)

        for item in items:
            if isinstance(item, ConnectionPoint) and item is not self:
                return item

        return None

    def _connection_is_possible(self, target_point):
        if target_point.medium != self.medium:
            return

        source_bidirectional = str(self.type_uri) == str(S223.BidirectionalConnectionPoint)
        target_bidirectional = str(target_point.type_uri) == str(S223.BidirectionalConnectionPoint)
        source_not_target = str(self.type_uri) != str(target_point.type_uri)

        if source_bidirectional and target_bidirectional:
            return True
        elif source_not_target and not (source_bidirectional or target_bidirectional):
            return True
        else:
            return False

    def finalize_connection(self, target_point):
        self.cancel_connection()

        if not self._connection_is_possible(target_point):
            return

        scene = self.scene()
        command = AddConnectionCommand(scene, self, target_point)
        push_command_to_scene(scene, command)

    def cancel_connection(self):
        if self.temp_connection:
            self.scene().removeItem(self.temp_connection)
            self.temp_connection = None

    def remove(self, scene):
        if self.connected_to is not None:
            command = RemoveConnectionCommand(scene, self.connected_to)
            push_command_to_scene(scene, command)

        scene.removeItem(self)


class Connection(QGraphicsPathItem):
    allowed_types = [S223.Connection, S223.Pipe, S223.Duct, S223.Conductor]

    def __init__(
            self,
            source: ConnectionPoint,
            target: ConnectionPoint,
            type_uri: rdflib.URIRef = S223.Pipe,
            inst_uri: str = None,
    ):
        super().__init__()

        if type_uri not in self.allowed_types:
            raise ValueError(f"Connection type must be one of s223.Pipe, s223.Duct, s223.Conductor Not {type_uri}")

        self.type_uri = type_uri
        self.inst_uri = inst_uri if inst_uri else BLDG[short_uuid()]
        self.label: str = ""
        self.comment: str = ""
        self.source = source
        self.target = target

        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(1)
        self.setAcceptHoverEvents(True)

        self.update_path()

        self.source.connected_to = self
        self.target.connected_to = self

        self.source.parentItem().setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.target.parentItem().setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    @property
    def medium(self):
        return self.source.medium

    @medium.setter
    def medium(self, new_medium):
        self.source.medium = new_medium
        self.target.medium = new_medium
        self.update_path()

    def update_path(self, width: Optional[int] = None):
        try:
            color = medium_library[self.source.medium].get('color', None)
        except KeyError:
            print(f'Unknown medium {self.source.medium} using default color')
            color = (200, 200, 200)
        if width is None:
            width = connection_library[self.type_uri].get('width')

        self.setPen(QPen(QColor(*color), width))

        source_pos = self.source.mapToScene(QPointF(self.source.pos_x, self.source.pos_y))
        target_pos = self.target.mapToScene(QPointF(self.target.pos_x, self.target.pos_y))

        path = QPainterPath(source_pos)
        path.lineTo(target_pos)

        self._draw_arrow(path, source_pos, target_pos)
        self.setPath(path)

    def hoverEnterEvent(self, event):
        width = connection_library[self.type_uri].get('width') + 2
        self.update_path(width)

    def hoverLeaveEvent(self, event):
        self.update_path()

    def _draw_arrow(self, path, source_pos, target_pos):
        source_is_outlet = self.source.type_uri == S223.OutletConnectionPoint
        source_is_inlet = self.source.type_uri == S223.InletConnectionPoint
        source_is_bidirectional = self.source.type_uri == S223.BidirectionalConnectionPoint
        target_is_outlet = self.target.type_uri == S223.OutletConnectionPoint
        target_is_inlet = self.target.type_uri == S223.InletConnectionPoint
        target_is_bidirectional = self.target.type_uri == S223.BidirectionalConnectionPoint

        if source_is_outlet and target_is_inlet:
            draw_arrow_towards_target = True
        elif source_is_inlet and target_is_outlet:
            draw_arrow_towards_target = False
        elif source_is_bidirectional and target_is_bidirectional:
            return
        else:
            raise ValueError(
                f"Invalid connection between {self.source.type_uri} and {self.target.type_uri}")

        arrow_size = 10
        arrow_angle = 45

        dx = target_pos.x() - source_pos.x()
        dy = target_pos.y() - source_pos.y()
        angle = math.atan2(dy, dx)

        if not draw_arrow_towards_target:
            angle += math.pi

        midpoint_x = (source_pos.x() + target_pos.x()) / 2
        midpoint_y = (source_pos.y() + target_pos.y()) / 2
        midpoint = QPointF(midpoint_x, midpoint_y)

        arrow_point1 = QPointF(
            midpoint.x() + arrow_size * math.cos(angle + math.radians(180 - arrow_angle / 2)),
            midpoint.y() + arrow_size * math.sin(angle + math.radians(180 - arrow_angle / 2))
        )

        arrow_point2 = QPointF(
            midpoint.x() + arrow_size * math.cos(angle + math.radians(180 + arrow_angle / 2)),
            midpoint.y() + arrow_size * math.sin(angle + math.radians(180 + arrow_angle / 2))
        )

        arrow_tip = QPointF(
            midpoint.x() + (arrow_size / 2) * math.cos(angle),
            midpoint.y() + (arrow_size / 2) * math.sin(angle)
        )

        path.moveTo(arrow_point1)
        path.lineTo(arrow_tip)
        path.lineTo(arrow_point2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSceneHasChanged and self.scene():
            for item in [self.source.parentItem(), self.target.parentItem()]:
                if item:
                    item.itemChange = self._monitor_parent_changes(item.itemChange)
        return super().itemChange(change, value)

    def _monitor_parent_changes(self, original_itemChange):
        def wrapped_itemChange(change, value):
            result = original_itemChange(change, value)
            if change == QGraphicsItem.ItemPositionHasChanged:
                self.update_path()
            return result

        return wrapped_itemChange

    def remove(self, scene):
        self.source.connected_to = None
        self.target.connected_to = None
        scene.removeItem(self)


class SystemItem(QGraphicsItem):
    PADDING = 20
    COLOR = QColor(100, 100, 100)
    COLOR_SELECTED = QColor(150, 150, 150)

    def __init__(self, members: List[ConnectableItem], inst_uri: rdflib.URIRef = None):

        if not isinstance(members, list):
            raise ValueError("Members must be a list")

        for member in members:
            if not isinstance(member, ConnectableItem):
                raise ValueError("Members must be ConnectableItem instances")
            if isinstance(member, (DomainSpace, PhysicalSpace)):
                raise ValueError("System members cannot be DomainSpace or PhysicalSpace")

        super().__init__()

        self.inst_uri = inst_uri if inst_uri else BLDG[short_uuid()]
        self.label: str = to_label(self.inst_uri)
        self.comment: str = str()
        self.members: set[ConnectableItem] = set()
        self.role: rdflib.URIRef | None = None

        self._bounding_rect = QRectF()
        self._setup()

        if members:
            for member in members:
                self.add_member(member)

    def _setup(self):
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setZValue(0)
        self.setAcceptHoverEvents(True)
        self.update_bounding_rect()

    def add_member(self, item: ConnectableItem) -> bool:
        if isinstance(item, ConnectableItem) and \
                not isinstance(item, (DomainSpace, PhysicalSpace)) and \
                item not in self.members:
            self.members.add(item)
            self.update_bounding_rect()
            return True
        return False

    def remove_member(self, item: ConnectableItem) -> bool:
        if item in self.members:
            self.members.remove(item)
            self.update_bounding_rect()
            if not self.members and self.scene():
                pass
            return True
        return False

    def update_bounding_rect(self):
        """Calculates the bounding rectangle based on the scene coordinates of members."""
        self.prepareGeometryChange()

        if not self.members or not self.scene():
            self._bounding_rect = QRectF()
            self.update()
            return

        total_rect_in_scene = QRectF()
        first = True
        for member in self.members:
            if not member.scene():
                continue

            member_rect = member.boundingRect()
            member_rect_in_scene = member.mapRectToScene(member_rect)

            if first:
                total_rect_in_scene = member_rect_in_scene
                first = False
            else:
                total_rect_in_scene = total_rect_in_scene.united(member_rect_in_scene)

        if first:
            self._bounding_rect = QRectF()
        else:
            rect_in_item_coords = self.mapRectFromScene(total_rect_in_scene)
            self._bounding_rect = rect_in_item_coords.adjusted(-self.PADDING, -self.PADDING, self.PADDING, self.PADDING)

        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        if not self.members or self._bounding_rect.isEmpty():
            return

        pen = QPen(self.COLOR, 1, Qt.DashLine)

        if option.state & QStyle.State_Selected:
            pen.setColor(self.COLOR_SELECTED)
            pen.setStyle(Qt.SolidLine)
            pen.setWidth(2)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self._bounding_rect)

        label_rect = QRectF(
            self._bounding_rect.left(),
            self._bounding_rect.top() - 20,
            self._bounding_rect.width(),
            20,
        )

        font = QFont()
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, self.label)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemChildAddedChange or \
                change == QGraphicsItem.ItemChildRemovedChange or \
                change == QGraphicsItem.ItemSceneHasChanged:
            QTimer.singleShot(0, self.update_bounding_rect)

        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        pen_width = 2
        adjusted_rect = self._bounding_rect.adjusted(-pen_width / 2, -pen_width / 2, pen_width / 2, pen_width / 2)
        label_height = 20
        adjusted_rect.setTop(adjusted_rect.top() - label_height)
        return adjusted_rect

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self._bounding_rect)
        return path

    def remove(self, scene):
        if self.scene():
            scene.removeItem(self)


class Selection(list):
    @property
    def last(self):
        return self[0] if len(self) > 0 else None

    @property
    def isEmpty(self) -> bool:
        return len(self) == 0

    @property
    def getConnectable(self) -> 'Selection':
        return Selection(item for item in self if isinstance(item, ConnectableItem))

    @property
    def getConnection(self) -> 'Selection':
        return Selection(item for item in self if isinstance(item, Connection))

    @property
    def getConnectionPoint(self) -> 'Selection':
        return Selection(item for item in self if isinstance(item, ConnectionPoint))

    @property
    def getSystem(self) -> 'Selection':
        return Selection(item for item in self if isinstance(item, SystemItem))

    @property
    def getPhysicalSpace(self) -> 'Selection':
        return Selection(item for item in self if isinstance(item, PhysicalSpace))

    @property
    def getDomainSpace(self) -> 'Selection':
        return Selection(item for item in self if isinstance(item, DomainSpace))

    @property
    def getProperty(self) -> 'Selection':
        return Selection(item for item in self if isinstance(item, Property))

    @property
    def onlyConnectable(self) -> bool:
        return all(isinstance(item, ConnectableItem) for item in self)

    @property
    def onlyConnection(self) -> bool:
        return all(isinstance(item, Connection) for item in self)

    @property
    def onlyConnectionPoint(self) -> bool:
        return all(isinstance(item, ConnectionPoint) for item in self)

    @property
    def onlyPhysicalSpace(self) -> bool:
        return all(isinstance(item, PhysicalSpace) for item in self)

    @property
    def onlyDomainSpace(self) -> bool:
        return all(isinstance(item, DomainSpace) for item in self)

    @property
    def onlyProperty(self) -> bool:
        return all(isinstance(item, Property) for item in self)


class SceneBrowser(QTreeWidget):
    """
    A QTreeWidget that displays a hierarchical view of all items in the QGraphicsScene.
    It synchronizes selection with the main canvas.
    """

    def __init__(self, scene: QGraphicsScene, parent: QWidget = None):
        super().__init__(parent)
        self.scene = scene
        self.setHeaderLabel("Scene Hierarchy")
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.AscendingOrder)

        # A flag to prevent feedback loops between scene and tree selection signals.
        self._is_updating_selection = False

        # A dictionary to map each QGraphicsItem to its corresponding QTreeWidgetItem
        # for quick lookups when syncing scene selection to the tree.
        self.graphics_item_map: Dict[QGraphicsItem, QTreeWidgetItem] = {}

        # Connect the tree's itemClicked signal to a handler that selects the item on the canvas.
        self.itemClicked.connect(self.on_tree_item_clicked)

        # Perform the initial population of the tree.
        self.repopulate_tree()

    def repopulate_tree(self):
        """
        Clears and repopulates the entire tree based on the current state of the scene.
        This method should be called whenever items are added, removed, or reparented.
        """
        self.blockSignals(True)  # Block signals to avoid triggering events during update
        self.clear()
        self.graphics_item_map.clear()

        # Identify top-level items (those not parented to another QGraphicsItem).
        # These will be the root nodes in our tree.
        top_level_items = [item for item in self.scene.items() if not item.parentItem()]

        for item in top_level_items:
            # We only display our custom types, ignoring helper items like grid lines.
            if isinstance(item, (ConnectableItem, Connection, PhysicalSpace, SystemItem, Property)):
                self._add_item_and_children(item, parent_tree_item=None)

        self.expandAll()
        self.blockSignals(False)

        # After repopulating, ensure the tree selection reflects the current scene selection.
        self.on_scene_selection_changed()

    def _add_item_and_children(self, graphics_item: QGraphicsItem, parent_tree_item: Optional[QTreeWidgetItem]):
        """
        Recursively adds a graphics item and its children (based on QGraphicsItem parenting)
        to the tree, displaying its rdfs:type.
        """
        # --- 1. Determine the primary display label ---
        # Use the user-defined rdfs:label if available.
        if hasattr(graphics_item, 'label') and graphics_item.label:
            primary_label = graphics_item.label
        # Fallback to the instance URI if no label is set.
        elif hasattr(graphics_item, 'inst_uri'):
            primary_label = to_label(graphics_item.inst_uri)
        # As a last resort, use the Python class name.
        else:
            primary_label = type(graphics_item).__name__

        # --- 2. Determine the rdfs:type label ---
        type_uri = None
        # Handle different ways the type URI is stored across classes.
        if hasattr(graphics_item, 'type_uri'):  # For ConnectableItem, Connection, ConnectionPoint
            type_uri = graphics_item.type_uri
        elif hasattr(graphics_item, 'property_type'):  # For Property
            type_uri = graphics_item.property_type
        elif isinstance(graphics_item, PhysicalSpace):  # Implicit type
            type_uri = S223.PhysicalSpace
        elif isinstance(graphics_item, SystemItem):  # Implicit type
            type_uri = S223.System

        # Convert the URI to a human-readable label.
        if type_uri:
            type_label = to_label(type_uri)
        else:
            # Fallback for unexpected item types.
            type_label = type(graphics_item).__name__

        # --- 3. Combine into the final, descriptive label ---
        final_label = f"{type_label} [{primary_label}]"

        # Create the new tree widget item.
        tree_item = QTreeWidgetItem([final_label])
        # Store a reference to the actual graphics item in the tree item's data.
        tree_item.setData(0, Qt.UserRole, graphics_item)

        # Add the new item to its parent in the tree or as a top-level item.
        if parent_tree_item:
            parent_tree_item.addChild(tree_item)
        else:
            self.addTopLevelItem(tree_item)

        # Store the mapping from the graphics item to the new tree item.
        self.graphics_item_map[graphics_item] = tree_item

        # Recursively process all children of the current graphics item.
        for child_item in graphics_item.childItems():
            self._add_item_and_children(child_item, tree_item)

    def on_tree_item_clicked(self, tree_item: QTreeWidgetItem, column: int):
        """
        Handles clicks on items in the tree. It selects the corresponding item on the canvas.
        """
        if self._is_updating_selection:
            return  # Avoid feedback loop

        graphics_item = tree_item.data(0, Qt.UserRole)
        if graphics_item and isinstance(graphics_item, QGraphicsItem) and graphics_item.scene():
            self._is_updating_selection = True

            # Clear any existing selection and select the new item.
            self.scene.clearSelection()
            graphics_item.setSelected(True)

            # Ensure the canvas view is centered on the selected item.
            if self.scene.views():
                self.scene.views()[0].centerOn(graphics_item)

            self._is_updating_selection = False

    def on_scene_selection_changed(self):
        """
        Handles selection changes on the canvas. It updates the selection in the tree to match.
        """
        if self._is_updating_selection:
            return  # Avoid feedback loop

        self._is_updating_selection = True
        self.clearSelection()
        selected_graphics_items = self.scene.selectedItems()

        if not selected_graphics_items:
            self._is_updating_selection = False
            return

        # Iterate through all items selected on the canvas.
        for item in selected_graphics_items:
            # Find the corresponding tree item using our map.
            tree_item = self.graphics_item_map.get(item)
            if tree_item:
                # Select the tree item.
                tree_item.setSelected(True)
                # Scroll the tree view to make the first selected item visible.
                self.scrollToItem(tree_item, QAbstractItemView.PositionAtCenter)

        self._is_updating_selection = False


class EntityBrowser(QTreeWidget):

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setHeaderLabel("Entities")
        self.setDragEnabled(True)
        self._populate_entity_tree()
        self.expandAll()

    def _populate_entity_tree(self):
        def add_items_recursively(parent_item, items_dict):
            for item_name, item_value in items_dict.items():
                tree_item = QTreeWidgetItem(parent_item)
                tree_item.setText(0, item_name)

                if not isinstance(item_value, dict):
                    tree_item.setData(0, Qt.UserRole, item_value)
                else:

                    add_items_recursively(tree_item, item_value)

        for category_name, category_dict in connectable_library.items():
            category_item = QTreeWidgetItem(self)
            category_item.setText(0, category_name)

            if isinstance(category_dict, dict):
                add_items_recursively(category_item, category_dict)
            else:

                category_item.setData(0, Qt.UserRole, category_dict)

    def mouseMoveEvent(self, event):
        if event.buttons() != Qt.LeftButton:
            return

        item = self.currentItem()
        if not item:
            return

        entity = item.data(0, Qt.UserRole)
        if not entity:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(entity))

        uri_bytes = QByteArray(str(entity).encode())
        mime_data.setData("application/type_uri", uri_bytes)

        drag.setMimeData(mime_data)

        try:
            if entity == S223.PhysicalSpace or entity == S223.DomainSpace:

                pixmap = QPixmap(100, 80)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                painter.setPen(QPen(Qt.black, 2))
                painter.setBrush(QBrush(QColor(240, 240, 240, 100)))
                painter.drawRect(10, 10, 80, 60)
                painter.drawText(QRect(10, 10, 80, 60), Qt.AlignCenter, "PhysicalSpace")
                painter.end()
                drag.setPixmap(pixmap)
                drag.setHotSpot(QPoint(50, 40))

            else:

                svg_data = svg_library[entity].encode()
                renderer = QSvgRenderer(QByteArray(svg_data))
                pixmap = QPixmap(renderer.defaultSize())
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                drag.setPixmap(pixmap)
                drag.setHotSpot(QPoint(25, 25))

            drag.exec_(Qt.CopyAction)
        except KeyError:
            popup(text="No SVG data available for this entity.", window_title="Backend Error")


class DiagramScene(QGraphicsScene):
    """Custom scene to draw location indicator lines in the foreground."""

    def __init__(self, parent=None):  # Add __init__
        super().__init__(parent)
        self.show_location_lines = True  # Add state variable, default to True

    def drawForeground(self, painter: QPainter, rect):
        # Call the base class method first (optional, but good practice)
        super().drawForeground(painter, rect)

        if not self.show_location_lines:
            return

        # --- Draw Physical Location Lines ---
        # Define the pen style for the lines
        line_pen = QPen(QColor(120, 120, 120), 1, Qt.DashLine)  # Slightly darker gray dash
        painter.setPen(line_pen)
        painter.setBrush(Qt.NoBrush)  # Ensure no fill

        items_to_check = self.items()  # Get all items in the scene once

        # Optional: Pre-build a lookup for faster physical space finding
        physical_spaces_by_uri: Dict[rdflib.URIRef, PhysicalSpace] = {
            item.inst_uri: item
            for item in items_to_check
            if isinstance(item, PhysicalSpace) and hasattr(item, 'inst_uri')
        }

        # Iterate through items to find equipment with locations
        for item in items_to_check:
            # Check if it's an Equipment item (Connectable, not Domain)
            # and has a physical location set
            if isinstance(item, ConnectableItem) and \
                    not isinstance(item, DomainSpace) and \
                    hasattr(item, 'physical_location_uri') and \
                    item.physical_location_uri:

                # Find the target PhysicalSpace using the pre-built lookup or by iterating again
                target_space = physical_spaces_by_uri.get(item.physical_location_uri)
                # Fallback search if lookup wasn't built or failed (less efficient)
                # if not target_space:
                #     for potential_target in items_to_check:
                #         if isinstance(potential_target, PhysicalSpace) and \
                #            hasattr(potential_target, 'inst_uri') and \
                #            potential_target.inst_uri == item.physical_location_uri:
                #             target_space = potential_target
                #             break

                # If the target space exists in the scene
                if target_space:
                    try:
                        # Calculate center of the equipment item in SCENE coordinates
                        # Use item's width/height for center calculation relative to its origin (0,0)
                        source_center_local = QPointF(item.width / 2, item.height / 2)
                        source_pos_scene = item.mapToScene(source_center_local)

                        # Calculate center of the physical space item in SCENE coordinates
                        target_rect = target_space.boundingRect()
                        target_center_local = target_rect.center()
                        target_pos_scene = target_space.mapToScene(target_center_local)

                        # Draw the line directly using scene coordinates
                        painter.drawLine(source_pos_scene, target_pos_scene)
                    except Exception as e:
                        # Catch potential errors during coordinate mapping if items are invalid
                        # print(f"Debug: Error drawing location line for {item.inst_uri}: {e}")
                        pass  # Avoid crashing if something goes wrong

    def toggle_location_lines(self):
        """Toggles the visibility of physical location lines and updates the scene."""
        self.show_location_lines = not self.show_location_lines
        self.update()  # Trigger a repaint of the scene foreground/background


class Canvas(QGraphicsView):

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        selected = Selection(self.scene.selectedItems())

        if selected:
            delete_action = menu.addAction("Delete")
            delete_action.setShortcut("Delete")
            delete_action.triggered.connect(self._delete_selected_items)

            copy_action = menu.addAction("Copy")
            copy_action.setShortcut("Ctrl+C")
            copy_action.triggered.connect(self._copy_selected_items)

        paste_action = menu.addAction("Paste")
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(lambda: self._paste_items())

        select_all_action = menu.addAction("Select All")
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self._select_all_items)

        equipment = Selection([
            item for item in selected.getConnectable
            if not isinstance(item, (DomainSpace, PhysicalSpace))
        ])
        if equipment:
            menu.addSeparator()
            rotate_action = menu.addAction("Rotate 90°")
            rotate_action.setShortcut("R")
            rotate_action.triggered.connect(self._rotate_selected_items_90)
            menu.addSeparator()

        equipment_for_system = Selection([
            item for item in selected.getConnectable
            if not isinstance(item, (DomainSpace, PhysicalSpace))
        ])
        if len(equipment_for_system) >= 1:
            create_sys_action = menu.addAction("Create System from Selection")
            create_sys_action.setShortcut("Ctrl+G")
            create_sys_action.triggered.connect(self._create_system_from_selection)
            menu.addSeparator()

        physical_spaces = selected.getPhysicalSpace
        domain_spaces = selected.getDomainSpace

        equipment = Selection([
            item for item in selected.getConnectable
            if not isinstance(item, (DomainSpace, PhysicalSpace))
        ])

        if len(physical_spaces) == 1 and len(selected) == 1:
            manage_action = menu.addAction("Manage Relationships...")
            manage_action.triggered.connect(lambda: self._show_relationship_dialog(physical_spaces[0]))

        elif len(equipment) == 1 and len(selected) == 1:
            manage_action = menu.addAction("Manage Relationships...")
            manage_action.triggered.connect(lambda: self._show_relationship_dialog(equipment[0]))

        elif len(physical_spaces) >= 2 and len(selected) == len(physical_spaces):
            container = physical_spaces[0]
            contained = physical_spaces[1:]
            contain_action = menu.addAction(f"Set '{container.label}' to contain {len(contained)} other space(s)")
            contain_action.triggered.connect(lambda: self._set_item_contains(container, contained))

        elif len(equipment) >= 2 and len(selected) == len(equipment):
            container = equipment[0]
            contained = equipment[1:]
            contain_action = menu.addAction(f"Set '{container.label}' to contain {len(contained)} other equipment")
            contain_action.triggered.connect(lambda: self._set_item_contains(container, contained))

        elif len(physical_spaces) == 1 and len(domain_spaces) >= 1 and len(selected) == (1 + len(domain_spaces)):
            container = physical_spaces[0]
            enclose_action = menu.addAction(f"Set '{container.label}' to enclose {len(domain_spaces)} domain space(s)")
            enclose_action.triggered.connect(lambda: self._set_physical_space_encloses(container, domain_spaces))

        if menu.actions():

            while menu.actions() and menu.actions()[-1].isSeparator():
                menu.removeAction(menu.actions()[-1])
            if menu.actions():
                menu.exec_(event.globalPos())
            else:
                super().contextMenuEvent(event)
        else:
            super().contextMenuEvent(event)

    def _set_item_contains(self, container, contained_items):
        """Generic function to set 'contains' relationship using commands."""

        class SetContainsCommand(CompoundCommand):
            def __init__(self, container, contained_items):
                super().__init__(f"Set Contains for {container.label}")
                self.container = container
                self.contained_items = contained_items
                for item in contained_items:
                    self.add_command(AddContainedItemCommand(container, item))

        command = SetContainsCommand(container, contained_items)
        if push_command_to_scene(self.scene, command):
            find_status_bar(self).showMessage(
                f"Item '{container.label}' now contains {len(contained_items)} other item(s)")
        else:
            find_status_bar(self).showMessage(f"Failed to set containment for '{container.label}'")

    def _set_physical_space_encloses(self, container, domain_spaces):
        """Sets 'encloses' relationship using commands."""

        class SetEnclosesCommand(CompoundCommand):
            def __init__(self, container, domain_spaces):
                super().__init__(f"Set Encloses for {container.label}")
                self.container = container
                self.domain_spaces = domain_spaces
                for space in domain_spaces:
                    self.add_command(AddEnclosedSpaceCommand(container, space))

        command = SetEnclosesCommand(container, domain_spaces)
        if push_command_to_scene(self.scene, command):
            find_status_bar(self).showMessage(
                f"PhysicalSpace '{container.label}' now encloses {len(domain_spaces)} domain space(s)")
        else:
            find_status_bar(self).showMessage(f"Failed to set enclosure for '{container.label}'")

    def _show_relationship_dialog(self, item: Union[PhysicalSpace, ConnectableItem]):
        """Shows the relationship dialog for a PhysicalSpace or ConnectableItem (Equipment)."""
        dialog = RelationshipDialog(item, self.scene)
        if dialog.exec_() == QDialog.Accepted:
            commands_to_push = dialog.get_commands()
            if commands_to_push:
                compound_command = CompoundCommand("Manage Relationships")
                for cmd in commands_to_push:
                    compound_command.add_command(cmd)
                push_command_to_scene(self.scene, compound_command)

            self._update_property_panel()

    def dropEvent(self, event):

        if event.mimeData().hasFormat("application/type_uri"):
            type_uri_str = event.mimeData().data("application/type_uri").data().decode()
            type_uri = rdflib.URIRef(type_uri_str)

            pos = self.mapToScene(event.pos())

            if type_uri == S223.PhysicalSpace:
                item = PhysicalSpace()
            elif type_uri == S223.DomainSpace:
                item = DomainSpace()
            else:
                item = ConnectableItem(type_uri=type_uri)
                item.load_default_connection_points()

            command = AddItemCommand(self.scene, item)
            self.command_history.push(command)

            item.setPos(pos.x(), pos.y())
            self.scene.clearSelection()
            item.setSelected(True)

            event.acceptProposedAction()

    def _set_physical_space_contains(self, container, contained_spaces):
        class SetContainsCommand(Command):
            def __init__(self, container, contained_spaces):
                self.container = container
                self.contained_spaces = contained_spaces
                self.previous_parents = {space: space.parentItem() for space in contained_spaces}

            def _execute(self):
                for space in self.contained_spaces:
                    self.container.add_physical_space(space)

            def _undo(self):
                for space, previous_parent in self.previous_parents.items():
                    if space in self.container.contained_physical_spaces:
                        self.container.remove_physical_space(space)
                    if previous_parent:
                        space.setParentItem(previous_parent)

        command = SetContainsCommand(container, contained_spaces)
        push_command_to_scene(self.scene, command)
        find_status_bar(self).showMessage(
            f"PhysicalSpace '{container.label}' now contains {len(contained_spaces)} other space(s)")

    def __init__(self, property_panel):
        super().__init__()

        self.scene = DiagramScene(self)
        self.setScene(self.scene)

        self.command_history = CommandHistory()
        self.scene.command_history = self.command_history

        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setAcceptDrops(True)

        self.property_panel = property_panel
        self.scene.selectionChanged.connect(self._handle_selection_changed)

        self.update_timer = QTimer(self)
        self.update_timer.setInterval(100)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._update_property_panel)
        self.update_timer.start()

        self._draw_grid()

        self.clipboard = {
            'items': [],
            'connections': []
        }

    def toggle_grid(self, enable: bool):
        CanvasProperties.enable_grid = enable

        grid_items = []
        for item in self.scene.items():
            if (isinstance(item, QGraphicsLineItem) or
                    (isinstance(item, QGraphicsRectItem) and
                     item.pen().color() == CanvasProperties.frame_color)):
                grid_items.append(item)

        for item in grid_items:
            self.scene.removeItem(item)

        self._draw_grid()
        self.update()

    def _draw_grid(self):
        width, height, grid_size = CanvasProperties.width, CanvasProperties.height, CanvasProperties.grid_size

        if CanvasProperties.enable_grid:
            grid_pen = QPen(QColor(230, 230, 230))
            grid_pen.setStyle(Qt.DotLine)

            for y in range(0, height, grid_size):
                self.scene.addLine(0, y, width, y, grid_pen)

            for x in range(0, width, grid_size):
                self.scene.addLine(x, 0, x, height, grid_pen)

        frame_pen = QPen(CanvasProperties.frame_color, CanvasProperties.frame_width)
        self.scene.addRect(0, 0, width, height, frame_pen)
        self.scene.setSceneRect(0, 0, width, height)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z and event.modifiers() == Qt.ControlModifier:
            success = self.command_history.undo()
            if success:
                self.update()
                find_status_bar(self).showMessage("Undo")

        elif event.key() == Qt.Key_Y and event.modifiers() == Qt.ControlModifier:
            success = self.command_history.redo()
            if success:
                self.update()
                find_status_bar(self).showMessage("Redo")
        elif event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self._select_all_items()
        elif event.key() == Qt.Key_R and event.modifiers() == Qt.NoModifier:
            self._rotate_selected_items_90()
        elif event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            self._copy_selected_items()
        elif event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            self._paste_items()
        elif event.key() == Qt.Key_Delete:
            self._delete_selected_items()
        elif event.key() == Qt.Key_P and event.modifiers() == Qt.ControlModifier:
            print([item for item in self.scene.items() if
                   isinstance(item, (ConnectableItem, Connection, ConnectionPoint))])
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/type_uri"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/entity-svg"):
            event.acceptProposedAction()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        for item in self.scene.items():
            if isinstance(item, Connection):
                item.update_path()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            zoom_factor = 1.1
            if event.angleDelta().y() > 0:
                self.scale(zoom_factor, zoom_factor)
            else:
                self.scale(1.0 / zoom_factor, 1.0 / zoom_factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def _handle_selection_changed(self):
        self.update_timer.start()

    def _update_property_panel(self):
        self.property_panel.update_properties(Selection(self.scene.selectedItems()))

    def _find_connection_point_index(self, cp):
        for i, item_data in enumerate(self.clipboard['items']):
            if hasattr(cp, 'connectable') and cp.connectable == item_data.get('original'):
                for j, cp_data in enumerate(item_data['connection_points']):
                    if cp_data.get('original') == cp:
                        return (i, j)
        return None

    def _create_system_from_selection(self):
        selection = Selection(self.scene.selectedItems())
        selected_connectable = selection.getConnectable

        try:
            system = SystemItem(members=selected_connectable)
        except ValueError as e:
            popup(text=str(e), window_title="Error")
            return

        command = CreateSystemCommand(self.scene, system)
        push_command_to_scene(self.scene, command)

    def _delete_selected_items(self):

        selected_items = self.scene.selectedItems()

        if not selected_items:
            return

        command = RemoveItemCommand(self.scene, selected_items)
        self.command_history.push(command)
        self.update()

    def _copy_selected_items(self):
        selected_items = self.scene.selectedItems()
        self.clipboard = {'items': [], 'connections': []}

        original_item_to_clipboard_index = {}

        original_cp_to_clipboard_index = {}

        original_prop_to_clipboard_info = {}

        clipboard_item_index = 0

        for item in selected_items:
            item_data = None
            is_copyable_item = False

            if isinstance(item, ConnectableItem):

                current_item_clipboard_idx = clipboard_item_index

                item_data = {
                    'type': 'ConnectableItem', 'type_uri': item.type_uri,
                    'pos_x': item.x(), 'pos_y': item.y(), 'rotation': item.rotation(),
                    'label': item.label, 'comment': item.comment, 'role': item.role,
                    'connection_points': [], 'properties': [],
                    'original': item
                }
                if isinstance(item, DomainSpace):
                    item_data['width'] = item.width
                    item_data['height'] = item.height

                for j, cp in enumerate(item.connection_points):
                    cp_data = {
                        'medium': cp.medium, 'type_uri': cp.type_uri,
                        'relative_x': cp.relative_x, 'relative_y': cp.relative_y,
                        'label': cp.label, 'comment': cp.comment, 'original': cp,
                        'properties': []
                    }

                    original_cp_to_clipboard_index[cp] = (current_item_clipboard_idx, j)

                    for p_idx, prop in enumerate(cp.properties):
                        prop_data_copy = self._copy_property_data(prop)
                        cp_data['properties'].append(prop_data_copy)
                        original_prop_to_clipboard_info[prop] = {
                            'parent_type': 'cp',
                            'parent_idx': (current_item_clipboard_idx, j),
                            'prop_idx': p_idx
                        }
                    item_data['connection_points'].append(cp_data)

                for p_idx, prop in enumerate(item.properties):
                    prop_data_copy = self._copy_property_data(prop)
                    item_data['properties'].append(prop_data_copy)
                    original_prop_to_clipboard_info[prop] = {
                        'parent_type': 'connectable',
                        'parent_idx': current_item_clipboard_idx,
                        'prop_idx': p_idx
                    }

                is_copyable_item = True

            elif isinstance(item, PhysicalSpace):

                current_item_clipboard_idx = clipboard_item_index

                item_data = {
                    'type': 'PhysicalSpace',
                    'pos_x': item.x(), 'pos_y': item.y(),
                    'width': item.width, 'height': item.height,
                    'label': item.label, 'comment': item.comment, 'role': item.role,
                    'original': item
                }
                is_copyable_item = True

            if is_copyable_item and item_data:
                original_item_to_clipboard_index[item] = clipboard_item_index
                self.clipboard['items'].append(item_data)
                clipboard_item_index += 1

        for item in selected_items:
            if isinstance(item, Connection):
                source_cp = item.source
                target_cp = item.target

                if source_cp in original_cp_to_clipboard_index and target_cp in original_cp_to_clipboard_index:
                    connection_data = {
                        'type': 'Connection',

                        'source_index': original_cp_to_clipboard_index[source_cp],
                        'target_index': original_cp_to_clipboard_index[target_cp],
                        'type_uri': item.type_uri,
                        'label': item.label, 'comment': item.comment

                    }
                    self.clipboard['connections'].append(connection_data)

        if self.clipboard['items']:
            copied_items_count = len(self.clipboard['items'])
            copied_connections_count = len(self.clipboard['connections'])
            msg = f"Copied {copied_items_count} item(s)"
            if copied_connections_count > 0:
                msg += f" and {copied_connections_count} connection(s)"
            msg += "..."
            find_status_bar(self).showMessage(msg)
        else:
            find_status_bar(self).showMessage("Nothing copyable selected")

    def _copy_property_data(self, prop: Property) -> dict:
        return {
            'property_type': prop.property_type, 'identifier': prop.identifier,
            'position_x': prop.x(),
            'position_y': prop.y(),
            'label': prop.label, 'comment': prop.comment, 'aspect': prop.aspect,
            'external_reference': prop.external_reference,
            'internal_reference': prop.internal_reference, 'value': prop.value,
            'medium': prop.medium,
            'unit': prop.unit,
            'quantity_kind': prop.quantity_kind,
            'original': prop
        }

    def _paste_items(self):
        if not self.clipboard['items']:
            find_status_bar(self).showMessage("Clipboard is empty")
            return

        self.scene.clearSelection()
        paste_offset = CanvasProperties.grid_size
        compound_command = CompoundCommand("Paste Items")
        new_items_map = {}
        new_cps_map = {}

        for i, item_data in enumerate(self.clipboard['items']):
            original_item = item_data['original']
            new_item = None
            item_type = item_data.get('type')

            if item_type == 'ConnectableItem':
                if isinstance(original_item, DomainSpace):
                    new_item = DomainSpace(type_uri=item_data['type_uri'])
                    new_item.width = item_data.get('width', 150)
                    new_item.height = item_data.get('height', 100)
                else:

                    try:
                        new_item = ConnectableItem(type_uri=item_data['type_uri'])
                    except KeyError:
                        print(f"Paste Warning: SVG not found for {item_data['type_uri']}. Skipping item.")
                        continue

                new_item.setPos(item_data['pos_x'] + paste_offset, item_data['pos_y'] + paste_offset)
                new_item.setRotation(item_data['rotation'])

            elif item_type == 'PhysicalSpace':
                new_item = PhysicalSpace()
                new_item.width = item_data.get('width', 200)
                new_item.height = item_data.get('height', 150)
                new_item.setPos(item_data['pos_x'] + paste_offset, item_data['pos_y'] + paste_offset)

            else:
                print(f"Paste Warning: Unknown item type '{item_type}' in clipboard.")
                continue

            new_item.label = item_data.get('label', '')
            new_item.comment = item_data.get('comment', '')
            new_item.role = item_data.get('role', None)

            add_item_command = AddItemCommand(self.scene, new_item)

            if add_item_command.execute():
                compound_command.add_command(add_item_command)
                new_items_map[original_item] = new_item
            else:
                print(f"Error adding pasted item {new_item.label} to scene.")

        for i, item_data in enumerate(self.clipboard['items']):
            original_item = item_data['original']
            new_item = new_items_map.get(original_item)
            if not new_item or not isinstance(new_item, ConnectableItem):
                continue

            default_cps_map = {}
            if hasattr(new_item, 'connection_points'):
                for cp in new_item.connection_points:
                    key = (cp.relative_x, cp.relative_y, str(cp.medium), str(cp.type_uri))
                    default_cps_map[key] = cp

            for j, cp_data in enumerate(item_data.get('connection_points', [])):
                original_cp = cp_data['original']
                key = (cp_data['relative_x'], cp_data['relative_y'],
                       str(cp_data['medium']), str(cp_data['type_uri']))
                new_cp = None

                if key in default_cps_map:
                    new_cp = default_cps_map[key]

                    new_cp.label = cp_data.get('label', '')
                    new_cp.comment = cp_data.get('comment', '')

                    del default_cps_map[key]
                else:
                    add_cp_cmd = AddConnectionPointCommand(
                        new_item, cp_data['relative_x'], cp_data['relative_y'],
                        cp_data['medium'], cp_data['type_uri']
                    )
                    if add_cp_cmd.execute():
                        new_cp = add_cp_cmd.connection_point
                        new_cp.label = cp_data.get('label', '')
                        new_cp.comment = cp_data.get('comment', '')
                        compound_command.add_command(add_cp_cmd)
                    else:
                        print(f"Error creating pasted CP for {new_item.label}")

                if new_cp:
                    new_cps_map[original_cp] = new_cp

                    for prop_data in cp_data.get('properties', []):

                        add_prop_cmd = AddPropertyCommand(new_cp, prop_data)
                        if add_prop_cmd.execute():
                            compound_command.add_command(add_prop_cmd)
                        else:
                            print(f"Error creating pasted property for CP {new_cp.inst_uri}")

            for prop_data in item_data.get('properties', []):
                add_prop_cmd = AddPropertyCommand(new_item, prop_data)
                if add_prop_cmd.execute():
                    compound_command.add_command(add_prop_cmd)
                else:
                    print(f"Error creating pasted property for {new_item.label}")

        for conn_data in self.clipboard['connections']:
            if conn_data['type'] == 'Connection':
                source_item_idx, source_cp_idx = conn_data['source_index']
                target_item_idx, target_cp_idx = conn_data['target_index']

                original_source_cp = None
                original_target_cp = None

                try:

                    original_source_cp = self.clipboard['items'][source_item_idx]['connection_points'][source_cp_idx][
                        'original']
                    original_target_cp = self.clipboard['items'][target_item_idx]['connection_points'][target_cp_idx][
                        'original']
                except (IndexError, KeyError, TypeError) as e:

                    print(
                        f"Paste Error: Could not find original CP data object in clipboard structure for connection. Indices: src({source_item_idx},{source_cp_idx}), tgt({target_item_idx},{target_cp_idx}). Error: {e}")
                    continue

                new_source_cp = new_cps_map.get(original_source_cp)
                new_target_cp = new_cps_map.get(original_target_cp)

                if new_source_cp and new_target_cp:

                    if not new_source_cp.connected_to and not new_target_cp.connected_to:
                        add_conn_cmd = AddConnectionCommand(
                            self.scene, new_source_cp, new_target_cp, conn_data['type_uri']
                        )
                        if add_conn_cmd.execute():
                            new_conn = add_conn_cmd.connection
                            new_conn.label = conn_data.get('label', '')
                            new_conn.comment = conn_data.get('comment', '')
                            compound_command.add_command(add_conn_cmd)
                        else:
                            print(
                                f"Error creating pasted connection command between {new_source_cp.inst_uri} and {new_target_cp.inst_uri}")
                    else:
                        print(
                            f"Skipping pasted connection: Points {new_source_cp.inst_uri} or {new_target_cp.inst_uri} already connected.")
                else:

                    missing = []
                    if not new_source_cp: missing.append(f"source (original: {original_source_cp})")
                    if not new_target_cp: missing.append(f"target (original: {original_target_cp})")
                    print(
                        f"Paste Error: Could not find new {' and '.join(missing)} CP(s) in new_cps_map. Skipping connection.")

        if self.command_history.push(compound_command):

            for original_item, new_item in new_items_map.items():
                is_child_of_pasted = False
                if new_item.parentItem():
                    for _, pasted_parent in new_items_map.items():
                        if new_item.parentItem() == pasted_parent:
                            is_child_of_pasted = True;
                            break
                if not is_child_of_pasted:
                    new_item.setSelected(True)
            find_status_bar(self).showMessage(f"Pasted {len(new_items_map)} items.")
        else:
            find_status_bar(self).showMessage("Paste failed")

    def _select_all_items(self):
        """Selects all selectable items in the scene."""
        self.scene.clearSelection()
        for item in self.scene.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)
        find_status_bar(self).showMessage("Selected all items")

    def _rotate_selected_items_90(self):
        """Rotates selected ConnectableItems by 90 degrees."""
        selected_items = Selection(self.scene.selectedItems()).getConnectable
        if not selected_items:
            return

        old_rotations = [item.rotation() for item in selected_items]
        new_rotations = [(item.rotation() + 90) % 360 for item in selected_items]

        command = RotateCommand(selected_items, old_rotations, new_rotations)
        if push_command_to_scene(self.scene, command):
            find_status_bar(self).showMessage("Rotated selected items 90°")

            if len(selected_items) == 1 and hasattr(self.property_panel, 'connectable_properties'):
                self.property_panel.connectable_properties.rotation.setText(f"{selected_items[0].rotation()}")


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

        self.identifier = QLineEdit("P");
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
        if isinstance(view, Canvas):
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

            command = AddConnectionPointCommand(
                connectable,
                data['position_x'],
                data['position_y'],
                data['medium'],
                data['type_uri']
            )

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
        self.available_contain_map = {}         # item -> list_item
        self.contained_map = {}                 # item -> list_item
        self.available_domains_map = {}         # item -> list_item
        self.enclosed_domains_map = {}          # item -> list_item
        self.available_physical_spaces_map = {} # item -> list_item
        self.available_observation_locations_map = {} # item -> list_item

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
            self.available_physical_spaces_list.setSelectionMode(QListWidget.SingleSelection) # Single selection
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
            self.available_observation_locations_list.setSelectionMode(QListWidget.SingleSelection) # Single selection
            available_obs_loc_layout.addWidget(self.available_observation_locations_list)
            obs_loc_layout.addWidget(available_obs_loc_group)

            # Group for current location and controls
            obs_loc_controls_group = QGroupBox("Set Observation Location")
            obs_loc_controls_layout = QFormLayout(obs_loc_controls_group)
            self.current_observation_location_label = QLabel("None")
            self.current_observation_location_label.setWordWrap(True)
            self.set_observation_location_btn = QPushButton("Set Selected as Observation Location")
            self.clear_observation_location_btn = QPushButton("Clear Observation Location")
            obs_loc_controls_layout.addRow("Current Observation Target:", self.current_observation_location_label) # Changed label slightly
            obs_loc_controls_layout.addRow(self.set_observation_location_btn)
            obs_loc_controls_layout.addRow(self.clear_observation_location_btn)
            obs_loc_layout.addWidget(obs_loc_controls_group)

            self.tabs.addTab(self.observation_location_widget, "Observation Location")

            # Connect signals for Observation Location tab
            self.set_observation_location_btn.clicked.connect(self._set_observation_location)
            self.clear_observation_location_btn.clicked.connect(self._clear_observation_location)
            self.available_observation_locations_list.currentItemChanged.connect(self._update_observation_location_button_state)
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
            if scene_item == self.item: continue # Skip self

            valid_contain_candidate = False
            # Check for valid containment relationship type and prevent cycles
            if is_physical_container and isinstance(scene_item, PhysicalSpace):
                parent = self.item.parentItem(); is_ancestor = False
                while parent:
                    if parent == scene_item: is_ancestor = True; break
                    parent = parent.parentItem()
                if not is_ancestor: valid_contain_candidate = True
            elif not is_physical_container and isinstance(self.item, ConnectableItem) and \
                 isinstance(scene_item, ConnectableItem) and not isinstance(scene_item, (DomainSpace, PhysicalSpace)):
                 # Equipment containing Equipment (excluding Domain/Physical)
                 parent = self.item.parentItem(); is_ancestor = False
                 while parent:
                     if parent == scene_item: is_ancestor = True; break
                     parent = parent.parentItem()
                 if not is_ancestor: valid_contain_candidate = True

            if valid_contain_candidate:
                # Ensure item has necessary attributes before creating label
                if hasattr(scene_item, 'label') and hasattr(scene_item, 'type_uri') and hasattr(scene_item, 'inst_uri'):
                     label = scene_item.label or f"{to_label(scene_item.type_uri)} ({to_label(scene_item.inst_uri)})"
                     list_item = QListWidgetItem(label)
                     list_item.setData(Qt.UserRole, scene_item) # Store the actual item

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
                if isinstance(scene_item, DomainSpace) and hasattr(scene_item, 'label') and hasattr(scene_item, 'inst_uri'):
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
                     print(f"Warning: Skipping DomainSpace {scene_item} in encloses list population - missing attributes.")


        # --- Populate Physical Location List (if Equipment) ---
        is_equipment = isinstance(self.item, ConnectableItem) and not isinstance(self.item, DomainSpace)
        if is_equipment and hasattr(self, 'available_physical_spaces_list'):
            current_location_item = None
            for scene_item in self.scene.items():
                # Ensure item has necessary attributes
                if isinstance(scene_item, PhysicalSpace) and hasattr(scene_item, 'label') and hasattr(scene_item, 'inst_uri'):
                    label = scene_item.label or f"Space ({to_label(scene_item.inst_uri)})"
                    list_item = QListWidgetItem(label)
                    list_item.setData(Qt.UserRole, scene_item) # Store item
                    self.available_physical_spaces_list.addItem(list_item)
                    self.available_physical_spaces_map[scene_item] = list_item

                    # Check if this is the currently assigned location (using the temporary selected_uri)
                    if self.selected_physical_location_uri == scene_item.inst_uri:
                        current_location_item = scene_item
                        # We select based on the *current* selection in the dialog, not initial state
                        self.available_physical_spaces_list.setCurrentItem(list_item) # Use setCurrentItem for single selection
                elif isinstance(scene_item, PhysicalSpace):
                    print(f"Warning: Skipping PhysicalSpace {scene_item} in physical location list population - missing attributes.")

            # Update the current location label based on the *current* selection in the dialog
            if current_location_item:
                label = current_location_item.label or f"Space ({to_label(current_location_item.inst_uri)})"
                self.current_location_label.setText(label)
            else:
                self.current_location_label.setText("None")
            self._update_location_button_state() # Update button state after population


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
                    if hasattr(scene_item, 'label') and hasattr(scene_item, 'type_uri') and hasattr(scene_item, 'inst_uri'):
                        # Create a descriptive label
                        label = f"{scene_item.label or to_label(scene_item.inst_uri)}"
                        if isinstance(scene_item, ConnectableItem): prefix = "Equip"
                        elif isinstance(scene_item, Connection): prefix = "Conn"
                        elif isinstance(scene_item, ConnectionPoint): prefix = "CP"
                        else: prefix = "Item" # Fallback
                        full_label = f"[{prefix}] {to_label(scene_item.type_uri)}: {label}"

                        list_item = QListWidgetItem(full_label)
                        list_item.setData(Qt.UserRole, scene_item) # Store the actual graphics item

                        self.available_observation_locations_list.addItem(list_item)
                        self.available_observation_locations_map[scene_item] = list_item

                        # Check if this is the currently assigned *selected* observation location
                        if self.selected_observation_location_uri == scene_item.inst_uri:
                            current_obs_loc_item = scene_item
                            self.available_observation_locations_list.setCurrentItem(list_item) # Select in list
                    else:
                        print(f"Warning: Skipping item {scene_item} in observation location list population - missing attributes.")


            # Update the current location label based on the *current* selection in the dialog
            if current_obs_loc_item:
                # Recreate the label for consistency
                label = f"{current_obs_loc_item.label or to_label(current_obs_loc_item.inst_uri)}"
                if isinstance(current_obs_loc_item, ConnectableItem): prefix = "Equip"
                elif isinstance(current_obs_loc_item, Connection): prefix = "Conn"
                elif isinstance(current_obs_loc_item, ConnectionPoint): prefix = "CP"
                else: prefix = "Item"
                full_label = f"[{prefix}] {to_label(current_obs_loc_item.type_uri)}: {label}"
                self.current_observation_location_label.setText(full_label)
            else:
                self.current_observation_location_label.setText("None")
            self._update_observation_location_button_state() # Update button state after population


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
             source_list.takeItem(source_list.row(list_item)) # Removes item from source list

        # Add items to target list and update maps
        for item_data in graphics_items_to_move:
            if item_data:
                 # Create a new QListWidgetItem for the target list (important!)
                 # Recreate the label based on the item type
                label = item_data.label or f"{to_label(item_data.type_uri)} ({to_label(item_data.inst_uri)})"
                if isinstance(item_data, PhysicalSpace): pass # Label already good
                elif isinstance(item_data, DomainSpace): label = f"Domain ({to_label(item_data.inst_uri)})" # Adjust if needed
                # Add more specific labels if needed

                new_list_item = QListWidgetItem(label)
                new_list_item.setData(Qt.UserRole, item_data)

                target_list.addItem(new_list_item) # Add QListWidgetItem to target list
                target_map[item_data] = new_list_item # Update target map (graphics_item -> list_item)
                if item_data in source_map:
                    del source_map[item_data] # Remove from source map

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
                    self._update_location_button_state() # Update button states after setting

    def _clear_physical_location(self):
        """Clears the currently set physical location for Physical Location tab."""
        if hasattr(self, 'current_location_label'):
            self.selected_physical_location_uri = None
            self.current_location_label.setText("None")
            # Deselect item in the list
            self.available_physical_spaces_list.setCurrentItem(None)
            self._update_location_button_state() # Update button states after clearing

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
                can_set = selected_target_item and (selected_target_item.inst_uri != self.selected_observation_location_uri)
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
                    if isinstance(selected_target_item, ConnectableItem): prefix = "Equip"
                    elif isinstance(selected_target_item, Connection): prefix = "Conn"
                    elif isinstance(selected_target_item, ConnectionPoint): prefix = "CP"
                    else: prefix = "Item"
                    full_label = f"[{prefix}] {to_label(selected_target_item.type_uri)}: {label}"
                    self.current_observation_location_label.setText(full_label)
                    self._update_observation_location_button_state() # Update buttons

    def _clear_observation_location(self):
        """Clears the currently set observation location."""
        if hasattr(self, 'current_observation_location_label'):
            self.selected_observation_location_uri = None
            self.current_observation_location_label.setText("None")
            # Deselect item in the list
            self.available_observation_locations_list.setCurrentItem(None)
            self._update_observation_location_button_state() # Update buttons

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
               (isinstance(self.item, ConnectableItem) and isinstance(item_to_add, ConnectableItem) and not isinstance(self.item, DomainSpace) and not isinstance(item_to_add, DomainSpace)):
                commands.append(AddContainedItemCommand(self.item, item_to_add))

        # Find items removed (in initial set but not current)
        removed_items = self.initial_contained_items - current_contained_items
        for item_to_remove in removed_items:
             if (isinstance(self.item, PhysicalSpace) and isinstance(item_to_remove, PhysicalSpace)) or \
               (isinstance(self.item, ConnectableItem) and isinstance(item_to_remove, ConnectableItem) and not isinstance(self.item, DomainSpace) and not isinstance(item_to_remove, DomainSpace)):
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
                item for item in self.available_domains_map.keys() | self.enclosed_domains_map.keys() # Check both maps
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
                    items=[self.item], # Command expects a list
                    attribute_name='physical_location_uri',
                    new_value=self.selected_physical_location_uri # Can be None or a URIRef
                )
                commands.append(cmd)


        # 4. --- Observation Location relationship (Only if item is Equipment) ---
        if is_equipment and hasattr(self, 'selected_observation_location_uri'):
            # Compare the final selected URI in the dialog with the initial one
            if self.initial_observation_location_uri != self.selected_observation_location_uri:
                # Use ChangeAttributeCommand to set/clear the URI
                cmd = ChangeAttributeCommand(
                    items=[self.item], # Command expects a list
                    attribute_name='observation_location_uri', # The attribute added to ConnectableItem
                    new_value=self.selected_observation_location_uri # Can be None or a URIRef
                )
                commands.append(cmd)

        return commands


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
        if not scene: return

        view = scene.views()[0] if scene.views() else None
        if isinstance(view, Canvas):
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


class PropertyPanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        self.connectable_widget = QWidget()
        self.connection_point_widget = QWidget()
        self.connection_widget = QWidget()
        self.system_widget = QWidget()
        self.physical_space_widget = QWidget()
        self.domain_space_widget = QWidget()
        self.property_widget = QWidget()

        self.connectable_layout = QVBoxLayout(self.connectable_widget)
        self.connection_point_layout = QVBoxLayout(self.connection_point_widget)
        self.connection_layout = QVBoxLayout(self.connection_widget)
        self.system_layout = QVBoxLayout(self.system_widget)
        self.physical_space_layout = QVBoxLayout(self.physical_space_widget)
        self.domain_space_layout = QVBoxLayout(self.domain_space_widget)
        self.property_layout = QVBoxLayout(self.property_widget)

        self.connectable_properties = ConnectableProperties()
        self.connection_properties = ConnectionProperties()
        self.connection_point_properties = ConnectionPointProperties()
        self.system_properties = SystemProperties()
        self.physical_space_properties = PhysicalSpaceProperties()
        self.domain_space_properties = DomainSpaceProperties()
        self.property_properties = PropertyProperties()

        self.connectable_layout.addLayout(self.connectable_properties)
        self.connectable_layout.addStretch(1)
        self.connection_point_layout.addLayout(self.connection_point_properties)
        self.connection_point_layout.addStretch(1)
        self.connection_layout.addLayout(self.connection_properties)
        self.connection_layout.addStretch(1)
        self.system_layout.addLayout(self.system_properties)
        self.system_layout.addStretch(1)
        self.physical_space_layout.addLayout(self.physical_space_properties)
        self.physical_space_layout.addStretch(1)
        self.domain_space_layout.addLayout(self.domain_space_properties)
        self.domain_space_layout.addStretch(1)
        self.property_layout.addLayout(self.property_properties)
        self.property_layout.addStretch(1)

        self.tabs.addTab(self.connectable_widget, "s223.Connectable")
        self.tabs.addTab(self.connection_point_widget, "s223.ConnectionPoint")
        self.tabs.addTab(self.connection_widget, "s223.Connection")
        self.tabs.addTab(self.system_widget, "s223.System")
        self.tabs.addTab(self.physical_space_widget, "s223.PhysicalSpace")
        self.tabs.addTab(self.domain_space_widget, "s223.DomainSpace")
        self.tabs.addTab(self.property_widget, "s223.Property")

        layout.addWidget(self.tabs)

        self.setMinimumWidth(250)
        self.setLayout(layout)

    def update_properties(self, selected_items: Selection):

        connectables = selected_items.getConnectable
        connections = selected_items.getConnection
        connection_points = selected_items.getConnectionPoint
        systems = selected_items.getSystem
        physical_spaces = selected_items.getPhysicalSpace
        domain_spaces = selected_items.getDomainSpace
        properties = selected_items.getProperty

        equipment = Selection([item for item in connectables if not isinstance(item, (DomainSpace, PhysicalSpace))])

        has_equipment = len(equipment) >= 1
        has_connections = len(connections) >= 1
        has_connection_points = len(connection_points) >= 1
        has_systems = len(systems) >= 1
        has_physical_spaces = len(physical_spaces) >= 1
        has_domain_spaces = len(domain_spaces) >= 1
        has_properties = len(properties) >= 1

        self.connectable_properties.update_properties(equipment)
        # self.tabs.setTabEnabled(0, has_equipment)
        self.tabs.setTabVisible(0, has_equipment)

        self.connection_point_properties.update_properties(connection_points)
        self.tabs.setTabVisible(1, has_connection_points)

        self.connection_properties.update_properties(connections)
        self.tabs.setTabVisible(2, has_connections)

        self.system_properties.update_properties(systems)
        self.tabs.setTabVisible(3, has_systems)

        self.physical_space_properties.update_properties(physical_spaces)
        self.tabs.setTabVisible(4, has_physical_spaces)

        self.domain_space_properties.update_properties(domain_spaces)
        self.tabs.setTabVisible(5, has_domain_spaces)

        self.property_properties.update_properties(properties)
        self.tabs.setTabVisible(6, has_properties)

        if has_properties:
            self.tabs.setCurrentIndex(6)
        elif has_domain_spaces:
            self.tabs.setCurrentIndex(5)
        elif has_equipment:
            self.tabs.setCurrentIndex(0)
        elif has_connection_points:
            self.tabs.setCurrentIndex(1)
        elif has_connections:
            self.tabs.setCurrentIndex(2)
        elif has_systems:
            self.tabs.setCurrentIndex(3)
        elif has_physical_spaces:
            self.tabs.setCurrentIndex(4)
        else:
            pass


class DiagramApplication(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Building Systems Design with Brick and REC Ontologies")
        self.resize(1200, 800)
        self._setup_ui()
        self.setAcceptDrops(True)

    def _output_to_status_bar(self, text: str):
        self.statusBar().showMessage(text)

    def _setup_ui(self):
        # The UI setup order is important to ensure objects that depend on
        # others are created after their dependencies.

        # 1. Create components that don't depend on the canvas.
        self._setup_entity_browser()
        self._setup_property_panel()

        # 2. Create the canvas, which also creates the scene.
        self._setup_canvas()

        # 3. Now that the canvas and scene exist, create the scene browser.
        self._setup_scene_browser()

        # 4. Setup the remaining UI elements.
        self._setup_menu_bar()
        self._setup_toolbar()
        self._output_to_status_bar("Ready")

    def _setup_entity_browser(self):
        entity_tree = EntityBrowser()
        entity_dock = QDockWidget("Entities", self)
        entity_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        entity_dock.setWidget(entity_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, entity_dock)

    def _setup_scene_browser(self):
        """Creates the new Scene Browser dock widget and connects its signals."""
        self.scene_browser = SceneBrowser(self.canvas.scene, self)
        scene_dock = QDockWidget("Scene Hierarchy", self)
        scene_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        scene_dock.setWidget(self.scene_browser)
        # Add the new dock widget to the left area, tabbed with the entity browser.
        self.addDockWidget(Qt.LeftDockWidgetArea, scene_dock)

        # --- Connect Signals for Automatic Updates ---
        # 1. When a command is executed/undone/redone, repopulate the tree.
        self.canvas.command_history.history_changed.connect(self.scene_browser.repopulate_tree)
        # 2. When canvas selection changes, update the tree selection.
        self.canvas.scene.selectionChanged.connect(self.scene_browser.on_scene_selection_changed)

    def _setup_property_panel(self):
        self.property_panel = PropertyPanel(self)
        properties_dock = QDockWidget("Properties", self)
        properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        properties_dock.setWidget(self.property_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)

    def _setup_canvas(self):
        self.canvas = Canvas(self.property_panel)
        self.setCentralWidget(self.canvas)

    def _setup_toolbar(self):
        toolbar = self.addToolBar("Tools")
        self.grid_action = toolbar.addAction("Toggle Grid")
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(CanvasProperties.enable_grid)
        self.grid_action.triggered.connect(self._toggle_grid)

        self.location_line_action = toolbar.addAction("Location Lines")
        self.location_line_action.setShortcut("Ctrl+L")
        self.location_line_action.setCheckable(True)
        self.location_line_action.setChecked(self.canvas.scene.show_location_lines)
        self.location_line_action.triggered.connect(self._toggle_location_lines)

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        save_action = file_menu.addAction("Save As...")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_canvas)

        load_action = file_menu.addAction("Load...")
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._load_canvas)

        edit_menu = menu_bar.addMenu("Edit")
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._undo)

        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self._redo)

        edit_menu.addSeparator()
        copy_action = edit_menu.addAction("Copy")
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.canvas._copy_selected_items)

        paste_action = edit_menu.addAction("Paste")
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.canvas._paste_items)

        group_action = edit_menu.addAction("Group")
        group_action.setShortcut("Ctrl+G")
        group_action.triggered.connect(self.canvas._create_system_from_selection)

        delete_action = edit_menu.addAction("Delete")
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.canvas._delete_selected_items)

    def _toggle_grid(self):
        enable = self.grid_action.isChecked()
        self.canvas.toggle_grid(enable)
        self._output_to_status_bar(f"Grid {'enabled' if enable else 'disabled'}")

    def _toggle_location_lines(self):
        if isinstance(self.canvas.scene, DiagramScene) and hasattr(self, 'location_line_action'):
            self.canvas.scene.toggle_location_lines()
            is_showing = self.canvas.scene.show_location_lines
            self.location_line_action.setChecked(is_showing)
            self._output_to_status_bar(f"Location indicator lines {'shown' if is_showing else 'hidden'}")
        else:
            print("Warning: Cannot toggle location lines - scene type mismatch or action not found.")

    def _undo(self):
        if self.canvas.command_history.undo():
            self._output_to_status_bar("Undo")
            self.canvas.update()

    def _redo(self):
        if self.canvas.command_history.redo():
            self._output_to_status_bar("Redo")
            self.canvas.update()

    def _zoom_in(self):
        self.canvas.scale(1.2, 1.2)
        self._output_to_status_bar("Zoomed in")

    def _zoom_out(self):
        self.canvas.scale(1 / 1.2, 1 / 1.2)
        self._output_to_status_bar("Zoomed out")

    def _reset_zoom(self):
        self.canvas.resetTransform()
        self._output_to_status_bar("Zoom reset to 100%")

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.ttl', '.turtle')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.ttl', '.turtle')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.ttl', '.turtle')):
                        self._output_to_status_bar(f"Loading diagram from dropped file: {file_path}...")
                        self.canvas.command_history.clear()
                        success = load_from_turtle(self.canvas.scene, file_path)
                        if success:
                            self.scene_browser.repopulate_tree()  # Manually refresh after load
                            self._output_to_status_bar(f"Diagram loaded from {file_path}")
                        else:
                            self._output_to_status_bar(f"Failed to load diagram from {file_path}")
                            QMessageBox.warning(self, "Load Error", f"Could not load the diagram from:\n{file_path}")
                        event.acceptProposedAction()
                        return
        event.ignore()

    def _save_canvas(self):
        suggested_filename = "hvac_diagram.ttl"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Diagram As", suggested_filename, "Turtle Files (*.ttl *.turtle);;All Files (*)"
        )
        if filepath:
            if not os.path.splitext(filepath)[1]:
                filepath += ".ttl"
            save_to_turtle(self.canvas.scene, filepath)
            self._output_to_status_bar(f"Diagram saved to {filepath}")

    def _load_canvas(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Diagram", "", "Turtle Files (*.ttl *.turtle);;All Files (*)"
        )
        if filepath:
            self._output_to_status_bar(f"Loading diagram from {filepath}...")
            self.canvas.command_history.clear()  # Clear history for the new file
            success = load_from_turtle(self.canvas.scene, filepath)
            if success:
                self.scene_browser.repopulate_tree()  # Manually refresh after load
                self._output_to_status_bar(f"Diagram loaded from {filepath}")
            else:
                self._output_to_status_bar(f"Failed to load from {filepath}")


if __name__ == "__main__":

    app = QApplication(sys.argv)
    diagram_app = DiagramApplication()
    diagram_app.show()

    sys.exit(app.exec_())

