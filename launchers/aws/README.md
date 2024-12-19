
## Steps to launch Inductiva Task Runner on your AWS account

1. Sign in to AWS and search for “IAM Identity Center”.
2. Click “Enable” to enable IAM Identity Center.
3. If prompted, click “Create AWS organization”.
4. On the left, click “Users” and then “Add user”.
5. Fill the “Primary information” when asked to “Specify user details”, then scroll down and click “Next”. Click “Next” when asked to “Add user to groups - optional”. Review, scroll down and click “Add user”.
6. Go to the email account and click “Accept Invitation” to join AWS IAM Identity Center.
7. Define your password and then “Set new password”.
8. Go to the “Dashboard” page, and copy the AWS access portal URL that is in the settings summary.
9. In your preferred terminal, run the aws configure sso command.
    SSO session name (Recommended): inductiva
    SSO start URL [None]: https://d-806709a3fb.awsapps.com/start
    SSO region [None]: eu-west-3
    SSO registration scopes [sso:account:access]: sso:account:all
    Attempting to automatically open the SSO authorization page in your default browser.
    If the browser does not open or you wish to use a different device to authorize this request, open the provided URL:
    On the web page that just opened in the browser click “Allow access”.
    If successful it should display the following:
        Request approved
        AWS CLI has been given requested permissions
        You can close this window and start using the AWS CLI.

The start_machine_group.py allows user inputs through flags (argparse) and uses Boto3 to interact with AWS (Software Development Kit [SDK] for Python).
Before running the python program, I authenticate with AWS through SSO (Single Sign-on). Example command:

10. aws sso login --profile lmcmr

Then, a browser windows opens for me to insert username and password.

Example of a command to run start_machine_group.py:

11. On the user-data.sh paste the Inductiva API key

12. python .\start_machine_group.py --vm_type t2.micro --num_machines 2 --region ap-south-1 --machine_group_name "my_aws_machine_group" --user_data_path '.\user-data.sh' --profile lmcmr

The file user-data.sh is a script that is given to each virtual machine before starting in order to install all the dependencies (docker, git, make); then git clone the task-runner repository; authenticate through the Inductiva_API_Key; the machine_group_name gets defined dynamically through the python script; and make task-runner-up.