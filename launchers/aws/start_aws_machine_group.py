import argparse  # Parser for command-line options, arguments and subcommand
import os        # Interacting with the operating system (e.g. read/write user-data.sh file)
import datetime  # Timestamping names
import boto3     # AWS Software Development Kit (SDK) for Python
import botocore
import json
import platform

# Function to fetch the latest Ubuntu 24.04 LTS Amazon Machine Image (AMI) ID from AWS Systems Manager Parameter Store
def fetch_ubuntu_ami_id(region, profile):
    """Fetches the latest Ubuntu 24.04 LTS AMI ID from AWS Systems Manager."""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        ssm = session.client('ssm')
        # Fetch the latest AMI ID for Ubuntu 24.04 LTS (amd64, hvm, ebs-gp3)
        parameter = ssm.get_parameter(
            Name='/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id'
        )
        return parameter['Parameter']['Value']
    except botocore.exceptions.ClientError as error:
        print(f"Error fetching AMI ID: {error}")
        return None

# Function to fetch and update the default AWS security group (i.e. Virtual Machine Firewall) in the respective region
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

def create_key_pair(region, profile, key_format):
    """Creates a new RSA key pair in the specified format (PEM or PPK)."""
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2_client = session.client('ec2')
    key_name = f"KeyPair-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    
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
        
        # Save the key material to a file
        with open(key_file, 'w') as file:
            file.write(key_pair['KeyMaterial'])
        
        # Set secure file permissions
        os.chmod(key_file, 0o400)
        
        print(f"Key pair saved to: {key_file}")

        return key_name
    except Exception as e:
        print(f"Error creating {key_format.upper()} key pair: {e}")
        return None

# Function to create an Identity and Acess Management (IAM) role with AdministratorAccess
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
        print(f"Role {role_name} created and AdministratorAccess policy attached.")

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
        print(f"Instance Profile {instance_profile_name} created and role associated.")
    return instance_profile_name

def get_default_api_key_path():
    """Determine the default path for the Inductiva API key based on the operating system."""
    if platform.system() == "Windows":
        # Windows: C:\Users\<username>\AppData\inductiva\api_key
        return os.path.join(os.path.expanduser("~"), "AppData", "inductiva", "api_key")
    else:
        # macOS/Linux: ~/.inductiva/api_key
        return os.path.join(os.path.expanduser("~"), ".inductiva", "api_key")

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
parser.add_argument('--mode', type=str, choices=['normal', 'lite', 'cuda'], default='normal',
                        help="Task Runner Mode: normal [default], lite, or cuda")
parser.add_argument('--key_format', type=str, choices=['pem', 'ppk'], default='pem',
                    help="Key Pair Format: pem [default] or ppk")
parser.add_argument('--user_data_path', type=str, default='user-data.sh',
                    help="File path to the user-data.sh script [default: user-data.sh]")
parser.add_argument('--profile', type=str, default='default', help="AWS CLI profile [default: default]")
args = parser.parse_args()

# Validate the user data script path
user_data_path = args.user_data_path
if not os.path.exists(user_data_path):
    print(f"User data file not found at {user_data_path}. Exiting.")
    exit(1)

# Read the user data script
with open(user_data_path, 'r') as user_data_file:
    user_data_lines = user_data_file.readlines()

# Function to remove any existing task runner command
def remove_existing_task_runner_command():
    for i, line in enumerate(user_data_lines):
        if line.startswith("make task-runner"):
            user_data_lines.pop(i)  # Remove the task runner line
            break

# Function to add the appropriate make command based on the mode
def update_task_runner_command(mode):
    # Define the commands for each mode
    mode_commands = {
        'normal': "make task-runner-up &",
        'lite': "make task-runner-lite-up &",
        'cuda': "make task-runner-cuda-up &"
    }

    # Get the command for the selected mode
    task_runner_command = mode_commands.get(mode)

    # Remove any existing task runner command to avoid duplicates
    remove_existing_task_runner_command()

    # Search for the "export $(grep -v ^# .env | xargs)" line
    for i, line in enumerate(user_data_lines):
        if "export $(grep -v ^# .env | xargs)" in line:
            # Insert the corresponding task runner command after the export line
            user_data_lines.insert(i + 1, f"\n{task_runner_command}")
            break

# Call the function to update the task runner command based on the selected mode
update_task_runner_command(args.mode)

# Save the modified script back to the file
with open(user_data_path, 'w') as user_data_file:
    user_data_file.writelines(user_data_lines)

