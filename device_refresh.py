__copyright__ = "Copyright 2016 Tyler Jordan"
__version__ = "0.1.1"
__email__ = "tjordan@juniper.net"

import os
import platform
import subprocess
import datetime
import getopt
import re
import time

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
log_dir = ''
template_file = ''

addl_opt = ''
listDict = []
mypwd = ''
myuser = ''
port = 22
system_slash = "/"   # This is the linux/mac slash format, windows format will be used in that case


def detect_env():
    """ Purpose: Detect OS and create appropriate path variables. """
    global template_file
    global listDictCSV
    global credsCSV
    global iplist_dir
    global config_dir
    global log_dir
    global system_slash

    if platform.system().lower() == "windows":
        #print "Environment Windows!"
        template_file = ".\\data\\configs\\Template.conf"
        listDictCSV = ".\\data\\listdict.csv"
        iplist_dir = ".\\data\\iplists\\"
        config_dir = ".\\data\\configs\\"
        log_dir = ".\\data\\logs\\"
        system_slash = "\\"
    else:
        #print "Environment Linux/MAC!"
        template_file = "./data/configs/Template.conf"
        listDictCSV = "./data/listdict.csv"
        iplist_dir = "./data/iplists/"
        config_dir = "./data/configs/"
        log_dir = "./data/logs/"

def load_config_file(ip, newest):
    """ Purpose: Load the selected device's configuration file into a variable. """
    record = get_record(ip=ip)
    if record:
        my_file = get_old_new_file(record, newest)
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
    """ Purpose: Returns the oldest config file from specified IP
        Parameters:     newest - Is either T or F, True means get the newest file, False, means get the oldest.
    """
    filtered_list = []
    if record:
        my_dir = config_dir + getSiteCode(record) + system_slash
        for file in listdir(my_dir):
            if file.startswith(record['host_name']):
                filtered_list.append(my_dir + file)
    sorted_list = sorted(filtered_list, key=os.path.getctime)
    if newest:
        return sorted_list[-1]
    else:
        return sorted_list[0]

def get_file_number(record):
    file_num = 0
    if record:
        my_dir = config_dir + getSiteCode(record) + system_slash
        for file in listdir(my_dir):
            if file.startswith(record['host_name']):
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


