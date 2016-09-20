__copyright__ = "Copyright 2016 Tyler Jordan"
__version__ = "0.1.1"
__email__ = "tjordan@juniper.net"

import os
import platform
import subprocess
import datetime
import sys  # for writing to terminal
import paramiko  # https://github.com/paramiko/paramiko for -c -mc -put -get
import getpass  # for retrieving password input from the user without echoing back what they are typing.

from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors
from netaddr import *
from utility import *
from prettytable import PrettyTable
from jnpr.junos import *
from jnpr.junos.exception import ConnectError
from lxml import etree

listDict = []
listDictCSV = ".\\data\\listdict.csv"
passCSV = ".\\data\\pass.csv"
config_dir = ".\\data\\configs\\"
mypwd = ''
myuser = ''
port = 22


def ping(ip):
    """ Purpose: Determine if an IP is pingable

    :param ip: IP address of host to ping
    :return: True if ping successful
    """
    with open(os.devnull, 'w') as DEVNULL:
        try:
            # Check for Windows or Linux/MAC
            ping_param = "-n" if platform.system().lower() == "windows" else "-c"
            subprocess.check_call(
                ['ping', ping_param, '3', ip],
                stdout=DEVNULL,
                stderr=DEVNULL
            )
            return True
        except subprocess.CalledProcessError:
            return False



def information(connection, ip, software_info, host_name):
    """ Purpose: This is the function called when using -info.
                 It is grabs the model, running version, and serial number of the device.

    :param: connection:    This is the ncclient manager connection to the remote device.
            ip:            String containing the IP of the remote device, used for logging purposes.
            software_info: A "show version" aka "get-software-information".
            host_name:     The device host-name for output purposes.
    :return: text of requested output
    """
    try:
        model = software_info.xpath('//software-information/product-model')[0].text
        junos_code = (software_info.xpath('//software-information/package-information/comment')[0].text.split('[')[1].split(']')[0])
        chassis_inventory = connection.get_chassis_inventory(format='xml')
        serial_number = chassis_inventory.xpath('//chassis-inventory/chassis/serial-number')[0].text
        return {'host_name': host_name, 'ip': ip, 'model': model, 'junos_code': junos_code, 'serial_number': serial_number}
    except:
        print 'Host-name: {0} \nAccessed via: {1} \nDevice was reachable, the information was not found.'.format(host_name, ip)
        return False


def run(ip, username, password, port):
    """ Purpose: To open an NCClient manager session to the device, and run the appropriate function against the device.
        Parameters:
            ip          -   String of the IP of the device, to open the connection, and for logging purposes.
            username    -   The string username used to connect to the device.
            password    -   The string password used to connect to the device.
    """
    try:
        connection = manager.connect(host=ip,
                                     port=port,
                                     username=username,
                                     password=password,
                                     timeout=15,
                                     device_params={'name': 'junos'},
                                     hostkey_verify=False)
        connection.timeout = 300
    except errors.SSHError:
        print 'Unable to connect to device: {0} on port: {1}'.format(ip, port)
        return False
    except errors.AuthenticationError:
        print 'Bad username or password for device: {0}'.format(ip)
        return False
    except Exception as err:
        print 'Unable to connect to device: {0} with error: {1}'.format(ip, err)
        return False
    else:
        software_info = connection.get_software_information(format='xml')
        host_name = software_info.xpath('//software-information/host-name')[0].text
        output = information(connection, ip, software_info, host_name)
        #print "Print Configuration"
        #print connection.get_config(source='running', format='set')
        return output


def get_record(ip='', hostname='', sn=''):
    """ Purpose: Returns a record from the listDict containing hostname, ip, model, version, serial number. Providing
                three different methods to return the data.
        Parameters:
            ip          -   String of the IP of the device
            hostname    -   String of the device hostname
            sn          -   String of the device chassis serial number
        Returns:
            A dictionary containing the device data or 'False' if no record is found
    """
    print "Getting record for ip: {0}".format(ip)
    if ip:
        for record in listDict:
            if record['ip'] == ip:
                return record
    elif hostname:
        for record in listDict:
            if record['host_name'] == hostname:
                return record
    elif sn:
        for record in listDict:
            if record['serial_number'] == sn:
                return record
    return False


def scan_network(iplist):
    pass


def show_devices():
    """ Purpose: Display a table showing devices with general facts.
        Returns: Nothing
    """
    t = PrettyTable(['IP', 'Hostname', 'Model', 'Current Code', 'Serial Number', 'Last Updated'])
    for device in listDict:
        t.add_row([device['ip'], device['host_name'], device['model'], device['junos_code'], device['serial_number'], device['last_update']])
    print t


