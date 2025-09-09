s3dgraphy Workflow Examples
==================================

This document provides complete, real-world workflow examples for archaeological projects using s3dgraphy, from data creation to analysis and visualization.

Complete Archaeological Site Workflow
-------------------------------------

Workflow 1: Roman Villa Excavation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This comprehensive example demonstrates a complete workflow for documenting a Roman villa excavation with s3dgraphy.

Step 1: Project Setup and Initial Graph Creation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from s3dgraphy import Graph, MultiGraphManager
   from s3dgraphy.nodes import *
   from s3dgraphy.importer import GraphMLImporter
   import json

   def setup_roman_villa_project():
       """
       Setup a complete Roman villa excavation project.
       """
       # Initialize multi-graph manager for project
       manager = MultiGraphManager()
       
       # Create main site graph
       villa_graph = Graph("Villa_Rustica_2024")
       villa_graph.name = {
           "en": "Villa Rustica Excavation 2024",
           "it": "Scavo Villa Rustica 2024"
       }
       villa_graph.description = {
           "en": "Complete excavation of a Roman villa rustica, Lazio, Italy",
           "it": "Scavo completo di una villa rustica romana, Lazio, Italia"
       }
       
       # Set project metadata
       villa_graph.data = {
           "coordinates": [41.9028, 12.4964],  # Rome area
           "elevation": 45,
           "excavation_permit": "MIC-2024-LAZ-001",
           "start_date": "2024-03-15",
           "end_date": "2024-10-30",
           "site_size_m2": 2500,
           "project_director": "Dr. Elena Rossi",
           "institution": "Università di Roma La Sapienza"
       }
       
       # Add to manager
       manager.graphs["villa_main"] = villa_graph
       
       return manager, villa_graph

   # Initialize project
   project_manager, main_graph = setup_roman_villa_project()
   print(f"Created project: {main_graph.graph_id}")
   print(f"Project area: {main_graph.data['site_size_m2']} m²")

Step 2: Import Existing Field Data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def import_field_documentation(graph):
       """
       Import existing field documentation and establish document hierarchy.
       """
       
       # Create documentation structure
       documents = [
           {
               "id": "DOC_001", "name": "Site Survey Report 2023", 
               "url": "reports/site_survey_2023.pdf",
               "type": "survey_report", "author": "Dr. Marco Bianchi"
           },
           {
               "id": "DOC_002", "name": "Geophysical Survey Results",
               "url": "data/geophys_2023.pdf", 
               "type": "geophysical_survey", "author": "GeoArch Ltd"
           },
           {
               "id": "DOC_003", "name": "Historical Sources Compilation",
               "url": "research/historical_sources.pdf",
               "type": "historical_research", "author": "Dr. Anna Verdi"
           },
           {
               "id": "DOC_004", "name": "Excavation Methodology",
               "url": "methodology/excavation_protocol.pdf",
               "type": "methodology", "author": "Dr. Elena Rossi"
           }
       ]
       
       # Add document nodes
       for doc_info in documents:
           doc = DocumentNode(
               doc_info["id"], 
               doc_info["name"], 
               doc_info["url"],
               f"Type: {doc_info['type']}, Author: {doc_info['author']}"
           )
           doc.set_attribute("document_type", doc_info["type"])
           doc.set_attribute("author", doc_info["author"])
           graph.add_node(doc)
       
       # Create author nodes and relationships
       authors = set(doc["author"] for doc in documents)
       for author_name in authors:
           author_id = f"AUTH_{author_name.replace(' ', '_').replace('.', '').upper()}"
           author = AuthorNode(author_id, author_name)
           graph.add_node(author)
           
           # Connect authors to their documents
           for doc_info in documents:
               if doc_info["author"] == author_name:
                   graph.add_edge(
                       f"authored_{doc_info['id']}", 
                       author_id, 
                       doc_info["id"], 
                       "has_authored"
                   )
       
       print(f"Added {len(documents)} documents and {len(authors)} authors")
       return graph

   # Import documentation
   main_graph = import_field_documentation(main_graph)

