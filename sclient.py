#!/usr/bin/python

import json
import socket
import RPi.GPIO as GPIO
import time
import datetime
import math
import os
import random

class Connection():

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def connect(self):
        print('Creating socket')
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            print('Failed to create socket: %s' % msg)
            raise

        print('Socket created')

        server_address = (self.host, self.port)
        print('Connecting to %s:%s' % server_address)

        try:
            self.sock.connect(server_address)
        except socket.error as msg:
            print('Failed to connect: %s' % msg)
            raise

        print('Connected')

    def shutdown(self):
        print('Shutting down')
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

class MAX31865(object):
    
    def __init__(self, cs_pin, clock_pin, data_in_pin, data_out_pin, address, data, units = "c", board = GPIO.BCM):

        '''Initialize Soft (Bitbang) SPI bus
        Parameters:
        - cs_pin:    Chip Select (CS) / Slave Select (SS) pin (Any GPIO)  
        - clock_pin: Clock (SCLK / SCK) pin (Any GPIO)
        - data_in_pin:  Data input (SO / MOSI) pin (Any GPIO)
	      - data_out_pin: Data output (MISO) pin (Any GPIO)
        - units:     (optional) unit of measurement to return. ("c" (default) | "k" | "f")
        - board:     (optional) pin numbering method as per RPi.GPIO library (GPIO.BCM (default) | GPIO.BOARD)
        '''

        self.cs_pin = cs_pin
        self.clock_pin = clock_pin
        self.data_in_pin = data_in_pin
        self.data_out_pin = data_out_pin
        self.address = address           # address of the register to write/read
        #self.data = data                # data to write/read
        self.units = units
        self.data = data
        self.board = board

        # Initialize needed GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(self.board)
        GPIO.setup(self.cs_pin, GPIO.OUT)
        GPIO.setup(self.clock_pin, GPIO.OUT)
        GPIO.setup(self.data_in_pin, GPIO.IN)
        GPIO.setup(self.data_out_pin, GPIO.OUT)

        # Pull chip select high to make chip inactive
        GPIO.output(self.cs_pin, GPIO.HIGH)
        
    def get_data(self):
        '''Acqures raw RDT data.'''
        self.address = int(0x01)    #RTD MSBs
        MSB = self.read()
        self.address = int(0x02)    #RTD LSBs
        LSB = self.read()
        #print MSB
        #print LSB
        MSB = MSB<<8 
        raw = MSB+LSB
        #print raw
        #fault = raw & 1
        #print fault
        raw = raw>>1
        #print raw      
        #print self
        #self.checkErrors()        
        return raw

    def write(self):
        '''Writes 8 bit of data to the 8 bit address'''
        GPIO.output(self.cs_pin, GPIO.LOW)
        GPIO.output(self.clock_pin, GPIO.LOW)
	      
        # Write to address 
        for i in range(8):        
            #print address, data
            bit  = self.address>>(7 - i)
            bit = bit & 1 
            #GPIO.output(self.clock_pin, GPIO.LOW)
            GPIO.output(self.data_out_pin, bit)
            #if bit:
            #    GPIO.output(self.data_out_pin, GPIO.HIGH)
            #else:
            #    GPIO.output(self.data_out_pin, GPIO.LOW)
            GPIO.output(self.clock_pin, GPIO.HIGH)            
            GPIO.output(self.clock_pin, GPIO.LOW)
                
        for i in range(8):        
            bit  = self.data>>(7 - i)
            bit = bit & 1 
            #GPIO.output(self.clock_pin, GPIO.LOW)
            GPIO.output(self.data_out_pin, bit)
            #if bit:
            #    GPIO.output(self.data_out_pin, GPIO.HIGH)
            #else:
            #    GPIO.output(self.data_out_pin, GPIO.LOW)
            GPIO.output(self.clock_pin, GPIO.HIGH)
            GPIO.output(self.clock_pin, GPIO.LOW)
            #GPIO.output(self.data_out_pin, GPIO.LOW)
        
        GPIO.output(self.clock_pin, GPIO.HIGH)                      
        # Unselect the chip
        GPIO.output(self.cs_pin, GPIO.HIGH)
        

    def read(self):
        '''Reads 16 bits of the SPI bus from a self.address register & stores as an integer in self.data.'''
        bytesin = 0                
        
        # Select the chip
        GPIO.output(self.cs_pin, GPIO.LOW)
        # Assert clock bit
        GPIO.output(self.clock_pin, GPIO.LOW)
	      
        # Write to address 
        for i in range(8):        
            #print address, data
            bit  = self.address>>(7 - i)
            bit = bit & 1 
            #GPIO.output(self.clock_pin, GPIO.LOW)
            GPIO.output(self.data_out_pin, bit)
            #if bit:
            #    GPIO.output(self.data_out_pin, GPIO.HIGH)
            #else:
            #    GPIO.output(self.data_out_pin, GPIO.LOW)
            GPIO.output(self.clock_pin, GPIO.HIGH)
            GPIO.output(self.clock_pin, GPIO.LOW)
            #GPIO.output(self.data_out_pin, GPIO.LOW)
        
        # Read in 8 bits        
        for i in range(8):
            GPIO.output(self.clock_pin, GPIO.HIGH)
            bytesin = bytesin << 1
            if (GPIO.input(self.data_in_pin)):
                bytesin = bytesin | 1
            GPIO.output(self.clock_pin, GPIO.LOW)
        
        # Dsable clock                
        GPIO.output(self.clock_pin, GPIO.HIGH)
        # Unselect the chip
        GPIO.output(self.cs_pin, GPIO.HIGH)
        
        # Save data
        self.data = bytesin
        #print bytesin
        return self.data

    def checkErrors(self, data_32 = None):
    # Not finished yet
        '''Checks error bits to see if there are any SCV, SCG, or OC faults'''
        if data_32 is None:
            data_32 = self.data
        anyErrors = (data_32 & 0x10000) != 0    # Fault bit, D16
        noConnection = (data_32 & 1) != 0       # OC bit, D0
        shortToGround = (data_32 & 2) != 0      # SCG bit, D1
        shortToVCC = (data_32 & 4) != 0         # SCV bit, D2
        if anyErrors:
            if noConnection:
                raise MAX31865Error("No Connection")
            elif shortToGround:
                raise MAX31865Error("Thermocouple short to ground")
            elif shortToVCC:
                raise MAX31865Error("Thermocouple short to VCC")
            else:
                # Perhaps another SPI device is trying to send data?
                # Did you remember to initialize all other SPI devices?
                raise MAX31865Error("Unknown Error")

    def convert(self, raw):
        #Takes raw RTD data and returns RTD temperature in celsius as well as RTD resistance.
        RefR = 400.0 #RefR/2        
        R0 = raw * RefR / 32768
        if R0==0:
            #temperature_data = ['', '', '']               
            temperature_data = 'None' + ',' + 'None' + ',' + 'None'
        #elif R0 >= 0:
        #    t = (-3.9083e-3 + math.sqrt(17.58480889e-6 + (-23.10e-9 * R0)))/1.155e-6         
        #    temperature_data = ['{:.0f}'.format(raw), '{:.4f}'.format(R0), '{:.4f}'.format(t)]        
        else:
            #t = -247.29 + 2.3992*R0 + 0.00063962*R0*R0 + 1.0241E-6*R0*R0*R0
            t = -242.02 + 2.2228*R0 + 2.5859e-3*R0*R0 - 4.8260e-6*R0*R0*R0 - 2.8183e-8*R0*R0*R0*R0 + 1.5243e-10*R0*R0*R0*R0*R0 
            #temperature_data = ['{:.0f}'.format(raw), '{:.4f}'.format(R0), '{:.4f}'.format(t)]
            temperature_data = '{:.0f}'.format(raw) + ',' + '{:.4f}'.format(R0) + ',' + '{:.4f}'.format(t)
            #print temperature_data
        #if R0==0:
        #    return -1,0        
        #print temperature_data
        #temperature_data = tuple('-' if x == '' else x for x in temperature_data)
        #temperature_data = '\t'.join(temperature_data)                   
        #return raw, R0, t
        return temperature_data
    
    def to_c(self, celsius):
        '''Celsius passthrough for generic to_* method.'''
        return celsius

    def to_k(self, celsius):
        '''Convert celsius to kelvin.'''
        return celsius + 273.15

    def to_f(self, celsius):
        '''Convert celsius to fahrenheit.'''
        return celsius * 9.0/5.0 + 32

    def cleanup(self):
        '''Selective GPIO cleanup'''
        GPIO.setup(self.cs_pin, GPIO.IN)
        GPIO.setup(self.clock_pin, GPIO.IN)

