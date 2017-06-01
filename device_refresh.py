__copyright__ = "Copyright 2017 Tyler Jordan"
__version__ = "0.2.0"
__email__ = "tjordan@juniper.net"

# ------------------------------------------------------------------------------------------------------------------- #
# Main Database Attributes:
# ip ................. Management IP Address (address to connect to device)
# inet_intf .......... List of dictionaries containing
#   - interface ...... Logical Interface
#   - ipaddr ......... IP address of this interface
#   - ipmask ......... IP mask
#   - status ......... Operational Status
#   - updated ........ Timestamp of last update
# hostname ........... Hostname of Device
# version ............ Juniper Code Version (ie 13.2X51-D35.3)
# serialnumber ....... Serial Number of Chassis
# model .............. Juniper Model Number (ie. EX4300-48P)
# last_access......... Last time device was accessed by script
# last_config_check .. Last time device config was checked by script
# last_config_change . Last time device config was changed by script
# last_param_check ... Last time device parameters were checked by script
# last_param_change .. Last time device parameter was changed by script
# last_temp_check .... Last time device template was checked by script
#
# Interface Database Attributes:
# hostname............ Hostname of device
# interface........... Interface of device
# ip.................. IP on this interface
# status.............. Operational state (up/down)
# updated............. Timestamp when this information was gathered

# Logs:
# Access_Error_Log.csv - Timestamped error messages returned from attempting to connect to devices
# Ops_Error_Log.csv ---- Timestamped error messages returned from running param, config, or template funtions
# New_Devices_Log.csv -- Timestamped list of devices that have been added

# Dict Lists
# Fail_Devices.csv ----- Timestamped list of devices that are not accessible
#
# ------------------------------------------------------------------------------------------------------------------- #
# Imports:
import getopt
import platform
import re
import jxmlease

from operator import itemgetter
from lxml import etree
from prettytable import PrettyTable

from jnpr.junos import *
from jnpr.junos.exception import *
from netaddr import *
from utility import *

# Paths
iplist_dir = ''
config_dir = ''
log_dir = ''
template_dir = ''
dir_path = ''

# Files
main_list_dict = ''
intf_list_dict = ''
credsCSV = ''
template_file = ''
template_csv = ''
iplistfile = ''
access_error_log = ''
access_error_list = []
ops_error_log = ''
ops_error_list = []
new_devices_log = ''
new_devices_list = []
run_change_log = ''
run_change_list = []
fail_devices_csv = ''

# Log Keys
error_key_list = ['ip', 'message', 'error', 'timestamp'] # access_error_log, ops_error_log
standard_key_list = ['ip', 'message', 'timestamp'] # new_devices_log

# Params
listDict = []
mypwd = ''
myuser = ''
port = 22
num_of_configs = 5
addl_opt = ''
detail_ip = ''
subsetlist = ''

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

# Key Lists
dbase_order = [ 'hostname', 'ip', 'version', 'model', 'serialnumber', 'last_access', 'last_config_check',
                'last_config_change', 'last_param_check', 'last_param_change', 'last_temp_check']
facts_list = [ 'hostname', 'serialnumber', 'model', 'version' ]


def detect_env():
    """ Purpose: Detect OS and create appropriate path variables. """
    global credsCSV
    global iplist_dir
    global config_dir
    global template_dir
    global log_dir
    global dir_path
    global template_file
    global template_csv
    global access_error_log
    global ops_error_log
    global new_devices_log
    global run_change_log
    global fail_devices_csv

    global main_list_dict
    global intf_list_dict
    global facts_list


    dir_path = os.path.dirname(os.path.abspath(__file__))
    if platform.system().lower() == "windows":
        #print "Environment Windows!"
        iplist_dir = os.path.join(dir_path, "data\\iplists")
        config_dir = os.path.join(dir_path, "data\\configs")
        template_dir = os.path.join(dir_path, "data\\templates")
        log_dir = os.path.join(dir_path, "data\\logs")

    else:
        #print "Environment Linux/MAC!"
        iplist_dir = os.path.join(dir_path, "data/iplists")
        config_dir = os.path.join(dir_path, "data/configs")
        template_dir = os.path.join(dir_path, "data/templates")
        log_dir = os.path.join(dir_path, "data/logs")

    # Statically defined files and logs
    main_list_dict = os.path.join(dir_path, "main_db.json")
    intf_list_dict = os.path.join(dir_path, "intf_db.csv")
    template_csv = os.path.join(dir_path, template_dir, "Template_Regex.csv")
    template_file = os.path.join(dir_path, template_dir, "Template.conf")
    access_error_log = os.path.join(log_dir, "Access_Error_Log.csv")
    ops_error_log = os.path.join(log_dir, "Ops_Error_Log.csv")
    new_devices_log = os.path.join(log_dir, "New_Devices_Log.csv")
    run_change_log = os.path.join(log_dir, "Run_Change_Log.csv")
    fail_devices_csv = os.path.join(log_dir, "Fail_Devices.csv")

