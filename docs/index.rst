s3dgraphy Documentation
========================

.. image:: https://img.shields.io/badge/version-0.1.13-blue.svg
   :target: https://pypi.org/project/s3dgraphy/
   :alt: Version

.. image:: https://img.shields.io/badge/python-3.8+-brightgreen.svg
   :target: https://python.org
   :alt: Python

.. image:: https://img.shields.io/badge/license-GPL--3.0-orange.svg
   :target: https://github.com/zalmoxes-laran/s3dgraphy/blob/main/LICENSE
   :alt: License

**s3dgraphy** is a Python library that implements the Extended Matrix formal language 
for archaeological stratigraphic documentation and virtual reconstruction processes. 
It provides the core graph structure and node management system that powers the 
Extended Matrix Framework (EMF).

🎯 What is s3dgraphy?
---------------------

s3dgraphy is the **core graph library** for Extended Matrix, providing:

- **Graph data structures** for archaeological documentation
- **Node and edge types** specific to stratigraphy and paradata
- **Import capabilities** from GraphML, XLSX, and SQLite databases
- **Export to JSON** for web visualization platforms
- **CIDOC-CRM mappings** for semantic interoperability
- **Integration with EM-tools** for Blender 3D visualization

Key Features
------------

🔗 **Graph-Based Architecture**
   Native support for complex archaeological relationships and temporal sequences

📊 **Stratigraphic Modeling**
   Specialized node types for stratigraphic units, documentation, and interpretation:
   
   - Physical units (US, SF, USD)
   - Virtual reconstructions (USV, VSF)
   - Documentation (DOC)
   - Paradata chains (EXT, COMB, PROP)

🔄 **Format Interoperability**
   Import from multiple formats:
   
   - **GraphML** - Primary format for Extended Matrix graphs
   - **XLSX** - Excel files with JSON mapping configurations
   - **SQLite** - pyArchInit database support

📤 **Export to JSON**
   Export graphs to JSON for web platforms (Heriverse, ATON)

🏛️ **Archaeological Standards**
   Built-in support for CIDOC-CRM mapping with extensions:
   
   - CIDOC-CRM (core)
   - CRMarchaeo (archaeological)
   - CRMdig (digital provenance)
   - CRMgeo (geographic)
   - CRMinf (argumentation)
   - CIDOC-S3D (Extended Matrix custom)

⚡ **Performance Optimized**
   Graph indexing system for efficient queries on large datasets

🔄 **Blender Integration**
   Direct integration with EM-tools for 3D archaeological visualization

📖 **Comprehensive Documentation**
   Detailed guides, tutorials, and API reference

Quick Start
-----------

Installation
~~~~~~~~~~~~

Install s3dgraphy using pip:

.. code-block:: bash

   pip install s3dgraphy

Or from source:

.. code-block:: bash

   git clone https://github.com/zalmoxes-laran/s3dgraphy.git
   cd s3dgraphy
   pip install -e .

Basic Usage
~~~~~~~~~~~

Create and populate a graph:

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes import StratigraphicNode, DocumentNode
   
   # Create a new graph
   graph = Graph("pompeii_house_vii")
   
   # Add a stratigraphic unit
   us001 = StratigraphicNode("US001", node_type="US")
   us001.name = "US001"
   us001.description = "Mosaic floor, main atrium"
   us001.set_attribute("material", "tesserae")
   us001.set_attribute("dating", "1st century CE")
   graph.add_node(us001)
   
   # Add documentation
   doc001 = DocumentNode("DOC001")
   doc001.name = "DOC001"
   doc001.description = "Floor photograph"
   doc001.set_attribute("type", "photograph")
   graph.add_node(doc001)
   
   # Create relationship
   graph.add_edge("edge_001", "US001", "DOC001", "has_documentation")
   
   print(f"Graph contains {len(graph.nodes)} nodes and {len(graph.edges)} edges")

