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
import multiprocessing

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
dir_path = ''

addl_opt = ''
listDict = []
mypwd = ''
myuser = ''
port = 22


def detect_env():
    """ Purpose: Detect OS and create appropriate path variables. """
    global template_file
    global listDictCSV
    global credsCSV
    global iplist_dir
    global config_dir
    global log_dir
    global dir_path

    dir_path = os.path.dirname(os.path.abspath(__file__))
    if platform.system().lower() == "windows":
        #print "Environment Windows!"
        listDictCSV = os.path.join(dir_path, "data\\listdict.csv")
        iplist_dir = os.path.join(dir_path, "data\\iplists")
        config_dir = os.path.join(dir_path, "data\\configs")
        log_dir = os.path.join(dir_path, "data\\logs")
        template_file = os.path.join(dir_path, config_dir, "Template.conf")
    else:
        #print "Environment Linux/MAC!"
        listDictCSV = os.path.join(dir_path, "data/listdict.csv")
        iplist_dir = os.path.join(dir_path, "data/iplists")
        config_dir = os.path.join(dir_path, "data/configs")
        log_dir = os.path.join(dir_path, "data/logs")
        template_file = os.path.join(dir_path, config_dir, "Template.conf")

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
        my_dir = os.path.join(config_dir, getSiteCode(record), record['host_name'])
        if os.path.exists(my_dir):
            try:
                for file in listdir(my_dir):
                    if file.startswith(record['host_name']):
                        filtered_list.append(os.path.join(my_dir, file))
                sorted_list = sorted(filtered_list, key=os.path.getctime)
            except Exception as err:
                print "Issue"
            if sorted_list:
                if newest:
                    return sorted_list[-1]
                else:
                    return sorted_list[0]
            else:
                return sorted_list
        # Returns an empty list, if directory doesn't exist
        else:
            return filtered_list


