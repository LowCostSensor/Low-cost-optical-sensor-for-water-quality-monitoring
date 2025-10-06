"""
Author: Riccardo G. Cirrone
Last update: Oct 2025

Calibration script for PRATICO sensor.
For on-field analysis, use FWW.py (see User's guide).
"""

import time
import board
import adafruit_ltr329_ltr303 as adafruit_ltr329
import RPi.GPIO as GPIO
from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression

# Paths to save calibration results
N_path = "/home/pa/N_cal.txt"
P_path = "/home/pa/P_cal.txt"

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(26, GPIO.OUT)

# Setup sensor
i2c = board.I2C()
time.sleep(0.5)
ltr329 = adafruit_ltr329.LTR329(i2c)

# Sensor parameters
ltr329.als_gain = 96
ALS_gain = ltr329.als_gain
ltr329.integration_time = 400
ALS_int = ltr329.integration_time
ltr329.measurement_rate = 2000
ALS_rate = ltr329.measurement_rate

print("Working parameters:\n",
      f"Gain = {ALS_gain}\n",
      f"Integration time = {ALS_int}\n",
      f"Measurement rate = {ALS_rate}\n")

# Temporary storage
values = []
N_abs = []
P_abs = []

# Standard solution concentrations
N = [0.2, 0.5, 1, 2, 5, 10]  # ppm
P = [0.02, 0.05, 0.1, 0.2, 0.5, 1]  # ppm

# --- Functions ---

def lux_conversion():
    CH0, CH1 = ltr329.light_channels
    try:
        ratio = CH1 / (CH0 + CH1)
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

def LED_on():
    values.clear()
    GPIO.output(26, GPIO.HIGH)
    stop = datetime.now() + timedelta(seconds=2)
    while datetime.now() <= stop:
        lux = round(lux_conversion(), 4)
        values.append(lux)
        print(lux)
        time.sleep(0.5)
    GPIO.output(26, GPIO.LOW)

def passive():
    values.clear()
    stop = datetime.now() + timedelta(seconds=3)
    while datetime.now() <= stop:
        lux = round(lux_conversion(), 4)
        values.append(lux)
        print(lux)
        time.sleep(0.5)

def measure():
    passive()
    LED_on()
    passive()

def blank():
    # Lasciata invariata come richiesto
    measure()
    b = max(values) if values else 1e-5
    values.clear()
    return b

def linear_fitting(a, b):
    lr = LinearRegression()
    X = np.array(a).reshape(-1, 1)
    y = np.array(b)
    lr.fit(X, y)
    R2 = round(lr.score(X, y), 4)
    slope = lr.coef_[0]
    intercept = lr.intercept_
    return R2, slope, intercept

def NNO3_calibration(b):
    print("Calibrating for N-NO3 (ppm): 0.2, 0.5, 1, 2, 5, 10")
    for conc in N:
        input(f"Insert N-NO3 standard solution at {conc} mg/L and press Enter...")
        measure()
        try:
            A = round(-np.log10((max(values)-0.0004)/(max(b)-0.0004)),4)
        except ZeroDivisionError:
            A = 0
        N_abs.append(A)
    print("Calibrating...")
    R2, slope, intercept = linear_fitting(N, N_abs)
    print(f">>> N-NO3 Calibration Results:\nR^2 = {R2}\nSlope = {slope}\nIntercept = {intercept}\n")
    with open(N_path, "w") as f:
        f.write(f"N-NO3 calibration results:\nR^2 = {R2}\nSlope = {slope}\nIntercept = {intercept}\n")

def PPO4_calibration(b):
    print("Calibrating for P-PO4 (ppm): 0.02, 0.05, 0.1, 0.2, 0.5, 1")
    for conc in P:
        input(f"Insert P-PO4 standard solution at {conc} mg/L and press Enter...")
        measure()
        try:
            A = round(-np.log10((max(values)-0.0004)/(max(b)-0.0004)),4)
        except ZeroDivisionError:
            A = 0
        P_abs.append(A)
    print("Calibrating...")
    R2, slope, intercept = linear_fitting(P, P_abs)
    print(f">>> P-PO4 Calibration Results:\nR^2 = {R2}\nSlope = {slope}\nIntercept = {intercept}\n")
    with open(P_path, "w") as f:
        f.write(f"P-PO4 calibration results:\nR^2 = {R2}\nSlope = {slope}\nIntercept = {intercept}\n")

# --- Main ---

input(">>> Insert the blank sample and press Enter...")
blank_value = blank()

while True:
    try:
        choice = input("Choose calibration: NNO3 or PPO4 (N/P) --> ").lower()
        if choice == 'n':
            NNO3_calibration(blank_value)
            break
        elif choice == 'p':
            PPO4_calibration(blank_value)
            break
        else:
            print("Invalid choice. Enter 'N' or 'P'.")
    except Exception as e:
        print("Error:", e)



