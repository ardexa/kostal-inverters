#! /usr/bin/python

# Copyright (c) 2013-2017 Ardexa Pty Ltd
#
# This code is licensed under the MIT License (MIT).
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#

# This script will query one or more Kostal inverters. 
# Usage: python kostal-ardexa.py IP_address start_address end_address log_directory query_type debug_str
# Eg; python kostal-ardexa.py 192.168.1.3 1 4 /opt/ardexa RUNTIME 0
# {IP Address} = ..something lijke: 192.168.1.4
# {Start Address} = start range 1
# {End Address} = end range (Max 255 for Kostal inverters)
# {log directory} = logging directory; eg; /opt/logging/
# {type of query} = DISCOVERY or RUNTIME
# {debug type} = 0 (no messages, except errors), 1 (discovery messages) or 2 (all messages)
#	 DEBUG = 0 ; No Debug information
#	 DEBUG = 1 ; Important Debug information
#	 DEBUG = 2 ; ALL Debug information
#
# For use on Linux systems
# Make sure the following tools have been installed
#		sudo apt-get install python-pip
#		sudo pip install hexdump

import sys
import time
import os
import socket
import hexdump
from Supporting import *

# These are the status codes from the Kostal Manual
status_codes = {0: 'Off', 1: 'Standby', 2: 'Starting', 3: 'Feed-in (MPP)', 4: 'Feed-in regulated', 5: 'Feed-in'}
BUFFERSIZE = 8196
PIDFILE = 'kostal-ardexa.pid'
PORT = 81

# This will write a line to the base_directory
# Assume header and lines are already \n terminated
def write_line(line, inverter_addr, base_directory, header_line, debug):
	# Write the log entry, as a date entry in the log directory
	date_str = (time.strftime("%d-%b-%Y"))
	log_filename = date_str + ".csv"
	log_directory = os.path.join(base_directory, inverter_addr)
	write_log(log_directory, log_filename, header_line, line, debug, True, log_directory, "latest.csv")

	return True

# Kostal IP Socket settings
def open_socket(IP_address, debug):
	# open the socket
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.settimeout(1)
	try:		
		retval = sock.connect((IP_address, PORT))
		return True, sock
	except:
		return False, sock

# Close the socket
def close_socket(sock):
	# close the socket
	sock.close()

# Get a 2bytes or 16 bits
def get_2bytes(response, index):
	# Check that retrieving 2 bytes won't overrun the response
	length = len(response)
	if (length >= index + 2):
		retval = ord(response[index]) + 256*ord(response[index+1])
		return retval
	else:
		return -999.9

# Get 4bytes or 32 bits
def get_4bytes(response, index):
	# Check that retrieving 4 bytes won't overrun the response
	length = len(response)
	if (length >= index + 4):
		retval = ord(response[index]) + 256*ord(response[index+1]) + 65536*ord(response[index+2]) + 16777216*ord(response[index+3])
		return retval
	else:
		return -999.9

# Formulate the request, which includes the checksum
def formulate_request(code, address):  
	request = '\x62%s\x03%s\x00%s' % (chr(address), chr(address), chr(code))
	checksum = 0
	for i in range(len(request)):
		checksum -= ord(request[i])
		checksum %= 256
	request += '%s\x00' % (chr(checksum))
	return request

# This verifies the checksum in a response packet
def verify_checksum(response):
	if len(response) < 2:
		return False
	checksum = 0
	for i in range(len(response) - 2):
		checksum -= ord(response[i])
		checksum %= 256

	if checksum != ord(response[-2]):
		return False

	return True

# Send a request and return the response
def send_recv(socket, request, debug):
	if (debug >= 2):
		print 'Sent: ', hexdump.hexdump(request)

	socket.send(request)
	response = socket.recv(BUFFERSIZE)
	if (debug >= 2):
		print 'Received: ', hexdump.hexdump(response)

	return response

