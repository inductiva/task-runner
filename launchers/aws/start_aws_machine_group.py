import argparse # Parser for command-line options, arguments and subcommands
import os       # Interacting with the operating system (e.g. read/write user_data.sh file)
import datetime # Timestamping names for keeping track and troubleshooting
import boto3    # AWS Software Development Kit (SDK) for Python
import botocore
import json
import platform # To determine the OS (Windows or MacOS/Linux)
import re       # Regular Expressions (RegEx)

# Function to fetch the latest Ubuntu 24.04 LTS Amazon Machine Image (AMI) ID from AWS Systems Manager Parameter Store for a particular region
def fetch_ubuntu_ami_id(region, profile):
    """Fetches the latest Ubuntu 24.04 LTS AMI ID for a particular region."""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        ssm = session.client('ssm')
        parameter = ssm.get_parameter(
            Name='/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id'
        )
        return parameter['Parameter']['Value']
    except botocore.exceptions.ClientError as error:
        print(f"Error fetching AMI ID: {error}")
        return None

# Function to fetch and update the default AWS security group (i.e. Virtual Machine Firewall) in the respective region and Adds Rules for ports SSH, HHTP, and HTTPS
def configure_default_security_group(region, profile):
    """Fetches the default security group (VM firewall) and adds rules for SSH, HTTP, and HTTPS."""
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2_client = session.client('ec2')
    try:
        # Fetch default Virtual Private Cloud (VPC) to get the default security group
        response = ec2_client.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': ['default']}]
        )
        security_group_id = response['SecurityGroups'][0]['GroupId']
        # Authorize SSH (22), HTTP (80), and HTTPS (443) ports if not already present
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        return security_group_id
    except botocore.exceptions.ClientError as error:
        if 'InvalidPermission.Duplicate' in str(error):
            pass
        else:
            print(f"Error configuring security group: {error}")
        return security_group_id

# Create key pair in order to access with SSH (port 22) the Virtual Machine (aka EC2 Instance) for troubleshooting (e.g. PuTTy)
def create_key_pair(region, profile, key_format):
    """Creates a new RSA key pair in the specified format (PEM or PPK)."""
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2_client = session.client('ec2')
    key_name = f"KeyPair-{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}"
    # Validate key_format
    if key_format not in ['pem', 'ppk']:
        raise ValueError("Invalid key format. Choose 'pem' or 'ppk'.")
    try:
        key_pair = ec2_client.create_key_pair(
            KeyName=key_name,
            KeyType='rsa',
            KeyFormat=key_format  # PEM or PPK
        )
        # Set the file extension and path based on the format
        file_extension = 'pem' if key_format == 'pem' else 'ppk'
        key_file = os.path.expanduser(f"~/{key_name}.{file_extension}")
        # Save the key to a file
        with open(key_file, 'w') as file:
            file.write(key_pair['KeyMaterial'])
        # Set secure file permissions
        os.chmod(key_file, 0o400)
        #print(f"Key pair saved to: {key_file}")
        return key_name
    except Exception as e:
        print(f"Error creating {key_format.upper()} key pair: {e}")
        return None

# Function to create an Identity and Acess Management (IAM) role with AdministratorAccess necessary for the VM to delete itself
def create_iam_role_with_admin_access(role_name, profile):
    session = boto3.Session(profile_name=profile)
    iam_client = session.client('iam')
    try:
        # Check if the role already exists
        iam_client.get_role(RoleName=role_name)
        #print(f"Role {role_name} already exists.")
    except iam_client.exceptions.NoSuchEntityException:
        print(f"Creating role {role_name} with AdministratorAccess...")
        # Define trust relationship policy for EC2 instances
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        # Create the role
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for EC2 instances with Administrator Access"
        )
        # Attach AdministratorAccess policy to the role
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess"
        )
        #print(f"Role {role_name} created and AdministratorAccess policy attached.")
    # Create an instance profile for the role
    instance_profile_name = f"{role_name}-instance-profile"
    try:
        # Check if the instance profile already exists
        iam_client.get_instance_profile(InstanceProfileName=instance_profile_name)
        #print(f"Instance Profile {instance_profile_name} already exists.")
    except iam_client.exceptions.NoSuchEntityException:
        # Create an instance profile and associate the role with it
        iam_client.create_instance_profile(InstanceProfileName=instance_profile_name)
        iam_client.add_role_to_instance_profile(
            InstanceProfileName=instance_profile_name,
            RoleName=role_name
        )
        #print(f"Instance Profile {instance_profile_name} created and role associated.")
    return instance_profile_name

