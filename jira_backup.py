# coding=utf-8

# Script created by The Epic Battlebeard 10/08/18
# this script will trigger and download a backup of a JIRA instance.

# --------- Change log ---------
#
# 13/08/18 - NKW - Added help text function, changed string manipulation from substring to regex for consistency.
# 14/08/18 - NKW - Changed to interactive so can still accept input after compilation. (may change to command line args).
# 01/10/18 - NKW - Added argparser to run from command line.
# 09/11/20 - bluesman80 -   Added logging and changed console outputs to logs
#                           Added traceback
#                           Added a feature to save the url of the last backup file to disk
#                           Added a feature to upload the backup file to AWS S3
#                           Added download-only option
#                           Changed the behavior of attachments option (default is false now)
#                           Moved some logic to the main function
#                           Separated common parts between jira and confluence backups
#                           Cleaned-up code

import traceback
import time
import re
import logging
import operations

# Atlassian imposes a restriction on the initiation of a backup process whereas
# a new process can be initiated after 24 hours
# This file is used to save the URL of the latest backup file, so we can try
# to download the latest backup instead of waiting
FILE_LAST_BACKUP_URL = 'last_backup_file_url_jira.txt'
PROGRAM_NAME = 'jira'


def jira_backup(account, attachments, session):
    # Create the full base url for the JIRA instance using the account name.
    url = 'https://' + account + '.atlassian.net'

    # Set json data to determine if backup to include attachments.
    json = b'{"cbAttachments": "false", "exportToCloud": "true"}'
    if attachments:
        json = b'{"cbAttachments": "true", "exportToCloud": "true"}'

    error = 'error'
    # Start backup
    try:
        backup_response = session.post(url + '/rest/backup/1/export/runbackup', data=json)

        if backup_response.status_code == 200 and error.casefold() not in backup_response.text:
            logging.info('Authentication is successful. Backup is starting...')
        # If we hit the backup init restriction, server returns 406
        elif backup_response.status_code == 406:
            file_url = operations.get_backup_file_url(FILE_LAST_BACKUP_URL)
            # Can return None here if file does not exist
            return file_url
        # If there is another backup process running, server returns 412
        elif backup_response.status_code == 412:
            logging.info('Another backup is in progress')
        else:
            logging.error('Backup could not start. Response code: ' + str(backup_response.status_code))
            logging.error('Response from server: ' + backup_response.text)
    except AttributeError:
        logging.error('Backup could not start (AttributeError)')
        logging.error('Response from server: ' + backup_response.text)
        exit(1)
    except Exception:
        logging.error('Backup could not start')
        logging.error(traceback.format_exc())
        exit(1)

    # Get task ID of backup.
    task_req = session.get(url + '/rest/backup/1/export/lastTaskId')
    task_id = task_req.text

    # set starting task progress values outside of while loop and if statements.
    task_progress = 0
    last_progress = -1
    sleep_timer = 10
    counter = 0
    progress_response = None

    # Get progress and print update until complete
    while task_progress < 100:
        logging.debug('Monitoring the progress')
        progress_response = session.get(url + '/rest/backup/1/export/getProgress?taskId=' + task_id)

        # Chop just progress update from JSON response
        try:
            task_progress = int(re.search('(?<=progress":)(.*?)(?=,)', progress_response.text).group(1))
            progress_message = re.search('(?<=message":)(.*?)(?=,)', progress_response.text).group(1)
            logging.info('Progress message: ' + progress_message)
        except AttributeError:
            logging.error('Backup could not start (AttributeError)')
            logging.error('Response from server: ' + progress_response.text)
            exit(1)

        if (last_progress != task_progress) and error.casefold() not in progress_response.text:
            logging.info(f'Progress: {task_progress}%')
            last_progress = task_progress
            counter = 0
            sleep_timer = 10
        elif error.casefold() in progress_response.text:
            logging.error('Error encountered in response')
            logging.error('Response from server: ' + progress_response.text)
            exit(1)

        # Gradually increase the task progress check interval if the percentage does not change
        counter += 1
        if counter == 3:
            sleep_timer = 20
        elif counter == 4:
            sleep_timer = 30
        elif counter == 6:
            sleep_timer = 60

        if task_progress < 100:
            time.sleep(sleep_timer)

    file_name = re.search('(?<=result":")(.*?)(?=\",)', progress_response.text).group(1)
    file_url = url + '/plugins/servlet/' + file_name

    operations.save_backup_file_url(FILE_LAST_BACKUP_URL, file_url)
    logging.info('Backup file can also be downloaded from ' + file_url)

    return file_url


def main():
    site, user_name, api_token, attachments, folder, download_only, s3_bucket = operations.parse_arguments(PROGRAM_NAME)

    logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s',
                        level=logging.INFO,
                        encoding='utf-8',
                        handlers=[
                            logging.FileHandler('jira_backup.log'),
                            logging.StreamHandler()
                        ])

    # Get a session
    session = operations.get_session(user_name, api_token)

    if download_only:
        logging.info('Download only option is used')
        file_url = operations.get_backup_file_url(FILE_LAST_BACKUP_URL)
    else:
        file_url = jira_backup(site, folder, session)

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
