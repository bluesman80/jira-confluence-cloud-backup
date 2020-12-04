import argparse
import logging
import os
import sys
import time
import traceback
import requests
import s3_operations


def parse_arguments(program):
    parser = argparse.ArgumentParser(program + '_backup')
    parser.add_argument('-s', '--site', help='Site name <account>.atlassian.net', required=True)
    parser.add_argument('-u', '--user', help='An Atlassian account email address with admin rights',
                        required=True)
    parser.add_argument('-t', '--token', help='API token of the Atlassian account', required=True)
    parser.add_argument('-f', '--folder', help='Destination folder for the backup file eg. /folder/sub-folder/',
                        required=True)
    parser.add_argument('-a', '--with-attachments',
                        help='Use this argument to include attachments in the backup. If omitted, attachments will not '
                             'be included ',
                        action='store_true')
    parser.add_argument('-d', '--download-only',
                        help='Use this argument to try downloading the latest backup file without initiating a new '
                             'backup.',
                        action='store_true')
    parser.add_argument('-s3', '--s3-bucket', help='Name of the S3 bucket to upload the backup file. Note that in '
                                                   'to upload to S3, AWS CLI must be installed and configured')

    args = parser.parse_args().__dict__
    return args["site"], \
           args["user"], \
           args["token"], \
           args["with_attachments"], \
           args["folder"], \
           args["download_only"], \
           args["s3_bucket"]


def get_session(username, token):
    # Open new session for cookie persistence and auth.
    session = requests.Session()
    session.auth = (username, token)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return session


def save_backup_file_url(file_name, url):
    # Save the latest backup file url to a file
    try:
        with open(file_name, 'w', encoding='UTF-8') as sf:
            sf.write(url)
    except IOError:
        logging.error(f'Could not save the backup file URL to {file_name}')
    else:
        logging.info(f'Backup file URL is saved to {file_name}')


def get_backup_file_url(file_name):
    if not os.path.isfile(file_name):
        logging.error(f'File does not exist: {file_name}')
        return None

    try:
        with open(file_name, 'r', encoding='UTF-8') as sf:
            file_url = sf.read().strip()
    except IOError:
        logging.error('Cannot read the file URL')
        return None
    else:
        return file_url


def download_backup_and_upload_to_s3(file_url, folder, session, program_name, s3_bucket):
    """Download the backup file from Atlassian and upload it to S3

    :param file_url: URL of the file to download
    :param folder: Full path of the download directory
    :param session: The current https session to be used to download the backup
    :param program_name: jira or confluence
    :param s3_bucket: Name of the S3 bucket to upload the backup file
    :return: True if download and upload succeeds, False if one of them fails
    """

    # Example download URL for Confluence:
    # https://userhappiness.atlassian.net/wiki/download/temp/filestore/8dd92113-7734-4cef-aa1a-ee11537adf7a
    # Example download URL for Jira:
    # https://userhappiness.atlassian.net/plugins/servlet/export/download/?fileId=8fdc0dd6-5af5-48f7-ab92-4b3a51024e40

    if not folder.endswith('/'):
        folder += '/'

    backup_file = program_name + '-export-' + time.strftime('%Y%m%d_%H%M%S') + '.zip'
    full_path = folder + backup_file
    result = False
    try:
        file = session.get(file_url, stream=True)
        file.raise_for_status()

        total_size = file.headers.get('content-length')
        total_size_mb = int(total_size) // 1000000
        logging.info(f'Total size of backup file is {total_size_mb} MB')

        with open(full_path, 'wb') as f:
            # Call performance counter first time to measure the elapsed time at the end
            time.perf_counter()
            logging.info('Downloading...')
            dl = 0
            for chunk in file.iter_content(1024):
                f.write(chunk)
                if total_size is not None:
                    dl += len(chunk)
                    done = int(100 * dl / int(total_size))
                    # Print the download percentage
                    sys.stdout.write("\r[%s%s] %s percent" % ('=' * done, ' ' * (100 - done), str(done)))

        logging.info(f"Download finished in {(time.perf_counter()):.2f} seconds")
    except KeyboardInterrupt:
        logging.info('Download is interrupted by user')
    except Exception:
        logging.error('Error while downloading/saving backup file')
        logging.error(traceback.format_exc())
    finally:
        if os.path.isfile(full_path) and os.stat(full_path).st_size == int(total_size):
            logging.info(backup_file + ' is saved to ' + folder)
            result = True

            if s3_bucket is not None:
                logging.info(f'Uploading {full_path} to {s3_bucket}')
                s3_upload_result = s3_operations.upload(full_path, s3_bucket, os.path.split(full_path)[-1])
                if s3_upload_result:
                    logging.info('Upload to S3 is finished')
                else:
                    logging.error('Upload to S3 failed')
        elif os.stat(full_path).st_size < int(total_size):
            logging.error(traceback.format_exc())
            os.remove(full_path)
        else:
            logging.error('Cannot download backup file')
            logging.error(traceback.format_exc())

        return result
