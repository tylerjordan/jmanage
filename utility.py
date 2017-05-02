# File: utility.py
# Author: Tyler Jordan
# Modified: 7/26/2016
# Purpose: Assist CBP engineers with Juniper configuration tasks

import sys, re, os, csv
import fileinput
import glob
import code
import difflib
import operator

from os import listdir
from os.path import isfile, join
from sys import stdout

#--------------------------------------
# ANSWER METHODS
#--------------------------------------


# Method for asking a question that has a single answer, returns answer
def getOptionAnswer(question, options):
    answer = ""
    loop = 0
    while not answer:
        print question + '?:\n'
        for option in options:
            loop += 1
            print '[' + str(loop) + '] -> ' + option
        answer = raw_input('Your Selection: ')
        if int(answer) >= 1 and int(answer) <= loop:
            index = int(answer) - 1
            return options[index]
        else:
            print "Bad Selection"
            loop = 0


# Method for asking a question that has a single answer, returns answer index
def getOptionAnswerIndex(question, options):
    answer = ""
    loop = 0
    while not answer:
        print question + '?:\n'
        for option in options:
            loop += 1
            print '[' + str(loop) + '] -> ' + option
        answer = raw_input('Your Selection: ')
        if int(answer) >= 1 and int(answer) <= loop:
            return answer
        else:
            print "Bad Selection"
            loop = 0


# Method for asking a user input question
def getInputAnswer(question):
    answer = ""
    while not answer:
        answer = raw_input(question + '?: ')
    return answer


# Method for asking a Y/N question
def getYNAnswer(question):
    answer = ""
    while not answer:
        answer = raw_input(question + '?(y/n): ')
        if answer == 'Y' or answer == 'y':
            answer = 'y'
        elif answer == 'N' or answer == 'n':
            answer = 'n'
        else:
            print "Bad Selection"
            answer = ""
    return answer


# Return list of files from a directory
def getFileList(mypath):
    fileList = []
    try:
        for afile in listdir(mypath):
            if isfile(join(mypath,afile)):
                fileList.append(afile)
    except:
        print "Error accessing directory: " + mypath

    return fileList


# Method for requesting IP address target
def getTarget():
    print 64*"="
    print "= Scan Menu                                                    ="
    print 64*"="
    # Loop through the IPs from the file "ipsitelist.txt"
    loop = 0
    list = {};
    for line in fileinput.input('ipsitelist.txt'):
        # Print out all the IPs/SITEs
        loop += 1
        ip,site = line.split(",")
        list[str(loop)] = ip;
        print '[' + str(loop) + '] ' + ip + ' -> ' + site.strip('\n')

    print "[c] Custom IP"
    print "[x] Exit"
    print "\n"

    response = ""
    while not response:
        response = raw_input("Please select an option: ")
        if response >= "1" and response <= str(loop):
            return list[response]
        elif response == "c":
            capturedIp = ""
            while not capturedIp:
                capturedIp = raw_input("Please enter an IP: ")
                return capturedIp
        elif response == "x":
            response = "exit"
            return response
        else:
            print "Bad Selection"

# Takes a text string and creates a top level heading
def topHeading(rawtext, margin):
    head_length = len(rawtext)
    equal_length = head_length + 6

    heading = " " * margin + "+" + "=" * equal_length + "+\n" +\
              " " * margin + "|   " + rawtext + "   |\n" +\
              " " * margin + "+" + "=" * equal_length + "+\n"

    return heading

# Takes a string and creates a sub heading
def subHeading(rawtext, margin):
    head_length = len(rawtext)
    dash_length = head_length + 2

    heading = " " * margin + "o" + "-" * dash_length + "o\n" +\
              " " * margin + "| " + rawtext + " |\n" +\
              " " * margin + "o" + "-" * dash_length + "o\n"

    return heading

# Common method for accessing multiple routers
def chooseDevices():
    # Define the routers to deploy the config to (file/range/custom)
    print "**** Configuration Deployment ****"
    method_resp = getOptionAnswer('How would you like to define the devices', ['file', 'range', 'custom'])
    ip_list = []
    # Choose a file from a list of options
    if method_resp == "file":
        print "Defining a file..."
        path = '.\ips\*.ips'
        files=glob.glob(path)
        file_resp = getOptionAnswer('Choose a file to use', files)

        # Print out all the IPs/SITEs
        for line in fileinput.input(file_resp):
            ip_list.append(line)

    # Define a certain range of IPs
    elif method_resp == "range":
        print "Defining a range..."

    # Define one or more IPs individually
    elif method_resp == "custom":
        print 'Define using /32 IP Addresses'
        answer = ""
        while( answer != 'x' ):
            answer = getInputAnswer('Enter an ip address (x) to exit')
            if( answer != 'x'):
                ip_list.append(answer)

    # Print the IPs that will be used
    loop = 1;
    for my_ip in ip_list:
        print 'IP' + str(loop) + '-> ' + my_ip
        loop=loop + 1

    return ip_list

# Convert listDict to CSV file
def listdict_to_csv(listDict, filePathName, fieldNames):
    try:
        with open(filePathName, 'wb') as csvfile:
            writer = csv.DictWriter(csvfile, fieldNames)
            writer.writeheader()
            writer.writerows(listDict)
        return True
    except Exception as err:
        print "ERROR: Problem writing to file {0} : {1}".format(filePathName, err)
        return False


