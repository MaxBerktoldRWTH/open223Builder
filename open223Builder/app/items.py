import math
import rdflib

from typing import List, Optional

from PyQt5.QtSvg import (
    QGraphicsSvgItem, QSvgRenderer,
)
from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsView, QGraphicsLineItem, QStyle,
)

from PyQt5.QtGui import (
    QPen, QBrush, QColor, QPainter, QPainterPath, QFont
)

from open223Builder.ontology.namespaces import (
    BLDG, short_uuid, to_label,
)

from open223Builder.library import (
    port_library, svg_library, medium_library, connection_library
)

from open223Builder.app.commands import *


def push_command_to_scene(scene, command: 'Command'):
    if hasattr(scene, 'command_history'):
        return scene.command_history.push(command)

    return None


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
                    else:
                        event.ignore()

                elif isinstance(source_item, DomainSpace):

                    command = AddEnclosedSpaceCommand(self, source_item)
                    if push_command_to_scene(scene, command):
                        event.accept()
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

    @classmethod
    def new(cls, parent, prop_data) -> 'Property':

        property = Property(
            parent_item=parent,
            property_type=prop_data['property_type'],
            identifier=prop_data['identifier'],
        )

        try:
            pos = QPointF(prop_data['position_x'], prop_data['position_y'])
            property.setPos(pos)
        except KeyError:
            raise KeyError(prop_data)

        prop_data.aspect = prop_data.get('aspect')
        prop_data.external_reference = prop_data.get('external_reference', "")
        prop_data.internal_reference = prop_data.get('internal_reference')

        prop_data.unit = prop_data.get('unit')
        prop_data.quantity_kind = prop_data.get('quantity_kind')

        prop_data.value = prop_data.get('value', "")
        prop_data.medium = prop_data.get('medium')

        return property

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

        connection = Connection(
            source=self,
            target=target_point,
            type_uri=S223.Pipe,
        )

        command = AddConnectionCommand(connection, scene)

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
