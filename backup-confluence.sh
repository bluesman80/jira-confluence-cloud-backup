#!/bin/bash

##### UPDATE JUNE 2019: #####
## COOKIE AUTHENTICATION IS BEING REMOVED AND THIS SCRIPT SHOULD STOP WORKING SOON, RETURNING 401 UNAUTHORIZED.
## FOR DETAILS SEE:
# - https://developer.atlassian.com/cloud/jira/platform/deprecation-notice-basic-auth-and-cookie-based-auth/
# - https://confluence.atlassian.com/cloud/deprecation-of-basic-authentication-with-passwords-for-jira-and-confluence-apis-972355348.html
#############################

### PLEASE NOTICE THAT THE SESSION IS CREATED BY CALLING THE JIRA SESSION ENDPOINT!!! ######
#### THE SCRIPT DOES NOT WORK IF JIRA IS NOT INSTALLED !!! #######


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

 

###---SCRIPT-START-----###

echo "Starting the script..."

# Grabs cookies and generates the backup on the UI. ########
### PLEASE NOTICE THAT THE SESSION IS CREATED BY CALLING THE JIRA SESSION ENDPOINT!!! ######
#### THE SCRIPT DOES NOT WORK IF JIRA IS NOT INSTALLED !!! #######
TODAY=$(TZ=$TIMEZONE date +%Y%m%d)
COOKIE_FILE_LOCATION=jiracookie
curl --silent --cookie-jar $COOKIE_FILE_LOCATION -X POST "https://${INSTANCE}/rest/auth/1/session" -d "{\"username\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" -H 'Content-Type: application/json' --output /dev/null

## The $BKPMSG variable will print the error message, you can use it if you're planning on sending an email
BKPMSG=$(curl -s --cookie $COOKIE_FILE_LOCATION --header "X-Atlassian-Token: no-check" -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json"  -X POST https://${INSTANCE}/wiki/rest/obm/1.0/runbackup -d '{"cbAttachments":"true" }' )

 ## Checks if the backup procedure has failed
if [ "$(echo "$BKPMSG" | grep -ic backup)" -ne 0 ]; then
rm $COOKIE_FILE_LOCATION
echo "FAILED, IT RETURNED $BKPMSG"
exit
fi

# Checks if the backup process completed for the number of times specified in PROGRESS_CHECKS variable
for (( c=1; c<=${PROGRESS_CHECKS}; c++ ))
do
PROGRESS_JSON=$(curl -s --cookie $COOKIE_FILE_LOCATION https://${INSTANCE}/wiki/rest/obm/1.0/getprogress.json)
FILE_NAME=$(echo "$PROGRESS_JSON" | sed -n 's/.*"fileName"[ ]*:[ ]*"\([^"]*\).*/\1/p')

##ADDED: PRINT BACKUP STATUS INFO ##
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

# If after the number of configured PROGRESS_CHECKS attempts it still not be completed, it ends the script.
if [ -z "$FILE_NAME" ];
then
rm $COOKIE_FILE_LOCATION
exit
else

## PRINT THE FILE TO DOWNLOAD ##
echo "File to download: $FILE_NAME"

curl -s -L --cookie $COOKIE_FILE_LOCATION "https://${INSTANCE}/wiki/download/$FILE_NAME" -o "$LOCATION/CONF-backup-${TODAY}.zip"

fi
rm $COOKIE_FILE_LOCATION