# Get the inverter metadata
# This includes mode, string, phase, serial number, version and name of the inverter
def get_metadata(socket, address, debug):
	model = "" ; string = "" ; phase = "" ; name = "" ; serial = "" ; version = "" ; retval = True

	# Get model, string and phase
	request = formulate_request(0x90, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 28)):
		if (debug >= 1):
			print "Model request checksum is not good"
		retval = False
	else:
		model = response[5:16]
		string = ord(response[21])
		phase = ord(response[28])

	# Get Name
	request = formulate_request(0x44, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 20)):
		if (debug >= 1):
			print "Name request checksum is not good"
		retval = False
	else:
		name = response[5:20]

	# Get Serial number
	request = formulate_request(0x50, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 20)):
		if (debug >= 1):
			print "Serial request checksum is not good"
		retval = False
	else:
		serial = response[5:18]

	# Get Inverter Version
	part1 = part2 = part3 = 0
	request = formulate_request(0x8a, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 13)):
		if (debug >= 1):
			print "Version request checksum is not good"
		retval = False
	else:
		part1 = get_2bytes(response, 5)
		part2 = get_2bytes(response, 7)
		part3 = get_2bytes(response, 9)
		version = "%04x %02x.%02x %02x.%02x" % (part1, part2//256, part2%256, part3//256, part3%256)

	if (debug >= 1):
		print "Metadata. Model: ",model," Name: ",name," Version: ",version," Phase: ",phase," Serial: ",serial," String: ",string," Return: ",retval

	return model, string, phase, name, serial, version, retval


# Convert temperature. If the incoming value is 0, don't try an convert it
# Just return 0
def convert(temp):
	if (temp <= 0.0):
		return 0.0
	else:
		tref = 51200
		temperature = ((tref - temp)/448.0) + 22.0
		return temperature

# Get the inverter data
def get_data(socket, address, debug):
	error_code = 0 ; error = 0 ; status = "" ; retval = True
	DC_string1_volts=0; DC_string2_volts=0; DC_string3_volts=0; DC_string1_current=0; DC_string2_current=0; DC_string3_current=0
	DC_string1_power=0; DC_string2_power=0; DC_string3_power=0; DC_string1_temperature=0; DC_string2_temperature=0; DC_string3_temperature=0
	AC_phase1_volts=0; AC_phase2_volts=0; AC_phase3_volts=0
	AC_phase1_current=0; AC_phase2_current=0; AC_phase3_current=0; AC_phase1_power=0; AC_phase2_power=0; AC_phase3_power=0 
	AC_phase1_temperature=0; AC_phase2_temperature=0; AC_phase3_temperature=0; DC_power=0; AC_power=0
	total_energy=0; daily_energy=0; total_hours=0

	# Get status
	request = formulate_request(0x57, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 9)):
		print "Status request checksum is not good"
		retval = False
	else:
		error_code = get_2bytes(response, 7)
		error = ord(response[6])
		status_num = ord(response[5])
		status = ""
		if (0 <= status_num <= 5):
			status = status_codes[status_num]
		
	# Get the voltage, current, power and temperature data
	request = formulate_request(0x43, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 65)):
		print "Data request checksum is not good"
		retval = False
	else:
		try:
			# NB: Multiplying by 1.0 is to turn everything into a float
			# Limit all these values to 2 decimal places
			DC_string1_volts = get_2bytes(response, 5)*1.0/10
			DC_string2_volts = get_2bytes(response, 15)*1.0/10
			DC_string3_volts = get_2bytes(response, 25)*1.0/10
			DC_string1_current = get_2bytes(response, 7)*1.0/100
			DC_string2_current = get_2bytes(response, 17)*1.0/100
			DC_string3_current = get_2bytes(response, 27)*1.0/100
			DC_string1_power = get_2bytes(response, 9)*1.0
			DC_string2_power = get_2bytes(response, 19)*1.0
			DC_string3_power = get_2bytes(response, 29)*1.0
			DC_string1_temperature = convert(get_2bytes(response, 11)*1.0)
			DC_string2_temperature = convert(get_2bytes(response, 21)*1.0)
			DC_string3_temperature = convert(get_2bytes(response, 31)*1.0)
			AC_phase1_volts = get_2bytes(response, 35)*1.0/10
			AC_phase2_volts = get_2bytes(response, 43)*1.0/10
			AC_phase3_volts = get_2bytes(response, 51)*1.0/10
			AC_phase1_current = get_2bytes(response, 37)*1.0/100
			AC_phase2_current = get_2bytes(response, 45)*1.0/100
			AC_phase3_current = get_2bytes(response, 53)*1.0/100
			AC_phase1_power = get_2bytes(response, 39)*1.0
			AC_phase2_power = get_2bytes(response, 47)*1.0
			AC_phase3_power = get_2bytes(response, 55)*1.0
			AC_phase1_temperature = convert(get_2bytes(response, 41)*1.0)
			AC_phase2_temperature = convert(get_2bytes(response, 49)*1.0)
			AC_phase3_temperature = convert(get_2bytes(response, 57)*1.0)
			DC_power = DC_string1_power + DC_string2_power + DC_string3_power
			AC_power = AC_phase1_power + AC_phase2_power + AC_phase3_power
		except:
			print "Could not retrieve data"
			retval = False

	# Get Total Energy
	request = formulate_request(0x45, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 9)):
		print "Status request checksum is not good"
		retval = False
	else:
		total_energy = get_4bytes(response, 5)

	# Get Daily Energy
	request = formulate_request(0x9d, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 9)):
		print "Status request checksum is not good"
		retval = False
	else:
		daily_energy = get_4bytes(response, 5)

	# Get Total Hours. Note that raw result in in seconds
	# Convert to hours by dividing by 3600
	request = formulate_request(0x46, address)
	response = send_recv(socket, request, debug)
	if ((not verify_checksum(response)) or (len(response) < 9)):
		print "Status request checksum is not good"
		retval = False
	else:
		total_hours = get_4bytes(response, 5)
		total_hours = total_hours / 3600

	if (debug >= 1):
		print "Error=",error," Error_Code=",error_code," Status=",status
		print "DC Volts1=",DC_string1_volts," DC Volts2=",DC_string2_volts," DC Volts3=",DC_string3_volts
		print "DC Current1=",DC_string1_current," DC Current2=",DC_string2_current," DC Current3=",DC_string3_current
		print "DC Power1=",DC_string1_power," DC Power2=",DC_string2_power," DC Power3=",DC_string3_power
		print "DC Temperature1=",DC_string1_temperature," DC Temperature2=",DC_string2_temperature," DC Temperature3=",DC_string3_temperature
		print "AC Volts1=",AC_phase1_volts," AC Volts2=",AC_phase2_volts," AC Volts3=",AC_phase3_volts
		print "AC Current1=",AC_phase1_current," AC Current2=",AC_phase2_current," AC Current3=",AC_phase3_current
		print "AC Power1=",AC_phase1_power," AC Power2=",AC_phase2_power," AC Power3=",AC_phase3_power
		print "AC Temperature1=",AC_phase1_temperature," AC Temperature2=",AC_phase2_temperature," AC Temperature3=",AC_phase3_temperature
		print "DC Power=",DC_power," AC Power=",AC_power
		print "Total Energy=",total_energy," Daily Energy=",daily_energy," Total Hours=",total_hours

	# Format all values, convert them to strings, and formaulet a header line
	# Return the line and the header line
	format(DC_string1_volts, '0.2f')
	format(DC_string2_volts, '0.2f')
	format(DC_string3_volts, '0.2f')
	format(DC_string1_current, '0.2f')
	format(DC_string2_current, '0.2f')
	format(DC_string3_current, '0.2f')
	format(DC_string1_power, '0.2f')
	format(DC_string2_power, '0.2f')
	format(DC_string3_power, '0.2f')
	format(DC_string1_temperature, '0.2f')
	format(DC_string2_temperature, '0.2f')
	format(DC_string3_temperature, '0.2f')
	format(AC_phase1_volts, '0.2f')
	format(AC_phase2_volts, '0.2f')
	format(AC_phase3_volts, '0.2f')
	format(AC_phase1_current, '0.2f')
	format(AC_phase2_current, '0.2f')
	format(AC_phase3_current, '0.2f')
	format(AC_phase1_power, '0.2f')
	format(AC_phase2_power, '0.2f')
	format(AC_phase3_power, '0.2f')
	format(AC_phase1_temperature, '0.2f')
	format(AC_phase2_temperature, '0.2f')
	format(AC_phase3_temperature, '0.2f')
	format(DC_power, '0.2f')
	format(AC_power, '0.2f')
	format(total_energy, '0.2f')
	format(daily_energy, '0.2f')
	format(total_hours, '0.2f')

	datetime = get_datetime()

	# Formulate the line
	line = datetime + "," + str(DC_string1_volts) + "," + str(DC_string2_volts) + "," + str(DC_string3_volts) + "," + str(DC_string1_current) + "," \
			 + str(DC_string2_current) + "," + str(DC_string3_current) + "," + str(DC_string1_power) + "," + str(DC_string2_power) + "," + str(DC_string3_power) \
			 + "," + str(DC_string1_temperature) + "," + str(DC_string2_temperature) + "," + str(DC_string3_temperature) + "," + str(AC_phase1_volts) + "," + \
			 str(AC_phase2_volts) + "," + str(AC_phase3_volts) + "," + str(AC_phase1_current) + "," + str(AC_phase2_current) + "," + str(AC_phase3_current) \
			 + "," + str(AC_phase1_power) + "," + str(AC_phase2_power) + "," + str(AC_phase3_power) + "," + str(AC_phase1_temperature) + "," + \
			 str(AC_phase2_temperature) + "," + str(AC_phase3_temperature) + "," + str(DC_power) + "," + str(AC_power) + "," + str(total_energy) + "," + \
			 str(daily_energy) + "," + str(total_hours) + "," + status + "," + str(error) + "," + str(error_code) + "\n"

	# And the header line
	header = "Datetime, String 1 Volts (V), String 2 Volts (V), String 3 Volts (V), String 1 Current (A), String 2 Current (A), String 3 Current (A), \
String 1 Power (W), String 2 Power (W), String 3 Power (W), String 1 Temp (C), String 2 Temp (C), String 3 Temp (C), \
AC Phase 1 Volts (V), AC Phase 2 Volts (V), AC Phase 3 Volts (V), AC Phase 1 Current (A), AC Phase 2 Current (A), AC Phase 3 Current (A), \
AC Phase 1 Power (W), AC Phase 2 Power (W), AC Phase 3 Power (W), AC Phase 1 Temp (C), AC Phase 2 Temp (C), AC Phase 3 Temp (C), \
DC Power (W), AC Power (W), Total Energy (Wh), Daily Energy (Wh), Total Hours (h), Status, Error, Error Code\n"

	return header,line,retval