def add_record(ip):
    """ Purpose: Adds a record to list of dictionaries
        Returns: True or False
    """
    try:
        items = run(ip, myuser, mypwd, port)
        now = datetime.datetime.now()
        items['last_update'] = now.strftime("%Y-%m-%d-%H%M")
    except Exception as err:
        print 'ERROR: Unable to get record information for: {0} : {1}'.format(ip, err)
        return False
    else:
        if save_config_file(fetch_config(ip), config_dir + items['host_name'] + ".conf"):
            print "Configuration saved..."
        else:
            print "Unable to save configuration"
        listDict.append(items)
        return True

def change_record(ip, attribute):
    """ Purpose: Change an attribute of an existing record.
        Returns: String
    """
    for myrecord in listDict:
        if myrecord['ip'] == ip:
            listDict.remove()


def save_config_file(myconfig, filename):
    """ Purpose: Creates a file and adds text to the file.
        Returns: True or False
    """
    try:
        newfile = open(filename, "w+")
    except Exception as err:
        print 'ERROR: Unable to open file: {0} : {1}'.format(filename, err)
        return False
    else:
        newfile.write(myconfig)
        newfile.close()
        return True


def check_ip(ip):
    """ Purpose: Scans the device with the IP and handles action.
        Returns: True or False
    """
    has_record = False
    print "Recalling any stored records..."
    if get_record(ip):
        has_record = True

    # If we can ping the IP...
    if ping(ip):
        # Try to collect current chassis info
        print "Getting current information..."
        remoteDict = run(ip, myuser, mypwd, port)

        # If info was collected...
        if remoteDict:
            # If this IP is associated with a record...
            if has_record:
                # Check that the existing record is up-to-date. If not, update.
                localDict = get_record(ip)
                if localDict['host_name'] != remoteDict['host_name']:
                    print "Hostname changed from {0} to {1}!".format(localDict['host_name'], remoteDict['host_name'])

                if localDict['serial_number'] != remoteDict['serial_number']:
                    pass
                if localDict['model'] != remoteDict['model']:
                    pass
                if localDict['junos_code'] != remoteDict['junos_code']:
                    pass

            else:
                # If no, this is a device that hasn't been identified yet, create a new record
                print "Adding new device: {0}".format(ip)
                if add_record(ip):
                    print "Device Add Successful."
                    return True
                else:
                    print "Device Add Failed."
                    return False
        else:
            print "ERROR: Unable to collect information from device: {0}".format(ip)
            return False
    # If we can't ping, but we have a record
    elif has_record:
        # Set record status to "unreachable"
        print "ERROR: Unable to ping KNOWN device: {0}".format(ip)
        return False
    # If we can't ping, and have no record
    else:
        print "ERROR: Unable to ping: {0}".format(ip)
        return False


def fetch_config(ip):
    """ Purpose: Get current configuration from device.
        Returns: Text File
    """
    dev = Device(host=ip, user=myuser, passwd=mypwd)
    # Try to open a connection to the device
    try:
        print "------------------------- Opening connection to: {0} -------------------------\n".format(ip)
        print "User: {0}".format(myuser)
        print "Pass: {0}".format(mypwd)
        dev.open()
    # If there is an error when opening the connection, display error and exit upgrade process
    except ConnectError as err:
        print "Cannot connect to device {0} : {1}".format(ip, err)
    # If try arguments succeed...
    else:
        # Increase the default RPC timeout to accommodate install operations
        dev.timeout = 600
        # Get config and try to display

        # Following command requires 15.1+
        # myconfig = dev.rpc.get_configuration(dict(format='set'))

        # myconfig = dev.rpc.get_config()
        # print etree.tostring(myconfig)

        myconfig = dev.cli('show config | display set')
        return myconfig

# START OF SCRIPT #
if __name__ == '__main__':
    passDict = user_pass(passCSV)
    mypwd = passDict['pass']
    myuser = passDict['user']
    my_options = ['Display Database', 'Scan Devices', 'Save Database', 'Load Database', 'Fetch Config', 'Refresh Devices']
    while True:
        print "*" * 25 + "\n"
        answer = getOptionAnswerIndex('Choose your poison', my_options)
        print "\n" + "*" * 25
        if answer == "1":
            show_devices()
        elif answer == "2":
            my_network = getInputAnswer('Enter IP/Mask')
            for myip in IPNetwork(my_network).iter_hosts():
                print "Scanning {0} ...".format(myip)
                check_ip(str(myip))
        elif answer == "3":
            print "Saving Database to CSV..."
            listdict_to_csv(listDict, listDictCSV)
            print "Completed Save"
        elif answer == "4":
            print "Loading Database from CSV..."
            listDict = csv_to_listdict(listDictCSV)
            print "Completed Load"
        elif answer == "5":
            ip = getInputAnswer('Enter IP')
            print "Fetching Configuration..."
            fetch_config(ip)
        elif answer == "6":
            for myrecord in listDict:
                print "Refreshing {0} ...".format(myrecord['ip'])
                check_ip(str(myrecord['ip']))
        else:
            quit()