class MAX31865Error(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)

def measure_temp():
    obj = {}
    obj['temp'] = random.randint(1,21)*5
    obj['humidity'] = random.randint(1,21)*5
    obj['pressure'] = random.randint(1,21)*5
    return json.dumps(obj)

def read_sensors():
    # Multi-chip example   
    # Configure GPIO pins    
    # standard pins //cs_pins = [8, 25, 24]
    # cs_pins = [7, 25, 24]
    cs_pins = [7, 8, 25, 24, 23, 18]
    clock_pin = 11
    data_in_pin = 9
    data_out_pin = 10
    #units = "k"
    
    # Configure RTDs
    rtds = []
    address = int(0x80)    # RTD control register, see datasheet for details
    data =  int(0xC2)      # RTD condrol register data, see datasheet for details
    for cs_pin in cs_pins:
        rtds.append(MAX31865(cs_pin, clock_pin, data_in_pin, data_out_pin, address, data))  
    #print rtds
    for rtd in rtds:        
        rtd.write()
    #print rtd    
     
    log_string = ''
    
    # Run main loop   
    running = True
    while(running):
        try:
            temperature_data = ''                
            for rtd in rtds:
              RTD_code = rtd.get_data()                    
              temperature_data += ',' + rtd.convert(RTD_code)             
            now = datetime.datetime.now().strftime('%Y-%m-%d,%H:%M:%S')
            print ('\033c')
            #log_string = now + temperature_data + '\r\n'
            log_string = now + temperature_data      
            print log_string
            obj = {}
            obj['response'] = log_string
            return json.dumps(obj)
        except KeyboardInterrupt:
            running = False
    GPIO.cleanup()

def sendData(sock):
    print('Sending data')
    while True:
        try:
            #data = 'data,' + measure_temp()
            data = 'data,' + read_sensors()
            sock.sendall(data.encode())
        except socket.error as msg:
            print("Cannot send to server: %s" % msg)
            break
        time.sleep(3)

connection = Connection('127.0.0.1', 8888)

while True:
    try:
        connection.connect()
        sendData(connection.sock)
        connection.shutdown()
        break
    except socket.error as msg:
        print('Connection failed, retrying in 3 seconds.')
        time.sleep(3)

print('Done')
