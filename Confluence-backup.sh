#!/bin/bash
 
 
###--- CONFIGURATION SECTION STARTS HERE ---###
# MAKE SURE ALL THE VALUES IN THIS SECTION ARE CORRECT BEFORE RUNNIG THE SCRIPT
EMAIL=
API_TOKEN=
INSTANCE=xxx.atlassian.net
DOWNLOAD_FOLDER="/absolute/path/here"

# Set to false if you don't want to backup attachments
INCLUDE_ATTACHMENTS=true

 
### Checks for progress max 3000 times, waiting 20 seconds between one check and the other ###
# If your instance is big you may want to increase the below values #
PROGRESS_CHECKS=3000
SLEEP_SECONDS=20
 
# Set this to your Atlassian instance's timezone.
# See this for a list of possible values:
# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIMEZONE=Europe/Amsterdam
  
###--- END OF CONFIGURATION SECTION ---####
 
 
####- START SCRIPT -#####
 
TODAY=$(TZ=$TIMEZONE date +%d-%m-%Y)
echo "starting the script: $TODAY"


## The $BKPMSG variable is used to save and print the response
BKPMSG=$(curl -s -u ${EMAIL}:${API_TOKEN} -H "X-Atlassian-Token: no-check" -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json"  -X POST "https://${INSTANCE}/wiki/rest/obm/1.0/runbackup" -d "{\"cbAttachments\":\"$INCLUDE_ATTACHMENTS\" }" )

## Uncomment below line to print the response message also in case of no errors ##
# echo "Response message: $BKPMSG \n"

## Checks if the backup procedure has failed
if [ "$(echo "$BKPMSG" | grep -ic backup)" -ne 0 ]; then
echo "BACKUP FAILED!! Message returned: $BKPMSG"
exit
fi


# Checks if the backup process completed for the number of times specified in PROGRESS_CHECKS variable
for (( c=1; c<=${PROGRESS_CHECKS}; c++ ))
do
PROGRESS_JSON=$(curl -s -u ${EMAIL}:${API_TOKEN} https://${INSTANCE}/wiki/rest/obm/1.0/getprogress.json)
FILE_NAME=$(echo "$PROGRESS_JSON" | sed -n 's/.*"fileName"[ ]*:[ ]*"\([^"]*\).*/\1/p')

##PRINT BACKUP STATUS INFO ##
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
exit

else

## PRINT THE FILE TO DOWNLOAD ##
echo "Downloading file: https://${INSTANCE}/wiki/download/$FILE_NAME"

curl -s -L -u ${EMAIL}:${API_TOKEN} "https://${INSTANCE}/wiki/download/$FILE_NAME" -o "$DOWNLOAD_FOLDER/CONF-backup-${TODAY}.zip"

fi
