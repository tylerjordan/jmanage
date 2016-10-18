__copyright__ = "Copyright 2016 Tyler Jordan"
__version__ = "0.1.1"
__email__ = "tjordan@juniper.net"

import os
import platform
import subprocess
import datetime
import getopt

from jnpr.junos import *
from jnpr.junos.exception import *
from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors
from utility import *

credsCSV = ''
iplistfile = ''
listDictCSV = ''
iplist_dir = ''
config_dir = ''

listDict = []
mypwd = ''
myuser = ''
port = 22


def detect_env():
    """ Purpose: Detect OS and create appropriate path variables. """
    global listDictCSV
    global credsCSV
    global iplist_dir
    global config_dir

    if platform.system().lower() == "windows":
        #print "Environment Windows!"
        listDictCSV = ".\\data\\listdict.csv"
        iplist_dir = ".\\data\\iplists\\"
        config_dir = ".\\data\\configs\\"
    else:
        #print "Environment Linux/MAC!"
        listDictCSV = "./data/listdict.csv"
        iplist_dir = "./data/iplists/"
        config_dir = "./data/configs/"

def load_config_file(ip):
    """ Purpose: Load the selected device's configuration file into a variable. """
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

def ip_list():
    """ Purpose: Create a list of the IPs from provided text file. """
    iplist = []
    filepath = iplist_dir + iplistfile
    try:
        f = open(filePath, 'r')
    except Exception as err:
        print '{0} - Unable to open file. ERROR: {1}'.format(filepath, err)
        return False
    else:
        iplist = f.readlines()
        return iplist

def check_ip(ip):
    """ Purpose: Scans the device with the IP and handles action. """
    has_record = False
    #print "Recalling any stored records..."
    if get_record(ip):
        has_record = True
    record_attribs = [ 'serial_number', 'model', 'host_name', 'junos_code' ]


    # If we can ping the IP...
    if ping(ip):
        # Try to collect current chassis info
        #print "Getting current information..."
        remoteDict = run(ip, myuser, mypwd, port)
        # If info was collected...
        if remoteDict:
            # If this IP is associated with a record...
            if has_record:
                # Check that the existing record is up-to-date. If not, update.
                localDict = get_record(ip)
                if localDict['host_name'] == remoteDict['host_name']:
                    if localDict['serial_number'] == remoteDict['serial_number']:
                        if localDict['junos_code'] == remoteDict['junos_code']:
                            print "{0} - No Changes".format(ip)
                        else:
                            print "{0} - JunOS changed from {1} to {2}".format(ip, localDict['junos_code'], remoteDict['junos_code'])
                            change_record(ip, remoteDict['junos_code'], key='junos_code')
                    else:
                        print "{0} - S/N changed from {1} to {2}".format(ip, localDict['serial_number'], remoteDict['serial_number'])
                        change_record(ip, remoteDict['serial_number'], key='serial_number')
                        if localDict['model'] != remoteDict['model']:
                            print "{0} - Model changed from {1} to {2}".format(ip, localDict['model'], remoteDict['model'])
                            change_record(ip, remoteDict['model'], key='model')
                        if localDict['junos_code'] != remoteDict['junos_code']:
                            print "{0} - JunOS changed from {1} to {2}".format(ip, localDict['junos_code'], remoteDict['junos_code'])
                            change_record(ip, remoteDict['junos_code'], key='junos_code')
                else:
                    if localDict['serial_number'] != remoteDict['serial_number']:
                        print "{0} - S/N changed from {1} to {2}".format(ip, localDict['serial_number'], remoteDict['serial_number'])
                        change_record(ip, remoteDict['serial_number'], key='serial_number')
                        if localDict['model'] != remoteDict['model']:
                            print "{0} - Model changed from {1} to {2}".format(ip, localDict['model'], remoteDict['model'])
                            change_record(ip, remoteDict['model'], key='model')
                    # Do these regardless of S/N results
                    print "{0} - Hostname changed from {1} to {2}".format(ip, localDict['host_name'], remoteDict['host_name'])
                    change_record(ip, remoteDict['host_name'], key='host_name')
                    if localDict['junos_code'] != remoteDict['junos_code']:
                        print "{0} - JunOS changed from {1} to {2}".format(ip, localDict['junos_code'], remoteDict['junos_code'])
                        change_record(ip, remoteDict['junos_code'], key='junos_code')
                """
                for attrib in record_attribs:
                    if localDict[attrib] != remoteDict[attrib]:
                        print attrib + " changed from {0} to {1}!".format(localDict[attrib], remoteDict[attrib])
                        change_record(ip, remoteDict[attrib], key=attrib)
                """
            else:
                # If no, this is a device that hasn't been identified yet, create a new record
                print "{0} - Adding device as new record".format(ip),
                if add_record(ip):
                    print " - Successful"
                    return True
                else:
                    print " - Failed"
                    return False
        else:
            print "{0} - ERROR: Unable to collect information from device".format(ip)
            return False
        print "Checking config..."

    # If we can't ping, but we have a record
    elif has_record:
        # Set record status to "unreachable"
        print "{0} - ERROR: Unable to ping KNOWN device".format(ip)
        return False
    # If we can't ping, and have no record
    else:
        print "{0} - ERROR: Unable to ping".format(ip)
        return False

