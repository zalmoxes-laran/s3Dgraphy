#!/usr/bin/env python3
"""
🏛️ Script completo per configurare la documentazione s3dgraphy con Read the Docs
Versione per repository unico - Crea TUTTI i file necessari
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configurazione
PROJECT_NAME = "s3dgraphy"
AUTHOR = "Emanuel Demetrescu"
EMAIL = "emanuel.demetrescu@cnr.it"
GITHUB_USER = "zalmoxes-laran"

def create_directory_structure():
    """Crea la struttura delle cartelle per la documentazione"""
    print("📁 Creazione struttura cartelle...")
    
    directories = [
        "docs",
        "docs/_static", 
        "docs/_templates",
        "docs/tutorials",
        "docs/guides", 
        "docs/api",
        "docs/examples"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {directory}")

def create_sphinx_config():
    """Crea il file conf.py per Sphinx"""
    print("\n⚙️ Creazione conf.py...")
    
    conf_content = f'''# Configuration file for the Sphinx documentation builder.
# s3dgraphy documentation configuration

import os
import sys
import datetime

# Add the project root and src to Python path
sys.path.insert(0, os.path.abspath('..'))
sys.path.insert(0, os.path.abspath('../src'))

# -- Project information -----------------------------------------------------
project = '{PROJECT_NAME}'
copyright = f'2024-{{datetime.datetime.now().year}}, {AUTHOR}'
author = '{AUTHOR}'

# Read version from pyproject.toml
version = '0.1.0'  # Will be updated dynamically
release = version

# -- General configuration ---------------------------------------------------
extensions = [
    # Core Sphinx extensions
    'sphinx.ext.autodoc',           # Auto-generate API docs
    'sphinx.ext.autosummary',       # Generate summaries
    'sphinx.ext.napoleon',          # Google/NumPy docstring style
    'sphinx.ext.viewcode',          # Add source code links
    'sphinx.ext.intersphinx',       # Cross-reference other docs
    'sphinx.ext.todo',              # TODO items
    'sphinx.ext.coverage',          # Documentation coverage
    'sphinx.ext.ifconfig',          # Conditional content
    
    # External extensions
    'myst_parser',                  # Markdown support
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_theme_options = {{
    'analytics_id': '',  # Google Analytics ID
    'analytics_anonymize_ip': False,
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    'vcs_pageview_mode': '',
    'style_nav_header_background': '#2980B9',
    # Toc options
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom CSS
html_css_files = [
    'custom.css',
]

# -- Extension configuration -------------------------------------------------

# -- Options for autodoc ----------------------------------------------------
autodoc_default_options = {{
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'show-inheritance': True,
    'imported-members': True,
}}

# -- Options for autosummary ------------------------------------------------
autosummary_generate = True
autosummary_generate_overwrite = False

# -- Options for napoleon ---------------------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

# -- Options for intersphinx ------------------------------------------------
intersphinx_mapping = {{
    'python': ('https://docs.python.org/3/', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'networkx': ('https://networkx.org/documentation/stable/', None),
}}

# -- Options for todo extension ---------------------------------------------
todo_include_todos = True

# -- Options for MyST parser -----------------------------------------------
myst_enable_extensions = [
    "deflist",
    "tasklist",
    "colon_fence",
]

# -- Custom configuration ---------------------------------------------------

# Master document (index file)
master_doc = 'index'

# Source file suffixes
source_suffix = {{
    '.rst': None,
    '.md': 'myst_parser',
}}

# Language for content autogenerated by Sphinx
language = 'en'

# HTML context for templates
html_context = {{
    'display_github': True,
    'github_user': '{GITHUB_USER}',
    'github_repo': '{PROJECT_NAME}',
    'github_version': 'main',
    'conf_py_path': '/docs/',
}}

# Show last updated timestamp
html_last_updated_fmt = '%b %d, %Y'

def setup(app):
    """Custom setup function for additional configuration."""
    app.add_css_file('custom.css')
'''
    
    with open("docs/conf.py", "w") as f:
        f.write(conf_content)
    print("   ✅ docs/conf.py creato")

def create_index_rst():
    """Crea la pagina principale index.rst"""
    print("\n📖 Creazione index.rst...")
    
    index_content = f'''{PROJECT_NAME} Documentation
========================

.. image:: https://img.shields.io/badge/version-0.1.0-blue.svg
   :target: https://pypi.org/project/{PROJECT_NAME}/
   :alt: Version

.. image:: https://img.shields.io/badge/python-3.8+-brightgreen.svg
   :target: https://python.org
   :alt: Python

.. image:: https://img.shields.io/badge/license-GPL--3.0-orange.svg
   :target: https://github.com/{GITHUB_USER}/{PROJECT_NAME}/blob/main/LICENSE
   :alt: License

**{PROJECT_NAME}** is a powerful Python library for managing 3D stratigraphic graphs in archaeological and heritage applications. It provides a comprehensive framework for modeling archaeological layers, their relationships, and integration with 3D visualization tools like Blender.

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

Install {PROJECT_NAME}:

.. code-block:: bash

   pip install {PROJECT_NAME}

Create your first stratigraphic graph:

.. code-block:: python

   from {PROJECT_NAME} import Graph
   from {PROJECT_NAME}.nodes.stratigraphic_node import StratigraphicUnit

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

   print(f"Graph has {{len(graph.nodes)}} nodes and {{len(graph.edges)}} edges")

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

{PROJECT_NAME} is particularly suited for:

* **Stratigraphic Analysis**: Model archaeological layers and their temporal relationships
* **Site Documentation**: Create structured records of excavation data
* **3D Visualization**: Integration with Blender for immersive archaeological presentations
* **Data Exchange**: Standards-compliant export for research collaboration
* **Temporal Modeling**: Track changes over time in archaeological contexts

Integration with EMtools
-------------------------

{PROJECT_NAME} is the core library powering `EMtools <https://github.com/{GITHUB_USER}/EM-blender-tools>`_, 
a Blender extension that brings the Extended Matrix methodology to 3D archaeological visualization.

Community & Support
--------------------

* **GitHub Repository**: https://github.com/{GITHUB_USER}/{PROJECT_NAME}
* **Issue Tracker**: https://github.com/{GITHUB_USER}/{PROJECT_NAME}/issues
* **Extended Matrix Project**: https://www.extendedmatrix.org
* **Contact**: {EMAIL}

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* * :ref:`search`
'''
    
    with open("docs/index.rst", "w") as f:
        f.write(index_content)
    print("   ✅ docs/index.rst creato")

def create_readthedocs_config():
    """Crea .readthedocs.yaml"""
    print("\n🔧 Creazione .readthedocs.yaml...")
    
    rtd_content = '''# .readthedocs.yaml
# Read the Docs configuration file for s3dgraphy
# See https://docs.readthedocs.io/en/stable/config-file/v2.html for details

# Required
version: 2

# Set the OS, set of tools, and environment
build:
  os: ubuntu-22.04
  tools:
    python: "3.11"
  # Install dependencies in a virtual environment
  # This is required to use local packages
  jobs:
    # Run before installing project dependencies
    pre_create_environment:
      - echo "Setting up environment for s3dgraphy documentation"
    
    # Run after installing project dependencies
    post_install:
      - echo "s3dgraphy documentation build environment ready"

# Python configuration
python:
  install:
    # Install the project in development mode
    - method: pip
      path: .
      extra_requirements:
        - docs
    # Install additional requirements for documentation
    - requirements: docs/requirements.txt

# Build documentation with Sphinx
sphinx:
  configuration: docs/conf.py
  fail_on_warning: false

# Additional formats to build
formats:
  - pdf
  - epub

# Optional: specify submodules to include
# submodules:
#   include: all

# Optional: set environment variables
# env:
#   DJANGO_SETTINGS_MODULE: myproject.settings
'''
    
    with open(".readthedocs.yaml", "w") as f:
        f.write(rtd_content)
    print("   ✅ .readthedocs.yaml creato")

def create_docs_requirements():
    """Crea docs/requirements.txt"""
    print("\n📦 Creazione docs/requirements.txt...")
    
    requirements_content = '''# Documentation requirements for s3dgraphy
# These are needed to build the documentation on Read the Docs

# Core Sphinx
sphinx>=5.0.0
sphinx-rtd-theme>=1.3.0

# Extensions
myst-parser>=2.0.0           # Markdown support
sphinx-autodoc-typehints>=1.24.0  # Better type hints
sphinx-copybutton>=0.5.2     # Copy code button

# Optional: Enhanced features
sphinxcontrib-napoleon>=0.7   # Better docstring parsing

# Project dependencies needed for autodoc
pandas>=2.0.0
numpy>=1.21.0

# Optional dependencies that might be imported
networkx>=3.0                 # For layout generation
'''
    
    with open("docs/requirements.txt", "w") as f:
        f.write(requirements_content)
    print("   ✅ docs/requirements.txt creato")

def create_api_docs():
    """Crea i file per l'API reference"""
    print("\n⚙️ Creazione API reference...")
    
    # Core API
    api_core_content = '''Core Classes
============

This section documents the core classes of s3dgraphy that form the foundation of the library.

Graph
-----

.. automodule:: s3dgraphy.graph
   :members:
   :undoc-members:
   :show-inheritance:

Base Node
---------

.. automodule:: s3dgraphy.nodes.base_node
   :members:
   :undoc-members:
   :show-inheritance:

Edge
----

.. automodule:: s3dgraphy.edges.edge
   :members:
   :undoc-members:
   :show-inheritance:

Multi Graph Manager
-------------------

.. automodule:: s3dgraphy.multi_graph_manager
   :members:
   :undoc-members:
   :show-inheritance:
'''
    
    with open("docs/api/core.rst", "w") as f:
        f.write(api_core_content)
    print("   ✅ docs/api/core.rst creato")
    
    # Nodes API
    api_nodes_content = '''Node Types
==========

This section documents all the different node types available in s3dgraphy.

Stratigraphic Nodes
-------------------

.. automodule:: s3dgraphy.nodes.stratigraphic_node
   :members:
   :undoc-members:
   :show-inheritance:

Paradata Nodes
--------------

.. automodule:: s3dgraphy.nodes.paradata_node
   :members:
   :undoc-members:
   :show-inheritance:

Representation Nodes
--------------------

.. automodule:: s3dgraphy.nodes.representation_node
   :members:
   :undoc-members:
   :show-inheritance:

Other Node Types
----------------

.. automodule:: s3dgraphy.nodes.group_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.graph_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.geoposition_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.epoch_node
   :members:
   :undoc-members:
   :show-inheritance:
'''
    
    with open("docs/api/nodes.rst", "w") as f:
        f.write(api_nodes_content)
    print("   ✅ docs/api/nodes.rst creato")
    
    # Utils API
    api_utils_content = '''Utilities
=========

.. automodule:: s3dgraphy.utils.utils
   :members:
   :undoc-members:
   :show-inheritance:

Visual Layout
-------------

.. automodule:: s3dgraphy.utils.visual_layout
   :members:
   :undoc-members:
   :show-inheritance:
'''
    
    with open("docs/api/utils.rst", "w") as f:
        f.write(api_utils_content)
    print("   ✅ docs/api/utils.rst creato")

