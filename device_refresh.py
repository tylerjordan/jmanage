__copyright__ = "Copyright 2018 Tyler Jordan"
__version__ = "0.2.0"
__email__ = "tjordan@juniper.net"

# ------------------------------------------------------------------------------------------------------------------- #
# Main JSON Database Attributes:
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
# vc ................. VC Status (True = VC, False = standalone chassis)
# last_access_attempt..Last time device access was attempted
# last_access_success..Last time device successfully was accessed
# last_config_check .. Last time device config was checked
# last_config_change . Last time device config was changed
# last_param_check ... Last time device parameters were checked
# last_param_change .. Last time device parameter was changed
# last_temp_check .... Last time device template was checked
# last_temp_refresh ... Last time device template was changed
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
import difflib
import datetime
import pprint
import multiprocessing

from operator import itemgetter
from lxml import etree

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
template_all = ''
template_all_opt = ''
template_els = ''
template_nonels = ''
template_ospf = ''

template_regex_csv = ''
template_map_csv = ''
iplistfile = ''
access_error_log = ''
access_error_list = []
ops_error_log = ''
ops_error_list = []
new_devices_log = ''
new_devices_list = []
run_change_log = ''
run_change_list = []
failing_devices_csv = ''
removed_devices_csv = ''

# Log Keys
error_key_list = ['ip', 'message', 'error', 'timestamp'] # access_error_log, ops_error_log
standard_key_list = ['ip', 'message', 'timestamp'] # new_devices_log

# Params
listDict = []
mypwd = ''
myuser = ''
alt_myuser = ''
alt_mypwd = ''
port = 22
num_of_configs = 5
current_dev = 0
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
inet_error_ips = []
templ_error_ips = []

param_change_ips = []
config_change_ips = []
templ_change_ips = []
inet_change_ips = []

# Key Lists
dbase_order = [ 'hostname', 'ip', 'version', 'model', 'serialnumber', 'last_access_attempt', 'last_access_success',
                'last_config_check', 'last_config_change', 'last_param_check', 'last_param_change', 'last_inet_check',
                'last_inet_change', 'last_temp_check', 'last_temp_refresh', 'add_date']
facts_list = [ 'hostname', 'serialnumber', 'model', 'version', 'vc' ]

def detect_env():
    """ Purpose: Detect OS and create appropriate path variables. """
    global credsCSV
    global iplist_dir
    global config_dir
    global template_dir
    global log_dir
    global dir_path
    global template_all
    global template_all_opt
    global template_els
    global template_nonels
    global template_ospf
    global template_regex_csv
    global template_map_csv
    global access_error_log
    global ops_error_log
    global new_devices_log
    global run_change_log
    global failing_devices_csv
    global removed_devices_csv

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
    template_regex_csv = os.path.join(dir_path, template_dir, "template_regex.csv")
    template_map_csv = os.path.join(dir_path, template_dir, "template_regex_map.csv")
    template_all = os.path.join(dir_path, template_dir, "template_all.conf")
    template_all_opt = os.path.join(dir_path, template_dir, "template_all_opt.conf")
    template_els = os.path.join(dir_path, template_dir, "template_els.conf")
    template_nonels = os.path.join(dir_path, template_dir, "template_nonels.conf")
    template_ospf = os.path.join(dir_path, template_dir, "template_ospf.conf")
    access_error_log = os.path.join(log_dir, "Access_Error_Log.csv")
    ops_error_log = os.path.join(log_dir, "Ops_Error_Log.csv")
    new_devices_log = os.path.join(log_dir, "New_Devices_Log.csv")
    run_change_log = os.path.join(log_dir, "Run_Change_Log.csv")
    failing_devices_csv = os.path.join(log_dir, "Failing_Devices.csv")
    removed_devices_csv = os.path.join(log_dir, "Removed_Devices.csv")
# -----------------------------------------------------------------
# FILE OPERATIONS
# -----------------------------------------------------------------
def get_config_str(hostname, newest):
    """ Purpose: Load the selected device's configuration file into a variable.
    
        :param hostname     -   Hostname of the device
        :param newest:      -   True/False (True means newest, false means oldest file)
        :return:            -   A string containing the configuration   
    """
    my_file = get_config_filename(hostname, hostname, newest)
    #print "File: {0}".format(my_file)
    if my_file:
        try:
            file_string = open(my_file, 'r').read()
        except Exception as err:
            print 'ERROR: Unable to read file: {0} | File: {1}'.format(err, my_file)
            return False
        else:
            return file_string

def get_config_filename(hostname, startwith, newest):
    """ Purpose: Returns the oldest or newest config file from specified hostname

        :param hostname:    -   The hostname of the device.
        :param startwith:   -   A common string that the file starts with
        :param newest:      -   True/False (True means newest, false means oldest file)
        :return:            -   A string containing the file with complete path. False   
    """
    #print "vars: {0}|{1}|{2}".format(hostname, startwith, newest)
    filtered_list = []
    # Create the appropriate absolute path for the config file
    my_dir = os.path.join(config_dir, getSiteCode(hostname), hostname)
    #print "MyDir: {0}".format(my_dir)
    if os.path.exists(my_dir):
        for file in listdir(my_dir):
            #print "File: {0}".format(file)
            if file.startswith(startwith):
                filtered_list.append(os.path.join(my_dir, file))
        try:
            sorted_list = sorted(filtered_list, key=os.path.getctime)
        except Exception as err:
            print "Error with sorted function. ERROR: {0}".format(err)
            return filtered_list
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

def get_config_list(hostname, newest):
    """ Purpose: Load the selected device's configuration file into a list.

        :param ip:          -   Dictionary record of the device.
        :param newest:      -   Parameter for the "get_old_new_file" function
        :return:            -   List containing file contents
    """
    linelist = []
    my_file = get_config_filename(hostname, hostname, newest)
    try:
        linelist = line_list(my_file)
    except Exception as err:
        print 'ERROR: Unable to read file: {0} | File: {1}'.format(err, my_file)
        return False
    else:
        return linelist

def line_list(filepath):
    """ Purpose: Create a list of lines from the file defined.

        :param filepath:    -   The path/filename of the file
        :param dev:         -   The PyEZ SSH netconf connection to the device.
        :return linelist:   -   A list of Strings from the file.
    """
    #print "IP List File: {0}".format(filepath)
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
        for line in f.readlines():
            linelist.append(line.replace('\n', '').replace('\r', ''))
        f.close()
        return linelist

def remove_template_file(hostname):
    """ Purpose: Remove the template(s) of the corresponding device.

        :param record:      -   The dictionary information of the device.
        :return:            -   True/False
    """
    file_start = "Template_Deviation_"
    device_dir = os.path.join(config_dir, getSiteCode(hostname), hostname)
    # Check if the specified directory exists
    if os.path.exists(device_dir):
        # Loop over the files in the directory
        for file in getFileList(device_dir):
            # Find a file that starts with the "file_start" string
            if file.startswith(file_start):
                try:
                    os.remove(os.path.join(device_dir, file))
                    #print "Removed: {0}".format(file)
                except Exception as err:
                    print "Problem removing file: {0} ERROR: {1}".format(file, err)
                    return False
        return True
    else:
        print "Directory does not exist: {0}".format(device_dir)
        return False

def get_file_number(searchdir, matchstring):
    """ Purpose: Returns the number of configuration files for the defined device.

        :param record:      -   Parameter for the "get_old_new_file" function
        :return:            -   List containing file contents
    """
    file_num = 0
    for file in listdir(searchdir):
        if matchstring in file:
            file_num += 1
    return file_num

def directory_check(record):
    """ Purpose: Check if the site/device dirs exists. Creates it if it does not.

        :param record:      -   Dictionary record of the device.
        :return:            -   True/False
    """
    # Check for site specific directory
    #print "Hostname: {0}".format(record['hostname'])
    #print "Site Name: {0}".format(getSiteCode(record['hostname']))
    if not os.path.isdir(os.path.join(config_dir, getSiteCode(record['hostname']))):
        try:
            os.mkdir(os.path.join(config_dir, getSiteCode(record['hostname'])))
        except Exception as err:
            print "Failed Creating Directory -> ERROR: {0}".format(err)
            return False

    # Check for the device specific directory
    if os.path.isdir(os.path.join(config_dir, getSiteCode(record['hostname']), record['hostname'])):
        return True
    else:
        try:
            os.mkdir(os.path.join(config_dir, getSiteCode(record['hostname']), record['hostname']))
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

    # Check if supplied config has contents
    if myconfig:
        # Create the filename
        now = get_now_time()
        site_dir = os.path.join(config_dir, getSiteCode(record['hostname']), record['hostname'])
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
            mydir = os.path.join(config_dir, getSiteCode(record['hostname']), record['hostname'])
            # Remove excess configurations if necessary
            if get_file_number(mydir, record['hostname']) > 5:
                del_file = get_config_filename(record['hostname'], record['hostname'], newest=False)
                try:
                    os.remove(del_file)
                except Exception as err:
                    message = "Unable to remove config file: " + del_file + "."
                    contentList = [record['ip'], message, str(err), get_now_time()]
                    ops_error_list.append(dict(zip(error_key_list, contentList)))
                    print "ERROR: Unable to remove old file: {0} | File: {1}".format(err, del_file)
            try:
                # Write the new configuration to the new file
                newfile.write(myconfig.encode("utf-8"))
            except Exception as err:
                #print "ERROR: Unable to write config to file: {0}".format(err)
                message = "Unable to write config to file: " + fileandpath + "."
                contentList = [ record['ip'], message, str(err), get_now_time() ]
                ops_error_list.append(dict(zip(error_key_list, contentList)))
                print "ERROR: Unable to write config to file: {0} | File: {1}".format(err, del_file)
                return False
            else:
                # Close the file
                newfile.close()
                return True
    # If this is executed, the myconfig variable was empty. Fetch did not work.
    else:
        return False

