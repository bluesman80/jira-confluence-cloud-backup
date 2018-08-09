#!/bin/bash

USERNAME=
PASSWORD=
INSTANCE=
LOCATION="/path/to/download/folder"

### Checks for progress 3000 times every 20 seconds ###
PROGRESS_CHECKS=3000
SLEEP_SECONDS=20

# Set this to your Atlassian instance's timezone.
# See this for a list of possible values:
# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIMEZONE=Europe/Amsterdam
 
##----START-----###
echo "starting the script"

# Grabs cookies and generates the backup on the UI. 
TODAY=$(TZ=$TIMEZONE date +%Y%m%d)
COOKIE_FILE_LOCATION=jiracookie
curl --silent --cookie-jar $COOKIE_FILE_LOCATION -X POST "https://${INSTANCE}/rest/auth/1/session" -d "{\"username\": \"$USERNAME\", \"password\": \"$PASSWORD\"}" -H 'Content-Type: application/json' --output /dev/null

## The $BKPMSG variable will print the error message, you can use it if you're planning on sending an email
BKPMSG=$(curl -s --cookie $COOKIE_FILE_LOCATION -H "Accept: application/json" -H "Content-Type: application/json" https://${INSTANCE}/rest/backup/1/export/runbackup --data-binary '{"cbAttachments":"true", "exportToCloud":"true"}' )


##ADDED##
echo "message: $BKPMSG"

 
#Checks if the backup procedure has failed
if [ "$(echo "$BKPMSG" | grep -ic error)" -ne 0 ]; then
rm $COOKIE_FILE_LOCATION
echo "FAILED, IT RETURNED: $BKPMSG"
exit
fi

TASK_ID=$(curl -s --cookie $COOKIE_FILE_LOCATION -H "Accept: application/json" -H "Content-Type: application/json" https://${INSTANCE}/rest/backup/1/export/lastTaskId)

#Checks if the backup exists every 10 seconds, 2000 times. If you have a bigger instance with a larger backup file you'll probably want to increase that.
for (( c=1; c<=2000; c++ ))
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
sleep 10
done

#If after 2000 attempts it still fails it ends the script.
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