def create_tutorial():
    """Crea un tutorial di base"""
    print("\n📚 Creazione tutorial base...")
    
    tutorial_content = '''Basic Usage Tutorial
===================

This tutorial will walk you through the basic usage of s3dgraphy, from creating your first graph to adding nodes and relationships.

Prerequisites
-------------

Make sure you have s3dgraphy installed:

.. code-block:: bash

   pip install s3dgraphy

Creating Your First Graph
--------------------------

Let's start by creating a simple stratigraphic graph for an archaeological site:

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

   # Create a new graph
   site_graph = Graph("Pompeii_Forum")
   print(f"Created graph: {site_graph.name}")

Adding Stratigraphic Units
---------------------------

Now let's add some stratigraphic units representing different archaeological layers:

.. code-block:: python

   # Create stratigraphic units
   surface_layer = StratigraphicUnit(
       node_id="US001", 
       name="Surface layer", 
       node_type="US"
   )
   
   medieval_layer = StratigraphicUnit(
       node_id="US002", 
       name="Medieval occupation", 
       node_type="US"
   )
   
   roman_floor = StratigraphicUnit(
       node_id="US003", 
       name="Roman floor", 
       node_type="US"
   )

Adding Nodes to the Graph
--------------------------

Add the stratigraphic units to your graph:

.. code-block:: python

   # Add nodes to the graph
   site_graph.add_node(surface_layer)
   site_graph.add_node(medieval_layer)
   site_graph.add_node(roman_floor)

   print(f"Graph now has {len(site_graph.nodes)} nodes")

Defining Stratigraphic Relationships
------------------------------------

The core of stratigraphic analysis is understanding temporal relationships:

.. code-block:: python

   # Add temporal relationships (stratigraphic sequence)
   # "is_before" means the source is older than the target
   
   site_graph.add_edge("rel1", "US002", "US001", "is_before")  # Medieval before Surface
   site_graph.add_edge("rel2", "US003", "US002", "is_before")  # Roman before Medieval

   print(f"Graph now has {len(site_graph.edges)} relationships")

Complete Example
----------------

Here's the complete code for this tutorial:

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

   # Create graph
   site_graph = Graph("Pompeii_Forum")

   # Create and add stratigraphic units
   units = [
       StratigraphicUnit("US001", "Surface layer", "US"),
       StratigraphicUnit("US002", "Medieval occupation", "US"),
       StratigraphicUnit("US003", "Roman floor", "US")
   ]

   for unit in units:
       site_graph.add_node(unit)

   # Add stratigraphic relationships
   relationships = [
       ("rel1", "US002", "US001", "is_before"),
       ("rel2", "US003", "US002", "is_before")
   ]

   for rel_id, source, target, rel_type in relationships:
       site_graph.add_edge(rel_id, source, target, rel_type)

   # Print summary
   print(f"Created graph '{site_graph.name}' with:")
   print(f"  - {len(site_graph.nodes)} nodes")
   print(f"  - {len(site_graph.edges)} edges")

   # Export
   site_graph.export_graphml("pompeii_forum.graphml")

Next Steps
----------

Now that you understand the basics, you can explore:

- More complex node types and relationships
- Integration with Blender for 3D visualization
- CIDOC-CRM mappings for semantic interoperability
'''
    
    with open("docs/tutorials/basic_usage.rst", "w") as f:
        f.write(tutorial_content)
    print("   ✅ docs/tutorials/basic_usage.rst creato")

