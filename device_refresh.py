__copyright__ = "Copyright 2016 Tyler Jordan"
__version__ = "0.1.1"
__email__ = "tjordan@juniper.net"

# ------------------------------------------------------------------------------------------------------------------- #
# listDictCSV Database Attributes:
# ip ................. Management IP of Device
# hostname .......... Hostname of Device
# version ......... Juniper Code Version (ie 13.2X51-D35.3)
# serialnumber ...... Serial Number of Chassis
# model .............. Juniper Model Number (ie. EX4300-48P)
# last_access......... Last time device was accessed by script
# last_config_check .. Last time device config was checked by script
# last_config_change . Last time device config was changed by script
# last_param_check ... Last time device parameters were checked by script
# last_param_change .. Last time device parameter was changed by script
# last_temp_check .... Last time device template was checked by script
#

# Logs:
# Access_Error_Log.csv - Timestamped error messages returned from attempting to connect to devices
# Ops_Error_Log.csv ---- Timestamped error messages returned from running param, config, or template funtions
# New_Devices_Log.csv -- Timestamped list of devices that have been added
# Fail_Devices_Log.csv - Timestamped list of devices that are not accessible
#

# Miscellaneous Files:
# ------------------------------------------------------------------------------------------------------------------- #

import os
import platform
import subprocess
import datetime
import getopt
import re
import time
import multiprocessing

from jnpr.junos import *
from jnpr.junos.exception import *
from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors
from utility import *

# Paths
iplist_dir = ''
config_dir = ''
log_dir = ''
template_dir = ''
dir_path = ''

# Files
listDictCSV = ''
credsCSV = ''
iplistfile = ''
template_file = ''
template_csv = ''
access_error_log = ''
ops_error_log = ''
new_devices_log = ''
fail_devices_csv = ''

# Params
addl_opt = ''
subsetlist = ''
listDict = []
mypwd = ''
myuser = ''
port = 22
num_of_configs = 5

# Check Lists
no_changes_ips = []
no_ping_ips = []
no_netconf_ips = []
no_auth_ips = []
no_connect_ips = []
config_save_error_ips = []
config_update_error_ips = []
param_attrib_error_ips = []
templ_error_ips = []
param_change_ips = []
config_change_ips = []
templ_change_ips = []

def detect_env():
    """ Purpose: Detect OS and create appropriate path variables. """
    global template_file
    global template_csv
    global access_error_log
    global ops_error_log
    global new_devices_log
    global fail_devices_csv
    global listDictCSV
    global credsCSV
    global iplist_dir
    global config_dir
    global template_dir
    global log_dir
    global dir_path

    dir_path = os.path.dirname(os.path.abspath(__file__))
    if platform.system().lower() == "windows":
        #print "Environment Windows!"
        listDictCSV = os.path.join(dir_path, "data\\listdict.csv")
        iplist_dir = os.path.join(dir_path, "data\\iplists")
        config_dir = os.path.join(dir_path, "data\\configs")
        template_dir = os.path.join(dir_path, "data\\templates")
        log_dir = os.path.join(dir_path, "data\\logs")

    else:
        #print "Environment Linux/MAC!"
        listDictCSV = os.path.join(dir_path, "data/listdict.csv")
        iplist_dir = os.path.join(dir_path, "data/iplists")
        config_dir = os.path.join(dir_path, "data/configs")
        template_dir = os.path.join(dir_path, "data/templates")
        log_dir = os.path.join(dir_path, "data/logs")

    # Statically defined files and logs
    template_csv = os.path.join(dir_path, template_dir, "Template_Regex.csv")
    template_file = os.path.join(dir_path, template_dir, "Template.conf")
    access_error_log = os.path.join(log_dir, "Access_Error_Log.csv")
    ops_error_log = os.path.join(log_dir, "Ops_Error_Log.csv")
    new_devices_log = os.path.join(log_dir, "New_Devices_Log.csv")
    fail_devices_csv = os.path.join(log_dir, "Fail_Devices_Log.csv")

def load_config_file(ip, newest):
    """ Purpose: Load the selected device's configuration file into a variable. """
    record = get_record(ip=ip)
    if record:
        my_file = get_old_new_file(record, newest)
        if my_file:
            try:
                file_string = open(my_file, 'r').read()
            except Exception as err:
                print 'ERROR: Unable to read file: {0} | File: {1}'.format(err, my_file)
                return False
            else:
                return file_string
        else:
            return my_file
    else:
        print "Problem getting record information..."

def get_old_new_file(record, newest):
    """ Purpose: Returns the oldest config file from specified IP
        Parameters:     newest - Is either T or F, True means get the newest file, False, means get the oldest.
    """
    filtered_list = []
    if record:
        # Create the appropriate absolute path for the config file
        my_dir = os.path.join(config_dir, getSiteCode(record), record['hostname'])
        if os.path.exists(my_dir):
            for file in listdir(my_dir):
                if file.startswith(record['hostname']):
                    filtered_list.append(os.path.join(my_dir, file))
            try:
                sorted_list = sorted(filtered_list, key=os.path.getctime)
            except Exception as err:
                print "Error with sorted function. ERROR: {0}".format(err)
            else:
                if sorted_list:
                    if newest:
                        return sorted_list[-1]
                    else:
                        return sorted_list[0]
                else:
                    return filtered_list
        # Returns an empty list, if directory doesn't exist
        else:
            return filtered_list


