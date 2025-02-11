#Author Riccardo G. Cirrone
#Update Feb 2025
import time
import board
import adafruit_ltr329_ltr303 as adafruit_ltr329
import RPi.GPIO as GPIO
from datetime import datetime, timedelta
import pandas as pd
from gpiozero import Button as bt
import numpy as np
#Setting up the LED (ligh source)
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(26, GPIO.OUT)  # Green LED

#Setting up control Light
GPIO.setup(23,GPIO.OUT) #Control red (not ready)
GPIO.setup(24,GPIO.OUT) #Control green (ready)

#Setting up the sensor
i2c = board.I2C()
time.sleep(0.5)  # sensor takes 100ms to 'boot' on power up
ltr329 = adafruit_ltr329.LTR329(i2c)

#Setting up the button
button= bt(4,pull_up=True)

# Setting working parameters
ltr329.als_gain = int(96)
ALS_gain = ltr329.als_gain
ltr329.integration_time = int(400)
ALS_int = ltr329.integration_time
ltr329.measurement_rate = int(2000)
ALS_rate = ltr329.measurement_rate
print("WORKING PARAMETERS",'\n',
      "GAIN = ", ALS_gain ,'\n',
      "Integration Time = ", ALS_int ,'\n',
      "Measurement Rate = ", ALS_rate,'\n')
#List to stock data
values = []
blank_value = []

def lux_conversion():
    CH0, CH1 = ltr329.light_channels
    ratio = (CH1 / (CH0 + CH1)+0.0000001) 
    
    # Calculating lux
    if ratio < 0.45:
        ALS_lux = (1.7743 * CH0 + 1.1059 * CH1) / ALS_gain / ALS_int
    elif 0.45 <= ratio < 0.64:
        ALS_lux = (4.2785 * CH0 - 1.9548 * CH1) / ALS_gain / ALS_int
    elif 0.64 <= ratio < 0.85:
        ALS_lux = (0.5926 * CH0 + 0.1185 * CH1) / ALS_gain / ALS_int
    else:
        ALS_lux = 0.00001
    return ALS_lux  # Return the calculated lux value

def LED_on():
    GPIO.output(26, GPIO.HIGH)  # Turn on LED
    stop = datetime.now() + timedelta(seconds=2)
    real_time = datetime.now()
    while real_time <= stop:
        ALS_lux = lux_conversion()
        ALS_lux = round(ALS_lux,4)
        print(ALS_lux)
        values.append(ALS_lux)
        time.sleep(0.5)
        real_time = datetime.now()
    GPIO.output(26,GPIO.LOW)

def passive():
    stop = datetime.now() + timedelta(seconds=3)
    real_time = datetime.now()
    while real_time <= stop:
        ALS_lux = lux_conversion()  # Use returned lux value
        ALS_lux = round(ALS_lux,4)
        values.append(ALS_lux)
        print(ALS_lux)
        time.sleep(0.5)
        real_time = datetime.now()
        
def save(absorbance):
    df = pd.DataFrame({'Lux': values, 'Abs':absorbance})
    half_path = "/home/pi/"
    rt = datetime.now()
    ft = rt.strftime("%Y_%m_%d_%H_%M")
    tm = str(ft)
    ext = ".xlsx"
    path = half_path+tm+ext
    df.to_excel(path,index=False)
    
def simple_measure():
    passive()
    LED_on()
    passive()

def ready_on():
    GPIO.output(24,GPIO.HIGH)

def ready_off():
    GPIO.output(24,GPIO.LOW)

def working_on():
    GPIO.output(23,GPIO.HIGH)

def working_off():
    GPIO.output(23,GPIO.LOW)

def get_keypress(): #To shutdown script if "esc" is pressed
    keys = event.getKeys()
    if keys:
        return keys[0]
    else:
        return None
    
def blank():
    ready_on()
    button.wait_for_press()
    ready_off()
    working_on()
    simple_measure()
    working_off()
    b = max(values)
    blank_value.append(b)
    values.clear()
    
def measure():
    ready_on()
    button.wait_for_press()
    ready_off()
    working_on()
    simple_measure()
    working_off()
    A = [round(-np.log10((max(values)-0.0004)/(max(blank_value)-0.0004)),4)]
    save(A)
while True:
    try:
        print("Ready")
        measure()
    except Exception as e:
        print("An error occured, wait few seconds")
        GPIO.output(26, GPIO.HIGH)
        GPIO.output(23, GPIO.LOW)
        GPIO.output(24, GPIO.LOW)
