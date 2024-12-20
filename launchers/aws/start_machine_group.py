import argparse  # Command-line options, arguments, and subcommands
import boto3     # AWS Software Development Kit (SDK) for Python
import datetime  # For readibility and tracking by generating a timestamp-based unique name
import botocore  # For error handling
import os        # For file handling

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

# Function to fetch and update the default AWS security group (aka Firewall) in the region
def configure_default_security_group(region, profile):
    """Fetches the default security group and adds rules for SSH, HTTP, and HTTPS."""
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2_client = session.client('ec2')
    try:
        # Fetch default VPC to get the default security group
        response = ec2_client.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': ['default']}
            ]
        )
        security_group_id = response['SecurityGroups'][0]['GroupId']
        print(f"Default Security Group ID: {security_group_id}")

        # Authorize SSH (22), HTTP (80), and HTTPS (443) ingress if not already present
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 443,
                    'ToPort': 443,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print(f"Ingress rules added to security group: {security_group_id}")
        return security_group_id
    except botocore.exceptions.ClientError as error:
        if 'InvalidPermission.Duplicate' in str(error):
            print("Ingress rules already exist.")
        else:
            print(f"Error configuring security group: {error}")
        return security_group_id

# Function to create a new key pair in AWS to be able to access it through SSH (e.g., PuTTy)
def create_key_pair(region, profile):
    """Creates a new RSA key pair in PPK format."""
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2_client = session.client('ec2')
    key_name = f"KeyPair-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        key_pair = ec2_client.create_key_pair(
            KeyName=key_name,
            KeyType='rsa',
            KeyFormat='ppk'  # PuTTy compatible
        )
    
        # Save the PPK key pair to a file
        ppk_file = os.path.expanduser(f"~/{key_name}.ppk")
        with open(ppk_file, 'w') as file:
            file.write(key_pair['KeyMaterial'])
        os.chmod(ppk_file, 0o400)
        
        print(f"Key pair created in PPK format and saved to {ppk_file}")
        return key_name
    except Exception as e:
        print(f"Error creating PPK key pair: {e}")
        return None

# Initialize the argument parser
parser = argparse.ArgumentParser(description="Launch Virtual Machines (VMs) using user-provided configurations.")
parser.add_argument('--vm_type', type=str, default='t2.micro', help="Virtual Machine Type [default: t2.micro]")
parser.add_argument('--num_machines', type=int, default=1, help="Number of Virtual Machines to launch [default: 1]")
parser.add_argument('--region', type=str, default='eu-west-3', help="AWS Region [default: eu-west-3]")
parser.add_argument('--profile', type=str, default='default', help="AWS CLI profile [default: default]")
parser.add_argument('--machine_group_name', type=str, default='Machine Group AWS', help="Machine Group Name [default: Machine Group AWS]")
parser.add_argument('--user_data_path', type=str, required=True, help="Path to the user data script")

args = parser.parse_args()

# Validate the user data script path
user_data_path = args.user_data_path
if not os.path.exists(user_data_path):
    print(f"User data file not found at {user_data_path}. Exiting.")
    exit(1)

# Fetch the latest Ubuntu 24.04 LTS AMI ID
ami_id = fetch_ubuntu_ami_id(args.region, args.profile)
if not ami_id:
    print("Failed to retrieve Ubuntu 24.04 LTS AMI ID. Exiting.")
    exit(1)

# Configure the default security group (Firewall) and create a key pair
security_group_id = configure_default_security_group(args.region, args.profile)
key_name = create_key_pair(args.region, args.profile)
if not key_name:
    print("Failed to create key pair. Exiting.")
    exit(1)

# Initialize boto3 session
session = boto3.Session(profile_name=args.profile)
ec2_client = session.client('ec2', region_name=args.region)

# Read the user data script
with open(user_data_path, 'r') as user_data_file:
    user_data_lines = user_data_file.readlines()

# Find and modify or insert the MACHINE_GROUP_NAME line in the User Data
updated_lines = []
inserted = False
for line in user_data_lines:
    if "echo \"MACHINE_GROUP_NAME=" in line:
        updated_lines.append(f"echo \"MACHINE_GROUP_NAME='{args.machine_group_name}'\" | sudo tee -a .env > /dev/null\n")
        inserted = True
    else:
        updated_lines.append(line)

if not inserted:
    for i, line in enumerate(user_data_lines):
        if "INDUCTIVA_API_URL=https://api.inductiva.ai" in line:
            updated_lines.insert(i + 1, f"echo \"MACHINE_GROUP_NAME='{args.machine_group_name}'\" | sudo tee -a .env > /dev/null\n")
            break

# Save the modified script back to the file
with open(user_data_path, 'w') as user_data_file:
    user_data_file.writelines(updated_lines)

# Launch EC2 Virtual Machine(s) with the modified User Data
with open(user_data_path, 'r') as user_data_file:
    user_data = user_data_file.read()

for i in range(args.num_machines):
    unique_name = f"VM-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{i+1}"
    try:
        response = ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType=args.vm_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            UserData=user_data,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': unique_name}]
            }]
        )
        for instance in response['Instances']:
            print(f"VM launched with ID: {instance['InstanceId']} and Name: {unique_name}")
    except Exception as e:
        print(f"Error launching VM: {e}")