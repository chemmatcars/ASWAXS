import epics
import cv2
import numpy as np
import time
import sys


def get_focus_measure(camera_image_pv, width, height):
    image_data = epics.caget(camera_image_pv)
    if image_data.ndim != 2:
        image = np.array(image_data, dtype=np.uint8).reshape((height, width, 3))
        gray_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray_img = image_data
    laplacian = cv2.Laplacian(gray_img, cv2.CV_64F)
    focus_measure = laplacian.var()
    return focus_measure


def autofocus(camara_pv, motor_pv, delta_z):
    width = epics.caget(camera_pv + "ArraySizeX_RBV")
    height = epics.caget(camera_pv + "ArraySizeY_RBV")
    camera_image_pv = camera_pv.split(':')[0] + ':image1:ArrayData'
    best_focus = get_focus_measure(camera_image_pv, width, height)
    cmir = epics.Motor(motor_pv)
    current_pos = cmir.get('VAL')
    best_pos = current_pos
    direction = 1

    while delta_z > 0.005:
        # last_focus = get_focus_measure() # initial focus value

        pos = current_pos + direction * delta_z  # move position
        cmir.move(pos, wait=True)

        current_focus = get_focus_measure(camera_image_pv, width, height)  # new focus value after moved z

        if current_focus < best_focus:
            cmir.move(current_pos, wait=True)
            direction = direction * (-1)
            delta_z = delta_z / 2
            print('changing direction with dz=%.3f' % delta_z)
        else:
            current_pos = pos * 1.0
            best_focus = current_focus * 1.0
            best_pos = current_pos * 1.0
        print(delta_z, direction, best_pos, best_focus)
    cmir.move(best_pos, wait=True)
    print('Focus Done')


if __name__ == '__main__':
    camera_pv = sys.argv[1]
    motor_pv = sys.argv[2]
    delta_z = float(sys.argv[3])
    # enable_callbacks = epics.PV('Teslong:HDF1:EnableCallbacks')
    image_mode = epics.PV(camera_pv + 'ImageMode')
    acquire_state = epics.PV(camera_pv + 'Acquire')
    autofocus(camera_pv, motor_pv, delta_z)