def save_config_file(myconfig, record):
    """ Purpose: Creates a config file and adds text to the file.
        Returns: True or False
    """
    # Get the current time
    now = get_now_time()
    site_dir = config_dir + getSiteCode(record) + system_slash

    # Check if the appropriate site directory is created. If not, then create it.
    if not os.path.isdir(site_dir):
        os.mkdir(site_dir)

    # Create the filename
    filename = site_dir + record['host_name'] + "-" + now + ".conf"
    try:
        newfile = open(filename, "w+")
    except Exception as err:
        print 'ERROR: Unable to open file: {0} | File: {1}'.format(err, filename)
        return False
    else:
        # Remove excess configurations if necessary
        if get_file_number(record) > 2:
            del_file = get_old_new_file(record, newest=False)
            try:
                os.remove(del_file)
            except Exception as err:
                print "ERROR: Unable to remove old file: {0} | File: {1}".format(err, del_file)
        try:
            newfile.write(myconfig)
        except Exception as err:
            print "ERROR: Unable to write config to file: {0}".format(err)
            return False
        else:
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
        return linelist


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
                            print "- Device Paramters Unchanged -\n"
                        else:
                            print "- JunOS changed from {0} to {1}".format(localDict['junos_code'], remoteDict['junos_code'])
                            change_record(ip, remoteDict['junos_code'], key='junos_code')
                    else:
                        print "- S/N changed from {0} to {1}".format(localDict['serial_number'], remoteDict['serial_number'])
                        change_record(ip, remoteDict['serial_number'], key='serial_number')
                        if localDict['model'] != remoteDict['model']:
                            print "- Model changed from {0} to {1}".format(localDict['model'], remoteDict['model'])
                            change_record(ip, remoteDict['model'], key='model')
                        if localDict['junos_code'] != remoteDict['junos_code']:
                            print "- JunOS changed from {0} to {1}".format(localDict['junos_code'], remoteDict['junos_code'])
                            change_record(ip, remoteDict['junos_code'], key='junos_code')
                else:
                    if localDict['serial_number'] != remoteDict['serial_number']:
                        print "- S/N changed from {0} to {1}".format(localDict['serial_number'], remoteDict['serial_number'])
                        change_record(ip, remoteDict['serial_number'], key='serial_number')
                        if localDict['model'] != remoteDict['model']:
                            print "- Model changed from {0} to {1}".format(localDict['model'], remoteDict['model'])
                            change_record(ip, remoteDict['model'], key='model')
                    # Do these regardless of S/N results
                    print "- Hostname changed from {0} to {1}".format(localDict['host_name'], remoteDict['host_name'])
                    change_record(ip, remoteDict['host_name'], key='host_name')
                    if localDict['junos_code'] != remoteDict['junos_code']:
                        print "- JunOS changed from {0} to {1}".format(localDict['junos_code'], remoteDict['junos_code'])
                        change_record(ip, remoteDict['junos_code'], key='junos_code')
                """
                for attrib in record_attribs:
                    if localDict[attrib] != remoteDict[attrib]:
                        print attrib + " changed from {0} to {1}!".format(localDict[attrib], remoteDict[attrib])
                        change_record(ip, remoteDict[attrib], key=attrib)
                """
            else:
                # If no, this is a device that hasn't been identified yet, create a new record
                print "-"*41
                print "- Adding device {0} as a new record".format(ip)
                if add_record(ip):
                    print "- Successful"
                    return True
                else:
                    print "- Failed"
                    return False
        else:
            print "ERROR: Unable to collect information from device: {0}".format(ip)
            return False
        #print "Checking config..."

    # If we can't ping, but we have a record
    elif has_record:
        # Set record status to "unreachable"
        print "ERROR: Unable to ping KNOWN device: {0}".format(ip)
        return False
    # If we can't ping, and have no record
    else:
        print "ERROR: Unable to ping: {0}".format(ip)
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
    """ Purpose: Adds a record to list of dictionaries.
    """
    try:
        items = run(ip, myuser, mypwd, port)
    except Exception as err:
        print 'ERROR: Unable to get record information: {0} | Device: {1}'.format(err, ip)
        items['last_update_attempt'] = get_now_time()
        listDict.append(items)
        return False
    else:
        if save_config_file(fetch_config(ip), items):
            items['last_config_success'] = get_now_time()
            items['last_config_attempt'] = get_now_time()
            items['last_update_attempt'] = get_now_time()
            items['last_update_success'] = get_now_time()
            print 'Configuration captured: {0}'.format(ip)
            listDict.append(items)
            return True
        else:
            items['last_config_attempt'] = get_now_time()
            items['last_update_attempt'] = get_now_time()
            items['last_update_success'] = get_now_time()
            listDict.append(items)
            return True

def ping(ip):
    """ Purpose: Determine if an IP is pingable
    :param ip: IP address of host to ping
    :return: True if ping successful
    """
    ping_str = "-n 3" if platform.system().lower()=="windows" else "-c 3"
    response = os.system("ping " + ping_str + " " + ip)

    if response == 0:
        return True
    else:
        return False

    '''
    with open(os.devnull, 'w') as DEVNULL:
        try:
            # Check for Windows or Linux/MAC
            ping_param = "-n" if platform.system().lower() == "windows" else "-c"
            subprocess.check_call(
                ['ping', ping_param, '3', ip],
                stdout=DEVNULL,
                stderr=DEVNULL
            )
        except subprocess.CalledProcessError:
            return False
        else:
            return True
    '''

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
                print "ERROR: Unable to update record value: {0} | Device: {1}".format(err, ip)
                return False
            else:
                # If the record change was successful...
                now = get_now_time()
                time_dict = {'last_update_success': now}
                myrecord.update(time_dict)
                return True

def fetch_config(ip):
    """ Purpose: Get current configuration from device.
        Returns: Text File
    """
    dev = Device(host=ip, user=myuser, passwd=mypwd)
    # Try to open a connection to the device
    try:
        #print "Connecting to: {0}".format(ip)
        dev.open()
    # If there is an error when opening the connection, display error and exit upgrade process
    except ConnectRefusedError as err:
        print "ERROR: Cannot connect to device: {0} Device: {1}".format(err, ip)
    except Exception as err:
        print "ERROR: Unable to open connection: {0} Device: {1}".format(err, ip)
    # If try arguments succeed...
    else:
        # Increase the default RPC timeout to accommodate install operations
        dev.timeout = 600
        myconfig = dev.cli('show config | display set', warning=False)
        return myconfig

