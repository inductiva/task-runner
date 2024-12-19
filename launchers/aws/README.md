## Requirements

* Have an AWS account.
* Install the AWS CLI (command line interface) based on the [official instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).


## Creating a user to launch resources

1. Sign in to AWS and search for “IAM Identity Center”.
2. Click “Enable” to enable IAM Identity Center.

Note that in this step you will chose a specific region, such as `eu-west-3`.
   
4. If prompted, click “Create AWS organization”.
5. On the left, click “Users” and then “Add user”.
6. Fill the “Primary information” when asked to “Specify user details”, then scroll down and click “Next”. Click “Next” when asked to “Add user to groups - optional”. Review, scroll down and click “Add user”.
7. Go to the email account and click “Accept Invitation” to join AWS IAM Identity Center.
8. Define your password and then “Set new password”.

## Authenticating with AWS

1. Go to the “Dashboard” page, and copy the AWS access portal URL that is in the settings summary.

It will look something like: `https://d-806709a3fb.awsapps.com/start`

2. In your preferred terminal, run the command:

```console
aws configure sso
```

You will be prompted to enter the following fields:

```
SSO session name (Recommended): inductiva
SSO start URL [None]: https://d-806709a3fb.awsapps.com/start
SSO region [None]: eu-west-3
SSO registration scopes [sso:account:access]: sso:account:all
```

You should see:

```
Attempting to automatically open the SSO authorization page in your default browser.
If the browser does not open or you wish to use a different device to authorize this request, open the provided URL:
```

On the web page that just opened in the browser click “Allow access”.
If successful it should display the following:

```
Request approved
AWS CLI has been given requested permissions
You can close this window and start using the AWS CLI.
```

Before running the python program, authenticate with AWS through SSO (Single Sign-on). Example command:

```console
aws sso login --profile <your_profile_name>
```

Then, a browser windows opens for me to insert username and password.


## Launch Inductiva Task Runner on your AWS account


The start_machine_group.py allows user inputs through flags (argparse) and uses Boto3 to interact with AWS (Software Development Kit [SDK] for Python).

Example of a command to run start_machine_group.py:

1. On the user-data.sh paste the Inductiva API key

```console
python start_machine_group.py \
--vm_type t2.micro \
--num_machines 2 \
--region ap-south-1 \
--machine_group_name "my_aws_machine_group" \
--user_data_path 'user-data.sh' \
--profile <your_profile_name>
```

The file user-data.sh is a script that is given to each virtual machine before starting in order to install all the dependencies (docker, git, make); then git clone the task-runner repository; authenticate through the Inductiva_API_Key; the machine_group_name gets defined dynamically through the python script; and make task-runner-up.
