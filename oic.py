import os
import re
import subprocess
import tarfile
import sys
import json
from datetime import datetime
import math
import tempfile
import base64
import shutil
import getpass
import time
import stat
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def check_and_install_packages():
    """Function to check for necessary packages and install them if missing."""
    missing_packages = []
    necessary_packages = [
        "os", "re", "subprocess", "tarfile", "sys", "json",
        "datetime", "math", "tempfile", "base64", "shutil",
        "getpass", "time", "stat", "logging"]

    for package in necessary_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        install = input(f"The following packages are missing: {missing_packages}. Do you want to install them? Yes/no (default is Yes): ").strip().lower()
        if install in ('', 'y', 'yes'):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to install packages: {e}")
                sys.exit(1)
        else:
            logging.info("Installation aborted by the user.")
            sys.exit(1)

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
    """Append new log entries to the output dictionary and log using logging module."""
    entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'level': level,
        'message': message
    }
    output['logs'].append(entry)
    with open("logfile.json", "w") as outfile:
        json.dump(output, outfile, indent=4)
    if level == 'INFO':
        logging.info(message)
    elif level == 'ERROR':
        logging.error(message)

def check_required_tools():
    """Check if the required command-line tools are available in the system's PATH."""
    missing_tools = []
    available_tools = []
    for tool in REQUIRED_TOOLS:
        try:
            if tool == "7z":
                result = subprocess.run([tool], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if "7-Zip" in result.stdout.decode() or "7-Zip" in result.stderr.decode():
                    available_tools.append(tool)
                else:
                    missing_tools.append(tool)
            else:
                subprocess.run([tool, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                available_tools.append(tool)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_tools.append(tool)
    
    if missing_tools:
        log('ERROR', f"Missing required tools: {', '.join(missing_tools)}. Please install them and try again.")
        sys.exit(1)
    else:
        log('INFO', "All required command-line tools are installed.")
    return available_tools

def prompt_archive_tool(available_tools):
    """Prompt the user to select an archive tool if both 'tar' and '7z' are available."""
    if "tar" in available_tools and "7z" in available_tools:
        choice = input("Both 'tar' and '7z' are available. Which one would you like to use for creating the archive? (tar/7z) (default is tar): ").strip().lower()
        if choice not in ["tar", "7z"]:
            log('INFO', "Invalid choice. Defaulting to 'tar'.")
            return "tar"
        return choice
    elif "tar" in available_tools:
        return "tar"
    elif "7z" in available_tools:
        return "7z"
    else:
        log('ERROR', "Neither 'tar' nor '7z' is available. Please install at least one of them and try again.")
        sys.exit(1)

def normalize_version_input(user_input):
    """Validate and normalize user input for the version number."""
    log('INFO', "Validating the user input for the version number.")
    match = re.match(r"(\d{4}\.\d\.\d)", user_input)
    if match:
        return match.group(1)
    else:
        log('ERROR', "Invalid version input format.")
        return None

def display_versions():
    """Display available versions in multiple columns in descending order."""
    log('INFO', "Displaying available versions in multiple columns.")
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

def handle_remove_readonly(func, path, exc_info):
    """Change the file to be writable and reattempt removal."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def clean_up():
    """Clean up hub directory and images file if they exist."""
    if os.path.exists("hub"):
        try:
            shutil.rmtree("hub", onerror=handle_remove_readonly)
            log('INFO', "Removed 'hub' directory.")
        except Exception as e:
            log('ERROR', f"Failed to remove 'hub' directory: {e}")
    
    if os.path.exists("images"):
        try:
            os.remove("images")
            log('INFO', "Removed 'images' file.")
        except Exception as e:
            log('ERROR', f"Failed to remove 'images' file: {e}")

def clone_hub_repo(version):
    """Clone the specified version of the Black Duck Hub repository."""
    log('INFO', f"Cloning Black Duck Hub repository for version {version}.")
    try:
        subprocess.run(["git", "config", "--global", "advice.detachedHead", "false"], check=True)
        subprocess.run(["git", "clone", "--branch", f"v{version}", "https://github.com/blackducksoftware/hub.git"], check=True)
        log('INFO', f"Successfully cloned Black Duck Hub repository for version {version}.")
    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to clone Black Duck Hub repository: {e}")
        sys.exit(1)

def extract_image_names():
    """Extract image names from the cloned Black Duck Hub repository."""
    log('INFO', "Extracting image names from the cloned Black Duck Hub repository.")
    try:
        cmd = "grep -R 'image' hub/docker-swarm/*.yml | awk '{print $3}' | sort | uniq > images"
        subprocess.run(cmd, shell=True, check=True)
        with open('images', 'r') as file:
            images = file.read().strip().split('\n')
        return images
    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to extract image names: {e}")
        sys.exit(1)

def filter_images(images, bdba_needed, rl_needed, ubi_needed):
    """Filter images based on user input."""
    log('INFO', "Filtering images based on user input.")
    filtered_images = []
    for image in images:
        if bdba_needed and "bdba-worker" in image:
            filtered_images.append(image)
        elif rl_needed and "rl-service" in image:
            filtered_images.append(image)
        elif ubi_needed and "ubi" in image:
            filtered_images.append(image)
        elif not ubi_needed and "ubi" not in image:
            if "bdba-worker" not in image and "rl-service" not in image:
                filtered_images.append(image)
    return filtered_images

def create_docker_config():
    """Create docker-config.json with Iron Bank credentials."""
    username = input("Enter your Iron Bank username: ")
    password = getpass.getpass("Enter your Iron Bank CLI secret: ")

    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    docker_config = {
        "auths": {
            "registry1.dso.mil": {
                "username": username,
                "password": password,
                "auth": encoded_credentials
            }
        }
    }

    with open("docker-config.json", "w") as file:
        json.dump(docker_config, file, indent=4)

    print("docker-config.json file has been created successfully.")

def iron_bank_login():
    """Authenticate to the Iron Bank registry using the docker-config.json file."""
    log('INFO', "Authenticating to Iron Bank registry using docker-config.json.")
    try:
        with tempfile.TemporaryDirectory() as temp_config_dir:
            temp_config_file_path = os.path.join(temp_config_dir, 'config.json')
            
            with open(temp_config_file_path, "w") as temp_config_file:
                with open("docker-config.json", "r") as file:
                    docker_config = json.load(file)
                temp_config_file.write(json.dumps(docker_config))

            cmd = f"docker --config {temp_config_dir} login registry1.dso.mil"
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            log('INFO', "Successfully logged into Iron Bank registry using docker-config.json.")
            print(result.stdout)

    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to log into Iron Bank registry: {e}")
        sys.exit(1)
    except Exception as e:
        log('ERROR', f"Error loading docker-config.json: {e}")
        sys.exit(1)

def pull_images(images, registry=None, retries=3, delay=5):
    """Pull images from the specified registry or Docker Hub with retry logic."""
    log('INFO', f"Pulling images from {'Iron Bank registry' if registry else 'Docker Hub'}.")
    pulled_images = []
    for image in images:
        attempt = 0
        while attempt < retries:
            try:
                if registry and "ubi" in image:
                    image_name = image.split('/')[-1]
                    tag = image.split(':')[-1]
                    image = f"{registry}/synopsys/blackduck/{image_name.split(':')[0]}:{tag}"
                log('INFO', f"Pulling image: {image}")
                print(f"Running command: docker pull {image}")
                subprocess.run(["docker", "image", "pull", image], check=True)
                log('INFO', f"Successfully pulled {image}")
                pulled_images.append(image)
                break
            except subprocess.CalledProcessError as e:
                attempt += 1
                log('ERROR', f"Failed to pull image {image}: {e}. Attempt {attempt} of {retries}. Retrying in {delay} seconds...")
                time.sleep(delay)
        else:
            log('ERROR', f"Failed to pull image {image} after {retries} attempts.")
    return pulled_images

def save_images_to_tar(images):
    """Save pulled images to tar files."""
    log('INFO', "Saving pulled images to tar files.")
    try:
        for image in images:
            image_name = image.split(':')[0].split('/')[-1]
            tag = image.split(':')[-1]
            tar_file = f"{image_name}_{tag}.tar"
            log('INFO', f"Saving image {image} to {tar_file}")
            subprocess.run(["docker", "image", "save", image, "-o", tar_file], check=True)
            log('INFO', f"Successfully saved {image} to {tar_file}")
    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to save image to tar: {e}")
    except Exception as e:
        log('ERROR', f"Unexpected error while saving images to tar: {e}")

def create_tarball(archive_tool):
    """Create a tarball of all saved images using the specified archive tool."""
    log('INFO', f"Creating a tarball of all saved images using {archive_tool}.")
    try:
        if archive_tool == 'tar':
            with tarfile.open('images.tar.gz', 'w:gz') as tar:
                for tar_file in os.listdir('.'):
                    if tar_file.endswith('.tar'):
                        log('INFO', f"Adding {tar_file} to images.tar.gz")
                        tar.add(tar_file)
            log('INFO', "Successfully created images.tar.gz")
        elif archive_tool == '7z':
            cmd = "7z a -ttar -so images.tar " + " ".join([f for f in os.listdir('.') if f.endswith('.tar')]) + " | 7z a -si images.tar.gz"
            subprocess.run(cmd, shell=True, check=True)
            log('INFO', "Successfully created images.tar.gz")
    except Exception as e:
        log('ERROR', f"Error creating archive with {archive_tool}: {e}")

def docker_config_exists():
    """Check if docker-config.json already exists."""
    return os.path.exists("docker-config.json")

def main():
    print("Starting the Black Duck image management script.")
    print("\nStep 1: Checking for required packages and tools.")
    check_and_install_packages()
    log('INFO', "Step 1: Checking for required packages and tools.")
    print("All required packages are installed.")
    log('INFO', "All required packages are installed.")
    available_tools = check_required_tools()
    print("All required command-line tools are installed.")
    log('INFO', "All required command-line tools are installed.")

    clean_up()

    while True:
        print("\nStep 2: Enter the version number (e.g., '2024.7.0') or 'list' to see available versions:")
        log('INFO', "Step 2: Prompting user for version number or list command.")
        user_input = input("Enter the version number (e.g., '2024.7.0') or 'list' to see available versions (default is '2024.7.0'):\n").strip()
        
        if user_input.lower() == 'list':
            display_versions()
            continue

        version = normalize_version_input(user_input) if user_input else '2024.7.0'
        
        if not version or version not in black_duck_versions:
            log('ERROR', f"Invalid or unsupported version input. Please try again.")
            print(f"Invalid or unsupported version input. Please try again.")
            continue

        print(f"\nObtaining image names and versions based on your selection of Black Duck v{version}.")
        log('INFO', f"Obtaining image names and versions based on your selection of Black Duck v{version}.")
        clone_hub_repo(version)
        images = extract_image_names()
        break

    print("\nStep 3: Asking about 'extra' images required.")
    log('INFO', "Step 3: Asking about 'extra' images required.")
    bdba_needed = input("Do you need the BDBA container? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    rl_needed = input("Do you need the Reversing Labs container? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    ubi_needed = input("Do you need UBI images? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    
    filtered_images = filter_images(images, bdba_needed, rl_needed, ubi_needed)
    expected_image_count = len(filtered_images)
    log('INFO', f"Expected number of images to pull: {expected_image_count}")
    
    if ubi_needed:
        if docker_config_exists():
            print("docker-config.json already exists.")
            log('INFO', "docker-config.json already exists.")
            use_existing_config = input("Do you want to use the existing docker-config.json? (yes/no) (default is yes): ").strip().lower()
            if use_existing_config in ['no', 'n']:
                create_docker_config()
        else:
            create_docker_config()
        iron_bank_login()
        registry = "registry1.dso.mil/ironbank"
    else:
        registry = None

    print("\nStep 4: Pulling images.")
    log('INFO', "Step 4: Pulling images.")
    pulled_images = pull_images(filtered_images, registry)
    actual_image_count = len(pulled_images)
    log('INFO', f"Actual number of images pulled: {actual_image_count}")

    print("\nStep 5: Saving images to tar files.")
    log('INFO', "Step 5: Saving images to tar files.")
    save_images_to_tar(pulled_images)

    archive_tool = prompt_archive_tool(available_tools)

    print(f"\nStep 6: Creating {archive_tool} archive.")
    log('INFO', f"Step 6: Creating {archive_tool} archive.")
    create_tarball(archive_tool)

    clean_up()

    print("\nStep 7: Providing user notes.")
    log('INFO', "Step 7: Providing user notes.")
    log('INFO', "Note: Move the tarball (images.tar.gz) to the target server using a jump box.")
    log('INFO', "Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'")
    print("Note: Move the tarball (images.tar.gz) to the target server using a jump box.")
    print("Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'")

    log('INFO', "You do not need to untar the individual images as Docker can load them as .tar archives.")
    log('INFO', "Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done")
    print("You do not need to untar the individual images as Docker can load them as .tar archives.")
    print("Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done")

    log('INFO', "Process complete. If there were no errors, the images should be ready for use.")
    print("Process complete. If there were no errors, the images should be ready for use.")
    print(f"\nSummary: Expected to pull {expected_image_count} images. Successfully pulled {actual_image_count} images.")
    log('INFO', f"Summary: Expected to pull {expected_image_count} images. Successfully pulled {actual_image_count} images.")

if __name__ == "__main__":
    main()