def update_config(ip, current_config):
    """ Purpose: Save the configuration for this """
    iprec = get_record(ip=ip)
    try:
        now = get_now_time()
        iprec.update({'last_config_attempt': now})
        save_config_file(current_config, get_record(ip=ip))
    except Exception as err:
        print "Unable to save config {0} : {1}".format(ip, err)
        return False
    else:
        now = get_now_time()
        iprec.update({'last_config_success': now})
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

def config_compare(myrecord, logfile):
    """ Purpose: To compare two configs and get the differences, log them
        Parameters:
            myrecord        -   Object that contains parameters of devices
            logfile         -   Reference to log object, for displaying and logging output
    """
    current_config = fetch_config(myrecord['ip'])
    change_list = compare_configs(load_config_file(myrecord['ip'], newest=True), current_config)
    if change_list:
        # print "Configs are different - updating..."
        print_sl("- Found Configuration Changes -\n\n", logfile)
        print_sl("Discrepancies:\n-------------\n", logfile)
        # Try to write diffList output to a file
        for item in change_list:
            print_sl("{0}\n".format(item), logfile)
        if update_config(myrecord['ip'], current_config):
            print "Configs updated!"
        else:
            print "Config update failed!"
        return True
    else:
        print_sl(" - No Configuration Changes -\n\n", logfile)
        # print "Configs are the same, do nothing..."
        return True

def template_scan(regtmpl_list, config_list, logfile):
    """ Purpose: To compare a regex list against a config list
        Parameters:
            regtmpl_list    -   List of template set commands with regex
            config_list     -   List of set commands from chassis
            logfile         -   Reference to log object, for displaying and logging output
    """
    nomatch = True
    for regline in regtmpl_list:
        matched = False
        #print "Start using Regex: {0}".format(regline)
        if regline != "":
            for compline in config_list:
                compline = re.sub(r"\\n", r"", compline)
                if re.search(regline, compline):
                    #print "MATCH FOUND!"
                    #print "Regex: {0}".format(regline)
                    #print "Compare String: {0}".format(compline)
                    #time.sleep(5)
                    matched = True
                else:
                    #print "compline: {0}".format(compline)
                    #print "NO MATCH FOUND!"
                    pass
            if not matched:
                #print "Regex Not Matched: {0}".format(regline)
                nomatch = False
                print_sl('Missing: {0}\n'.format(regline), logfile)
        else:
            #print "No Regex!"
            pass
    if nomatch:
        print_sl('- No Template Commands Missing -\n\n', logfile)
    return True

# CHECK CONFIGS AGAINST TEMPLATE
# File to log all changes to
def template_menu():
    # Regexs for template comparisons
    var_regex = '{{[A-Z]+}}'
    d = {
        "{{VERSION}}": r'\d{1,2}\.\d{1,2}[A-Z]\d{1,2}-[A-Z]\d{1,2}\.\d{1,2}',
        "{{HOSTNAME}}": r'SW?[A-Z]{3}\d{3}[A-Z]\d{2}[A-Z]',
        "{{ENCPASS}}": r'\$1\$[A-Z|a-z|\.|\$|\/|\-|\d]{31}',
        "{{TACSECRET}}": r'\$9\$[A-Z|a-z|\.|\$|\/|\-|\d]{18,21}',
        "{{SNMPSECRET}}": r'\$9\$[A-Z|a-z|\.|\$|\/|\-|\d]{184,187}',
        "{{IPADDRESS}}": r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)',
        "{{CITY}}": r'[A-Z][A-Z|a-z|\s]+',
        "{{STATE}}": r'[A-Z]{2}',
        "{{REV}}": r'\d{1,2}\.\d{1,2}',
        "{{TEXT}}": r'.*'
        }

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

    # Create log file for template process
    now = get_now_time()
    template_log = log_dir + "template_log-" + now + ".log"
    # Attempt to open the new log file for input
    try:
        logfile = open(template_log, 'a')
    except Exception as err:
        print "Error opening log file {0}".format(err)
    else:
        print_sl("Purpose: Template Comparison\n", logfile)
        print_sl("User: {0}\n".format(myuser), logfile)
        print_sl("Process Started: {0}\n\n".format(now), logfile)
        # Looping over regtmpl list and comparing to configuration
        for myrecord in listDict:
            config_list = load_config_file_list(myrecord['ip'], newest=True)
            print_sl("-"*41, logfile)
            print_sl("\n***** {0} ({1}) *****\n\n".format(myrecord['host_name'], myrecord['ip']), logfile)
            #print_sl("Site Code: {0}\n\n".format(getSiteCode(myrecord)), logfile)
            #print "SCANNING HOST: {0}".format(myrecord['host_name'])
            if template_scan(regtmpl_list, config_list, logfile):
                print_sl("-"*41, logfile)
                print_sl("\n\n", logfile)
            else:
                print_sl("-"*41, logfile)
                print_sl("\n***** Unable to perfrom template scan of {0} *****\n\n".format(myrecord['ip']), logfile)
        print_sl("\n\nProcess Ended: {0}\n\n".format(get_now_time()), logfile)