Import from GraphML
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.importer import GraphMLImporter
   from s3dgraphy import Graph
   
   # Create graph
   graph = Graph("my_excavation")
   
   # Import GraphML file
   importer = GraphMLImporter("excavation_data.graphml")
   graph = importer.parse()
   
   print(f"Imported {len(graph.nodes)} nodes")
   
   # Check for warnings
   if graph.warnings:
       print("Import warnings:")
       for warning in graph.warnings:
           print(f"  - {warning}")

Export to JSON
~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporter import JSONExporter
   
   # Create exporter
   exporter = JSONExporter("output/project.json")
   
   # Export all graphs
   exporter.export_graphs()
   
   print("Export completed")

Import from XLSX
~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.importer import MappedXLSXImporter
   from s3dgraphy import Graph
   
   # Create graph
   graph = Graph("xlsx_import")
   
   # Import with predefined mapping
   importer = MappedXLSXImporter(
       filepath="stratigraphic_units.xlsx",
       mapping_name="emdb_basic",
       graph=graph
   )
   
   graph = importer.parse()
   print(f"Imported {len(graph.nodes)} nodes from XLSX")

Architecture Overview
---------------------

Core Components
~~~~~~~~~~~~~~~

**Graph Class**
   Central container managing nodes and edges with indexing for performance

**Node Types**
   Specialized classes for different archaeological entities:
   
   - StratigraphicNode (US, USV, SF, VSF, USD)
   - ParadataNode (DOC, EXT, COMB, PROP)
   - GroupNode (Paradata groups, time branches, activities)
   - RepresentationModelNode (3D models)
   - ReferenceNode (GEO, LINK, EP, AUTH)

**Edge Types**
   Defined relationships with CIDOC-CRM mappings:

   - Temporal (is_after, is_before, has_same_time, changed_from)
   - Physical (abuts, fills, cuts, covers, rests_on)
   - Documentation (has_documentation, extracted_from)
   - Properties (has_property)
   - Paradata (has_paradata_nodegroup)
   - Epochs (has_first_epoch, survive_in_epoch)

**Import System**
   Modular importers for GraphML, XLSX, SQLite with JSON mapping support

**Export System**
   JSON exporter for web visualization platforms

**Multi-Graph Manager**
   Manage multiple graphs within a single project

JSON Configuration Files
~~~~~~~~~~~~~~~~~~~~~~~~~

s3dgraphy uses three core JSON configuration files:

1. **s3Dgraphy_node_datamodel.json** (v1.5.2)
   
   - Defines all node types and properties
   - CIDOC-CRM mappings for each node type
   - Node hierarchy and inheritance

2. **s3Dgraphy_connections_datamodel.json** (v1.5.2)
   
   - Defines all edge types
   - CIDOC-CRM mappings for relationships
   - Allowed source/target node combinations

3. **em_visual_rules.json**
   
   - Visual representation rules for Blender
   - 3D models, 2D icons, colors, styles

See :doc:`s3dgraphy_json_config` for detailed documentation.

Use Cases
---------

Archaeological Documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create comprehensive stratigraphic documentation:

.. code-block:: python

   # Document stratigraphic sequence
   graph = Graph("excavation_area_a")
   
   # Add units
   wall = StratigraphicNode("US001", node_type="US")
   wall.description = "Stone wall foundation"
   
   floor = StratigraphicNode("US002", node_type="US")
   floor.description = "Mosaic floor"

   # Add temporal relationship (canonical direction: recent → ancient)
   graph.add_node(wall)
   graph.add_node(floor)
   graph.add_edge("e1", "US002", "US001", "is_after")  # floor is after (more recent than) wall

Virtual Reconstruction
~~~~~~~~~~~~~~~~~~~~~~

Document 3D reconstruction processes:

.. code-block:: python

   # Virtual unit
   usv = StratigraphicNode("USV001", node_type="USVs")
   usv.description = "Reconstructed upper wall"
   
   # Link to documentation
   doc = DocumentNode("DOC001")
   doc.description = "Archaeological parallels"
   
   # Extraction process
   ext = ExtractorNode("EXT001")
   ext.source = "Comparative analysis"
   
   graph.add_node(usv)
   graph.add_node(doc)
   graph.add_node(ext)
   
   # Create paradata chain
   graph.add_edge("e1", "EXT001", "DOC001", "extracted_from")
   graph.add_edge("e2", "USV001", "EXT001", "has_paradata_nodegroup")