def get_file_number(record):
    file_num = 0
    if record:
        my_dir = os.path.join(config_dir, getSiteCode(record), record['host_name'])
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
    if os.path.isdir(os.path.join(config_dir, getSiteCode(record), record['host_name'])):
        return True
    else:
        try:
            os.mkdir(os.path.join(config_dir, getSiteCode(record), record['host_name']))
        except Exception as err:
            print "Failed Creating Directory -> ERROR: {0}".format(err)
            return False
        else:
            return True

    '''
    try:
        site_dir = os.path.join(config_dir, getSiteCode(record), record['host_name'])
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
    site_dir = os.path.join(config_dir, getSiteCode(record), record['host_name'])
    filename = record['host_name'] + "_" + now + ".conf"
    fileandpath = os.path.join(site_dir, filename)
    try:
        newfile = open(fileandpath, "w+")
    except Exception as err:
        print 'ERROR: Unable to open file: {0} | File: {1}'.format(err, fileandpath)
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


def check_ip(ip, logfile):
    """ Purpose: Scans the device with the IP and handles action. """
    has_record = False
    #print "Recalling any stored records..."
    if get_record(ip):
        has_record = True
    record_attribs = [ 'serial_number', 'model', 'host_name', 'junos_code' ]

    returncode = 1
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
                        print_sl("No Parameter Changes\n", logfile)
                        returncode = 0
                    else:
                        print_sl("\t- JunOS changed from {0} to {1}\n".format(localDict['junos_code'], remoteDict['junos_code']), logfile)
                        change_record(ip, remoteDict['junos_code'], key='junos_code')
                else:
                    print_sl("\t- S/N changed from {0} to {1}\n".format(localDict['serial_number'], remoteDict['serial_number']), logfile)
                    change_record(ip, remoteDict['serial_number'], key='serial_number')
                    if localDict['model'] != remoteDict['model']:
                        print_sl("\t- Model changed from {0} to {1}\n".format(localDict['model'], remoteDict['model']), logfile)
                        change_record(ip, remoteDict['model'], key='model')
                    if localDict['junos_code'] != remoteDict['junos_code']:
                        print_sl("\t- JunOS changed from {0} to {1}\n".format(localDict['junos_code'], remoteDict['junos_code']), logfile)
                        change_record(ip, remoteDict['junos_code'], key='junos_code')
            else:
                if localDict['serial_number'] != remoteDict['serial_number']:
                    print_sl("\t- S/N changed from {0} to {1}\n".format(localDict['serial_number'], remoteDict['serial_number']), logfile)
                    change_record(ip, remoteDict['serial_number'], key='serial_number')
                    if localDict['model'] != remoteDict['model']:
                        print_sl("\t- Model changed from {0} to {1}\n".format(localDict['model'], remoteDict['model']), logfile)
                        change_record(ip, remoteDict['model'], key='model')
                # Do these regardless of S/N results
                print_sl("\t- Hostname changed from {0} to {1}\n".format(localDict['host_name'], remoteDict['host_name']), logfile)
                change_record(ip, remoteDict['host_name'], key='host_name')
                if localDict['junos_code'] != remoteDict['junos_code']:
                    print_sl("\t- JunOS changed from {0} to {1}".format(localDict['junos_code'], remoteDict['junos_code']), logfile)
                    change_record(ip, remoteDict['junos_code'], key='junos_code')
        else:
            # If no, this is a device that hasn't been identified yet, create a new record
            print_sl("\t- Adding device {0} as a new record\n".format(ip), logfile)
            if add_record(ip):
                print_sl("\t- Successfully added record\n", logfile)
            else:
                print_sl("\t- Failed adding record\n", logfile)
    else:
        print_sl("\t- ERROR: Unable to collect information from device: {0}\n".format(ip), logfile)
    #print "Checking config..."

    return returncode

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
        return has_record

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
            print '\t- Configuration retrieved and saved'.format(ip)
        else:
            items['last_config_attempt'] = get_now_time()
            items['last_update_attempt'] = get_now_time()
            items['last_update_success'] = get_now_time()
            print '\t- Configuration retrieved, but save failed'.format(ip)
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
        print '\t- ERROR: Device was reachable, the information was not found.'
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
        print '\t- ERROR: Unable to connect to device: {0} on port: {1}'.format(ip, port)
        return False
    except errors.AuthenticationError:
        print '\t- ERROR: Bad username or password for device: {0}'.format(ip)
        return False
    except Exception as err:
        print '\t- ERROR: Unable to connect to device: {0} with error: {1}'.format(ip, err)
        return False
    else:
        software_info = connection.get_software_information(format='xml')
        host_name = software_info.xpath('//software-information/host-name')[0].text
        output = information(connection, ip, software_info, host_name)
        #print "Print Configuration"
        #print connection.get_config(source='running', format='set')
        return output

def config_compare(record, logfile):
    """ Purpose: To compare two configs and get the differences, log them
        Parameters:
            record          -   Object that contains parameters of devices
            logfile         -   Reference to log object, for displaying and logging output
    """
    returncode = 1

    # Check if the appropriate site directory is created. If not, then create it.

    loaded_config = load_config_file(record['ip'], newest=True)
    if not directory_check(record) or not loaded_config:
        if save_config_file(fetch_config(record['ip']), record):
            print_sl("No Existing Config, Configuration Saved\n", logfile)
        else:
            print_sl("No Existing Config, Configuration Save Failed\n", logfile)
    else:
        current_config = fetch_config(record['ip'])
        change_list = compare_configs(loaded_config, current_config)
        if change_list:
            # print "Configs are different - updating..."
            print_sl("Found Configuration Changes\n", logfile)
            print_sl("-" * 50 + "\n", logfile)
            # Try to write diffList output to a file
            for item in change_list:
                print_sl("{0}".format(item), logfile)
            if update_config(record['ip'], current_config):
                print_sl("\n[ New Config Uploaded ]\n", logfile)
            else:
                print_sl("\n[ Config Update Failed ]\n", logfile)
            print_sl("-" * 50 + "\n", logfile)
            return True
        else:
            print_sl("No Configuration Changes\n", logfile)
            returncode = 0

    return returncode

def template_scanner(regtmpl_list, myrecord, logfile):
    """ Purpose: To compare a regex list against a config list
        Parameters:
            regtmpl_list    -   List of template set commands with regex
            config_list     -   List of set commands from chassis
            logfile         -   Reference to log object, for displaying and logging output
    """
    returncode = 1
    config_list = load_config_file_list(myrecord['ip'], newest=True)

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
                        print_sl('Template Commands Missing\n', logfile)
                        print_sl("-" * 50 + "\n", logfile)
                        firstpass = False
                    nomatch = False
                    print_sl('{0}\n'.format(regline), logfile)
        if nomatch:
            print_sl('No Template Commands Missing\n\n', logfile)
            returncode = 0
            return returncode
    except Exception as err:
        print_sl("\n***** Unable to perfrom template scan of {0} *****\n\n".format(myrecord['ip']), logfile)
        print_sl("-" * 50 + "\n\n", logfile)
    else:
        print_sl("-" * 50 + "\n\n", logfile)

    return returncode

def template_regex():
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

    return regtmpl_list

# Print summary results to log file
def summaryLog(myuser, total_devices, addl_opt, all_log_names, param_change_total, config_change_total, templ_change_total, param_change_ips, config_change_ips, templ_change_ips):
    # Create log file for scan results summary
    now = get_now_time()
    sum_name = "results_summary-" + now + ".log"
    sumfile = os.path.join(log_dir, sum_name)

    # Write the scan results to a text file
    print_log(subHeading("Scan Results Summary", 5), sumfile)
    print_log("-" * 50 + "\n", sumfile)
    print_log("Username: " + myuser + "\n", sumfile)
    print_log("Logs:\n", sumfile)
    for log_name in all_log_names:
        print_log("\t- {0}\n".format(log_name), sumfile)

    print_log("-" * 50 + "\n\n", sumfile)
    print_log("=" * 50 + "\n", sumfile)
    print_log("Parameters Changed (" + str(param_change_total) + " of " + str(total_devices) + ")\n", sumfile)
    print_log("-" * 50 + "\n", sumfile)
    if len(param_change_ips) == 0:
        print_log("\t * No Devices *\n", sumfile)
    else:
        for ip in param_change_ips:
            print_log("\t- " + ip + "\n", sumfile)
    print_log("\n" + "=" * 50 + "\n", sumfile)
    print_log("Configurations Changed (" + str(config_change_total) + " of " + str(total_devices) + ")\n", sumfile)
    print_log("-" * 50 + "\n", sumfile)
    if len(config_change_ips) == 0:
        print_log("\t * No Devices *\n", sumfile)
    else:
        for ip in config_change_ips:
            print_log("\t- " + ip + "\n", sumfile)
    if addl_opt == "template":
        print_log("\n" + "=" * 50 + "\n", sumfile)
        print_log("Template Mismatches (" + str(templ_change_total) + " of " + str(total_devices) + ")\n", sumfile)
        print_log("-" * 50 + "\n", sumfile)
        if len(templ_change_ips) == 0:
            print_log("\t * No Devices *\n", sumfile)
        else:
            for ip in templ_change_ips:
                print_log("\t- " + ip + "\n", sumfile)
    print_log("-" * 50 + "\n\n", sumfile)


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
    myfile = os.path.join(dir_path, credsCSV)
    creds = csv_to_dict(myfile)
    myuser = creds['username']
    mypwd = creds['password']

    # Load records from existing CSV
    #print "Loading records..."
    listDict = csv_to_listdict(listDictCSV)

    # Running change log file
    run_change_log = os.path.join(log_dir, "run_change_log.csv")

    # Create log file for parameter and config details
    all_log_paths = []
    all_log_names = []
    now = get_now_time()
    conf_name = "conf_log-" + now + ".log"
    conf_log = os.path.join(log_dir, conf_name)
    all_log_paths.append(conf_log)
    all_log_names.append(conf_name)

    # Create log file for template details, if necessary
    if addl_opt == "template":
        templ_name = "templ_log-" + now + ".log"
        templ_log = os.path.join(log_dir, templ_name)
        all_log_paths.append(templ_log)
        all_log_names.append(templ_name)

    # CHECK CONFIGS FOR CHANGES
    print_sl("\n\n" + topHeading("SCAN DEVICES", 5), all_log_paths)
    print_sl("-" * 50 + "\n", all_log_paths)
    print_sl("User: {0}\n".format(myuser), all_log_paths)
    print_sl("Process Started: {0}\n".format(now), all_log_paths)
    print_sl("-" * 50 + "\n", all_log_paths)

    # Loads new IPs into the database, must specify in command line arguments " -o <file> "
    print_sl("\n" + subHeading("Add New Devices", 5), [conf_log])
    print_sl("-" * 50 + "\n", [conf_log])

    if iplistfile:
        iplist = line_list(os.path.join(iplist_dir, iplistfile))
        # Loop over the list of new IPs
        for raw_ip in iplist:
            ip = raw_ip.strip()
            print_sl("\n----- [{0}] -----\n".format(ip), [conf_log])
            # If a record doesn't exist, try to create one
            if not get_record(ip):
                # Make sure you can ping the device before trying to configure
                print_sl("\t- Device is not in the database\n", [conf_log])
                if ping(ip):
                    check_ip(ip, [conf_log])
                else:
                    print_sl("\t- Unable to ping device - skipping\n", [conf_log])
            else:
                print_sl("\t- Device is already in database - skipping\n", [conf_log])
    else:
        print_sl("\n - No New IPs Specified -\n\n", [conf_log])
    print_sl("-" * 50 + "\n\n", [conf_log])
    # Performs the parameter check, configuration check, and template check
    print_sl("\n" + subHeading("Check Devices", 5), [conf_log])
    print_sl("-" * 50 + "\n", [conf_log])

    total_devices = len(listDict)
    param_change_total = 0
    param_change_ips = []
    config_change_total = 0
    config_change_ips = []
    templ_change_total = 0
    templ_change_ips = []

    # Parameter/Configuration/Template Check loop
    for record in listDict:
        print_sl("\n" + "=" * 50 + "\n", all_log_paths)
        print_sl("***** {0} ({1}) *****\n".format(record['host_name'], record['ip']), all_log_paths)
        print_sl("=" * 50 + "\n", all_log_paths)
        # Run parameter check: return (0) = no parameter change, (1) = parameter change
        if directory_check(record):
            device_dir = os.path.join(config_dir, getSiteCode(record), record['host_name'])
            if ping(record['ip']):
                print_sl
                try:
                    print_sl("Parameter Check: ", [conf_log])
                    if check_ip(str(record['ip']), conf_log):
                        param_change_total += 1
                        param_change_ips.append(record['host_name'] + " (" + record['ip'] + ")")
                except Exception as err:
                    print_sl("Error with parameter check: {0}/n".format(err), [conf_log])
                # Run configuration check: return (0) = no config change, (1) = config change
                try:
                    print_sl("Configuration Check: ", [conf_log])
                    if config_compare(record, conf_log):
                        config_change_total += 1
                        config_change_ips.append(record['host_name'] + " (" + record['ip'] + ")")
                        add_to_csv_sort(record['ip'] + "," + record['host_name'] + "," + now, run_change_log)
                except Exception as err:
                    print_sl("Error with configuration check: {0}/n".format(err), [conf_log])
                # Check if template was specified: return (0) = no template discrepancy, (1) = discrepancies
                if addl_opt == "template":
                    print_sl("Template Check: ", [templ_log])
                    # Run template check
                    if template_scanner(template_regex(), record, templ_log):
                        templ_change_total += 1
                        templ_change_ips.append(record['host_name'] + " (" + record['ip'] + ")")
            else:
                print_sl("\n\t- Unable to ping device - skipping/n/n", all_log_paths)
                print_log("{0}: Unable to ping @ {1}/n".format(now, record['ip']), device_log)
    # End of processing
    print_sl("Process Ended: {0}\n\n".format(get_now_time()), all_log_paths)

    # Print brief results to screen
    print subHeading("Scan Results", 5)
    print"=============================="
    print"Total Number of Devices....{0}".format(total_devices)
    print"=============================="
    print"Devices with..."
    print"------------------------------"
    print"Parameters Changed.........{0}".format(param_change_total)
    print"Configs Changed............{0}".format(config_change_total)
    if addl_opt == "template":
        print"Template Mismatches........{0}".format(templ_change_total)
    print"==============================\n"

    # Print results  to summary file
    if summaryLog(myuser, total_devices, addl_opt, all_log_names, param_change_total, config_change_total, templ_change_total, param_change_ips, config_change_ips,
               templ_change_ips):
        print "\nResults file completed"

    # Save the changes of the listDict to CSV
    if listDict:
        listdict_to_csv(listDict, listDictCSV)
        print "\nSaved any changes. We're done!"
    else:
        print "\nNo content in database. Exiting!"
