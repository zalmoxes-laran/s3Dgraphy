# s3Dgraphy/importer/pyarchinit_importer.py

import re
from typing import Dict, Any, List, Optional, Tuple
from .base_importer import BaseImporter
import sqlite3
import os
from ..graph import Graph
from ..nodes.base_node import Node
from ..nodes.property_node import PropertyNode
from ..nodes.stratigraphic_node import StratigraphicNode
from ..utils.utils import get_stratigraphic_node_class
from ..multigraph.multigraph import multi_graph_manager

# Conservative SQLite identifier whitelist: letters, digits, underscore.
# Used to guard table names and filter column names interpolated into
# query strings (values always go through paramstyle binding).
_SAFE_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# Recognized connection URL prefixes for dialect detection.
_PG_URL_PREFIXES = ("postgresql://", "postgresql+psycopg2://",
                    "postgres://")
_SQLITE_URL_PREFIX = "sqlite:///"


class PyArchInitImporter(BaseImporter):
    def __init__(self, filepath: Optional[str] = None,
                 mapping_name: str = None, overwrite: bool = False,
                 existing_graph=None,
                 filters: Optional[Dict[str, Any]] = None,
                 *,
                 connection_url: Optional[str] = None):
        """
        Initialize pyArchInit importer with mapping configuration.

        Args:
            filepath: Path to a SQLite database (legacy / default path).
                Mutually exclusive with ``connection_url``. When given,
                it is internally promoted to ``sqlite:///<abspath>`` so
                downstream code uses a single URL-based representation.
            mapping_name: Name of the JSON mapping file to use.
            overwrite: If True, overwrites existing nodes.
            existing_graph: Existing graph instance to use.
                If None, creates new unregistered graph with temporary
                ID. The caller (EM-tools) is responsible for setting
                proper graph_id and registering it in
                MultiGraphManager.
            filters: Optional dict of {column_name: value} to restrict
                the imported rows. Combined with AND. Each column is
                whitelisted against the mapping's column_mappings, then
                bound as a parameterized SQL value — safe against
                injection. Placeholder syntax adapts to the dialect
                (``?`` on SQLite, ``%s`` on PostgreSQL).
            connection_url: SQLAlchemy-style connection URL. Mutually
                exclusive with ``filepath``. Supported schemes:
                ``sqlite:///<abspath>``,
                ``postgresql://user:pass@host:port/dbname`` (or the
                ``postgres://`` alias / ``postgresql+psycopg2://`` form).
                For PostgreSQL, ``psycopg2-binary`` must be installed
                (``pip install s3dgraphy[postgres]``); a friendly
                ``ImportError`` fires on first connection attempt if
                it isn't.

        Raises:
            ValueError: If both ``filepath`` and ``connection_url`` are
                given, if neither is given, or if ``connection_url``
                uses an unsupported scheme.
        """
        # Mutually exclusive + at-least-one validation.
        if filepath is not None and connection_url is not None:
            raise ValueError(
                "Pass either filepath= or connection_url=, not both."
            )
        if filepath is None and connection_url is None:
            raise ValueError(
                "Either filepath= or connection_url= is required."
            )

        # Resolve dialect + canonical URL + the path-or-URL string we
        # hand to BaseImporter as `filepath` (diagnostic-friendly).
        if filepath is not None:
            abs_path = os.path.abspath(filepath)
            self._dialect = "sqlite"
            self._connection_url = f"{_SQLITE_URL_PREFIX}{abs_path}"
            _base_filepath = filepath
        else:
            if connection_url.startswith(_PG_URL_PREFIXES):
                self._dialect = "postgres"
            elif connection_url.startswith(_SQLITE_URL_PREFIX):
                self._dialect = "sqlite"
            else:
                raise ValueError(
                    "Unsupported connection_url scheme: "
                    f"{connection_url!r}. "
                    "Use sqlite:///<path>, postgresql://..., "
                    "or postgres://..."
                )
            self._connection_url = connection_url
            # BaseImporter uses filepath for diagnostics + abspath
            # normalization. SQLite URLs reduce to a real path; PG URLs
            # are passed through verbatim.
            if self._dialect == "sqlite":
                _base_filepath = connection_url[
                    len(_SQLITE_URL_PREFIX):
                ]
            else:
                _base_filepath = connection_url

        super().__init__(
            filepath=_base_filepath,
            mapping_name=mapping_name,
            overwrite=overwrite,
            filters=filters,
        )

        if existing_graph:
            # Use provided graph (EM_ADVANCED mode)
            self.graph = existing_graph
            self.graph_id = existing_graph.graph_id
            self._use_existing_graph = True
            # print(f"PyArchInitImporter: Using provided graph '{self.graph_id}'")
        else:
            # Create new UNREGISTERED graph (3DGIS mode)
            # Caller must set proper graph_id and register it
            self.graph = Graph(graph_id="temp_graph")
            self._use_existing_graph = False
            # print(f"PyArchInitImporter: Created new unregistered graph (caller must register)")

        # Structured list of rows whose stratigraphic node name could
        # not be matched in the host graph (only meaningful in
        # enriching mode). Each entry is ``{"key_id": str, "payload":
        # dict}``. Neutral data exposed to any caller; the EMtools
        # Hybrid-C adapter maps it to graph.attributes['aux_orphans'].
        self.orphans = []

        self.validate_mapping()

    # ------------------------------------------------------------------
    # Backend abstraction (#9 multi-backend)
    # ------------------------------------------------------------------
    def _connect(self):
        """Open a DB-API 2 connection for the active dialect.

        Returns a connection that the caller must close. For SQLite,
        uses the stdlib ``sqlite3``. For PostgreSQL, uses
        ``psycopg2`` and raises a friendly ``ImportError`` if the
        extras are missing.
        """
        if self._dialect == "sqlite":
            return sqlite3.connect(self.filepath)
        # PostgreSQL path. Probe psycopg2 lazily so SQLite-only
        # callers never pay the import cost (and don't need the wheel).
        try:
            import psycopg2  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "PostgreSQL backend requires psycopg2-binary. "
                "Install via: pip install s3dgraphy[postgres]"
            ) from e
        import psycopg2
        return psycopg2.connect(self._psycopg2_dsn())

    def _psycopg2_dsn(self) -> str:
        """Normalize the connection URL for ``psycopg2.connect()``.

        ``psycopg2`` doesn't understand SQLAlchemy-style driver
        suffixes (e.g. ``postgresql+psycopg2://``): it parses the
        scheme literally and rejects the ``+psycopg2`` part with
        "invalid dsn". The write side of the bridge
        (``s3dgraphy.sync`` via SQLAlchemy) naturally produces those
        URLs, so a caller wiring the *same* connection string into
        both the read side (here) and the write side would otherwise
        hit a silent failure on the read.

        Stripping the ``+<driver>`` token lets one URL flow into both
        without every caller having to know the dialect-prefix
        convention. ``postgresql+psycopg2://`` → ``postgresql://`` and
        ``postgres+psycopg2://`` → ``postgres://`` — both accepted by
        psycopg2. Plain ``postgresql://`` / ``postgres://`` pass
        through untouched.
        """
        url = self._connection_url
        scheme, sep, rest = url.partition("://")
        if sep and "+" in scheme:
            scheme = scheme.split("+", 1)[0]
            return f"{scheme}://{rest}"
        return url

    def _qmark(self) -> str:
        """Parameter placeholder for the active dialect (``?`` / ``%s``)."""
        return "?" if self._dialect == "sqlite" else "%s"

    def _resolve_node_name(self, row_dict: Dict[str, Any], id_column: str) -> str:
        """Compose the human-readable node name for ``row_dict``.

        When the mapping declares ``table_settings.node_name_template``
        (1.6+), the template is interpreted as a Python str.format-style
        string with ``{column_name}`` placeholders. Each placeholder is
        substituted with the corresponding row value.

        Empty / ``None`` components are **omitted** from the composite
        name and the resulting double-dots are collapsed to single
        dots, with leading/trailing dots stripped — so a template
        ``{area}.{unita_tipo}.{us}`` against a row with
        ``area='A', unita_tipo='', us='101'`` yields ``'A.101'``,
        not ``'A..101'``.

        If no template is declared, fall back to the pre-1.6 behaviour:
        ``str(row_dict[id_column])``.
        """
        template = (
            self.mapping.get('table_settings', {}).get('node_name_template')
        )
        if not template:
            return str(row_dict[id_column])

        def _resolve(match):
            col = match.group(1)
            value = row_dict.get(col)
            if value is None:
                return ''
            text = str(value).strip()
            return text  # may be '' — collapsed below

        composed = re.sub(r"\{(\w+)\}", _resolve, template)
        # Collapse runs of separator dots created by empty components,
        # then strip leading/trailing dots.
        composed = re.sub(r"\.{2,}", ".", composed)
        composed = composed.strip(".")
        # If every component was empty, fall back to the bare id value
        # (defensive — better an ambiguous bare-id node than an empty
        # name that would silently collide across rows).
        if not composed:
            return str(row_dict[id_column])
        return composed

    def process_row(self, row_dict: Dict[str, Any]) -> Optional[Node]:
        """Process a row from pyArchInit database"""
        try:
            # 1️⃣ Get ID column and convert if numeric
            id_column = self._get_id_column()
            if isinstance(row_dict.get(id_column), (int, float)):
                row_dict[id_column] = str(row_dict[id_column])

            # Compose node name: honor table_settings.node_name_template
            # (1.6+) when present, otherwise fall back to the bare id
            # value. Empty / None components are omitted from the
            # composite name.
            node_name = self._resolve_node_name(row_dict, id_column)
            
            # print(f"\n=== Processing pyArchInit row ===")
            # print(f"Node name from DB: {node_name}")
            
            # 2️⃣ Check if we're enriching existing graph
            is_enriching_existing = self._use_existing_graph and len(self.graph.nodes) > 0
            # print(f"Enriching existing graph: {is_enriching_existing}")
            
            # 3️⃣ Try to find existing node by NAME (not ID!)
            existing_node = self._find_node_by_name(node_name)
            
            if existing_node:
                # ✅ Node found in existing graph: only add properties
                # print(f"✓ Found existing node: {existing_node.name} (ID: {existing_node.node_id})")
                # print(f"  → Adding properties to existing node")
                
                # Get description from mapping
                desc_column = self._get_description_column()
                description = row_dict.get(desc_column) if desc_column else None
                
                # Update description if overwrite is enabled
                if self.overwrite and description:
                    existing_node.description = str(description)
                
                # Process properties for existing node
                self._process_pyarchinit_properties(row_dict, existing_node)
                return existing_node
                
            elif is_enriching_existing:
                # ❌ Enriching mode but node not found → SKIP this row
                warning_msg = f"Node '{node_name}' not found in existing graph - SKIPPED"
                self.warnings.append(warning_msg)
                # Record the orphan as neutral data. The EMtools
                # Hybrid-C adapter promotes these into
                # graph.attributes['aux_orphans']; other consumers
                # (CLI, headless viewers) can inspect self.orphans
                # directly.
                self.orphans.append({
                    "key_id": node_name,
                    "payload": {"source": "pyarchinit",
                                "row": dict(row_dict)},
                })
                return None
                
            else:
                # ✅ Creating new graph → create new stratigraphic node
                # print(f"✓ Creating new stratigraphic node: {node_name}")
                
                # Get description from mapping
                desc_column = self._get_description_column()
                description = row_dict.get(desc_column) if desc_column else "pyarchinit element"
                
                # Get node type from id column mapping
                id_col_config = self.mapping['column_mappings'][id_column]
                strat_type = id_col_config.get('node_type', 'US')
                node_class = get_stratigraphic_node_class(strat_type)
                
                # Create new node with UUID
                import uuid
                new_node = node_class(
                    node_id=str(uuid.uuid4()),
                    name=node_name,
                    description=str(description)
                )
                
                self.graph.add_node(new_node)
                # print(f"  → Node created with ID: {new_node.node_id}")

                # Process properties for new node
                self._process_pyarchinit_properties(row_dict, new_node)
                return new_node

        except KeyError as e:
            self.warnings.append(f"Missing required column: {str(e)}")
            raise

    def _process_pyarchinit_properties(self, row_dict: Dict[str, Any], strat_node: Node):
        """
        Process property columns for a stratigraphic node.
        Only creates properties if they have non-empty values.
        """
        # print(f"\n  Processing properties for node: {strat_node.name}")
        
        for col_name, col_config in self.mapping.get('column_mappings', {}).items():
            # Skip ID and description columns
            if col_config.get('is_id', False) or col_config.get('is_description', False):
                continue
                
            if col_config.get('property_name'):
                value = row_dict.get(col_name, '')
                
                # ✅ IMPORTANTE: Crea proprietà SOLO se valore esiste e non è vuoto
                if value and str(value).strip():
                    property_id = f"{strat_node.node_id}_{col_config['property_name']}"
                    
                    # Check if property already exists
                    existing_prop = self.graph.find_node_by_id(property_id)
                    
                    if existing_prop:
                        # Update existing property if overwrite enabled
                        if self.overwrite:
                            existing_prop.value = str(value)
                            existing_prop.description = str(value)
                            # print(f"    ↻ Updated property: {col_config['property_name']} = '{value}'")
                    else:
                        # Create new property node
                        property_node = PropertyNode(
                            node_id=property_id,
                            name=col_config['property_name'],
                            description=str(value),
                            value=str(value),
                            property_type=col_config['property_name']
                        )
                        self.graph.add_node(property_node)
                        # print(f"    + Created property: {col_config['property_name']} = '{value}'")

                        # Create edge between stratigraphic node and property
                        edge_id = f"{strat_node.node_id}_has_property_{property_id}"
                        if not self.graph.find_edge_by_id(edge_id):
                            self.graph.add_edge(
                                edge_id=edge_id,
                                edge_source=strat_node.node_id,
                                edge_target=property_id,
                                edge_type="has_property"
                            )
                else:
                    pass
                    # Valore vuoto o mancante - non creare proprietà
                    # print(f"    ⊘ Skipped property: {col_config['property_name']} (empty value)")

    def _get_description_column(self) -> Optional[str]:
        """Get description column from mapping"""
        for col_name, col_config in self.mapping.get('column_mappings', {}).items():
            if col_config.get('is_description', False):
                return col_name
        return None

    @staticmethod
    def _is_safe_identifier(name: str) -> bool:
        """Whitelist check for a SQL identifier (table or column name).

        We refuse anything that isn't a plain ``[A-Za-z_][A-Za-z0-9_]*``
        token. SQLite's ? placeholders only bind *values*, not
        identifiers, so any identifier we interpolate into a query
        string must be vetted here first.
        """
        return bool(name) and _SAFE_IDENT_RE.match(name) is not None

    def _get_table_name(self) -> str:
        """Return the SQLite table name from the mapping's table_settings."""
        table_settings = self.mapping.get('table_settings', {})
        table_name = table_settings.get('table_name')
        if not table_name:
            raise ValueError("Table name not specified in mapping configuration")
        if not self._is_safe_identifier(table_name):
            raise ValueError(f"Unsafe table_name in mapping: {table_name!r}")
        return table_name

    def _build_select_query(self, table_name: str) -> Tuple[str, List[Any]]:
        """Build the ``SELECT * FROM ...`` query with optional WHERE.

        Filter columns are whitelisted against ``column_mappings`` (so a
        caller can't slip an arbitrary column name into the SQL) and
        against the static identifier whitelist; filter *values* go
        through ? parameter binding.

        Returns:
            (query_string, params_list) ready for ``cursor.execute``.
        """
        if not self.filters:
            return f"SELECT * FROM {table_name}", []

        where_fragments = []
        params: List[Any] = []
        qmark = self._qmark()
        for col, value in self.filters.items():
            # Defense in depth: validate against mapping + ident regex.
            self._validate_filter_column(col)
            if not self._is_safe_identifier(col):
                raise ValueError(f"Unsafe filter column name: {col!r}")
            where_fragments.append(f"{col} = {qmark}")
            params.append(value)

        where_clause = " AND ".join(where_fragments)
        return f"SELECT * FROM {table_name} WHERE {where_clause}", params

    def get_distinct_values(self, column: str) -> List[Any]:
        """Return sorted distinct non-null values for ``column``.

        Issues ``SELECT DISTINCT {column} FROM {table} ORDER BY {column}``
        on the configured table. The column name is whitelisted against
        the mapping's ``column_mappings`` before being interpolated.

        Args:
            column: Column to enumerate. Must appear in the mapping.

        Returns:
            Sorted list of distinct values (NULLs excluded).
        """
        self._validate_filter_column(column)
        if not self._is_safe_identifier(column):
            raise ValueError(f"Unsafe column name: {column!r}")
        table_name = self._get_table_name()

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT DISTINCT {column} FROM {table_name} "
                f"WHERE {column} IS NOT NULL ORDER BY {column}"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def parse(self) -> Graph:
        """Parse pyArchInit database using mapping configuration"""
        try:
            # print("\n=== Starting PyArchInit Import ===")
            conn = self._connect()
            cursor = conn.cursor()
            
            # Debug del mapping
            # print(f"\nMapping configuration:")
            # print(f"Filepath: {self.filepath}")
            # print(f"Table settings: {self.mapping.get('table_settings', {})}")
            # print(f"Column mappings: {self.mapping.get('column_mappings', {})}")
            
            # Get table name from mapping
            table_settings = self.mapping.get('table_settings', {})
            table_name = table_settings.get('table_name')
            
            if not table_name:
                raise ValueError("Table name not specified in mapping configuration")
            
            # print(f"\nReading from table: {table_name}")

            # Validate table_name against the mapping: it comes from the
            # JSON, not from the user, but we still refuse anything that
            # looks like it could break out of an identifier (defense in
            # depth — the JSON itself could be user-supplied).
            if not self._is_safe_identifier(table_name):
                raise ValueError(
                    f"Unsafe table_name in mapping: {table_name!r}"
                )

            # Build SELECT with optional WHERE clause for filters. Column
            # names are whitelisted via the mapping; values go through ?
            # parameter binding (no string interpolation of user data).
            query, params = self._build_select_query(table_name)
            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            # print(f"Columns found: {columns}")
            
            rows = cursor.fetchall()
            # print(f"Total rows to process: {len(rows)}")
            
            successful_rows = 0
            skipped_rows = 0
            error_rows = 0
            
            # Process each row
            for idx, row in enumerate(rows, 1):
                try:
                    # Convert row to dictionary
                    row_dict = dict(zip(columns, row))
                    
                    # Process the row
                    result = self.process_row(row_dict)
                    
                    if result is not None:
                        successful_rows += 1
                        if (successful_rows % 10) == 0:
                            pass
                            # print(f"Processed {successful_rows} rows...")
                    else:
                        skipped_rows += 1
                        
                except Exception as e:
                    error_rows += 1
                    error_msg = f"Error processing row {idx}: {str(e)}"
                    self.warnings.append(error_msg)
                    # print(f"❌ {error_msg}")
            
            conn.close()
            
            # Summary
            # print(f"\n=== Import Summary ===")
            # print(f"Total rows: {len(rows)}")
            # print(f"✓ Successfully imported: {successful_rows}")
            # print(f"⊘ Skipped: {skipped_rows}")
            # print(f"✗ Errors: {error_rows}")
            # print(f"Final graph size: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
            
            # Add to warnings for UI
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Successfully imported: {successful_rows}/{len(rows)}")
            if skipped_rows > 0:
                self.warnings.append(f"Skipped rows (not in graph): {skipped_rows}")
            if error_rows > 0:
                self.warnings.append(f"Errors: {error_rows}")
            
            return self.graph
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ImportError(f"Error parsing pyArchInit database: {str(e)}")