# Function to update the INDUCTIVA_API_KEY in user-data.sh
def update_inductiva_api_key_in_user_data(api_key):
    api_key_updated = False
    inside_task_runner_block = False
    # Loop through the lines and find where "cd task-runner" is
    for i, line in enumerate(user_data_lines):

        if "cd task-runner" in line:
            inside_task_runner_block = True

        if inside_task_runner_block and "export $(grep -v ^# .env | xargs)" in line:
            # If "INDUCTIVA_API_KEY" exists in the lines already, update it
            for j in range(i - 1, -1, -1):
                if "INDUCTIVA_API_KEY" in user_data_lines[j]:
                    user_data_lines[j] = f"echo \"INDUCTIVA_API_KEY='{api_key}'\" | sudo tee -a .env > /dev/null\n"
                    api_key_updated = True
                    break

            # If key doesn't exist, add it at the correct position
            if not api_key_updated:
                user_data_lines.insert(i, f"echo \"INDUCTIVA_API_KEY='{api_key}'\" | sudo tee -a .env > /dev/null\n")
            break


# Function to update the MACHINE_GROUP_NAME in user-data.sh
def update_machine_group_name_in_user_data(machine_group_name):
    machine_group_name_updated = False
    inside_task_runner_block = False
    # Loop through the lines and find where "cd task-runner" is
    for i, line in enumerate(user_data_lines):

        if "cd task-runner" in line:
            inside_task_runner_block = True

        if inside_task_runner_block and "export $(grep -v ^# .env | xargs)" in line:
            # If "MACHINE_GROUP_NAME" exists in the lines already, update it
            for j in range(i - 1, -1, -1):
                if "MACHINE_GROUP_NAME" in user_data_lines[j]:
                    user_data_lines[
                        j] = f"echo \"MACHINE_GROUP_NAME='{machine_group_name}'\" | sudo tee -a .env > /dev/null\n"
                    machine_group_name_updated = True
                    break

            # If the machine group name doesn't exist, add it at the correct position
            if not machine_group_name_updated:
                user_data_lines.insert(i,
                                       f"echo \"MACHINE_GROUP_NAME='{machine_group_name}'\" | sudo tee -a .env > /dev/null\n")
            break

# Retrieve the Inductiva API Key from the file
inductiva_api_key = get_inductiva_api_key()
# If inductiva_api_key is provided, update or insert it
if inductiva_api_key:
    update_inductiva_api_key_in_user_data(inductiva_api_key)
else:
    # If inductiva_api_key is not provided, check if it exists in user-data.sh
    key_exists = any("INDUCTIVA_API_KEY" in line for line in user_data_lines)
    if not key_exists:
        print("Error: INDUCTIVA_API_KEY not found in user-data.sh.")
        print("Please provide your Inductiva API Key.")
        inductiva_api_key = input("Enter your Inductiva API Key: ")
        if not inductiva_api_key:
            print("Error: No Inductiva API Key provided. The operation cannot continue.")
            exit(1)  # Exit the script
        # Update user data with the provided API key
        update_inductiva_api_key_in_user_data(inductiva_api_key)

# If machine_group_name is provided, update or insert it
if args.machine_group_name:
    update_machine_group_name_in_user_data(args.machine_group_name)
else:
    # If machine_group_name is not provided, update it with the default value if missing
    update_machine_group_name_in_user_data(args.machine_group_name)

# Save the modified script back to the file
with open(user_data_path, 'w') as user_data_file:
    user_data_file.writelines(user_data_lines)

# Get the Ubuntu AMI ID (OS Template)
ami_id = fetch_ubuntu_ami_id(args.region, args.profile)
if not ami_id:
    print("Error: Could not fetch AMI ID. Exiting.")
    exit(1)

# Configure the default security group (VM Firewall)
security_group_id = configure_default_security_group(args.region, args.profile)
if not security_group_id:
    print("Error: Could not configure the security group. Exiting.")
    exit(1)

# Create a key pair (pem or ppk) for SSH access to the VM
key_name = create_key_pair(args.region, args.profile, args.key_format)
if not key_name:
    print("Failed to create key pair.")

# Create the Virtual Machine (EC2 Instance)
session = boto3.Session(profile_name=args.profile, region_name=args.region)
ec2_client = session.client('ec2')

# Define IAM role name
role_name = 'EC2RoleAdmin'

# Create the IAM role with AdministratorAccess to allow Virtual Machine to delete itself
instance_profile_name = create_iam_role_with_admin_access(role_name, args.profile)

# Launch EC2 Virtual Machine(s) with the modified User Data
for i in range(args.num_machines):
    unique_name = f"VM-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{i + 1}"
    try:
        response = ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType=args.vm_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            UserData=''.join(user_data_lines),
            MinCount=1,
            MaxCount=1,
            IamInstanceProfile={'Name': instance_profile_name},  # Attach the instance profile here
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
            print(f"VM launched with ID: {instance['InstanceId']} and Name: {unique_name}")
    except Exception as e:
        print(f"Error launching VM: {e}")
