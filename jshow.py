# File: jshow.py
# Author: Tyler Jordan
# Purpose: The purpose of this script is to execute commands on multiple Juniper devices. The script works in
# Windows, Linux, and Mac enviroments. This script can do bulk configuration pushes by using a CSV. When using the
# template feature, it is possible to push unique configurations to devices.
#   - execute operational commands on one or more Juniper devices
#   - execute edit commands on one or more Juniper devices
#   - execute a dynamic template on one or more Juniper devices
#   - upgrade one or more Juniper devices

import getopt
import logging
import netaddr
import platform
import sys

from jnpr.junos import Device
from jnpr.junos.utils.sw import SW
from jnpr.junos.exception import *
from ncclient.operations.errors import TimeoutExpiredError
from utility import *
from getpass import getpass
from prettytable import PrettyTable
from sys import stdout
from multiprocessing import Pool
from shutil import copyfile

# Global Variables
ssh_port = 22
username = ''
password = ''

# File Vars
main_list_dict = ''
common_content_csv = ''
specific_content_csv = ''

# Directory Vars
iplist_dir = ""
log_dir = ""
config_dir = ""
data_configs_dir = ""
config_temp_dir = ""
temp_config_dir = ""
temp_dev_dir = ""
template_dir = ""
temp_dir = ""
csv_dir = ""
inv_dir = ""
upgrade_dir = ""
images_dir = ""
system_slash = "/"   # This is the linux/mac slash format, windows format will be used in that case
remote_path = "/var/tmp"
ex_version_list = ['10.0', '10.1', '10.2', '10.3', '10.4', '11.1', '11.2', '11.3', '11.4', '12.1', '12.2', '12.3',
                   '13.1', '13.2', '13.2X50', '13.2X51', '13.2X52', '13.3', '14.1', '14.1X53', '14.2', '15.1',
                   '15.1X53', '16.1', '17.1', '17.2', '17.3']

# Function to determine running enviornment (Windows/Linux/Mac) and use correct path syntax
def detect_env():
    """ Purpose: Detect OS and create appropriate path variables. """
    global iplist_dir
    global config_dir
    global data_configs_dir
    global config_temp_dir
    global temp_config_dir
    global temp_dev_dir
    global template_dir
    global log_dir
    global csv_dir
    global inv_dir
    global upgrade_dir
    global images_dir
    global temp_dir
    global system_slash
    global ssh_port
    global dir_path

    global main_list_dict
    global specific_content_csv
    global common_content_csv

    dir_path = os.path.dirname(os.path.abspath(__file__))
    if platform.system().lower() == "windows":
        #print "Environment Windows!"
        iplist_dir = ".\\iplists\\"
        config_dir = ".\\configs\\"
        data_configs_dir = ".\\data\\configs\\"
        template_dir = ".\\data\\templates\\"
        log_dir = ".\\logs\\"
        csv_dir = ".\\csv\\"
        inv_dir = ".\\csv\\inventory\\"
        upgrade_dir = ".\\upgrade\\"
        images_dir = ".\\images\\"
        temp_dir = ".\\temp\\"
        system_slash = "\\"
    else:
        #print "Environment Linux/MAC!"
        iplist_dir = "./iplists/"
        config_dir = "./configs/"
        data_configs_dir = "./data/configs/"
        template_dir = "./data/templates/"
        log_dir = "./logs/"
        csv_dir = "./csv/"
        inv_dir = "./csv/inventory/"
        upgrade_dir = "./upgrade/"
        images_dir = "./images/"
        temp_dir = "./temp/"

    temp_dev_dir = os.path.join(dir_path, template_dir, "deviation_templates")
    temp_config_dir = os.path.join(dir_path, template_dir, "template_configs")
    config_temp_dir = os.path.join(dir_path, config_dir, "temp_dir")

    main_list_dict = os.path.join(dir_path, "main_db.json")
    common_content_csv = os.path.join(dir_path, template_dir, "common_content.csv")
    specific_content_csv = os.path.join(dir_path, template_dir, "specific_content.csv")

