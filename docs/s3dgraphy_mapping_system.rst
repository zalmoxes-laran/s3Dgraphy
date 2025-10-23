Mapping System Guide
====================

The s3dgraphy mapping system enables import of tabular data from XLSX and SQLite databases by defining how columns map to graph nodes and attributes.

.. note::
   This guide focuses on the practical aspects of creating and using mappings for data import.

Overview
--------

The mapping system consists of:

1. **JSON mapping files** that define column-to-attribute mappings
2. **Mapping registry** that manages available mappings
3. **Importers** (MappedXLSXImporter, PyArchInitImporter) that use mappings
4. **Column normalization** for flexible matching

Why Use Mappings?
~~~~~~~~~~~~~~~~~

Mappings solve these problems:

- **Diverse data formats**: Different projects use different column names
- **Flexible imports**: Same importer works with multiple formats
- **Reusability**: Share mappings across projects
- **Validation**: Define required fields and data types
- **Documentation**: Mappings serve as data format documentation

Mapping File Structure
----------------------

Basic Structure
~~~~~~~~~~~~~~~

A mapping file is a JSON document with this structure:

.. code-block:: json

   {
       "mapping_name": "unique_identifier",
       "description": "Human-readable description",
       "version": "1.0",
       "format_type": "xlsx" or "sqlite",
       "table_settings": {
           "sheet_name": "Sheet1",  // For XLSX
           "table_name": "us_table",  // For SQLite
           "header_row": 0,
           "id_column": "US"  // Or formula for SQLite
       },
       "column_mappings": {
           "ColumnName": {
               "is_id": false,
               "required": false,
               "node_attribute": "attribute_name",
               "default_value": null,
               "data_type": "string"
           }
       },
       "node_settings": {
           "default_node_type": "US",
           "create_properties": true,
           "id_format": "{column1}_{column2}"
       }
   }

Section Breakdown
~~~~~~~~~~~~~~~~~

Metadata Section
^^^^^^^^^^^^^^^^

.. code-block:: json

   {
       "mapping_name": "emdb_basic",
       "description": "Basic EMdb format for stratigraphic units",
       "version": "1.0",
       "format_type": "xlsx"
   }

- **mapping_name**: Unique identifier (used in code to reference mapping)
- **description**: Human-readable description
- **version**: Mapping version for tracking changes
- **format_type**: ``xlsx`` or ``sqlite``

Table Settings
^^^^^^^^^^^^^^

For XLSX files:

.. code-block:: json

   {
       "table_settings": {
           "sheet_name": "Stratigraphic Units",
           "header_row": 0
       }
   }

For SQLite databases:

.. code-block:: json

   {
       "table_settings": {
           "table_name": "us_table",
           "id_column": "sito||'_'||area||'_'||us"
       }
   }

- **sheet_name** (XLSX): Name of the Excel sheet
- **header_row** (XLSX): Row number containing column headers (0-indexed)
- **table_name** (SQLite): Database table name
- **id_column** (SQLite): Column name or SQL expression for generating IDs

Column Mappings
^^^^^^^^^^^^^^^

.. code-block:: json

   {
       "column_mappings": {
           "US": {
               "is_id": true,
               "required": true,
               "node_attribute": "node_id"
           },
           "Definition": {
               "node_attribute": "description",
               "default_value": ""
           },
           "Chronology": {
               "node_attribute": "dating"
           },
           "Material": {
               "node_attribute": "material",
               "data_type": "string"
           },
           "Area": {
               "node_attribute": "area",
               "required": false
           }
       }
   }

Column mapping properties:

- **is_id**: Marks this column as the unique identifier
- **required**: Import fails if column is missing
- **node_attribute**: Target attribute name in the graph node
- **default_value**: Default if cell is empty
- **data_type**: Expected data type (for validation)

Node Settings
^^^^^^^^^^^^^

.. code-block:: json

   {
       "node_settings": {
           "default_node_type": "US",
           "create_properties": true,
           "id_format": "{site}_{area}_{us}",
           "prefix": "SITE01"
       }
   }

- **default_node_type**: Node type to create (US, USV, DOC, etc.)
- **create_properties**: Create PropertyNode for each column
- **id_format**: Template for generating node IDs from columns
- **prefix**: Optional prefix for all node IDs

Column Normalization
--------------------

The mapping system normalizes both Excel column names and JSON mapping keys to enable flexible matching.

