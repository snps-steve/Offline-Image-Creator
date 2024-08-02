import os
import re
import subprocess
import tarfile
import sys
import json
from datetime import datetime
import math

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

# Check if the required package is installed
def check_required_packages():
    try:
        import yaml
        log_info("Required packages are installed.")
    except ImportError:
        missing_packages = ['pyyaml']

        install = input(f"The following packages are missing: {missing_packages}. Do you want to install them? Yes/no (default is Yes): ").strip().lower()
        if install in ('', 'y', 'yes'):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
                log_info("Successfully installed required packages.")
                import yaml
            except subprocess.CalledProcessError as e:
                log_error(f"Failed to install packages: {e}")
                sys.exit(1)
        elif install in ('n', 'no'):
            log_info("Installation aborted by the user.")
            sys.exit(1)
        else:
            log_info("Invalid input. Installation aborted.")
            sys.exit(1)

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
        while True:
            choice = input("Both 'tar' and '7z' are available. Which one would you like to use for creating the archive? (tar/7z) (default is tar): ").strip().lower() or "tar"
            if choice in ["tar", "7z"]:
                log_info(f"User selected '{choice}' for creating the archive.")
                return choice
            else:
                print("Invalid choice. Please enter 'tar' or '7z'.")
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

def display_versions(versions):
    """
    Display available versions in multiple columns in descending order.
    """
    log_info("Displaying available versions in multiple columns.")
    versions_list = sorted(versions, reverse=True)
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

def iron_bank_login(username, password):
    """Authenticate to the Iron Bank registry."""
    log_info("Authenticating to Iron Bank registry.")
    try:
        cmd = f"echo {password} | docker login -u {username} --password-stdin registry1.dso.mil"
        subprocess.run(cmd, shell=True, check=True)
        log_info("Successfully logged into Iron Bank registry.")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to log into Iron Bank registry: {e}")
        sys.exit(1)

# Function to filter images based on user input
def filter_images(images, bdba_needed, rl_needed, ubi_needed):
    """Filter images based on user input."""
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

# Function to pull images from GitHub
def pull_images_from_github(version):
    log_info("Pulling images from the GitHub repository.")
    try:
        cmd = f"git clone https://github.com/blackducksoftware/hub.git --branch v{version} && grep -R 'image' hub/docker-swarm/*.yml | awk '{{print $3}}' | sort | uniq > images"
        subprocess.run(cmd, shell=True, check=True)
        log_info("Successfully saved images with tags to 'images' file.")
        with open('images', 'r') as file:
            images = file.read().strip().split('\n')
        valid_images = []
        for image in images:
            if re.match(r"^[\w.-]+/[\w.-]+:[\w.-]+$", image):
                log_info(f"Valid image reference found: {image}")
                valid_images.append(image)
            else:
                log_error(f"Invalid image reference format: {image}")
        return valid_images
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to pull images from GitHub: {e}")
        sys.exit(1)
    except Exception as e:
        log_error(f"Unexpected error while pulling images from GitHub: {e}")
        sys.exit(1)

# Function to pull images from the specified registry or Docker Hub
def pull_images(images, registry=None):
    """Pull images from the specified registry or Docker Hub."""
    log_info(f"Pulling images from {'Iron Bank registry' if registry else 'Docker Hub'}.")
    pulled_images = []
    for image in images:
        original_image = image
        if registry:
            image_parts = image.split('/')
            image_name = image_parts[-1]
            image = f"{registry}/synopsys/blackduck/{image_name}"
        log_info(f"Pulling image: {image}")
        print(f"Running command: docker pull {image}")
        try:
            subprocess.run(["docker", "image", "pull", image], check=True)
            log_info(f"Successfully pulled {image}")
            pulled_images.append(original_image)  # Append the original image name for saving
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to pull image {image}: {e}")
    return pulled_images

# Function to save images to tar files
def save_images_to_tar(images):
    log_info("Saving pulled images to tar files.")
    try:
        for image in images:
            image_parts = image.split(':')
            image_name = image_parts[0].split('/')[-1]
            tag = image_parts[1]
            tar_file = f"{image_name}-{tag}.tar" if "ubi" in tag else f"{image_name}.tar"
            log_info(f"Saving image {image} to {tar_file}")
            subprocess.run(["docker", "image", "save", image, "-o", tar_file], check=True)
            log_info(f"Successfully saved {image} to {tar_file}")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to save image to tar: {e}")
    except Exception as e:
        log_error(f"Unexpected error while saving images to tar: {e}")

# Function to create a tarball of all tar files
def create_tarball(archive_tool):
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

# Function to clean up files and directories
def clean_up():
    log_info("Cleaning up temporary files and directories.")
    if os.path.exists("hub"):
        subprocess.run(["rm", "-rf", "hub"])
    if os.path.exists("images"):
        os.remove("images")

# Main script
def main():
    print("Starting the Black Duck image management script.")
    log_info("Starting the Black Duck image management script.")

    print("\nStep 1: Checking for required packages and tools.")
    log_info("Step 1: Checking for required packages and tools.")
    check_required_packages()
    print("All required Python packages are installed.")
    log_info("All required Python packages are installed.")
    available_tools = check_required_tools()
    print("All required command-line tools are installed.")
    log_info("All required command-line tools are installed.")

    clean_up()

    print("\nStep 2: Selecting Black Duck version.")
    log_info("Step 2: Selecting Black Duck version.")
    while True:
        user_input = input(f"Enter the Black Duck version (e.g., '2024.7.0') or 'list' to see available versions (default is 2024.7.0): ").strip() or "2024.7.0"
        if user_input.lower() == 'list':
            display_versions(black_duck_versions)
            continue

        version = normalize_version_input(user_input)
        if not version:
            log_error("Invalid version input. Please try again.")
            print("Invalid version input. Please try again.")
            continue

        if version not in black_duck_versions:
            log_error(f"Version {version} not found in the configuration. Please try again.")
            print(f"Version {version} not found in the configuration. Please try again.")
            continue

        break

    print(f"\nObtaining image names and versions based on your selection of Black Duck v{version}.")
    log_info(f"Obtaining image names and versions based on your selection of Black Duck v{version}.")
    images = pull_images_from_github(version)

    print("\nStep 3: Asking about 'extra' images required.")
    log_info("Step 3: Asking about 'extra' images required.")
    bdba_needed = input("Do you need the BDBA container? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    rl_needed = input("Do you need the Reversing Labs container? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']
    ubi_needed = input("Do you need UBI images? (yes/no) (default is no): ").strip().lower() in ['yes', 'y']

    if ubi_needed:
        iron_bank_username = input("Enter your Iron Bank username: ").strip()
        iron_bank_password = input("Enter your Iron Bank CLI secret: ").strip()
        iron_bank_login(iron_bank_username, iron_bank_password)
        filtered_images = filter_images(images, bdba_needed, rl_needed, ubi_needed)
        pulled_images = pull_images(filtered_images, registry="registry1.dso.mil/ironbank/synopsys/blackduck")
    else:
        filtered_images = filter_images(images, bdba_needed, rl_needed, ubi_needed)
        pulled_images = pull_images(filtered_images)

    print("\nStep 4: Saving images to tar files.")
    log_info("Step 4: Saving images to tar files.")
    save_images_to_tar(pulled_images)

    print("\nStep 5: Creating archive of images.")
    log_info("Step 5: Creating archive of images.")
    archive_tool = prompt_archive_tool(available_tools)
    create_tarball(archive_tool)

    print("\nStep 6: Providing user notes.")
    log_info("Step 6: Providing user notes.")
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

    clean_up()

if __name__ == "__main__":
    main()