# When logging in with 'inductiva auth login' the api key is requested and stored in a file inductiva\api_key
def get_default_api_key_path():
    """Determine the default path for the Inductiva API key based on the operating system."""
    if platform.system() == "Windows":
        # Windows: C:\Users\<username>\AppData\inductiva\api_key
        return os.path.join(os.path.expanduser("~"), "AppData", "inductiva", "api_key")
    else:
        # macOS/Linux: ~/.inductiva/api_key
        return os.path.join(os.path.expanduser("~"), ".inductiva", "api_key")

# Retrieve the API Key from the previously file inductiva\api_key
def get_inductiva_api_key():
    """Retrieve the Inductiva API key from the default path."""
    default_path = get_default_api_key_path()
    try:
        with open(default_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"API key file not found at {default_path}. Please ensure it exists.")
        return None
    except PermissionError:
        print(f"Permission denied when accessing the API key file at {default_path}.")
        print("Try running the script with elevated privileges or adjust the file permissions.")
        return None
    except Exception as e:
        print(f"Error reading API key file: {e}")
        return None
    
# Update the USER_API_KEY in user-data.sh
def update_inductiva_api_key_in_user_data(api_key, script_path="user_data.sh"):
    """
    Update the USER_API_KEY in the user_data.sh file.
    """
    try:
        # Read the content of the script
        with open(script_path, 'r') as file:
            script_content = file.read()

        # Replace the USER_API_KEY value using regex
        updated_content = re.sub(
            r'(--env USER_API_KEY=)([^\s]+)',  # Match `--env USER_API_KEY=` and its value
            rf'\1{api_key}',                  # Replace with `--env USER_API_KEY=<api_key>`
            script_content
        )

        # Write the updated content back to the script
        with open(script_path, 'w') as file:
            file.write(updated_content)

    except FileNotFoundError:
        print(f"Error: File {script_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Function to update the MACHINE_GROUP_NAME in user-data.sh
def update_machine_group_name(file_path, machine_group_name):
    """
    Updates the MACHINE_GROUP_NAME in the user_data.sh file.
    """
    try:
        # Read the current contents of the file
        with open(file_path, "r") as file:
            content = file.read()
        
        # Define the regex pattern to find the MACHINE_GROUP_NAME line
        pattern = r"--env MACHINE_GROUP_NAME=[^ ]+"
        replacement = f"--env MACHINE_GROUP_NAME='{machine_group_name}'"
        
        # Replace the MACHINE_GROUP_NAME value
        updated_content = re.sub(pattern, replacement, content)
        
        # Write the updated contents back to the file
        with open(file_path, "w") as file:
            file.write(updated_content)
        
        print(f"'{machine_group_name}' will appear in the Inductiva.AI Console, at 'Machine Groups'.")
    except Exception as e:
        print(f"An error occurred while updating MACHINE_GROUP_NAME: {e}")

def update_user_data_tag_branch(file_path, branch):
    """
    Updates the user_data.sh file with the specified Docker image tags for the branch.
    """
    # Read the user_data.sh file
    with open(file_path, 'r') as file:
        user_data = file.read()

    # Define the new tags based on the branch
    file_tracker_tag = f"inductiva/file-tracker:{branch}"
    task_runner_tag = f"inductiva/task-runner:{branch}"

    # Use regex to replace existing image tags
    user_data = re.sub(r'inductiva/file-tracker(:\w+)?', file_tracker_tag, user_data)
    user_data = re.sub(r'inductiva/task-runner(:\w+)?', task_runner_tag, user_data)

    # Write the updated user_data.sh file back to disk
    with open(file_path, 'w') as file:
        file.write(user_data)
    #print(f"user_data.sh file updated for the '{branch}' branch.")

# Initialize the argument parser
parser = argparse.ArgumentParser(description="Launch Virtual Machines (VMs) by configuring them.")
parser.add_argument('--vm_type', type=str, default='t2.micro', help="Virtual Machine Type [default: t2.micro]. Learn more at https://aws.amazon.com/pt/ec2/instance-types/")
parser.add_argument('--volume_size', type=int, default=8, help="Size of the root volume in GiB [default: 8]")
parser.add_argument('--volume_type', type=str, choices=['gp3', 'gp2', 'io1', 'io2'], default='gp3',
                    help="Type of the root volume [default: gp3]")
parser.add_argument('--iops', type=int, default=3000, help="IOPS for the volume (applies to io1, io2, gp3 only) [default: 3000]")
parser.add_argument('--throughput', type=int, default=125, help="Throughput in MiB/s (gp3 only) [default: 125]")
parser.add_argument('--num_machines', type=int, default=1, help="Number of Virtual Machines to launch [default: 1]")
parser.add_argument('--region', type=str, default='eu-west-2', help="AWS Region [default: eu-west-2]")
parser.add_argument('--machine_group_name', type=str, default='AWS Machine Group',
                    help="Inductiva Machine Group Name [default: AWS Machine Group]")
parser.add_argument('--branch', type=str, choices=['main', 'dev'], default='main',
                    help="Task-runner branch to clone: main [default] or dev")
parser.add_argument('--key_format', type=str, choices=['pem', 'ppk'], default='pem',
                    help="Key Pair Format: pem [default] or ppk")
parser.add_argument('--user_data_path', type=str, default='user_data.sh',
                    help="File path to the user-data.sh script [default: user_data.sh]")
parser.add_argument('--profile', type=str, default='default', help="AWS CLI profile [default: default]")
"""parser.add_argument('--mode', type=str, choices=['normal', 'lite', 'cuda'], default='normal',
                        help="Task Runner Mode: normal [default], lite, or cuda") """
args = parser.parse_args()

# Validate the user data script path
user_data_path = args.user_data_path
if not os.path.exists(user_data_path):
    print(f"User data file not found at {user_data_path}. Exiting.")
    exit(1)

# Retrieve the Inductiva API Key from the file
inductiva_api_key = get_inductiva_api_key()
update_inductiva_api_key_in_user_data(inductiva_api_key, args.user_data_path)

# Update the Machine Group Name
update_machine_group_name(args.user_data_path, args.machine_group_name)

# Get the Ubuntu AMI ID (Image OS Template)
ami_id = fetch_ubuntu_ami_id(args.region, args.profile)
if not ami_id:
    print("Error: Could not fetch AMI ID. Exiting.")
    exit(1)

# Configure the default security group (i.e. Virtual Machine Firewall)
security_group_id = configure_default_security_group(args.region, args.profile)
if not security_group_id:
    print("Error: Could not configure the security group. Exiting.")
    exit(1)

# Create a key pair (pem or ppk) for SSH access to the Virtual Machine [EC2 Instance]
key_name = create_key_pair(args.region, args.profile, args.key_format)
if not key_name:
    print("Failed to create key pair.")

# Define IAM role name
role_name = 'EC2RoleAdmin'

# Create the IAM role with AdministratorAccess to allow Virtual Machine [EC2 Instance] to delete itself
instance_profile_name = create_iam_role_with_admin_access(role_name, args.profile)

# Update the docker container tag in the user_data.sh file to use the appropriate branch
update_user_data_tag_branch(args.user_data_path, args.branch)

# Save the user_data.sh file in a variable
try:
    with open(args.user_data_path, 'r') as user_data_file:
        user_data_lines = user_data_file.read()
except FileNotFoundError:
    print(f"Error: User data file {args.user_data_path} not found. Exiting.")
    exit(1)
except Exception as e:
    print(f"Error reading user data file: {e}. Exiting.")
    exit(1)

# Create the Virtual Machine [EC2 Instance]
session = boto3.Session(profile_name=args.profile, region_name=args.region)
ec2_client = session.client('ec2')

# Launch Virtual Machine(s) [EC2 Instances] with the modified User Data
for i in range(args.num_machines):
    unique_name = f"VM-{i + 1}-{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M')}"
    try:
        response = ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType=args.vm_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            UserData=''.join(user_data_lines),
            MinCount=1,
            MaxCount=1,
            IamInstanceProfile={'Name': instance_profile_name},
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': unique_name}]
            }],
            BlockDeviceMappings=[{
                'DeviceName': '/dev/sda1',
                'Ebs': {
                    'VolumeSize': args.volume_size,
                    'VolumeType': args.volume_type,
                    'DeleteOnTermination': True,
                    'Iops': args.iops if args.volume_type in ['gp3', 'io1', 'io2'] else None,
                    'Throughput': args.throughput if args.volume_type == 'gp3' else None
                }
            }]
        )
        for instance in response['Instances']:
            print(f"Machine {i+1} with Name '{unique_name}' and ID '{instance['InstanceId']}' launched at AWS.")
    except Exception as e:
        print(f"Error launching VM: {e}")