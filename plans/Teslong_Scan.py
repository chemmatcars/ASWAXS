## Teslong Image Capture Scripts
# Autofocuse funtion
# Syringe pump control functions
# Image capture and save into HDF functions
# ver 1.0: fixed live table display in the queue server when running capture image function
# !!! Saving path need to be setup first

from ophyd import EpicsSignal, EpicsMotor
import pandas as pd
from ophyd.signal import EpicsSignal
from bluesky.preprocessors import run_decorator
from bluesky.plan_stubs import mv, mvr, sleep,trigger_and_read
import epics
import numpy as np
import cv2
import os

## Initiate Motor control
sx = EpicsMotor('15IDD:m19', name='sx')
sy = EpicsMotor('15IDD:m18', name='sy')
cmir = EpicsMotor('15IDD:m7', name='cmir')

## Pump parameters
phdUltra_pump_flowrate = EpicsSignal('15IDD:PHDUltra:InfuseRate', string=True)
phdUltra_pump_infuse = EpicsSignal('15IDD:PHDUltra:Infuse', string=True)
phdUltra_pump_targetvolume = EpicsSignal('15IDD:PHDUltra:TargetVolume', string=True)

## Initialize HDF1 setup
Teslong_file_path = EpicsSignal('Teslong:HDF1:FilePath', string=True)
Teslong_file_number = EpicsSignal('Teslong:HDF1:FileNumber')
Teslong_file_name = EpicsSignal('Teslong:HDF1:FileName', string=True)
Teslong_full_file_name = EpicsSignal('Teslong:HDF1:FullFileName_RBV', string=True)
Teslong_file_template = EpicsSignal('Teslong:HDF1:FileTemplate', string=True)
Teslong_enable_callbacks = EpicsSignal('Teslong:HDF1:EnableCallbacks')
Teslong_write_file = EpicsSignal('Teslong:HDF1:WriteFile')
Teslong_image_mode = EpicsSignal('Teslong:cam1:ImageMode')
Teslongacquire_state = EpicsSignal('Teslong:cam1:Acquire')
Teslong_auto_increment = EpicsSignal('Teslong:HDF1:AutoIncrement')
Teslong_acquire_data = EpicsSignal('Teslong:cam1:Acquire')
Teslong_num_images = EpicsSignal('Teslong:cam1:NumImages')
Teslong_HDF_path_exist = EpicsSignal('Teslong:HDF1:FilePathExists_RBV')

Teslong_file_number.put(0)

Teslong_file_template.put('%s%s_%3.3d.h5')

# Set camera to multiple mode and put a number of images captured in multiple mode
# Teslong_image_mode.put(0)
# Teslong_num_images.put(60)

# Enable HDF1
Teslong_enable_callbacks.put(0)

# Turn off auto increment
Teslong_auto_increment.put(0)

def set_infuse_flowrate_phdUltra(flow_rate):
    """
    :param flow_rate: flow rate in uL/min
    """
    # yield from mv(phdUltra_pump_flowrate, flow_rate)
    yield from abs_set(phdUltra_pump_flowrate, flow_rate, wait=False)
    # yield from phdUltra_pump_flowrate.set(flow_rate, wait=False)
    print(f'Set syringe infusing flow rate {flow_rate} uL/min' )

def set_volume_phdUltra(target_volume):
    yield from abs_set(phdUltra_pump_targetvolume, target_volume * 1000, wait=False)
    print(f'Set syringe target volume {target_volume} mL')

def start_infuse_phdUltra_plan():
    yield from abs_set(phdUltra_pump_infuse,1, wait=False)
    print("Started syringe pump")

def stop_infuse_phdUltra():
    yield from abs_set(phdUltra_pump_infuse, 0, wait=False)
    print('Syringe pump stopped')

def get_focus_measure():
    if epics.caget('Teslong:Over1:NDArrayPort') == 'UVC1':

        rgb, height, width = 3, 1280, 720
        image_data = epics.caget("Teslong:image1:ArrayData")
        image = np.array(image_data, dtype=np.uint8).reshape((width, height, rgb))

        gray_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        rgb, height, width = 1, 1280, 720
        image_data = epics.caget("Teslong:image1:ArrayData")
        image = np.array(image_data, dtype=np.uint8).reshape((width, height, rgb))
        gray_img = image

    laplacian = cv2.Laplacian(gray_img, cv2.CV_64F)
    focus_measure = laplacian.var()

    return focus_measure


def autofocus(delta_z):
    direction = 1
    # Disable HDF1 reading
    Teslong_enable_callbacks.put(0)

    if not Teslongacquire_state.get():
        Teslongacquire_state.put(1)
        # yield from sleep(2)
        sleep(2)

    best_focus = get_focus_measure()

    current_pos = cmir.get().user_readback
    best_pos = current_pos

    while abs(delta_z) > 0.005:
        # last_focus = get_focus_measure() # initial focus value

        pos = current_pos + direction * delta_z  # move position
        yield from mv(cmir,pos)

        current_focus = get_focus_measure()  # new focus value after moved z

        if current_focus < best_focus:
            yield from mv(cmir, current_pos)
            direction = direction * (-1)
            # print('changing direction with dz=%.3f'%delta_z)
            delta_z = delta_z / 2
        else:
            current_pos = pos * 1.0
            best_focus = current_focus * 1.0
            best_pos = current_pos * 1.0
        # print(best_pos, best_focus)
        yield from mv(cmir, best_pos)
    # print('Focus Done')


