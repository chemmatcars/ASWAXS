import subprocess
import sys

input_csv  = sys.argv[1]
output_csv = sys.argv[2]
spacing = sys.argv[3]

# Path to Blender executable (since it's added to system settings, you can use 'blender')
blender_command = "blender"

# Path to the Python script you want to run inside Blender
script_path = "Blender_Macro.py"

# Input and output CSV files
# input_csv = "Z:\Asax\Jiajun\Data\A_Real_Positions0313.csv"
# output_csv = "Z:\Asax\Jiajun\Data\output_test_data.csv"

# Command to run Blender with the Python script
command = [
    blender_command,
    "--background",  # Run Blender in background mode (no GUI)
    "--python", script_path,  # Python script to run
    "--",  # Separator between Blender arguments and script arguments
    input_csv,  # Input CSV file
    output_csv,  # Output CSV file
    spacing
]

# Run the command
subprocess.run(command)