def remove_template_file(record):
    file_start = "Template_Deviation_"
    device_dir = os.path.join(config_dir, getSiteCode(record), record['hostname'])
    if os.path.exists(device_dir):
        for file in getFileList(device_dir):
            if file.startswith(file_start):
                try:
                    os.remove(os.path.join(device_dir, file))
                except Exception as err:
                    print "Problem removing file: {0} ERROR: {1}".format(file, err)
        return True
    else:
        print "Directory does not exist: {0}".format(device_dir)
        return False


def get_file_number(record):
    file_num = 0
    if record:
        my_dir = os.path.join(config_dir, getSiteCode(record), record['hostname'])
        for file in listdir(my_dir):
            if file.startswith(record['hostname']):
                file_num += 1
    return file_num

def load_config_file_list(ip, newest):
    """ Purpose: Load the selected device's configuration file into a list.
    """
    record = get_record(ip=ip)
    linelist = []
    if record:
        my_file = get_old_new_file(record, newest)
        try:
            linelist = line_list(my_file)
        except Exception as err:
            print 'ERROR: Unable to read file: {0} | File: {1}'.format(err, my_file)
            return False
        else:
            return linelist
    else:
        print "Problem getting record information..."


def directory_check(record):
    """ Purpose: Check if the site/device dirs exists. Creates it if it does not.
        Returns: True or False
    """
    # Check for site specific directory
    if not os.path.isdir(os.path.join(config_dir, getSiteCode(record))):
        try:
            os.mkdir(os.path.join(config_dir, getSiteCode(record)))
        except Exception as err:
            print "Failed Creating Directory -> ERROR: {0}".format(err)
            return False

    # Check for the device specific directory
    if os.path.isdir(os.path.join(config_dir, getSiteCode(record), record['hostname'])):
        return True
    else:
        try:
            os.mkdir(os.path.join(config_dir, getSiteCode(record), record['hostname']))
        except Exception as err:
            print "Failed Creating Directory -> ERROR: {0}".format(err)
            return False
        else:
            return True

    '''
    try:
        site_dir = os.path.join(config_dir, getSiteCode(record), record['hostname'])
    except Exception as err:
        print "Failed Creating Site Path -> ERROR: {0}".format(err)
        return False
    else:
        # Check if the appropriate site directory is created. If not, then create it.
        if not os.path.isdir(site_dir):
            try:
                os.mkdir(site_dir)
            except Exception as err:
                print "Failed Creating Directory -> ERROR: {0}".format(err)
                return False
    return True
    '''

def save_config_file(myconfig, record):
    """ Purpose: Creates a config file and adds text to the file.
        Returns: True or False
    """
    # Check if the appropriate site directory is created. If not, then create it.
    directory_check(record)

    # Create the filename
    now = get_now_time()
    site_dir = os.path.join(config_dir, getSiteCode(record), record['hostname'])
    filename = record['hostname'] + "_" + now + ".conf"
    fileandpath = os.path.join(site_dir, filename)
    try:
        newfile = open(fileandpath, "w+")
    except Exception as err:
        #print 'ERROR: Unable to open file: {0} | File: {1}'.format(err, fileandpath)
        add_to_csv_sort(record['ip'] + ";" + str(err) + ";" + get_now_time(), ops_error_log)
        return False
    else:
        # Remove excess configurations if necessary
        if get_file_number(record) > 5:
            del_file = get_old_new_file(record, newest=False)
            try:
                os.remove(del_file)
            except Exception as err:
                add_to_csv_sort(record['ip'] + ";" + str(err) + ";" + get_now_time(), ops_error_log)
                #print "ERROR: Unable to remove old file: {0} | File: {1}".format(err, del_file)
        try:
            newfile.write(myconfig)
        except Exception as err:
            #print "ERROR: Unable to write config to file: {0}".format(err)
            add_to_csv_sort(record['ip'] + ";" + str(err) + ";" + get_now_time(), ops_error_log)
            return False
        else:
            # Update configuration change time for record
            record.update({'last_config_change': get_now_time()})
            newfile.close()
            return True


def line_list(filepath):
    """ Purpose: Create a list of lines from the file defined. """
    linelist = []
    try:
        f = open(filepath, 'r')
    except IOError as ioex:
        if ioex.errno == 2:
            print "No IPList Defined"
        else:
            print 'IOERROR: Unable to open file: {0} | File: {1}'.format(err, filepath)
        return False
    except Exception as err:
        print 'ERROR: Unable to open file: {0} | File: {1}'.format(err, filepath)
    else:
        linelist = f.readlines()
        f.close()
        return linelist


