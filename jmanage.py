__copyright__ = "Copyright 2018 Tyler Jordan"
__version__ = "0.1.1"
__email__ = "tjordan@juniper.net"

import datetime
import platform
import json
import os
import netaddr
import jxmlease

from jnpr.junos import *
from jnpr.junos.exception import *
from utility import *

from ncclient import manager  # https://github.com/ncclient/ncclient
from ncclient.transport import errors
from prettytable import PrettyTable
from pprint import pprint
from os import path
from operator import itemgetter
from netaddr import IPAddress, IPNetwork

# Paths
iplist_dir = ''
config_dir = ''
log_dir = ''
template_dir = ''
temps_dir = ''
dir_path = ''
csvs_dir = ''

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
dbase_order = [ 'hostname', 'ip', 'vc', 'version', 'model', 'serialnumber', 'last_access_attempt',
                'last_access_success', 'last_config_check', 'last_config_change', 'last_param_check',
                'last_param_change', 'last_inet_check', 'last_inet_change', 'last_temp_check', 'last_temp_refresh',
                'add_date']
facts_list = [ 'hostname', 'serialnumber', 'model', 'version' ]

def detect_env():
    """ Purpose: Detect OS and create appropriate path variables
    :param: None
    :return: None
    """
    global iplist_dir
    global config_dir
    global template_dir
    global temps_dir
    global maps_dir
    global log_dir
    global csvs_dir
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
        temps_dir = os.path.join(dir_path, "data\\templates\\deviation_templates")
        maps_dir = os.path.join(dir_path, "data\\templates\\maps")
        log_dir = os.path.join(dir_path, "data\\logs")
        csvs_dir = os.path.join(dir_path, "data\\templates\\csvs")

    else:
        #print "Environment Linux/MAC!"
        iplist_dir = os.path.join(dir_path, "data/iplists")
        config_dir = os.path.join(dir_path, "data/configs")
        template_dir = os.path.join(dir_path, "data/templates")
        temps_dir = os.path.join(dir_path, "data/templates/deviation_templates")
        maps_dir = os.path.join(dir_path, "data/templates/maps")
        log_dir = os.path.join(dir_path, "data/logs")
        csvs_dir = os.path.join(dir_path, "data/templates/csvs")

    # Statically defined files and logs
    main_list_dict = os.path.join(dir_path, "main_db.json")
    intf_list_dict = os.path.join(dir_path, "intf_db.csv")
    template_csv = os.path.join(dir_path, template_dir, "Template_Regex.csv")
    template_file = os.path.join(dir_path, template_dir, "Template.conf")

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
    first_pass = True
    add_search = 'N'
    search_dict = {}

    while first_pass or add_search:
        print "*" * 25
        search_key = getOptionAnswer("What key would you like to search for", dbase_order)
        #print "Search Key: {0}".format(search_key)
        if search_key == "Quit":
            #print "False!"
            return False
        elif search_key:
            print "*" * 25
            search_val = getInputAnswer("What value for \"" + search_key + "\" would you like to search for")
            search_dict[search_key] = search_val
        first_pass = False
        add_search = getTFAnswer("Add another key to search for")

    print "*" * 25
    search_sort_on = getOptionAnswer("What would you like to sort the results on", dbase_order)
    if search_sort_on == "Quit":
        return False

    print "*" * 25
    search_sort_type = getOptionAnswer("How would you like to sort", myoptions)
    if search_sort_type == "Quit":
        return False

    # First filter the database based on search criteria
    filtered_list_dict = search_dict_multi(search_dict)

    # Now sort the filtered list dict
    sort_type = False
    if search_sort_type == 'Reverse': sort_type = True
    print "Displaying Sorted Table:"
    show_devices(sorted(filtered_list_dict, key=itemgetter(search_sort_on), reverse=sort_type))

def pyez_connect(ip):
    dev = Device(host=ip, passwd=mypwd, user=myuser)
    try:
        dev.open()
    except Exception as err:
        stdout.write("Error connecting using PyEZ: {0}".format(err))
        return False
    else:
        return dev