def create_custom_css():
    """Crea CSS personalizzato"""
    print("\n🎨 Creazione CSS personalizzato...")
    
    css_content = '''/* Custom CSS for s3dgraphy documentation */

/* Improve code block appearance */
.highlight {
    background: #f8f8f8;
    border: 1px solid #e1e4e5;
    border-radius: 4px;
    margin: 1em 0;
}

/* Add custom colors for archaeological context */
.archaeological-node {
    color: #8B4513;
    font-weight: bold;
}

.stratigraphic-unit {
    background-color: #F5DEB3;
    padding: 2px 4px;
    border-radius: 3px;
}

/* Improve table appearance */
table.docutils {
    border-collapse: collapse;
    margin: 1em 0;
}

table.docutils th,
table.docutils td {
    border: 1px solid #e1e4e5;
    padding: 8px 12px;
}

table.docutils th {
    background-color: #f1f2f3;
    font-weight: bold;
}

/* Improve admonition styling */
.admonition {
    margin: 1em 0;
    padding: 12px;
    border-left: 5px solid #ccc;
    background-color: #f9f9f9;
}

.admonition.note {
    border-left-color: #3498db;
    background-color: #ebf3fd;
}

.admonition.warning {
    border-left-color: #f39c12;
    background-color: #fef4e7;
}

.admonition.important {
    border-left-color: #e74c3c;
    background-color: #fdeaea;
}

/* Archaeological workflow steps */
.workflow-step {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    border-radius: 6px;
    padding: 12px;
    margin: 12px 0;
    position: relative;
}

.workflow-step:before {
    content: "→";
    color: #28a745;
    font-weight: bold;
    font-size: 1.2em;
    margin-right: 8px;
}

/* 3D visualization highlights */
.blender-integration {
    background-color: #fff3e0;
    border: 2px solid #ff9800;
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
}

.blender-integration:before {
    content: "🎨 Blender Integration";
    display: block;
    font-weight: bold;
    color: #e65100;
    margin-bottom: 8px;
}
'''
    
    with open("docs/_static/custom.css", "w") as f:
        f.write(css_content)
    print("   ✅ docs/_static/custom.css creato")