def check_params(ip):
    """ Purpose: Scans the device with the IP and handles action. """
    # 0 = Unable to Check, 1 = No Changes, 2 = Changes Detected
    returncode = 1
    # Store the results of check and returncode
    results = []
    # Try to collect current chassis info
    remoteDict = fetch_params(ip, indbase=True)
    #remoteDict = run(ip, myuser, mypwd, port)
    # If info was collected...
    if remoteDict:
        # Get current information to compare against database info
        localDict = get_record(ip)
        if localDict:
            # Update database date for parameter check
            localDict.update({'last_param_check': get_now_time()})
            # Check that the existing record is up-to-date. If not, update.
            if not localDict['hostname'] == remoteDict['hostname']:
                results.append("Hostname changed from " + localDict['hostname'] + " to " + remoteDict['hostname'])
                change_record(ip, remoteDict['hostname'], key='hostname')
                returncode = 2

            if not localDict['serialnumber'] == remoteDict['serialnumber']:
                results.append("S/N changed from " + localDict['serialnumber'] + " to " + remoteDict['serialnumber'])
                change_record(ip, remoteDict['serialnumber'], key='serialnumber')
                returncode = 2

            if not localDict['version'] == remoteDict['version']:
                results.append("JunOS changed from " + localDict['version'] + " to " + remoteDict['version'])
                change_record(ip, remoteDict['version'], key='version')
                returncode = 2

            if not localDict['model'] == remoteDict['model']:
                results.append("Model changed from " + localDict['model'] + " to " + remoteDict['model'])
                change_record(ip, remoteDict['model'], key='model')
                returncode = 2
        else:
            returncode = 0
            results.append("ERROR: Unable to collect params from database.")
    # If we are unable to collect info from this device
    else:
        returncode = 0
        results.append("ERROR: Unable to collect current params from device")

    # Return the info to caller
    results.append(returncode)
    return results


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
    has_record = False
    #print "Getting record for ip: {0}".format(ip)
    if ip:
        for record in listDict:
            if record['ip'] == ip:
                return record
    elif hostname:
        for record in listDict:
            if record['hostname'] == hostname:
                return record
    elif sn:
        for record in listDict:
            if record['serialnumber'] == sn:
                return record
    elif code:
        for record in listDict:
            if record['version'] == code:
                return record
    else:
        return has_record

def add_record(ip):
    """ Purpose: Adds a record to list of dictionaries.
    """
    items = fetch_params(ip, indbase=False)
    #items = run(ip, myuser, mypwd, port)
    if not items:
        # Record an error if the items doesn't return anything
        return False
    else:
        # Save config file and add attributes to
        now = get_now_time()
        if save_config_file(fetch_config(ip), items):
            items['last_config_check'] = now
            items['last_config_change'] = now
        items['last_access'] = now
        items['last_param_change'] = now
        items['last_param_check'] = now
        items['last_temp_check'] = ''
        items['ip'] = ip
        listDict.append(items)
        return True

# Return the site code by extracting from a provided hostname
def getSiteCode(record):
    hostname = record['hostname'].upper()
    if re.match(r'SW[A-Z]{3}', hostname):
        siteObj = re.match(r'SW[A-Z]{3}', hostname)
    elif re.match(r'S[A-Z]{3}', hostname):
        siteObj = re.match(r'S[A-Z]{3}', hostname)
    else:
        mydirect = "MISC"
        return mydirect

    return siteObj.group()[-3:]

"""
def ping(ip):
    # Purpose: Determine if an IP is pingable
    #:param ip: IP address of host to ping
    #:return: True if ping successful
    
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
        except subprocess.CalledProcessError as err:
            add_to_csv_sort(ip + ";" + str(err) + ";" + get_now_time(), access_error_log)
            return False
"""

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
                myrecord.update(change_dict)
            except Exception as err:
                # Error checking...
                print "ERROR: Unable to update record value: {0} | Device: {1}".format(err, ip)
                add_to_csv_sort(
                    ip + ";" + "Error changing " + key + " to " + value + ". ERROR:(" + str(err) + ");" + get_now_time() + "\n",
                    ops_error_log)
                return False
            # If the record change was successful...
            else:
                myrecord.update({'last_param_change': get_now_time()})
                return True

