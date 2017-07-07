__copyright__ = "Copyright 2016 Tyler Jordan"
__version__ = "0.1.1"
__email__ = "tjordan@juniper.net"

import datetime
import platform
import json
import os

from jnpr.junos import *
from jnpr.junos.exception import *
from netaddr import *
from utility import *

from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors
from prettytable import PrettyTable
from os import path
from operator import itemgetter

# Paths
iplist_dir = ''
config_dir = ''
log_dir = ''
template_dir = ''
dir_path = ''

# Files
main_list_dict = ''
intf_list_dict = ''
template_file = ''
template_csv = ''

# Params
listDict = []
mypwd = ''
myuser = ''
port = 22

# Key Lists
dbase_order = [ 'hostname', 'ip', 'version', 'model', 'serialnumber', 'last_access', 'last_config_check',
                'last_config_change', 'last_param_check', 'last_param_change', 'last_inet_check', 'last_inet_change',
                'last_temp_check', 'add_date']
facts_list = [ 'hostname', 'serialnumber', 'model', 'version' ]

def detect_env():
    """ Purpose: Detect OS and create appropriate path variables
    :param: None
    :return: None
    """
    global iplist_dir
    global config_dir
    global template_dir
    global log_dir
    global dir_path
    global template_file
    global template_csv

    global main_list_dict
    global intf_list_dict

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

def information(connection, ip, software_info, hostname):
    """ Purpose: This is the function called when using -info. It is grabs the model, running version, 
    and serial number of the device.

    :param connection:      -   This is the ncclient manager connection to the remote device.
    :param ip:              -   String containing the IP of the remote device, used for logging purposes.
    :param software_info:   -   A "show version" aka "get-software-information".
    :param hostname:        -   The device host-name for output purposes.
    :return:                -   Dictionary of requested output
    """
    try:
        model = software_info.xpath('//software-information/product-model')[0].text
        version = (
        software_info.xpath('//software-information/package-information/comment')[0].text.split('[')[1].split(']')[0])
        chassis_inventory = connection.get_chassis_inventory(format='xml')
        serialnumber = chassis_inventory.xpath('//chassis-inventory/chassis/serial-number')[0].text
        return {'hostname': hostname, 'ip': ip, 'model': model, 'version': version, 'serialnumber': serialnumber}
    except Exception as err:
        # print '\t- ERROR: Device was reachable, the information was not found.'
        message = "Device was reachable, but unable to gather system information."
        contentList = [ip, message, str(err), get_now_time()]
        ops_error_list.append(dict(zip(error_key_list, contentList)))
        return False

