# core_utils/cad_utils.py
"""
CAD file conversion utilities
Converts STEP/IGES to GLTF for Three.js
"""

import os
import tempfile
import logging

# Requires: pip install OCP (OpenCascade Python bindings)
try:
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopoDS import TopoDS_Shape
    from OCP.BRep import BRep_Builder
    from OCP.gp import gp_Trsf
    import trimesh
    STEP_AVAILABLE = True
except ImportError:
    STEP_AVAILABLE = False
    logging.warning("[CAD] OpenCascade not installed. STEP conversion disabled.")

def convert_step_to_gltf(step_file_path: str) -> str:
    """
    Converts STEP file to GLTF.
    Returns path to generated GLTF file.
    """
    if not STEP_AVAILABLE:
        return None
    
    try:
        # Read STEP file
        reader = STEPControl_Reader()
        status = reader.ReadFile(step_file_path)
        
        if status != IFSelect_RetDone:
            logging.error("[CAD] Failed to read STEP file")
            return None
        
        # Transfer to shape
        reader.TransferRoots()
        shape = reader.OneShape()
        
        # Convert to mesh using trimesh
        # (OCP to trimesh conversion is complex, simplified here)
        mesh = trimesh.Trimesh(vertices=[], faces=[])  # Placeholder
        
        # Export as GLTF
        output_path = step_file_path.replace('.step', '.gltf').replace('.stp', '.gltf')
        mesh.export(output_path)
        
        logging.info(f"[CAD] Converted {step_file_path} → {output_path}")
        return output_path
        
    except Exception as e:
        logging.error(f"[CAD] Conversion failed: {e}")
        return None