# This will discover all the inverters, by checking addresses 1 to 255, inclusive
def discover_inverters(sock, debug):
	for address in range(1,255):
		try:
			model, string, phase, name, serial, version, retval = get_metadata(sock, address, debug)
			if (retval):
				print "Address: ", address, "; Model: ",model,  "; String: ",string, "; Phase: ",phase, "; Serial: ",serial, "; Version: ",version
		except:
			pass

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   END Functions ~~~~~~~~~~~~~~~~~~~~~~~

# Check script is run as root
if os.geteuid() != 0:
	print "You need to have root privileges to run this script, or as \'sudo\'. Exiting."
	sys.exit(1)

#check the arguments
arguments = check_args(6)
if (len(arguments) < 6):
	print "The arguments cannot be empty. Usage: ", USAGE
	sys.exit(2)

IP_address = arguments[1]
start_address = arguments[2]
end_address = arguments[3]
log_directory = arguments[4]
query_type = arguments[5]
debug_str = arguments[6]

# Convert debug
retval, debug = convert_to_int(debug_str)
if (not retval):
	print "Debug needs to be an integer number. Value entered: ",debug_str
	sys.exit(3)

# If the logging directory doesn't exist, create it
if (not os.path.exists(log_directory)):
	os.makedirs(log_directory)

