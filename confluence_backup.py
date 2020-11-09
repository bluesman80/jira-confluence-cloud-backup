# coding=utf-8

# Script created by The Epic Battlebeard 10/08/18
# this script will trigger and download a backup of a CONFLUENCE instance.

# --------- Change log ---------
#
# 2019/11/14 - Script creation
# 2020/11/09 - bluesman80 - Added logging and changed console outputs to logs
#                           Added traceback
#                           Added a feature to save the url of the last backup file to disk
#                           Added a feature to upload the backup file to AWS S3
#                           Added download-only option
#                           Changed the behavior of attachments option (default is false now)
#                           Moved some logic to the main function
#                           Separated common parts between jira and confluence backups
#                           Cleaned-up code

import time
import re
import logging
import traceback
import operations

# Atlassian imposes a restriction on the initiation of a backup process whereas
# a new process can be initiated after 24 hours
# This file is used to save the URL of the latest backup file, so we can try
# to download the latest backup instead of waiting
FILE_LAST_BACKUP_URL = 'last_backup_file_url_confluence.txt'
PROGRAM_NAME = 'confluence'


def conf_backup(account, attachments, session):
    logging.info('Starting a new Confluence backup job.')

    # Set json data to determine if backup to include attachments.
    json = b'{"cbAttachments": "false", "exportToCloud": "true"}'
    if attachments:
        json = b'{"cbAttachments": "true", "exportToCloud": "true"}'

    # Create the full base url for the Confluence instance using the account name.
    url = 'https://' + account + '.atlassian.net/wiki'

    error = 'error'
    # Start backup
    try:
        backup_start = session.post(url + '/rest/obm/1.0/runbackup', data=json)
        # Catch error response from backup start and exit if error found.
        backup_response = int(re.search('(?<=<Response \[)(.*?)(?=\])', str(backup_start)).group(1))

        if backup_response == 200 and error.casefold() not in backup_start.text:
            logging.info('Authentication is successful. Backup is starting...')
        else:
            logging.error('Backup could not start. Response code: ' + str(backup_response))
            logging.error('Response from server: ' + backup_start.text)

            # If we hit the backup init restriction, server returns 406
            if backup_response == 406:
                file_url = operations.get_backup_file_url(FILE_LAST_BACKUP_URL)
                # Can return None here if file does not exist
                return file_url
    except AttributeError:
        logging.error('Backup could not start (AttributeError)')
        logging.error('Response from server: ' + backup_start.text)
        exit(1)
    except Exception:
        logging.error('Backup could not start')
        logging.error(traceback.format_exc())
        exit(1)

    progress_req = session.get(url + '/rest/obm/1.0/getprogress')

    # Check for filename match in response
    file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text))

    # If no file name match in JSON response keep outputting progress every 10 seconds
    while file_name == 'None':
        progress_req = session.get(url + '/rest/obm/1.0/getprogress')
        # Regex to extract elements of JSON progress response.
        file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text))
        estimated_percentage = str(re.search('(?<=Estimated progress: )(.*?)(?=\")', progress_req.text))

        # While there is an estimated percentage this will be output.
        if estimated_percentage != 'None':
            # Regex for current status.
            current_status = str(
                re.search('(?<=currentStatus\":\")(.*?)(?=\")', progress_req.text).group(1))
            # Regex for percentage progress value
            estimated_percentage_value = str(
                re.search('(?<=Estimated progress: )(.*?)(?=\")', progress_req.text).group(1))
            logging.info('Action: ' + current_status + ' / Overall progress: ' + estimated_percentage_value)
            time.sleep(10)
        # Once no estimated percentage in response the alternative progress is output.
        elif estimated_percentage == 'None':
            # Regex for current status.
            current_status = str(
                re.search('(?<=currentStatus\":\")(.*?)(?=\")', progress_req.text).group(1))
            # Regex for alternative percentage value.
            alt_percentage_value = str(
                re.search('(?<=alternativePercentage\":\")(.*?)(?=\")', progress_req.text).group(1))
            logging.info('Action: ' + current_status + ' / Overall progress: ' + alt_percentage_value)
            time.sleep(10)
        # Catch any instance of the of word 'error' in the response and exit script.
        elif error.casefold() in progress_req.text:
            logging.error('Error encountered in response')
            logging.error('Response from server: ' + progress_req.text)
            exit(1)

    # Get filename from progress JSON
    file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text))

    # Check filename is not None
    if file_name != 'None':
        logging.info('Backup process is complete')
        file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text).group(1))
        file_url = url + '/download/' + file_name

        operations.save_backup_file_url(FILE_LAST_BACKUP_URL, file_url)

        logging.info('Backup file can also be downloaded from ' + file_url)

        return file_url
    else:
        logging.error('Error in backup file name. File name is not set.')
        exit(1)


def main():
    site, user_name, api_token, attachments, folder, download_only, s3_bucket = operations.parse_arguments(PROGRAM_NAME)

    logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s',
                        level=logging.INFO,
                        encoding='utf-8',
                        handlers=[
                            logging.FileHandler('confluence_backup.log'),
                            logging.StreamHandler()
                        ])

    # Get a session
    session = operations.get_session(user_name, api_token)

    if download_only:
        logging.info('Download only option is used')
        file_url = operations.get_backup_file_url(FILE_LAST_BACKUP_URL)
    else:
        file_url = conf_backup(site, attachments, session)

    successful = False
    if file_url is not None:
        logging.info('Backup complete, downloading file to ' + folder)
        successful = operations.download_backup_and_upload_to_s3(file_url, folder, session, PROGRAM_NAME, s3_bucket)

    if successful:
        logging.info('Backup job is finished successfully')
    else:
        logging.info('Backup job finished with errors. See the logs.')


if __name__ == '__main__':
    main()