Data Integration
~~~~~~~~~~~~~~~~

Import from multiple sources:

.. code-block:: python

   # Import GraphML base structure
   importer1 = GraphMLImporter("base_stratigraphy.graphml")
   graph = importer1.parse()
   
   # Add data from Excel
   importer2 = MappedXLSXImporter(
       filepath="additional_data.xlsx",
       mapping_name="emdb_basic",
       graph=graph
   )
   graph = importer2.parse()
   
   # Export combined data
   from s3dgraphy.exporter import export_to_json
   export_to_json("combined_data.json", [graph.graph_id])

Extended Matrix Ecosystem
--------------------------

s3dgraphy is part of the broader Extended Matrix Framework:

**EM-tools for Blender**
   3D visualization and annotation using s3dgraphy as core library

**Extended Matrix Documentation**
   Formal language reference and tutorials

**3D Survey Collection (3DSC)**
   High-quality 3D model preparation

**ATON 3 Framework**
   Web-based archaeological visualization

**Heriverse Platform**
   Virtual heritage experiences and visualization

Repository and Resources
------------------------

**GitHub Repository**
   https://github.com/zalmoxes-laran/s3dgraphy

**PyPI Package**
   https://pypi.org/project/s3dgraphy/

**EM-tools for Blender**
   https://github.com/zalmoxes-laran/EM-blender-tools

**Extended Matrix Project**
   https://www.extendedmatrix.org

**Issue Tracker**
   https://github.com/zalmoxes-laran/s3dgraphy/issues

Community & Support
-------------------

**Telegram Group**
   https://t.me/UserGroupEM

**Facebook Group**
   https://www.facebook.com/groups/extendedmatrix

**Email Contact**
   emanuel.demetrescu@cnr.it

Current Status
--------------

**Version**: 0.1.13

**Status**: Active development

**Python**: 3.8+

**License**: GPL-3.0

Roadmap
-------

Completed Features
~~~~~~~~~~~~~~~~~~

✅ Core graph structure with indexing
✅ Node type system with CIDOC-CRM mappings
✅ GraphML import
✅ XLSX import with mapping system
✅ SQLite/pyArchInit import
✅ JSON export
✅ Multi-graph management
✅ Integration with EM-tools for Blender

Planned Features
~~~~~~~~~~~~~~~~

**Near-term** (next releases):

- GraphML export functionality
- Enhanced validation system
- Performance optimizations for very large graphs
- Additional CIDOC-CRM mapping refinements

**Long-term**:

- GeoJSON export for GIS integration
- RDF/TTL export for semantic web
- Neo4j export for graph databases
- Command-line interface (CLI)
- Standalone GUI application

Table of Contents
=================

.. toctree::
   :maxdepth: 2
   :caption: Getting Started
   
   installation
   quickstart
   core_concepts

.. toctree::
   :maxdepth: 2
   :caption: User Guide
   
   s3dgraphy_import_export
   s3dgraphy_mapping_system
   s3dgraphy_json_config
   s3dgraphy_integration_emtools
   graph_management
   node_types

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   
   api/graph
   api/nodes
   api/edges
   api/importers
   api/exporters
   api/s3dgraphy_classes_reference
   api/s3dgraphy_edges_reference

.. toctree::
   :maxdepth: 2
   :caption: Examples & Workflows
   
   examples/basic_usage
   examples/archaeological_workflow
   examples/blender_integration
   examples/data_migration

.. toctree::
   :maxdepth: 2
   :caption: Development
   
   contributing
   architecture
   changelog
   roadmap

.. toctree::
   :maxdepth: 1
   :caption: Support
   
   troubleshooting
   faq

Citation
--------

If you use s3dgraphy in your research, please cite:

.. code-block:: bibtex

   @software{s3dgraphy,
     title = {s3dgraphy: Core Graph Library for Extended Matrix},
     author = {Demetrescu, Emanuel},
     year = {2024},
     url = {https://github.com/zalmoxes-laran/s3dgraphy},
     version = {0.1.13}
   }

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
