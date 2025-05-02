import bpy
import bmesh  # Import bmesh for mesh operations
import sys
import argparse
import csv
import numpy as np

def purge_orphans():
    """
    Remove all orphan data blocks

    see this from more info:
    https://youtu.be/3rNqVPtbhzc?t=149
    """
    if bpy.app.version >= (3, 0, 0):
        # run this only for Blender versions 3.0 and higher
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    else:
        # run this only for Blender versions lower than 3.0
        # call purge_orphans() recursively until there are no more orphan data blocks to purge
        result = bpy.ops.outliner.orphans_purge()
        if result.pop() != "CANCELLED":
            purge_orphans()


def clean_scene():
    """
    Removing all of the objects, collection, materials, particles,
    textures, images, curves, meshes, actions, nodes, and worlds from the scene

    Checkout this video explanation with example

    "How to clean the scene with Python in Blender (with examples)"
    https://youtu.be/3rNqVPtbhzc
    """
    # make sure the active object is not in Edit Mode
    if bpy.context.active_object and bpy.context.active_object.mode == "EDIT":
        bpy.ops.object.editmode_toggle()

    # make sure non of the objects are hidden from the viewport, selection, or disabled
    for obj in bpy.data.objects:
        obj.hide_set(False)
        obj.hide_select = False
        obj.hide_viewport = False

    # select all the object and delete them (just like pressing A + X + D in the viewport)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # find all the collections and remove them
    collection_names = [col.name for col in bpy.data.collections]
    for name in collection_names:
        bpy.data.collections.remove(bpy.data.collections[name])

    # in the case when you modify the world shader
    # delete and recreate the world object
    world_names = [world.name for world in bpy.data.worlds]
    for name in world_names:
        bpy.data.worlds.remove(bpy.data.worlds[name])
    # create a new world data block
    bpy.ops.world.new()
    bpy.context.scene.world = bpy.data.worlds["World"]

    purge_orphans()


def active_object():
    """
    returns the currently active object
    """
    return bpy.context.active_object


clean_scene()


# Parse arguments from the command line
parser = argparse.ArgumentParser(description="Blender script to process CSV data.")
parser.add_argument("csv_file", help="Path to the input CSV file")
parser.add_argument("output_file", help="Path to save the output CSV with normals")

# Extract arguments from Blender's sys.argv (skip Blender's own arguments)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

csv_file_path = args.csv_file
output_file = args.output_file
spacing = args.spacing

print(f"Input CSV: {csv_file_path}")
print(f"Output CSV: {output_file}")
print(f"Step: {spacing} mm")

# print(csv_file_path,output_file)

# Step 1: Read CSV file and convert to curve

# Set the path to your CSV file
# csv_file_path = r"Z:\Asax\Jiajun\Data\A_Real_Positions0311.csv"
# output_file = r"Z:\Asax\Jiajun\Data\A_mesh_lines_normals_test.csv"  # Absolute path for output file

# Create a new curve object
bpy.ops.object.select_all(action='DESELECT')  # Deselect all objects
bpy.ops.object.add(type='CURVE')  # Add a new curve
curve = bpy.context.object
curve.name = 'ImportedCurve'
curve.data.dimensions = '3D'

# Read the CSV file and count the number of rows
with open(csv_file_path, 'r') as file_path:
    reader = csv.reader(file_path, delimiter=" ")  # Set delimiter to space
    next(reader)  # Skip header row if needed
    vertices = [tuple(map(float, row)) for row in reader]

# Create the spline with the correct number of points
spline = curve.data.splines.new('POLY')
spline.points.add(count=len(vertices) - 1)  # Create enough points for the vertices

# Set the coordinates of each point in the spline
for i, (x, y, z) in enumerate(vertices):
    spline.points[i].co = (x, y, 0, 1)  # Set the coordinates

# Optionally, adjust curve settings like resolution or type
curve.data.resolution_u = float(spacing)   # Smoothness of the curve

# Step 2 apply geometry nodes
# Create a new Geometry Nodes modifier and set up nodes

bpy.ops.node.new_geometry_nodes_modifier()
node_tree = bpy.data.node_groups["Geometry Nodes"]

# Create geometry nodes in the node tree
out_node = node_tree.nodes["Group Output"]
input_node = node_tree.nodes["Group Input"]

# Create Curve to Points node and set length
curve_to_point_node = node_tree.nodes.new(type="GeometryNodeCurveToPoints")
curve_to_point_node.mode = 'LENGTH'
curve_to_point_node.inputs[2].default_value = 0.2  # step = 0.2

# Create Point to Curve node
point_to_curve_node = node_tree.nodes.new(type="GeometryNodePointsToCurves")

# Link nodes
node_tree.links.new(input_node.outputs["Geometry"], curve_to_point_node.inputs["Curve"])
node_tree.links.new(curve_to_point_node.outputs["Points"], point_to_curve_node.inputs["Points"])
node_tree.links.new(point_to_curve_node.outputs["Curves"], out_node.inputs["Geometry"])

# Step 3: Get normals from extruded mesh

active_object()

bpy.ops.object.convert(target='MESH')  # Convert curve to mesh

bpy.ops.object.mode_set(mode='EDIT')  # Switch to edit mode
bpy.ops.mesh.select_all(action='SELECT')  # Select all vertices

# Extrude the geometry along Z-axis
bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, 10)})

bpy.ops.object.mode_set(mode='OBJECT')  # Switch back to object mode

# Save the normals of the vertices
obj = bpy.context.object

if obj and obj.type == 'MESH':
    # Get mesh data and use bmesh for normal calculation
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()

    # Get all vertices and compute the halfway point
    verts = list(bm.verts)  # Convert to list for slicing
    half_index = len(verts) // 2  # Get the midpoint

    # Open a CSV file to save the output
    with open(output_file, mode='w', newline='') as f:
        writer = csv.writer(f)

        # Write the header row
        writer.writerow(["Vertex_X", "Vertex_Y", "Vertex_Z", "Normal_X", "Normal_Y", "Normal_Z"])

        # Write only the first half of the vertex coordinates and normal vectors
        for vert in verts[:half_index]:
            writer.writerow([vert.co.x, vert.co.y, vert.co.z, vert.normal.x, vert.normal.y, vert.normal.z])

    bm.free()  # Free the bmesh data
    print(f"Exported first half of vertex normals to {output_file}")

else:
    print("No valid mesh object selected.")
