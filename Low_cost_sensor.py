# Importing necessary libraries
import RPi.GPIO as GPIO
import time
from gpiozero import RGBLED
from colorzero import Color
import Adafruit_ADS1x15  # ADC library for ADS1115
import board  # GPIO pin definitions
import busio  # I2C communication library
from datetime import datetime, timedelta  # Date and time handling
import numpy as np  # Mathematical operations library
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import pandas as pd
import io

# Initialize ADC and GPIOs 
i2c = busio.I2C(board.SCL, board.SDA)
adc = Adafruit_ADS1x15.ADS1115()
GAIN = 2/3
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(6, GPIO.OUT)  # Red LED
GPIO.setup(26, GPIO.OUT)  # Green LED
GPIO.setup(5, GPIO.OUT)  # Blue LED
conversion = (6.144 / 32768)  # Ratio to convert raw signal to voltage

# Storage for sample and blank signals
sm = []
bl = []

# Storage for all measured absorbances
list_of_absorbances = []

# Function to ensure that the light source is turned off
def clean():
    GPIO.output(5, GPIO.LOW)
    GPIO.output(6, GPIO.LOW)
    GPIO.output(26, GPIO.LOW)

# Function to sample the dark current for 5 seconds
# Destination is the list in which the signal is stored
def passive(destination):
    stop_sampling_time = datetime.now() + timedelta(seconds=5)
    real_time = datetime.now()
    while real_time <= stop_sampling_time:
        value = ((adc.read_adc(1, gain=GAIN)) * conversion)
        value = round(value, 4)
        print(value)
        destination.append(value)
        real_time = datetime.now()
        time.sleep(1)

# Function to wait for the LDR to relax
def relax():
    value = ((adc.read_adc(1, gain=GAIN)) * conversion)
    value = round(value, 2)
    upper = 1.1156
    while value > upper:
        time.sleep(5)
        value = ((adc.read_adc(1, gain=GAIN)) * conversion)
        value = round(value, 4)
        print("Waiting LDR relax : ", value)

# Function to calculate absorbance
def abs(blank, sample):
    dark = 1.11
    absorbance = -(np.log10((sample - dark) / (blank - dark)))
    print("Measured absorbance: ", absorbance)
    list_of_absorbances.append(absorbance)

# Function to perform a measurement
def measure(destination):
    clean()
    relax()
    passive(destination)
    stop_sampling_time = datetime.now() + timedelta(seconds=30)
    real_time = datetime.now()
    GPIO.output(26, GPIO.HIGH)
    while real_time <= stop_sampling_time:
        value = ((adc.read_adc(1, gain=GAIN)) * conversion)
        value = round(value, 4)
        real_time = datetime.now()
        time.sleep(1)
        destination.append(value)
    passive(destination)
    GPIO.output(26, GPIO.LOW)
    clean()

# Function to send email with absorbance data
def send_email_with_absorbances(absorbance_list):
    # Prepare absorbance data as a DataFrame
    data__ = {'Absorbance': absorbance_list}
    df_excel = pd.DataFrame(data__)

    # Convert DataFrame to Excel format
    excel_buffer = io.BytesIO()
    df_excel.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)

    # Email settings
    tm = time.strftime('%a, %d %b %Y %H:%M:%S')
    sender_email = 'your_sender_email@example.com'
    receiver_email = 'your_receiver_email@example.com'
    subject_ = f'Absorbance Measurements {tm}'
    subject = subject_
    body_ = f'Absorbance measurements taken at {tm}'
    body = body_

    # Create a multipart message
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject

    # Add body to the email
    message.attach(MIMEText(body, 'plain'))

    # Attach the Excel file
    excel_attachment = MIMEApplication(excel_buffer.getvalue(), _subtype="xlsx")
    excel_attachment.add_header('Content-Disposition', 'attachment', filename=f'Absorbance_Data_{tm}.xlsx')
    message.attach(excel_attachment)

    # Establish a secure connection with the SMTP server
    smtp_server = 'smtp.your_mail_server.com'  # Replace with your SMTP server address
    smtp_port = 587  # Replace with your SMTP server port
    smtp_username = 'your_username'
    smtp_password = 'your_password'

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Enable TLS encryption
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print(f"Email sent successfully to {receiver_email}")
    except Exception as e:
        print(f"Failed to send email. Error: {str(e)}")

# Main loop to control the measurement process
# Prompts user to take measurements until they choose to stop
while True:
    try:
        # Prompt user to start a measurement
        q = input("Do you want to take a measurement? (y/n): ").strip().lower()
        
        if q == 'n':
            break  # Exit loop if user chooses not to take another measurement
        
        elif q == 'y':
            print("Insert the blank\n")
            measure(bl)  # Measure blank
            print("Insert the sample\n")
            measure(sm)  # Measure sample
            
            # Calculate absorbance based on max values of blank and sample
            b = max(bl)
            s = max(sm)
            abs(b, s)
            
            print("Measure done\n")
            
            # Send email with absorbance data
            send_email_with_absorbances(list_of_absorbances)
            
            # Clear sample and blank lists for next measurement
            sm = []
            bl = []
            
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
    
    except KeyboardInterrupt:
        print("\nMeasurement interrupted by user.")
        break
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        break

# Clean up GPIO settings at the end
GPIO.cleanup()