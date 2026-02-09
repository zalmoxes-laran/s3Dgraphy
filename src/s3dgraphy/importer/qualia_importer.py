"""
QualiaImporter - Long-format property+provenance importer for Extended Matrix.

Imports em_paradata.xlsx files in long format (one row per US+property pair)
and enriches an existing graph with PropertyNode, ExtractorNode, DocumentNode,
and CombinerNode structures. These are "baked" into the GraphML as
ParadataNodeGroups by the GraphMLExporter.

This is NOT a BaseImporter subclass — the logic is fundamentally different:
- Requires an existing graph (enrichment, not creation)
- Reads long-format rows (one property per row, not one US per row)
- Creates paradata provenance chains (property→extractor→document)
- Supports multi-source combiner reasoning

Usage:
    # 1. First import stratigraphy (creates US nodes)
    strat_importer = MappedXLSXImporter(filepath='stratigraphy.xlsx', ...)
    graph = strat_importer.parse()

    # 2. Then import qualia paradata (enriches graph)
    qualia = QualiaImporter(filepath='em_paradata.xlsx', existing_graph=graph)
    graph = qualia.parse()

    # 3. Export to GraphML (PD groups auto-generated from graph structure)
    exporter = GraphMLExporter(graph)
    exporter.export('output.graphml')
"""

import os
import io
import json
import uuid
import platform
import pandas as pd
from pathlib import Path

from ..graph import Graph
from ..nodes.property_node import PropertyNode
from ..nodes.extractor_node import ExtractorNode
from ..nodes.document_node import DocumentNode
from ..nodes.combiner_node import CombinerNode