# This function attempts to open a connection with the device. If successful, session is returned,
def connect(ip, indbase=False):
    """ Purpose: Get current configuration from device.
        Returns: Device object / False
    """
    #make_dev_start = time.clock()
    #Device.auto_probe = 15
    dev = Device(host=ip, user=myuser, passwd=mypwd, auto_probe=True)
    #make_dev = time.clock() - make_dev_start
    #print('Create device time: %8.3f sec.' % make_dev)
    # Try to open a connection to the device
    try:
        #open_dev_start = time.clock()
        dev.open()
        #open_dev = time.clock() - open_dev_start
        #print('Open device time: %8.3f sec.' % open_dev)
    # If there is an error when opening the connection, display error and exit upgrade process
    except ConnectRefusedError as err:
        no_netconf_ips.append(ip)
        add_to_csv_sort(
            ip + ";" + "Host Reachable, but NETCONF not configured. ERROR:(" + str(err) + ");" + get_now_time() + "\n",
            access_error_log)
        return False
    except ConnectAuthError as err:
        no_auth_ips.append(ip)
        add_to_csv_sort(
            ip + ";" + "Unable to connect with credentials. User:" + myuser + " ERROR:(" + str(err) + ");" + get_now_time() + "\n",
            access_error_log)
        return False
    except ConnectTimeoutError as err:
        no_ping_ips.append(ip)
        err_message = ip + ";" + "Timeout error, possible IP reachability issues. ERROR:(" + str(err) + ");" + get_now_time() + "\n"
        fail_check(ip, get_now_time(), indbase, err_message)
        return False
    except ProbeError as err:
        no_ping_ips.append(ip)
        err_message = ip + ";" + "Probe timeout, possible IP reachability issues. ERROR:(" + str(err) + ");" + get_now_time() + "\n"
        fail_check(ip, get_now_time(), indbase, err_message)
        return False
    except ConnectError as err:
        no_connect_ips.append(ip)
        err_message = ip + ";" + "Unknown connection issue. DEBUG:(" + str(err) + ");" + get_now_time() + "\n"
        fail_check(ip, get_now_time(), indbase, err_message)
        return False
    except Exception as err:
        no_connect_ips.append(ip)
        err_message = ip + ";" + "Undefined exception. DEBUG:(" + str(err) + ");" + get_now_time() + "\n"
        fail_check(ip, get_now_time(), indbase, err_message)
        return False
    # If try arguments succeed...
    else:
        return dev

# Perform database steps on failed devices
def fail_check(ip, now, indbase, err_message):
    # Number of days to keep IP after first fail attempt
    attempt_limit = 10
    matched = False

    if indbase:
        myListDict = csv_to_listdict(fail_devices_csv)
        # Go through failed devices log, find a specific ip
        for myDict['ip'] in myListDict:
            # If we find the IP in this list
            if myDict['ip'] == ip:
                matched = True
                myDict.update({'last_attempt': get_now_time()})
                days_exp = get_now_time().days - myDict['date_added'].days
                if days_exp > attempt_limit:
                    myListDict.remove(myDict)
                break
        # If this device is not in the failed list
        if not matched:
            # Create new record
            mylist = []
            mydicts = {
                'ip': ip,
                'last_attempt': get_now_time(),
                'date_added': get_now_time(),
            }
            mylist.append(mydicts)
            attribOrder = ['ip', 'last_attempt', 'date_added']
            # Add record to failed csv
            listdict_to_csv(mylist, fail_devices_csv, attribOrder)
        # Do this for devices in database
        add_to_csv_sort(err_message, access_error_log)
    # This applies to all unreachable devices, not in database already, so new devices
    # Don't do anything, these failures are recorded in new_devices_log
    else:
        pass


def fetch_config(ip):
    """ Purpose: Get current configuration from device.
        Returns: Text File
    """
    dev = connect(ip)
    # Increase the default RPC timeout to accommodate install operations
    if dev:
        myconfig = dev.cli('show config | display set', warning=False)
        dev.close()
        return myconfig
    else:
        return False


def fetch_params(ip, indbase):
    # Purpose: Collect the parameters needed for the database.
    # Returns: Dictionary
    #fact_list = ['hostname', 'serialnumber', 'model', 'version']
    facts = {}
    dev = connect(ip, indbase)
    if dev:
        #gather_facts_start = time.clock()
        facts['hostname'] = dev.facts['hostname']
        facts['serialnumber'] = dev.facts['serialnumber']
        facts['model'] = dev.facts['model']
        facts['version'] = dev.facts['version']
        #for key,val in dev.facts.items():
        #    if key in fact_list:
        #        facts[key] = val
        #gather_facts = time.clock() - gather_facts_start
        #print('Gather facts time: %8.3f sec.' % gather_facts)
        #close_dev_start = time.clock()
        dev.close()
        #close_dev = time.clock() - close_dev_start
        #print('Close device time: %8.3f sec.' % close_dev)
    return facts


def information(connection, ip, software_info, hostname):
    """ Purpose: This is the function called when using -info.
                 It is grabs the model, running version, and serial number of the device.

    :param: connection:    This is the ncclient manager connection to the remote device.
            ip:            String containing the IP of the remote device, used for logging purposes.
            software_info: A "show version" aka "get-software-information".
            hostname:     The device host-name for output purposes.
    :return: text of requested output
    """
    try:
        model = software_info.xpath('//software-information/product-model')[0].text
        version = (software_info.xpath('//software-information/package-information/comment')[0].text.split('[')[1].split(']')[0])
        chassis_inventory = connection.get_chassis_inventory(format='xml')
        serialnumber = chassis_inventory.xpath('//chassis-inventory/chassis/serial-number')[0].text
        return {'hostname': hostname, 'ip': ip, 'model': model, 'version': version, 'serialnumber': serialnumber}
    except:
        #print '\t- ERROR: Device was reachable, the information was not found.'
        add_to_csv_sort(ip + ";" + "Unable to gather system information" + ";" + get_now_time() + "\n", ops_error_log)
        return False


