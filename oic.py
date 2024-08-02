import os
import re
import subprocess
import tarfile
import sys
import json
from datetime import datetime
import math
import getpass

# Configuration: Black Duck versions supported by this script
black_duck_versions = ["2024.7.0", "2024.4.1", "2024.4.0", "2024.1.1", "2024.1.0", 
                       "2023.10.2", "2023.10.1", "2023.10.0", "2023.7.3", "2023.7.2", 
                       "2023.7.1", "2023.7.0", "2023.4.2", "2023.4.1", "2023.4.0", 
                       "2023.1.2", "2023.1.1", "2023.1.0"]

# Required command-line tools
REQUIRED_TOOLS = ["curl", "docker", "tar", "7z"]

# Log output dictionary to store logs
output = {
    'logs': [],
}

def log(level, message):
    """
    Append new log entries to the output dictionary and save to a JSON file.

    Args:
        level (str): The log level (INFO or ERROR).
        message (str): The log message.
    """
    entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'level': level,
        'message': message
    }
    output['logs'].append(entry)
    with open("logfile.json", "w") as outfile:
        json.dump(output, outfile, indent=4)

def log_info(message):
    """
    Log informational messages.
    """
    log('INFO', message)

def log_error(message):
    """
    Log error messages.
    """
    log('ERROR', message)

