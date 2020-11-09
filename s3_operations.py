import os
import sys
import threading
import boto3
import logging
import traceback


def upload(file_path, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_path: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :returns True if operation succeeds, False otherwise
    """

    # If S3 object_name was not specified, use file_path
    if object_name is None:
        object_name = file_path

    # Upload the file
    s3_client = boto3.client('s3')

    try:
        s3_client.upload_file(file_path, bucket, object_name, Callback=ProgressPercentage(file_path))
        return True
    except:
        logging.error('Error in uploading to S3')
        logging.error(traceback.format_exc())
        return False


class ProgressPercentage(object):

    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            sys.stdout.write("\r%s  (%.2f%%)" % (self._filename, percentage))
            sys.stdout.flush()
