s3dgraphy Documentation
========================

.. image:: https://img.shields.io/badge/version-0.1.0-blue.svg
   :target: https://pypi.org/project/s3dgraphy/
   :alt: Version

.. image:: https://img.shields.io/badge/python-3.8+-brightgreen.svg
   :target: https://python.org
   :alt: Python

.. image:: https://img.shields.io/badge/license-GPL--3.0-orange.svg
   :target: https://github.com/zalmoxes-laran/s3dgraphy/blob/main/LICENSE
   :alt: License

**s3dgraphy** is a powerful Python library for managing 3D stratigraphic graphs in archaeological and heritage applications. It provides a comprehensive framework for modeling archaeological layers, their relationships, and integration with 3D visualization tools like Blender.

🏛️ **Archaeological Focus**
   Built specifically for archaeological stratigraphy and Extended Matrix methodology

📊 **Graph Management** 
   Sophisticated tools for creating and managing complex stratigraphic relationships

🎯 **3D Integration**
   Seamless integration with Blender and 3D modeling workflows

📋 **Standards Compliant**
   Full CIDOC-CRM mapping for archaeological data interoperability

Quick Start
-----------

Install s3dgraphy:

.. code-block:: bash

   pip install s3dgraphy

Create your first stratigraphic graph:

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

   # Create a new graph
   graph = Graph("my_site")

   # Add stratigraphic units
   layer1 = StratigraphicUnit("US001", "Surface layer", "US")
   layer2 = StratigraphicUnit("US002", "Medieval layer", "US") 
   layer3 = StratigraphicUnit("US003", "Roman foundation", "US")

   graph.add_node(layer1)
   graph.add_node(layer2)
   graph.add_node(layer3)

   # Add temporal relationships
   graph.add_edge("rel1", "US002", "US001", "is_before")
   graph.add_edge("rel2", "US003", "US002", "is_before")

   print(f"Graph has {len(graph.nodes)} nodes and {len(graph.edges)} edges")

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   introduction
   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   tutorials/basic_usage
   tutorials/archaeological_workflow
   tutorials/blender_integration
   guides/node_types
   guides/cidoc_mapping
   guides/export_formats

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/stratigraphic_analysis
   examples/3d_visualization
   examples/data_export

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/core
   api/nodes
   api/edges
   api/utils
   api/blender

.. toctree::
   :maxdepth: 1
   :caption: Development

   contributing
   changelog
   roadmap

.. toctree::
   :maxdepth: 1
   :caption: About

   license
   contact
   citing

Key Features
------------

🔗 **Comprehensive Node Types**
   Support for all stratigraphic unit types: US, USV, SF, VSF, series, and more

⚡ **Fast Performance**
   Optimized for large archaeological datasets with thousands of relationships

🛠️ **Extensible Architecture**
   Easy to extend with custom node types and relationship definitions

📤 **Multiple Export Formats**
   Export to GraphML, JSON, and standards-compliant formats

🔄 **Blender Integration**
   Direct integration with EMtools for 3D archaeological visualization

📖 **Rich Documentation**
   Comprehensive guides, tutorials, and API reference

Archaeological Applications
---------------------------

s3dgraphy is particularly suited for:

* **Stratigraphic Analysis**: Model archaeological layers and their temporal relationships
* **Site Documentation**: Create structured records of excavation data
* **3D Visualization**: Integration with Blender for immersive archaeological presentations
* **Data Exchange**: Standards-compliant export for research collaboration
* **Temporal Modeling**: Track changes over time in archaeological contexts

Integration with EMtools
-------------------------

s3dgraphy is the core library powering `EMtools <https://github.com/zalmoxes-laran/EM-blender-tools>`_, 
a Blender extension that brings the Extended Matrix methodology to 3D archaeological visualization.

Community & Support
--------------------

* **GitHub Repository**: https://github.com/zalmoxes-laran/s3dgraphy
* **Issue Tracker**: https://github.com/zalmoxes-laran/s3dgraphy/issues
* **Extended Matrix Project**: https://www.extendedmatrix.org
* **Contact**: emanuel.demetrescu@cnr.it

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* * :ref:`search`
