## Crop Intensity Data Perpendicular to Flow Channel ver.1.4


import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import sys
from PIL import Image
import os
import h5py
from scipy.optimize import curve_fit

class RoiCropperApp(QtWidgets.QMainWindow):
    def __init__(self, file_path=None, experiment_index=4, normal_vector_path = None):
        super().__init__()
        self.experiment_index = experiment_index
        self.normal_vector_path = normal_vector_path
        self.file_path = file_path
        self.setWindowTitle("PyQtGraph ROI Cropper")
        self.resize(1200, 700)

        # Create central widget with horizontal layout
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # Image layout
        self.image_layout = QtWidgets.QHBoxLayout()

        # Left side - original image with ROI
        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.view_box = self.graphics_layout.addViewBox()
        self.view_box.setAspectLocked(True)
        self.img_item = pg.ImageItem()
        self.view_box.addItem(self.img_item)

        # Bottom side - Intensity profile
        self.profile_layout = pg.GraphicsLayoutWidget()
        self.profile_plot = self.profile_layout.addPlot(title="Averaged Intensity Profile")
        self.profile_curve = self.profile_plot.plot(pen='b')

        # Add both image views to image layout
        self.image_layout.addWidget(self.graphics_layout)
        self.image_layout.addWidget(self.profile_layout)

        # Control layout
        self.control_layout = QtWidgets.QHBoxLayout()

        # File controls
        self.file_group = QtWidgets.QGroupBox("File")
        self.file_layout = QtWidgets.QVBoxLayout()
        self.load_button = QtWidgets.QPushButton("Load HDF")
        self.load_button.clicked.connect(self.load_image)
        self.file_layout.addWidget(self.load_button)
        self.file_group.setLayout(self.file_layout)
        self.control_layout.addWidget(self.file_group)

        # Create a SpinBox for setting the experiment_index
        self.experiment_index_spinbox = QtWidgets.QSpinBox()
        self.experiment_index_spinbox.setRange(0, 100)  # Adjust range if necessary
        self.experiment_index_spinbox.setValue(self.experiment_index)
        self.experiment_index_spinbox.valueChanged.connect(self.update_experiment_index)
        self.set_experiment_index_button = QtWidgets.QPushButton('Set Experiment Index')
        self.set_experiment_index_button.clicked.connect(self.update_experiment_index)

        # Add SpinBox and button to the control layout
        self.control_layout.addWidget(self.experiment_index_spinbox)
        self.control_layout.addWidget(self.set_experiment_index_button)

        # ROI controls
        self.roi_group = QtWidgets.QGroupBox("ROI")
        self.roi_layout = QtWidgets.QVBoxLayout()

        # ROI type selection
        self.roi_type_combo = QtWidgets.QComboBox()
        self.roi_type_combo.addItems(["Rectangle"])
        self.roi_layout.addWidget(QtWidgets.QLabel("ROI Type:"))
        self.roi_layout.addWidget(self.roi_type_combo)

        # ROI size and angle manual inputs
        self.manual_size_layout = QtWidgets.QFormLayout()
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(10, 1000)
        self.width_spin.setValue(200)
        self.height_spin = QtWidgets.QSpinBox()
        self.height_spin.setRange(10, 1000)
        self.height_spin.setValue(100)
        self.angle_spin = QtWidgets.QLineEdit("0")


        self.manual_size_layout.addRow("Width:", self.width_spin)
        self.manual_size_layout.addRow("Height:", self.height_spin)
        self.manual_size_layout.addRow("Angle:", self.angle_spin)
        self.roi_layout.addLayout(self.manual_size_layout)

        self.apply_manual_button = QtWidgets.QPushButton("Apply Manual Settings")
        self.apply_manual_button.clicked.connect(self.apply_manual_roi)
        self.roi_layout.addWidget(self.apply_manual_button)

        self.roi_group.setLayout(self.roi_layout)
        self.control_layout.addWidget(self.roi_group)

        # Output controls
        self.output_group = QtWidgets.QGroupBox("Output")
        self.output_layout = QtWidgets.QVBoxLayout()

        self.save_original_button = QtWidgets.QPushButton("Save Original Image")
        self.save_original_button.clicked.connect(self.save_original_image)
        self.output_layout.addWidget(self.save_original_button)

        self.save_cropped_button = QtWidgets.QPushButton("Save Cropped Image")
        self.save_cropped_button.clicked.connect(self.save_cropped_image)
        self.output_layout.addWidget(self.save_cropped_button)

        self.output_group.setLayout(self.output_layout)
        self.control_layout.addWidget(self.output_group)

        # Add layouts to main layout
        self.main_layout.addLayout(self.image_layout)
        self.main_layout.addLayout(self.control_layout)

        # Initialize variables
        self.image_data = None
        self.cropped_result = None
        self.roi = None

        # If file path is provided, load the image
        if self.file_path is not None:
            self.load_h5_file(self.file_path)


    def update_experiment_index(self):
        """Update the experiment index from the SpinBox value."""
        self.experiment_index = self.experiment_index_spinbox.value()
        print(f"Experiment Index set to: {self.experiment_index}")

    def load_image(self):
        """Load an HDF5 file from disk."""

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Image", "", "HDF5 Files (*.h5 *.hdf5)"
        )

        if file_path:
            self.file_path = file_path  # ✅ Store as instance variable
            try:
                self.load_h5_file(self.file_path)  # ✅ Use the instance variable
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to load file: {str(e)}"
                )

    def load_h5_file(self, file_path):
        """Load an image dataset from an HDF5 file."""
        with h5py.File(file_path, 'r') as f:
            dataset_path = 'entry/data/data'  # Adjust this based on your file structure
            if dataset_path not in f:
                raise ValueError(f"Dataset '{dataset_path}' not found in file")

            data = f[dataset_path][:]

        # Normalize if needed (assumed signed byte)
        img = np.where(data < 0, data + 256, data)
        self.set_image(img)

        self.setWindowTitle(f"PyQtGraph ROI Cropper - {os.path.basename(file_path)}")

    def set_image(self, image_data):
        """Set the image data and initialize the ROI."""

        # Clear the previous image and ROI
        if self.image_data is not None:
            self.image_data = None
            self.img_item.clear()  # Clear the previous image from the graphics item

        # Remove existing ROI if any
        if self.roi is not None:
            self.view_box.removeItem(self.roi)
            self.roi = None  # Reset the ROI

        self.image_data = image_data
        self.img_item.setImage(image_data)

        # Reset view
        self.view_box.autoRange()

        # Remove existing ROI if any
        if self.roi is not None:
            self.view_box.removeItem(self.roi)

        # Default ROI parameters
        roi_size = [240, 50]
        default_angle = 0  # Default angle will be overridden if normal vector is loaded

        # Try to load normal vector for default angle if base_filename is set

        angle_deg, normal_vector = self.load_normal_vector_from_file(self.normal_vector_path, self.experiment_index)
        if angle_deg is not None:
            default_angle = angle_deg

        x_center = image_data.shape[0] // 2
        y_center = image_data.shape[1] // 2

        # Create ROI based on current selection with the default angle
        if self.roi_type_combo.currentText() == "Rectangle":
            self.roi = pg.RectROI(
                [x_center - roi_size[0] // 2, y_center - roi_size[1] // 2],
                [roi_size[0], roi_size[1]],
                pen='r',
                rotatable=True,
                resizable=False,
                movable=True
            )

            self.roi.addRotateHandle(
                (1, 1),
                (0.5, 0.5)
            )
            self.view_box.addItem(self.roi)
            self.roi.sigRegionChangeFinished.connect(self.update_cropped_image)

            # Set the calculated angle
            self.roi.setAngle(default_angle, (0.5, 0.5))

    def update_cropped_image(self):
        """Extract the ROI from the original image and display the cropped result."""
        if self.image_data is None:
            return

        # Get the ROI data as a rectangular array
        cropped_data = self.roi.getArrayRegion(self.image_data, self.img_item)

        # Store the result
        self.cropped_result = cropped_data

        # Update manual inputs to match ROI
        pos = self.roi.pos()
        size = self.roi.size()
        angle = self.roi.angle()

        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.angle_spin.blockSignals(True)

        self.width_spin.setValue(int(size[0]))
        self.height_spin.setValue(int(size[1]))
        self.angle_spin.setText("%.3f" % angle)

        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)
        self.angle_spin.blockSignals(False)

        gray_image = 0.2989 * self.cropped_result[:, :, 0] + 0.5870 * self.cropped_result[:, :,
                                                                      1] + 0.1140 * self.cropped_result[:, :, 2]
        line_data = np.sum(gray_image, 1)

        self.profile_curve.setData(line_data)

        # Save the intensity data into txt file
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        file_path = os.path.dirname(self.file_path) # Get the directory where the HDF5 file is located
        output_txt_file = os.path.join(file_path, f"{base_name}_cropped.txt")
        try:
            np.savetxt(output_txt_file, line_data, fmt='%.4e')
            print(f"Saved cropped gray image data to {output_txt_file}")
        except Exception as e:
            print(f"Error saving cropped gray image data: {e}")


    def apply_manual_roi(self):
        """Apply manually specified ROI parameters."""
        if self.image_data is None:
            return

        width = self.width_spin.value()
        height = self.height_spin.value()
        angle = float(self.angle_spin.text())

        x_center = self.image_data.shape[0] // 2
        y_center = self.image_data.shape[1] // 2

        # Create the ROI with the manually set parameters
        self.roi = pg.RectROI(
            [x_center - width // 2, y_center - height // 2],
            [width, height],
            pen='r',
            rotatable=True,
            resizable=False,
            movable=True
        )

        self.roi.addRotateHandle(
            (1, 1),
            (0.5, 0.5)
        )

        self.view_box.addItem(self.roi)
        self.roi.sigRegionChangeFinished.connect(self.update_cropped_image)

        # Apply the specified angle
        self.roi.setAngle(angle, (0.5, 0.5))

    def load_normal_vector_from_file(self, normal_file_path, experiment_index=0):
        """Load normal vector from file based on the experiment index."""
        try:
            import pandas as pd
            print(normal_file_path)
            df = pd.read_csv(normal_file_path)
            print('read done')
            if 'Normal_X' not in df.columns or 'Normal_Y' not in df.columns:
                raise ValueError("CSV must contain 'Normal_X' and 'Normal_Y' columns")

            row_index = experiment_index   # Adjust this if you have multiple rows per experiment

            x_normal = df.loc[row_index, 'Normal_X']
            y_normal = df.loc[row_index, 'Normal_Y']
            normal_vector = [x_normal, y_normal]
            print(f"Normal Vector: {normal_vector}")
            print(f"number {experiment_index}")
            magnitude = np.sqrt(x_normal ** 2 + y_normal ** 2)
            dot_product = x_normal
            angle_rad = np.arccos(dot_product / magnitude)
            angle_deg = np.degrees(angle_rad)

            if y_normal < 0:
                angle_deg = -angle_deg
            angle_deg -= 90

            print(f"Loaded normal vector: ({x_normal}, {y_normal})")
            print(f"Calculated angle: {angle_deg} degrees")
            return angle_deg, normal_vector

        except Exception as e:
            print(f"Failed to load normal vector: {str(e)}")
            return None

    def save_original_image(self):
        """Save the original image to disk."""
        if self.image_data is not None:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Original Image", "", "Image Files (*.png *.jpg)"
            )
            if file_path:
                Image.fromarray(self.image_data).save(file_path)

    def save_cropped_image(self):
        """Save the cropped image to disk."""
        if self.cropped_result is not None:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Cropped Image", "", "Image Files (*.png *.jpg)"
            )
            if file_path:
                Image.fromarray(self.cropped_result).save(file_path)


# Example usage
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    # Define the file path
    file_path = "Z:/Asax/Jiajun/Data/A_50uL_min_HR3/A_50uL_min_HR3_000.h5"
    normal_vector_path = "Z:/Asax/Jiajun/Data/A_mesh_lines_normals_test.csv"
    window = RoiCropperApp(file_path=file_path, experiment_index=0,normal_vector_path = normal_vector_path)
    window.show()
    app.exec_()
