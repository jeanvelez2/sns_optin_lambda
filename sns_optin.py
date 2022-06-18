import boto3
import re
import json
import os
from botocore.exceptions import ClientError

#Predefined values
REGION = os.environ['AWS_REGION']
sns = boto3.client('sns', region_name=REGION)
result ={}

#Tags|Labels|Properties
message_tag = 'message'
phone_numbers_tag = 'phone_numbers'
success_tag = 'SUCCESS'
failed_tag = 'FAILED'
failed_message_tag = 'FAILED_MESSAGE'
optout_property = 'isOptedOut'

#Messages
sns_all_numbers_optin_message = 'All phone numbers provided were opted-in successfully.'
sns_partial_numbers_optin_message = 'Not all numbers were opted-in, Verify cloudwatch logs to see more details.'
phone_numbers_missing_message = 'Parameter ''phone_numbers'' was not found in Request Body.'
not_found_optedout_message = ' it is not Opted-out.'
failed_message = 'Failed opted-in phone numbers could be due to the following: non-existing or incorrectly formatted phone numbers or phone number does not exist, phone number is not subscribed to AWS SNS, phone number was never opted-out from AWS SNS, phone number last opt-in was implemented in less than 30 days (AWS SNS does not allow to opt-in until 30 days have passed).'

#Lambda Function Handler.
def lambda_handler(event, context):
    body = event['body']

    #Obtain phone number list from Request Body
    phoneNumbers = body[phone_numbers_tag]

    #If phone number list is empty, then return error message
    if len(phoneNumbers) == 0:
        raise ValueError(phone_numbers_missing_message) 
    result_message = opt_in_process(phoneNumbers)
    return { 'statusCode': 200, 'body': json.dumps(result_message) }

#Function that collects and distributes successful and failed Opt-In Phone Numbers.
def opt_in_process(phoneNumbers):
    #Implements iterate_phonenumbers function
    phoneNumberOptInResult = iterate_phonenumbers(phoneNumbers)

    #Sucess and Failed Opted-In Phone Numbers
    optinSuccess = phoneNumberOptInResult[success_tag]
    optinFailed = phoneNumberOptInResult[failed_tag]
    
    if optinFailed != []:        
        #result_message contains:  message, successful opted-in phone numbers, failed opted-in phone numbers
        result_message =  { 
            message_tag: sns_partial_numbers_optin_message, 
            success_tag: optinSuccess,
            failed_tag: optinFailed,
            failed_message_tag: failed_message
        }
    else:
        #Shows all succesful Opted-In Phone Numbers
        result_message = {
            message_tag: sns_all_numbers_optin_message,
            success_tag: optinSuccess,
            failed_tag: optinFailed
        }
    return result_message

#Function that Loops through phone numbers provided in the HTTP Request Body(API) and performs maintenance and opt-in actions.
def iterate_phonenumbers(phoneNumbers):
    #Phone numbers opted-in successfully and failed arrays
    optin_success = []
    optin_failed = []
    
    #Loop through phone number list
    for phoneNumber in phoneNumbers:
        #Implements phone_number_maintenance function and validates if phone number format is correct
        phoneNumberWithAreaCode = phone_number_maintenance(phoneNumber)
        if phoneNumberWithAreaCode == "+":
            optin_failed.append(phoneNumber)
        else:
            #Implements sns_optin_phone_numbers function
            phoneNumberOptInResult = sns_optin_phone_number(phoneNumberWithAreaCode)
            if success_tag in phoneNumberOptInResult:
                optin_success.append(phoneNumberOptInResult[success_tag])
            else:
                optin_failed.append(phoneNumberOptInResult[failed_tag])
            
    return {success_tag: optin_success, failed_tag: optin_failed}

#Function that Implements phone numbers formatting necessary for AWS SNS opt-in process.
def phone_number_maintenance(phoneNumber):
    areaCodeIndex = '+'
    #Remove all non numerical characters from phone number
    phoneNumberClean = re.sub('[^0-9]+', '', phoneNumber)
    if phoneNumberClean != "" and '1' != phoneNumberClean[0]:
        areaCodeIndex = '+1'
    #Return Phone Number with Area Code Index
    return areaCodeIndex + phoneNumberClean

#Function that validates if phone number is Opted-Out in AWS SNS and takes action due to its status.
def sns_optin_phone_number(phoneNumberWithAreaCode):
    #Validates if phone number appears in AWS SNS opted-out list
    response = sns.check_if_phone_number_is_opted_out(phoneNumber = phoneNumberWithAreaCode)
    phoneNumberResult = ''
    #If number wasn't opted-out then it will be added to phoneNumberResult variable
    if response[optout_property] is False:
        #Print Failed Opted-In Phone Number to display in Logs
        phoneNumberResult = { failed_tag: phoneNumberWithAreaCode }
    else:
        try:
            #Opt-In phone number in AWS SNS
            response = sns.opt_in_phone_number(phoneNumber=phoneNumberWithAreaCode)
            phoneNumberResult = { success_tag: phoneNumberWithAreaCode }
            #Print successfuly Opted-In Phone Number to display in Logs
        except ClientError as e:
            #If sns.opt_in_phone_number function gives an exception, then SNS is having problems opting-in phone number
            phoneNumberResult = { failed_tag: phoneNumberWithAreaCode }
    return phoneNumberResult