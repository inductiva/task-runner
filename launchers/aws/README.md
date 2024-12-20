<details>
<summary>Table of Contents</summary>

- [Requirements](#requirements).
- [Authenticating with AWS](#authenticating-with-aws)
  - [Authentication Method 1: Access and secret key credentials](#authentication-method-1-access-and-secret-key-credentials)
  - [Authentication Method 2: IAM Identity Center / Single Sign-On (SSO)](#authentication-method-2-iam-identity-center--single-sign-on-sso)
- [Running](#running)
- [Launch Inductiva Task Runner on your AWS account](#launch-inductiva-task-runner-on-your-aws-account)

</details>
    
# Requirements

* Python installation (download [here](https://www.python.org/downloads/)).
* AWS account (register at https://aws.amazon.com/).
* AWS CLI (command line interface) installation based on the [official instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
* Boto3 [AWS Software Development Kit (SDK) for Python] installation (pip install boto3)
* Inductiva API key (register at https://inductiva.ai/).
* git – (optional) – to clone this repository, alternatively download the zip file.

# Authenticating with AWS
## Authentication Method 1: Access and secret key credentials

1. Sign in to AWS and search for “IAM”. 
2. On the right, in “Quick Links”, click “My security credentials”.
3. Click “Create access key”. Copy and save the “Access key” and “Secret access key” and/or click “Download .csv file”.
4. For the next step, find an AWS region on the top right to be your default. For example, for "London" use "eu-west-2".
5. Open your terminal and run the command:
```console
> aws configure
```
You will be prompted to enter the following fields:
```
AWS Access Key ID [None]: <insert_access_key>
AWS Secret Access Key [None]: <insert_secret_key>
Default region name [None]: <insert_aws_region>
Default output format [json]: json
```

A file should be created at ~/.aws/credentials, containing:
```
[default]
aws_access_key_id = <aws_access_key_id>
aws_secret_access_key = <aws_secret_access_key>
```
Plus, you can validate that your AWS profile is working by running the command:
```console
> aws sts get-caller-identity
```

The output should look like this:
```
{
    "UserId": "<account_ID>",
    "Account": "<account_ID>",
    "Arn": "arn:aws:iam::<Account_ID>:root"
}
```

### Recommendations

1.  As a best practice, avoid using long-term/permanent credentials like access keys. Instead, use alternatives such as a user in IAM Identity Center, which provide short-term/temporary credentials (see [Authentication Method 2](#authentication-method-2-iam-identity-center--single-sign-on-sso)).
2.  Instead of using a root account, create an IAM user with an access key and apply least privilege permissions for that user.

### Next steps
To launch a Machine Group with the Inductiva Task Runner with this method go [here](#authentication-method-1-access-and-secret-key-credentials).

## Authentication Method 2: IAM Identity Center / Single Sign-On (SSO)

1. Sign in to AWS and search for “IAM Identity Center”. Take note of the region where you're at (e.g. "eu-west-2" means "London").
3. Click “Enable” to enable IAM Identity Center. If prompted, click “Create AWS organization”.
5. On the left, click “Users” and then “Add user”.
6. At "Specify user details", fill the “Primary information”, and then click “Next”. When asked to “Add user to groups - optional” click “Next”. Review and click “Add user”.
7. Go to your email account and click “Accept Invitation” to join AWS IAM Identity Center.
8. Define your password and then “Set new password”. Next "Sign in" with your "Username" and "Password". The web browser should display something like:
```    
You have navigated to the AWS access portal
After your administrator gives you access to applications and AWS accounts, you can find them here.
```

10. In the IAM Identity Center, on the left, in "Multi-account permissions", click "Permission sets".
11. Then, click "Create permission set", and in "Policy for predefined permission set" choose "AdministratorAccess". Click next, review and create.
12. In "Multi-account permissions", click AWS accounts, select your "management account" and click "Assign users or groups". Go to the "Users" tab, select your user and click "Next.". Select your "Permission set" called "AdministratorAccess" and click "Next". Review and click "Submit".
13. Go to the “Dashboard” page, and copy the AWS access portal URL that is in the settings summary. It will look something like: `https://d-xxxxxxxxxx.awsapps.com/start`
14. In your preferred terminal, run the command:
```console
aws configure sso
```

You will be prompted to enter the following fields:

```
SSO session name (Recommended): <insert_session_name>
SSO start URL [None]: https://d-xxxxxxxxxx.awsapps.com/start
SSO region [None]: <insert_aws_region> # the AWS Region that hosts the IAM Identity Center directory
SSO registration scopes [sso:account:access]: sso:account:access
```

After that, you should see:

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
Back in the terminal, the following should appear:
```
The only AWS account available to you is: <account ID>
Using the account ID <account ID>
The only role available to you is: AdministratorAccess
Using the role name "AdministratorAccess"
CLI default client Region [eu-west-3]: <Enter>
CLI default output format [json]: <Enter>
CLI profile name [AdministratorAccess-<Account_ID>]: <your_profile_name>
```
To launch Machine Group with the Inductiva Task Runner with this method go [here](#authentication-method-2-iam-identity-center--single-sign-on-sso).


# Launch Machine Group with the Inductiva Task Runner
## Launch Method 1
Continue if you've followed [Authentication Method 1: Access and secret key credentials](#authentication-method-1-access-and-secret-key-credentials).
Go to your local repository and open a terminal, and run this example:
```console
> python start_aws_machine_group.py \
--vm_type t2.micro \
--num_machines 2 \
--region eu-west-2 \
--machine_group_name "my_aws_machine_group" \
```

## Launch Method 2

Continue if you've followed [Authentication Method 2: IAM Identity Center / Single Sign-On (SSO)](#authentication-method-2-iam-identity-center--single-sign-on-sso).

Before running the python program, authenticate with AWS through SSO (Single Sign-on).

```console
> aws sso login --profile <your_profile_name>
```

A browser windows should open and ask you to insert username and password.

The start_machine_group.py allows user inputs through flags (argparse) and uses Boto3 to interact with AWS (Software Development Kit [SDK] for Python).

Go to your local repository and open a terminal, and run this example:
```console
python start_machine_group.py \
--vm_type t2.micro \
--num_machines 2 \
--region eu-west-2 \
--machine_group_name "my_aws_machine_group" \
--profile <your_profile_name> \
--user_data_path 'user-data.sh'
```
## Extra

The file user-data.sh is a script that is provided to each virtual machine in order for them to install all the dependencies and run the task-runner.