Step 3: Create Stratigraphic Sequence
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def create_villa_stratigraphy(graph):
       """
       Create the complete stratigraphic sequence for the Roman villa.
       """
       
       # Phase 1: Modern layers (topsoil, modern disturbances)
       modern_units = [
           ("US_001", "Topsoil", "Dark brown humic soil, modern materials", "modern"),
           ("US_002", "Modern fill", "Concrete and brick debris from farm building", "modern"),
           ("US_003", "Plowing layer", "Mixed soil with ceramic fragments", "post_medieval")
       ]
       
       # Phase 2: Medieval reoccupation
       medieval_units = [
           ("US_004", "Medieval floor", "Beaten earth floor with pottery", "medieval"),
           ("US_005", "Medieval hearth", "Stone and clay hearth structure", "medieval"),
           ("US_006", "Medieval wall foundation", "Reused Roman stones", "medieval")
       ]
       
       # Phase 3: Late Roman abandonment layers
       late_roman_units = [
           ("US_007", "Collapse layer", "Roof tile and wall collapse", "late_roman"),
           ("US_008", "Abandonment deposit", "Accumulated debris and soil", "late_roman"),
           ("US_009", "Final occupation floor", "Well-preserved mosaic floor", "late_roman")
       ]
       
       # Phase 4: Imperial Roman villa (main occupation)
       villa_units = [
           ("US_010", "Villa entrance hall", "Marble threshold and floor", "imperial_roman"),
           ("US_011", "Atrium floor", "Geometric mosaic with emblema", "imperial_roman"),
           ("US_012", "Peristyle garden", "Planted area with water features", "imperial_roman"),
           ("US_013", "Kitchen area", "Hearth, storage areas, and drains", "imperial_roman"),
           ("US_014", "Balneum (bath complex)", "Hypocaust and marble decorations", "imperial_roman"),
           ("US_015", "Storage rooms (horrea)", "Large dolia and amphora storage", "imperial_roman"),
           ("US_016", "Villa wall foundations", "Opus reticulatum construction", "imperial_roman"),
           ("US_017", "Villa floor preparation", "Rubble and mortar foundation", "imperial_roman")
       ]
       
       # Phase 5: Republican predecessor
       republican_units = [
           ("US_018", "Early farm building", "Simple stone construction", "republican"),
           ("US_019", "Early agricultural layers", "Soil with farming implements", "republican"),
           ("US_020", "Original ground surface", "Natural soil with minimal artifacts", "prehistoric")
       ]
       
       # Combine all units
       all_units = modern_units + medieval_units + late_roman_units + villa_units + republican_units
       
       # Create stratigraphic unit nodes
       created_nodes = []
       for us_id, name, description, period in all_units:
           node = StratigraphicUnit(us_id)
           node.name = name
           node.description = description
           node.set_attribute("period", period)
           node.set_attribute("excavation_area", "Main Villa")
           node.set_attribute("excavation_year", "2024")
           
           # Add period-specific attributes
           if period == "imperial_roman":
               node.set_attribute("construction_technique", "opus_reticulatum")
               node.set_attribute("dating", "50-300 CE")
           elif period == "medieval":
               node.set_attribute("dating", "800-1200 CE")
           elif period == "modern":
               node.set_attribute("dating", "1800-2000 CE")
           
           graph.add_node(node)
           created_nodes.append(node)
       
       # Create stratigraphic relationships (earlier units are "before" later ones)
       relationships = [
           # Modern sequence
           ("REL_001", "US_003", "US_002", "is_before"),
           ("REL_002", "US_002", "US_001", "is_before"),
           
           # Medieval to modern transition
           ("REL_003", "US_006", "US_003", "is_before"),
           ("REL_004", "US_005", "US_003", "is_before"),
           ("REL_005", "US_004", "US_003", "is_before"),
           
           # Late Roman to medieval
           ("REL_006", "US_009", "US_004", "is_before"),
           ("REL_007", "US_008", "US_005", "is_before"),
           ("REL_008", "US_007", "US_006", "is_before"),
           
           # Imperial Roman to late Roman
           ("REL_009", "US_017", "US_009", "is_before"),
           ("REL_010", "US_016", "US_007", "is_before"),
           ("REL_011", "US_015", "US_008", "is_before"),
           ("REL_012", "US_014", "US_008", "is_before"),
           ("REL_013", "US_013", "US_008", "is_before"),
           ("REL_014", "US_012", "US_008", "is_before"),
           ("REL_015", "US_011", "US_008", "is_before"),
           ("REL_016", "US_010", "US_008", "is_before"),
           
           # Republican to Imperial Roman
           ("REL_017", "US_020", "US_017", "is_before"),
           ("REL_018", "US_019", "US_016", "is_before"),
           ("REL_019", "US_018", "US_016", "is_before"),
           
           # Contemporary relationships (same period)
           ("REL_020", "US_010", "US_011", "has_same_time"),
           ("REL_021", "US_011", "US_012", "has_same_time"),
           ("REL_022", "US_013", "US_014", "has_same_time"),
           ("REL_023", "US_014", "US_015", "has_same_time")
       ]
       
       # Add relationships to graph
       for rel_id, source, target, rel_type in relationships:
           try:
               graph.add_edge(rel_id, source, target, rel_type)
           except ValueError as e:
               graph.add_warning(f"Failed to add relationship {rel_id}: {e}")
       
       print(f"Created {len(all_units)} stratigraphic units with {len(relationships)} relationships")
       return created_nodes

   # Create stratigraphy
   stratigraphic_nodes = create_villa_stratigraphy(main_graph)

