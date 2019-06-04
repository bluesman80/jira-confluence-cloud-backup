### PLEASE NOTICE THAT THIS SCRIPT USES THE SESSION ENDPOINT THAT HAS BEEN DEPRECATED. SEE BELOW LINK FOR DETAILS:
## https://developer.atlassian.com/cloud/jira/platform/deprecation-notice-basic-auth-and-cookie-based-auth/

# Having the right skillset you can modify this script to use the API Tokens instead (use the bash scripts as example) 

$account     = 'youratlassianjira' # Atlassian subdomain i.e. whateverproceeds.atlassian.net
$username    = 'youratlassianusername' # username without domain
$password    = 'youratlassianpassword' 
$destination = 'C:\Backups' # Location on server where script is run to dump the backup zip file.
$attachments = 'false' # Tells the script whether or not to pull down the attachments as well
$cloud     = 'true' # Tells the script whether to export the backup for Cloud or Server

$hostname    = "$account.atlassian.net"
$today       = Get-Date -format yyyyMMdd-hhmmss
$credential  = New-Object System.Management.Automation.PSCredential($username, (ConvertTo-SecureString $password -AsPlainText -Force))

$string = "cbAttachments:true, exportToCloud:true"
$stringbinary = [system.Text.Encoding]::Default.GetBytes($String) | %{[System.Convert]::ToString($_,2).PadLeft(8,'0') }

$body = @{
          cbAttachments=$attachments
          exportToCloud=$cloud
         }
$bodyjson = $body | ConvertTo-Json

if ($PSVersionTable.PSVersion.Major -lt 4) {
    throw "Script requires at least PowerShell version 4. Get it here: https://www.microsoft.com/en-us/download/details.aspx?id=40855"
}

# New session
Invoke-RestMethod -UseBasicParsing -Method Post -Uri "https://$hostname/rest/auth/1/session" -SessionVariable session -Body (@{username = $username; password = $password} | convertTo-Json -Compress) -ContentType 'application/json'

# Request backup
try {
        $InitiateBackup = Invoke-RestMethod -Method Post -Headers @{"Accept"="application/json"} -Uri "https://$hostname/rest/backup/1/export/runbackup" -WebSession $session -ContentType 'application/json' -Body $bodyjson -Verbose | ConvertTo-Json -Compress | Out-Null
} catch {
        $InitiateBackup = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($InitiateBackup)
        $reader.BaseStream.Position = 0
        $reader.DiscardBufferedData()
        $responseBody = $reader.ReadToEnd();
}

$responseBody

$GetBackupID = Invoke-WebRequest -Method Get -WebSession $session https://$hostname/rest/backup/1/export/lastTaskId
$LatestBackupID = $GetBackupID.content


# Wait for backup to finish
do {
    $status = Invoke-RestMethod -Method Get -Headers @{"Accept"="application/json"} -Uri "https://$hostname/rest/backup/1/export/getProgress?taskId=$LatestBackupID" -WebSession $session
    $statusoutput = $status.result
    $separator = ","
    $option = [System.StringSplitOptions]::None
    $s

    if ($status.progress -match "(\d+)") {
        $percentage = $Matches[1]
        if ([int]$percentage -gt 100) {
            $percentage = "100"
        }
        Write-Progress -Activity 'Creating backup' -Status $status.progress -PercentComplete $percentage
    }
    Start-Sleep -Seconds 5
} while($status.status -ne 'Success')

# Download
if ([bool]($status.PSObject.Properties.Name -match "failedMessage")) {
    throw $status.failedMessage
}

$BackupDetails = $status.result
$BackupURI = "https://$hostname/plugins/servlet/$BackupDetails"

Invoke-WebRequest -Method Get -Headers @{"Accept"="*/*"} -WebSession $session -Uri $BackupURI -OutFile (Join-Path -Path $destination -ChildPath "JIRA-backup-$today.zip")