Normalization Rules
~~~~~~~~~~~~~~~~~~~

1. Convert to uppercase
2. Replace spaces with underscores
3. Replace hyphens, slashes, parentheses, brackets, dots with underscores
4. Replace special dashes (–, —) with underscores
5. Remove multiple consecutive underscores
6. Remove leading/trailing underscores

Examples
~~~~~~~~

.. code-block:: python

   # Original -> Normalized
   "US Number" -> "US_NUMBER"
   "Type (Primary)" -> "TYPE_PRIMARY"
   "Date - Start" -> "DATE_START"
   "Area/Sector" -> "AREA_SECTOR"
   "Phase.Name" -> "PHASE_NAME"

This means your mapping can use ``"US Number"`` and it will match Excel columns named:
- ``"US Number"``
- ``"us number"``
- ``"US_NUMBER"``
- ``"us-number"``
- ``"US.Number"``

Built-in Mappings
-----------------

s3dgraphy includes several predefined mappings:

EMdb Mappings
~~~~~~~~~~~~~

For the EMdb (Extended Matrix Database) format:

**emdb_basic** - Basic stratigraphic units

.. code-block:: json

   {
       "mapping_name": "emdb_basic",
       "description": "Basic EMdb format for stratigraphic units",
       "format_type": "xlsx",
       "table_settings": {
           "sheet_name": "US",
           "header_row": 0
       },
       "column_mappings": {
           "US": {
               "is_id": true,
               "required": true,
               "node_attribute": "node_id"
           },
           "Type": {
               "node_attribute": "node_type",
               "default_value": "US"
           },
           "Definition": {
               "node_attribute": "description"
           },
           "Chronology": {
               "node_attribute": "dating"
           },
           "Material": {
               "node_attribute": "material"
           }
       },
       "node_settings": {
           "default_node_type": "US"
       }
   }

**emdb_extended** - Extended EMdb with all fields

Includes additional columns for conservation state, interpretation, excavation method, etc.

PyArchInit Mappings
~~~~~~~~~~~~~~~~~~~

For pyArchInit database format:

**pyarchinit_us_table** - US table mapping

.. code-block:: json

   {
       "mapping_name": "pyarchinit_us_table",
       "description": "PyArchInit US table mapping",
       "format_type": "sqlite",
       "table_settings": {
           "table_name": "us_table",
           "id_column": "sito||'_'||area||'_'||us"
       },
       "column_mappings": {
           "sito": {
               "node_attribute": "site"
           },
           "area": {
               "node_attribute": "area"
           },
           "us": {
               "is_id": true,
               "node_attribute": "us_number"
           },
           "d_stratigrafica": {
               "node_attribute": "description"
           },
           "interpretazione": {
               "node_attribute": "interpretation"
           },
           "colore": {
               "node_attribute": "color"
           },
           "consistenza": {
               "node_attribute": "consistency"
           }
       },
       "node_settings": {
           "default_node_type": "US",
           "id_format": "{site}_{area}_{us}"
       }
   }

Creating Custom Mappings
------------------------

Step 1: Analyze Your Data
~~~~~~~~~~~~~~~~~~~~~~~~~~

First, examine your data structure:

.. code-block:: python

   import pandas as pd
   
   # For XLSX
   df = pd.read_excel("your_data.xlsx", sheet_name="Sheet1")
   print("Columns:", df.columns.tolist())
   print("\nFirst row:")
   print(df.iloc[0])

Step 2: Create Mapping File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a JSON file with your mapping:

.. code-block:: json

   {
       "mapping_name": "myproject_excavation",
       "description": "Custom format for My Project excavation data",
       "version": "1.0",
       "format_type": "xlsx",
       "table_settings": {
           "sheet_name": "Excavation Units",
           "header_row": 0
       },
       "column_mappings": {
           "Unit ID": {
               "is_id": true,
               "required": true,
               "node_attribute": "node_id"
           },
           "Unit Type": {
               "node_attribute": "node_type",
               "required": true,
               "default_value": "US"
           },
           "Description": {
               "node_attribute": "description"
           },
           "Excavator": {
               "node_attribute": "excavator"
           },
           "Date Excavated": {
               "node_attribute": "excavation_date",
               "data_type": "date"
           },
           "Area": {
               "node_attribute": "area"
           },
           "Phase": {
               "node_attribute": "chronological_phase"
           }
       },
       "node_settings": {
           "default_node_type": "US",
           "create_properties": true
       }
   }