def main(argv):
    """ Purpose: Capture command line arguments and populate variables.
        Arguments:
            -c    -  The file containing credentials to be used to access devices
            -i    -  (Optional) A file containing a list of ip addresses (for adding to the database)
            -o    -  (Optional) Can be use to select an optional process, such as template check
    """
    global credsCSV
    global iplistfile
    global addl_opt
    try:
        opts, args = getopt.getopt(argv, "hc:i:o:",["creds=","iplist=","optal="])
    except getopt.GetoptError:
        print "device_refresh -c <credsfile> -i <iplistfile> -o <optional>"
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'device_refresh -c <credsfile> -i <iplistfile> -o <optional>'
            sys.exit()
        elif opt in ("-c", "--creds"):
            credsCSV = arg
        elif opt in ("-i", "--iplist"):
            iplistfile = arg
        elif opt in ("-o", "--optal"):
            addl_opt = arg
    print "Credentials file is:", credsCSV
    print "IP List file is:", iplistfile
    print "Optional function is:", addl_opt

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

    # CHECK CONFIGS FOR CHANGES
    # File to log all changes to
    now = get_now_time()
    change_log = log_dir + "change_log-" + now + ".log"
    try:
        logfile = open(change_log, 'a')
    except Exception as err:
        print "Error opening log file {0}".format(err)
    else:
        print_sl("Purpose: Config Comparison\n", logfile)
        print_sl("User: {0}\n".format(myuser), logfile)
        print_sl("Process Started: {0}\n\n".format(now), logfile)
        for myrecord in listDict:
            print_sl("-"*41, logfile)
            print_sl("\n***** {0} ({1}) *****\n\n".format(myrecord['host_name'], myrecord['ip']), logfile)
            check_ip(str(myrecord['ip']))
            if config_compare(myrecord, logfile):
                #print_sl("***** %s *****\n" % myrecord['ip'], logfile)
                print_sl("-"*41, logfile)
                print_sl("\n\n", logfile)
            else:
                print_sl("-"*41, logfile)
                print_sl("\n***** Unable to connect to {0} *****\n\n".format(myrecord['ip']), logfile)

        # Check optional ip list
        print "IPList File: {0}".format(iplistfile)
        iplist = line_list((iplist_dir + iplistfile))
        if iplist:
            print "Working on IP list..."
            for ip in iplist:
                print "Ping code for {0} : {1}".format(ip, ping(ip))
                '''
                check_ip(str(ip))
                current_config = fetch_config(ip)
                if compare_configs(load_config_file(ip, newest=True), current_config):
                    print "- Configs are different - updating..."
                    if update_config(ip, current_config):
                        print "- Configs updated!"
                    else:
                        print "- Config update failed!"
                else:
                    print "- Do nothing to the config."
                '''
        # End of processing
        print_sl("\n\nProcess Ended: {0}\n\n".format(get_now_time()), logfile)

    print "Optional: " + addl_opt
    if addl_opt == "template":
        template_menu()

    # Save the changes of the listDict to CSV
    listdict_to_csv(listDict, listDictCSV)
    print "Saved any changes."
    print "Completed Work!"