def create_makefile():
    """Crea Makefile per build locale"""
    print("\n🔨 Creazione Makefile...")
    
    makefile_content = '''# Minimal makefile for Sphinx documentation

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD  ?= sphinx-build
SOURCEDIR    = docs
BUILDDIR     = docs/_build

# Put it first so that "make" without argument is like "make help".
help:
\t@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx-build
%: Makefile
\t@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

clean:
\trm -rf docs/_build/

livehtml:
\tsphinx-autobuild docs docs/_build/html --watch src/

install-docs:
\tpip install -e .[docs]

check-docs:
\tsphinx-build -W -b html docs docs/_build/html
'''
    
    with open("Makefile", "w") as f:
        f.write(makefile_content)
    print("   ✅ Makefile creato")

def move_existing_docs():
    """Sposta file documentazione esistenti"""
    print("\n📄 Controllo file esistenti...")
    
    files_to_move = ["introduction.rst"]
    
    for filename in files_to_move:
        if Path(filename).exists():
            shutil.move(filename, f"docs/{filename}")
            print(f"   📄 {filename} → docs/{filename}")
        else:
            print(f"   ⚠️  {filename} non trovato (normale se è la prima volta)")

def install_docs_dependencies():
    """Installa le dipendenze per la documentazione"""
    print("\n📦 Installazione dipendenze documentazione...")
    
    try:
        # Installa il progetto con dipendenze docs
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".[docs]"], 
                              check=True, capture_output=True, text=True)
        print("   ✅ Dipendenze installate con successo")
        
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️  Errore installazione automatica: {e}")
        print("   💡 Prova manualmente: pip install -e .[docs]")
        print("   💡 Se mancano dipendenze: pip install sphinx sphinx-rtd-theme myst-parser")