Step 3: Save Mapping File
~~~~~~~~~~~~~~~~~~~~~~~~~~

Save to the mappings directory:

.. code-block:: bash

   # For project-specific mappings
   mkdir -p s3dgraphy/mappings/custom
   # Save as: myproject_excavation.json

Step 4: Register Mapping
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.mappings import mapping_registry
   import json
   
   # Load mapping file
   with open('path/to/myproject_excavation.json') as f:
       mapping_data = json.load(f)
   
   # Register mapping
   mapping_registry.register_mapping(
       'myproject_excavation',
       mapping_data
   )

Step 5: Use Mapping
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.importer import MappedXLSXImporter
   from s3dgraphy import Graph
   
   graph = Graph("my_excavation")
   
   importer = MappedXLSXImporter(
       filepath="excavation_data.xlsx",
       mapping_name="myproject_excavation",
       graph=graph
   )
   
   graph = importer.parse()
   print(f"Imported {len(graph.nodes)} units")

Advanced Mapping Features
--------------------------

ID Format Templates
~~~~~~~~~~~~~~~~~~~

Generate complex IDs from multiple columns:

.. code-block:: json

   {
       "node_settings": {
           "id_format": "{site}_{trench}_{context}_{year}"
       },
       "column_mappings": {
           "Site": {"node_attribute": "site"},
           "Trench": {"node_attribute": "trench"},
           "Context": {"node_attribute": "context"},
           "Year": {"node_attribute": "year"}
       }
   }

This creates node IDs like: ``POMPEII_TR01_0045_2024``

Conditional Defaults
~~~~~~~~~~~~~~~~~~~~

Use default values for empty cells:

.. code-block:: json

   {
       "column_mappings": {
           "Preservation": {
               "node_attribute": "preservation",
               "default_value": "unknown"
           },
           "Excavation Method": {
               "node_attribute": "method",
               "default_value": "manual"
           }
       }
   }

Creating Property Nodes
~~~~~~~~~~~~~~~~~~~~~~~

Automatically create PropertyNode for each attribute:

.. code-block:: json

   {
       "node_settings": {
           "create_properties": true
       }
   }

This creates:
- StratigraphicNode for the unit
- PropertyNode for each attribute
- ``has_property`` edges connecting them

Multi-Sheet Import
~~~~~~~~~~~~~~~~~~

For XLSX files with multiple sheets:

.. code-block:: python

   # Create mapping for each sheet
   mappings = {
       'stratigraphic_units': 'emdb_basic',
       'special_finds': 'emdb_finds',
       'samples': 'emdb_samples'
   }
   
   graph = Graph("multi_sheet_import")
   
   for sheet_name, mapping_name in mappings.items():
       importer = MappedXLSXImporter(
           filepath="data.xlsx",
           mapping_name=mapping_name,
           graph=graph
       )
       graph = importer.parse()

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**Issue: "Column not found" errors**

Solution: Check column normalization

.. code-block:: python

   # Debug normalization
   original_name = "US Number"
   normalized = original_name.upper().replace(' ', '_')
   print(f"'{original_name}' -> '{normalized}'")
   
   # Check actual Excel columns
   df = pd.read_excel("file.xlsx")
   print("Actual columns:", df.columns.tolist())

**Issue: "No ID column found"**

Solution: Ensure one column has ``"is_id": true``

.. code-block:: json

   {
       "column_mappings": {
           "US": {
               "is_id": true,  // ← Must have this
               "required": true,
               "node_attribute": "node_id"
           }
       }
   }

**Issue: "Required column missing"**

Solution: Make column optional or provide default

.. code-block:: json

   {
       "Material": {
           "node_attribute": "material",
           "required": false,  // ← Make optional
           "default_value": "unknown"  // ← Provide default
       }
   }

Debugging Imports
~~~~~~~~~~~~~~~~~

Enable detailed logging:

.. code-block:: python

   importer = MappedXLSXImporter(
       filepath="data.xlsx",
       mapping_name="my_mapping",
       graph=graph
   )
   
   # Importer prints detailed progress
   graph = importer.parse()
   
   # Check warnings
   importer.display_warnings()
   
   # Inspect what was imported
   print(f"Nodes: {len(graph.nodes)}")
   print(f"Node types: {set(n.node_type for n in graph.nodes)}")

