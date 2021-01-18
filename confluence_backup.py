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
# 2021/01/18 - bluesman80 - Removed download-only option


import time
import re
import logging
import traceback
import operations

# NOTE: Atlassian imposes a restriction on the initiation of a backup process whereas
# a new process can be initiated after 24 hours

PROGRAM_NAME = 'confluence'


def conf_backup(account, attachments, session):
    logging.info('Starting a new Confluence backup job.')

    # Set json data to determine if backup to include attachments.
    json = b'{"cbAttachments": "false", "exportToCloud": "true"}'
    if attachments:
        json = b'{"cbAttachments": "true", "exportToCloud": "true"}'

    # Create the full base url for the Confluence instance using the account name.
    account_url = 'https://' + account + '.atlassian.net/wiki'

    error = 'error'
    # Start backup
    try:
        backup_response = session.post(account_url + '/rest/obm/1.0/runbackup', data=json)
        # Catch error response from backup start and exit if error found.

        if backup_response.status_code == 200 and error.casefold() not in backup_response.text:
            logging.info('Authentication is successful. Backup is starting...')
        else:
            logging.error('Backup could not start. Response code: ' + str(backup_response.status_code))
            logging.error('Response from server: ' + backup_response.text)

            # If we hit the backup frequency limit, server returns 406
            if backup_response.status_code == 406:
                logging.info('Hit the limit of backup frequency. Trying to download from the last known location')
                progress = session.get(account_url + '/rest/obm/1.0/getprogress')
                # Can return None here, caller should handle it
                return get_file_name_from_progress_response(progress, account_url)

    except AttributeError:
        logging.error('Backup could not start (AttributeError)')
        logging.error('Response from server: ' + backup_response.text)
        exit(1)
    except Exception:
        logging.error('Backup could not start')
        logging.error(traceback.format_exc())
        exit(1)

    progress = session.get(account_url + '/rest/obm/1.0/getprogress')

    # Check for filename match in response
    file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress.text))

    # If no file name match in JSON response keep outputting progress every 10 seconds
    while file_name == 'None':
        progress = session.get(account_url + '/rest/obm/1.0/getprogress')
        # Regex to extract elements of JSON progress response.
        file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress.text))
        estimated_percentage = str(re.search('(?<=Estimated progress: )(.*?)(?=\")', progress.text))

        # While there is an estimated percentage this will be output.
        if estimated_percentage != 'None':
            # Regex for current status.
            current_status = str(
                re.search('(?<=currentStatus\":\")(.*?)(?=\")', progress.text).group(1))
            # Regex for percentage progress value
            estimated_percentage_value = str(
                re.search('(?<=Estimated progress: )(.*?)(?=\")', progress.text).group(1))
            logging.info('Action: ' + current_status + ' / Overall progress: ' + estimated_percentage_value)
            time.sleep(10)
        # Once no estimated percentage in response the alternative progress is output.
        elif estimated_percentage == 'None':
            # Regex for current status.
            current_status = str(
                re.search('(?<=currentStatus\":\")(.*?)(?=\")', progress.text).group(1))
            # Regex for alternative percentage value.
            alt_percentage_value = str(
                re.search('(?<=alternativePercentage\":\")(.*?)(?=\")', progress.text).group(1))
            logging.info('Action: ' + current_status + ' / Overall progress: ' + alt_percentage_value)
            time.sleep(10)
        # Catch any instance of the of word 'error' in the response and exit script.
        elif error.casefold() in progress.text:
            logging.error('Error encountered in response')
            logging.error('Response from server: ' + progress.text)
            exit(1)

    file_url = get_file_name_from_progress_response(progress, account_url)
    return file_url


def get_file_name_from_progress_response(progress_response, account_url):
    if type(progress_response) is None:
        return None

    # Get fileName attribute from progress JSON
    # If it does not exist, file_name will be None
    file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_response.text))
    if file_name != 'None':
        logging.info('File name found. Preparing URL to download it')
        # Extract the file name from the response text
        file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_response.text).group(1))
        file_url = account_url + '/download/' + file_name

        return file_url
    else:
        logging.error('Error in backup file name. File name is not set')
        return None


def main():
    site, user_name, api_token, attachments, folder, s3_bucket = operations.parse_arguments(PROGRAM_NAME)

    logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s',
                        level=logging.INFO,
                        encoding='utf-8',
                        handlers=[
                            logging.FileHandler('confluence_backup.log'),
                            logging.StreamHandler()
                        ])

    # Get a session
    session = operations.get_session(user_name, api_token)

    file_url = conf_backup(site, attachments, session)

    successful = False
    if file_url is not None:
        logging.info('Backup file URL: ' + file_url)
        logging.info('Backup file is ready to download. Downloading to ' + folder)
        successful = operations.download_backup_and_upload_to_s3(file_url, folder, session, PROGRAM_NAME, s3_bucket)
    else:
        logging.error('Cannot get backup file URL. Aborting.')

    if successful:
        logging.info('Backup job is finished successfully')
    else:
        logging.info('Backup job finished with errors. See the logs.')


if __name__ == '__main__':
    main()