def run(ip, username, password, port):
    """ Purpose: To open an NCClient manager session to the device, and run the appropriate function against the device.

    :param ip:          -   String of the IP of the device, to open the connection, and for logging purposes.
    :param username:    -   String username used to connect to the device.
    :param password:    -   String password used to connect to the device.
    :param port:        -   Integer port number of SSH (830)
    :return output:     -   Returns device parameters
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
    except Exception as err:
        print '\t- ERROR: Unable to connect using NCCLIENT. ERROR: {0}'.format(err)
        message = "Unable to connect using NCCLIENT."
        contentList = [ip, message, str(err), get_now_time()]
        access_error_list.append(dict(zip(error_key_list, contentList)))
        return False
    else:
        try:
            software_info = connection.get_software_information(format='xml')
        except Exception as err:
            message = "Unable to get software information."
            contentList = [ip, message, str(err).strip('\b\r\n'), get_now_time()]
            ops_error_list.append(dict(zip(error_key_list, contentList)))
            return False
        # Collect information from device
        hostname = software_info.xpath('//software-information/host-name')[0].text
        output = information(connection, ip, software_info, hostname)

        # Close the session
        connection.close_session()

        # Determine what to return
        if not output:
            return False
        return output

def search_dict_multi(search_dict):
    """ Purpose: Searches the main record dictionary based on defined criteria.
        Returns: A filtered list dictionary of records
    """
    filtered_list_dict = []

    for d in listDict:
        bad_match = False
        for s_key, s_val in search_dict.iteritems():
            #print "Key: {0} | Search Val: {1} | DB Val: {2} ".format(s_key, s_val, d[s_key])
            if s_val.upper() not in d[s_key]:
                bad_match = True
        if not bad_match:
            filtered_list_dict.append(d)

    return filtered_list_dict

def search_menu():
    """ Purpose: Determine what user wants to search on.
        Return: Search criteria
    """
    myoptions = ['Alphabetical', "Reverse"]
    search_key = "placeholder"
    search_dict = {}

    while search_key:
        print "*" * 25
        search_key = getOptionAnswer("What key would you like to search for", dbase_order)
        if search_key:
            print "*" * 25
            search_val = getInputAnswer("What value for \"" + search_key + "\" would you like to search for")
            search_dict[search_key] = search_val
    print "*" * 25
    search_sort_on = getOptionAnswer("What would you like to sort the results on", dbase_order)
    print "*" * 25
    search_sort_type = getOptionAnswer("How would you like to sort", myoptions)

    # First filter the database based on search criteria
    filtered_list_dict = search_dict_multi(search_dict)

    # Now sort the filtered list dict
    sort_type = False
    if search_sort_type == 'Reverse': sort_type = True
    print "Displaying Sorted Table:"
    show_devices(sorted(filtered_list_dict, key=itemgetter(search_sort_on), reverse=sort_type))

def show_devices(list_dict):
    """ Purpose: Display a table showing devices with general facts.
        Returns: Nothing
    """
    t = PrettyTable(['Management IP', 'Hostname', 'Model', 'Current Code', 'Serial Number', 'Last Access',
                     'Last Config Change', 'Last Parameter Change', 'Last Inet Change', 'Add Date'])
    for device in list_dict:
        t.add_row([device['ip'], device['hostname'], device['model'], device['version'], device['serialnumber'],
                   device['last_access'], device['last_config_change'], device['last_param_change'],
                   device['last_inet_change'], device['add_date']])
    print t

def delete_menu():
    """ Purpose: Menu for selecting a record to delete.
        Returns: T/F
    """
    search_key = "placeholder"
    search_dict = {}

    while search_key:
        print "*" * 25
        search_key = getOptionAnswer("What key would you like to delete on", dbase_order)
        if search_key:
            print "*" * 25
            search_val = getInputAnswer("What value for \"" + search_key + "\" would you like to delete on")
            search_dict[search_key] = search_val

    # Filter the database based on search criteria and sort
    sorted_list_dict = sorted(search_dict_multi(search_dict), key=itemgetter('ip'), reverse=False)

    # Show the table of devices
    show_devices(sorted_list_dict)

    # Get list of IPs from sorted list as selection criteria
    host_list = []
    for device in sorted_list_dict:
        host_list.append(device['hostname'])

    # Ask question to get answers and delete valid answers
    if host_list:
        host_answer_list = getOptionMultiAnswer("Which devices would you like to delete", host_list)
        if host_answer_list:
            for hostname in host_answer_list:
                if remove_record(listDict, 'hostname', hostname):
                    print "Removed: {0}".format(hostname)
                else:
                    print "Removal Failed: {0}".format(hostname)
            # csv_write_sort(listDict, main_list_dict, sort_column=0, column_names=dbase_order)
            stdout.write("Applying database changes (" + main_list_dict + "): ")
            if write_to_json(listDict, main_list_dict):
                print "Successful!"
            else:
                print "Failed!"
    else:
        print "No hosts in the defined criteria!"

def display_device_info(search_str):
    """ Purpose: Display a devices info to the screen

    :param ip:          -   The IP of the device
    :param dev:         -   The PyEZ connection object (SSH Netconf)
    :return:            -   True/False
    """
    if re.match(r'[S|s][W|w]?[a-zA-Z]{3}.*', search_str):
        print "Trying Host: {0}".format(search_str.upper())
        myrecord = get_record(listDict, hostname=search_str.upper())
    else:
        print "Trying IP: {0}".format(search_str)
        myrecord = get_record(listDict, ip=search_str)

    if myrecord:
        print subHeading(myrecord['hostname'] + " - (" + search_str + ")", 15)
        print "Hostname.............{0}".format(myrecord['hostname'])
        print "Management IP........{0}".format(myrecord['ip'])
        print "Model................{0}".format(myrecord['model'])
        print "Version..............{0}".format(myrecord['version'])
        print "S/N..................{0}".format(myrecord['serialnumber'])
        print "Last Access..........{0}".format(myrecord['last_access'])
        print "Last Config Change...{0}".format(myrecord['last_config_change'])
        print "Last Config Check....{0}".format(myrecord['last_config_check'])
        print "Last Param Change....{0}".format(myrecord['last_param_change'])
        print "Last Param Check.....{0}".format(myrecord['last_param_check'])
        print "Last Inet Change.....{0}".format(myrecord['last_inet_change'])
        print "Last Inet Check......{0}".format(myrecord['last_inet_check'])
        print "Add Date.............{0}".format(myrecord['add_date'])

        t = PrettyTable(['Interface', 'IP', 'Mask', 'Status', 'Last Updated'])
        if 'inet_intf' in myrecord:
            for my_intf in myrecord['inet_intf']:
                t.add_row([my_intf['interface'], my_intf['ipaddr'], my_intf['ipmask'], my_intf['status'], my_intf['updated']])
            print t
            #pp = pprint.PrettyPrinter(indent=4)
            #pp.pprint(myrecord)
            return True
        else:
            print "\n- Inet Interface Info not available -\n"
    else:
        print "No record found for:{0}".format(search_str)
        return False

# START OF SCRIPT #
if __name__ == '__main__':
    try:
        detect_env()
    except Exception as err:
        print "Problem detecting OS type..."
        quit()
    else:
        # Credentials
        myfile = os.path.join(dir_path, 'pass.csv')
        creds = csv_to_dict(myfile)
        myuser = creds['username']
        mypwd = creds['password']
        print "User: {0} | Pass: {1}".format(myuser, mypwd)

        # Load Main Database
        listDict = json_to_listdict(main_list_dict)

        # Main Program Loop
        my_options = ['Display Database', 'Search Database', 'Display Device', 'Delete Record', 'Quit']
        while True:
            print "\n" + "*" * 25
            print "Total Records: {0}".format(len(listDict))
            print "*" * 25
            answer = getOptionAnswerIndex('Choose your poison', my_options)
            print "\n" + "*" * 25
            if answer == "1":
                print "Run -> Display Database"
                show_devices(listDict)
            elif answer == "2":
                print "Run -> Search Database"
                search_menu()
            elif answer == "3":
                if listDict:
                    loop = True
                    while (loop):
                        answer = getInputAnswer("Device IP or Hostname('Q' to quit)")
                        if answer == 'q' or answer == 'Q':
                            loop = False
                        else:
                            display_device_info(answer)
                else:
                    print "No Records in Database!"
            elif answer == "4":
                print "Run -> Delete Record"
                delete_menu()
            elif answer == "5":
                print "Goodbye!"
                quit()
            else:
                quit()