def sort_and_save_csv(log_name, list_name, key_list, sort_column, new_first=True, delimiter=";"):
    """ Purpose: Adds new data to and sorts a csv log file.

    :param  log_name.........The fully qualified name of the log being saved.
            list_name........The list containing the changes for the log.
            key_list.........A list containing the fields for this log.
            sort_column......The column that this log should be sort by.
            new_first........Boolean, if True, sorts with most recent changes at top of file. (Default is "True")
            delimiter........The delimiter of this file. (Default is ";")
    :return: None
    """
    # Print brief results to screen
    if list_name:
        stdout.write("Saving -> " + log_name + ": ")
        if csv_write_sort(list_name, log_name, sort_column=sort_column, reverse_sort=new_first,
                          column_names=key_list, my_delimiter=delimiter):
            print "Successful!"
        else:
            print "Failed!"
    else:
        print "No changes to " + log_name

def sort_and_save_json(db_list_dict, db_file):
    """ Purpose: Adds new data to and sorts a json file.

    :param  db_list_dict....The list dictionary being saved into the json file.
            db_file.........The fully qualified name of the json file being saved.
    :return: None
    """
    if db_list_dict:
        stdout.write("Saving -> " + db_file + ": ")
        if write_to_json(db_list_dict, db_file):
            print "Successful!"
        else:
            print "Failed!"
    else:
        print "Database list dict not found!"

def sort_and_save():
    """ Purpose: Saves main database and sorts and saves the logs.
    :param: None
    :return: None
    """
    # Main Database
    sort_and_save_json(listDict, main_list_dict)

    # Access Error Log
    sort_and_save_csv(access_error_log, access_error_list, error_key_list, 3)

    # Operations Error Log
    sort_and_save_csv(ops_error_log, ops_error_list, error_key_list, 3)

    # New Devices Log
    sort_and_save_csv(new_devices_log, new_devices_list, standard_key_list, 2)

    # Running Changes Log
    sort_and_save_csv(run_change_log, run_change_list, standard_key_list, 2)

def get_vc_fact(dev):
    #
    # 'UNDEFINED' ... Not able to determine VC status
    # 'YES'.......... This chassis is a VC
    # 'NO'........... This chassis is not a VC
    #
    # Return appropriate value for virutal chassis status
    junos_info = 'UNDEFINED'
    capt_info = str(dev.facts['junos_info'])
    #print "JUNOS_INFO: {0}".format(capt_info)
    if capt_info.count('fpc') > 1:
        junos_info = 'YES'
    else:
        junos_info = 'NO'
    # Provide response to caller
    return junos_info

# -----------------------------------------------------------------
# CONNECTIONS
# -----------------------------------------------------------------
def connect(ip, hostname="UNKNOWN", indbase=False, probe=0, timeout=300):
    """ Purpose: Attempt to connect to the device

    :param ip:          -   IP of the device
    :param indbase:     -   Boolean if this device is in the database or not, defaults to False if not specified
    :return dev:        -   Returns the device handle if its successfully opened.
    """
    dev = Device(host=ip, user=myuser, passwd=mypwd, auto_probe=probe)
    # Try to open a connection to the device
    try:
        dev.open()
        dev.timeout = timeout
    # If there is an error when opening the connection, display error and exit upgrade process
    except ConnectRefusedError as err:
        message = "Host Reachable, but NETCONF not configured."
        stdout.write(hostname + " (" + ip + ") | Connect Fail - " + message + "\n")
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
        stdout.write(hostname + " (" + ip + ") | Connect Fail - " + message + "\n")
        if alt_myuser:
            stdout.write("Attempt to connect. User:" + alt_myuser + " |")
            dev = Device(host=ip, user=alt_myuser, passwd=alt_mypwd)
            try:
                dev.open()
            except Exception as err:
                if indbase:
                    contentList = [ip, message, str(err), get_now_time()]
                    access_error_list.append(dict(zip(error_key_list, contentList)))
                else:
                    contentList = [ip, message, get_now_time()]
                    new_devices_list.append(dict(zip(standard_key_list, contentList)))
                no_auth_ips.append(ip)
                return False
            else:
                return dev
        else:
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
        stdout.write(hostname + " (" + ip + ") | Connect Fail - " + message + "\n")
        contentList = [ ip, message, str(err), get_now_time() ]
        fail_num = fail_check(ip, indbase, contentList)
        no_ping_ips.append({'ip': ip, 'days': fail_num})
        return False
    except ProbeError as err:
        message = "Probe timeout, possible IP reachability issues."
        stdout.write(hostname + " (" + ip + ") | Connect Fail - " + message + "\n")
        contentList = [ ip, message, str(err), get_now_time() ]
        fail_num = fail_check(ip, indbase, contentList)
        no_ping_ips.append({'ip': ip, 'days': fail_num})
        return False
    except ConnectError as err:
        message = "Unknown connection issue."
        stdout.write(hostname + " (" + ip + ") | Connect Fail - " + message + "\n")
        contentList = [ ip, message, str(err), get_now_time() ]
        fail_num = fail_check(ip, indbase, contentList)
        no_connect_ips.append({'ip': ip, 'days': fail_num})
        return False
    except Exception as err:
        message = "Undefined exception."
        stdout.write(hostname + " (" + ip + ") | Connect Fail - " + message + "\n")
        contentList = [ip, message, str(err), get_now_time()]
        fail_num = fail_check(ip, indbase, contentList)
        no_connect_ips.append({'ip': ip, 'days': fail_num})
        return False
    # If try arguments succeeded...
    else:
        stdout.write(hostname + " (" + ip + ") | Connected!\n")
        return dev