class QualiaImporter:
    """
    Imports long-format paradata (em_paradata.xlsx) into an existing graph.

    Each row represents ONE property for ONE stratigraphic unit, with its
    extractor text and source document. Supports combiner reasoning for
    multi-source properties.

    Naming convention:
        - Documents: D.01, D.02, ... (global serial, reused if same document)
        - Extractors: D.01.01, D.01.02, ... (serial per document)
        - Combiners: C.01, C.02, ... (global serial)
    """

    def __init__(self, filepath: str, existing_graph: Graph,
                 mapping_name: str = 'em_paradata_mapping',
                 overwrite: bool = False):
        """
        Initialize QualiaImporter.

        Args:
            filepath: Path to em_paradata.xlsx file
            existing_graph: Graph with stratigraphic nodes already loaded (REQUIRED)
            mapping_name: Name of the mapping JSON file (without extension)
            overwrite: If True, update existing properties with new values.
                       If False, skip duplicates with warning. Default: False.

        Raises:
            ValueError: If existing_graph is None
            FileNotFoundError: If filepath doesn't exist
        """
        if existing_graph is None:
            raise ValueError(
                "QualiaImporter requires an existing graph with stratigraphic nodes. "
                "Import stratigraphy first using MappedXLSXImporter."
            )

        self.filepath = filepath
        self.graph = existing_graph
        self.mapping = self._load_mapping(mapping_name)
        self.overwrite = overwrite
        self.warnings = []

        # Naming registries
        self.document_registry = {}    # doc_name → serial number (1, 2, ...)
        self.doc_serial_counter = 1
        self.extractor_counters = {}   # doc_serial → counter for D.XX.YY naming
        self.combiner_counter = 0

        # Overwrite tracking
        self.skipped_duplicates = 0
        self.overwritten_properties = 0

        # Node registries (to avoid duplicates)
        self._document_nodes = {}      # doc_name → DocumentNode

    def _load_mapping(self, mapping_name: str) -> dict:
        """Load mapping JSON from the generic mappings directory."""
        # Try generic mappings directory first
        mappings_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'mappings', 'generic'
        )
        mapping_path = os.path.join(mappings_dir, f'{mapping_name}.json')

        if not os.path.exists(mapping_path):
            # Fallback: try emdb directory
            mappings_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'mappings', 'emdb'
            )
            mapping_path = os.path.join(mappings_dir, f'{mapping_name}.json')

        if not os.path.exists(mapping_path):
            raise FileNotFoundError(
                f"Mapping file not found: {mapping_name}.json\n"
                f"Searched in: {mappings_dir}"
            )

        with open(mapping_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _generate_uuid(self) -> str:
        """Generate a UUID for node/edge IDs."""
        return str(uuid.uuid4())

    def _get_document_serial(self, doc_name: str) -> int:
        """
        Get or create serial number for a document name.
        Reuses serial if same document name already registered.

        Args:
            doc_name: Document filename (e.g., 'field_notes_day5.pdf')

        Returns:
            Serial number (1, 2, 3, ...)
        """
        if doc_name not in self.document_registry:
            self.document_registry[doc_name] = self.doc_serial_counter
            self.doc_serial_counter += 1
        return self.document_registry[doc_name]

    def _get_extractor_serial(self, doc_serial: int) -> int:
        """
        Get next extractor serial for a given document.

        Args:
            doc_serial: Document serial number

        Returns:
            Extractor serial (1, 2, 3, ...)
        """
        if doc_serial not in self.extractor_counters:
            self.extractor_counters[doc_serial] = 0
        self.extractor_counters[doc_serial] += 1
        return self.extractor_counters[doc_serial]

    def _get_next_combiner_serial(self) -> int:
        """Get next combiner serial number."""
        self.combiner_counter += 1
        return self.combiner_counter

    def _format_serial(self, num: int) -> str:
        """Format serial number as zero-padded string (e.g., 1 → '01')."""
        return f"{num:02d}"

    def _get_or_create_document_node(self, doc_name: str) -> DocumentNode:
        """
        Get existing or create new DocumentNode for a document name.
        Reuses nodes if same document appears multiple times.

        Args:
            doc_name: Document filename

        Returns:
            DocumentNode instance
        """
        if doc_name in self._document_nodes:
            return self._document_nodes[doc_name]

        doc_serial = self._get_document_serial(doc_name)
        node_name = f"D.{self._format_serial(doc_serial)}"

        doc_node = DocumentNode(
            node_id=self._generate_uuid(),
            name=node_name,
            description=doc_name  # Store original filename as description
        )

        self.graph.add_node(doc_node)
        self._document_nodes[doc_name] = doc_node
        return doc_node

    def _create_extractor_node(self, doc_serial: int, extractor_text: str) -> ExtractorNode:
        """
        Create a new ExtractorNode with D.XX.YY naming.

        Args:
            doc_serial: Document serial number for naming
            extractor_text: The extracted text/observation

        Returns:
            ExtractorNode instance
        """
        ext_serial = self._get_extractor_serial(doc_serial)
        node_name = f"D.{self._format_serial(doc_serial)}.{self._format_serial(ext_serial)}"

        ext_node = ExtractorNode(
            node_id=self._generate_uuid(),
            name=node_name,
            description=extractor_text
        )

        self.graph.add_node(ext_node)
        return ext_node

    def _create_combiner_node(self, reasoning: str) -> CombinerNode:
        """
        Create a new CombinerNode with C.XX naming.

        Args:
            reasoning: The combiner reasoning text

        Returns:
            CombinerNode instance
        """
        comb_serial = self._get_next_combiner_serial()
        node_name = f"C.{self._format_serial(comb_serial)}"

        comb_node = CombinerNode(
            node_id=self._generate_uuid(),
            name=node_name,
            description=reasoning
        )

        self.graph.add_node(comb_node)
        return comb_node

    def _find_existing_property(self, us_node_id: str, property_type: str):
        """
        Check if a PropertyNode with the same property_type already exists
        for the given stratigraphic node.

        Args:
            us_node_id: ID of the stratigraphic node
            property_type: Property type name to search for

        Returns:
            PropertyNode if found, None otherwise
        """
        existing_props = self.graph.get_property_nodes_for_node(us_node_id)
        for prop in existing_props:
            if prop.name == property_type:
                return prop
        return None

    def _remove_provenance_chain(self, property_node: PropertyNode):
        """
        Remove all has_data_provenance edges from a PropertyNode.

        In overwrite mode, we preserve the has_property edge (US→Property)
        but remove the provenance chain so it can be rebuilt with new data.
        Orphaned nodes (old extractors/documents/combiners) remain in the graph
        but are unreachable from the qualia path and ignored by the exporter.

        Args:
            property_node: The PropertyNode whose provenance chain to remove
        """
        old_edges = [e for e in self.graph.edges
                     if e.edge_source == property_node.node_id
                     and e.edge_type == 'has_data_provenance']
        for old_edge in old_edges:
            self.graph.remove_edge(old_edge.edge_id)

    def _process_single_source_row(self, property_node: PropertyNode,
                                    extractor_text: str, document_name: str):
        """
        Process a single-source row: property → extractor → document.

        Creates:
            - DocumentNode (reused if same doc)
            - ExtractorNode
            - Edge: ExtractorNode → extracted_from → DocumentNode
            - Edge: PropertyNode → has_data_provenance → ExtractorNode

        Args:
            property_node: The PropertyNode for this row
            extractor_text: Extracted text/observation
            document_name: Source document filename
        """
        # Create/get DocumentNode
        doc_node = self._get_or_create_document_node(document_name)
        doc_serial = self.document_registry[document_name]

        # Create ExtractorNode
        ext_node = self._create_extractor_node(doc_serial, extractor_text)

        # Edge: ExtractorNode → extracted_from → DocumentNode
        self.graph.add_edge(
            edge_id=self._generate_uuid(),
            edge_source=ext_node.node_id,
            edge_target=doc_node.node_id,
            edge_type='extracted_from'
        )

        # Edge: PropertyNode → has_data_provenance → ExtractorNode
        self.graph.add_edge(
            edge_id=self._generate_uuid(),
            edge_source=property_node.node_id,
            edge_target=ext_node.node_id,
            edge_type='has_data_provenance'
        )

    def _process_combiner_row(self, property_node: PropertyNode,
                               extractor_text: str, combiner_reasoning: str,
                               combiner_sources: list):
        """
        Process a combiner row: property → combiner → [extractor→document, ...].

        Creates:
            - CombinerNode
            - For each combiner source:
                - DocumentNode (reused if same doc)
                - ExtractorNode (with extractor_text from main EXTRACTOR column)
                - Edge: ExtractorNode → extracted_from → DocumentNode
                - Edge: CombinerNode → combines → ExtractorNode
            - Edge: PropertyNode → has_data_provenance → CombinerNode

        Args:
            property_node: The PropertyNode for this row
            extractor_text: Summary text of the combined reasoning
            combiner_reasoning: Detailed reasoning text
            combiner_sources: List of source document names
        """
        # Create CombinerNode
        comb_node = self._create_combiner_node(combiner_reasoning)

        # Edge: PropertyNode → has_data_provenance → CombinerNode
        self.graph.add_edge(
            edge_id=self._generate_uuid(),
            edge_source=property_node.node_id,
            edge_target=comb_node.node_id,
            edge_type='has_data_provenance'
        )

        # For each combiner source, create extractor→document chain
        for source_doc in combiner_sources:
            if not source_doc or pd.isna(source_doc):
                continue

            source_doc = str(source_doc).strip()
            if not source_doc:
                continue

            # Create/get DocumentNode
            doc_node = self._get_or_create_document_node(source_doc)
            doc_serial = self.document_registry[source_doc]

            # Create ExtractorNode for this source
            # Use a portion of the extractor text + source doc reference
            ext_node = self._create_extractor_node(doc_serial, extractor_text)

            # Edge: ExtractorNode → extracted_from → DocumentNode
            self.graph.add_edge(
                edge_id=self._generate_uuid(),
                edge_source=ext_node.node_id,
                edge_target=doc_node.node_id,
                edge_type='extracted_from'
            )

            # Edge: CombinerNode → combines → ExtractorNode
            self.graph.add_edge(
                edge_id=self._generate_uuid(),
                edge_source=comb_node.node_id,
                edge_target=ext_node.node_id,
                edge_type='combines'
            )

            # Store source reference in CombinerNode
            comb_node.sources.append(ext_node.node_id)

    def parse(self) -> Graph:
        """
        Parse em_paradata.xlsx and enrich the existing graph.

        For each row:
        1. Find the US node by name (US_ID column)
        2. Create PropertyNode with PROPERTY_TYPE and VALUE
        3. Create provenance chain (single-source or combiner)
        4. Connect everything with proper edge types

        Returns:
            The enriched Graph

        Raises:
            FileNotFoundError: If the Excel file doesn't exist
            ValueError: If the file is empty or invalid
        """
        print(f"\n{'='*60}")
        print(f"QualiaImporter: Loading em_paradata from {os.path.basename(self.filepath)}")
        print(f"{'='*60}")

        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Paradata file not found: {self.filepath}")

        # Get settings from mapping
        table_settings = self.mapping.get('table_settings', {})
        sheet_name = table_settings.get('sheet_name', 'Paradata')
        start_row = table_settings.get('start_row', 2)

        # Read Excel file
        file_content = None
        try:
            with open(self.filepath, 'rb') as f:
                file_content = io.BytesIO(f.read())

            with pd.ExcelFile(file_content, engine='openpyxl') as excel_file:
                df = pd.read_excel(
                    excel_file,
                    sheet_name=sheet_name,
                    header=0,
                    na_values=['', 'NA', 'N/A'],
                    keep_default_na=True,
                    dtype=str
                )

            # Skip tutorial/example rows if start_row > 1
            if start_row > 1:
                actual_start_idx = start_row - 2
                df = df.iloc[actual_start_idx:].reset_index(drop=True)

            if df.empty:
                raise ValueError("Paradata file is empty")

            print(f"  Rows loaded: {len(df)}")
            print(f"  Columns: {list(df.columns)}")

        except Exception as e:
            raise ValueError(f"Error reading paradata file: {e}")
        finally:
            if file_content is not None:
                file_content.close()

        # Process each row
        successful = 0
        skipped = 0
        errors = 0
        us_not_found = set()

        for idx, row in df.iterrows():
            try:
                # 1. Get US_ID and find the node
                us_id = row.get('US_ID')
                if pd.isna(us_id) or not str(us_id).strip():
                    skipped += 1
                    continue

                us_id = str(us_id).strip()
                us_node = self.graph.find_node_by_name(us_id)

                if us_node is None:
                    if us_id not in us_not_found:
                        us_not_found.add(us_id)
                        self.warnings.append(f"US '{us_id}' not found in graph — skipping all its properties")
                    skipped += 1
                    continue

                # 2. Get property data
                property_type = row.get('PROPERTY_TYPE')
                value = row.get('VALUE')
                extractor_text = row.get('EXTRACTOR')
                document_name = row.get('DOCUMENT')
                combiner_reasoning = row.get('COMBINER_REASONING')
                combiner_source_1 = row.get('COMBINER_SOURCE_1')
                combiner_source_2 = row.get('COMBINER_SOURCE_2')

                # Validate required fields
                if pd.isna(property_type) or not str(property_type).strip():
                    self.warnings.append(f"Row {idx+1}: Missing PROPERTY_TYPE — skipping")
                    skipped += 1
                    continue

                if pd.isna(value) or not str(value).strip():
                    self.warnings.append(f"Row {idx+1}: Missing VALUE — skipping")
                    skipped += 1
                    continue

                if pd.isna(extractor_text) or not str(extractor_text).strip():
                    self.warnings.append(f"Row {idx+1}: Missing EXTRACTOR — skipping")
                    skipped += 1
                    continue

                property_type = str(property_type).strip()
                value = str(value).strip()
                extractor_text = str(extractor_text).strip()

                # 3. Check for existing property (duplicate detection)
                existing_prop = self._find_existing_property(us_node.node_id, property_type)

                if existing_prop:
                    if self.overwrite:
                        # Overwrite mode: update value and rebuild provenance chain
                        existing_prop.value = value
                        existing_prop.description = value
                        self.overwritten_properties += 1
                        # Remove old provenance edges (preserves has_property US→Prop)
                        self._remove_provenance_chain(existing_prop)
                        prop_node = existing_prop  # Reuse existing node for new chain
                    else:
                        # Skip mode: duplicate found, skip with warning
                        self.skipped_duplicates += 1
                        self.warnings.append(
                            f"Row {idx+1}: '{property_type}' already exists for "
                            f"'{us_id}' — skipped (use overwrite=True to update)"
                        )
                        skipped += 1
                        continue
                else:
                    # No duplicate: create new PropertyNode + has_property edge
                    prop_node = PropertyNode(
                        node_id=self._generate_uuid(),
                        name=property_type,
                        description=value,
                        value=value,
                        property_type=property_type
                    )
                    self.graph.add_node(prop_node)

                    # Edge: US → has_property → PropertyNode
                    self.graph.add_edge(
                        edge_id=self._generate_uuid(),
                        edge_source=us_node.node_id,
                        edge_target=prop_node.node_id,
                        edge_type='has_property'
                    )

                # 5. Create provenance chain
                has_combiner = (
                    not pd.isna(combiner_reasoning) and
                    str(combiner_reasoning).strip()
                )

                if has_combiner:
                    # Multi-source combiner path
                    combiner_sources = []
                    if not pd.isna(combiner_source_1) and str(combiner_source_1).strip():
                        combiner_sources.append(str(combiner_source_1).strip())
                    if not pd.isna(combiner_source_2) and str(combiner_source_2).strip():
                        combiner_sources.append(str(combiner_source_2).strip())

                    if not combiner_sources:
                        self.warnings.append(
                            f"Row {idx+1}: COMBINER_REASONING present but no COMBINER_SOURCE columns — "
                            f"treating as single-source"
                        )
                        # Fallback: treat as single-source if no sources specified
                        if not pd.isna(document_name) and str(document_name).strip():
                            self._process_single_source_row(
                                prop_node, extractor_text, str(document_name).strip()
                            )
                        else:
                            self.warnings.append(
                                f"Row {idx+1}: No DOCUMENT and no COMBINER_SOURCE — "
                                f"property created without provenance"
                            )
                    else:
                        self._process_combiner_row(
                            prop_node, extractor_text,
                            str(combiner_reasoning).strip(),
                            combiner_sources
                        )
                else:
                    # Single-source path
                    if pd.isna(document_name) or not str(document_name).strip():
                        self.warnings.append(
                            f"Row {idx+1}: Missing DOCUMENT for single-source row — "
                            f"property created without provenance"
                        )
                    else:
                        self._process_single_source_row(
                            prop_node, extractor_text, str(document_name).strip()
                        )

                successful += 1

            except Exception as e:
                errors += 1
                self.warnings.append(f"Row {idx+1}: Error — {str(e)}")
                if errors <= 3:
                    print(f"  ❌ Row {idx+1}: {str(e)}")

        # Summary
        print(f"\n  QualiaImporter Summary:")
        print(f"  ✓ Properties created: {successful}")
        if self.overwrite and self.overwritten_properties > 0:
            print(f"  ↻ Properties overwritten: {self.overwritten_properties}")
        if self.skipped_duplicates > 0:
            print(f"  ⊘ Duplicates skipped: {self.skipped_duplicates}")
        print(f"  ⚠ Rows skipped: {skipped}")
        print(f"  ❌ Errors: {errors}")
        print(f"  📄 Documents registered: {len(self.document_registry)}")
        print(f"  🔀 Combiners created: {self.combiner_counter}")
        print(f"  🔧 Mode: {'overwrite' if self.overwrite else 'skip duplicates'}")

        if us_not_found:
            print(f"  ⚠ US not found in graph: {', '.join(sorted(us_not_found))}")

        if self.warnings:
            print(f"\n  Warnings ({len(self.warnings)}):")
            for w in self.warnings[:10]:
                print(f"    - {w}")
            if len(self.warnings) > 10:
                print(f"    ... and {len(self.warnings) - 10} more")

        print(f"{'='*60}\n")

        return self.graph

    def display_warnings(self):
        """Display all warnings collected during import."""
        if self.warnings:
            print(f"\n⚠️ QualiaImporter Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"  - {w}")
