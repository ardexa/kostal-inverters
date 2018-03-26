"""
This script will query one or more Kostal inverters.
Usage: python kostal-ardexa.py ip_address start_address end_address log_directory
Eg; python kostal-ardexa.py 192.168.1.3 1 4 /opt/ardexa RUNTIME 0
{IP Address} = ..something lijke: 192.168.1.4
{Start Address} = start range 1
{End Address} = end range (Max 255 for Kostal inverters)
{log directory} = logging directory; eg; /opt/logging/
{type of query} = DISCOVERY or RUNTIME
{debug type} = 0 (no messages, except errors), 1 (discovery messages) or 2 (all messages)
    DEBUG = 0 ; No Debug information
    DEBUG = 1 ; Important Debug information
    DEBUG = 2 ; ALL Debug information
"""

# Copyright (c) 2018 Ardexa Pty Ltd
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

import sys
import time
import os
import socket
import click
import hexdump
import ardexaplugin as ap

# These are the status codes from the Kostal Manual
STATUS_CODES = {0: 'Off', 1: 'Standby', 2: 'Starting', 3: 'Feed-in (MPP)', 4: 'Feed-in regulated', 5: 'Feed-in'}
BUFFERSIZE = 8196
PIDFILE = 'kostal-ardexa.pid'
PORT = 81

def write_line(line, inverter_addr, base_directory, header_line, debug):
    """This will write a line to the base_directory
    Assume header and lines are already \n terminated"""
    # Write the log entry, as a date entry in the log directory
    date_str = (time.strftime("%Y-%b-%d"))
    log_filename = date_str + ".csv"
    log_directory = os.path.join(base_directory, inverter_addr)
    ap.write_log(log_directory, log_filename, header_line, line, debug, True, log_directory, "latest.csv")

    return True

def open_socket(ip_address):
    """Kostal IP Socket settings"""
    # open the socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        sock.connect((ip_address, PORT))
        return True, sock
    except:
        return False, sock

def close_socket(sock):
    """Close the socket"""
    # close the socket
    sock.close()

def get_2bytes(response, index):
    """Get a 2bytes or 16 bits"""
    # Check that retrieving 2 bytes won't overrun the response
    length = len(response)
    if length >= index + 2:
        retval = ord(response[index]) + 256*ord(response[index+1])
        return retval
    else:
        return -999.9

def get_4bytes(response, index):
    """Get 4bytes or 32 bits"""
    # Check that retrieving 4 bytes won't overrun the response
    length = len(response)
    if length >= index + 4:
        retval = ord(response[index]) + 256*ord(response[index+1]) + 65536*ord(response[index+2]) + 16777216*ord(response[index+3])
        return retval
    else:
        return -999.9

def formulate_request(code, address):
    """Formulate the request, which includes the checksum"""
    request = '\x62%s\x03%s\x00%s' % (chr(address), chr(address), chr(code))
    checksum = 0
    for i in range(len(request)):
        checksum -= ord(request[i])
        checksum %= 256
    request += '%s\x00' % (chr(checksum))
    return request

def verify_checksum(response):
    """This verifies the checksum in a response packet"""
    if len(response) < 2:
        return False
    checksum = 0
    for i in range(len(response) - 2):
        checksum -= ord(response[i])
        checksum %= 256

    if checksum != ord(response[-2]):
        return False

    return True

def send_recv(sock, request, debug):
    """Send a request and return the response"""
    if debug >= 2:
        print('Sent: ', hexdump.hexdump(request))

    response = ''
    try:
        sock.send(request)
        response = sock.recv(BUFFERSIZE)
    except:
        pass

    if debug >= 2:
        print('Received: ', hexdump.hexdump(response))

    return response