def get_record(ip='', hostname='', sn='', code=''):
    """ Purpose: Returns a record from the listDict containing hostname, ip, model, version, serial number. Providing
                three different methods to return the data.
        Parameters:
            ip          -   String of the IP of the device
            hostname    -   String of the device hostname
            sn          -   String of the device chassis serial number
            code        -   String of the JunOS code version
        Returns:
            A dictionary containing the device data or 'False' if no record is found
    """
    blank_record = {}
    #print "Getting record for ip: {0}".format(ip)
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
    elif code:
        for record in listDict:
            if record['junos_code'] == code:
                return record
    else:
        return blank_record

def add_record(ip):
    """ Purpose: Adds a record to list of dictionaries. """
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

def get_now_time():
    """ Purpose: Create a correctly formatted timestamp
        Returns: Timestamp
    """
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d-%H%M")

def change_record(ip, value, key):
    """ Purpose: Change an attribute of an existing record.
        Returns: String
    """
    change_dict = { key: value }
    for myrecord in listDict:
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

def fetch_config(ip):
    """ Purpose: Get current configuration from device.
        Returns: Text File
    """
    dev = Device(host=ip, user=myuser, passwd=mypwd)
    # Try to open a connection to the device
    try:
        print "Connecting to: {0}".format(ip)
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


def compare_configs(config1, config2):
    """ Purpose: To compare two configs and get the changes. """
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
        if not diffList:
            return False
        else:
            for line in diffList:
                if line[0] == '-':
                    print line,
                elif line[0] == '+':
                    print line,
            print
            return True
    else:
        print "Errors with compare configs..."
        return True

def update_config(ip, current_config):
    """ Purpose: Save the configuration for this """
    try:
        save_config_file(current_config, config_dir + items['host_name'] + ".conf")
    except Exception as err:
        print "Unable to save config {0} : {1}".format(ip, err)
        return False
    else:
        return True

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

def main(argv):
    """ Purpose: Capture command line arguments and populate variables. """
    global credsCSV
    global iplistfile
    try:
        opts, args = getopt.getopt(argv, "hc:i:",["creds=","iplist="])
    except getopt.GetoptError:
        print "device_refresh -c <credsfile> -i <iplistfile>"
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'device_refresh -c <credsfile> -i <iplistfile>'
            sys.exit()
        elif opt in ("-c", "--creds"):
            credsCSV = arg
        elif opt in ("-i", "--iplist"):
            iplistfile = arg
    print "Credentials file is ", credsCSV
    print "IP List file is ", iplistfile

# Main execution loop
if __name__ == "__main__":
    detect_env()
    main(sys.argv[1:])
    creds = csv_to_dict(credsCSV)
    myuser = creds['username']
    mypwd = creds['password']

    # Load records from existing CSV
    print "Loading records..."
    listDict = csv_to_listdict(listDictCSV)

    # Check existing records...
    print "Refreshing existing records..."
    for myrecord in listDict:
        check_ip(str(myrecord['ip']))
        current_config = fetch_config(myrecord['ip'])
        if compare_configs(load_config_file(ip=ip), current_config):
            print "Configs are different - updating..."
            if update_config(myrecord['ip'], current_config):
                print "Configs updated!"
            else:
                print "Config update failed!"
        else:
            print "Do nothing."

    # Check optional ip list
    iplist = ip_list()
    if iplist:
        print "Working on IP list..."
        for ip in iplist:
            check_ip(str(ip))
            current_config = fetch_config(ip)
            if compare_configs(load_config_file(ip=ip), current_config):
                print "Configs are different - updating..."
                if update_config(ip, current_config):
                    print "Configs updated!"
                else:
                    print "Config update failed!"
            else:
                print "Do nothing to the config."

    # Save the changes of the listDict to CSV
    listdict_to_csv(listDict, listDictCSV)
    print "Saved any changes."
    print "Completed Work!"