# Check that no other scripts are running
pidfile = os.path.join(log_directory, PIDFILE)
if check_pidfile(pidfile, debug):
	print "This script is already running"
	sys.exit(4)

# if any args are empty, exit with error
if ((not IP_address) or (not start_address) or (not end_address) or (not log_directory)):
	print "The arguments cannot be empty. Usage: ", USAGE
	sys.exit(5)

# Convert start and stop addresses
retval_start, start_addr = convert_to_int(start_address)
retval_end, end_addr = convert_to_int(end_address)
if ((not retval_start) or (not retval_end)):
	print "Start and End Addresses need to be an integers"
	sys.exit(6)

start_time = time.time()
# Open the socket
retval, sock = open_socket(IP_address, debug)
if (not retval):
	print "Could not connect to IP Address: ", IP_address
	sys.exit(7)

if (query_type == "RUNTIME"):
	# This will check each inverter. If a bad line is received, it will try one more time
	for (inverter_addr) in range(start_addr, end_addr+1):
		count = 2
		while (count >= 1):
			# Query the data
			header,line,retval = get_data(sock, inverter_addr, debug)
			if (retval == True):
				success = write_line(line, str(inverter_addr), log_directory, header, debug)
				if (success == True):
					break
			count = count - 1

elif (query_type == "DISCOVERY"):
	discover_inverters(sock, debug)

# Close the socket
close_socket(sock)

elapsed_time = time.time() - start_time
if (debug > 0):
	print "This request took: ",elapsed_time, " seconds."

# Remove the PID file	
if os.path.isfile(pidfile):
	os.unlink(pidfile)

print 0










