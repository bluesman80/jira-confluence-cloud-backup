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
# 18/01/21 - bluesman80 -   Removed download-only option


import traceback
import time
import re
import logging
import operations

# NOTE: Atlassian imposes a restriction on the initiation of a backup process whereas
# a new process can be initiated after 24 hours

PROGRAM_NAME = 'jira'


def jira_backup(account, attachments, session):
    # Create the full base url for the JIRA instance using the account name.
    account_url = 'https://' + account + '.atlassian.net'

    # Set json data to determine if backup to include attachments.
    json = b'{"cbAttachments": "false", "exportToCloud": "true"}'
    if attachments:
        json = b'{"cbAttachments": "true", "exportToCloud": "true"}'

    error = 'error'
    # Start backup
    try:
        backup_response = session.post(account_url + '/rest/backup/1/export/runbackup', data=json)

        if backup_response.status_code == 200 and error.casefold() not in backup_response.text:
            logging.info('Authentication is successful. Backup is starting...')
        # If there is another backup process running or we hit the backup frequency limit, server returns 412
        elif backup_response.status_code == 412:
            logging.info('Authentication is successful. But...')
            logging.info('Response from server: ' + backup_response.text)
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
    task_req = session.get(account_url + '/rest/backup/1/export/lastTaskId')
    task_id = task_req.text

    # set starting task progress values outside of while loop and if statements.
    task_progress = 0
    last_progress = -1
    sleep_timer = 60
    progress = None

    # Get progress and print update until complete
    while task_progress < 100:
        logging.debug('Monitoring the progress')
        progress = session.get(account_url + '/rest/backup/1/export/getProgress?taskId=' + task_id)

        # Chop just progress update from JSON response
        try:
            task_progress = int(re.search('(?<=progress":)(.*?)(?=,)', progress.text).group(1))
            progress_message = re.search('(?<=message":)(.*?)(?=,)', progress.text).group(1)
            logging.info('Progress message: ' + progress_message)
        except AttributeError:
            logging.error('Backup could not start (AttributeError)')
            logging.error('Response from server: ' + progress.text)
            exit(1)

        if (last_progress != task_progress) and error.casefold() not in progress.text:
            logging.info(f'Progress: {task_progress}%')
            last_progress = task_progress
        elif error.casefold() in progress.text:
            logging.error('Error encountered in response')
            logging.error('Response from server: ' + progress.text)
            exit(1)

        if task_progress < 100:
            time.sleep(sleep_timer)

    file_url = get_file_url_from_progress_response(progress, account_url)

    return file_url


def get_file_url_from_progress_response(progress_response, account_url):
    if type(progress_response) is None:
        return None

    # Get fileName attribute from progress JSON
    # If it does not exist, file_name will be None
    file_name = str(re.search('(?<=result":")(.*?)(?=\",)', progress_response.text))
    if file_name != 'None':
        logging.info('File name found. Preparing URL to download it')
        # Extract the file name from the response text
        file_name = str(re.search('(?<=result":")(.*?)(?=\",)', progress_response.text).group(1))
        file_url = account_url + '/plugins/servlet/' + file_name

        return file_url
    else:
        logging.error('Error in backup file name. File name is not set')
        return None


def main(site=None, user_name=None, api_token=None, attachments=None, folder=None, s3_bucket=None):
    if site is None or user_name is None or api_token is None or folder is None:
        site, user_name, api_token, attachments, folder, s3_bucket = operations.parse_arguments(PROGRAM_NAME)

    logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s',
                        level=logging.INFO,
                        encoding='utf-8',
                        handlers=[
                            logging.FileHandler('jira_backup.log'),
                            logging.StreamHandler()
                        ])

    # Get a session
    session = operations.get_session(user_name, api_token)

    file_url = jira_backup(site, folder, session)

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