Step 4: Add Material Evidence and Special Finds
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def add_material_evidence(graph):
       """
       Add special finds and material evidence with detailed documentation.
       """
       
       # Special finds from the villa
       special_finds = [
           {
               "id": "SF_001", "name": "Bronze lamp with maker's mark",
               "description": "Volute lamp with FORTIS mark, complete",
               "context": "US_011", "material": "bronze",
               "dating": "100-150 CE", "preservation": "complete",
               "dimensions": "L: 12cm, W: 8cm, H: 3cm"
           },
           {
               "id": "SF_002", "name": "Marble portrait head",
               "description": "Portrait of middle-aged man, imperial style",
               "context": "US_010", "material": "white_marble",
               "dating": "120-180 CE", "preservation": "fragmentary",
               "dimensions": "H: 28cm, W: 20cm, D: 22cm"
           },
           {
               "id": "SF_003", "name": "Gold ring with intaglio",
               "description": "Gold ring with carnelian intaglio showing Mercury",
               "context": "US_011", "material": "gold_carnelian",
               "dating": "150-200 CE", "preservation": "complete",
               "dimensions": "Diam: 2.1cm, Weight: 8.3g"
           },
           {
               "id": "SF_004", "name": "Terra sigillata service set",
               "description": "15 vessels, Dragendorff forms 18, 27, 35",
               "context": "US_013", "material": "terra_sigillata",
               "dating": "80-120 CE", "preservation": "mostly_complete",
               "dimensions": "Various sizes"
           },
           {
               "id": "SF_005", "name": "Mosaic emblema with dolphins",
               "description": "Central medallion from atrium floor mosaic",
               "context": "US_011", "material": "stone_tesserae",
               "dating": "100-150 CE", "preservation": "complete",
               "dimensions": "Diam: 80cm"
           }
       ]
       
       # Create special find nodes
       for sf_info in special_finds:
           sf = SpecialFindUnit(sf_info["id"])
           sf.name = sf_info["name"]
           sf.description = sf_info["description"]
           
           # Set attributes
           for attr in ["material", "dating", "preservation", "dimensions"]:
               sf.set_attribute(attr, sf_info[attr])
           
           sf.set_attribute("find_number", sf_info["id"])
           sf.set_attribute("context", sf_info["context"])
           sf.set_attribute("excavation_year", "2024")
           
           graph.add_node(sf)
           
           # Connect to stratigraphic context
           context_rel_id = f"CONTEXT_{sf_info['id']}"
           graph.add_edge(context_rel_id, sf_info["id"], sf_info["context"], "extracted_from")
       
       print(f"Added {len(special_finds)} special finds")
       return special_finds

   # Add material evidence
   special_finds_data = add_material_evidence(main_graph)

Step 5: Create Comprehensive Documentation Chain
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def create_documentation_chain(graph):
       """
       Create comprehensive paradata chain linking physical evidence to documentation.
       """
       
       # Create property nodes for different types of analysis
       properties = [
           {
               "id": "PROP_001", "name": "material", "node_target": "SF_001",
               "description": "bronze", "analysis_method": "XRF_spectroscopy"
           },
           {
               "id": "PROP_002", "name": "dating", "node_target": "SF_001", 
               "description": "100-150 CE", "analysis_method": "typological_comparison"
           },
           {
               "id": "PROP_003", "name": "material", "node_target": "SF_002",
               "description": "Carrara marble", "analysis_method": "petrographic_analysis"
           },
           {
               "id": "PROP_004", "name": "style", "node_target": "SF_002",
               "description": "Antonine portrait style", "analysis_method": "art_historical_analysis"
           },
           {
               "id": "PROP_005", "name": "construction_technique", "node_target": "US_016",
               "description": "opus reticulatum", "analysis_method": "architectural_analysis"
           }
       ]
       
       # Create property nodes
       for prop_info in properties:
           prop = PropertyNode(prop_info["id"], prop_info["name"], prop_info["description"])
           prop.set_attribute("analysis_method", prop_info["analysis_method"])
           prop.set_attribute("confidence_level", "high")
           prop.set_attribute("analyst", "Dr. Elena Rossi")
           prop.set_attribute("analysis_date", "2024-05-15")
           
           graph.add_node(prop)
           
           # Connect property to its target node
           prop_rel_id = f"HAS_PROP_{prop_info['id']}"
           graph.add_edge(prop_rel_id, prop_info["node_target"], prop_info["id"], "has_property")
       
       # Create extractor nodes (information extraction processes)
       extractors = [
           {
               "id": "EXT_001", "name": "Lamp typology extraction",
               "description": "Extraction of typological data from lamp corpus",
               "source_doc": "DOC_LAMP_CORPUS", "target_prop": "PROP_002"
           },
           {
               "id": "EXT_002", "name": "Marble provenance analysis",
               "description": "Isotopic analysis results interpretation",
               "source_doc": "DOC_LAB_REPORT_001", "target_prop": "PROP_003"
           },
           {
               "id": "EXT_003", "name": "Portrait style analysis",
               "description": "Comparison with dated imperial portraits",
               "source_doc": "DOC_PORTRAIT_CATALOG", "target_prop": "PROP_004"
           }
       ]
       
       # Create additional documentation for specialized analyses
       analysis_docs = [
           {
               "id": "DOC_LAMP_CORPUS", "name": "Roman Lamp Typology Reference",
               "url": "references/lamp_typology_bailey1988.pdf",
               "type": "reference_work"
           },
           {
               "id": "DOC_LAB_REPORT_001", "name": "Marble Analysis Lab Report",
               "url": "lab_reports/marble_analysis_2024_05.pdf", 
               "type": "laboratory_report"
           },
           {
               "id": "DOC_PORTRAIT_CATALOG", "name": "Imperial Portrait Catalog",
               "url": "references/imperial_portraits_fittschen1999.pdf",
               "type": "reference_work"
           }
       ]
       
       # Add analysis documents
       for doc_info in analysis_docs:
           doc = DocumentNode(doc_info["id"], doc_info["name"], doc_info["url"])
           doc.set_attribute("document_type", doc_info["type"])
           graph.add_node(doc)
       
       # Create extractor nodes and connections
       for ext_info in extractors:
           extractor = ExtractorNode(ext_info["id"], ext_info["name"], ext_info["description"])
           extractor.set_attribute("extraction_method", "manual_analysis")
           extractor.set_attribute("analyst", "Dr. Elena Rossi")
           extractor.set_attribute("extraction_date", "2024-05-20")
           
           graph.add_node(extractor)
           
           # Connect extractor to source document
           doc_rel_id = f"EXTRACT_{ext_info['id']}"
           graph.add_edge(doc_rel_id, ext_info["id"], ext_info["source_doc"], "extracted_from")
           
           # Connect extractor to target property
           prop_rel_id = f"SUPPORTS_{ext_info['id']}"
           graph.add_edge(prop_rel_id, ext_info["target_prop"], ext_info["id"], "has_data_provenance")
       
       # Create combiner nodes for synthesized interpretations
       combiner = CombinerNode("COMB_001", "Villa dating synthesis", 
                              "Combined evidence for villa construction date")
       combiner.set_attribute("combination_method", "bayesian_synthesis")
       combiner.set_attribute("analyst", "Dr. Elena Rossi")
       combiner.set_attribute("synthesis_date", "2024-06-01")
       
       graph.add_node(combiner)
       
       # Connect combiners to multiple extractors
       graph.add_edge("COMBINES_001", "COMB_001", "EXT_001", "combines")
       graph.add_edge("COMBINES_002", "COMB_001", "EXT_003", "combines")
       
       print(f"Created documentation chain with {len(properties)} properties, "
             f"{len(extractors)} extractors, and 1 combiner")

   # Create documentation chain
   create_documentation_chain(main_graph)