Validate Mapping Before Use
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def validate_mapping(mapping_data):
       """Validate mapping structure"""
       errors = []
       
       # Check required fields
       if 'mapping_name' not in mapping_data:
           errors.append("Missing 'mapping_name'")
       
       if 'column_mappings' not in mapping_data:
           errors.append("Missing 'column_mappings'")
       
       # Check for ID column
       has_id = False
       for col, config in mapping_data.get('column_mappings', {}).items():
           if config.get('is_id'):
               has_id = True
               break
       
       if not has_id:
           errors.append("No column marked as ID (is_id: true)")
       
       if errors:
           print("Mapping validation errors:")
           for error in errors:
               print(f"  - {error}")
           return False
       
       print("✓ Mapping is valid")
       return True

Best Practices
--------------

1. Document Your Mappings
~~~~~~~~~~~~~~~~~~~~~~~~~~

Add clear descriptions:

.. code-block:: json

   {
       "mapping_name": "site_format_2024",
       "description": "Excavation format for Site X, Season 2024. Uses area codes and sequential numbering.",
       "version": "1.0"
   }

2. Version Your Mappings
~~~~~~~~~~~~~~~~~~~~~~~~~

Update version when changing mapping:

.. code-block:: json

   {
       "version": "1.1",  // Increment when modifying
       "changelog": [
           "1.1: Added 'preservation' field",
           "1.0: Initial version"
       ]
   }

3. Use Consistent Naming
~~~~~~~~~~~~~~~~~~~~~~~~~

Follow naming conventions:

- **mapping_name**: lowercase_with_underscores
- **node_attribute**: lowercase_with_underscores
- Match s3dgraphy node attribute names when possible

4. Test with Sample Data
~~~~~~~~~~~~~~~~~~~~~~~~~

Always test with a small dataset first:

.. code-block:: python

   # Test with first 10 rows
   df = pd.read_excel("data.xlsx", nrows=10)
   df.to_excel("test_data.xlsx", index=False)
   
   # Import test data
   importer = MappedXLSXImporter(
       filepath="test_data.xlsx",
       mapping_name="my_mapping",
       graph=test_graph
   )
   graph = importer.parse()
   
   # Verify results
   print(f"Test import: {len(graph.nodes)} nodes")

5. Handle Missing Data Gracefully
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use defaults and make columns optional:

.. code-block:: json

   {
       "column_mappings": {
           "Optional Field": {
               "node_attribute": "optional_attr",
               "required": false,
               "default_value": null
           }
       }
   }

Example Workflows
-----------------

Complete XLSX Import Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import json
   from s3dgraphy import Graph
   from s3dgraphy.importer import MappedXLSXImporter
   from s3dgraphy.mappings import mapping_registry
   
   # 1. Load and register mapping
   with open('mappings/excavation_2024.json') as f:
       mapping = json.load(f)
   
   mapping_registry.register_mapping('excavation_2024', mapping)
   
   # 2. Create graph
   graph = Graph("excavation_2024")
   
   # 3. Import data
   importer = MappedXLSXImporter(
       filepath="data/stratigraphic_units.xlsx",
       mapping_name="excavation_2024",
       graph=graph
   )
   
   # 4. Parse and check warnings
   graph = importer.parse()
   importer.display_warnings()
   
   # 5. Validate imported data
   print(f"✓ Imported {len(graph.nodes)} nodes")
   print(f"✓ Imported {len(graph.edges)} edges")
   
   # 6. Export for verification
   from s3dgraphy.exporter import export_to_json
   export_to_json("output/verification.json", [graph.graph_id])

PyArchInit Database Import
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.importer import PyArchInitImporter
   
   # Create graph
   graph = Graph("pyarchinit_import")
   
   # Import from database
   importer = PyArchInitImporter(
       filepath="excavation.db",
       mapping_name="pyarchinit_us_table",
       graph=graph
   )
   
   graph = importer.parse()
   importer.display_warnings()
   
   print(f"Imported from SQLite: {len(graph.nodes)} nodes")

See Also
--------

- :doc:`s3dgraphy_import_export` - Complete import/export guide
- :doc:`s3dgraphy_json_config` - JSON configuration files
- :doc:`s3dgraphy_integration_emtools` - EM-tools integration examples
- :doc:`api/s3dgraphy_classes_reference` - Complete API reference
