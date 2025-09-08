Development Roadmap
===================

This document outlines the development roadmap for s3dgraphy, the core Python library 
that implements the Extended Matrix formal language for archaeological documentation.

.. note::
   s3dgraphy is currently developed within EM-tools but is being extracted as a 
   standalone library.

Version 1.0 (Q2 2025) - Standalone Library Release
---------------------------------------------------

✅ **Completed Features**

- [x] Three core JSON files (Visual Rules, CIDOC Mapping, Connection Rules)
- [x] Stratigraphic node subclasses (US, USV, SF, etc.)
- [x] Actor and Link nodes implementation
- [x] Document and Extractor node support
- [x] Representation Model nodes
- [x] GraphML import compatibility
- [x] Tag parser for EM canvas integration
- [x] 3D model library (GLTF) and 2D icons (PNG)
- [x] Modular architecture revision
- [x] Information propagation algorithm (v1)
- [x] Color schema migration from EM-tools

📋 **Planned for v1.0**

- [ ] ParadataGroup node handling for stratigraphic units
- [ ] Preset qualia vocabulary implementation
- [ ] Complete CIDOC-CRM mapping validation
- [ ] Enhanced GraphML import/export
- [ ] Comprehensive unit test coverage
- [ ] API documentation completion
- [ ] PyPI package release

Version 1.1 (Q3 2025) - Enhanced Functionality
-----------------------------------------------

- [ ] Command-line interface (CLI)
- [ ] Batch processing capabilities
- [ ] Performance optimization for large graphs
- [ ] Basic visualization utilities
- [ ] Database integration (PostgreSQL, Neo4j, SQLite)

Version 1.2 (Q4 2025) - Ecosystem Integration
----------------------------------------------

- [ ] Seamless EMtools integration
- [ ] 3DSC workflow support
- [ ] ATON 3 framework integration
- [ ] Heriverse platform compatibility
- [ ] Unity/Unreal integration examples

Version 2.0 (2026) - Advanced Features
---------------------------------------

- [ ] Enhanced temporal modeling
- [ ] Multi-user collaboration
- [ ] Advanced analytics tools
- [ ] Graph neural networks integration
- [ ] Full Linked Data support

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