def test_sphinx_build():
    """Testa la build della documentazione"""
    print("\n🔨 Test build documentazione...")
    
    try:
        result = subprocess.run([
            "sphinx-build", "-b", "html", 
            "docs", "docs/_build/html"
        ], capture_output=True, text=True, check=True)
        
        print("   ✅ Build completata con successo!")
        print(f"   📖 Documentazione disponibile in: docs/_build/html/index.html")
        
        # Try to open the documentation
        index_path = Path("docs/_build/html/index.html").absolute()
        print(f"   🌐 File disponibile: {index_path}")
        
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️  Build fallita: {e}")
        print("   🔍 Output errori:")
        if e.stderr:
            print(e.stderr)
        if e.stdout:
            print(e.stdout)
        
    except FileNotFoundError:
        print("   ❌ sphinx-build non trovato")
        print("   💡 Installa sphinx: pip install sphinx")

def create_installation_guide():
    """Crea guida installazione"""
    print("\n📋 Creazione guida installazione...")
    
    install_content = '''Installation
============

System Requirements
-------------------

- **Python**: 3.8 or higher
- **Operating System**: Cross-platform (Windows, macOS, Linux)
- **Memory**: 512MB RAM minimum
- **Storage**: 50MB available space

Install from PyPI
-----------------

The easiest way to install s3dgraphy is using pip:

.. code-block:: bash

   pip install s3dgraphy

Development Installation
------------------------

For development or to get the latest features:

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/zalmoxes-laran/s3dgraphy.git
   cd s3dgraphy
   
   # Install in development mode
   pip install -e .[dev]

Optional Dependencies
--------------------

Install additional features:

.. code-block:: bash

   # For visualization features
   pip install s3dgraphy[visualization]
   
   # For development tools
   pip install s3dgraphy[dev]
   
   # For documentation building
   pip install s3dgraphy[docs]

Verify Installation
-------------------

Test your installation:

.. code-block:: python

   import s3dgraphy
   print(f"s3dgraphy version: {s3dgraphy.__version__}")
   
   # Create a simple graph
   from s3dgraphy import Graph
   graph = Graph("test")
   print("Installation successful!")

Troubleshooting
---------------

**Common Issues:**

1. **Import Error**: Make sure you're using Python 3.8+
2. **Permission Error**: Use `pip install --user s3dgraphy`
3. **Network Issues**: Try `pip install --trusted-host pypi.org s3dgraphy`

**For Blender Integration:**

s3dgraphy works with Blender 4.0+ through the EMtools extension.
'''
    
    with open("docs/installation.rst", "w") as f:
        f.write(install_content)
    print("   ✅ docs/installation.rst creato")