def get_metadata(sock, address, debug):
    """Get the inverter metadata. This includes mode, string, phase, serial number, version and name of the inverter"""
    model = ""
    string = ""
    phase = ""
    name = ""
    serial = ""
    version = ""
    retval = True

    # Get model, string and phase
    request = formulate_request(0x90, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 28:
        if debug >= 1:
            print("Model request checksum is not good")
        retval = False
    else:
        model = response[5:16]
        string = ord(response[21])
        phase = ord(response[28])

    # Get Name
    request = formulate_request(0x44, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 20:
        if debug >= 1:
            print("Name request checksum is not good")
        retval = False
    else:
        name = response[5:20]

    # Get Serial number
    request = formulate_request(0x50, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 20:
        if debug >= 1:
            print("Serial request checksum is not good")
        retval = False
    else:
        serial = response[5:18]

    # Get Inverter Version
    part1 = part2 = part3 = 0
    request = formulate_request(0x8a, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 13:
        if debug >= 1:
            print("Version request checksum is not good")
        retval = False
    else:
        part1 = get_2bytes(response, 5)
        part2 = get_2bytes(response, 7)
        part3 = get_2bytes(response, 9)
        version = "%04x %02x.%02x %02x.%02x" % (part1, part2//256, part2%256, part3//256, part3%256)

    if debug >= 1:
        print("Metadata. Model: ", model, " Name: ", name, " Version: ", version, " Phase: ", phase,
              " Serial: ", serial, " String: ", string, " Return: ", retval)

    return model, string, phase, name, serial, version, retval


def convert(temp):
    """Convert temperature. If the incoming value is 0, don't try an convert it, just return 0"""
    if temp <= 0.0:
        return 0.0
    else:
        tref = 51200
        temperature = ((tref - temp)/448.0) + 22.0
        return temperature

def get_data(sock, address, debug):
    """Get the inverter data"""
    # Get status
    request = formulate_request(0x57, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 9:
        print("Status request checksum is not good")
        return '', '', False
    else:
        error_code = get_2bytes(response, 7)
        error = ord(response[6])
        status_num = ord(response[5])
        status = ""
        if 0 <= status_num <= 5:
            status = STATUS_CODES[status_num]

    # Get the voltage, current, power and temperature data
    request = formulate_request(0x43, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 65:
        print("Data request checksum is not good")
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
            print("Could not retrieve data")
            retval = False

    # Get Total Energy
    request = formulate_request(0x45, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 9:
        print("Status request checksum is not good")
        retval = False
    else:
        total_energy = get_4bytes(response, 5)

    # Get Daily Energy
    request = formulate_request(0x9d, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 9:
        print("Status request checksum is not good")
        retval = False
    else:
        daily_energy = get_4bytes(response, 5)

    # Get Total Hours. Note that raw result in in seconds
    # Convert to hours by dividing by 3600
    request = formulate_request(0x46, address)
    response = send_recv(sock, request, debug)
    if not verify_checksum(response) or len(response) < 9:
        print("Status request checksum is not good")
        retval = False
    else:
        total_hours = get_4bytes(response, 5)
        total_hours = total_hours / 3600

    # Format all values, convert them to strings, and formaulet a header line
    # Return the line and the header line
    DC_string1_volts = format(DC_string1_volts, '0.2f')
    DC_string2_volts = format(DC_string2_volts, '0.2f')
    DC_string3_volts = format(DC_string3_volts, '0.2f')
    DC_string1_current = format(DC_string1_current, '0.2f')
    DC_string2_current = format(DC_string2_current, '0.2f')
    DC_string3_current = format(DC_string3_current, '0.2f')
    DC_string1_power = format(DC_string1_power, '0.2f')
    DC_string2_power = format(DC_string2_power, '0.2f')
    DC_string3_power = format(DC_string3_power, '0.2f')
    DC_string1_temperature = format(DC_string1_temperature, '0.2f')
    DC_string2_temperature = format(DC_string2_temperature, '0.2f')
    DC_string3_temperature = format(DC_string3_temperature, '0.2f')
    AC_phase1_volts = format(AC_phase1_volts, '0.2f')
    AC_phase2_volts = format(AC_phase2_volts, '0.2f')
    AC_phase3_volts = format(AC_phase3_volts, '0.2f')
    AC_phase1_current = format(AC_phase1_current, '0.2f')
    AC_phase2_current = format(AC_phase2_current, '0.2f')
    AC_phase3_current = format(AC_phase3_current, '0.2f')
    AC_phase1_power = format(AC_phase1_power, '0.2f')
    AC_phase2_power = format(AC_phase2_power, '0.2f')
    AC_phase3_power = format(AC_phase3_power, '0.2f')
    AC_phase1_temperature = format(AC_phase1_temperature, '0.2f')
    AC_phase2_temperature = format(AC_phase2_temperature, '0.2f')
    AC_phase3_temperature = format(AC_phase3_temperature, '0.2f')
    DC_power = format(DC_power, '0.2f')
    AC_power = format(AC_power, '0.2f')
    total_energy = format(total_energy, '0.2f')
    daily_energy = format(daily_energy, '0.2f')
    total_hours = format(total_hours, '0.2f')

    datetime = ap.get_datetime_str()

    if debug >= 1:
        print("Error=", error, " Error_Code=", error_code, " Status=", status)
        print("DC Volts1=", DC_string1_volts, " DC Volts2=", DC_string2_volts, " DC Volts3=", DC_string3_volts)
        print("DC Current1=", DC_string1_current, " DC Current2=", DC_string2_current, " DC Current3=", DC_string3_current)
        print("DC Power1=", DC_string1_power, " DC Power2=", DC_string2_power, " DC Power3=", DC_string3_power)
        print("DC Temperature1=", DC_string1_temperature, " DC Temperature2=", DC_string2_temperature, " DC Temperature3=", DC_string3_temperature)
        print("AC Volts1=", AC_phase1_volts, " AC Volts2=", AC_phase2_volts, " AC Volts3=", AC_phase3_volts)
        print("AC Current1=", AC_phase1_current, " AC Current2=", AC_phase2_current, " AC Current3=", AC_phase3_current)
        print("AC Power1=", AC_phase1_power, " AC Power2=", AC_phase2_power, " AC Power3=", AC_phase3_power)
        print("AC Temperature1=", AC_phase1_temperature, " AC Temperature2=", AC_phase2_temperature, " AC Temperature3=", AC_phase3_temperature)
        print("DC Power=", DC_power, " AC Power=", AC_power)
        print("Total Energy=", total_energy, " Daily Energy=", daily_energy, " Total Hours=", total_hours)
        print("Datetime=", datetime)


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

    return header, line, retval

def discover_inverters(sock, debug):
    """This will discover all the inverters, by checking addresses 1 to 255, inclusive"""
    for address in range(1, 255):
        try:
            model, string, phase, unused_name, serial, version, retval = get_metadata(sock, address, debug)
            if retval:
                print("Address: ", address, "; Model: ", model, "; String: ", string, "; Phase: ", phase, "; Serial: ", serial, "; Version: ", version)
        except:
            pass


class Config(object):
    """Config object for click"""
    def __init__(self):
        self.verbosity = 0


CONFIG = click.make_pass_decorator(Config, ensure=True)

@click.group()
@click.option('-v', '--verbose', count=True)
@CONFIG
def cli(config, verbose):
    """Command line entry point"""
    config.verbosity = verbose


@cli.command()
@click.argument('ip_address')
@CONFIG
def discover(config, ip_address):
    """Connect to the target IP address and run a scan of all 255 possible addresses"""
    # Open the socket
    retval, sock = open_socket(ip_address)
    if not retval:
        print("Could not connect to IP Address: ", ip_address)
        sys.exit(7)
    discover_inverters(sock, config.verbosity)
    close_socket(sock)

@cli.command()
@click.argument('ip_address')
@click.argument('bus_addresses')
@click.argument('output_directory')
@CONFIG
def log(config, ip_address, bus_addresses, output_directory):
    """Connect to the target IP address and log the inverter output for the given bus addresses"""
    # If the logging directory doesn't exist, create it
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Check that no other scripts are running
    pidfile = os.path.join(output_directory, PIDFILE)
    if ap.check_pidfile(pidfile, config.verbosity):
        print("This script is already running")
        sys.exit(4)

    start_time = time.time()
    # Open the socket
    retval, sock = open_socket(ip_address)
    if not retval:
        print("Could not connect to IP Address: ", ip_address)
        sys.exit(7)

    # This will check each inverter. If a bad line is received, it will try one more time
    for inverter_addr in ap.parse_address_list(bus_addresses):
        count = 2
        while count >= 1:
            # Query the data
            header, line, retval = get_data(sock, inverter_addr, config.verbosity)
            if retval:
                success = write_line(line, str(inverter_addr), output_directory, header, config.verbosity)
                if success:
                    break
            count = count - 1

    # Close the socket
    close_socket(sock)

    elapsed_time = time.time() - start_time
    if config.verbosity > 0:
        print("This request took: ", elapsed_time, " seconds.")

    # Remove the PID file
    if os.path.isfile(pidfile):
        os.unlink(pidfile)
