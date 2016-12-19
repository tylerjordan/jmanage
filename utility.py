# File: utility.py
# Author: Tyler Jordan
# Modified: 7/26/2016
# Purpose: Assist CBP engineers with Juniper configuration tasks

import sys, re, os, csv
import fileinput
import glob
import code
import difflib

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


# Converts listDict to CSV file
def listDictCSV(myListDict, filePathName, keys):
    addKeys = True
    if (os.path.isfile(filePathName)):
        addKeys = False
    try:
        f = open(filePathName, 'a')
    except:
        print "ERROR: Failure opening file in append mode.\n"
        print("Be sure {0} isn't open in another program.".format(filePathName))
    else:
        if addKeys:
            #Write all the headings in the CSV
            for akey in keys[:-1]:							# Runs for every element, except the last
                f.write(akey + ",")							# Writes most elements
            f.write(keys[-1])								# Writes last element
            f.write("\n")

        for part in myListDict:
            for bkey in keys[:-1]:
                #print "Key: " + bkey + "  Value: " + str(part[bkey])
                f.write(str(part[bkey]) + ",")
            f.write(str(part[keys[-1]]))
            f.write("\n")
        f.close()
        print "\nCompleted appending to CSV."


# Convert listDict to CSV file
def listdict_to_csv(listDict, filePathName):
    try:
        fieldNames = listDict[0].keys()
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
    except Exception as err:
        print "ERROR: Problem reading from file {0} : {1}".format(filePathName, err)
        return emptyList


# Converts CSV file to Dictionary
def csv_to_dict(filePathName):
    input_file = csv.DictReader(open(filePathName))
    for row in input_file:
        pass
    return row


# Gets a target code
def getCode(device, mypath):
    tar_code = ""

    # Does not have a target code, let's ask for one
    print("\n" + "*"*10)
    print("Hostname: " + device.hostname)
    print("IP: " + device.ip)
    print("Model: " + device.model)
    print("Current Code: " + device.curr_code)

    fileList = getFileList(mypath)
    if fileList:
        tar_code = getOptionAnswer("Choose an image", fileList)
    else:
        print("No images available.")
    print("*"*10 + "\n")

    return tar_code


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
                print line,
            elif line[0] == '+':
                change_list.append(line)
                print line,
        #print '-'*50
    else:
        print "ERROR with compare configs, check configs."
    return change_list

def print_sl(statement, logobj):
    # Print to log
    logobj.write(statement)
    # Print to screen
    stdout.write(statement)
