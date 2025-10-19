import os
import traceback

from typing import  Dict
from rdflib import Literal

from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView,
    QGraphicsLineItem, QGraphicsRectItem, QTreeWidgetItem, QWidget, QTreeWidget, QFormLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QMainWindow, QDockWidget,
    QApplication, QDialog, QDoubleSpinBox, QMessageBox, QTabWidget, QStyle, QMenu, QFileDialog,
)

from PyQt5.QtGui import (
    QPixmap, QDrag, QDragMoveEvent, QDragEnterEvent
)

from open223Builder.ontology.namespaces import (
    S223, VISU, BLDG, RDF, RDFS, QUDT, QUDTQK
)

from open223Builder.library import connectable_library

from open223Builder.app.dialogs import RelationshipDialog, AddPropertyDialog, AddConnectionPointDialog
import open223Builder.app.widgets as properties
from open223Builder.app.items import *


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

        command = RemoveItemCommand(self.scene, Selection(selected_items))
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
                    connection_point = ConnectionPoint(
                        connectable=new_item,
                        medium=cp_data['medium'],
                        type_uri=cp_data['type_uri'],
                        position=(cp_data['relative_x'], cp_data['relative_y']),
                    )
                    add_cp_cmd = AddConnectionPointCommand(connection_point=connection_point)

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

                        property = Property.new(prop_data=prop_data, parent=new_cp)
                        add_prop_cmd = AddPropertyCommand(parent_item=new_cp, property=property)

                        if add_prop_cmd.execute():
                            compound_command.add_command(add_prop_cmd)
                        else:
                            print(f"Error creating pasted property for CP {new_cp.inst_uri}")

            for prop_data in item_data.get('properties', []):

                property = Property.new(prop_data=prop_data, parent=new_cp)
                add_prop_cmd = AddPropertyCommand(parent_item=new_cp, property=property)

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
                        connection = Connection(
                            source=new_source_cp,
                            target=new_target_cp,
                            type_uri=conn_data['type_uri'],
                        )

                        add_conn_cmd = AddConnectionCommand(
                            scene=self.scene, connection=connection,
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

        self.connectable_properties = properties.ConnectableProperties()
        self.connection_properties = properties.ConnectionProperties()
        self.connection_point_properties = properties.ConnectionPointProperties()
        self.system_properties = properties.SystemProperties()
        self.physical_space_properties = properties.PhysicalSpaceProperties()
        self.domain_space_properties = properties.DomainSpaceProperties()
        self.property_properties = properties.PropertyProperties()

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

        self._setup_ui()
        self.showMaximized()
        self.setAcceptDrops(True)

    def _output_to_status_bar(self, text: str):
        self.statusBar().showMessage(text)

    def _setup_ui(self):
        self._setup_entity_browser()
        self._setup_property_panel()
        self._setup_canvas()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._output_to_status_bar("Ready")

    def _setup_entity_browser(self):
        entity_tree = EntityBrowser()
        entity_dock = QDockWidget("Entities", self)
        entity_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        entity_dock.setWidget(entity_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, entity_dock)

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
        self.location_line_action.setShortcut("Ctrl+L")  # Set the desired shortcut
        self.location_line_action.setCheckable(True)
        self.location_line_action.setChecked(self.canvas.scene.show_location_lines)
        self.location_line_action.triggered.connect(self._toggle_location_lines)  # Connect to handler

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
        # Ensure the scene is the correct type and the action exists
        if isinstance(self.canvas.scene, DiagramScene) and hasattr(self, 'location_line_action'):
            # Call the scene's toggle method
            self.canvas.scene.toggle_location_lines()
            # Update the action's checked state to match the scene's state
            is_showing = self.canvas.scene.show_location_lines
            self.location_line_action.setChecked(is_showing)
            # Update status bar
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
                if url.isLocalFile():
                    file_path = url.toLocalFile()

                    if file_path.lower().endswith(('.ttl', '.turtle')):
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):

        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.ttl', '.turtle')):
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

                        success = load_from_turtle(self.canvas.scene, file_path)
                        if success:
                            self._output_to_status_bar(f"Diagram loaded from {file_path}")
                        else:
                            self._output_to_status_bar(f"Failed to load diagram from {file_path}")
                            QMessageBox.warning(self, "Load Error", f"Could not load the diagram from:\n{file_path}")
                        event.acceptProposedAction()
                        return

        event.ignore()

    def _save_canvas(self):
        suggested_filename = "hvac_diagram.ttl"

        current_dir = os.getcwd() # Or remember last used directory
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Diagram As",
            os.path.join(current_dir, suggested_filename),
            "Turtle Files (*.ttl *.turtle);;All Files (*)"
        )

        if filepath:
            if not os.path.splitext(filepath)[1]:
                filepath += ".ttl"
            save_to_turtle(self.canvas.scene, filepath)
            self._output_to_status_bar(f"Diagram saved to {filepath}")

    def _load_canvas(self):

        current_dir = os.getcwd()
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Diagram", current_dir,
            "Turtle Files (*.ttl *.turtle);;All Files (*)"
        )

        if filepath:
            self._output_to_status_bar(f"Loading diagram from {os.path.basename(filepath)}...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:

                 success = load_from_turtle(self.canvas.scene, filepath)
                 if success:
                      self._output_to_status_bar(f"Diagram loaded from {os.path.basename(filepath)}")
                 else:

                      self._output_to_status_bar(f"Failed to load diagram from {os.path.basename(filepath)}")
            finally:
                 QApplication.restoreOverrideCursor()