# -----------------------------------------------------------------
# FILE OPERATIONS
# -----------------------------------------------------------------
def load_config_file(ip, newest):
    """ Purpose: Load the selected device's configuration file into a variable.
    
        :param ip           -   Management IP address of the device
        :param newest:      -   True/False (True means newest, false means oldest file)
        :return:            -   A string containing the configuration   
    """
    record = get_record(listDict, ip=ip)
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
        print "Problem getting record information..."

def get_old_new_file(record, newest):
    """ Purpose: Returns the oldest or newest config file from specified IP

        :param record:      -   The dictionary information of the device.
        :param newest:      -   True/False (True means newest, false means oldest file)
        :return:            -   A string containing the file with complete path. False   
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
    """ Purpose: Remove the template of the corresponding device.

        :param record:      -   The dictionary information of the device.
        :return:            -   True/False
    """
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
    """ Purpose: Returns the number of configuration files for the defined device.

        :param record:      -   Parameter for the "get_old_new_file" function
        :return:            -   List containing file contents
    """
    file_num = 0
    if record:
        my_dir = os.path.join(config_dir, getSiteCode(record), record['hostname'])
        for file in listdir(my_dir):
            if file.startswith(record['hostname']):
                file_num += 1
    return file_num

def load_config_file_list(ip, newest):
    """ Purpose: Load the selected device's configuration file into a list.
    
        :param ip:          -   Dictionary record of the device.
        :param newest:      -   Parameter for the "get_old_new_file" function
        :return:            -   List containing file contents
    """
    record = get_record(listDict, ip=ip)
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

        :param record:      -   Dictionary record of the device.
        :return:            -   True/False
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

def save_config_file(myconfig, record):
    """ Purpose: Creates a config file and adds text to the file.
 
        :param myconfig:    -   Text version of the current configuration. ("set" style)
        :param record:      -   Dictionary record of the device.
        :return:            -   True/False
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
        message = "Unable to open file: " + fileandpath + "."
        contentList = [record['ip'], message, str(err), get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        return False
    else:
        # Remove excess configurations if necessary
        if get_file_number(record) > 5:
            del_file = get_old_new_file(record, newest=False)
            try:
                os.remove(del_file)
            except Exception as err:
                message = "Unable to remove config file: " + del_file + "."
                contentList = [record['ip'], message, str(err), get_now_time()]
                ops_error_list.append(dict(zip(error_key_list, contentList)))
                #print "ERROR: Unable to remove old file: {0} | File: {1}".format(err, del_file)
        try:
            # Write the new configuration to the new file
            newfile.write(myconfig)
        except Exception as err:
            #print "ERROR: Unable to write config to file: {0}".format(err)
            message = "Unable to write config to file: " + fileandpath + "."
            contentList = [ record['ip'], message, str(err), get_now_time() ]
            ops_error_list.append(dict(zip(error_key_list, contentList)))
            return False
        else:
            # Update configuration change time for record
            record.update({'last_config_change': get_now_time()})
            newfile.close()
            return True

def line_list(filepath):
    """ Purpose: Create a list of lines from the file defined.
 
        :param filepath:    -   String of the IP of the device
        :param dev:         -   The PyEZ SSH netconf connection to the device.
        :return linelist:   -   A list of Strings from the file.
    """
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

def getSiteCode(record):
    """ Purpose: Get the site code from the Hostname. Use "MISC" if it doesn't match the two regular expressions.

    :param record:      -   Dictionary of the parameters of the device in question
    :return:            -   String of the timestamp in "YYYY-MM-DD_HHMM" format
    """
    hostname = record['hostname'].upper()
    if re.match(r'SW[A-Z]{3}', hostname):
        siteObj = re.match(r'SW[A-Z]{3}', hostname)
    elif re.match(r'S[A-Z]{3}', hostname):
        siteObj = re.match(r'S[A-Z]{3}', hostname)
    else:
        mydirect = "MISC"
        return mydirect

    return siteObj.group()[-3:]

# -----------------------------------------------------------------
# CONNECTIONS
# -----------------------------------------------------------------
def connect(ip, indbase=False):
    """ Purpose: Attempt to connect to the device

    :param ip:          -   IP of the device
    :param indbase:     -   Boolean if this device is in the database or not, defaults to False if not specified
    :return dev:        -   Returns the device handle if its successfully opened.
    """
    dev = Device(host=ip, user=myuser, passwd=mypwd, auto_probe=True)
    # Try to open a connection to the device
    try:
        dev.open()
    # If there is an error when opening the connection, display error and exit upgrade process
    except ConnectRefusedError as err:
        message = "Host Reachable, but NETCONF not configured."
        stdout.write("-> " + message + " | ")
        if indbase:
            contentList = [ip, message, str(err), get_now_time()]
            access_error_list.append(dict(zip(error_key_list, contentList)))
        else:
            contentList = [ip, message, get_now_time()]
            new_devices_list.append(dict(zip(standard_key_list, contentList)))
        no_netconf_ips.append(ip)
        return False
    except ConnectAuthError as err:
        message = "Unable to connect with credentials. User:" + myuser
        stdout.write("-> " + message + " | ")
        if indbase:
            contentList = [ip, message, str(err), get_now_time()]
            access_error_list.append(dict(zip(error_key_list, contentList)))
        else:
            contentList = [ip, message, get_now_time()]
            new_devices_list.append(dict(zip(standard_key_list, contentList)))
        no_auth_ips.append(ip)
        return False
    except ConnectTimeoutError as err:
        message = "Timeout error, possible IP reachability issues."
        stdout.write("-> " + message + " | ")
        contentList = [ ip, message, str(err), get_now_time() ]
        fail_check(ip, indbase, contentList)
        no_ping_ips.append(ip)
        return False
    except ProbeError as err:
        message = "Probe timeout, possible IP reachability issues."
        stdout.write("-> " + message + " | ")
        contentList = [ ip, message, str(err), get_now_time() ]
        fail_check(ip, indbase, contentList)
        no_ping_ips.append(ip)
        return False
    except ConnectError as err:
        message = "Unknown connection issue."
        stdout.write("-> " + message + " | ")
        contentList = [ ip, message, str(err), get_now_time() ]
        fail_check(ip, indbase, contentList)
        no_connect_ips.append(ip)
        return False
    except Exception as err:
        message = "Undefined exception."
        stdout.write("-> " + message + " | ")
        contentList = [ip, message, str(err), get_now_time()]
        fail_check(ip, indbase, contentList)
        no_connect_ips.append(ip)
        return False
    # If try arguments succeed...
    else:
        return dev

# -----------------------------------------------------------------
# LOGGING | SHOWS
# -----------------------------------------------------------------
def fail_check(ip, indbase, contentList):
    """ Purpose: Performs additional operations and logging on devices if they are not accessible.

    :param ip:          -   The IP address of the device in question
    :param indbase:     -   Boolean on if the device is in the database or not.
    :param contentList: -   Content for the log entry.
    :return:            -   None
    """
    # Number of days to keep IP after first fail attempt
    attempt_limit = 10
    matched = False

    if indbase:
        myListDict = csv_to_listdict(fail_devices_csv)
        myDelimiter = ","
        # Go through failed devices log, find a specific ip
        if myListDict:
            for myDict in myListDict:
                # If we find the IP in this list
                if myDict['ip'] == ip:
                    matched = True
                    myDict.update({'last_attempt': get_now_time()})
                    past_time = datetime.datetime.strptime(myDict['date_added'], "%Y-%m-%d_%H%M")
                    now_time = datetime.datetime.now()
                    days_exp = (now_time - past_time).days
                    print "Consecutive Failed Days: {0}".format(days_exp)
                    if days_exp > attempt_limit:
                        myListDict.remove(myDict)
                        listdict_to_csv(myListDict, fail_devices_csv, myDelimiter)
                        #print "ListDict: {0}".format(listDict)
                        #print "MyDict: {0}".format(myDict)
                        remove_record('ip', ip)
                    break
        # If this device is not in the failed list or failed devices log doesn't exist
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
            listdict_to_csv(mylist, fail_devices_csv, myDelimiter, attribOrder)
        # This applies to devices that are in the database already. Add to access error log.
        access_error_list.append(dict(zip(error_key_list, contentList)))
    else:
        # This applies to new devices that had a connection issue. Add to new devices log.
        del contentList[2]
        new_devices_list.append(dict(zip(standard_key_list, contentList)))

def summaryLog():
    """ Purpose: Creates the log entries and output for the results summary.

    :param: None
    :return: None
    """
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
    """ Purpose: Prints a short summary of the check results to the screen.

    :param: None
    :return: None
    """
    # Print brief results to screen
    print"Devices with..."
    print"------------------------------"
    print"Parameters Changed.........{0}".format(len(param_change_ips))
    print"Configs Changed............{0}".format(len(config_change_ips))
    if addl_opt == "template" or addl_opt == "all":
        print"Template Mismatches........{0}".format(len(templ_change_ips))
    print"=============================="

def sort_and_save():
    """ Purpose: Saves main database and sorts and saves the logs.

    :param: None
    :return: None
    """
    delimiter = ";"
    # Main Database
    if listDict:
        # csv_write_sort(listDict, main_list_dict, sort_column=0, column_names=dbase_order)
        stdout.write("Save -> Main Database (" + main_list_dict + "): ")
        if write_to_json(listDict, main_list_dict):
            print "Successful!"
        else:
            print "Failed!"
    # Access Error Log
    if access_error_list:
        stdout.write("Save -> Access Error Log (" + access_error_log + "): ")
        if csv_write_sort(access_error_list, access_error_log, sort_column=3, reverse_sort=True,
                          column_names=error_key_list, my_delimiter=delimiter):
            print "Successful!"
        else:
            print "Failed!"
    else:
        print "No changes to Access Error Log"
    # Operations Error Log
    if ops_error_list:
        stdout.write("Save -> Ops Error Log (" + ops_error_log + "): ")
        if csv_write_sort(ops_error_list, ops_error_log, sort_column=3, reverse_sort=True,
                          column_names=error_key_list, my_delimiter=delimiter):
            print "Successful!"
        else:
            print "Failed!"
    else:
        print "No changes to Ops Error Log"
    # New Devices Log
    if new_devices_list:
        stdout.write("Save -> New Devices Log (" + new_devices_log + "): ")
        if csv_write_sort(new_devices_list, new_devices_log, sort_column=2, reverse_sort=True,
                          column_names=standard_key_list, my_delimiter=delimiter):
            print "Successful!"
        else:
            print "Failed!"
    else:
        print "No changes to New Devices Log"
    # Running Changes Log
    if run_change_list:
        stdout.write("Save -> Run Change Log (" + run_change_log + "): ")
        if csv_write_sort(run_change_list, run_change_log, sort_column=2, reverse_sort=True,
                          column_names=standard_key_list, my_delimiter=delimiter):
            print "Successful!"
        else:
            print "Failed!"
    else:
        print "No changes to Run Change Log"

# -----------------------------------------------------------------
# PARAMETER STUFF
# -----------------------------------------------------------------
def check_params(ip, dev):
    """ Purpose: Chacks the parameters to see if they have changed. If param is changed, it is updated and logged, if 
    not, the "last_param" timestamp is only updated.

        :param ip:          -   String of the IP of the device
        :param dev:         -   The PyEZ SSH netconf connection to the device.
        :return results:    -   A list that contains the results of the check, including the following parameter.
                            (0 = Unable to Check, 1 = No Changes, 2 = Changes Detected)
    """
    returncode = 1
    # Store the results of check and returncode
    results = []
    remoteDict = {}
    # Try to collect current chassis info
    for key in facts_list:
        remoteDict[key] = dev.facts[key]

    # If info was collected...
    if remoteDict:
        # Get current information to compare against database info
        localDict = get_record(listDict, ip)
        if localDict:
            # Update database date for parameter check
            localDict.update({'last_param_check': get_now_time()})
            # Check that the existing record is up-to-date. If not, update.
            print "\t- Check parameters:"

            for item in facts_list:
                stdout.write("\t\t- Check " + item + "...")
                if not localDict[item].upper() == remoteDict[item].upper():
                    results.append(item.upper() + " changed from " + localDict[item] + " to " + remoteDict[item])
                    change_record(ip, remoteDict[item].upper(), key=item)
                    returncode = 2
                    print "Changed!"
                else:
                    print "Unchanged"
            # Check inet interfaces, if they have changed, update them
            stdout.write("\t- Check Inet Interfaces...")
            list1 = get_inet_interfaces(ip, dev)
            list2 = localDict['inet_intf']
            # Remove updated keys, these will always be different
            modlist1 = [{k: v for k, v in d.iteritems() if k != 'updated'} for d in list1]
            modlist2 = [{k: v for k, v in d.iteritems() if k != 'updated'} for d in list2]
            #print "List 1: {0}".format(list1)
            #print "List 2: {0}".format(list2)
            # Use zip to combine two lists to find differences
            pairs = zip(modlist1, modlist2)
            if any (x != y for x, y in pairs):
                #print "Change True"
                change_record(ip, list1, key='inet_intf')
                results.append("Inet interfaces have changed")
                returncode = 2
                print "Changed!"
            else:
                print "Unchanged"
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

def get_inet_interfaces(ip, dev):
    """
        Purpose: Collect a list dictionary of inet interfaces containing IPv4 addresses (irb,vlan,lo0,ae,ge,me0)
    :param dev: Reference for the connection to a device.
    :return: List Dictionary 
    """
    # Physical Interface Regex
    phys_regex = r'^irb$|^vlan$|^lo0$|^ae\d{1,3}$|^ge-\d{1,3}/\d{1,3}/\d{1,3}$|^me0$'
    # Logical Interface Regex
    logi_regex = r'^irb\.\d{1,3}$|^vlan\.\d{1,3}$|^lo0\.\d{1,3}$|^ae\d{1,3}\.\d{1,4}$|^ge-\d{1,3}/\d{1,3}/\d{1,3}\.\d{1,4}$|^me0\.0$'

    # Get the "interface" information from the device
    try:
        rsp = dev.rpc.get_interface_information(terse=True, normalize=True)
    except Exception as err:
        message = "Error collecting interface information via RPC. "
        #print message + "ERROR: {0}".format(err)
        contentList = [ip, message, str(err), get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        blank_list = []
        return blank_list
    else:
        root = jxmlease.parse(etree.tostring(rsp))

        # Display the raw data
        #print root
        intf_list = []

        #print "IP Interfaces..."
        if 'physical-interface' in root['interface-information']:
            for intf in root['interface-information']['physical-interface']:
                #print intf['name']
                # Interface Dictionary
                intf_dict = {'interface': '', 'ipaddr': '', 'ipmask': '', 'status': '', 'updated': ''}
                # Check if the interface has a logical interface and matches one of the types in the regex
                if 'logical-interface' in intf and re.match(phys_regex, intf['name']):
                    #print "Has logical interface and matches regex..."
                    if isinstance(intf['logical-interface'], dict):
                        if re.match(logi_regex, intf['logical-interface']['name']):
                            if intf['logical-interface']['address-family']['address-family-name'] == 'inet' and 'interface-address' in intf['logical-interface']['address-family']:
                                if isinstance(intf['logical-interface']['address-family']['interface-address'], dict):
                                    # Assign variables to dictionary
                                    ip_and_mask = get_ip_mask(intf['logical-interface']['address-family']['interface-address']['ifa-local'])
                                    intf_dict['interface'] = intf['logical-interface']['name'].encode('utf-8')
                                    intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                    intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                    intf_dict['status'] = intf['logical-interface']['oper-status'].encode('utf-8')
                                    intf_dict['updated'] = get_now_time()
                                    # Append dictionary to list
                                    intf_list.append(intf_dict.copy())

                                else:
                                    for mylist in intf['logical-interface']['address-family']['interface-address']:
                                        ip_and_mask = get_ip_mask(intf['ifa-local'])
                                        intf_dict['interface'] = intf['logical-interface']['name'].encode('utf-8')
                                        intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                        intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                        intf_dict['status'] = intf['logical-interface']['oper-status'].encode('utf-8')
                                        intf_dict['updated'] = get_now_time()
                                        # Append dictionary to list
                                        intf_list.append(intf_dict.copy())

                    else:
                        for mylist in intf['logical-interface']:
                            if re.match(logi_regex, mylist['name']):
                                if mylist['address-family']['address-family-name'] == 'inet' and 'interface-address' in mylist['address-family']:
                                    if isinstance(mylist['address-family']['interface-address'], dict):
                                        ip_and_mask = get_ip_mask(mylist['address-family']['interface-address']['ifa-local'])
                                        #print "IP and Mask {0}".format(mylist['address-family']['interface-address']['ifa-local'])
                                        intf_dict['interface'] = mylist['name'].encode('utf-8')
                                        intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                        intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                        intf_dict['status'] =  mylist['oper-status'].encode('utf-8')
                                        intf_dict['updated'] = get_now_time()
                                        # Append dictionary to list
                                        intf_list.append(intf_dict.copy())

                                    else:
                                        for mynewlist in mylist['address-family']['interface-address']:
                                            ip_and_mask = get_ip_mask(mynewlist['ifa-local'])
                                            intf_dict['interface'] = mylist['name'].encode('utf-8')
                                            intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                            intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                            intf_dict['status'] = mylist['oper-status'].encode('utf-8')
                                            intf_dict['updated'] = get_now_time()
                                            # Append dictionary to list
                                            intf_list.append(intf_dict.copy())
        else:
            message = "Error collecting interface information."
            err = "KeyError: run show interfaces on device."
            contentList = [ip, message, err, get_now_time()]
            ops_error_list.append(dict(zip(error_key_list, contentList)))
            blank_list = []
            return blank_list

        # Sort criteria
        sort_list = ['me0.0', 'lo0.119', 'lo0.0', 'irb.119', 'irb.0', 'vlan.119', 'vlan.0']

        # Sort and provide list dictionary
        return list_dict_custom_sort(intf_list, "interface", sort_list)

#-----------------------------------------------------------------
# CONFIG STUFF
#-----------------------------------------------------------------
def config_compare(record, dev):
    """ Purpose: To compare two configs and get the differences, log them

    :param record:          -   A dictionary that contains device attributes
    :param dev:             -   Connection handle to device.
    :return:                -   A results list of changes
    """
    results = []
    # 0 = Save Failed, 1 = No Changes, 2 = Changes Detected, 3 = Update Failed
    returncode = 1

    # Check if the appropriate site directory is created. If not, then create it.
    loaded_config = load_config_file(record['ip'], newest=True)
    if not loaded_config:
        if save_config_file(fetch_config(dev), record):
            results.append("No Existing Config, Configuration Saved\n")
        else:
            results.append("No Existing Config, Configuration Save Failed\n")
            returncode = 0
    else:
        current_config = fetch_config(dev)
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
                    save_config_file(current_config, record)
                if not save_config_file(current_config, record):
                    returncode = 3
        else:
            results.append("Unable to retrieve configuration\n")
            returncode = 0
    results.append(returncode)
    return results

def fetch_config(dev):
    """ Purpose: Creates the log entries and output for the results summary.

    :param dev:         -   The device handle for gather info from device
    :return:            -   Returns a ASCII set version of the configuration
    """
    try:
        myconfig = dev.cli('show config | display set', warning=False)
    except Exception as err:
        print "Error getting configuration from device. ERROR: {0}".format(err)
        return False
    else:
        return myconfig

#-----------------------------------------------------------------
# TEMPLATE STUFF
#-----------------------------------------------------------------
def template_check(record, temp_dev_log):
    """ Purpose: Runs the template function and creates log entries.

    :param record: A dictionary containing the device information from main_db
    :param temp_dev_log: Filename/path for the template log.
    :return: None
    """
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
        message = "Issue in template scanner function."
        contentList = [ip, message, templ_results[0], get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        templ_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")

def template_scanner(regtmpl_list, record):
    """ Purpose: Compares a regex list against a config list.

    :param regtmpl_list:    -   List of template set commands with regex
    :param record:          -   A dictionary containing device attributes
    :return results:        -   A list containing results of scan.
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
    """ Purpose: Creates the template regex using the template file and regex mapping document.

    :param: None
    :return regtmpl_list: A list containing regexs for template scanner. 
    """
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

#-----------------------------------------------------------------
# ADD/CHANGE/REMOVE DEVICES AND RECORDS
#-----------------------------------------------------------------
def add_new_device(ip, total_num, curr_num):
    """ Purpose: Checks device initial status

    :param ip: IP address of a device to check.
    :param total_num: Total number of devices in the current loop.
    :param curr_num: The number of the current device. 
    :return: None
    """
    # Check if this IP exists in the database or if it belongs to a device already in the database
    stdout.write("Connecting to {0} ({1} of {2}): ".format(ip, curr_num, total_num))
    if not get_record(listDict, ip):
        # Try connecting to this device
        dev = connect(ip, False)
        # If we can connect...
        if dev:
            # Check for hostname/serial number match
            if not check_host_sn(ip, dev):
                #print "\t-  Trying to add {0}...".format(ip)
                if add_record(ip, dev):
                    print "-> Added Successfully!"
                    message = "Successfully added to database."
                    contentList = [ip, message, get_now_time()]
                    new_devices_list.append(dict(zip(standard_key_list, contentList)))
                # If "add" fails
                else:
                    print "-> Add Failed!"
            # Check matches an existing hostname or S/N...
            else:
                print "-> Added to an existing device!"
                message = "Adding IP to existing device in database."
                contentList = [ip, message, get_now_time()]
                new_devices_list.append(dict(zip(standard_key_list, contentList)))
        # If we can't connect...
        else:
            print "-> Failed Connecting!"
    else:
        print "\t\t* Skipping device, already in database *"

def add_record(ip, dev):
    """ Purpose: Adds a record to list of dictionaries.

    :param ip:          -   The IP of the device
    :param dev:         -   The PyEZ connection object (SSH Netconf)
    :return:            -   Returns True/False
    """
    mydict = {}
    # Try to gather facts from device
    try:
        for key in facts_list:
            temp = dev.facts[key]
            if temp is None:
                message = "Add Failed - Unable to get critical parameter [" + key + "]"
                contentList = [ip, message, get_now_time()]
                new_devices_list.append(dict(zip(standard_key_list, contentList)))
                return False
                #mydict[key]
            else:
                mydict[key] = temp.upper()
    except Exception as err:
        message = "Add Failed - Error accessing facts on device. ERROR:{0}".format(err)
        contentList = [ip, message, get_now_time()]
        new_devices_list.append(dict(zip(standard_key_list, contentList)))
        return False
    else:
        now = get_now_time()
        # Try to gather inet interface parameters
        inet_info = get_inet_interfaces(ip, dev)
        #print "------------ INET INFO ---------------"
        #pp = pprint.PrettyPrinter(indent=4)
        #pp.pprint(inet_info)
        # If we were able to collect the information, add to data structure
        if inet_info:
            mydict['inet_intf'] = inet_info
            mydict['ip'] = mydict['inet_intf'][0]['ipaddr']
        else:
            mydict['ip'] = ip

        # Try to save config file, add appropriate dates to dict if save works
        if save_config_file(fetch_config(dev), mydict):
            mydict['last_config_check'] = now
            mydict['last_config_change'] = now
        # Apply dates to record dict
        mydict['last_access'] = now
        mydict['last_param_change'] = now
        mydict['last_param_check'] = now

        # Add entire record to database
        listDict.append(mydict)
        return True

def remove_record(key, value):
    """ Purpose: Remove a record from the main database. Removes only the first record found with the value.

    :param key:         -   The key to search for
    :param value:       -   The value to search for
    :return:            -   Returns True/False
    """
    for i in range(len(listDict)):
        if listDict[i][key] == value:
            print "Removing: {0}".format(listDict[i])
            del listDict[i]
            print "Removed!"
            return True
    return False

def change_record(ip, value, key):
    """ Purpose: Change an attribute of an existing record. Record is a dictionary.

    :param ip:          -   IP of the device
    :param value:       -   Value of attribute
    :param key:         -   Key of the attribute
    :return:            -   True/False
    """
    for myrecord in listDict:
        # If we've found the correct record...
        if myrecord['ip'] == ip:
            try:
                # Trying to update the record...
                change_dict = {key: value}
                myrecord.update(change_dict)
            except Exception as err:
                # Error checking...
                print "ERROR: Unable to update record value: {0} | Device: {1}".format(err, ip)
                message = "Error changing " + key + " to " + value + "."
                contentList = [ ip, message, str(err), get_now_time() ]
                ops_error_list.append(dict(zip(error_key_list, contentList)))
                return False
            # If the record change was successful...
            else:
                myrecord.update({'last_param_change': get_now_time()})
                return True

def check_host_sn(ip, dev):
    """ Purpose: Checks to see if this IP is part of another device that is already discovered. If it is, we capture all
    inet interfaces and get the preferred management IP.

    :param ip:          -   The IP of the device
    :param dev:         -   The PyEZ connection object (SSH Netconf)
    :return:            -   True/False
    """
    try:
        serialnumber = dev.facts['serialnumber']
        hostname = dev.facts['hostname']
    except Exception as err:
        print "Problem collecting facts from device. ERROR: {0}".format(err)
        return False
    else:
        # Make sure the types are valid
        if serialnumber is None or hostname is None:
            if serialnumber is None:
                serialnumber = 'BLANK'
            if hostname is None:
                hostname = 'BLANK'
            #print "Serial Number: {0}".format(serialnumber)
            #print "Hostname: {0}".format(hostname)
        # Search over database for a match
        for record in listDict:
            if record['hostname'] == hostname.upper() or record['serialnumber'] == serialnumber.upper():
                # This IP belongs to a device that is already discovered.
                # Get inet_intf info
                inet_intf = get_inet_interfaces(ip, dev)
                # Get preferred management ip address
                man_ip = inet_intf[0]['ipaddr']
                # Make changes
                #print "Change attempt!"
                if change_record(record['ip'], inet_intf, 'inet_intf') and change_record(record['ip'], man_ip, 'ip'):
                    return True
                else:
                    return False
        # No records matched
        return False

#-----------------------------------------------------------------
# MAIN LOOPS
#-----------------------------------------------------------------
def add_new_devices_loop(iplistfile):
    """ Purpose: Loop for adding devices and extracts IPs from network as needed.

    :param ipListFile: The file containing a list of IPs provided using the "-i" parameter.
    :return: None
    """
    print "Report: Add New Devices"
    print "User: {0}".format(myuser)
    print "Captured: {0}\n".format(get_now_time())

    print "Add New Devices:"
    # Loop over the list of new IPs
    ip_list = line_list(os.path.join(iplist_dir, iplistfile))
    if ip_list:
        total_num = len(ip_list)
        curr_num = 0
        for raw_ip in ip_list:
            myip = raw_ip.strip()
            # Check if this ip address is a network
            if '/' in myip:
                for ip in IPNetwork(myip):
                    # Attempt to add new device
                    curr_num += 1
                    add_new_device(str(ip), total_num, curr_num)
            # Otherwise, it should be a standard IP
            else:
                curr_num += 1
                add_new_device(myip, total_num, curr_num)

def param_config_check(record, conf_chg_log, dev):
    """ Purpose: Runs functions for checking parameters and configurations. Creates log entries.

    :param record: A dictionary containing the device information from main_db
    :param conf_chg_log: Filename/path for the config change log.
    :param dev: Reference for the connection to a device. 
    :return: None
    """
    param_results = check_params(str(record['ip']), dev)
    compare_results = config_compare(record, dev)

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
        contentList = [record['ip'], record['hostname'], get_now_time()]
        run_change_list.append(dict(zip(standard_key_list, contentList)))

    # If param results detect changes
    if param_results[-1] == 2:
        print_sl("Parameter Check:\n", conf_chg_log)
        for result in param_results[:-1]:
            print_sl("\t> {0}\n".format(result), conf_chg_log)
        print_sl("\n", conf_chg_log)
        param_change_ips.append(record['hostname'] + " (" + record['ip'] + ")")

    # If param results are errors
    elif param_results[-1] == 0:
        message = "Parameters results, errors."
        contentList = [record['ip'], message, param_results[0], get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
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
        message = "Config compare, save errors."
        contentList = [record['ip'], message, compare_results[0], get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        config_save_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")
    # If compare results are update errors
    elif compare_results[-1] == 3:
        message = "Config compare, update errors."
        contentList = [record['ip'], message, compare_results[0], get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        config_update_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")

def check_loop(subsetlist):
    """ Purpose: Checks if the subset parameter was set and decide what to execute. Adds device if it is not in the 
    database. Executes a standard check of the entire database if subset is not defined.

    :param record: A list containing IP addresses to query.
    :return: None
    """
    curr_num = 0
    if subsetlist:
        ipv4_regex = r'^([1][0-9][0-9].|^[2][5][0-5].|^[2][0-4][0-9].|^[1][0-9][0-9].|^[0-9][0-9].|^[0-9].)([1][0-9][0-9].|[2][5][0-5].|[2][0-4][0-9].|[1][0-9][0-9].|[0-9][0-9].|[0-9].)([1][0-9][0-9].|[2][5][0-5].|[2][0-4][0-9].|[1][0-9][0-9].|[0-9][0-9].|[0-9].)([1][0-9][0-9]|[2][5][0-5]|[2][0-4][0-9]|[1][0-9][0-9]|[0-9][0-9]|[0-9])$'
        if re.match(ipv4_regex, subsetlist):
            check_main(get_record(listDict, subsetlist))
        else:
            temp_list = []
            for ip_addr in line_list(os.path.join(iplist_dir, subsetlist)):
                temp_list.append(ip_addr.strip())
            # Total number of devices in this loop
            total_num = len(temp_list)
            # Loop through IPs in the provided list
            for ip in temp_list:
                curr_num += 1
                # Checks if the specified IP is NOT defined in the list of dictionaries.
                if not any(ipaddr.get('ip', None) == ip for ipaddr in listDict):
                    #print "\n" + "-" * 80
                    #print subHeading(ip, 15)
                    add_new_device(ip, total_num, curr_num)
                # If the IP IS present, execute this...
                else:
                    check_main(get_record(listDict, ip), total_num, curr_num)
    # Check the entire database
    else:
        total_num = len(listDict)
        for record in listDict:
            curr_num += 1
            check_main(record, total_num, curr_num)
    # End of processing
    print "\n" + "=" * 80
    print "Device Processsing Ended: {0}\n\n".format(get_now_time())

def check_main(record, total_num=1, curr_num=1):
    """ Purpose: Performs the selected checks (Parameter/Config, Template, or All)
        
    :param record: A dictionary containing the device information from main_db.
    :param total_num: Total number of devices in the current loop.
    :param curr_num: The number of the current device.
    :return: None
    """
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

    print "\n" + ("-" * 40) + "|" + str(curr_num) + " of " + str(total_num) + "|" + ("-" * 40)
    print subHeading(record['hostname'] + " - (" + record['ip'] + ")", 15)
    # Try to connect to device and open a connection
    record.update({'last_access': get_now_time()})
    # Try to connect to the device
    dev = connect(record['ip'], True)
    if dev:
        #print "IP Interfaces..."
        #for intf in record['inet_intf']:
        #    print "\tInterface: {0} | IP: {1} | Mask: {2} | Status: {3}".format(intf['interface'], intf['ipaddr'], intf['ipmask'], intf['status'])
        if addl_opt == "configs" or addl_opt == "all":
            print "Running Param/Config Check..."
            param_config_check(record, conf_chg_log, dev)
            # Close the connection to the device
            dev.close()
        # Try to do the template check
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
    global detail_ip
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
            print '  -i : (OPTIONAL) A TXT file in the "iplists" directory that contains a list of IPs to add to the database.'
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
    # Detect if this system is Windows or Linux/MAC
    detect_env()
    # Capture arguments
    main(sys.argv[1:])

    # Assign arguments
    myfile = os.path.join(dir_path, credsCSV)
    creds = csv_to_dict(myfile)
    myuser = creds['username']
    mypwd = creds['password']

    # Test Bed
    #xml_to_dict(dev=connect('10.104.76.193'))

    #'''
    # Load records from existing CSV
    #print "Loading records..."
    listDict = json_to_listdict(main_list_dict)
    #print "LIST DICT:"
    #print(json.dumps(listDict, indent=2))

    # Add New Device function if IPs have been supplied
    print topHeading("JMANAGE SCRIPT", 15)

    # If included in arguments, shows details of IP specified
    if detail_ip:
        print subHeading("IP DETAIL FUNCTION", 15)
        if listDict:
            loop = True
            while (loop):
                if not display_device_info(detail_ip):
                    print "Unable to find or display IP information"
                answer = getInputAnswer("Another IP ('Q' to quit)")
                if answer == 'q' or answer == 'Q':
                    loop = False
                else:
                    detail_ip = answer
        else:
            print "No Records in Database!"
    # The rest of the options, functions
    else:
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
        print "=" * 80

        # Write sorted changes to these CSVs if there are changes
        print ""
        print topHeading("SORT AND SAVE DATABASE & LOGS", 15)
        print "-" * 80
        # Run sort and save function. Will only save database or logs that are changed.
        sort_and_save()

        # Close this section
        print "\n" + "-" * 80
        print "\nFinished with saves. We're done!"