def run(ip, username, password, port):
    """ Purpose: To open an NCClient manager session to the device, and run the appropriate function against the device.
        Parameters:
            ip          -   String of the IP of the device, to open the connection, and for logging purposes.
            username    -   The string username used to connect to the device.
            password    -   The string password used to connect to the device.
    """
    try:
        #make_conn_start = time.clock()
        connection = manager.connect(host=ip,
                                     port=port,
                                     username=username,
                                     password=password,
                                     timeout=15,
                                     device_params={'name': 'junos'},
                                     hostkey_verify=False)
        #make_conn = time.clock() - make_conn_start
        #print('Make conn time: %8.3f sec.' % make_conn)
        connection.timeout = 300
    except Exception as err:
        print '\t- ERROR: Unable to connect using NCCLIENT. ERROR: {0}'.format(err)
        add_to_csv_sort(ip + ";" + str(err) + ";" + get_now_time(), access_error_log)
        return False
    else:
        #gather_info_start = time.clock()
        try:
            software_info = connection.get_software_information(format='xml')
        except Exception as err:
            add_to_csv_sort(ip + ";" + str(err).strip('\b\r\n') + ";" + get_now_time() + "\n", ops_error_log)
            return False
        # Collect information from device
        hostname = software_info.xpath('//software-information/host-name')[0].text
        output = information(connection, ip, software_info, hostname)
        #gather_info = time.clock() - gather_info_start
        #print('Gather info time: %8.3f sec.' % gather_info)
        # Close the session
        #close_conn_start = time.clock()
        connection.close_session()
        #close_conn = time.clock() - close_conn_start
        #print('Close conn time: %8.3f sec.' % close_conn)
        # Determine what to return
        if not output:
            return False
        return output


def config_compare(record):
    """ Purpose: To compare two configs and get the differences, log them
        Parameters:
            record          -   Object that contains parameters of devices
            logfile         -   Reference to log object, for displaying and logging output
    """
    results = []
    # 0 = Save Failed, 1 = No Changes, 2 = Changes Detected, 3 = Update Failed
    returncode = 1

    # Check if the appropriate site directory is created. If not, then create it.
    loaded_config = load_config_file(record['ip'], newest=True)
    if not loaded_config:
        if save_config_file(fetch_config(record['ip']), record):
            results.append("No Existing Config, Configuration Saved\n")
        else:
            results.append("No Existing Config, Configuration Save Failed\n")
            returncode = 0
    else:
        current_config = fetch_config(record['ip'])
        if current_config:
            # Compare configurations
            change_list = compare_configs(loaded_config, current_config)
            # Update config check date in record
            record.update({'last_config_check': get_now_time()})
            if change_list:
                returncode = 2
                # Try to write diffList output to a list
                for item in change_list:
                    results.append(item)
                    save_config_file(current_config, record['ip'])
                if not save_config_file(current_config, record['ip']):
                    returncode = 3
        else:
            results.append("Unable to retrieve configuration\n")
            returncode = 0
    results.append(returncode)
    return results

def template_scanner(regtmpl_list, record):
    """ Purpose: To compare a regex list against a config list
        Parameters:
            regtmpl_list    -   List of template set commands with regex
            config_list     -   List of set commands from chassis
            logfile         -   Reference to log object, for displaying and logging output
    """
    # Template Results: 0 = Error, 1 = No Changes, 2 = Changes
    results = []
    returncode = 1
    config_list = load_config_file_list(record['ip'], newest=True)

    nomatch = True
    try:
        firstpass = True
        for regline in regtmpl_list:
            matched = False
            if regline != "":
                for compline in config_list:
                    compline = re.sub(r"\\n", r"", compline)
                    if re.search(regline, compline):
                        matched = True
                if not matched:
                    if firstpass:
                        firstpass = False
                    nomatch = False
                    results.append(regline)
                    returncode = 2
    except Exception as err:
        results.append("ERROR: Problems preforming template scan")
        returncode = 0
    else:
        record.update({'last_temp_check': get_now_time()})
        if nomatch:
            returncode = 1
    finally:
        results.append(returncode)
        return results

def template_regex():
    # Regexs for template comparisons
    with open(template_csv) as f:
        d = dict(filter(None, csv.reader(f, delimiter=";")))

    # Process for replacing placeholders with regexs
    varindc = "{{"
    templ_list = line_list(template_file)
    regtmpl_list = []
    for tline in templ_list:
        tline = re.sub(r"\*", r"\*", tline)
        if varindc in tline:
            str_out = ''
            for key in d:
                str_out = re.subn(key, d[key], tline)
                if str_out[1] > 0:
                    tline = str_out[0]
            regtmpl_list.append(tline.strip('\n\t'))
        elif tline != '':
            regtmpl_list.append(tline.strip('\n\t'))

    return regtmpl_list

