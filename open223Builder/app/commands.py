from typing import Union

from open223Builder.ontology.namespaces import S223

from PyQt5.QtCore import (
    Qt, QPointF, QByteArray, QMimeData, QPoint, QTimer, QRectF, QRect
)


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

        # self.items = Selection(items).getConnectable
        self.items = items

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
    def __init__(
            self,
            container: Union['PhysicalSpace', 'ConnectableItem'],
            contained: Union['PhysicalSpace', 'ConnectableItem'],
    ):
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
                if hasattr(item, "update_bounding_rect") and self.contained in item.members:
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
                    if hasattr(item, "update_bounding_rect") and self.contained in item.members:
                        QTimer.singleShot(0, item.update_bounding_rect)


class RemoveContainedItemCommand(Command):
    def __init__(self, container, contained):

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
                if hasattr(item, 'update_bounding_rect') and self.contained in item.members:
                    QTimer.singleShot(0, item.update_bounding_rect)

    def _undo(self):

        current_scene_pos = self.contained.scenePos() if self.contained.scene() else QPointF(0, 0)

        added = self.container.add_item(self.contained)

        if added:

            new_relative_pos = self.container.mapFromScene(current_scene_pos)

            self.contained.setPos(new_relative_pos)

            if self.contained.scene():
                for item in self.contained.scene().items():
                    if hasattr(item, 'update_bounding_rect') and self.contained in item.members:
                        QTimer.singleShot(0, item.update_bounding_rect)


class RemoveItemCommand(Command):

    def __init__(
            self,
            scene,
            selection,
    ):

        self.scene = scene

        self.directly_selected = set(selection)

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

    def __init__(
            self,
            parent_item,
            property,
    ):

        self.parent_item = parent_item
        self.property = property

    def _execute(self):
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
    def __init__(self, connection, scene):
        self.scene = scene
        self.connection = connection

    def _execute(self):
        if self.connection not in self.scene.items():
            self.scene.addItem(self.connection)

    def _undo(self):
        if self.connection in self.scene.items():
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
    def __init__(self, connection_point):
        self.connection_point = connection_point

    def _execute(self):

        self.connection_point.connectable.add_connection_point(self.connection_point)

    def _undo(self):
        connectable = self.connection_point.connectable

        if self.connection_point in connectable.connection_points:
            connectable.connection_points.remove(self.connection_point)
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


class CommandHistory:
    def __init__(self, max_history=100):
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = max_history

    def push(self, command):
        if command.execute():
            self.undo_stack.append(command)
            self.redo_stack.clear()

            if len(self.undo_stack) > self.max_history:
                self.undo_stack.pop(0)
            return True
        return False

    def undo(self):
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        if command.undo():
            self.redo_stack.append(command)
            return True

        self.undo_stack.append(command)
        return False

    def redo(self):
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        if command.execute():
            self.undo_stack.append(command)
            return True

        self.redo_stack.append(command)
        return False

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