# Converts CSV file to listDict
def csv_to_listdict(filePathName):
    emptyList = []
    try:
        with open(filePathName) as csvfile:
            listDict = [{csvfile: v for csvfile, v in row.items()}
                        for row in csv.DictReader(csvfile, skipinitialspace=True)]
        return listDict
    except IOError as err:
        print "Database file not found: Using empty database."
        return emptyList

    except Exception as err:
        print "Non-IOError problem with: {0} ERROR: {1}".format(filePathName, err)
        return emptyList


# Converts CSV file to Dictionary
def csv_to_dict(filePathName):
    input_file = csv.DictReader(open(filePathName))
    for row in input_file:
        return row


# Apply lines to CSV, then sort it, newest entries first ** USES SEMICOLONs **
def add_to_csv_sort(listkey, contentList, storageList):

    '''
        READ IN THE EXISTING CSV FILE AS A LISTDICT, IF IT EXISTS. ADD THE NEW LOG CONTENT TO THE LIST DICT, SORT IT,
        THEN WRITE LISTDICT TO CSV.
    '''

    # Add to csv file
    print_log(entry, csv_file)

    # Check that the file exists
    if os.path.isfile(csv_file):
        # Opens the file for reading only, places pointer at beginning
        with open(csv_file, "r") as f:
            reader = csv.reader(f, delimiter=";")
            try:
                # Attempt to sort the contents, sorting by the third column values, from newest to oldest
                sortedlist = sorted(reader, key=operator.itemgetter(2), reverse=True)
            except Exception as err:
                print "Issue sorting file -> ERROR: {0}".format(err)
                return False
            else:
                try:
                    # Opens the file and overwrites if it already exists
                    with open(csv_file, "w") as f:
                        # This writes the newly sorted data to the file
                        fileWriter = csv.writer(f, delimiter=';')
                        for row in sortedlist:
                            fileWriter.writerow(row)
                except Exception as err:
                    print "Issue writing to file -> ERROR: {0}".format(err)
                    return False
                else:
                    return True
    else:
        print "File does not exist - {0}".format(csv_file)
        return False


# Analyze listDict and create statistics (Upgrade)
def tabulateUpgradeResults(listDict):
    statusDict = {'success_rebooted': [],'success_not_rebooted': [], 'connect_fails': [], 'software_install_fails': [], 'total_devices': 0}

    for mydict in listDict:
        if mydict['Connected'] == 'Y' and mydict['OS_installed'] == 'Y':
            if mydict['Rebooted'] == 'Y':
                statusDict['success_rebooted'].append(mydict['IP'])
            else:
                statusDict['success_not_rebooted'].append(mydict['IP'])
        elif mydict['Connected'] == 'Y' and mydict['OS_installed'] == 'N':
            statusDict['software_install_fails'].append(mydict['IP'])
        elif mydict['Connected'] == 'N':
            statusDict['connect_fails'].append(mydict['IP'])
        else:
            print("Error: Uncaptured Result")
        # Every device increments this total
        statusDict['total_devices'] += 1

    return statusDict


# Analyze listDict and create statistics (Reboot)
def tabulateRebootResults(listDict):
    statusDict = {'rebooted': [], 'not_rebooted': [], 'connect_fails': [], 'total_devices': 0}

    for mydict in listDict:
        if mydict['Connected'] == 'Y':
            if mydict['Rebooted'] == 'Y':
                statusDict['rebooted'].append(mydict['IP'])
            else:
                statusDict['not_rebooted'].append(mydict['IP'])
        elif mydict['Connected'] == 'N':
            statusDict['connect_fails'].append(mydict['IP'])
        else:
            print("Error: Uncaptured Result")
        # Every device increments this total
        statusDict['total_devices'] += 1

    return statusDict

def compare_configs(config1, config2):
    """ Purpose: To compare two configs and get the changes.
        Returns: True means there are differences, false means they are the same.
    """
    change_list = []
    if config1 and config2:
        config1_lines = config1.splitlines(1)
        config2_lines = config2.splitlines(1)

        diffInstance = difflib.Differ()
        diffList = list(diffInstance.compare(config1_lines, config2_lines))

        #print '-'*50
        #print "Lines different in config1 from config2:"
        for line in diffList:
            if line[0] == '-':
                change_list.append(line)
                #print line,
            elif line[0] == '+':
                change_list.append(line)
                #print line,
        #print '-'*50
    else:
        print "ERROR with compare configs, check configs."
    return change_list

# Print output to the screen and a log file (either a list or string)
def print_sl(statement, file_list):
    # Print to screen
    stdout.write(statement)
    # Print to log
    if type(file_list) is list:
        for log in file_list:
            print_log(statement, log)
    else:
        print_log(statement, file_list)

# Print output to log file only
def print_log(statement, logfile):
    # Print to log
    #print "Log File: {0}".format(logfile)
    try:
        logobj = open(logfile, 'a')
    except Exception as err:
        print "Error opening log file {0}".format(err)
    else:
        logobj.write(statement)
        logobj.close()