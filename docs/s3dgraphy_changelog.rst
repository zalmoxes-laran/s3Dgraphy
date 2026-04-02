Changelog
=========

All notable changes to s3dgraphy will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

[0.1.31] - 2025
----------------

Added
^^^^^
- **GraphML export** with full round-trip support (``GraphMLExporter``)
- **Container group nodes**: US (``#9B3333``), USD (``#D86400``), VSF (``#B19F61``) as group nodes in GraphML, converted to regular nodes with ``is_part_of`` edges on import
- **VirtualSpecialFindUnit as container**: VSF can now contain SF elements via ``is_part_of``
- **Instance chains**: ``changed_from`` edges link the same object across epochs; BFS traversal identifies connected components
- **Comment node skipping**: yEd annotation nodes with yellow fill (``#FFCC00``, ``#FFFF00``, ``#FFFF99``) are skipped during import
- **has_visual_reference** edge type (connections datamodel v1.5.4)
- Canonical/reverse edge directionality pattern (connections datamodel v1.5.3)
- GraphML export of container group nodes with correct background colours
- GraphML export of epoch swimlanes, activity groups, and paradata groups

Changed
^^^^^^^
- Connections datamodel updated to v1.5.4
- ``is_part_of`` allowed targets now include ``VirtualSpecialFindUnit``
- Improved duplicate EMID detection during GraphML import

[0.1.13] - 2024
----------------

Added
^^^^^
- XLSX import with JSON mapping system (``MappedXLSXImporter``)
- SQLite/pyArchInit import with JSON mapping
- Graph indexing system (``GraphIndices``) for O(1) lookups
- UUID slipback mechanism for GraphML round-trip editing
- Multi-graph management (``MultiGraphManager``)
- Three core JSON configuration files (Visual Rules, CIDOC Mapping, Connection Rules)
- Stratigraphic node subclasses (US, USV, SF, VSF, USD)
- Paradata chain nodes (DOC, EXT, COMB, PROP)
- Representation Model nodes
- Actor, Link, License, Embargo nodes
- Tag parser for EM canvas integration
- 3D model library (glTF) and 2D icons (PNG)

Changed
^^^^^^^
- Modular architecture revision from EM-tools codebase
- Node type hierarchy restructured for extensibility

[0.1.0] - Initial Development
------------------------------

Added
^^^^^
- Basic graph structure implementation
- Node and edge management system
- JSON export functionality
- Integration hooks for Blender (via EM-tools)
- Core stratigraphic modeling capabilities
- Document and paradata node support
- Python package structure
- Documentation structure with Sphinx

Version History Context
-----------------------

s3dgraphy represents the core graph library that powers the Extended Matrix Framework.
It evolved from the graph management components of EM-tools and is developed
as a standalone Python library to enable Extended Matrix functionality across
multiple platforms and applications.

Links
-----

| [0.1.31]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.13...v0.1.31
| [0.1.13]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.0...v0.1.13
| [0.1.0]: https://github.com/zalmoxes-laran/s3dgraphy/releases/tag/v0.1.0