# Returns an interface name if MAC is found, empty string if not
def find_mac_return_intf(dev, mac_addr, vlan_tag):
    interface = ""
    ethsw_response = jxmlease.parse_etree(dev.rpc.get_ethernet_switching_table_information())
    for myethtable in ethsw_response['l2ng-l2ald-rtb-macdb']['l2ng-l2ald-mac-entry-vlan']:
        if myethtable['l2ng-l2-vlan-id'].encode('utf-8') == vlan_tag:
            for mymacentry in myethtable['l2ng-mac-entry']:
                #print "mymacentry:{0}".format(mymacentry['l2ng-l2-mac-address'].encode('utf-8'))
                #print "MAC:{0}".format(mac_addr)
                if mymacentry['l2ng-l2-mac-address'].encode('utf-8') == mac_addr:
                    #print "\t\tMAC: {0}".format(mymacentry['l2ng-l2-mac-address'].encode('utf-8'))
                    #print "\t\tINTF: {0}".format(mymacentry['l2ng-l2-mac-logical-interface'].encode('utf-8'))
                    return mymacentry['l2ng-l2-mac-logical-interface'].encode('utf-8')
    return interface

def ip_search_menu(list_dict):
    """ 
        Purpose: Identifies exact location of a single IP address
        Returns: Nothing
    """
    #lldp_response = jxmlease.parse_etree(dev.rpc.get_lldp_neighbors_information())

    user_input = getInputAnswer("What IP would you like to locate")
    if netaddr.valid_ipv4(user_input):
        #print "{0} is a valid IP!".format(user_input)
        #stdout.write("Checking Database For Network...")
        match_found = False
        print "Looking for ... {0}".format(user_input)
        for device in list_dict:
            is_target = False
            stdout.write(".")
            if 'inet_intf' in device:
                # Loop over route points on this device, checking for matching network
                for my_intf in device['inet_intf']:
                    if IPAddress(user_input) in IPNetwork(my_intf['ipaddr'] + '/' + my_intf['ipmask']):
                        print "\nFound Possible Match:"
                        print "\tDevice: ............ {0} ({1})".format(device['hostname'], device['ip'])
                        print "\tTarget IP: ......... {0}".format(user_input)
                        print "\tMatched IP: ........ {0}".format(my_intf['ipaddr'] + '/' + my_intf['ipmask'])
                        is_target = True
                        # Break out of this loop
                        break
                # If we found a device with a network match...
                if is_target:
                    # Connect to device
                    dev = pyez_connect(device['ip'])
                    # If I can connect to the device...
                    if dev:

                        # Device Variables
                        mac_addr = ''
                        intf_name = ''

                        # Collect ARP information from the route-point for target IP
                        arp_response = jxmlease.parse_etree(dev.rpc.get_arp_table_information())
                        # Loop over ARP data to find a match
                        is_match = False
                        for myarp in arp_response['arp-table-information']['arp-table-entry']:
                            # Loop over ARP entries and check for target IP
                            if myarp['ip-address'].encode('utf-8') == user_input:
                                intf_name = myarp['interface-name'].encode('utf-8')
                                mac_addr = myarp['mac-address'].encode('utf-8')
                                print "\n\tExact ARP Record Found!"
                                print "\t\tARP IP: ........... {0}".format(myarp['ip-address'].encode('utf-8'))
                                print "\t\tARP Mac Address: .. {0}".format(mac_addr)
                                print "\t\tARP Interface: .... {0}".format(intf_name)
                                is_match = True
                                # Get out of loop after we find an exact match
                                break
                        # If we got an exact match...
                        if is_match:
                            # If the interface is a VLAN or IRB, ie. vlan.XXX, then user port is on a different switch
                            if 'vlan' in intf_name or 'irb' in intf_name:
                                print "\n\tPhysical Interface is on a downstream switch."
                                intf_list = []
                                vlan_tag = intf_name.rsplit('.',1)[1]
                                #print "VLAN Tag: {0}".format(vlan_tag)

                                # Get VLAN information to determine the possible interfaces this IP could exist on
                                vlan_response = jxmlease.parse_etree(dev.rpc.get_vlan_information())
                                # If the device is a NON-ELS switch (EX4550,EX4200,EX6200)
                                if 'vlan' in intf_name:
                                    for myvlan in vlan_response['vlan-information']['vlan']:
                                        if myvlan['vlan-tag'] == vlan_tag:
                                            for vlan_intf in myvlan['vlan-detail']['vlan-member-list']['vlan-member']:
                                                if "*" in vlan_intf['vlan-member-interface']:
                                                    myintf = vlan_intf['vlan-member-interface'].encode('utf-8').rsplit('*',1)[0]
                                                    #print "VLAN INTERFACE: {0}".format(myintf)
                                                    intf_list.append(myintf)
                                # If the device is an ELS switch (EX4300)
                                else:
                                    for myvlan in vlan_response['l2ng-l2ald-vlan-instance-information']['l2ng-l2ald-vlan-instance-group']:
                                        if myvlan['l2ng-l2rtb-vlan-tag'] == vlan_tag:
                                            for vlan_intf in myvlan['l2ng-l2rtb-vlan-member']:
                                                if "*" in vlan_intf['l2ng-l2rtb-vlan-member-interface']:
                                                    myintf = vlan_intf['l2ng-l2rtb-vlan-member-interface'].encode('utf-8').rsplit('*',1)[0]
                                                    #print "VLAN INTEFACE: {0}".format(myintf)
                                                    intf_list.append(myintf)

                                # Use LLDP info to get possible hosts
                                lldp_response = jxmlease.parse_etree(dev.rpc.get_lldp_neighbors_information())
                                poss_hosts = []
                                for mylldp in lldp_response['lldp-neighbors-information'][
                                    'lldp-neighbor-information']:
                                    for myintf in intf_list:
                                        if myintf == mylldp['lldp-local-interface'].encode(
                                                'utf-8') or myintf == mylldp[
                                            'lldp-local-parent-interface-name'].encode('utf-8'):
                                            host_name = mylldp['lldp-remote-system-name'].encode(
                                                'utf-8')
                                            if host_name not in poss_hosts:
                                                poss_hosts.append(host_name)
                                                break
                                print "\tPossible Switches: {0}".format(poss_hosts)

                                # Search downstream devices for MAC
                                for host_name in poss_hosts:
                                    host_record = get_record(list_dict, hostname=host_name)
                                    stdout.write("\n\tConnecting to {0}({1}) -> ".format(host_name, host_record['ip']))
                                    host_dev = pyez_connect(host_record['ip'])
                                    if host_dev:
                                        stdout.write("Connected! -> ")
                                        interface = find_mac_return_intf(host_dev, mac_addr, vlan_tag)
                                        if interface:
                                            print "Interface Located!"
                                            print "\n***** Location Of {0} *****".format(user_input)
                                            print "Device: ........ {0}({1})".format(host_name, host_record['ip'])
                                            print "MAC Address: ... {0}".format(mac_addr)
                                            print "Interface: ..... {0}".format(interface)
                                            print "VLAN: .......... {0}".format(vlan_tag)
                                            match_found = True
                                            break
                                        else:
                                            stdout.write("Not Here.")
                            # Otherwise, the interface is local, let's get the local interface
                            else:
                                print "\n\tPhysical Interface is on this switch."
                                pass
                        # If no exact match is found...
                        else:
                            print "\tNo Exact Matches in this Device!"
                    # Unable to connect to device
                    else:
                        #print "\tUnable to connect!"
                        stdout.write("C")
                        pass
                # Device without a network match
                else:
                    stdout.write("_")
                    pass
            # If 'inet_intf' info isn't in this device
            else:
                #print "Incomplete information - Skipping Device"
                stdout.write("I")
                pass
            if match_found:
                break
        # If we didn't find any matches...
        if not match_found:
            print "\nNo device found in the database with IP {0}.".format(user_input)
    else:
        print "{0} is an invalid IP!".format(user_input)
        # response = jxmlease.parse_etree(dev.rpc.get_lldp_neighbors_information())
        # Check lldp information for
        # for lldpneigh in response['lldp-neighbors-information']['lldp-neighbor-information']:

def show_devices(list_dict):
    """ 
        Purpose: Display a table showing devices with general facts.
        Returns: Nothing
    """
    t = PrettyTable(['Management IP', 'Hostname', 'Model', 'VC', 'Current Code', 'Last Access Success',
                     'Last Config Change', 'Last Parameter Change', 'Last Inet Change', 'Last Temp Check',
                     'Last Temp Refresh', 'Add Date'])
    for device in list_dict:
        #print device
        if 'last_temp_refresh' not in device:
            print "Device: {0} -> ".format(device['ip'])
        else:
            t.add_row([device['ip'], device['hostname'], device['model'], device['vc'], device['version'],
                       device['last_access_success'], device['last_config_change'], device['last_param_change'],
                       device['last_inet_change'], device['last_temp_check'], device['last_temp_refresh'],
                       device['add_date']])
    print t
    print "Device Total: {0}".format(len(list_dict))

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
        print "VC...................{0}".format(myrecord['vc'])
        print "Version..............{0}".format(myrecord['version'])
        print "S/N..................{0}".format(myrecord['serialnumber'])
        print "Last Access Attempt..{0}".format(myrecord['last_access_attempt'])
        print "Last Access Success..{0}".format(myrecord['last_access_success'])
        print "Last Config Change...{0}".format(myrecord['last_config_change'])
        print "Last Config Check....{0}".format(myrecord['last_config_check'])
        print "Last Param Change....{0}".format(myrecord['last_param_change'])
        print "Last Param Check.....{0}".format(myrecord['last_param_check'])
        print "Last Inet Change.....{0}".format(myrecord['last_inet_change'])
        print "Last Inet Check......{0}".format(myrecord['last_inet_check'])
        print "Last Temp Change.....{0}".format(myrecord['last_temp_refresh'])
        print "Last Temp Check......{0}".format(myrecord['last_temp_check'])
        print "Add Date.............{0}".format(myrecord['add_date'])

        t = PrettyTable(['Interface', 'IP', 'Mask', 'Status', 'Last Updated'])
        if 'inet_intf' in myrecord:
            for my_intf in myrecord['inet_intf']:
                t.add_row([my_intf['interface'], my_intf['ipaddr'], my_intf['ipmask'], my_intf['status'], my_intf['updated']])
            print t
            #pp = pprint.PrettyPrinter(indent=4)
            #pp.pprint(myrecord)
        else:
            print "\n- Inet Interface Info not available -\n"

        # Display all the facts
        """
        dev = Device(host=myrecord['ip'], passwd=mypwd, user=myuser)
        try:
            dev.open()
        except Exception as err:
            print "Error connecting using PyEZ: {0}".format(err)
        else:
            print "Connection Opened to {0}".format(myrecord['ip'])
            print "HOSTNAME: {0}".format(dev.facts["hostname"])
            if 'fpc1' in dev.facts['junos_info']:
                print "VC: This is a real VC"
            else:
                print "VC: This is NOT a VC"
            print "VC MODE: {0}".format(dev.facts["vc_mode"])
            pprint( dev.facts )
            dev.close()
        """
        return True

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

    # Credentials
    myfile = os.path.join(dir_path, 'pass.csv')
    creds = csv_to_dict(myfile)
    myuser = creds['username']
    mypwd = creds['password']
    print "User: {0} | Pass: {1}".format(myuser, mypwd)

    # Load Main Database
    listDict = json_to_listdict(main_list_dict)

    # Main Program Loop
    my_options = ['Display Database', 'Search Database', 'Display Device', 'IP Search', 'Delete Record', 'Quit']

    try:
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
                print "Run -> IP Search"
                ip_search_menu(listDict)
            elif answer == "5":
                print "Run -> Delete Record"
                delete_menu()
            elif answer == "6":
                print "Goodbye!"
                quit()
            else:
                quit()
    except KeyboardInterrupt:
        print 'Exiting...'
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)