Step 6: Temporal Analysis and Epoch Creation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def create_temporal_analysis(graph):
       """
       Create temporal epochs and analyze chronological relationships.
       """
       
       # Define chronological epochs for the site
       epochs = [
           {
               "id": "EPOCH_001", "name": "Prehistoric Period",
               "start_time": -3000, "end_time": -753,
               "description": "Pre-Roman settlement evidence"
           },
           {
               "id": "EPOCH_002", "name": "Republican Period", 
               "start_time": -753, "end_time": -27,
               "description": "Early Roman settlement and farming"
           },
           {
               "id": "EPOCH_003", "name": "Early Imperial Period",
               "start_time": -27, "end_time": 180,
               "description": "Villa construction and florescence"
           },
           {
               "id": "EPOCH_004", "name": "Late Imperial Period",
               "start_time": 180, "end_time": 476,
               "description": "Villa decline and abandonment"
           },
           {
               "id": "EPOCH_005", "name": "Medieval Period",
               "start_time": 476, "end_time": 1500,
               "description": "Reoccupation and partial destruction"
           },
           {
               "id": "EPOCH_006", "name": "Post-Medieval Period",
               "start_time": 1500, "end_time": 1950,
               "description": "Agricultural use and modern disturbance"
           }
       ]
       
       # Create epoch nodes
       for epoch_info in epochs:
           epoch = EpochNode(
               epoch_info["id"],
               epoch_info["name"], 
               epoch_info["start_time"],
               epoch_info["end_time"]
           )
           epoch.description = epoch_info["description"]
           epoch.set_attribute("archaeological_period", epoch_info["name"])
           
           graph.add_node(epoch)
       
       # Connect stratigraphic units to appropriate epochs
       unit_epoch_mapping = {
           "US_020": "EPOCH_001",  # Original ground surface
           "US_019": "EPOCH_002",  # Early agricultural layers
           "US_018": "EPOCH_002",  # Early farm building
           "US_017": "EPOCH_003",  # Villa floor preparation
           "US_016": "EPOCH_003",  # Villa wall foundations
           "US_015": "EPOCH_003",  # Storage rooms
           "US_014": "EPOCH_003",  # Balneum
           "US_013": "EPOCH_003",  # Kitchen area
           "US_012": "EPOCH_003",  # Peristyle garden
           "US_011": "EPOCH_003",  # Atrium floor
           "US_010": "EPOCH_003",  # Villa entrance hall
           "US_009": "EPOCH_004",  # Final occupation floor
           "US_008": "EPOCH_004",  # Abandonment deposit
           "US_007": "EPOCH_004",  # Collapse layer
           "US_006": "EPOCH_005",  # Medieval wall foundation
           "US_005": "EPOCH_005",  # Medieval hearth
           "US_004": "EPOCH_005",  # Medieval floor
           "US_003": "EPOCH_006",  # Plowing layer
           "US_002": "EPOCH_006",  # Modern fill
           "US_001": "EPOCH_006"   # Topsoil
       }
       
       # Create epoch relationships
       for unit_id, epoch_id in unit_epoch_mapping.items():
           rel_id = f"EPOCH_REL_{unit_id}"
           graph.add_edge(rel_id, unit_id, epoch_id, "has_first_epoch")
       
       print(f"Created {len(epochs)} temporal epochs with unit assignments")
       
       # Perform chronological analysis
       return analyze_site_chronology(graph, epochs)

   def analyze_site_chronology(graph, epochs):
       """
       Perform comprehensive chronological analysis of the site.
       """
       
       analysis_results = {
           "total_timespan": 0,
           "occupation_phases": [],
           "major_transitions": [],
           "continuity_evidence": []
       }
       
       # Calculate total site timespan
       earliest_epoch = min(epochs, key=lambda x: x["start_time"])
       latest_epoch = max(epochs, key=lambda x: x["end_time"])
       analysis_results["total_timespan"] = latest_epoch["end_time"] - earliest_epoch["start_time"]
       
       # Identify major occupation phases
       for epoch_info in epochs:
           epoch_node = graph.find_node_by_id(epoch_info["id"])
           
           # Count associated stratigraphic units
           epoch_edges = [e for e in graph.edges 
                         if e.edge_target == epoch_info["id"] and e.edge_type == "has_first_epoch"]
           
           phase_info = {
               "epoch_name": epoch_info["name"],
               "duration": epoch_info["end_time"] - epoch_info["start_time"],
               "unit_count": len(epoch_edges),
               "intensity": "high" if len(epoch_edges) > 3 else "medium" if len(epoch_edges) > 1 else "low"
           }
           analysis_results["occupation_phases"].append(phase_info)
       
       # Identify major transitions
       analysis_results["major_transitions"] = [
           {
               "transition": "Republican to Imperial",
               "date_range": "-27 to +50 CE",
               "evidence": "Villa construction, architectural upgrade",
               "significance": "Major investment and lifestyle change"
           },
           {
               "transition": "Imperial to Late Imperial", 
               "date_range": "180 to 300 CE",
               "evidence": "Maintenance decline, partial abandonment",
               "significance": "Economic or social disruption"
           },
           {
               "transition": "Roman to Medieval",
               "date_range": "476 to 800 CE", 
               "evidence": "Reuse of materials, different construction techniques",
               "significance": "Cultural and technological change"
           }
       ]
       
       print("Chronological Analysis Results:")
       print(f"  Total timespan: {analysis_results['total_timespan']} years")
       print(f"  Major occupation phases: {len(analysis_results['occupation_phases'])}")
       print(f"  Identified transitions: {len(analysis_results['major_transitions'])}")
       
       return analysis_results

   # Create temporal analysis
   chronological_analysis = create_temporal_analysis(main_graph)

