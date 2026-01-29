"""
TableNode Generator for Extended Matrix GraphML Export.

Generates yEd TableNode elements with epoch swimlanes.
Based on reverse engineering of TempluMare_EM_converted_converted.graphml.
"""

from typing import List, Dict, Tuple
from lxml import etree as ET
from s3dgraphy.nodes import EpochNode


class TableNodeGenerator:
    """Generate yEd TableNode with epoch swimlanes."""

    # yFiles namespace
    YFILES_NS = "http://www.yworks.com/xml/graphml"

    def __init__(self):
        """Initialize the TableNode generator."""
        self.ns_map = {'y': self.YFILES_NS}

    def generate_tablenode(
        self,
        site_id: str,
        site_metadata: Dict[str, str],
        epochs: List[EpochNode],
        canvas_width: float = 2584.0,
        canvas_height: float = 2284.0,
        canvas_x: float = -29.0,
        canvas_y: float = -35.0
    ) -> ET.Element:
        """
        Generate complete TableNode XML element.

        Args:
            site_id: Site identifier (e.g., "GT16")
            site_metadata: Additional metadata (ORCID, etc.)
            epochs: List of EpochNode objects
            canvas_width: Total canvas width
            canvas_height: Total canvas height (will be recalculated from rows)
            canvas_x: Canvas X position
            canvas_y: Canvas Y position

        Returns:
            lxml Element representing the TableNode
        """
        # Create root node element
        node = ET.Element(
            'node',
            id="n0",
            attrib={'{http://www.yworks.com/xml/graphml}foldertype': 'group'}
        )

        # Create data element for d6 (node graphics)
        data = ET.SubElement(node, 'data', key='d6')

        # Create TableNode
        table_node = ET.SubElement(
            data,
            '{%s}TableNode' % self.YFILES_NS,
            configuration='YED_TABLE_NODE'
        )

        # Geometry
        geometry = ET.SubElement(table_node, '{%s}Geometry' % self.YFILES_NS)
        geometry.set('height', str(canvas_height))
        geometry.set('width', str(canvas_width))
        geometry.set('x', str(canvas_x))
        geometry.set('y', str(canvas_y))

        # Main site label
        site_label_parts = [site_id]
        if 'id' in site_metadata:
            site_label_parts.append(f"ID:{site_metadata['id']}")
        if 'orcid' in site_metadata:
            site_label_parts.append(f"ORCID:{site_metadata['orcid']}")

        main_label = ET.SubElement(table_node, '{%s}NodeLabel' % self.YFILES_NS)
        main_label.text = ' '.join(site_label_parts)

        # Table with Rows
        table = ET.SubElement(table_node, '{%s}Table' % self.YFILES_NS)
        rows_elem = ET.SubElement(table, '{%s}Rows' % self.YFILES_NS)

        # Sort epochs by start time (most recent first for visual consistency)
        sorted_epochs = sorted(epochs, key=lambda e: e.start if e.start else 0, reverse=True)

        # Calculate row heights (proportional to epoch duration or default)
        total_duration = sum(
            abs(e.end - e.start) if (e.start and e.end) else 100
            for e in sorted_epochs
        )

        min_row_height = 66.0
        available_height = canvas_height - (len(sorted_epochs) * min_row_height)

        # Generate rows and epoch labels
        for idx, epoch in enumerate(sorted_epochs):
            row_id = f"row_{idx}"

            # Calculate proportional height
            if epoch.start is not None and epoch.end is not None:
                duration = abs(epoch.end - epoch.start)
                proportional_height = (duration / total_duration) * available_height if total_duration > 0 else 0
            else:
                proportional_height = 0

            row_height = max(min_row_height, min_row_height + proportional_height)

            # Create Row element
            row = ET.SubElement(rows_elem, '{%s}Row' % self.YFILES_NS)
            row.set('height', f"{row_height:.1f}")
            row.set('id', row_id)
            row.set('minimumHeight', '50.0')

            # Create Insets
            insets = ET.SubElement(row, '{%s}Insets' % self.YFILES_NS)
            insets.set('bottom', '0')
            insets.set('left', '0')
            insets.set('right', '0')
            insets.set('top', '0')

        # Generate epoch labels (after rows)
        for idx, epoch in enumerate(sorted_epochs):
            row_id = f"row_{idx}"

            # Epoch label
            epoch_label = ET.SubElement(table_node, '{%s}NodeLabel' % self.YFILES_NS)

            # Determine background color (can be customized per epoch)
            bg_color = self._get_epoch_color(epoch)
            epoch_label.set('backgroundColor', bg_color)

            # Build epoch label text
            label_parts = [epoch.name]
            if epoch.start is not None and epoch.end is not None:
                label_parts.append(f"[start:{int(epoch.start)};end:{int(epoch.end)}]")

            epoch_label.text = ' '.join(label_parts)

            # RowNodeLabelModelParameter - binds label to row
            param = ET.SubElement(epoch_label, '{%s}RowNodeLabelModelParameter' % self.YFILES_NS)
            param.set('id', row_id)

        # Create nested graph for content
        graph = ET.SubElement(node, 'graph')
        graph.set('edgedefault', 'directed')
        graph.set('id', 'n0:')

        return node

    def _get_epoch_color(self, epoch: EpochNode) -> str:
        """
        Determine background color for epoch swimlane.

        Can be customized based on epoch properties.
        Default colors following TempluMare example.

        Args:
            epoch: EpochNode object

        Returns:
            Hex color string
        """
        # Default color palette (can be extended)
        default_colors = {
            'Post antiquity': '#CCFFCC',
            'Roman': '#FFFFCC',
            'Medieval': '#FFCCCC',
            'Modern': '#CCCCFF',
        }

        # Check if epoch name matches predefined colors
        for name_pattern, color in default_colors.items():
            if name_pattern.lower() in epoch.name.lower():
                return color

        # Default fallback color
        return '#E6E6E6'

    def calculate_epoch_y_ranges(
        self,
        epochs: List[EpochNode],
        canvas_height: float = 2284.0,
        canvas_y: float = -35.0
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate Y-coordinate ranges for each epoch swimlane.

        Used by node positioning logic to place stratigraphic nodes
        within their corresponding epoch bands.

        Args:
            epochs: List of EpochNode objects
            canvas_height: Total canvas height
            canvas_y: Canvas Y starting position

        Returns:
            Dictionary mapping epoch IDs to (min_y, max_y) tuples
        """
        # Sort epochs by start time (most recent first)
        sorted_epochs = sorted(epochs, key=lambda e: e.start if e.start else 0, reverse=True)

        # Calculate total duration
        total_duration = sum(
            abs(e.end - e.start) if (e.start and e.end) else 100
            for e in sorted_epochs
        )

        min_row_height = 66.0
        available_height = canvas_height - (len(sorted_epochs) * min_row_height)

        # Calculate y ranges
        y_ranges = {}
        current_y = canvas_y

        for epoch in sorted_epochs:
            # Calculate row height
            if epoch.start is not None and epoch.end is not None:
                duration = abs(epoch.end - epoch.start)
                proportional_height = (duration / total_duration) * available_height if total_duration > 0 else 0
            else:
                proportional_height = 0

            row_height = max(min_row_height, min_row_height + proportional_height)

            # Store range
            y_ranges[epoch.id] = (current_y, current_y + row_height)

            # Move to next row
            current_y += row_height

        return y_ranges