def check_required_tools():
    """
    Check if the required command-line tools are available in the system's PATH.
    """
    missing_tools = []
    available_tools = []
    for tool in REQUIRED_TOOLS:
        try:
            if tool == "7z":
                # Check for 7z by running it without arguments
                result = subprocess.run([tool], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if "7-Zip" in result.stdout.decode() or "7-Zip" in result.stderr.decode():
                    log_info(f"{tool} is installed.")
                    available_tools.append(tool)
                else:
                    missing_tools.append(tool)
            else:
                subprocess.run([tool, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                log_info(f"{tool} is installed.")
                available_tools.append(tool)
        except subprocess.CalledProcessError:
            missing_tools.append(tool)
        except FileNotFoundError:
            missing_tools.append(tool)
    
    if missing_tools:
        log_error(f"Missing required tools: {', '.join(missing_tools)}. Please install them and try again.")
        print(f"Missing required tools: {', '.join(missing_tools)}. Please install them and try again.")
        sys.exit(1)
    else:
        log_info("All required command-line tools are installed.")
    return available_tools

def prompt_archive_tool(available_tools):
    """
    Prompt the user to select an archive tool if both 'tar' and '7z' are available.
    """
    if "tar" in available_tools and "7z" in available_tools:
        choice = input("Both 'tar' and '7z' are available. Which one would you like to use for creating the archive? (tar/7z) (default is tar): ").strip().lower()
        if choice not in ["tar", "7z"]:
            log_info("Invalid choice. Defaulting to 'tar'.")
            return "tar"
        log_info(f"User selected '{choice}' for creating the archive.")
        return choice
    elif "tar" in available_tools:
        log_info("Only 'tar' is available for creating the archive.")
        return "tar"
    elif "7z" in available_tools:
        log_info("Only '7z' is available for creating the archive.")
        return "7z"
    else:
        log_error("Neither 'tar' nor '7z' is available. Please install at least one of them and try again.")
        print("Neither 'tar' nor '7z' is available. Please install at least one of them and try again.")
        sys.exit(1)

# Function to validate and normalize user input
def normalize_version_input(user_input):
    log_info("Validating the user input for the version number.")
    match = re.match(r"(\d{4}\.\d\.\d)", user_input)
    if match:
        log_info(f"Successfully validated version: {match.group(1)}")
        return match.group(1)
    else:
        log_error("Invalid version input format.")
        return None

def display_versions():
    """
    Display available versions in multiple columns in descending order.
    """
    log_info("Displaying available versions in multiple columns.")
    versions_list = sorted(black_duck_versions, reverse=True)
    column_count = 4
    row_count = math.ceil(len(versions_list) / column_count)
    columns = [[] for _ in range(column_count)]

    for i, version in enumerate(versions_list):
        columns[i % column_count].append(version)

    for row in range(row_count):
        for col in range(column_count):
            if row < len(columns[col]):
                print(f"{columns[col][row]:<15}", end=' ')
        print()

def clean_up():
    """
    Clean up hub directory and images file if they exist.
    """
    if os.path.exists("hub"):
        subprocess.run(["rm", "-rf", "hub"], check=True)
        log_info("Removed 'hub' directory.")
    
    if os.path.exists("images"):
        os.remove("images")
        log_info("Removed 'images' file.")

def clone_hub_repo(version):
    """
    Clone the specified version of the Black Duck Hub repository.
    """
    log_info(f"Cloning Black Duck Hub repository for version {version}.")
    try:
        subprocess.run(["git", "config", "--global", "advice.detachedHead", "false"], check=True)
        subprocess.run(["git", "clone", "--branch", f"v{version}", "https://github.com/blackducksoftware/hub.git"], check=True)
        log_info(f"Successfully cloned Black Duck Hub repository for version {version}.")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to clone Black Duck Hub repository: {e}")
        sys.exit(1)

def extract_image_names():
    """
    Extract image names from the cloned Black Duck Hub repository.
    """
    log_info("Extracting image names from the cloned Black Duck Hub repository.")
    try:
        cmd = "grep -R 'image' hub/docker-swarm/*.yml | awk '{print $3}' | sort | uniq > images"
        subprocess.run(cmd, shell=True, check=True)
        log_info("Successfully extracted image names and saved to 'images' file.")
        with open('images', 'r') as file:
            images = file.read().strip().split('\n')
        return images
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to extract image names: {e}")
        sys.exit(1)

def filter_images(images, bdba_needed, rl_needed, ubi_needed):
    """
    Filter images based on user input.
    """
    log_info("Filtering images based on user input.")
    filtered_images = []
    for image in images:
        if not bdba_needed and "bdba-worker" in image:
            continue
        if not rl_needed and "rl-service" in image:
            continue
        if ubi_needed and "ubi" not in image:
            continue
        if not ubi_needed and "ubi" in image:
            continue
        filtered_images.append(image)
    return filtered_images

def iron_bank_login(username, password):
    """
    Authenticate to the Iron Bank registry.
    """
    log_info("Authenticating to Iron Bank registry.")
    try:
        cmd = f"echo {password} | docker login -u {username} --password-stdin registry1.dso.mil"
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        log_info("Successfully logged into Iron Bank registry.")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to log into Iron Bank registry: {e}")
        sys.exit(1)

def pull_images(images, registry=None):
    """
    Pull images from the specified registry or Docker Hub.
    """
    log_info(f"Pulling images from {'Iron Bank registry' if registry else 'Docker Hub'}.")
    pulled_images = []
    for image in images:
        if registry:
            image_name = image.split('/')[-1]
            tag = image.split(':')[-1]
            image = f"{registry}/synopsys/blackduck/{image_name.split(':')[0]}:{tag}"
        log_info(f"Pulling image: {image}")
        print(f"Running command: docker pull {image}")
        try:
            subprocess.run(["docker", "image", "pull", image], check=True)
            log_info(f"Successfully pulled {image}")
            pulled_images.append(image)
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to pull image {image}: {e}")
    return pulled_images

def save_images_to_tar(images):
    """
    Save pulled images to tar files.
    """
    log_info("Saving pulled images to tar files.")
    try:
        for image in images:
            image_name = image.split(':')[0].split('/')[-1]
            tag = image.split(':')[-1]
            tar_file = f"{image_name}_{tag}.tar"
            log_info(f"Saving image {image} to {tar_file}")
            subprocess.run(["docker", "image", "save", image, "-o", tar_file], check=True)
            log_info(f"Successfully saved {image} to {tar_file}")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to save image to tar: {e}")
    except Exception as e:
        log_error(f"Unexpected error while saving images to tar: {e}")

def create_tarball(archive_tool):
    """
    Create a tarball of all saved images using the specified archive tool.
    """
    log_info(f"Creating a tarball of all saved images using {archive_tool}.")
    try:
        if archive_tool == 'tar':
            with tarfile.open('images.tar.gz', 'w:gz') as tar:
                for tar_file in os.listdir('.'):
                    if tar_file.endswith('.tar'):
                        log_info(f"Adding {tar_file} to images.tar.gz")
                        tar.add(tar_file)
            log_info("Successfully created images.tar.gz")
        elif archive_tool == '7z':
            cmd = "7z a -ttar -so images.tar " + " ".join([f for f in os.listdir('.') if f.endswith('.tar')]) + " | 7z a -si images.tar.gz"
            subprocess.run(cmd, shell=True, check=True)
            log_info("Successfully created images.tar.gz")
    except Exception as e:
        log_error(f"Error creating archive with {archive_tool}: {e}")

def main():
    print("Starting the Black Duck image management script.")
    log_info("Starting the Black Duck image management script.")

    print("\nStep 1: Checking for required tools.")
    log_info("Step 1: Checking for required tools.")
    available_tools = check_required_tools()
    print("All required command-line tools are installed.")
    log_info("All required command-line tools are installed.")

    clean_up()

    while True:
        print("\nStep 2: Enter the version number (e.g., '2024.7.0') or 'list' to see available versions:")
        log_info("Step 2: Prompting user for version number or list command.")
        user_input = input("Enter the version number (e.g., '2024.7.0') or 'list' to see available versions (default is '2024.7.0'):\n").strip()
        
        if user_input.lower() == 'list':
            display_versions()
            continue

        if user_input == '':
            version = '2024.7.0'
        else:
            version = normalize_version_input(user_input)
        
        if not version:
            log_error("Invalid version input. Please try again.")
            print("Invalid version input. Please try again.")
            continue

        if version not in black_duck_versions:
            log_error(f"Version {version} not found in the configuration. Please try again.")
            print(f"Version {version} not found in the configuration. Please try again.")
            continue

        print(f"\nObtaining image names and versions based on your selection of Black Duck v{version}.")
        log_info(f"Obtaining image names and versions based on your selection of Black Duck v{version}.")
        clone_hub_repo(version)
        images = extract_image_names()
        break

    print("\nStep 3: Asking about 'extra' images required.")
    log_info("Step 3: Asking about 'extra' images required.")
    bdba_needed = input("Do you need the BDBA container? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    rl_needed = input("Do you need the Reversing Labs container? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    ubi_needed = input("Do you need UBI images? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    
    filtered_images = filter_images(images, bdba_needed, rl_needed, ubi_needed)
    
    if ubi_needed:
        username = input("Enter your Iron Bank username: ")
        password = input("Enter your Iron Bank CLI secret: ")
        iron_bank_login(username, password)
        registry = "registry1.dso.mil/ironbank"
    else:
        registry = None

    print("\nStep 4: Pulling images.")
    log_info("Step 4: Pulling images.")
    pulled_images = pull_images(filtered_images, registry)

    print("\nStep 5: Saving images to tar files.")
    log_info("Step 5: Saving images to tar files.")
    save_images_to_tar(pulled_images)

    archive_tool = prompt_archive_tool(available_tools)

    print(f"\nStep 6: Creating {archive_tool} archive.")
    log_info(f"Step 6: Creating {archive_tool} archive.")
    create_tarball(archive_tool)

    clean_up()

    print("\nStep 7: Providing user notes.")
    log_info("Step 7: Providing user notes.")
    log_info("Note: Move the tarball (images.tar.gz) to the target server using a jump box.")
    log_info("Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'")
    print("Note: Move the tarball (images.tar.gz) to the target server using a jump box.")
    print("Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'")

    log_info("You do not need to untar the individual images as Docker can load them as .tar archives.")
    log_info("Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done")
    print("You do not need to untar the individual images as Docker can load them as .tar archives.")
    print("Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done")

    log_info("Process complete. If there were no errors, the images should be ready for use.")
    print("Process complete. If there were no errors, the images should be ready for use.")

if __name__ == "__main__":
    main()