Step 7: Data Validation and Quality Control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def validate_villa_data(graph):
       """
       Comprehensive data validation and quality control.
       """
       
       validation_report = {
           "node_validation": {},
           "edge_validation": {},
           "paradata_validation": {},
           "temporal_validation": {},
           "warnings": [],
           "recommendations": []
       }
       
       # Validate nodes
       node_types = {}
       orphaned_nodes = []
       
       for node in graph.nodes:
           # Count node types
           if node.node_type not in node_types:
               node_types[node.node_type] = 0
           node_types[node.node_type] += 1
           
           # Check for orphaned nodes (no edges)
           node_edges = [e for e in graph.edges 
                        if e.edge_source == node.node_id or e.edge_target == node.node_id]
           if not node_edges and node.node_type not in ["geo_position", "author"]:
               orphaned_nodes.append(node.node_id)
           
           # Validate required attributes
           if node.node_type == "US":
               if not node.name:
                   validation_report["warnings"].append(f"US node {node.node_id} missing name")
               if not node.get_attribute("period"):
                   validation_report["warnings"].append(f"US node {node.node_id} missing period")
           
           elif node.node_type == "SF":
               if not node.get_attribute("material"):
                   validation_report["warnings"].append(f"SF node {node.node_id} missing material")
               if not node.get_attribute("context"):
                   validation_report["warnings"].append(f"SF node {node.node_id} missing context")
       
       validation_report["node_validation"] = {
           "total_nodes": len(graph.nodes),
           "node_types": node_types,
           "orphaned_nodes": orphaned_nodes
       }
       
       # Validate edges
       edge_types = {}
       invalid_edges = []
       
       for edge in graph.edges:
           # Count edge types
           if edge.edge_type not in edge_types:
               edge_types[edge.edge_type] = 0
           edge_types[edge.edge_type] += 1
           
           # Validate edge endpoints exist
           source_node = graph.find_node_by_id(edge.edge_source)
           target_node = graph.find_node_by_id(edge.edge_target)
           
           if not source_node:
               invalid_edges.append(f"{edge.edge_id}: source {edge.edge_source} not found")
           if not target_node:
               invalid_edges.append(f"{edge.edge_id}: target {edge.edge_target} not found")
           
           # Validate connection types
           if source_node and target_node:
               if not Graph.validate_connection(source_node.node_type, 
                                              target_node.node_type, 
                                              edge.edge_type):
                   invalid_edges.append(f"{edge.edge_id}: invalid connection type")
       
       validation_report["edge_validation"] = {
           "total_edges": len(graph.edges),
           "edge_types": edge_types,
           "invalid_edges": invalid_edges
       }
       
       # Validate paradata chains
       stratigraphic_nodes = graph.get_nodes_by_type("US")
       paradata_stats = {
           "complete_chains": 0,
           "partial_chains": 0,
           "missing_chains": 0,
           "average_properties": 0,
           "average_documents": 0
       }
       
       total_properties = 0
       total_documents = 0
       
       for node in stratigraphic_nodes:
           paradata = graph.get_complete_paradata_chain(node.node_id)
           
           prop_count = len(paradata["properties"])
           doc_count = len(paradata["documents"])
           
           total_properties += prop_count
           total_documents += doc_count
           
           if prop_count > 0 and doc_count > 0:
               paradata_stats["complete_chains"] += 1
           elif prop_count > 0 or doc_count > 0:
               paradata_stats["partial_chains"] += 1
           else:
               paradata_stats["missing_chains"] += 1
               validation_report["warnings"].append(f"Node {node.node_id} has no paradata")
       
       if stratigraphic_nodes:
           paradata_stats["average_properties"] = total_properties / len(stratigraphic_nodes)
           paradata_stats["average_documents"] = total_documents / len(stratigraphic_nodes)
       
       validation_report["paradata_validation"] = paradata_stats
       
       # Validate temporal consistency
       temporal_issues = []
       temporal_edges = [e for e in graph.edges if e.edge_type == "is_before"]
       
       # Check for potential circular dependencies in temporal relationships
       from collections import defaultdict, deque
       
       adj_list = defaultdict(list)
       in_degree = defaultdict(int)
       
       for edge in temporal_edges:
           adj_list[edge.edge_source].append(edge.edge_target)
           in_degree[edge.edge_target] += 1
       
       # Topological sort to detect cycles
       queue = deque([node for node in adj_list.keys() if in_degree[node] == 0])
       processed = 0
       
       while queue:
           current = queue.popleft()
           processed += 1
           
           for neighbor in adj_list[current]:
               in_degree[neighbor] -= 1
               if in_degree[neighbor] == 0:
                   queue.append(neighbor)
       
       if processed < len(adj_list):
           temporal_issues.append("Circular dependency detected in temporal relationships")
       
       validation_report["temporal_validation"] = {
           "temporal_edges": len(temporal_edges),
           "temporal_issues": temporal_issues
       }
       
       # Generate recommendations
       if len(orphaned_nodes) > 0:
           validation_report["recommendations"].append(f"Connect {len(orphaned_nodes)} orphaned nodes")
       
       if paradata_stats["missing_chains"] > 0:
           validation_report["recommendations"].append(f"Add paradata for {paradata_stats['missing_chains']} stratigraphic units")
       
       if len(invalid_edges) > 0:
           validation_report["recommendations"].append(f"Fix {len(invalid_edges)} invalid edges")
       
       # Print validation summary
       print("\nData Validation Report")
       print("=" * 40)
       print(f"Nodes: {validation_report['node_validation']['total_nodes']}")
       print(f"Edges: {validation_report['edge_validation']['total_edges']}")
       print(f"Warnings: {len(validation_report['warnings'])}")
       print(f"Recommendations: {len(validation_report['recommendations'])}")
       
       if validation_report["warnings"]:
           print("\nWarnings:")
           for warning in validation_report["warnings"][:5]:  # Show first 5
               print(f"  - {warning}")
           if len(validation_report["warnings"]) > 5:
               print(f"  ... and {len(validation_report['warnings']) - 5} more")
       
       if validation_report["recommendations"]:
           print("\nRecommendations:")
           for rec in validation_report["recommendations"]:
               print(f"  - {rec}")
       
       return validation_report

   # Validate data
   validation_results = validate_villa_data(main_graph)