# -----------------------------------------------------------------
# LOGGING | SHOWS
# -----------------------------------------------------------------
def fail_check(ip, indbase, contentList):
    """ Purpose: Performs additional operations and logging on devices if they are not accessible.

    :param ip:          -   The IP address of the device in question
    :param indbase:     -   Boolean on if the device is in the database or not.
    :param contentList: -   Content for the log entry.
    :return days_exp:   -   Number of days expired for this device
    """
    # Number of days to keep IP after first fail attempt
    attempt_limit = 10
    matched = False
    days_exp = "0"

    # If the device is in the database...
    if indbase:
        oldListDict = csv_to_listdict(failing_devices_csv)
        myDelimiter = ","
        newListDict = []

        # If the CSV exists...
        if oldListDict:
            # Loop over records in the CSV...
            for myDict in oldListDict:
                # If we find the subject IP in the CSV...
                if myDict['ip'] == ip:
                    matched = True
                    # Remove the previous record from the Fail Devices list dict
                    oldListDict.remove(myDict)
                    # Determine calculate how long device has been unreachable
                    past_time = datetime.datetime.strptime(myDict['date_added'], "%Y-%m-%d_%H%M")
                    now_time = datetime.datetime.now()
                    days_exp = str((now_time - past_time).days)
                    # Update the record
                    stdout.write(" Consecutive Failed Days: {0} |".format(days_exp))
                    # Check if time exceeds the allowable attempt limit
                    if int(days_exp) > attempt_limit:
                        # Remove record from main database
                        stdout.write(" Attempts Exceeded Limit - Removing from Database |")
                        remove_record(listDict, 'ip', ip, config_dir)
                        # Add record to Removed_Devices CSV
                        attribOrderRemove = ['ip', 'consec_days', 'date_removed']
                        remListDict = [{'ip': ip, 'consec_days': days_exp, 'date_removed': get_now_time()}]
                        listdict_to_csv(remListDict, removed_devices_csv, myDelimiter, attribOrderRemove)
                    else:
                        # Update the record last attempt and consecutive days
                        myDict.update({'last_attempt': get_now_time()})
                        myDict.update({'consec_days': days_exp})
                        # Add the record to the list dictionary
                        newListDict = oldListDict
                        newListDict.append(myDict)
                    # Update the Failed Devices CSV
                    attribOrderFail = ['ip', 'consec_days', 'last_attempt', 'date_added']
                    listdict_to_csv(newListDict, failing_devices_csv, myDelimiter, attribOrderFail)
                    # Add the error to the appropriate list
                    access_error_list.append(dict(zip(error_key_list, contentList)))
                    return days_exp
            # If IP is not in the CSV...
            if not matched:
                # Create new record
                myDict = {
                    'ip': ip,
                    'consec_days': "1",
                    'last_attempt': get_now_time(),
                    'date_added': get_now_time(),
                }
                # Preserve the existing records and add this dictionary to the end
                newListDict = oldListDict
                newListDict.append(myDict)
        # Otherwise, if the CSV doesn't exist...
        else:
            # Create new record
            myDict = {
                'ip': ip,
                'consec_days': "1",
                'last_attempt': get_now_time(),
                'date_added': get_now_time(),
            }
            # Add this record to the new listDict
            newListDict.append(myDict)

        stdout.write(" Adding to Failed Devices |")
        days_exp = "1"
        # Add record to failing CSV
        attribOrderFail = ['ip', 'consec_days', 'last_attempt', 'date_added']
        if listdict_to_csv(newListDict, failing_devices_csv, myDelimiter, attribOrderFail):
            stdout.write(" Adding Successful |")
        else:
            stdout.write(" Adding Failed |")
        # This applies to devices that are in the database already. Add to access error log.
        access_error_list.append(dict(zip(error_key_list, contentList)))
    # If the device is not in the database...
    else:
        # This applies to new devices that had a connection issue. Add to new devices log.
        del contentList[2]
        new_devices_list.append(dict(zip(standard_key_list, contentList)))
    return days_exp

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
    # Unable to Ping
    print_log("\tUnable to Ping: {0}\n".format(len(no_ping_ips)), summary_log)
    if len(no_ping_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        #print no_ping_ips
        for ip in no_ping_ips:
            if not ip['days'] == "0":
                print_log("\t\t-> " + ip['ip'] + " (" + ip['days'] + ")\n", summary_log)
            else:
                print_log("\t\t-> " + ip['ip'] + "\n", summary_log)
    # Generic Connection Issue
    print_log("\tUnknown connection issue: {0}\n".format(len(no_connect_ips)), summary_log)
    if len(no_connect_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        #print no_connect_ips
        for ip in no_connect_ips:
            if not ip['days'] == "0":
                print_log("\t\t-> " + ip['ip'] + " (" + ip['days'] + ")\n", summary_log)
            else:
                print_log("\t\t-> " + ip['ip'] + "\n", summary_log)

    print_log("=" * 50 + "\n", summary_log)

    # *************** PARAMETER CONTENT ***************
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

    # *************** INET CONTENT ***************
    print_log("[Inets]\n", summary_log)
    print_log("\tChanged Inets: {0}\n".format(len(inet_change_ips)), summary_log)
    if len(inet_change_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in inet_change_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("\tError Accessing Inets: {0}\n".format(len(inet_error_ips)), summary_log)
    if len(inet_error_ips) == 0:
        print_log("\t\t* No Devices *\n", summary_log)
    else:
        for ip in inet_error_ips:
            print_log("\t\t-> " + ip + "\n", summary_log)
    print_log("=" * 50 + "\n", summary_log)

    # *************** CONFIG COMPARE CONTENT ***************
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

    # *************** TEMPLATE DEVIATION CONTENT ***************
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

# -----------------------------------------------------------------
# PARAMETER STUFF
# -----------------------------------------------------------------
def check_params(record, dev):
    """ Purpose: Checks the parameters to see if they have changed. If param is changed, it is updated and logged, if 
    not, the "last_param" timestamp is only updated.

        remoteDict: The chassis information gathered from the device now. (NEW INFO)
        record:  The chassis information gathered from the database. (OLD INFO)

        :param record:      -   Contains the parameters of the devicels
        :param dev:         -   The PyEZ SSH netconf connection to the device.
        :return results:    -   A list that contains the results of the check, including the following parameter.
                            (0 = Unable to Check, 1 = No Changes, 2 = Changes Detected    
    """
    returncode = 1
    # Store the results of check and returncode
    results = []
    remoteDict = {}

    #stdout.write("\n\t\tParameter Check: ")
    # Try to collect current chassis info
    for key in facts_list:
        # Check VC with special function, not in facts
        if key == 'vc':
            # Provide returned value (YES, NO, UNDEFINED)
            remoteDict['vc'] = get_vc_fact(dev)
        # Check the rest of the keys that are in the 'facts'
        else:
            if key in dev.facts and dev.facts[key]:
                remoteDict[key] = dev.facts[key]
            else:
                #print "No Key Match!"
                remoteDict[key] = "UNDEFINED"

    # If info was collected...
    if remoteDict:
        if record:
            # Update database date for parameter check
            record.update({'last_param_check': get_now_time()})
            # Check that the existing record is up-to-date. If not, update.
            #print "\t- Check parameters:"

            for item in facts_list:
                if item in record.keys():
                    #print "Check Item: {0}".format(item)
                    #print "Remote Item: {0}".format(remoteDict[item])
                    #print "Record Item: {0}".format(record[item])
                    # This captures any undefined parameters and processes and error message
                    if remoteDict[item] == "UNDEFINED":
                        message = "Unable to collect " + item.upper() + " from device."
                        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Parameter Check: ERROR: " + message + "\n")
                        results.append(message)
                        returncode = 0
                    # This will check any properly formatted attributes, to see if they changed
                    else:
                        if not record[item].upper() == remoteDict[item].upper():
                            message = item.upper() + " changed from " + record[item] + " to " + remoteDict[item]
                            stdout.write(record['hostname'] + " (" + record['ip'] + ") | Parameter Check: " + message + "\n")
                            results.append(message)
                            #print "Check Params function"
                            old_hostname = record[item]
                            change_record(record['ip'], remoteDict[item].upper(), key=item)
                            returncode = 2
                            # print "Changed!"
                            # Check if HOSTNAME has changed, if yes, change the directory name
                            if item.upper() == 'HOSTNAME' and returncode == 2:
                                old_path = os.path.join(config_dir, getSiteCode(record[item]), old_hostname)
                                new_path = os.path.join(config_dir, getSiteCode(record[item]), remoteDict[item])
                                #print "Old Path: {0}".format(old_path)
                                #print "New Path: {0}".format(new_path)
                                try:
                                    os.rename(old_path, new_path)
                                except Exception as err:
                                    stdout.write(record['hostname'] + " (" + record['ip'] + ") | Parameter Check: ERROR: Unable to change path: {0}\n".format(err))
                                else:
                                    stdout.write(record['hostname'] + " (" + record['ip'] + ") | Parameter Check: Changed directory path from "  + old_path + " to " + new_path + "\n")
                    # Check for VC specifically
                    '''
                    if not record['vc'].upper() == remoteDict['vc'].upper():
                        message = "VC changed from " + record['vc'] + " to " + remoteDict['vc']
                        stdout.write("\n\t\tParameter Check: " + message)
                        results.append(message)
                        change_record(record['ip'], remoteDict['vc'].upper(), key='vc')
                        returncode = 2
                    '''
                # If the key does not exist, create it using the current value
                else:
                    change_record(record['ip'], remoteDict[item].upper(), key=item)
                    message = "'{0}' does not exist in record, creating using current value".format(item)
                    stdout.write(record['hostname'] + " (" + record['ip'] + ") | Parameter Check: " + message + "\n")
                    results.append(message)
                    returncode = 2
        else:
            message = "Unable to collect parameters from database."
            stdout.write(record['hostname'] + " (" + record['ip'] + ") | Parameter Check: ERROR: " + message + "\n")
            results.append(message)
            returncode = 0
    # If we are unable to collect info from this device
    else:
        message = "Unable to collect current parameters from device."
        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Parameter Check: ERROR: " + message + "\n")
        results.append(message)
        returncode = 0

    #if returncode == 1:
    #   stdout.write("No changes")

    # Return the info to caller
    results.append(returncode)
    return results

def param_check(record, chg_log, dev):
    """ Purpose: Runs functions for checking parameters. Creates log entries.

    :param record: A dictionary containing the device information from main_db
    :param conf_chg_log: Filename/path for the config change log.
    :param dev: Reference for the connection to a device. 
    :return: None
    """
    param_results = check_params(record, dev)

    # Param Results: 0 = Error, 1 = No Changes, 2 = Changes
    # Scan param results
    if param_results[-1] == 2:  # If changes are detected
        print_log("Report: Parameter Check\n", chg_log)
        print_log("Device: {0} ({1})\n".format(record['hostname'], record['ip']), chg_log)
        print_log("User: {0}\n".format(myuser), chg_log)
        print_log("Checked: {0}\n".format(get_now_time()), chg_log)
        # The "run_change_log" format is "IP,HOSTNAME,DATE"
        contentList = [record['ip'], record['hostname'], get_now_time()]
        run_change_list.append(dict(zip(standard_key_list, contentList)))

    # If param results detect changes
    if param_results[-1] == 2:
        print_log("Parameter Check:\n", chg_log)
        for result in param_results[:-1]:
            print_log("\t> {0}\n".format(result), chg_log)
        print_log("\n", chg_log)
        param_change_ips.append(record['hostname'] + " (" + record['ip'] + ")")

    # If param results are errors
    elif param_results[-1] == 0:
        message = "Parameters results, errors."
        contentList = [record['ip'], message, param_results[0], get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        param_attrib_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")

    return param_results[-1]

#-----------------------------------------------------------------
# INET STUFF
#-----------------------------------------------------------------
def check_inet(record, dev):
    """ Purpose: Checks the inet interfaces to see if they have changed. If inets have changed, it is updated and logged, if 
    not, the "last_inet" timestamp is only updated.

        record:              The chassis information gathered from the database. (OLD INFO)
        get_inet_interfaces:    Gathers the current inet interface info. (NEW INFO)

        :param ip:          -   String of the IP of the device
        :param dev:         -   The PyEZ SSH netconf connection to the device.
        :return results:    -   A list that contains the results of the check, including the following parameter.
                            (0 = Unable to Check, 1 = No Changes, 2 = Changes Detected
    """
    returncode = 1
    # Store the results of check and returncode
    results = []

    # Get current information to compare against database info
    if record:
        # Update database date for parameter check
        record.update({'last_inet_check': get_now_time()})
        # Check that the existing record is up-to-date. If not, update.
        #print "\t- Check parameters:"
        # Check inet interfaces, if they have changed, update them
        #stdout.write("\t- Check Inet Interfaces...")
        list1 = get_inet_interfaces(record['ip'], dev)
        # Check if database info contains "inet interface" data
        if 'inet_intf' in record:
            # Check if able to get "inet interface" from device now
            if list1:
                list2 = record['inet_intf']
                # Remove updated keys, these will always be different
                modlist1 = [{k: v for k, v in d.iteritems() if k != 'updated'} for d in list1]
                modlist2 = [{k: v for k, v in d.iteritems() if k != 'updated'} for d in list2]
                # print "List 1: {0}".format(list1)
                # print "List 2: {0}".format(list2)
                # Use zip to combine two lists to find differences
                pairs = zip(modlist1, modlist2)
                if any(x != y for x, y in pairs):
                    # print "Change True"
                    if change_record(record['ip'], list1, key='inet_intf'):
                        record.update({'last_inet_change': get_now_time()})
                        message = "Inet intefaces have changed."
                        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Inet Check: " + message + "\n")
                        results.append(message)
                        returncode = 2
                        #print "Changed!"
            else:
                message = "Unable to collect new inet interface info. Keeping old info."
                stdout.write(record['hostname'] + " (" + record['ip'] + ") | Inet Check: ERROR: " + message + "\n")
                results.append(message)
                returncode = 0
        # This means database does not contain "inet interface" information
        else:
            # Check if able to get "inet interface" from device now
            if list1:
                # Save info to device record
                if change_record(record['ip'], list1, key='inet_intf'):
                    record.update({'last_inet_change': get_now_time()})
                    message = "Inet intefaces have changed."
                    stdout.write(record['hostname'] + " (" + record['ip'] + ") | Inet Check: " + message + "\n")
                    results.append(message)
                    returncode = 2
                    #print "Changed!"
            # Unable to collect info, send error
            else:
                message = "Unable to collect inet interface info from device."
                stdout.write(record['hostname'] + " (" + record['ip'] + ") | Inet Check: ERROR: " + message + "\n")
                results.append(message)
                returncode = 0
    else:
        message = "Unable to collect inet interface info from database."
        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Inet Check: ERROR: " + message + "\n")
        results.append(message)
        returncode = 0

    #if returncode == 1:
    #    stdout.write("No changes")
    # Return the info to caller
    results.append(returncode)
    return results

def inet_check(record, chg_log, dev):
    """ Purpose: Runs functions for checking configurations. Creates log entries.

    :param record: A dictionary containing the device information from main_db
    :param conf_chg_log: Filename/path for the config change log.
    :param dev: Reference for the connection to a device. 
    :return: None
    """
    inet_results = check_inet(record, dev)
    # Inet Results: 0 = Error, 1 = No Changes, 2 = Changes Detected
    # Compare Results: 0 = Saving Error, 1 = No Changes, 2 = Changes Detected 3 = Update Error
    if inet_results[-1] == 2:  # If changes are detected
        print_log("Report: Inet Interfaces\n", chg_log)
        print_log("Device: {0} ({1})\n".format(record['hostname'], record['ip']), chg_log)
        print_log("User: {0}\n".format(myuser), chg_log)
        print_log("Checked: {0}\n".format(get_now_time()), chg_log)
        # The "run_change_log" format is "IP,HOSTNAME,DATE"
        contentList = [record['ip'], record['hostname'], get_now_time()]
        run_change_list.append(dict(zip(standard_key_list, contentList)))

    # If inet results detect changes
    if inet_results[-1] == 2:
        print_log("Inet Check:\n", chg_log)
        for result in inet_results[:-1]:
            print_log("\t> {0}\n".format(result), chg_log)
        print_log("\n", chg_log)
        inet_change_ips.append(record['hostname'] + " (" + record['ip'] + ")")

    # If inet results are errors
    elif inet_results[-1] == 0:
        message = "Inet results, errors."
        contentList = [record['ip'], message, inet_results[0], get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        inet_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")

    return inet_results[-1]

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
    # IP Exclude List
    excluded_ip_list = ['127.0.0.1', '255.255.255.255']

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
                            if 'address-family' in intf['logical-interface']:
                                if intf['logical-interface']['address-family']['address-family-name'] == 'inet' and 'interface-address' in intf['logical-interface']['address-family']:
                                    if isinstance(intf['logical-interface']['address-family']['interface-address'], dict):
                                        # Assign variables to dictionary
                                        ip_and_mask = get_ip_mask(intf['logical-interface']['address-family']['interface-address']['ifa-local'])
                                        #print "A IP and Mask {0}".format(intf['logical-interface']['address-family']['interface-address']['ifa-local'])
                                        intf_dict['interface'] = intf['logical-interface']['name'].encode('utf-8')
                                        intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                        intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                        intf_dict['status'] = intf['logical-interface']['oper-status'].encode('utf-8')
                                        intf_dict['updated'] = get_now_time()
                                        # Append dictionary to list if the IP is not from the excluded list
                                        #if not intf_dict['ipaddr'] in excluded_ip_list:
                                        intf_list.append(intf_dict.copy())

                                    else:
                                        for mylist in intf['logical-interface']['address-family']['interface-address']:
                                            ip_and_mask = get_ip_mask(mylist['ifa-local'])
                                            #print "B IP and Mask {0}".format(intf['ifa-local'])
                                            intf_dict['interface'] = intf['logical-interface']['name'].encode('utf-8')
                                            intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                            intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                            intf_dict['status'] = intf['logical-interface']['oper-status'].encode('utf-8')
                                            intf_dict['updated'] = get_now_time()
                                            # Append dictionary to list if the IP is not from the excluded list
                                            #if not intf_dict['ipaddr'] in excluded_ip_list:
                                            intf_list.append(intf_dict.copy())
                            else:
                                # Doesn't contain "address-family"
                                pass
                    else:
                        for mylist in intf['logical-interface']:
                            if 'address-family' in mylist:
                                if re.match(logi_regex, mylist['name']):
                                    #print "INTERFACE: {0}".format(mylist['name'])
                                    #print mylist
                                    if mylist['address-family']['address-family-name'] == 'inet' and 'interface-address' in mylist['address-family']:
                                        if isinstance(mylist['address-family']['interface-address'], dict):
                                            ip_and_mask = get_ip_mask(mylist['address-family']['interface-address']['ifa-local'])
                                            #print "C IP and Mask {0}".format(mylist['address-family']['interface-address']['ifa-local'])
                                            intf_dict['interface'] = mylist['name'].encode('utf-8')
                                            intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                            intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                            intf_dict['status'] =  mylist['oper-status'].encode('utf-8')
                                            intf_dict['updated'] = get_now_time()
                                            # Append dictionary to list if the IP is not from the excluded list
                                            #if not intf_dict['ipaddr'] in excluded_ip_list:
                                            intf_list.append(intf_dict.copy())

                                        else:
                                            for mynewlist in mylist['address-family']['interface-address']:
                                                ip_and_mask = get_ip_mask(mynewlist['ifa-local'])
                                                #print "D IP and Mask {0}".format(mynewlist['ifa-local'])
                                                intf_dict['interface'] = mylist['name'].encode('utf-8')
                                                intf_dict['ipaddr'] = ip_and_mask[0].encode('utf-8')
                                                intf_dict['ipmask'] = ip_and_mask[1].encode('utf-8')
                                                intf_dict['status'] = mylist['oper-status'].encode('utf-8')
                                                intf_dict['updated'] = get_now_time()
                                                # Append dictionary to list if the IP is not from the excluded list
                                                #if not intf_dict['ipaddr'] in excluded_ip_list:
                                                intf_list.append(intf_dict.copy())
                            else:
                                # Doesn't contain "address-family"
                                pass
        else:
            message = "Error collecting interface information."
            err = "KeyError: run show interfaces on device."
            contentList = [ip, message, err, get_now_time()]
            ops_error_list.append(dict(zip(error_key_list, contentList)))
            blank_list = []
            return blank_list

        # Sort criteria
        sort_list = ['me0.0', 'lo0.119', 'lo0.0', 'irb.119', 'irb.0', 'vlan.119', 'vlan.0']
        #print "Interface List:"
        #print intf_list
        # Sort and provide list dictionary
        return list_dict_custom_sort(intf_list, "interface", sort_list, "ipaddr", excluded_ip_list)

#-----------------------------------------------------------------
# CONFIG STUFF
#-----------------------------------------------------------------
# Compare two configurations and provide a list of the differences
def compare_configs(config1, config2):
    """ Purpose: To compare two configs and get the changes.
        Returns: True means there are differences, false means they are the same.
    """
    change_list = []
    config1_lines = config1.splitlines(1)
    config2_lines = config2.splitlines(1)

    diffInstance = difflib.Differ()
    try:
        diffList = list(diffInstance.compare(config1_lines, config2_lines))
    except Exception as err:
        print "ERROR: Config comparison failed."
        return False
    else:
        #print '-'*50
        #print "Lines different in config1 from config2:"
        for line in diffList:
            if line[0] == '-':
                change_list.append(line)
                #print "\t" + line
            elif line[0] == '+':
                change_list.append(line)
                #print "\t" + line
        #print '-'*50
        return change_list

def config_compare(record, dev):
    """ Purpose: To compare two configs and get the differences, log them

    :param record:          -   A dictionary that contains device attributes
    :param dev:             -   Connection handle to device.
    :return:                -   A results list of changes
    """
    results = []
    # 0 = Save Failed, 1 = No Changes, 2 = Changes Detected, 3 = Update Failed
    returncode = 1

    # Loads the existing (latest) configuration file into a string.
    loaded_config = get_config_str(record['hostname'], newest=True)
    #print "Loaded Config: " + loaded_config

    # Update check date
    record.update({'last_config_check': get_now_time()})
    # If loaded_config has nothing, then no configuration exists
    if not loaded_config:
        # Try to collect the config
        myconfig = fetch_config(dev, record['version'])
        # If the config was collected, try to save it as well
        if myconfig:
            # If the configuration save works
            if save_config_file(myconfig, record):
                #stdout.write("\n\t\tNo existing config, config saved")
                results.append("No Existing Config, Configuration Saved")
                record.update({'last_config_change': get_now_time()})
            # If the configuration save doesn't work
            else:
                message = "Unable to save configuration."
                stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: ERROR: " + message + "\n")
                results.append(message)
                returncode = 0
        # If the config was not collected, print a fetch error
        else:
            message = "Unable to fetch configuration from device - unable to save configuration."
            stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: ERROR: " + message + "\n")
            results.append(message)
            returncode = 0
    # If loaded_config returns a configuration...
    else:
        # Try to get the current configuration
        current_config = fetch_config(dev, record['version'])

        # If the current configuration is returned...
        if current_config:
            # Compare configurations
            change_list = compare_configs(loaded_config, current_config)
            # If change_list returns with values, the configs are different
            if change_list:
                record.update({'last_config_change': get_now_time()})
                stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: Configuration was changed")
                returncode = 2
                # Try to write diffList output to a list
                for item in change_list:
                    results.append(item)
                # Try to save the new config file
                if save_config_file(current_config, record):
                    stdout.write(" | New config saved\n")
                else:
                    message = "Unable to save new config"
                    stdout.write(" | ERROR: " + message + "\n")
                    results.append(message)
                    returncode = 3
            # If change_list length is 0, there are no differences in config
            elif len(change_list) == 0:
                # Calculate how old the newest configuration file is
                newest_config_file = get_config_filename(record['hostname'], record['hostname'], newest=True)
                config_time_obj = re.search('\d{4}-\d{2}-\d{2}_\d{4}', newest_config_file)
                c_time = datetime.datetime.strptime(config_time_obj.group(0), "%Y-%m-%d_%H%M")
                now_time = datetime.datetime.now()
                diff = now_time - c_time
                #print "\nDiff Days: {0}".format(diff.days)
                # If the latest configuration is over a week old, create a new one
                if diff.days > 2:
                    try:
                        save_config_file(current_config, record)
                        message = "Refreshed latest configuration"
                        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: " + message + "\n")
                        results.append(message)
                        returncode = 1
                    except Exception as err:
                        message = "Unable to save new config"
                        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: ERROR: " + message + "\n")
                        results.append(message)
                        returncode = 3
                else:
                    message = "No configuration changes"
                    stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: " + message + "\n")
                    results.append(message)
                    returncode = 1
            # False means the compare_configs process failed
            else:
                message = "Error during configuration comparison, check configs"
                stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: ERROR: " + message + "\n")
                results.append(message)
                returncode = 0
        else:
            message = "Unable to retrieve configuration"
            stdout.write(record['hostname'] + " (" + record['ip'] + ") | Config Check: ERROR: " + message + "\n")
            results.append(message)
            returncode = 0
    #if returncode == 1:
    #    stdout.write("No changes")

    results.append(returncode)
    return results

def config_check(record, chg_log, dev):
    """ Purpose: Runs functions for checking configurations. Creates log entries.

    :param record: A dictionary containing the device information from main_db
    :param conf_chg_log: Filename/path for the config change log.
    :param dev: Reference for the connection to a device. 
    :return: None
    """
    compare_results = config_compare(record, dev)
    # Compare Results: 0 = Saving Error, 1 = No Changes, 2 = Changes Detected 3 = Update Error
    if compare_results[-1] == 2:  # If changes are detected
        print_log("Report: Config Check\n", chg_log)
        print_log("Device: {0} ({1})\n".format(record['hostname'], record['ip']), chg_log)
        print_log("User: {0}\n".format(myuser), chg_log)
        print_log("Checked: {0}\n".format(get_now_time()), chg_log)
        # The "run_change_log" format is "IP,HOSTNAME,DATE"
        contentList = [record['ip'], record['hostname'], get_now_time()]
        run_change_list.append(dict(zip(standard_key_list, contentList)))

    # If compare results detect differences
    if compare_results[-1] == 2:
        print_log("Config Check:\n", chg_log)
        for result in compare_results[:-1]:
            print_log("\t> {0}".format(result), chg_log)
        print_log("\n", chg_log)
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

    return compare_results[-1]

def fetch_config(dev, ver):
    """ Purpose: Creates the log entries and output for the results summary.

    :param dev:         -   The device handle for gather info from device
    :param sn:          -   The serial-number of the device
    :return:            -   Returns a ASCII set version of the configuration
    """
    myconfig = ""
    # Get the interger representation of the major version
    try:
        maj_ver = int(ver[:2])
    except ValueError as err:
        print "\n\t\tERROR: {0}".format(err)
        print "\t\tREASON: Unable to pull major version from {0}".format(ver)
        maj_ver = 14
    # Attempts to use cli hack if version is earlier than 15
    if maj_ver < 15:
        rawconfig = dev.cli('show configuration | display set', warning=False)
        # Following code removes any non-ascii characters from the configuration string.
        rawconfig = rawconfig.encode('ascii', errors='ignore')
        # Following code strips out any tabs, newlines, carriage returns
        myconfig = rawconfig.strip('\t\n\r')
        # Following code catches any non set
        if not re.match('^set\s', myconfig):
            err = re.search('^.*', myconfig)
            print "Config Error: {0}".format(err.group(0))
            myconfig = ""
    # Otherwise use the "better" get_config rpc that is supported in JunOS 15.1 and later
    else:
        rawconfig = dev.rpc.get_config(options={'format': 'set'})
        myconfig = re.sub('<.+>', '', etree.tostring(rawconfig))
    # Returns a text version of the configuration in "set" format
    return myconfig

#-----------------------------------------------------------------
# TEMPLATE STUFF
#-----------------------------------------------------------------
def template_check(record, force_refresh=False):
    """ Purpose: Runs the template function and creates log entries.
    :param record: A dictionary containing the device information from main_db
    :param temp_dev_log: Filename/path for the template log.
    :return: None
    """
    # Check if template option was specified
    # Template Results: 0 = Error, 1 = No Deviations, 2 = Deviations, 3 = No New Template Needed

    # Check for OSPF configuration, see if this is a route point
    ospf_str = "set protocols ospf"
    is_mdf = False
    host_config = get_config_str(record['hostname'], True)
    if ospf_str in host_config:
        is_mdf = True

    # Run template check
    templ_results = template_results(template_regex(record['model'], is_mdf), record, force_refresh)

    # Check to see if a template run was even needed.
    #print "Result Code: {0}".format(templ_results[-1])
    if templ_results[-1] != 0:
        # Create the template deviation log
        now = get_now_time()
        device_dir = os.path.join(config_dir, getSiteCode(record['hostname']), record['hostname'])
        temp_dev_name = "Template_Deviation_" + now + ".log"
        temp_dev_log = os.path.join(device_dir, temp_dev_name)

        print_log("Report: Template Deviation Check\n", temp_dev_log)
        print_log("Device: {0} ({1})\n".format(record['hostname'], record['ip']), temp_dev_log)
        print_log("User: {0}\n".format(myuser), temp_dev_log)
        print_log("Checked: {0}\n".format(get_now_time()), temp_dev_log)

        # Run this if we have missing configuration components reported
        if templ_results[-1] == 1:
            print_log("\t* Template Matches *\n", temp_dev_log)
        # Run this if an error was reported
        elif templ_results[-1] == 0:
            print_log("\t* Template Error: {0} *\n".format(templ_results[0]), temp_dev_log)
            message = "Error when running template function."
            contentList = [record['ip'], message, templ_results[0], get_now_time()]
            ops_error_list.append(dict(zip(error_key_list, contentList)))
            templ_error_ips.append(record['hostname'] + " (" + record['ip'] + ")")
        # Run this for any other report codes
        else:
            missing_conf = []
            extra_conf = []
            # Loop over configuration, sorting the config lines accordingly
            for result in templ_results[:-1]:
                if result.startswith("(-)"):
                    missing_conf.append(result)
                else:
                    extra_conf.append(result)
            # Assemble the template deviation check file
            if missing_conf:
                print_log("\nMissing Configuration:\n", temp_dev_log)
                for line in missing_conf:
                    print_log("\t{0}\n".format(line), temp_dev_log)
            if extra_conf:
                print_log("\nExtra Configuration:\n", temp_dev_log)
                for line in extra_conf:
                    print_log("\t{0}\n".format(line), temp_dev_log)
            templ_change_ips.append(record['hostname'] + " (" + record['ip'] + ")")
    # Return the result code of the template report
    return templ_results[-1]

# Creates a dictionary of the variables and their corresponding regex
def create_template_mapping():
    regex_terms = csv_to_dict_twoterm(template_regex_csv, ";")    # CSV with regex strings
    regex_mapping = csv_to_dict_twoterm(template_map_csv, ";")    # CSV with variable to regex string mappings

    # Create the mapping translation
    map_dict = {}
    for key1, value1 in regex_mapping.iteritems():
        for key2, value2 in regex_terms.iteritems():
            if value1 == key2:
                map_dict[key1] = value2
                #print "\nName: {0} | Value: {1}".format(key1, value2)
    #print "MAP DICT:"
    #print map_dict
    #exit()
    return map_dict

def template_results(regtmpl_list, record, force_refresh):
    """ Purpose: Make sure a new template is needed. If it is, create deviation log, and return results.

    :param regtmpl_list:    -   List of template set commands with regex
    :param record:          -   A dictionary containing device attributes
    :return results:        -   A list containing results of scan.
    """
    results = []

    # Template Results: 0 = Error, 1 = No Changes, 2 = Changes, 3 = No Template Needed
    newest_config_file = get_config_filename(record['hostname'], record['hostname'], newest=True)
    # Check if this is a forced refresh or just a standard scan
    if force_refresh:
        remove_template_file(record['hostname'])
        results = template_scan_opt(record, regtmpl_list)
        record.update({'last_temp_refresh': get_now_time()})
        record.update({'last_temp_check': get_now_time()})
        message = "Forced Refresh of Template"
        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: " + message + "\n")
        return results
    # Run this if this is a standard scan
    else:
        if newest_config_file:

            #print "Config Time: {0}".format(config_time_obj.group(0))
            newest_template_file = get_config_filename(record['hostname'], 'Template_Deviation', newest=True)
            #print "Template File: {0}".format(newest_template_file)
            if newest_template_file:
                template_time_obj = re.search('\d{4}-\d{2}-\d{2}_\d{4}', newest_template_file)
                t_time = datetime.datetime.strptime(template_time_obj.group(0), "%Y-%m-%d_%H%M")
                config_time_obj = re.search('\d{4}-\d{2}-\d{2}_\d{4}', newest_config_file)
                c_time = datetime.datetime.strptime(config_time_obj.group(0), "%Y-%m-%d_%H%M")
                # Compute the time difference between the config file and template file
                diff = c_time - t_time
                #print "\nC time: {0}".format(c_time)
                #print "T time: {0}".format(t_time)
                #print "Diff: {0}".format(diff)
                # If the config file is newer than the template file...
                if c_time > t_time:
                    remove_template_file(record['hostname'])
                    results = template_scan_opt(record, regtmpl_list)
                    record.update({'last_temp_refresh': get_now_time()})
                    record.update({'last_temp_check': get_now_time()})
                    message = "Configuration File Newer Than Template"
                    stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: " + message + " -> Successfully Refreshed Template" + "\n")
                    return results
                # The template file is current for the latest config file available, skip template function
                else:
                    message = "Template Newer Than Configuration File"
                    stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: " + message + " -> No Template Refresh Needed" + "\n")
                    results.append(message)
                    returncode = 3
            # There is no template file, but there is a config file, try to compare and create a template
            else:
                results = template_scan_opt(record, regtmpl_list)
                record.update({'last_temp_refresh': get_now_time()})
                record.update({'last_temp_check': get_now_time()})
                message = "No Template Found"
                stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: " + message + " -> Successfully Created Template" + "\n")
                return results
        # No config file, skip template function
        else:
            message = "No Valid Configuration Available"
            stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: " + message + "\n")
            results.append(message)
            returncode = 0
    # Update template check timestamp
    record.update({'last_temp_check': get_now_time()})

    results.append(returncode)
    return results


def template_scan_opt(record, regtmpl_list):
    """ Purpose: Run the template against the record

    :param record:          -   A dictionary containing device attributes
    :return results:        -   A list containing results of scan.
    """
    # Template Results: 0 = Error, 1 = No Changes, 2 = Changes
    nomatch = True
    results = []
    returncode = 1

    # Print the regex template list
    #print "Regex Template List:"
    #pprint.pprint(regtmpl_list)
    #exit()

    # Try to get the latest config file
    config_list = get_config_list(record['hostname'], newest=True)

    # PUT THE MAPPING DICTIONARY IN THIS AREA #
    map_dict = create_template_mapping()

    # Create optional configuration list
    regtmplopt_list = []
    opt_tmpl_list = line_list(template_all_opt)
    # Loop over each line of the template
    if opt_tmpl_list:
        # print "Printing TLINE"
        for tline in opt_tmpl_list:
            if tline != "":
                # Correctly format the string for matching
                regtmplopt_list.append(template_str_parse(tline).strip('\n\t'))

    # Bool for determining if extra configuration was found
    extra_present = False
    all_regex_present = False
    # Check if the config_list contains content
    if config_list:
        # Loop over the configuration content
        for compline in config_list:
            matched = False
            compline = compline.strip()
            # Make sure this configuration line is not blank
            if compline != "":
                # Make sure this line of configuration is valid
                if re.match('^(set|activate|deactivate|delete)\s.*$', compline):
                    #print "-" * 50
                    #print "Test Line: {0}".format(compline)
                    # Loop over the template regex lines
                    for regline in regtmpl_list:
                        # If we find a match...
                        if re.search(regline, compline):
                            #print "Regex Match: {0}".format(regline)
                            matched = True
                            # Remove the matched element from the list
                            regtmpl_list.remove(regline)
                            break
                    #print "-" * 50
            # If we didn't find a match for this config line in the regex, this is extra configuration...
            if not matched:
                opt_matched = False
                # Check if this line matches the optional configuration template
                #########################
                for optline in regtmplopt_list:
                    if re.search(optline, compline):
                        #print "Omitting Config: {0}".format(compline)
                        opt_matched = True
                        break
                if not opt_matched:
                    #print "Extra Config: {0}".format(compline)
                    results.append("(+) " + compline)
                    extra_present = True
        #print "Regtmpl_list: {0}".format(regtmpl_list)
        # If there are regex configuration left in the list...
        if regtmpl_list:
            # Loop over the remaining regex commands to create the missing list
            for regline_matched in regtmpl_list:
                nice_output = ""
                nomatch = False
                first_pass = True
                for key, value in map_dict.iteritems():
                    if value in regline_matched:
                        if first_pass:
                            nice_output = regline_matched
                        # print "Key: {0} | Value: {1}".format(key, value)
                        nice_output = nice_output.replace(value, "{{" + key + "}}")
                        # print "NEW OUTPUT: {0}".format(nice_output)
                        first_pass = False
                if first_pass:
                    regline_matched = clear_extra_escapes(regline_matched)
                    results.append("(-) " + regline_matched)
                else:
                    nice_output = clear_extra_escapes(nice_output)
                    results.append("(-) " + nice_output)
        # If this executes, all template commands are in the config
        else:
            all_regex_present = True

    # If check is successful..
    if not extra_present and all_regex_present:
        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: No Missing Regex Configuration" + "\n")
        returncode = 1
    elif extra_present and all_regex_present:
        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: No Missing Regex Configuration, Additional Configuration Present" + "\n")
        returncode = 2
    elif not extra_present:
        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: Missing Regex Configuration, No Additional Configuration" + "\n")
        returncode = 3
    elif extra_present:
        stdout.write(record['hostname'] + " (" + record['ip'] + ") | Template Check: Missing Regex Configuration, Additional Configuration Present" + "\n")
        returncode = 4

    # Return the results
    results.append(returncode)
    return results

# This function scans the string and
def template_str_parse(str):
    tline = ""
    openbracket = False
    closebracket = False
    onvar = False
    varstr = ""
    textstr = ""
    # Put the template regex into a dictionary
    map_dict = create_template_mapping()
    # Loop over each character in the string
    for char in str:
        # If this character is an open bracket
        if char == "{":
            if openbracket:
                onvar = True
                openbracket = False
            else:
                openbracket = True
                # Add any standard text (escaped)
                tline += re.escape(textstr)
                # Clear the textstr
                textstr = ""
        # If this character is a close bracket
        elif char == "}":
            if closebracket:
                onvar = False
                closebracket = False
            else:
                closebracket = True
                # Add the corresponding regex expression
                tline += map_dict[varstr]
                # Clear the varstr
                varstr = ""
        # If this character if part of a regex variable
        elif onvar:
            # Append this character to the variable string
            varstr += char
        # If this character is a regular character
        else:
            # Append this character to the text string
            textstr += char

    # Add any remaining text, might happen if string ends on a close bracket
    tline += re.escape(textstr)
    #print "TLINE:{0}".format(tline)
    return tline

def template_regex(model, is_mdf):
    """ Purpose: Creates the template regex using the template file and regex mapping document.
    :param: None
    :return regtmpl_list: A list containing regexs for template scanner. 
    """
    regtmpl_list = []
    templ_list = line_list(template_all)
    # Generate generic template content
    # Loop over each line of the template
    if templ_list:
        #print "Printing TLINE"
        for tline in templ_list:
            if tline != "":
                # Correctly format the string for matching
                regtmpl_list.append(template_str_parse(tline).strip('\n\t'))

    # Check for specific switch ELS type
    addl_list = []
    if "EX4300" in model:
        addl_list = line_list(template_els)
    # Otherwise, it is non-ELS
    else:
        addl_list = line_list(template_nonels)

    # If OSPF configuration is present
    if is_mdf:
        addl_list = line_list(template_ospf)

    # Loop over each line that contains text
    for tline in addl_list:
        if tline != "":
            # Correctly format the string for matching
            regtmpl_list.append(template_str_parse(tline).strip('\n\t'))

    # Return the regex infused template list
    return regtmpl_list

def clear_extra_escapes(escaped_str):
    new_str = ''
    index = 0
    slash_match = False
    # Fixes the "double slashes" and captures the index of "single slashes"
    for character in escaped_str:
        if character == "\\":
            if slash_match:
                slash_match = False
                new_str += character
            else:
                slash_match = True
                # Skip this character
        elif slash_match:
            slash_match = False
            new_str += character
        else:
            new_str += character
        index += 1
    return new_str

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
    stdout.write("\n| {0} of {1} | Adding... {2}  | ".format(curr_num, total_num, ip))
    sys.stdout.flush()
    if not get_record(listDict, ip):
        # Try connecting to this device
        dev = connect(ip, indbase=False, probe=10)
        # If we can connect...
        if dev:
            # Check for hostname/serial number match
            if not check_host_sn(ip, dev):
                #print "\t-  Trying to add {0}...".format(ip)
                if add_record(ip, dev):
                    stdout.write("Added Successfully!")
                    message = "Successfully added to database."
                    contentList = [ip, message, get_now_time()]
                    new_devices_list.append(dict(zip(standard_key_list, contentList)))
                # If "add" fails
                else:
                    stdout.write("Add Failed!")
            # Check matches an existing hostname or S/N...
            else:
                stdout.write("Added to an existing device!")
                message = "Adding IP to existing device in database."
                contentList = [ip, message, get_now_time()]
                new_devices_list.append(dict(zip(standard_key_list, contentList)))
    else:
        print "Skipping device, already in database"
    sys.stdout.flush()

def add_record(ip, dev):
    """ Purpose: Adds a record to list of dictionaries.

    :param ip:          -   The IP of the device
    :param dev:         -   The PyEZ connection object (SSH Netconf)
    :return:            -   Returns True/False
    """
    mydict = {}
    # Try to gather facts from device
    try:
        # Try to capture general device parameters
        for key in facts_list:
            if key == 'vc':
                mydict[key] = get_vc_fact(dev)
            else:
                fact = dev.facts[key]
                if fact is None:
                    message = "Add Failed - Unable to get critical parameter [" + key + "]"
                    contentList = [ip, message, get_now_time()]
                    new_devices_list.append(dict(zip(standard_key_list, contentList)))
                    return False
                    #mydict[key]
                else:
                    mydict[key] = fact.upper()
    except Exception as err:
        message = "Add Failed - Error accessing facts on device. ERROR:{0}".format(err)
        contentList = [ip, message, get_now_time()]
        new_devices_list.append(dict(zip(standard_key_list, contentList)))
        return False
    else:
        now = get_now_time()
        mydict['last_inet_check'] = now
        # Try to gather inet interface parameters
        inet_info = get_inet_interfaces(ip, dev)
        #print "------------ INET INFO ---------------"
        #pp = pprint.PrettyPrinter(indent=4)
        #pp.pprint(inet_info)

        # Define all the record data
        if inet_info:
            mydict['inet_intf'] = inet_info
            mydict['ip'] = mydict['inet_intf'][0]['ipaddr']
            mydict['last_inet_change'] = now
        else:
            mydict['ip'] = ip
            mydict['last_inet_change'] = "UNDEFINED"

        # Set other timestamp params
        mydict['last_config_check'] = "UNDEFINED"
        mydict['last_config_change'] = "UNDEFINED"
        mydict['last_access_attempt'] = now
        mydict['last_access_success'] = now
        mydict['last_param_change'] = now
        mydict['last_param_check'] = now
        mydict['last_temp_check'] = "UNDEFINED"
        mydict['last_temp_refresh'] = "UNDEFINED"

        # Add entire record to database
        mydict['add_date'] = now
        listDict.append(mydict)
        return True

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

def delete_record_key(ip, key):
    """ Purpose: Delete an existing key/value pair, based on key value. Record is a dictionary.

    :param ip:          -   IP of the device
    :param key:         -   Key of the attribute
    :return:            -   True/False
    """
    for myrecord in listDict:
        # If we've found the correct record...
        if myrecord['ip'] == ip:
            try:
                # Trying to update the record...
                del myrecord[key]
            except Exception as err:
                # Error checking...
                print "ERROR: Unable to delete key '{0}' : {1} | Device: {2}".format(key, err, ip)
                return False
            # If the record change was successful...
            else:
                print "Successfully deleted key '{0}'".format(key)
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
        stdout.write("Problem collecting facts from device. ERROR: {0}".format(err))
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
                print "Check Host SN function"
                if change_record(record['ip'], inet_intf, 'inet_intf') and change_record(record['ip'], man_ip, 'ip'):
                    return True
                else:
                    return False
        # No records matched
        return False

def explode_masked_list(iplist):
    """ Purpose: Extracts masked IPs from list and adds to a new list with individual IPs.
    
    :param iplist: 
    :return exploded_list: 
    """
    exploded_list = []

    for raw_ip in iplist:
        myip = raw_ip.strip()
        if '/' in myip:
            for ip in IPNetwork(myip):
                #print "From {0} -> Adding {1}".format(myip, str(ip))
                exploded_list.append(str(ip))
        elif myip:
            #print "Adding {0}".format(myip)
            exploded_list.append(myip)
    return exploded_list

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
        exploded_list = explode_masked_list(ip_list)
        total_num = len(exploded_list)
        curr_num = 0
        for myip in exploded_list:
            curr_num += 1
            add_new_device(myip, total_num, curr_num)
        stdout.write("\n\n")
        sys.stdout.flush()
    else:
        print "IP List is empty!"

def check_loop(subsetlist):
    """ Purpose: Checks if the subset parameter was set and decide what to execute. Adds device if it is not in the 
    database. Executes a standard check of the entire database if subset is not defined.

    :param record: A list containing IP addresses to query.
    :return: None
    """
    # Create a single change log for all changes
    now = get_now_time()
    if addl_opt == "config" or "param" or "inet" or "all":
        chg_log_name = "Change_Log~" + now + "~.log"
        chg_log = os.path.join(log_dir, chg_log_name)

    # Begin processing all the devices
    curr_num = 0
    print "\nDevice Processsing Begins: {0}".format(get_now_time())
    print "=" * 80
    # Check if the subsetlist is defined
    #try:
    if subsetlist:
        temp_list = []
        # Get the total number of IP addresses
        for ip_addr in line_list(os.path.join(iplist_dir, subsetlist)):
            raw_ip = ip_addr.strip()
            temp_list.append(raw_ip)
        # Total number of IPs in this list
        total_num = len(temp_list)

        # Loop over the ip addresses provided
        for ip in temp_list:
            # Increase count by 1...
            curr_num += 1
            record = get_record(listDict, ip)
            # Checks if the specified IP is NOT defined in the list of dictionaries.
            if not record:
                #print "\n" + "-" * 80
                #print subHeading(ip, 15)
                add_new_device(ip, total_num, curr_num)
                record = get_record(listDict, ip)
                if record:
                    check_main(record, chg_log, total_num, curr_num)
            # If the IP IS present, execute this...
            else:
               check_main(record, chg_log, total_num, curr_num)


    # Check the entire database
    else:
        # Record (ip, etc)
        total_num = len(listDict)
        for record in listDict:
            curr_num += 1
            check_main(record, chg_log, total_num, curr_num)

    #except KeyboardInterrupt:
    #    print "\n --- Process has been interrupted ---"
    #except Exception as err:
    #    print "\n --- An ERROR has been encountered: {0} ---".format(err)
    # End of processing
    print "\n\n" + "=" * 80
    print "Device Processsing Ends: {0}\n\n".format(get_now_time())

# Update a record inside a list dictionary
def update_ld(key, value, ip):
    for record in listDict:
        if record['ip'] == ip:
            print "BEFORE:"
            print record
            record.update({key, value})
            print "AFTER:"
            print record

# Performs the selected checks and logs the results
def check_main(record, chg_log="deflog.log", total_num=1, curr_num=1):
    """ Purpose: Performs the selected checks (Parameter/Config, Template, or All)
        
    :param record: A dictionary containing the device information from main_db.
    :param total_num: Total number of devices in the current loop.
    :param curr_num: The number of the current device.
    :return: None
    """
    # Make sure that a folder exists for this site
    directory_check(record)

    # Print out the device and count information
    stdout.write("\n" + "| " + str(curr_num) + " of " + str(total_num) + " | ")
    sys.stdout.flush()
    # Update the 'last_access_attempt'
    record.update({'last_access_attempt': get_now_time()})
    # Try to connect to the device
    dev = connect(record['ip'], hostname=record['hostname'], indbase=True)

    # If the connection was successfull, start checking device
    if dev:
        record.update({'last_access_success': get_now_time()})
        stdout.write("Checking: ")
        sys.stdout.flush()
        if addl_opt == "all":
            stdout.write("Param|Config|Inet|Template | ")
            sys.stdout.flush()
            param_check(record, chg_log, dev)
            config_check(record, chg_log, dev)
            inet_check(record, chg_log, dev)
            template_check(record)
        else:
            # Print the selected checks
            if run_param: stdout.write("| Param |")
            if run_config: stdout.write("| Config |")
            if run_inet: stdout.write("| Inet |")
            if run_template: stdout.write("| Template |\n")
            sys.stdout.flush()

            # Run the selected checks
            if run_param: param_check(record, chg_log, dev)
            # Running Config Check
            if run_config: config_check(record, chg_log, dev)
            # Running Inet Check
            if run_inet: inet_check(record, chg_log, dev)
            # Running Template Check
            if run_template: template_check(record, True)
        try:
            dev.close()
        except:
            print "Caught dev.close() exception"
            pass
    # If connection was not successful, check how long system has been unreachable to see if we need to remove this one
    else:
        tmp_chk = record['last_temp_check']
        acc_suc = record['last_access_success']
        #stdout.write("\nAccess_Success: {0} | Temp_Check: {1} | ".format(acc_suc, tmp_chk))
        # If the last_success is not known, check another
        if acc_suc == 'UNDEFINED':
            # If last_temp_check is also not known, remove this record
            if tmp_chk == 'UNDEFINED':
                #print "Both timestamps are Undefined"
                remove_record(listDict, 'ip', record['ip'], config_dir)
            else:
                # Check if this device hasn't been reached for a month, using last_temp_check timestamp
                day_diffs = day_difference(record['last_temp_check'])
                if day_diffs > 30:
                    #print "Access_Success is UNDEF, Temp_Check diff is GT 30: {0}".format(day_diffs)
                    remove_record(listDict, 'ip', record['ip'], config_dir)
                    #print "Record Removed!"
                #else:
                #    print "Access_Success is UNDEF, Temp_Check diff is LT 30: {0}".format(day_diffs)
        # If this record has a valid success
        else:
            # Check if this device hasn't been reached for a month, using last_access_success timestamp
            day_diffs = day_difference(record['last_access_success'])
            if day_diffs > 30:
                #print "Access_Success diff is GT 30: {0}".format(day_diffs)
                remove_record(listDict, 'ip', record['ip'], config_dir)
                #print "Record Removed!"
            #else:
            #    print "Access_Success diff is LT 30: {0}".format(day_diffs)

def main(argv):
    """ Purpose: Capture command line arguments and populate variables.
        Arguments:
            -c    -  (Required) The CSV file containing credentials to be used to access devices.
            -s    -  (Optional) The TEXT file that contains a list of device IPs to scan.
            -o    -  (Optional) Run one of the following options.
                        - "config" will run the Param and Config Check Function
                        - "template" will run the Template Scan Function of existing devices
                        - "all" will run both of the above functions
            -i    -  (Optional) A TEXT file containing a list of ip addresses to add to the database.
    """
    global credsCSV
    global iplistfile
    global subsetlist
    global detail_ip
    global run_param
    global run_config
    global run_inet
    global run_template
    # Set these params as not set, by default
    run_param = False
    run_config = False
    run_inet = False
    run_template = False

    try:
        opts, args = getopt.getopt(argv, "hl:a:s:pcitA",["login=","ipadd=","subset="])
    except getopt.GetoptError:
        print "device_refresh -l <loginfile> -s <subsetlist> -a <ipaddfile> -p -c -i -t -A"
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'SYNTAX: device_refresh -l <loginfile> -s <subsetlist> -a <iplistfile> -p -c -i -t -A'
            print '  -l : (REQUIRED) A CSV file in the root of the jmanage folder. It contains the username or hashid and password.'
            print '  -s : (OPTIONAL) A TXT file in the "iplists" directory that contains a list of IP addresses to scan.'
            print '  -a : (OPTIONAL) A TXT file in the "iplists" directory that contains a list of IPs to add to the database.'
            print '  -p : (OPTIONAL) Run the parameter check.'
            print '  -c : (OPTIONAL) Run the configuration check.'
            print '  -i : (OPTIONAL) Run the inet check.'
            print '  -t : (OPTIONAL) Run the template scan.'
            print '  -A : (OPTIONAL) Run all the scans'
            sys.exit()
        elif opt in ("-l", "--login"):
            credsCSV = arg
        elif opt in ("-s", "--subset"):
            subsetlist = arg
        elif opt in ("-a", "--ipadd"):
            iplistfile = arg
        elif opt in ("-p", "--param"):
            run_param = True
        elif opt in ("-c", "--config"):
            run_config = True
        elif opt in ("-i", "--inet"):
            run_inet = True
        elif opt in ("-t", "--template"):
            run_template = True
        elif opt in ("-A", "--all"):
            run_param = True
            run_config = True
            run_inet = True
            run_template = True

    print "Credentials file is: {0}".format(credsCSV)
    print "IP List file is: {0}".format(iplistfile)
    print "Subset List File is: {0}".format(subsetlist)
    if run_param: print "Param Flag is set."
    if run_config: print "Config Flag is set."
    if run_inet: print "Inet Flag is set."
    if run_template: print "Template Flag is set."

# Main execution loop
if __name__ == "__main__":
    # Detect if this system is Windows or Linux/MAC
    detect_env()
    # Capture arguments
    main(sys.argv[1:])

    # Assign arguments
    if credsCSV:
        myfile = os.path.join(dir_path, credsCSV)
        creds = csv_to_dict(myfile)
        myuser = creds['username']
        mypwd = creds['password']
        alt_myuser = creds['alt_username']
        alt_mypwd = creds['alt_password']
    else:
        print "Error: No CSV credentials file specified!"
        exit()

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
        if run_param or run_config or run_inet or run_template:
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
        exit()