# Handles arguments provided at the command line
def getargs(argv):
    # Interprets and handles the command line arguments
    try:
        opts, args = getopt.getopt(argv, "hu:", ["user="])
    except getopt.GetoptError:
        print("jscan.py -u <username>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("jscan.py -u <username>")
            sys.exit()
        elif opt in ("-u", "--user"):
            return arg

# Function to exit program
def quit():
    print("Thank you for using jShow!")
    sys.exit(0)

# Create a log
def create_timestamped_log(prefix, extension):
    now = datetime.datetime.now()
    return log_dir + prefix + now.strftime("%Y%m%d-%H%M") + "." + extension

######################
# TEMPLATE FUNCTIONS #
######################
# Replaces template variables with defined terms
def template_populate(command_list, host_dict):
    new_command_list = []
    if command_list:
        # Loop over commands
        for command in command_list:
            #print("Command: {0}").format(command)
            # Remove whitespace on either side of this line
            command = command.strip()
            # Check if this is an empty line, if it is, skip it
            if not re.match(r'^\s*$', command) or re.match(r'^#.*$', command):
                # Continue searching this string for variables...
                if host_dict:
                    while re.match(r'.*\{\{.*\}\}.*', command):
                        #print "-----------------------------------------"
                        #print("String: {0}").format(command)
                        #print "-----------------------------------------"
                        matches = re.findall(r"\{\{.*?\}\}", command)
                        #print("Template Matches: {0}").format(matches)
                        for match in matches:
                            #print "Match: {0}".format(match)
                            term = match[2:-2]
                            vareg = r"{{" + term + "}}"
                            #print "Pattern: {0}".format(vareg)
                            #print "Replace: {0}".format(host_dict[term])
                            try:
                                command = re.sub(vareg, host_dict[term], command)
                            except KeyError as err:
                                print "ERROR: Detected a missing key: {0} - Exiting Process".format(err)
                                return ''
                            except Exception as err:
                                print "ERROR: Detected an error: {0} - Exiting Process".format(err)
                                return ''
                            #print "New String: {0}".format(command)
                            #print "-----------------------------------------"
                # Add this line to the list
                new_command_list.append(command)
            # This will execute if a blank line is found
            else:
                pass
                #print "Skipping a blank line..."
    return new_command_list

# Adds device specific content to a template file.
def populate_template(template_file, device=[]):
    command_list = txt_to_list(template_file)
    temp_conf = ''
    # Check if device was provided, if yes, then we need to create templates for each device
    if device:
        temp_conf = os.path.join(dir_path, temp_dir, "temp_" + device['mgmt_ip'].replace(".","") + ".conf")
    else:
        temp_conf = os.path.join(dir_path, temp_dir, "temp_" + get_now_time() + ".conf")

    # Perform the replacement of any variables in these commands
    new_command_list = template_populate(command_list, device)

    # Convert list to a file
    if list_to_txt(temp_conf, new_command_list):
        return temp_conf
    else:
        return temp_conf

# Function to create a specific content CSV with latest information.
def update_content(list_dict):
    content_ld = []
    # Search through old content file to get location and contact info, if available
    old_content = csv_to_listdict(specific_content_csv, mydelim=";")
    # Loop over master list dictionary
    stdout.write("Running content update ... ")
    for record in list_dict:
        new_rec = {}
        new_rec['MGMT_IP'] = record['ip']
        new_rec['HOSTNAME'] = record['hostname']
        new_rec['MODEL'] = record['model']
        new_rec['SITE_CODE'] = getSiteCode(record['hostname'])
        matched = False
        # Loop over the old CSV
        for old_record in old_content:
            # If a matching record is found, match both IP and HOSTNAME
            if old_record['MGMT_IP'] == record['ip'] and old_record['HOSTNAME'] == record['hostname']:
                matched = True
                new_rec['CITY'] = old_record['CITY']
                new_rec['STATE'] = old_record['STATE']
                new_rec['COUNTRY'] = old_record['COUNTRY']
                new_rec['CONTACT_NAME'] = old_record['CONTACT_NAME']
                new_rec['CONTACT_PHONE'] = old_record['CONTACT_PHONE']
        # If no record for this content was found, provide a placeholder
        if not matched:
            new_rec['CITY'] = 'UNDEFINED'
            new_rec['STATE'] = 'UNDEFINED'
            new_rec['COUNTRY'] = 'UNDEFINED'
            new_rec['CONTACT_NAME'] = 'UNDEFINED'
            new_rec['CONTACT_PHONE'] = 'UNDEFINED'
        # Add dictionary to list
        content_ld.append(new_rec)
    # Finished looping over list dictionary
    print "DONE!"
    # Create CSV file
    spec_file_old = os.path.join(dir_path, template_dir, "specific_content_old.csv")
    spec_file = os.path.join(dir_path, template_dir, "specific_content.csv")
    # Copy content to "old" file
    copyfile(spec_file, spec_file_old)
    # Converts the list dict to a CSV, this overwrites the existing file
    if listdict_to_csv(content_ld, spec_file, myDelimiter=";"):
        print "Successfully created new content file!"

# Searches all records for missing commands defined by the provided deviation template
# If there are records, a directory is created to hold the records
# The missing commands are collected into files, any variables are populated based on master CSV
# The commands can be optionally pushed to devices
def deviation_search(list_dict):
    # Update the specific_content file to latest possible version
    update_content(list_dict)
    tmp_lines = []
    hosts = []
    ip_list = []
    discrep_num = 0
    # print "Temps Dir: {0}".format(temps_dir)
    # Choose a series of commands to search for
    file_list = getFileList(temp_dev_dir, ext_filter='conf')

    deviation_selection = getOptionAnswer("Choose a deviation to search for", file_list)
    # If a valid entry is selected
    if deviation_selection:
        tmppath = os.path.join(temp_dev_dir, deviation_selection)
        tmp_lines = txt_to_list(tmppath)

        # Merge the host content and common content to an ld
        new_ld = []
        host_list = []
        common_dict = csv_to_dict_twoterm(common_content_csv, ";")
        content_ld = csv_to_listdict(specific_content_csv, mydelim=";")
        for host_dict in content_ld:
            new_host_dict = host_dict.copy()
            new_host_dict.update(common_dict)
            new_ld.append(new_host_dict)
        #print "NEW_LD:"
        #print new_ld

        # print "Config Dir: {0}".format(config_dir)
        # print "Temps Dir: {0}".format(tmppath)
        print "Searching for template files with content..."
        # Clear out the directory "temp_config_dir"
        rm_rf(temp_config_dir, False)
        # Search configs directory recursively for content
        for folder, dirs, files in os.walk(data_configs_dir):
            for file in files:
                #print "File Name: {0}".format(file)
                command_list = []
                hostname = ""
                if file.startswith('Template_Deviation'):
                    #print "\tFound Template Deviation File: {0}".format(file)
                    #stdout.write("O")
                    fullpath = os.path.join(folder, file)
                    hostname = os.path.split(folder)[1]
                    num_matches = 0
                    with open(fullpath, 'r') as f:
                        ### NEW CONTENT ###
                        #print "HOST: {0}".format(hostname)
                        command_list = []
                        for line in f:
                            # print "Line: {0}".format(line)
                            subline = line.split('> ', 1)[-1].rstrip()
                            if subline in tmp_lines:
                                #print "\tMatched Subline: {0}".format(subline)
                                # Append the commands to a list
                                command_list.append(subline)
                                num_matches += 1
                    # Run this if matches are made
                    if num_matches > 0:
                        if hostname not in hosts:
                            hosts.append(hostname)
                            ip = 'Unknown'
                            for device in list_dict:
                                if device['hostname'] == hostname:
                                    ip = device['ip']
                            #print "Found {0} lines ... appending: {1} ({2}) to file".format(num_matches, hostname, ip)
                            #for command in command_list:
                            #    print "\tCommand: {0}".format(command)
                        else:
                            print "Hostname {0} already listed?".format(hostname)
                        # Replace any variables in the command list
                        for host_dict in new_ld:
                            #print "Host Dict Content:"
                            #print host_dict
                            new_command_list = []
                            #print "Host Dict: {0} checking with {1}".format(hostname, host_dict['HOSTNAME'])
                            if hostname == host_dict['HOSTNAME']:
                                ip = host_dict['MGMT_IP']
                                if ping(ip):
                                    host_list.append({'MGMT_IP': ip, 'HOSTNAME': hostname})
                                    # This populates the commands with any appropriate variables for this device
                                    new_command_list = template_populate(command_list, host_dict)
                                    if new_command_list:
                                        # Get the latest template check date for this device
                                        temp_check = get_db_fact(list_dict, ip, 'last_temp_check')
                                        print "HOST: {0} ({1}) | *** Discrepancies Detected *** | Template Created: {2}".format(hostname, ip, temp_check)
                                        # Increase discrepancy counter by one for display at the end
                                        discrep_num += 1
                                        # List the template commands that matched
                                        for commands in new_command_list:
                                            print "\tLine: {0}".format(commands)
                                        # Save the command list to a text file
                                        temp_dev_name = hostname + "-" + deviation_selection
                                        temp_dev_file = os.path.join(temp_config_dir, temp_dev_name)
                                        try:
                                            list_to_txt(temp_dev_file, new_command_list)
                                        except Exception as err:
                                            print "\t---> Failed converting list to text file: {0}".format(err)
                                        else:
                                            print "\t---> Succeessfully created template file: {0} --".format(temp_dev_name)
                                    else:
                                        print "HOST: {0} ({1}) | ERROR: Failed to populate the template!".format(hostname, ip)
                                else:
                                    print "HOST: {0} ({1}) | Discrepancies Detected, but device not pingable!".format(hostname, ip)
                                # Add ips to list
                                ip_list.append(ip)
                # This will hit any non-template files, we want to skip those
                else:
                    pass
                    #print "Skipping {0} ...".format(file)
        # IP list from these devices
        ip_list_name = os.path.join(temp_config_dir, "ip_list.txt")
        if not list_to_txt(ip_list_name, ip_list):
            print "Failed to create ip list file."
        print "-"*50
        print "Found {0} devices with discrepancies.".format(discrep_num)
        print "-"*50
    # This will execute if there are valid files in the list
    else:
        if not file_list:
            print "No valid .conf files found in {0}".format(temp_dev_dir)
        else:
            print "User quitted ..."
    # Return the host_list
    return host_list

# Template push (For new template function)
def template_push(host_list):
    # Loop over all devices in list of dictionaries
    results_list = []
    output_log = create_timestamped_log("template_output_", "log")
    summary_csv_name = "results_summary_" + get_now_time() + ".csv"
    summary_csv_file = os.path.join(log_dir, summary_csv_name)
    loop = 0
    for host in host_list:
        loop += 1
        host_template_file = getFilename(temp_config_dir, host['HOSTNAME'], ext_filter="conf")
        stdout.write("[{0} of {1}]: Connected to {2}!\n".format(loop, len(host_list), host['MGMT_IP']))
        dev_dict = push_commands_single(host_template_file, output_log, host['MGMT_IP'])
        screen_and_log("\n" + ("-" * 110) + "\n", output_log)
        #exit()
        # Print to a CSV file
        keys = ['HOSTNAME', 'IP', 'MODEL', 'JUNOS', 'CONNECTED', 'LOAD_SUCCESS', 'ERROR']
        dict_to_csv(dev_dict, summary_csv_file, keys)
        results_list.append(dev_dict)

    return results_list

# Template function for bulk set command deployment
def template_commands():
    keys = []
    dev_vars_ld = []
    print "*" * 50 + "\n" + " " * 10 + "TEMPLATE COMMANDS\n" + "*" * 50

    # Choose the template configuration file to use
    filelist = getFileList(config_dir, 'txt')
    template_config = getOptionAnswer("Choose a template command (.txt) file", filelist)
    if template_config:
        template_file = config_dir + template_config
        print "-" * 50
        print " " * 10 + "File: " + template_config
        print "-" * 50
        # Display the commands in the configuration file
        for line in txt_to_list(template_file):
            print " -> {0}".format(line)
        print "-" * 50
    else:
        print "Quit Template Menu..."
        return False

    looping = True
    # Choose the IPs to push the template to
    while looping:
        method_resp = getOptionAnswer('How would you like to select IPs', ['file', 'manual'])
        # Choose a file from a list of options
        if method_resp == "file":
            # Choose the template csv file to use
            filelist = getFileList(csv_dir, 'csv')
            csv_config = getOptionAnswer("Choose a template csv (.csv) file", filelist)
            if csv_config:
                csv_file = csv_dir + csv_config
                dev_vars_ld = csv_to_listdict(csv_file)
                print "-" * 50
                print " " * 10 + "File: " + csv_config
                print "-" * 50

                # Capture the headers of the CSV file
                with open(csv_file, 'r') as f:
                    first_line = f.readline().strip()
                keys = first_line.split(',')
                looping = False
        # Define one or more IPs individually
        elif method_resp == "manual":
            print 'Provide IPs - Correct format: X.X.X.X or X.X.X.X/X:'
            answer = ""
            while( answer != 'x' ):
                answer = getInputAnswer('Enter an ip address (x) to exit')
                if( answer != 'x'):
                    #print get_fact(answer, username, password, 'ip')
                    dev_vars_ld.append({'MGMT_IP': answer})
                    keys = ['MGMT_IP']
            looping = False
        elif method_resp == False:
            print "Quit Template Menu"
            return False
        else:
            print "Invalid selection!"

    # Sort headers with mgmt_ip being the first key
    sorted_keys = []
    if 'MGMT_IP' in keys:
        sorted_keys.append('MGMT_IP')
        for one_key in keys:
            if one_key != 'MGMT_IP':
                sorted_keys.append(one_key)
        # Print the CSV file and the
        for device in dev_vars_ld:
            for key in sorted_keys:
                if key == 'MGMT_IP':
                    print " -> {0}".format(device[key])
                else:
                    print " ---> {0}: {1}".format(key, device[key])
        print "-" * 50
        print "Total IPs: {0}".format(len(dev_vars_ld))

        if getTFAnswer("Continue with template deployment?"):
            # ---------- STARTING LOGGING ------------
            # Start Logging and other stuff
            now = datetime.datetime.now()
            output_log = create_timestamped_log("set_output_", "log")
            summary_csv = create_timestamped_log("summary_csv_", "csv")

            # Print output header, for both screen and log outputs
            screen_and_log(starHeading("DEPLOY COMMANDS LOG", 110), output_log)
            screen_and_log(('User: {0}\n').format(username), output_log)
            screen_and_log(('Performed: {0}\n').format(get_now_time()), output_log)
            screen_and_log(('Output Log: {0}\n').format(output_log), output_log)

            # Print the unpopulated template file to be used to create the configs
            screen_and_log(starHeading("COMMANDS TO EXECUTE", 110), output_log)
            command_list = txt_to_list(template_file)
            for line in command_list:
                screen_and_log("{0}\n".format(line), output_log)
            screen_and_log("*" * 110 + "\n\n", output_log)

            # Define the attributes and show the start of the process
            screen_and_log(starHeading("START PROCESS", 110), output_log)

            # Deploy commands to list of ips
            results = deploy_template_config(template_file, dev_vars_ld, output_log, summary_csv)
            if results:
               #print results
                # Display the end of the process
                screen_and_log(starHeading("END PROCESS", 110), output_log)

                # Results of commands
                screen_and_log(starHeading("PROCESS SUMMARY", 110), output_log)
                # Count the numbers for these
                reachable = 0
                load_success = 0
                unreachable = 0
                load_failed = 0
                for record in results:
                    if record['REACHABLE']:
                        reachable += 1
                    else:
                        unreachable += 1
                    if record['LOAD_SUCCESS']:
                        load_success += 1
                    else:
                        load_failed += 1
                # Display statistics and print to output log
                screen_and_log("Devices Accessed:       {0}\n".format(reachable), output_log)
                screen_and_log("Devices Successful:     {0}\n".format(load_success), output_log)
                screen_and_log("Devices Unreachable:    {0}\n".format(unreachable), output_log)
                screen_and_log("Devices Unsuccessful:   {0}\n".format(load_failed), output_log)
                screen_and_log("Total Devices:          {0}\n\n".format(len(results)), output_log)
                screen_and_log(starHeading("", 110), output_log)
                return True
            else:
                print "Configuration deployment failed\n"
                return False
        else:
            print "\n!!! Configuration deployment aborted... No changes made !!!\n"
            return False
    else:
        print "Unable to find mandatory 'mgmt_ip' column in {0}. Please check the column headers.".format(csv_file)
        return False

# Function for capturing output and initiaing push function
def deploy_template_config(template_file, dev_vars_ld, output_log, summary_csv):

    ##### MULTIPROCESSING #####
    # Create Tuple of Devices
    queue_num = 5                   # The max number of devices that can be connected to at one time
    list_seq = 1                    # Starting sequence of devices
    list_len = len(dev_vars_ld)     # Total number of devices
    ip_pool = ()                    # List for storing process specific parameters
    create_unique = True            # Check if unique templates are needed for each device (varibles)
    temp_conf = ''
    results = ''

    # Check the template file, if there are varibles, we must create individual config files derived from
    # the template/config fusion. If there are no variables, all the template/config fusions will be the same, so
    # we can do it once before the loop below.

    # If variables exist, we must create a unique template configuration for each device
    if not '{{' in open(template_file).read():
        create_unique = False
        temp_conf = populate_template(template_file)

    # Loop over all the devices
    for device in dev_vars_ld:
        if create_unique:
            temp_conf = populate_template(template_file, device)
        # Check that a valid template configuration has been returned
        if temp_conf:
            device_vars = ([temp_conf, output_log, device['mgmt_ip'], list_len, list_seq, summary_csv, username, password], )
            ip_pool += device_vars
            list_seq += 1
        # If a valid template configuration is not returned, return a blank results which means failure
        else:
            return results

    # Pool Commands
    #pp = pprint.PrettyPrinter(indent=4)
    #print "IP Pool:"
    #pp.pprint(ip_pool)

    p = Pool(queue_num)
    try:
        results = p.map(push_commands_multi, ip_pool)
    except TypeError as err:
        print "Map Command Failed: {0}".format(err)
        return False
    except Exception as err:
        print "Unknown Error: {0}".format(err)
        return False
    else:
        p.close()
        p.join()

    return results
    
    ##### MULTIPROCESSING #####
    '''
    ##### STANDARD PROCESSING #####
    # Loop over all devices in list of dictionaries
    results_list = []
    loop = 0
    for device in list_dict:
        loop += 1
        stdout.write("[{0} of {1}]: Connected to {2}!\n".format(loop, len(list_dict), device['mgmt_ip']))
        dev_dict = push_commands_single(populate_template(template_file, device), output_log, device['mgmt_ip'])
        screen_and_log("\n" + ("-" * 110) + "\n", output_log)

        # Print to a CSV file
        keys = ['HOSTNAME', 'IP', 'MODEL', 'JUNOS', 'REACHABLE', 'LOAD_SUCCESS', 'ERROR']
        dict_to_csv(dev_dict, summary_csv, keys)
        results_list.append(dev_dict)

    return results_list
    ##### STANDARD PROCESSING #####
    '''


###########################
# DEVICE ACCESS FUNCTIONS #
###########################

# A function to open a connection to devices and capture any exceptions
def connect(ip, username, password):
    """ Purpose: Attempt to connect to the device

    :param ip:          -   IP of the device
    :param indbase:     -   Boolean if this device is in the database or not, defaults to False if not specified
    :return dev:        -   Returns the device handle if its successfully opened.
    """
    dev = Device(host=ip, user=username, password=password)
    message = ""

    # Try to open a connection to the device
    try:
        dev.open()
        dev.timeout = 700
    # If there is an error when opening the connection, display error and exit upgrade process
    except ConnectRefusedError as err:
        message = "Host Reachable - but NETCONF not configured."
        return False, message
    except ConnectAuthError as err:
        message = "Unable to connect with credentials. User:" + username
        return False, message
    except ConnectTimeoutError as err:
        message = "Timeout error - possible IP reachability issues."
        return False, message
    except ProbeError as err:
        message = "Probe timeout - possible IP reachability issues."
        return False, message
    except ConnectError as err:
        message = "Unknown connection issue."
        return False, message
    except Exception as err:
        message = "Undefined exception."
        return False, message
    # If try arguments succeeded...
    else:
        return dev, message

# Function to push commands using multiple processing streams
def push_commands_multi(attr):
    dev_dict = {'IP': attr[2], 'HOSTNAME': 'Unknown', 'MODEL': 'Unknown', 'JUNOS': 'Unknown', 'REACHABLE': False,
                'LOAD_SUCCESS': False, 'ERROR': ''}
    #print "DEVICE: {0}".format(attr[2])
    #print "\tAttrib 0: {0}".format(attr[0])
    #print "\tAttrib 1: {0}".format(attr[1])
    #print "\tAttrib 2: {0}".format(attr[2])
    #print "\tAttrib 3: {0}".format(attr[3])
    #print "\tAttrib 4: {0}".format(attr[4])
    #print "\tAttrib 5: {0}".format(attr[5])
    dev, message = connect(attr[2], attr[6], attr[7])
    # If we can connect to the device...
    if dev:
        dev_dict['REACHABLE'] = True
        screen_and_log("{0} [{1} of {2}]: Connected!\n".format(attr[2], attr[4], attr[3]), attr[1])
        # Get the hostname
        hostname = dev.facts['hostname']
        if not hostname:
            hostname = "Unknown"
        dev_dict['HOSTNAME'] = hostname
        # Get the model number
        dev_dict['MODEL'] = dev.facts['model']
        # Get the version
        dev_dict['JUNOS'] = dev.facts['version']
        # Try to load the changes
        results = load_with_pyez(dev, config_temp_dir, attr[0], attr[1], attr[2], hostname, attr[6], attr[7])
        # If the load was successful...
        if results == "Completed":
            dev_dict['LOAD_SUCCESS'] = True
        # If the load failed...
        else:
            #screen_and_log("Moving to next device...\n", attr[1])
            dev_dict['ERROR'] = "Issue Loading Configuration: " + results
    # If there were errors connecting to device...
    else:
        dev_dict['ERROR'] = "Unable to Connect! : {0}".format(message)
        screen_and_log("{0} [{1} of {2}]: {3}\n".format(attr[2], attr[4], attr[3], dev_dict['ERROR']), attr[1])

    # Print results to a CSV file
    keys = ['HOSTNAME', 'IP', 'MODEL', 'JUNOS', 'REACHABLE', 'LOAD_SUCCESS', 'ERROR']
    # Save content to the CSV summary file
    dict_to_csv(dev_dict, attr[5], keys)

    # Return this to the calling function
    return dev_dict

# Function to push commands, via file, to one device at a time
def push_commands_single(commands_fp, output_log, ip):
    dev_dict = {'IP': ip, 'HOSTNAME': 'Unknown', 'MODEL': 'Unknown', 'JUNOS': 'Unknown', 'CONNECTED': False,
                'LOAD_SUCCESS': False, 'ERROR': ''}
    dev, message = connect(ip, username, password)
    if dev:
        dev_dict['CONNECTED'] = True
        screen_and_log("{0}: Connected!\n".format(ip), output_log)
        # Get the hostname
        hostname = dev.facts['hostname']
        if not hostname:
            hostname = "Unknown"
        dev_dict['HOSTNAME'] = hostname
        # Get the model number
        dev_dict['MODEL'] = dev.facts['model']
        # Get the version
        dev_dict['JUNOS'] = dev.facts['version']
        # Try to load the changes
        results = load_with_pyez(dev, config_temp_dir, commands_fp, output_log, ip, hostname, username, password)
        # If the load was successful...
        if results == "Completed":
            dev_dict['LOAD_SUCCESS'] = True
        else:
            dev_dict['ERROR'] = "Issue Loading Configuration: " + results
    # If there were errors connecting to device...
    else:
        dev_dict['ERROR'] = "Unable to Connect! : {0}\n".format(message)
        screen_and_log("{0}: Unable to Connect: {1}\n".format(ip, message), output_log)

    # Return this to the calling function
    return dev_dict

# Function for capturing output and initiaing push function
def deploy_config(commands_fp, my_ips, output_log, summary_csv):
    # Lists
    dict_of_lists = {'devs_connected': [], 'devs_successful': []}

    # Loop over all devices in my_ips list
    loop = 0
    for ip in my_ips:
        loop += 1
        stdout.write("[{0} of {1}] - Connecting to {2} ... ".format(loop, len(my_ips), ip))
        results = push_commands_single(commands_fp, output_log, ip)
        screen_and_log("\n" + ("-" * 110) + "\n", output_log)
        if results['CONNECTED']: dict_of_lists['devs_connected'].append(ip)
        if results['LOAD_SUCCESS']: dict_of_lists['devs_successful'].append(ip)

        # Print to a CSV file
        keys = ['HOSTNAME', 'IP', 'MODEL', 'JUNOS', 'CONNECTED', 'LOAD_SUCCESS', 'ERROR']
        dict_to_csv(results, summary_csv, keys)

    # Return the dicts of lists with results
    return dict_of_lists

# Function to push set commands to multiple devices
def standard_commands():
    my_ips = []
    temp_conf = os.path.join(dir_path, "temp.conf")
    print "*" * 50 + "\n" + " " * 10 + "SET COMMANDS\n" + "*" * 50
    # Get the devices to push commands to
    my_ips = chooseDevices(iplist_dir)
    # Provide option for using a file to supply configuration commands, if the list is populated
    if my_ips:
        set_file = ""
        commands_fp = ""
        command_list = []
        if not getTFAnswer('\nProvide commands from a file'):
            command_list = getMultiInputAnswer("Enter a set command")
            if list_to_txt(temp_conf, command_list):
                commands_fp = temp_conf
        else:
            filelist = getFileList(config_dir)
            # If the files exist...
            if filelist:
                set_config = getOptionAnswer("Choose a config file", filelist)
                commands_fp = config_dir + set_config
                command_list = txt_to_list(commands_fp)

        # Print the set commands that will be pushed
        print "\n" + " " * 10 + "Set Commands Entered"
        print "-" * 50
        if command_list:
            for one_comm in command_list:
                print " -> {0}".format(one_comm)
        print "-" * 50 + "\n"

        # Verify that user wants to continue with this deployment
        if getTFAnswer("Continue with set commands deployment?"):
            # ---------- STARTING LOGGING ------------
            # Start Logging and other stuff
            now = datetime.datetime.now()
            output_log = create_timestamped_log("set_output_", "log")
            summary_csv = create_timestamped_log("summary_csv_", "csv")

            # Print output header, for both screen and log outputs
            screen_and_log(starHeading("DEPLOY COMMANDS LOG", 110), output_log)
            screen_and_log(('User: {0}\n').format(username), output_log)
            screen_and_log(('Performed: {0}\n').format(get_now_time()), output_log)
            screen_and_log(('Output Log: {0}\n').format(output_log), output_log)

            # Print the commands that will be executed
            screen_and_log(starHeading("COMMANDS TO EXECUTE", 110), output_log)
            for line in command_list:
                screen_and_log(" -> {0}\n".format(line), output_log)
            screen_and_log("*" * 110 + "\n\n", output_log)

            # Define the attributes and show the start of the process
            screen_and_log(starHeading("START PROCESS", 110), output_log)

            # ---------- MAIN EXECUTION ----------
            # Deploy commands to list of ips
            results = deploy_config(commands_fp, my_ips, output_log, summary_csv)

            # ---------- ENDING LOGGING -----------
            # Display the end of the process
            screen_and_log(starHeading("END PROCESS", 110), output_log)

            # Compute the stats
            total_num = len(my_ips)
            connect_num = len(results['devs_connected'])
            not_connect_num = total_num - connect_num
            success_num = len(results['devs_successful'])
            not_success_num = total_num - success_num

            # Results of commands
            screen_and_log(starHeading("PROCESS SUMMARY", 110), output_log)
            screen_and_log("Devices Connected:      {0}\n".format(connect_num), output_log)
            screen_and_log("Devices Unreachable:    {0}\n".format(not_connect_num), output_log)
            screen_and_log("Devices Successful:     {0}\n".format(success_num), output_log)
            screen_and_log("Devices Unsuccessful:   {0}\n".format(not_success_num), output_log)
            screen_and_log("Total Devices:          {0}\n\n".format(total_num), output_log)
            screen_and_log(starHeading("", 110), output_log)
        else:
            print "\n!!! Configuration deployment aborted... No changes made !!!\n"

# Collects the attributes from the object and returns a dictionary
def collect_attribs(dev_obj, hostname):
    item_dict = {'hostname': '', 'name': '', 'description': '', 'version': '', 'location': '',
                 'part-number': '', 'serial-number': ''}
    items = ['name', 'description', 'version', 'part-number', 'serial-number']

    location = "LOCATION"
    # Gather chassis attribs
    item_dict['hostname'] = hostname
    item_dict['location'] = location
    for item in items:
        if dev_obj.findtext(item):
            if item == 'name' and dev_obj.findtext(item) == 'CPU':
                return False
            else:
                item_dict[item] = dev_obj.findtext(item).replace(',', '')

    return item_dict

# Grabs the devices chassis hardware info and places it in
def get_chassis_inventory(dev, hostname):
    # Testing context
    root = dev.rpc.get_chassis_inventory()
    print "\t- Gathering chassis hardware information..."
    inventory_listdict = []

    # Check to see if chassis exists
    if root.findtext('chassis'):
        # Gather chassis attribs
        for base in root.findall('chassis'):
            item = collect_attribs(base, hostname)
            if item:
                inventory_listdict.append(item)
            # Gather module attribs
            if base.findtext('chassis-module'):
                for module in base.findall('chassis-module'):
                    item = collect_attribs(module, hostname)
                    if item:
                        inventory_listdict.append(item)
                    # Gather attribs
                    if module.findtext('chassis-sub-module'):
                        for submodule in module.findall('chassis-sub-module'):
                            item = collect_attribs(submodule, hostname)
                            if item:
                                inventory_listdict.append(item)
                            # Gather attribs
                            if submodule.findtext('chassis-sub-sub-module'):
                                for subsubmodule in submodule.findall('chassis-sub-sub-module'):
                                    item = collect_attribs(subsubmodule, hostname)
                                    if item:
                                        inventory_listdict.append(item)
                                    # Gather attribs
                                    if subsubmodule.findtext('chassis-sub-sub-sub-module'):
                                        for subsubsubmodule in subsubmodule.findall('chassis-sub-sub-sub-module'):
                                            item = collect_attribs(subsubsubmodule, hostname)
                                            if item:
                                                inventory_listdict.append(item)
    # Add the content to the inventory CSV
    stdout.write("\t- Adding to CSV...")
    item_key = ['hostname', 'name', 'description', 'version', 'location', 'part-number', 'serial-number']
    inv_file = hostname + "_inventory.csv"
    inv_csv = os.path.join(inv_dir, inv_file)
    listdict_to_csv(inventory_listdict, inv_csv, columnNames=item_key)
    print "Done!"

# Function for running operational commands to multiple devices
def oper_commands(my_ips):
    print "*" * 50 + "\n" + " " * 10 + "OPERATIONAL COMMANDS\n" + "*" * 50
    # Provide selection for sending a single command or multiple commands from a file
    if not my_ips:
        my_ips = chooseDevices(iplist_dir)

    if my_ips:
        command_list = []
        print "\n" + "*" * 110 + "\n"
        command_list = getMultiInputAnswer("Enter a command to run")

        if getTFAnswer("Continue with operational requests?"):
            output_log = create_timestamped_log("oper_output_", "log")
            err_log = create_timestamped_log("oper_err_", "log")
            # Header of operational command output
            screen_and_log(starHeading("OPERATIONAL COMMANDS OUTPUT", 110), output_log)
            screen_and_log(('User: {0}\n').format(username), output_log)
            screen_and_log(('Performed: {0}\n').format(get_now_time()), output_log)
            screen_and_log(('Output Log: {0}\n').format(output_log), output_log)
            screen_and_log(('Error Log: {0}\n').format(err_log), output_log)
            screen_and_log(starHeading("COMMANDS EXECUTED", 110), output_log)
            for command in command_list:
                screen_and_log(' -> {0}\n'.format(command), output_log)
            screen_and_log('*' * 110 + '\n', output_log)

            # Loop over commands and devices
            devs_unreachable = []
            devs_no_output = []
            devs_with_output = []
            loop = 0
            try:
                screen_and_log("-" * 110 + "\n", output_log)
                for ip in my_ips:
                    command_output = ""
                    loop += 1
                    stdout.write("-> Connecting to " + ip + " ... ")
                    dev, message = connect(ip, username, password)
                    # If the connection is successful...
                    if dev:
                        print "Connected!"
                        hostname = dev.facts['hostname']
                        if not hostname:
                            hostname = "Unknown"
                        got_output = False
                        # Loop over the commands provided
                        if command_list:
                            stdout.write(hostname + ": Executing commands ")
                            for command in command_list:
                                command_output += "\n" + hostname + ": Executing -> {0}\n".format(command)
                                #com = dev.cli_to_rpc_string(command)
                                #print "Command: {0}\nRPC: {1}\n".format(command, com)
                                #if com is None:
                                try:
                                    results = dev.cli(command, warning=False)
                                except Exception as err:
                                    stdout.write("\n")
                                    screen_and_log("{0}: Error executing '{1}'. ERROR: {2}\n".format(ip, command, err), err_log)
                                    stdout.write("\n")
                                else:
                                    if results:
                                        command_output += results
                                        got_output = True
                                    stdout.write(".")
                                    stdout.flush()
                            if got_output:
                                devs_with_output.append(ip)
                                screen_and_log(command_output, output_log)
                                stdout.write("\n")
                            else:
                                devs_no_output.append(ip)
                                stdout.write(" No Output!\n")
                        # If no commands are provided, run the get_chassis_inventory on devices
                        else:
                            get_chassis_inventory(dev, hostname)
                        # Close connection to device
                        try:
                            dev.close()
                        except TimeoutExpiredError as err:
                            print "Error: {0}".format(err)
                            break
                    # If the connection is not successful, provide the connection failure information
                    else:
                        screen_and_log("{0}: Unable to connect : {1}\n".format(ip, message), err_log)
                        devs_unreachable.append(ip)
                screen_and_log("-" * 110 + "\n", output_log)
                screen_and_log(starHeading("COMMANDS COMPLETED", 110), output_log)
                # Results of commands
                screen_and_log(starHeading("PROCESS SUMMARY", 110), output_log)
                screen_and_log("Devices With Output:  {0}\n".format(len(devs_with_output)), output_log)
                screen_and_log("Devices No Output:    {0}\n".format(len(devs_no_output)), output_log)
                screen_and_log("Devices Unreachable:  {0}\n".format(len(devs_unreachable)), output_log)
                screen_and_log("Total Devices:        {0}\n".format(len(my_ips)), output_log)
                screen_and_log("*" * 110 + "\n", output_log)
            except KeyboardInterrupt:
                print "Exiting Procedure..."
        else:
            print "\n!!! Configuration deployment aborted... No changes made !!!\n"
    else:
        print "\n!! Configuration deployment aborted... No IPs defined !!!\n"


###################
# UPGRADE CONTENT #
###################

# Create an upgrade dictionary
def upgrade_menu():
    intial_upgrade_ld = []
    heading_list = ['Hostname', 'IP', 'Model', 'Current Code', 'Target Code']
    key_list = ['hostname', 'ip', 'model', 'curr_code', 'targ_code']

    # Ask user how to select devices for upgrade (file or manually)
    my_options = ['Add from a CSV file', 'Add from a list of IPs', 'Add IPs Individually', 'Continue', 'Quit']
    print "*" * 50 + "\n" + " " * 10 + "JSHOW: UPGRADE JUNIPERS\n" + "*" * 50
    while True:
        answer = getOptionAnswerIndex('Make a Selection', my_options)
        print subHeading("ADD CANDIDATES", 10)
        # Option for providing a file with IPs and target versions
        if answer == "1":
            selected_file = getOptionAnswer("Choose a CSV file", getFileList(upgrade_dir, 'csv'))
            temp_ld = csv_to_listdict(selected_file, keys=['ip', 'target_code'])
            # Loop over all CSV entries
            print "*" * 50
            if selected_file:
                for chassis in temp_ld:
                    ip = chassis['ip']
                    targ_code = chassis['target_code']
                    # Checks if the IP already exists, if it doesn't, add it
                    if not any(d['ip'] == ip for d in intial_upgrade_ld):
                        chassis_info = get_chassis_info(ip, targ_code=None)
                        # Check if we are able to capture chassis info,
                        if chassis_info:
                            intial_upgrade_ld.append(chassis_info)
                        else:
                            print "Skipping..."
                    else:
                        print "IP {0} is already in the list. Skipping...".format(ip)
                print "*" * 50
                print ""
                print subHeading("CANDIDATE LIST", 10)
                print_listdict(intial_upgrade_ld, heading_list, key_list)
        # Option for creating a listDict from a source file with IPs
        elif answer == "2":
            ip_list = []
            # Lets user select an "ips" file from a directory
            selected_file = getOptionAnswer("Choose a IPS file", getFileList(upgrade_dir, 'ips'))
            # Convert it to a list and then add them to a list dictionary
            ip_list = txt_to_list(selected_file)
            # Loop over all the IPs in the list
            print "*" * 50
            if selected_file:
                for ip in ip_list:
                    # Checks if the IP already exists, if it doesn't, add it
                    if not any(d['ip'] == ip for d in intial_upgrade_ld):
                        chassis_info = get_chassis_info(ip, targ_code=None)
                        # Check if we are able to capture chassis info,
                        if chassis_info:
                            intial_upgrade_ld.append(chassis_info)
                        else:
                            print "Skipping..."
                    else:
                        print "IP {0} is already in the list. Skipping...".format(ip)
                print "*" * 50
                print ""
                print subHeading("CANDIDATE LIST", 10)
                print_listdict(intial_upgrade_ld, heading_list, key_list)
        # Option for manually providing the information
        elif answer == "3":
            ip_list = []
            # Ask for an IP address
            while True:
                ip = getInputAnswer(question="Enter an IPv4 Host Address('q' when done)")
                if ip == "q":
                    break
                # Check if answer is a valid IPv4 address
                elif netaddr.valid_ipv4(ip):
                    # Checks if the IP already exists, if it doesn't, add it
                    if not any(d['ip'] == ip for d in intial_upgrade_ld):
                        print "*" * 50
                        chassis_info = get_chassis_info(ip, targ_code=None)
                        # Check if we are able to capture chassis info,
                        if chassis_info:
                            intial_upgrade_ld.append(chassis_info)
                        else:
                            print "Skipping..."
                        print "*" * 50
                    else:
                        print "IP {0} is already in the list. Skipping...".format(ip)
            print ""
            print subHeading("CANDIDATE LIST", 10)
            print_listdict(intial_upgrade_ld, heading_list, key_list)
        # Finish selection and continue
        elif answer == "4" and intial_upgrade_ld:
            final_upgrade_ld = format_data(intial_upgrade_ld)
            # Display the list of target codes chosen
            print ""
            print subHeading("UPGRADE LIST", 40)
            print_listdict(final_upgrade_ld, heading_list, key_list)
            # Start upgrade process
            upgrade_loop(final_upgrade_ld)
            break
        # Quit this menu
        elif answer == "5":
            break
    print "Exiting JSHOW: UPGRADE JUNIPERS"

# Function to loop over all devices chosen for upgrades
def upgrade_loop(upgrade_ld):
    # Get Reboot Preference
    reboot = "askReboot"
    myoptions = ['Reboot ALL devices AFTER upgrade', 'Do not reboot ANY device AFTER upgrade', 'Ask for ALL devices']
    answer = getOptionAnswerIndex("How would you like to handle reboots", myoptions)

    if answer == "1":
        reboot = "doReboot"
    elif answer == "2":
        reboot = "noReboot"
    else:
        reboot = "askReboot"

    print subHeading("UPGRADE LIST", 40)
    t = PrettyTable(['Hostname', 'IP', 'Model', 'Current Code', 'Target Code', 'Reboot'])
    for device in upgrade_ld:
        t.add_row([device['hostname'], device['ip'], device['model'], device['curr_code'], device['targ_code'], reboot])
    print t
    # Last confirmation before entering loop
    verified = getTFAnswer("Please Verify the information above. Continue")

    # Upgrade Loop
    # verified = 'y'
    if verified:
        # Create log file
        now = datetime.datetime.now()
        date_time = now.strftime("%Y-%m-%d-%H%M")
        install_log = log_dir + "install-log_" + date_time + ".log"
        host = "PyEZ Server"

        # Start logging if required
        logging.basicConfig(filename=install_log, level=logging.INFO, format='%(asctime)s:%(name)s: %(message)s')
        logging.getLogger().name = host
        logging.getLogger().addHandler(logging.StreamHandler())
        logging.info('Information logged in {0}'.format(install_log))

        # Loop over all devices in list
        for device in upgrade_ld:
            # Define the Device being upgraded
            logging.info('-' * 30)
            logging.info('Upgrading {0} IP: {1}'.format(device['hostname'], device['ip']))
            logging.info('Model ........ {0}'.format(device['model']))
            logging.info('Current OS ... {0}'.format(device['curr_code']))
            logging.info('Target OS .... {0}'.format(device['targ_code']))
            logging.info('-' * 30)

            # Assemble image file path
            image_path_file = images_dir + device['targ_code']

            # Upgrade the device
            upgrade_device(device['ip'], image_path_file, logging, reboot)

        # Attempt to deactivate logging
        print "Attempt to deactivate logging..."
        logging.disable('CRITICAL')

# Upgrade the Juniper device
def upgrade_device(host, package, logging, reboot, remote_path='/var/tmp', validate=True):

    # Verify package is present
    if not (os.path.isfile(package)):
        msg = 'Software package does not exist: {0}. '.format(package)
        logging.error(msg)
        sys.exit()

    dev = Device(host=host, user=username, passwd=password)
    try:
        dev.open()
    except ConnectError as err:
        logging.error('Cannot connect to device: {0}\n'.format(err))
        return False

    # Create an instance of SW
    sw = SW(dev)

    try:
        logging.info('Starting the software upgrade process: {0}'.format(package))
        ok = sw.install(package=package, remote_path = remote_path, progress=update_progress, validate=validate)
    except Exception as err:
        logging.error('Unable to install software, {0}'.format(err))
        ok = False
        dev.close()
        logging.shutdown()
        return False

    if ok is True:
        logging.info('Software installation complete.')
        # Check rebooting status...
        if reboot == "askReboot":
            answer = getYNAnswer('Would you like to reboot')
            if answer == 'y':
                reboot = "doReboot"
            else:
                reboot = "noReboot"
        if reboot == "doReboot":
            rsp = sw.reboot()
            logging.info('Upgrade pending reboot cycle, please be patient.')
            logging.info(rsp)
            # Open a command terminal to monitor device connectivity
            # os.system("start cmd /c ping -t " + ip)
        elif reboot == "noReboot":
            logging.info('Reboot NOT performed. System must be rebooted to complete upgrade.')
    else:
        logging.error('Issue installing software')
        logging.shutdown()
        dev.close()
        return False

    # End the NDTCONF session and close the connection
    dev.close()
    return True

# Log the upgrade progress
def update_progress(dev, report):
    # Log the progress of the installation process
    logging.info(report)

# Capture chassis info
def get_chassis_info(ip, targ_code):
    chassis_dict = {}
    stdout.write("Connecting to {0} ... ".format(ip))
    dev, message = connect(ip)
    if dev:
        try:
            chassis_dict['ip'] = ip
            chassis_dict['targ_code'] = targ_code
            chassis_dict['curr_code'] = dev.facts['version']
            chassis_dict['model'] = dev.facts['model']
            chassis_dict['hostname'] = dev.facts['hostname']
        except Exception as err:
            print " Error detected: {0}".format(err)
        else:
            print " Information Successfully Collected!"
        dev.close()
    else:
        print "{0}: Unable to connect : {1}\n".format(ip, message)
    return chassis_dict

# Fix any deficiencies in the list dictionary. Verify a valid IP and valid code if the code is provided.
def format_data(intial_upgrade_ld):
    # List Dictionary to store completed list in
    final_upgrade_ld = []

    # Loop over all devices in the list
    for host_dict in intial_upgrade_ld:
        # Get target code and corresponding image file
        if host_dict['curr_code'] and host_dict['model']:
            print "Hostname.........{0}".format(host_dict['hostname'])
            print "IP...............{0}".format(host_dict['ip'])
            print "Model............{0}".format(host_dict['model'])
            print "Current Code.....{0}".format(host_dict['curr_code'])
            print "Requested Code...{0}".format(host_dict['targ_code'])

            target_code_file = get_target_image(host_dict['curr_code'], host_dict['targ_code'], host_dict['model'])
            if target_code_file:
                final_upgrade_ld.append({'hostname': host_dict['hostname'], 'ip': host_dict['ip'],
                                         'model': host_dict['model'], 'curr_code': host_dict['curr_code'],
                                         'targ_code': target_code_file})
                print "--> Selected version {0} for {1}".format(target_code_file, host_dict['ip'])
            else:
                pass
        else:
            print "--> ERROR: Unable to verify current code and model"

    return final_upgrade_ld

# Checks the code to make sure its available and that the code is correct for the model
def get_target_image(curr_code, targ_code, model):
    exact_match = []
    partial_match = []
    found_match = False

    # Extract model, type, and prefix
    dev_model = model[:4]
    dev_type = dev_model[:2].lower()
    dev_prefix = str(dev_model[-2:])

    # Loop over each available image in the images directory
    for img_file in getFileList(images_dir, "tgz"):
        # Remove the path prefix
        file_only = img_file.rsplit('/', 1)[1]
        # Regex to match the current device model number
        image_regex = r'^jinstall-' + re.escape(dev_type) + r'-' + re.escape(dev_prefix) + r'\d{2}-\d{2}\.\d{1}.*-domestic-signed\.tgz$'
        # If this image matches the device model...
        if re.search(image_regex, file_only):
            found_match = True
            # If a target code was specified for this upgrade...
            if targ_code:
                # Check if we can match the requested target code...
                if targ_code in file_only:
                    print " --> Found Exact Match: {0}".format(file_only)
                    exact_match.append(file_only)
                # If we can't match target code, return model matches
                else:
                    print " --> Found Partial Match: {0}".format(file_only)
                    partial_match.append(file_only)
            # If no target was prescribed, return model matches
            else:
                print " --> Found Partial Match: {0}".format(file_only)
                partial_match.append(file_only)
    #print "FINISHED WITH IMAGE CHECK!"

    # If a match was found...
    print ""
    if found_match:
        if exact_match:
            if len(exact_match) == 1:
                print "Exact Match!"
                return exact_match[0]
            else:
                print "Mutiple exact matches found!"
                return getOptionAnswer("Please choose an image", exact_match)
        else:
            print "Partial matches found!"
            return getOptionAnswer("Please choose an image", partial_match)
    else:
        print "No matches were found!"
        return getOptionAnswer("Please choose an image", partial_match)

    # If only one exact match exists, automatically add it as the target image
    # If multiple exact matches exist, only display exact maches for the user to choose from
    # If only partial matches exist, display them for the user to choose from
    # If no matches exist, display all images

        #else:
            #print "\t --> Didn't Match: {0}".format(file_only)

        #selected_file = getOptionAnswer("Choose an image file", getFileList(upgrade_dir, 'tgz'))

# Print a list dictionary using PrettyTable
def print_listdict(list_dict, headings, keys):
    """ 
        Purpose: Display a table showing contents of the list dictionary.
        Returns: Nothing
    """
    t = PrettyTable(headings)
    for host_dict in list_dict:
        # print device
        mylist = []
        for key in keys:
            if key in host_dict.keys():
                mylist.append(host_dict[key])
            else:
                mylist.append("")
        t.add_row(mylist)
    print t
    print "Total Items: {0}".format(len(list_dict))


#######################
# MAIN EXECUTION LOOP #
#######################
if __name__ == "__main__":
    # Detect the platform type
    detect_env()

    # Get a username and password from the user
    username = getargs(sys.argv[1:])

    if not username:
        print 'Please supply a username as an argument: jshow.py -u <username>'
        exit()
    password = getpass(prompt="\nEnter your password: ")

    # Define menu options
    my_options = ['Execute Operational Commands', 'Execute Set Commands', 'Execute Template Commands', 'Deviation Template', 'Upgrade Junipers', 'Quit']
    my_ips = []

    # Get menu selection
    try:
        while True:
            stdout.write("\n\n")
            print "*" * 50 + "\n" + " " * 10 + "JSHOW: MAIN MENU\n" + "*" * 50
            print "Username: {0}".format(username)
            answer = getOptionAnswerIndex('Make a Selection', my_options)
            if answer == "1":
                oper_commands(my_ips)
            elif answer == "2":
                standard_commands()
            elif answer == "3":
                template_commands()
            elif answer == "4":
                host_list = deviation_search(json_to_listdict(main_list_dict))
                if host_list:
                        if getTFAnswer("Would you like to push the changes"):
                            template_push(host_list)
                        else:
                            print "No changes pushed. Returning to Main Menu..."
                else:
                    print "No changes needed!"
            elif answer == "5":
                upgrade_menu()
            elif answer == "6":
                quit()
    except KeyboardInterrupt:
        print 'Exiting...'
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