Step 8: Export and Sharing
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def export_villa_project(graph, project_manager):
       """
       Export the complete villa project in multiple formats.
       """
       
       import os
       import json
       from datetime import datetime
       
       # Create export directory
       export_dir = "villa_rustica_export"
       os.makedirs(export_dir, exist_ok=True)
       
       # 1. Export comprehensive JSON
       print("Exporting comprehensive JSON...")
       json_data = {
           "project_metadata": {
               "graph_id": graph.graph_id,
               "name": graph.name,
               "description": graph.description,
               "data": graph.data,
               "export_date": datetime.now().isoformat(),
               "export_version": "1.0"
           },
           "nodes": [],
           "edges": [],
           "statistics": {
               "total_nodes": len(graph.nodes),
               "total_edges": len(graph.edges),
               "node_types": {},
               "edge_types": {}
           }
       }
       
       # Export nodes with full information
       node_types = {}
       for node in graph.nodes:
           node_data = {
               "node_id": node.node_id,
               "node_type": node.node_type,
               "name": getattr(node, 'name', ''),
               "description": getattr(node, 'description', ''),
               "attributes": getattr(node, 'attributes', {})
           }
           
           # Add type-specific data
           if hasattr(node, 'start_time'):  # EpochNode
               node_data["temporal_data"] = {
                   "start_time": node.start_time,
                   "end_time": node.end_time
               }
           
           json_data["nodes"].append(node_data)
           
           # Count node types
           if node.node_type not in node_types:
               node_types[node.node_type] = 0
           node_types[node.node_type] += 1
       
       json_data["statistics"]["node_types"] = node_types
       
       # Export edges
       edge_types = {}
       for edge in graph.edges:
           edge_data = {
               "edge_id": edge.edge_id,
               "source": edge.edge_source,
               "target": edge.edge_target,
               "edge_type": edge.edge_type,
               "label": getattr(edge, 'label', ''),
               "description": getattr(edge, 'description', '')
           }
           json_data["edges"].append(edge_data)
           
           # Count edge types
           if edge.edge_type not in edge_types:
               edge_types[edge.edge_type] = 0
           edge_types[edge.edge_type] += 1
       
       json_data["statistics"]["edge_types"] = edge_types
       
       # Save comprehensive JSON
       with open(f"{export_dir}/villa_complete.json", 'w', encoding='utf-8') as f:
           json.dump(json_data, f, indent=2, ensure_ascii=False)
       
       # 2. Export to CSV for analysis
       print("Exporting CSV files...")
       export_to_csv(graph, export_dir)
       
       # 3. Create project summary report
       print("Creating project summary...")
       summary_report = generate_project_summary(graph, validation_results, chronological_analysis)
       
       with open(f"{export_dir}/project_summary.md", 'w', encoding='utf-8') as f:
           f.write(summary_report)
       
       # 4. Export paradata chains
       print("Exporting paradata documentation...")
       paradata_export = export_paradata_chains(graph)
       
       with open(f"{export_dir}/paradata_chains.json", 'w', encoding='utf-8') as f:
           json.dump(paradata_export, f, indent=2, ensure_ascii=False)
       
       print(f"\nExport completed to {export_dir}/")
       print("Generated files:")
       print("  - villa_complete.json (comprehensive graph data)")
       print("  - nodes.csv, edges.csv, stratigraphic_units.csv (tabular data)")
       print("  - project_summary.md (human-readable report)")
       print("  - paradata_chains.json (documentation lineages)")
       
       return export_dir

   # Export the complete project
   export_directory = export_villa_project(main_graph, project_manager)

   print(f"\n✅ Complete Roman Villa workflow finished!")
   print(f"📁 Project exported to: {export_directory}")
   print(f"🏛️ {len(main_graph.nodes)} nodes and {len(main_graph.edges)} relationships documented")

