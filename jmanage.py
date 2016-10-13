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
import difflib

from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors
from netaddr import *
from utility import *
from prettytable import PrettyTable
from jnpr.junos import *
from jnpr.junos.exception import *
from lxml import etree

listDict = []
listDictCSV = ""
passCSV = ""
config_dir = ""
mypwd = ''
myuser = ''
port = 22


def detect_env():
    """ Purpose: Detect OS and create appropriate path variables
    :param: None
    :return: None
    """
    global listDictCSV
    global passCSV
    global config_dir

    if platform.system().lower() == "windows":
        print "Environment Windows!"
        listDictCSV = ".\\data\\listdict.csv"
        passCSV = ".\\data\\pass.csv"
        config_dir = ".\\data\\configs\\"
    else:
        print "Environment Linux/MAC!"
        listDictCSV = "./data/listdict.csv"
        passCSV = "./data/pass.csv"
        config_dir = "./data/configs/"

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
    blank_record = {}
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
    else:
        return blank_record


def scan_network(iplist):
    pass


def get_now_time():
    """ Purpose: Create a correctly formatted timestamp
        Returns: Timestamp
    """
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d-%H%M")


def show_devices():
    """ Purpose: Display a table showing devices with general facts.
        Returns: Nothing
    """
    t = PrettyTable(['IP', 'Hostname', 'Model', 'Current Code', 'Serial Number', 'Update Attempt', 'Update Success', 'Config Attempt', 'Config Success'])
    for device in listDict:
        t.add_row([device['ip'], device['host_name'], device['model'], device['junos_code'], device['serial_number'], device['last_update_attempt'], device['last_update_success'], device['last_config_attempt'], device['last_config_success']])
    print t


def add_record(ip):
    """ Purpose: Adds a record to list of dictionaries
        Returns: True or False
    """
    try:
        items = run(ip, myuser, mypwd, port)
    except Exception as err:
        print 'ERROR: Unable to get record information for: {0} : {1}'.format(ip, err)
        items['last_update_attempt'] = get_now_time()
        listDict.append(items)
        return False
    else:
        items['last_update_attempt'] = get_now_time()
        items['last_update_success'] = get_now_time()
        if save_config_file(fetch_config(ip), config_dir + items['host_name'] + ".conf"):
            items['last_config_success'] = get_now_time()
            items['last_config_attempt'] = get_now_time()
            print 'Configuration captured: {0}'.format(ip)
            listDict.append(items)
            return True
        else:
            items['last_config_attempt'] = get_now_time()
            print 'ERROR: Unable to capture configuration: {0}'.format(ip)
            listDict.append(items)
            return True


def compare_configs(config1, config2):
    print "*"*10 + "CONFIG1" + "*"*10
    print config1
    print "*"*10 + "CONFIG2" + "*"*10
    print config2
    if config1 and config2:
        config1_lines = config1.splitlines(1)
        config2_lines = config2.splitlines(1)

        diffInstance = difflib.Differ()
        diffList = list(diffInstance.compare(config1_lines, config2_lines))

        print '-'*50
        print "Lines different in config1 from config2:"
        for line in diffList:
            if line[0] == '-':
                print line,
            elif line[0] == '+':
                print line,
        print
    else:
        print "Errors with compare configs..."


def compare_configs_two(config1, config2):
    diff = difflib.unified_diff(
        config2.splitlines(1),
        config1.splitlines(1),
        fromfile='config2',
        tofile='config1',
        n=0,
    )
    for line in diff:
        for prefix in ('---', '+++', '@@'):
            if line.startswith(prefix):
                break
        else:
            sys.stdout.write(line[1:])


def change_record(ip, value, key):
    """ Purpose: Change an attribute of an existing record.
        Returns: String
    """
    change_dict = { key: value }
    for myrecord in listDict:
        print "In Loop"
        # If we've found the correct record...
        if myrecord['ip'] == ip:
            try:
                # Trying to update the record...
                now = get_now_time()
                time_dict = {'last_update_attempt': now}
                myrecord.update(time_dict)
                myrecord.update(change_dict)
            except Exception as err:
                # Error checking...
                print "ERROR: Unable to update record value {0} : {1}".format(ip, err)
                return False
            else:
                # If the record change was successful...
                now = get_now_time()
                time_dict = { 'last_update_success': now }
                myrecord.update(time_dict)
                return True


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


def load_config_file(ip):
    record = get_record(ip=ip)
    if record:
        my_file = config_dir + record['host_name'] + '.conf'
        try:
            file_string = open(my_file, 'r').read()
        except Exception as err:
            print 'ERROR: Unable to read file: {0} : {1}'.format(my_file, err)
            return False
        else:
            return file_string
    else:
        print "Problem getting record information..."


def check_ip(ip):
    """ Purpose: Scans the device with the IP and handles action.
        Returns: True or False
    """
    has_record = False
    print "Recalling any stored records..."
    if get_record(ip):
        has_record = True
    record_attribs = [ 'serial_number', 'model', 'host_name', 'junos_code' ]


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
                change_record(ip, localDict[''])
                for attrib in record_attribs:
                    if localDict[attrib] != remoteDict[attrib]:
                        print attrib + " changed from {0} to {1}!".format(localDict[attrib], remoteDict[attrib])
                        change_record(ip, remoteDict[attrib], key=attrib)
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
    except ConnectRefusedError as err:
        print "Cannot connect to device {0} : {1}".format(ip, err)
    # If try arguments succeed...
    else:
        # Increase the default RPC timeout to accommodate install operations
        dev.timeout = 600
        myconfig = dev.cli('show config | display set')
        return myconfig

# START OF SCRIPT #
if __name__ == '__main__':
    try:
        detect_env()
    except Exception as err:
        print "Problem detecting OS type..."
        quit()
    else:
        print "Pass directory: {0}".format(passCSV)
        passDict = user_pass(passCSV)
        mypwd = passDict['pass']
        myuser = passDict['user']
        my_options = ['Display Database', 'Scan Devices', 'Save Database', 'Load Database', 'Fetch Config',
                      'Refresh Devices', 'Compare Configs']
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
                myconfig = fetch_config(ip)
                if myconfig:
                    print "Got configuration..."
                else:
                    print "No configuration..."
            elif answer == "6":
                for myrecord in listDict:
                    print "Refreshing {0} ...".format(myrecord['ip'])
                    check_ip(str(myrecord['ip']))
            elif answer == "7":
                ip = getInputAnswer('Enter IP')
                compare_configs(load_config_file(ip=ip), fetch_config(ip))
            else:
                quit()
