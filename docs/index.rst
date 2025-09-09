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

**s3dgraphy** is a Python library that implements the Extended Matrix formal language 
for archaeological stratigraphic documentation and virtual reconstruction processes. 
It provides the core graph structure and node management system that powers the 
Extended Matrix Framework (EMF).

🎯 **Key Features**

🔗 **Graph-Based Architecture**
   Native support for complex archaeological relationships and temporal sequences

📊 **Stratigraphic Modeling**
   Specialized node types for archaeological units, documentation, and interpretation

🔄 **Format Interoperability**
   Import/export support for GraphML, JSON, and archaeological data formats

🏛️ **Archaeological Standards**
   Built-in support for CIDOC-CRM mapping and archaeological best practices

⚡ **Extensible Design**
   Easy to extend with custom node types and relationship definitions

📤 **Multiple Export Formats**
   Export to GraphML, JSON, and standards-compliant formats

🔄 **Blender Integration**
   Direct integration with EMtools for 3D archaeological visualization

📖 **Rich Documentation**
   Comprehensive guides, tutorials, and API reference

Quick Start
-----------

Install s3dgraphy using pip:

.. code-block:: bash

   pip install s3dgraphy

Create your first archaeological graph:

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes import StratigraphicNode, DocumentNode
   
   # Create a new graph
   graph = Graph("my_site")
   
   # Add a stratigraphic unit
   us001 = StratigraphicNode("US001", node_type="US")
   us001.set_attribute("description", "Stone wall foundation")
   graph.add_node(us001)
   
   # Add documentation
   doc001 = DocumentNode("DOC001", "site_plan.pdf")
   graph.add_node(doc001)
   
   # Create relationship
   graph.add_edge(us001.node_id, doc001.node_id, "documented_by")
   
   # Export to GraphML
   graph.export_graphml("my_site.graphml")

Extended Matrix Language Reference
==================================

s3dgraphy implements the Extended Matrix formal language. For a complete 
understanding of EM concepts, node types, and theoretical foundations, 
please refer to the `Extended Matrix Documentation 
<https://docs.extendedmatrix.org/en/1.5.0dev/>`_.

The Extended Matrix documentation includes detailed explanations of:

- **Stratigraphic and auxiliary node types** – Complete catalog of archaeological units
- **Connector semantics and usage** – Temporal and logical relationships
- **Theoretical archaeological foundations** – Scientific methodology and best practices
- **Canvas and visual representation guidelines** – Standardized notation system
- **Formal language specification** – Grammar and syntax rules

This separation allows s3dgraphy to focus on technical implementation while the 
Extended Matrix documentation provides the conceptual framework and human-readable 
explanations of the methodology.

Archaeological Applications
---------------------------

s3dgraphy is particularly suited for:

* **Stratigraphic Analysis**: Model archaeological layers and their temporal relationships
* **Site Documentation**: Create structured records of excavation data
* **3D Visualization**: Integration with Blender for immersive archaeological presentations
* **Data Exchange**: Standards-compliant export for research collaboration
* **Temporal Modeling**: Track changes over time in archaeological contexts
* **Virtual Reconstruction**: Document hypotheses and reconstruction processes
* **Paradata Management**: Track sources and analytical processes

Integration with EMtools
------------------------

s3dgraphy is the core library powering `EMtools <https://github.com/zalmoxes-laran/EM-blender-tools>`_, 
a Blender extension that brings the Extended Matrix methodology to 3D archaeological visualization.

The integration provides:

- **Real-time 3D annotation** of stratigraphic units
- **Visual graph management** within Blender's interface  
- **Export capabilities** to ATON 3, Heriverse, and other platforms
- **3D paradata visualization** for reconstruction documentation

Extended Matrix Ecosystem
--------------------------

s3dgraphy is part of the broader Extended Matrix Framework:

* **EM-tools for Blender** - 3D visualization and annotation
* **Extended Matrix Documentation** - Formal language reference and tutorials
* **3D Survey Collection (3DSC)** - High-quality 3D model preparation
* **ATON 3 Framework** - Web-based archaeological visualization
* **Heriverse Platform** - Virtual heritage experiences

Community & Support
--------------------

* **GitHub Repository**: https://github.com/zalmoxes-laran/s3dgraphy
* **Issue Tracker**: https://github.com/zalmoxes-laran/s3dgraphy/issues
* **Extended Matrix Project**: https://www.extendedmatrix.org
* **Telegram Group**: https://t.me/UserGroupEM
* **Facebook Group**: https://www.facebook.com/groups/extendedmatrix
* **Contact**: emanuel.demetrescu@cnr.it

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
   
   s3dgraphy_import_export_complete
   graph_management
   node_types
   integration

.. toctree::
   :maxdepth: 2
   :caption: Advanced Guides
   
   guides/s3dgraphy_operators_guide
   guides/s3dgraphy_caching_performance

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
   examples/s3dgraphy_workflow_examples

.. toctree::
   :maxdepth: 2
   :caption: Tutorials
   
   tutorials/basic_usage

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

.. toctree::
   :maxdepth: 1
   :caption: Legacy Documentation
   
   introduction

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