Multi-Site Comparative Analysis
-------------------------------

Workflow 2: Regional Settlement Pattern Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def comparative_settlement_analysis():
       """
       Analyze settlement patterns across multiple sites in a region.
       """
       
       manager = MultiGraphManager()
       
       # Load multiple site graphs
       sites = [
           {"file": "villa_rustica_a.graphml", "id": "VillaA", "type": "villa"},
           {"file": "villa_rustica_b.graphml", "id": "VillaB", "type": "villa"}, 
           {"file": "urban_house_rome.graphml", "id": "UrbanHouse", "type": "urban"},
           {"file": "rural_settlement.graphml", "id": "RuralSite", "type": "rural"},
           {"file": "sanctuary_site.graphml", "id": "Sanctuary", "type": "religious"}
       ]
       
       loaded_graphs = {}
       
       for site_info in sites:
           try:
               graph_id = manager.load_graph(site_info["file"], site_info["id"])
               graph = manager.get_graph(graph_id)
               graph.set_attribute("site_type", site_info["type"])
               loaded_graphs[site_info["id"]] = graph
               print(f"Loaded {site_info['id']}: {len(graph.nodes)} nodes")
           except Exception as e:
               print(f"Failed to load {site_info['file']}: {e}")
       
       # Comparative analysis
       analysis_results = perform_comparative_analysis(loaded_graphs)
       
       # Generate comparative report
       generate_comparative_report(analysis_results)
       
       return loaded_graphs, analysis_results

   def perform_comparative_analysis(graphs):
       """Perform comprehensive comparative analysis across sites."""
       
       analysis = {
           "site_statistics": {},
           "chronological_comparison": {},
           "material_culture_comparison": {},
           "architectural_comparison": {},
           "settlement_patterns": {}
       }
       
       # Collect statistics for each site
       for site_id, graph in graphs.items():
           stats = {
               "total_nodes": len(graph.nodes),
               "total_edges": len(graph.edges),
               "stratigraphic_units": len(graph.get_nodes_by_type("US")),
               "special_finds": len(graph.get_nodes_by_type("SF")),
               "site_type": graph.get_attribute("site_type", "unknown"),
               "temporal_span": calculate_temporal_span(graph),
               "material_types": analyze_material_types(graph),
               "architectural_features": analyze_architectural_features(graph)
           }
           analysis["site_statistics"][site_id] = stats
       
       # Chronological comparison
       analysis["chronological_comparison"] = compare_site_chronologies(graphs)
       
       # Material culture comparison  
       analysis["material_culture_comparison"] = compare_material_culture(graphs)
       
       # Architectural comparison
       analysis["architectural_comparison"] = compare_architecture(graphs)
       
       return analysis

   # Run comparative analysis
   comparative_results = comparative_settlement_analysis()

