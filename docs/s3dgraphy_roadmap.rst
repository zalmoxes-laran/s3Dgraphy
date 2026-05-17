Development Roadmap
===================

This document outlines the development roadmap for s3dgraphy, the core Python library
that implements the Extended Matrix formal language for archaeological documentation.

Current Version: 0.1.35
------------------------

Completed Features
~~~~~~~~~~~~~~~~~~

- [x] Core graph structure with indexing (``GraphIndices``)
- [x] Node type system with CIDOC-CRM mappings
- [x] Three core JSON configuration files (Visual Rules, CIDOC Mapping, Connection Rules)
- [x] Stratigraphic node subclasses (US, USV, SF, VSF, USD, TSU) and serial variants
- [x] Actor, Link, License, and Embargo nodes
- [x] Document, Extractor, Combiner, Property nodes (paradata chain)
- [x] Representation Model nodes (3D models for US, DOC, SF)
- [x] GraphML import with UUID slipback
- [x] GraphML export with container group support
- [x] Container group nodes (US, USD, VSF) with is_part_of edges
- [x] Instance chains via changed_from edges
- [x] Comment/note node skipping during import
- [x] XLSX import with JSON mapping system
- [x] SQLite/pyArchInit import with JSON mapping
- [x] JSON export for web platforms (Heriverse, ATON)
- [x] Multi-graph management (MultiGraphManager)
- [x] Integration with EM-tools for Blender
- [x] Tag parser for EM canvas integration
- [x] 3D model library (glTF) and 2D icons (PNG)
- [x] Modular architecture
- [x] PyPI package release
- [x] Canonical/reverse edge directionality (v1.5.3)
- [x] has_visual_reference edge type (v1.5.4)
- [x] **Chronology calculation** (``calculate_chronology``): BFS-based TPQ/TAQ propagation from absolute dates and epoch membership through stratigraphic relations
- [x] **Temporal property detection** with fallback matching by name and description
- [x] [v0.1.27-0.1.30] **AI extraction capabilities** and prompt templates
- [x] [v0.1.28] **Qualia Importer** for importing from Qualia templates
- [x] [v0.1.33] **GraphML Patcher** for round-trip editing (patches existing GraphML files with in-memory graph changes, EMID validation)
- [x] [v0.1.33] **Graph Merger** with conflict resolution (compares existing graphs with incoming data, produces conflict lists for UI resolution)
- [x] [v0.1.33] **Master DocumentNode enrichment**
- [x] [v0.1.34] **Epoch/Relations second-pass processing** for enhanced GraphML handling
- [x] [v0.1.35] **Import GraphML updates**

Next Priorities
~~~~~~~~~~~~~~~

- [~] Enhanced validation system (in progress: EMID validation exists)
- [ ] Performance optimizations for very large graphs (10,000+ nodes)
- [ ] Additional CIDOC-CRM mapping refinements
- [ ] Comprehensive unit test coverage
- [ ] Complete API documentation

Future Features
~~~~~~~~~~~~~~~

- [ ] GeoJSON export for GIS integration
- [ ] RDF/TTL export for semantic web (CIDOC-CRM compliance)
- [ ] Neo4j export for graph database integration
- [ ] Command-line interface (CLI)
- [ ] Batch processing capabilities
- [ ] Standalone GUI application

Related Projects
----------------

- `EM-tools for Blender <https://github.com/zalmoxes-laran/EM-blender-tools>`_ - 3D visualization
- `Extended Matrix Documentation <https://github.com/zalmoxes-laran/ExtendedMatrix>`_ - Language reference
- `3D Survey Collection <https://docs.extendedmatrix.org/projects/3DSC/>`_ - 3D model preparation

Current Status
--------------

For the most current development status, see:

- `GitHub Issues <https://github.com/zalmoxes-laran/s3dgraphy/issues>`_
- `Project Milestones <https://github.com/zalmoxes-laran/s3dgraphy/milestones>`_
- `EM-tools Changelog <https://github.com/zalmoxes-laran/EM-blender-tools/blob/main/changelog.md>`_
