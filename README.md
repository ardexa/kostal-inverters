# Purpose
Kostal (http://www.kostal-solar-electric.com/) supply retail and commercial grade Solar PV inverters. The purpose of this project is to collect data from Kostal Inverters and send the data to your cloud using Ardexa. Data from Kostal solar inverters is read using an Ethernet connection to the first inverter (and then RS485 for other inverters) and a Linux device such as a Raspberry Pi, or an X86 intel powered computer. 

# How does it work
This application is written in Python, to query Kostal inverters connected via Ethernet. This application will query 1 or more connected inverters at regular intervals. Data will be written to log files on disk in a directory specified by the user. Usage and command line parameters are as follows:

## Install
On a raspberry Pi, or other Linux machines (arm, intel, mips or whetever), make sure Python is installed (which it should be). Then install the dependancies and this package as follows:
```
git clone https://github.com/ardexa/kostal-inverters.git
cd kostal-inverters/scripts
pip install .
```

## Usage
To scan the whole 1-255 RS485 address range and print out the inverter metadata
```
Usage: kostal_ardexa discover IP_address
Eg; kostal_ardexa discover 192.168.1.3
```

Send production data to a file on disk 
```
Usage: kostal_ardexa log IP_address bus_addresses output_directory
Eg; kostal_ardexa log 192.168.1.3 1-4 /opt/ardexa
```
- IP Address = ..something like: 192.168.1.4
- Bus Addresses = List of bus addresses using commas and hyphens, e.g. `1-4,6,10-20` (this is an RS485 address, NOT Ethernet). 
- ouput directory = logging directory; eg; /opt/logging/


To view debug output, increase the verbosity using the `-v` flag.
- standard (no messages, except errors), `-v` (discovery messages) or `-vv` (all messages)

## Connecting to, and communicating with, Kostal Inverters
In this project, please take a look at the 'docs' directory. You will find a version of the "Installation and
Operating Manual PIKO Inverter for versions 4.2, 5.5, 7.0, 8.3, 10.1". This document is from Kostal. If you go to Page 24 (Figure 32), you will see that you can communicate to one or more inverters directly via an Ethernet cable to the FIRST INVERTER. Other inverters need to be connected via RS485 daisy chain. RS485 is a signalling protocol that allows many devices to share the same physical pair of wires, in a master master/slave relationship.

So remember these things:
1. Connection from your Linux device to the first inverter is via an ethernet cable (via a switch or using a crossover cable).
2. Other inverters are connected to this first one via RS485 daisy chain.
3. You MUST know the IP Address of the FIRST inverters only.
4. Each inverter (if there are more than 1) must have a UNIQUE RS485 address

If in doubt, see the latest documentation on the Kostal website.

## How to use the script

## Collecting to the Ardexa cloud
Collecting to the Ardexa cloud is free for up to 3 Raspberry Pis (or equivalent). Ardexa provides free agents for ARM, Intel x86 and MIPS based processors. To collect the data to the Ardexa cloud do the following:
- Create a `RUN` scenario to schedule the Ardexa Kostal script to run at regular intervals (say every 300 seconds/5 minutes).
- Then use a `CAPTURE` scenario to collect the csv (comma separated) data from the filename (say) `/opt/ardexa/Kostal/logs/`. This file contains a header entry (as the first line) that describes the CSV elements of the file.

## Help
Contact Ardexa at support@ardexa.com, and we'll do our best efforts to help.