Advanced Workflow Features
--------------------------

Integration with External Tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Blender Integration
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def export_for_blender_visualization(graph):
       """
       Export graph data in format suitable for Blender EM-tools visualization.
       """
       
       # Create Blender-compatible export
       blender_data = {
           "metadata": {
               "format_version": "em_tools_1.5",
               "coordinate_system": "local",
               "scale_factor": 1.0
           },
           "stratigraphic_units": [],
           "temporal_phases": [],
           "spatial_relationships": []
       }
       
       # Export stratigraphic units with 3D coordinates
       us_nodes = graph.get_nodes_by_type("US")
       for node in us_nodes:
           unit_data = {
               "id": node.node_id,
               "name": node.name,
               "description": node.description,
               "material": node.get_attribute("material", "unknown"),
               "period": node.get_attribute("period", "unknown"),
               "coordinates": {
                   "x": node.get_attribute("x_coord", 0.0),
                   "y": node.get_attribute("y_coord", 0.0), 
                   "z": node.get_attribute("z_coord", 0.0)
               },
               "dimensions": {
                   "length": node.get_attribute("length", 1.0),
                   "width": node.get_attribute("width", 1.0),
                   "height": node.get_attribute("height", 0.1)
               }
           }
           blender_data["stratigraphic_units"].append(unit_data)
       
       # Export temporal phases
       epochs = graph.get_nodes_by_type("epoch")
       for epoch in epochs:
           phase_data = {
               "id": epoch.node_id,
               "name": epoch.name,
               "start_time": getattr(epoch, 'start_time', 0),
               "end_time": getattr(epoch, 'end_time', 0),
               "color": epoch.get_attribute("display_color", "#888888")
           }
           blender_data["temporal_phases"].append(phase_data)
       
       # Export spatial relationships
       spatial_edges = [e for e in graph.edges 
                       if e.edge_type in ["is_before", "has_same_time", "changed_from"]]
       for edge in spatial_edges:
           rel_data = {
               "source": edge.edge_source,
               "target": edge.edge_target,
               "relationship_type": edge.edge_type,
               "strength": 1.0
           }
           blender_data["spatial_relationships"].append(rel_data)
       
       # Save for Blender import
       with open("blender_export.json", 'w') as f:
           json.dump(blender_data, f, indent=2)
       
       print("Exported graph data for Blender EM-tools visualization")
       return blender_data

   # Usage
   blender_export = export_for_blender_visualization(main_graph)

Web Publication Integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def create_web_publication(graph):
       """
       Create web-ready publication format with interactive elements.
       """
       
       web_publication = {
           "title": graph.name.get("en", graph.graph_id),
           "description": graph.description.get("en", ""),
           "metadata": {
               "authors": [node.name for node in graph.get_nodes_by_type("author")],
               "publication_date": "2024-01-15",
               "license": graph.data.get("license", "CC BY 4.0"),
               "doi": "10.1000/example.doi"
           },
           "sections": {
               "introduction": generate_introduction_section(graph),
               "methodology": generate_methodology_section(graph),
               "results": generate_results_section(graph),
               "discussion": generate_discussion_section(graph),
               "conclusions": generate_conclusions_section(graph)
           },
           "interactive_elements": {
               "stratigraphic_matrix": create_interactive_matrix(graph),
               "temporal_timeline": create_temporal_timeline(graph),
               "find_catalog": create_find_catalog(graph),
               "documentation_tree": create_documentation_tree(graph)
           },
           "datasets": {
               "raw_data": "data/villa_raw_data.csv",
               "processed_graph": "data/villa_graph.json",
               "analysis_results": "data/analysis_results.json"
           }
       }
       
       # Save web publication package
       import json
       with open("web_publication.json", 'w') as f:
           json.dump(web_publication, f, indent=2)
       
       print("Created web publication package")
       return web_publication

   # Usage
   web_pub = create_web_publication(main_graph)

This comprehensive workflow example demonstrates the full capability of s3dgraphy for complex archaeological projects, from initial setup through final analysis and reporting.
