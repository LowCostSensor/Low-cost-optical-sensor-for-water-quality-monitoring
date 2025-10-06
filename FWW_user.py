"""
Author: Riccardo G. Cirrone
Last Update: Oct 2025

Field Guidelines for Water Analysis Instrument:
    1. Ensure calibration files (P_cal.txt and N_cal.txt) are present.
    2. Power on instrument; the green LED will turn on (ready for the blank).
    3. Press the button to perform the blank measurement (using distilled water).
    4. After the blank, the red LED will blink indicating the system is ready:
       - Wait 10 seconds without pressing --> P-PO4 mode
       - Press the button within 10 seconds --> N-NO3 mode
    5. In N-NO3 mode the green LED will blink
    6. Results are automatically saved to a timestamped .txt file
    7. After each measurement, the red LED blares again and the system is ready to choose the analyte again
"""

import time
import board
import adafruit_ltr329_ltr303 as adafruit_ltr329
import RPi.GPIO as GPIO
from datetime import datetime, timedelta
import pandas as pd
from gpiozero import Button as bt
import numpy as np
import threading

# --- Setup LEDs ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(26, GPIO.OUT)  # Green LED (light source)
GPIO.setup(23, GPIO.OUT)  # Red LED (working/not ready)
GPIO.setup(24, GPIO.OUT)  # Green LED (ready)

# --- Setup button ---
button = bt(4, pull_up=True)
red_led_running = False
green_led_running = False

# --- Setup sensor ---
i2c = board.I2C()
time.sleep(0.5)
ltr329 = adafruit_ltr329.LTR329(i2c)

# --- Sensor parameters ---
ltr329.als_gain = 96
ALS_gain = ltr329.als_gain
ltr329.integration_time = 400
ALS_int = ltr329.integration_time
ltr329.measurement_rate = 2000
ALS_rate = ltr329.measurement_rate

print("WORKING PARAMETERS\n",
      f"GAIN = {ALS_gain}\n",
      f"Integration Time = {ALS_int}\n",
      f"Measurement Rate = {ALS_rate}\n")

# --- Load calibration ---
def get_calibration():
    P = open("/home/pa/P_cal.txt")
    P_content = P.readlines()
    P.close()
    P_R2 = float(P_content[6])
    P_slope = float(P_content[7])
    P_intercept = float(P_content[8])

    N = open("/home/pa/N_cal.txt")
    N_content = N.readlines()
    N.close()
    N_R2 = float(N_content[6])
    N_slope = float(N_content[7])
    N_intercept = float(N_content[8])

    return P_R2, P_slope, P_intercept, N_R2, N_slope, N_intercept

P_R2, P_slope, P_intercept, N_R2, N_slope, N_intercept = get_calibration()

# --- Global variables ---
values = []
blank_value = []

# --- Lux conversion ---
def lux_conversion():
    CH0, CH1 = ltr329.light_channels
    try:
        ratio = CH1 / (CH0 + CH1 + 1e-7)  # avoid division by zero
        if ratio < 0.45:
            ALS_lux = (1.7743 * CH0 + 1.1059 * CH1) / ALS_gain / ALS_int
        elif 0.45 <= ratio < 0.64:
            ALS_lux = (4.2785 * CH0 - 1.9548 * CH1) / ALS_gain / ALS_int
        elif 0.64 <= ratio < 0.85:
            ALS_lux = (0.5926 * CH0 + 0.1185 * CH1) / ALS_gain / ALS_int
        else:
            ALS_lux = 1e-5
    except ZeroDivisionError:
        ALS_lux = 0
    return ALS_lux

# --- LED control ---
def LED_on():
    GPIO.output(26, GPIO.HIGH)
    stop = datetime.now() + timedelta(seconds=2)
    while datetime.now() <= stop:
        lux = round(lux_conversion(),4)
        print(lux)
        values.append(lux)
        time.sleep(0.5)
    GPIO.output(26, GPIO.LOW)

def passive():
    stop = datetime.now() + timedelta(seconds=3)
    while datetime.now() <= stop:
        lux = round(lux_conversion(),4)
        print(lux)
        values.append(lux)
        time.sleep(0.5)

def simple_measure():
    passive()
    LED_on()
    passive()

# --- LED blinking ---
def ready_on():
    GPIO.output(24, GPIO.HIGH)

def ready_off():
    GPIO.output(24, GPIO.LOW)

def working_on():
    GPIO.output(23, GPIO.HIGH)

def working_off():
    GPIO.output(23, GPIO.LOW)

def blare_red():
    global red_led_running
    red_led_running = True
    while red_led_running:
        GPIO.output(23, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(23, GPIO.LOW)
        time.sleep(0.5)

def stop_blare_red():
    global red_led_running
    red_led_running = False

def blare_green():
    global green_led_running
    green_led_running = True
    while green_led_running:
        GPIO.output(24, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(24, GPIO.LOW)
        time.sleep(0.5)

def stop_blare_green():
    global green_led_running
    green_led_running = False

# --- Measurement functions ---
def blank():
    ready_on()
    button.wait_for_press()
    ready_off()
    working_on()
    simple_measure()
    working_off()
    try:
        b = max(values)
    except ValueError:
        b = 0
    blank_value.append(b)
    values.clear()

def measure():
    stop_blare_red()
    stop_blare_green()
    time.sleep(0.5)
    ready_on()
    button.wait_for_press()
    ready_off()
    working_on()
    simple_measure()
    working_off()
    try:
        A = round(-np.log10((max(values)-0.0004)/(max(blank_value)-0.0004)),4)
    except (ZeroDivisionError, ValueError):
        A = 0
    values.clear()
    GPIO.output(26, GPIO.LOW)
    return A

def concentration(absorbance, analyte):
    if analyte == 'N':
        if N_slope != 0:
            c = (absorbance - N_intercept) / N_slope
        else:
            c = 0
    elif analyte == 'P':
        if P_slope != 0:
            c = (absorbance - P_intercept) / P_slope
        else:
            c = 0
    return c

def save(conc, analyte):
    conc_str = str(conc) + " " + analyte + " (mg/L)"
    half_path = "/home/pa/"
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
    path = f"{half_path}{timestamp}_{analyte}.txt"
    with open(path,"w") as f:
        f.write(conc_str)

# --- Analysis ---
def Nitrates():
    stop_blare_red()
    t2 = threading.Thread(target=blare_green)
    t2.start()
    absorbance = measure()
    result = concentration(absorbance, 'N')
    save(result, 'NNO3')
    stop_blare_green()

def Phosphates():
    stop_blare_red()
    absorbance = measure()
    result = concentration(absorbance, 'P')
    save(result, 'PPO4')

# --- Main control ---
def main():
    while True:
        t = threading.Thread(target=blare_red)
        t.start()
        stop_time = datetime.now() + timedelta(seconds=10)
        while datetime.now() <= stop_time:
            if button.is_pressed:
                Nitrates()
                break
            time.sleep(0.05)
        else:
            Phosphates()
        time.sleep(1)

# --- Run ---
if __name__ == "__main__":
    blank()
    main()
