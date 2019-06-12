#!/bin/bash

##### UPDATE JUNE 2019: #####
## COOKIE AUTHENTICATION IS BEING REMOVED AND THIS SCRIPT SHOULD STOP WORKING SOON, RETURNING 401 UNAUTHORIZED.
## FOR DETAILS SEE:
# - https://developer.atlassian.com/cloud/jira/platform/deprecation-notice-basic-auth-and-cookie-based-auth/
#############################


###--- CONFIGURATION SECTION STARTS HERE ---###
# MAKE SURE ALL THE VALUES IN THIS SECTION ARE CORRECT BEFORE RUNNIG THE SCRIPT
EMAIL=
PASSWORD=
INSTANCE=xxxx.atlassian.net
LOCATION="/path/to/download/folder"

### Checks for progress max 3000 times, waiting 20 seconds between one check and the other ###
# If your instance is big you may want to increase the below values #
PROGRESS_CHECKS=3000
SLEEP_SECONDS=20

# Set this to your Atlassian instance's timezone.
# See this for a list of possible values:
# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIMEZONE=Europe/Amsterdam

###--- END OF CONFIGURATION SECTION ---####

 

##----START-----###

TODAY=$(TZ=$TIMEZONE date +%d-%m-%Y)
echo "starting the script: $TODAY"

# Grabs cookies and starts the backup process 
COOKIE_FILE_LOCATION=jiracookie
curl --silent --cookie-jar $COOKIE_FILE_LOCATION -X POST "https://${INSTANCE}/rest/auth/1/session" -d "{\"username\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" -H 'Content-Type: application/json' --output /dev/null

## The $BKPMSG variable will print the error message, you can use it if you're planning on sending an email
BKPMSG=$(curl -s --cookie $COOKIE_FILE_LOCATION -H "Accept: application/json" -H "Content-Type: application/json" https://${INSTANCE}/rest/backup/1/export/runbackup --data-binary '{"cbAttachments":"true", "exportToCloud":"true"}' )


 
#Checks if the backup procedure has failed
if [ "$(echo "$BKPMSG" | grep -ic error)" -ne 0 ]; then
rm $COOKIE_FILE_LOCATION
echo "BACKUP FAILED, IT RETURNED: $BKPMSG"
exit
fi


# If the backup started correctly it extracts the taskId value from the response
# As an alternative you can call the endpoint /rest/backup/1/export/lastTaskId to get the last task-id
TASK_ID=$(echo "$BKPMSG" | sed -n 's/.*"taskId"[ ]*:[ ]*"\([^"]*\).*/\1/p')


# Checks if the backup process completed for the number of times specified in PROGRESS_CHECKS variable
for (( c=1; c<=${PROGRESS_CHECKS}; c++ ))
do
PROGRESS_JSON=$(curl -s --cookie $COOKIE_FILE_LOCATION https://${INSTANCE}/rest/backup/1/export/getProgress?taskId=${TASK_ID})
FILE_NAME=$(echo "$PROGRESS_JSON" | sed -n 's/.*"result"[ ]*:[ ]*"\([^"]*\).*/\1/p')

##ADDED##
echo "$PROGRESS_JSON"

if [[ $PROGRESS_JSON == *"error"* ]]; then
break
fi

if [ ! -z "$FILE_NAME" ]; then
break
fi

# Waits for the amount of seconds specified in SLEEP_SECONDS variable between a check and the other
sleep ${SLEEP_SECONDS}

done

# If the backup is not ready after the configured amount of PROGRESS_CHECKS, it ends the script.
if [ -z "$FILE_NAME" ];
then
rm $COOKIE_FILE_LOCATION
exit
else

## PRINT THE FILE TO DOWNLOAD ##
echo "File to download: https://${INSTANCE}/plugins/servlet/${FILE_NAME}"

curl -s -L --cookie $COOKIE_FILE_LOCATION "https://${INSTANCE}/plugins/servlet/${FILE_NAME}" -o "$LOCATION/JIRA-backup-${TODAY}.zip"



fi
rm $COOKIE_FILE_LOCATION