# Print summary results to log file
def summaryLog():
    # Get total devices
    total_devices = len(listDict)

    # Create log file for scan results summary
    now = get_now_time()
    summary_name = "Results_Summary_" + now + ".log"
    summary_log = os.path.join(log_dir, summary_name)

    # Write the scan results to a text file
    print_log("Report: Scan Results Summary\n", summary_log)
    print_log("User: {0}\n".format(myuser), summary_log)
    print_log("Captured: {0}\n".format(now), summary_log)
    print_log("=" * 50 + "\n", summary_log)
    print_log("Total Devices: {0}\n".format(total_devices), summary_log)
    print_log("=" * 50 + "\n", summary_log)

    # ********** CONNECTION ERRORS ***************
    print_log("[Connection Errors]\n", summary_log)
    # Unable to Ping
    print_log("\tUnable to Ping: {0}\n".format(len(no_ping_ips)), summary_log)
    if len(no_ping_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in no_ping_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    # No NETCONF configured
    print_log("\tNo NETCONF configured: {0}\n".format(len(no_netconf_ips)), summary_log)
    if len(no_netconf_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in no_netconf_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    # Bad authentication credentials
    print_log("\tAuth credentials failed: {0}\n".format(len(no_auth_ips)), summary_log)
    if len(no_auth_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in no_auth_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    # Generic Connection Issue
    print_log("\tUnknown connection issue: {0}\n".format(len(no_connect_ips)), summary_log)
    if len(no_connect_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in no_connect_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("=" * 50 + "\n", summary_log)

    # PARAMETER CONTENT
    print_log("[Parameters]\n", summary_log)
    print_log("\tChanged Parameters: {0}\n".format(len(param_change_ips)), summary_log)
    if len(param_change_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in param_change_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("\tError Accessing Parameters: {0}\n".format(len(param_attrib_error_ips)), summary_log)
    if len(param_attrib_error_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in param_attrib_error_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("=" * 50 + "\n", summary_log)

    # CONFIG COMPARE CONTENT
    print_log("[Configuration Compare]\n", summary_log)
    print_log("\tChanged Configurations: {0}\n".format(len(config_change_ips)), summary_log)
    if len(config_change_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in config_change_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("\tSave Configuration Errors: {0}\n".format(len(config_save_error_ips)), summary_log)
    if len(config_save_error_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in config_save_error_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("\tUpdate Configuration Errors: {0}\n".format(len(config_update_error_ips)), summary_log)
    if len(config_update_error_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in config_update_error_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("=" * 50 + "\n", summary_log)

    # TEMPLATE DEVIATION CONTENT
    if addl_opt == "template" or addl_opt == "all":
        print_log("[Template Deviation]\n", summary_log)
        print_log("\tTemplate Deviation: {0}\n".format(len(templ_change_ips)), summary_log)
        if len(templ_change_ips) == 0:
            print_log("\t\t* No Devices *\n", summary_log)
        else:
            for ip in templ_change_ips:
                print_log("\t\t-> " + ip + "\n", summary_log)
        print_log("=" * 50 + "\n", summary_log)
        print_log("\tTemplate Errors: {0}\n".format(len(templ_error_ips)), summary_log)
        if len(templ_error_ips) == 0:
            print_log("\t\t* No Devices *\n", summary_log)
        else:
            for ip in templ_error_ips:
                print_log("\t\t-> " + ip + "\n", summary_log)
        print_log("=" * 50 + "\n", summary_log)

    # Unchanged Devices
    print_log("\tUnchanged Devices: {0}\n".format(len(no_changes_ips)), summary_log)
    if len(no_changes_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in no_changes_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("=" * 50 + "\n", summary_log)

def scan_results():
    total_devices = len(listDict)
    # Print brief results to screen
    print"Devices with..."
    print"------------------------------"
    print"Parameters Changed.........{0}".format(len(param_change_ips))
    print"Configs Changed............{0}".format(len(config_change_ips))
    if addl_opt == "template" or addl_opt == "all":
        print"Template Mismatches........{0}".format(len(templ_change_ips))
    print"=============================="
    print"Total Number of Devices....{0}".format(total_devices)
    print"==============================\n"

# Simple function for adjusting tabs
def iptab(ip):
    if len(ip) < 14:
        mytab = "\t\t"
    else:
        mytab = "\t"

    return mytab

# Function for adding new devices to the database
def add_new_devices_loop(iplistfile):
    print "Report: Add New Devices"
    print "User: {0}".format(myuser)
    print "Captured: {0}\n".format(get_now_time())

    print "Add New Devices:"
    # Loop over the list of new IPs
    for raw_ip in line_list(os.path.join(iplist_dir, iplistfile)):
        # Attempt to add new device
        add_new_device(raw_ip.strip())

# Function to add specific device
def add_new_device(ip):
    print "\t-  Trying to add {0}...".format(ip)
    # If a record doesn't exist, try to create one
    if not get_record(ip):
        # Try adding this device to the database
        if add_record(ip):
            print "\t\t* Successfully added device to database."
            add_to_csv_sort(
                ip + ";" + "Successfully added (" + ip + ") to database." + ";" + get_now_time(),
                new_devices_log)
        else:
            print "\t\t* Failed adding device to database *"
            add_to_csv_sort(
                ip + ";" + "Failed adding (" + ip + ") to database." + ";" + get_now_time(),
                new_devices_log)
    else:
        print "\t\t* Skipping device, already in database."


def template_check(record, temp_dev_log):
    # Check if template option was specified
    # Template Results: 0 = Error, 1 = No Deviations, 2 = Deviations
    # Delete existing template file(s)
    remove_template_file(record)

    # Run template check
    templ_results = template_scanner(template_regex(), record)

    print_log("Report: Template Deviation Check\n", temp_dev_log)
    print_log("Device: {0} ({1})\n".format(record['hostname'], record['ip']), temp_dev_log)
    print_log("User: {0}\n".format(myuser), temp_dev_log)
    print_log("Checked: {0}\n".format(get_now_time()), temp_dev_log)

    print_log("\nMissing Configuration:", temp_dev_log)
    if templ_results[-1] == 2:
        for result in templ_results[:-1]:
            print_log("\t> {0}\n".format(result), temp_dev_log)
        templ_change_ips.append(record['hostname'] + " (" + record['ip'] + ")")
    elif templ_results[-1] == 1:
        print_log("\t* Template Matches *\n", temp_dev_log)
    else:
        print_log("\t* {0} *\n".format(templ_results[0]), temp_dev_log)
        add_to_csv_sort(record['ip'] + ";" + templ_results[0] + ";" + get_now_time() + "\n", ops_error_log)
        templ_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")

# Parameter and Cconfiguration Check Function
def param_config_check(record, conf_chg_log):
    # A single running log of changes
    run_change_log = os.path.join(log_dir, "Run_Change_Log.csv")

    # Functions for checking parameters and configurations
    param_results = check_params(str(record['ip']))
    compare_results = config_compare(record)

    # Param Results: 0 = Error, 1 = No Changes, 2 = Changes
    # Compare Results: 0 = Saving Error, 1 = No Changes, 2 = Changes Detected 3 = Update Error
    # Scan param results
    if param_results[-1] == 1 and compare_results[-1] == 1:  # If no changes are detected
        no_changes_ips.append(record['hostname'] + " (" + record['ip'] + ")")
    elif param_results[-1] == 2 or compare_results[-1] == 2:  # If changes are detected
        print_sl("Report: Parameter and Config Check\n", conf_chg_log)
        print_sl("Device: {0} ({1})\n".format(record['hostname'], record['ip']), conf_chg_log)
        print_sl("User: {0}\n".format(myuser), conf_chg_log)
        print_sl("Checked: {0}\n".format(get_now_time()), conf_chg_log)
        # The "run_change_log" format is "IP,HOSTNAME,DATE"
        add_to_csv_sort(record['ip'] + ";" + record['hostname'] + ";" + get_now_time(), run_change_log)

    # If param results detect changes
    if param_results[-1] == 2:
        print_sl("Parameter Check:\n", conf_chg_log)
        for result in param_results[:-1]:
            print_sl("\t> {0}\n".format(result), conf_chg_log)
        print_sl("\n", conf_chg_log)
        param_change_ips.append(record['hostname'] + " (" + record['ip'] + ")")

    # If param results are errors
    elif param_results[-1] == 0:
        add_to_csv_sort(record['ip'] + ";" + param_results[0] + ";" + get_now_time() + "\n", ops_error_log)
        param_attrib_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")
    # If compare results detect differences
    if compare_results[-1] == 2:
        print_sl("Config Check:\n", conf_chg_log)
        for result in compare_results[:-1]:
            print_sl("\t> {0}".format(result), conf_chg_log)
        print_sl("\n", conf_chg_log)
        config_change_ips.append(record['hostname'] + " (" + record['ip'] + ")")
    # If compare results are save errors
    elif compare_results[-1] == 0:
        add_to_csv_sort(record['ip'] + ";" + compare_results[0] + ";" + get_now_time() + "\n", ops_error_log)
        config_save_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")
    # If compare results are update errors
    elif compare_results[-1] == 3:
        add_to_csv_sort(record['ip'] + ";" + compare_results[0] + ";" + get_now_time() + "\n", ops_error_log)
        config_update_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")


# Function that checks if were using a subset or not
def check_loop(subsetlist):
    # Check if subset option is defined
    if subsetlist:
        temp_list = []
        for ip_addr in line_list(os.path.join(iplist_dir, subsetlist)):
            temp_list.append(ip_addr.strip())
        #for record in listDict:
        #    if record['ip'] in temp_list:
        #        check_main(record, access_error_log)
        # Loop through IPs in the provided list
        for ip in temp_list:
            # Checks if the specified IP is NOT defined in the list of dictionaries. Add it as a new device.
            if not any(ipaddr.get('ip', None) == ip for ipaddr in listDict):
                print "\n" + "-" * 80
                print subHeading(ip, 15)
                add_new_device(ip)
            # If the IP IS present, execute this...
            else:
                check_main(get_record(ip))
    # Check the entire database
    else:
        for record in listDict:
            check_main(record)
    # End of processing
    print "\n" + "=" * 80
    print "Device Processsing Ended: {0}\n\n".format(get_now_time())


# Function checking devices that are in the database
def check_main(record):
    # Performs the selected checks (Parameter/Config, Template, or All)
    directory_check(record)
    device_dir = os.path.join(config_dir, getSiteCode(record), record['hostname'])

    # Create logs for capturing info
    now = get_now_time()
    if addl_opt == "configs" or addl_opt == "all":
        conf_chg_name = "Config_Change_" + now + ".log"
        conf_chg_log = os.path.join(device_dir, conf_chg_name)

    if addl_opt == "template" or addl_opt == "all":
        temp_dev_name = "Template_Deviation_" + now + ".log"
        temp_dev_log = os.path.join(device_dir, temp_dev_name)

    print "\n" + "-" * 80
    print subHeading(record['hostname'] + " - (" + record['ip'] + ")", 15)
    # Try to connect to device
    record.update({'last_access': get_now_time()})
    if addl_opt == "configs" or addl_opt == "all":
        print "Running Param/Config Check..."
        param_config_check(record, conf_chg_log)
    if addl_opt == "template" or addl_opt == "all":
        print "Running Template Check..."
        template_check(record, temp_dev_log)

def main(argv):
    """ Purpose: Capture command line arguments and populate variables.
        Arguments:
            -c    -  (Required) The CSV file containing credentials to be used to access devices.
            -s    -  (Optional) The TEXT file that contains a list of device IPs to scan.
            -o    -  (Optional) Run one of the following options.
                        - "configs" will run the Param and Config Check Function
                        - "template" will run the Template Scan Function of existing devices
                        - "all" will run both of the above functions
            -i    -  (Optional) A TEXT file containing a list of ip addresses to add to the database.

    """
    global credsCSV
    global iplistfile
    global addl_opt
    global subsetlist
    try:
        opts, args = getopt.getopt(argv, "hc:i:o:s:",["creds=","iplist=","funct=","subset="])
    except getopt.GetoptError:
        print "device_refresh -c <credsfile> -s <subsetlist> -i <iplistfile> -o <functions>"
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'SYNTAX: device_refresh -c <credsfile> -s <subsetlist> -i <iplistfile> -o <functions>'
            print '  -c : (REQUIRED) A CSV file in the root of the jmanage folder. It contains the username or hashid and password.'
            print '  -s : (OPTIONAL) A TXT file in the "iplists" directory that contains a list of IP addresses to scan.'
            print '  -i : (OPTIONAL) A TXT file in the "iplists" directory that contains a list of IPs to add to the directory.'
            print '  -o : (OPTIONAL) Allows various options, provide one of the following three arguments:'
            print '      - "configs"  : Performs the parameter and configuration checks.'
            print '      - "template" : Performs the template scan.'
            print '      - "all"      : Performs all the above checks.'
            sys.exit()
        elif opt in ("-c", "--creds"):
            credsCSV = arg
        elif opt in ("-s", "--subset"):
            subsetlist = arg
        elif opt in ("-i", "--iplist"):
            iplistfile = arg
        elif opt in ("-o", "--funct"):
            addl_opt = arg
    print "Credentials file is: {0}".format(credsCSV)
    print "IP List file is: {0}".format(iplistfile)
    print "Function Choice is: {0}".format(addl_opt)
    print "Subset List File is: {0}".format(subsetlist)

# Main execution loop
if __name__ == "__main__":
    detect_env()
    main(sys.argv[1:])
    myfile = os.path.join(dir_path, credsCSV)
    creds = csv_to_dict(myfile)
    myuser = creds['username']
    mypwd = creds['password']

    # Load records from existing CSV
    #print "Loading records..."
    listDict = csv_to_listdict(listDictCSV)

    # Add New Device function if IPs have been supplied
    print topHeading("JMANAGE SCRIPT", 15)
    print subHeading("ADD DEVICES FUNCTION", 15)
    if iplistfile:
        print " >> Running add_new_devices..."
        add_new_devices_loop(iplistfile)
        print " >> Completed add_new_devices"
    else:
        print "\n >> No devices to add.\n"

    # Check Params/Config/Template Function if records exist
    if addl_opt:
        print " >> Running check_main..."
        print subHeading("CHECK FUNCTIONS", 15)
        # Run the check main process
        check_loop(subsetlist)
        print " >> Completed check_main"

        # Print the scan results (troubleshooting)
        print " >> Running scan_results..."
        print subHeading("SCAN RESULTS", 5)
        scan_results()
        print " >> Completed scan_results"

        # Create the summary log
        print " >> Running summary_log..."
        summaryLog()
        print " >> Completed summary_log"
    else:
        print "\n >> No Checks Selected.\n"

    # Save the changes of the listDict to CSV
    if listDict:
        # Order to print the CSV in
        attribOrder = ['hostname', 'ip', 'version', 'model', 'serialnumber', 'last_access',
                      'last_param_check', 'last_config_check', 'last_temp_check', 'last_param_change',
                      'last_config_change']
        # Print the list dictionary to a CSV file
        listdict_to_csv(listDict, listDictCSV, attribOrder)
        print "\nSaved any changes. We're done!"
    else:
        print "\nNo content in database. Exiting!"