def show_next_steps():
    """Mostra i prossimi passi da seguire"""
    print("\n" + "="*60)
    print("🎉 CONFIGURAZIONE COMPLETATA!")
    print("="*60)
    print()
    print("📋 PROSSIMI PASSI:")
    print()
    print("1. 🔍 Verifica i file creati:")
    print("   ls -la docs/")
    print("   cat .readthedocs.yaml")
    print()
    print("2. 🔧 Testa localmente:")
    print("   make install-docs          # Installa dipendenze")
    print("   make html                  # Build documentazione")
    print("   open docs/_build/html/index.html  # Visualizza")
    print()
    print("3. 🔗 Configura Read the Docs:")
    print("   - Vai su https://readthedocs.org")
    print("   - Connetti il repository GitHub s3dgraphy")
    print("   - Importa il progetto")
    print("   - La build partirà automaticamente")
    print()
    print("4. 🚀 Pubblica:")
    print("   git add .")
    print("   git commit -m 'Add Sphinx documentation setup'")
    print("   git push origin main")
    print()
    print("📖 La documentazione sarà disponibile su:")
    print(f"   https://{PROJECT_NAME}.readthedocs.io")
    print()
    print("📝 Per personalizzare ulteriormente:")
    print("   - Aggiungi docstring nel codice Python")
    print("   - Espandi tutorial in docs/tutorials/")
    print("   - Aggiungi esempi in docs/examples/")
    print("   - Personalizza docs/_static/custom.css")
    print()
    print("🆘 In caso di problemi:")
    print("   - Controlla i log su Read the Docs")
    print("   - Verifica docs/requirements.txt")
    print("   - Testa localmente con 'make html'")

def main():
    """Funzione principale"""
    print("🏛️  Setup Completo Documentazione s3dgraphy")
    print("=" * 50)
    
    # Verifica di essere nella directory corretta
    if not Path("pyproject.toml").exists():
        print("❌ Errore: Esegui questo script dalla root del progetto s3dgraphy")
        print("   (dove si trova pyproject.toml)")
        sys.exit(1)
    
    # Esegui tutti i passi
    create_directory_structure()
    create_sphinx_config()
    create_index_rst()
    create_readthedocs_config()
    create_docs_requirements()
    create_api_docs()
    create_tutorial()
    create_installation_guide()
    create_custom_css()
    create_makefile()
    move_existing_docs()
    
    # Installa dipendenze (opzionale, potrebbe fallire)
    install_docs_dependencies()
    
    # Test build (opzionale)
    test_sphinx_build()
    
    # Mostra prossimi passi
    show_next_steps()

if __name__ == "__main__":
    main()