def capture_live_image(position_csv_path,
        file_prefix,
        interval,
        max_i,
        x_offset=0,
        y_offset=0,
        position_test=False,
        md ={}):
    md = md or {}
    _md = {'plan_args': {'position_csv_path': position_csv_path,
                         'file_prefix': file_prefix,
                         'interval': interval,
                         'max_i': max_i,
                         'x_offset':x_offset,
                         'y_offset': y_offset,
                         'position_test':position_test},

            'plan_name': 'capture_live_image',
            'expDir':'/cars6/Data/chemdata/ASWAXS/Software/ASWAXS/Data'
           }
    _md.update(md)
    @run_decorator(md = md)
    def inner_function():
         yield from capture_images_from_list(
            position_csv_path,
            file_prefix,
            interval,
            max_i,
            x_offset=x_offset,
            y_offset=y_offset,
            position_test=position_test,
            md=md)
    return (yield from inner_function())




def capture_images_from_list(
        position_csv_path,
        file_prefix,
        interval,
        max_i,
        x_offset=0,
        y_offset=0,
        position_test=False,
        md = {}):
    """
    Perform Teslong scan based on a preset position path in a csv file.

    Parameters
    ----------
    position_csv_path: str
        file path of the csv file contains the scan positions
    file_preflix: str
        series name of the experiment
    interval: integer
        numbers of interval steps between each scan
    max_i: integer, optional
        Maximum number of the scan
        If None, scan the whole position set
    x_offset: float
        offset of scan position x coordinates
    y_offset: float
        offset of scan position y coordinates
    position_test:
        If True, brief through the scan positions without saving data

    """
    # Set offset for motors
    # print(f"x_offset set to {x_offset}, y_offset set to {y_offset}")

    # Setup file saving
    # file_path_to_save = os.path.join(md['expDir'], file_prefix)
    file_path_to_save = md['expDir']
    # os.makedirs(file_path_to_save, exist_ok=True)
    # print('path created!!!')

    Teslong_file_path.put(file_path_to_save)

    if not Teslong_HDF_path_exist.get():
        print(f'HDF path {file_path_to_save}'
              f' does not exist')
        return -1

    """Read x, y, z positions from an Excel file and capture images at those positions with a specified interval."""
    df = pd.read_csv(position_csv_path)  # Adjusted to read Excel files

    # Set file prefix for naming
    Teslong_file_name.put(file_prefix)

    x_values, y_values = df['#Vertex_X'].values, df['Vertex_Y'].values  # Adjusted column access

    if position_test:
        # Capture images at intervals specified by 'interval'
        if max_i is None:
            stop_idx = len(x_values)
        else:
            stop_idx = max_i
        scan_num = 0
        Teslong_enable_callbacks.put(0)  # Enable callbacks for data capture
        Teslong_image_mode.put(2)
        Teslong_acquire_data.put(1)  # Start acquiring data
        scan_num = 0
        for i in range(0, stop_idx, interval):  # Iterate with the given interval
            tx, ty = x_values[i], y_values[i]
            yield from mv(sx, tx + x_offset, sy, ty + y_offset)  # Move motors to (x, y)
            yield from sleep(2)  # Wait for motors to settle

            # Teslong_file_number.put(i)  # Update file number for saving
            yield from autofocus(0.5)  # Adjust autofocus

            yield from trigger_and_read([sx,sy,cmir,Teslong_full_file_name])
            # print(f"Scan {scan_num}: Test at ({tx}, {ty}).")  # Log position
            scan_num +=1
    else:
        # Capture images at intervals specified by 'interval'
        if max_i is None:
            stop_idx = len(x_values)
        else:
            stop_idx = max_i
        scan_num = 0

        for i in range(0, stop_idx, interval):  # Iterate with the given interval
            tx, ty = x_values[i], y_values[i]
            yield from mv(sx, tx + x_offset, sy, ty + y_offset)  # Move motors to (x, y)
            yield from sleep(2)  # Wait for motors to settle

            Teslong_file_number.put(i)  # Update file number for saving
            yield from autofocus(0.5)  # Adjust autofocus

            Teslong_enable_callbacks.put(1)  # Enable callbacks for data capture
            yield from trigger_and_read([sx, sy, cmir, Teslong_full_file_name])
            # print(f"Scan {scan_num}: Image  captured at ({tx}, {ty}) and saved as {file_prefix}_{i:03d}.")  # Log position
            scan_num += 1
    Teslong_enable_callbacks.put(0)  # Turn off callbacks after scans

    return 0


# if __name__ == "__main__":
#     autofocus(0.5)

