Changelog
=========

All notable changes to s3dgraphy will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

.. note::
   s3dgraphy is currently developed within EM-tools but will become a standalone 
   library. This changelog tracks s3dgraphy-specific developments.

[Unreleased]
------------

Core Library Development
~~~~~~~~~~~~~~~~~~~~~~~~

Added
^^^^^
- Three core JSON configuration files (Visual Rules, CIDOC Mapping, Connection Rules)
- Stratigraphic node subclasses implementation
- Actor and Link nodes support
- Representation Model node functionality
- GraphML import compatibility layer
- Tag parser for EM canvas integration
- 3D model library (GLTF) and 2D icons (PNG) support
- Modular architecture revision
- Information propagation algorithm (v1)
- Color schema migration from EM-tools

Changed
^^^^^^^
- Migrated core graph functionality from EM-tools codebase
- Restructured node type hierarchy for better extensibility
- Improved JSON configuration management

[0.1.0] - Development Version
-----------------------------

Initial Development
~~~~~~~~~~~~~~~~~~~

Added
^^^^^
- Basic graph structure implementation
- Node and edge management system
- JSON import/export functionality
- Integration hooks for Blender (via EM-tools)
- Core stratigraphic modeling capabilities
- Document and paradata node support

Technical Infrastructure
~~~~~~~~~~~~~~~~~~~~~~~~

Added
^^^^^
- Python package structure
- Basic unit testing framework
- Documentation structure with Sphinx
- CI/CD pipeline preparation

Planned for v1.0
----------------

Library Completion
~~~~~~~~~~~~~~~~~~

- [ ] ParadataGroup node handling for stratigraphic units
- [ ] Preset qualia vocabulary implementation  
- [ ] Complete CIDOC-CRM mapping validation
- [ ] Enhanced GraphML import/export
- [ ] Comprehensive unit test coverage
- [ ] API documentation completion
- [ ] Performance optimization
- [ ] Memory usage optimization

Standalone Features
~~~~~~~~~~~~~~~~~~~

- [ ] Independent installation via PyPI
- [ ] Command-line interface (CLI)
- [ ] Batch processing capabilities
- [ ] Integration examples for other platforms (Unity, Unreal, etc.)

Documentation
~~~~~~~~~~~~~

- [ ] Complete user guide
- [ ] API reference documentation
- [ ] Tutorial series
- [ ] Integration examples
- [ ] Performance benchmarking

Version History Context
-----------------------

s3dgraphy represents the core graph library that powers the Extended Matrix Framework. 
It evolved from the graph management components of EM-tools and is being developed 
as a standalone Python library to enable Extended Matrix functionality across 
multiple platforms and applications.

The library implements the formal Extended Matrix language for archaeological 
stratigraphic documentation and virtual reconstruction processes, providing a 
robust foundation for scientific 3D heritage documentation workflows.

Related Projects
----------------

- `EM-tools for Blender <https://github.com/zalmoxes-laran/EM-blender-tools>`_ - 3D visualization and annotation
- `Extended Matrix Documentation <https://github.com/zalmoxes-laran/ExtendedMatrix>`_ - Formal language reference
- `Extended Matrix Framework <https://www.extendedmatrix.org>`_ - Complete ecosystem

Links
-----

[Unreleased]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zalmoxes-laran/s3dgraphy/releases/tag/v0.1.0