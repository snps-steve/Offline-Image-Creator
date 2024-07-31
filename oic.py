import os
import re
import subprocess
import tarfile
import yaml
import sys
import json
from datetime import datetime
import math

# Configuration: YAML file with Black Duck versions and images
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'black_duck_versions.yaml')

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
            choice = input("Both 'tar' and '7z' are available. Which one would you like to use for creating the archive? (tar/7z): ").strip().lower()
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

# Function to load Black Duck versions from YAML file
def load_black_duck_versions():
    log_info("Loading versions from the configuration file.")
    try:
        with open(CONFIG_FILE, 'r') as file:
            data = yaml.safe_load(file)
            log_info("Successfully loaded versions.")
            return data
    except FileNotFoundError:
        log_error(f"Configuration file '{CONFIG_FILE}' not found.")
    except yaml.YAMLError as exc:
        log_error(f"Error reading YAML file: {exc}")
    except Exception as e:
        log_error(f"Unexpected error while loading configuration: {e}")
    return {}

def display_versions(versions):
    """
    Display available versions in multiple columns in descending order.
    """
    log_info("Displaying available versions in multiple columns.")
    versions_list = sorted(list(versions.keys()), reverse=True)
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

# Function to pull images from GitHub
def pull_images_from_github():
    log_info("Pulling images from the GitHub repository.")
    try:
        cmd = "curl -s https://raw.githubusercontent.com/blackducksoftware/hub/master/docker-swarm/docker-compose.yml | grep image | awk -F '[:]' '{printf \"%s:%s\\n\",$2,$3}' | tr -d ' '"
        result = subprocess.check_output(cmd, shell=True, text=True)
        images = result.strip().split('\n')
        valid_images = []
        for image in images:
            if re.match(r"^[\w.-]+/[\w.-]+:[\w.-]+$", image):
                log_info(f"Pulling image: {image}")
                try:
                    subprocess.run(["docker", "image", "pull", image], check=True)
                    log_info(f"Successfully pulled {image}")
                    valid_images.append(image)
                except subprocess.CalledProcessError as e:
                    log_error(f"Failed to pull image {image}: {e}")
            else:
                log_error(f"Invalid image reference format: {image}")
        return valid_images
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to pull images from GitHub: {e}")
    except Exception as e:
        log_error(f"Unexpected error while pulling images from GitHub: {e}")
    return []

# Function to pull additional images manually
def pull_manual_images(version_images):
    log_info("Pulling additional images manually (bdba-worker, postgres-waiter, integration).")
    try:
        manual_images = [img for img in version_images if "bdba-worker" in img or "postgres-waiter" in img or "integration" in img]
        for image in manual_images:
            log_info(f"Pulling manual image: {image}")
            subprocess.run(["docker", "image", "pull", image], check=True)
            log_info(f"Successfully pulled {image}")
        return manual_images
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to pull manual images: {e}")
    except Exception as e:
        log_error(f"Unexpected error while pulling manual images: {e}")
    return []

# Function to save images with tags to a file
def save_images_with_tags():
    log_info("Saving images with tags to a file.")
    try:
        cmd = "curl -s https://raw.githubusercontent.com/blackducksoftware/hub/master/docker-swarm/docker-compose.yml | grep image | awk -F '[:]' '{printf \"%s:%s\\n\",$2,$3}' | tr -d ' ' > images"
        subprocess.run(cmd, shell=True, check=True)
        log_info("Successfully saved images with tags to 'images' file.")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to save images with tags: {e}")
        print(f"Failed to save images with tags: {e}")
    except Exception as e:
        log_error(f"Unexpected error while saving images with tags: {e}")
        print(f"Unexpected error while saving images with tags: {e}")

# Function to save images to tar files using tags
def save_images_to_tar_using_tags():
    log_info("Saving images to tar files using tags.")
    try:
        with open('images', 'r') as file:
            images = file.read().strip().split('\n')
        for image in images:
            image_name = image.split(':')[0].split('/')[-1]
            tar_file = f"{image_name}.tar"
            log_info(f"Saving image {image} to {tar_file}")
            subprocess.run(["docker", "image", "save", image, "-o", tar_file], check=True)
            log_info(f"Successfully saved {image} to {tar_file}")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to save image to tar: {e}")
        print(f"Failed to save image to tar: {e}")
    except Exception as e:
        log_error(f"Unexpected error while saving images to tar: {e}")
        print(f"Unexpected error while saving images to tar: {e}")

# Function to save images to tar files
def save_images_to_tar(images):
    log_info("Saving pulled images to tar files.")
    try:
        for image in images:
            image_name = image.split(':')[0].split('/')[-1]
            tar_file = f"{image_name}.tar"
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
            cmd = ["7z", "a", "images.7z"] + [f for f in os.listdir('.') if f.endswith('.tar')]
            subprocess.run(cmd, check=True)
            log_info("Successfully created images.7z")
    except Exception as e:
        log_error(f"Error creating archive with {archive_tool}: {e}")

# Main script
def main():
    print("Starting the Black Duck image management script.")
    log_info("Starting the Black Duck image management script.")

    print("\nStep 1: Checking for required Python packages.")
    log_info("Step 1: Checking for required Python packages.")
    check_required_packages()
    print("All required Python packages are installed.")
    log_info("All required Python packages are installed.")

    print("\nStep 2: Checking for required command-line tools.")
    log_info("Step 2: Checking for required command-line tools.")
    available_tools = check_required_tools()
    print("All required command-line tools are installed.")
    log_info("All required command-line tools are installed.")

    archive_tool = prompt_archive_tool(available_tools)

    print("\nStep 3: Checking for the existence of the configuration file.")
    log_info("Step 3: Checking for the existence of the configuration file.")
    if os.path.exists(CONFIG_FILE):
        log_info(f"Detected configuration file: {CONFIG_FILE}")
        print(f"Detected configuration file: {CONFIG_FILE}")
    else:
        log_error(f"Configuration file '{CONFIG_FILE}' not detected. Please ensure it exists.")
        print(f"Configuration file '{CONFIG_FILE}' not detected. Please ensure it exists.")
        sys.exit(1)

    print("\nStep 4: Loading versions from YAML file.")
    log_info("Step 4: Loading versions from YAML file.")
    black_duck_versions = load_black_duck_versions()
    if not black_duck_versions:
        log_error("Exiting script due to failure in loading configuration.")
        print("Exiting script due to failure in loading configuration.")
        sys.exit(1)

    while True:
        print("\nStep 5: Enter the version number (e.g., '2024.7.0') or 'list' to see available versions:")
        log_info("Step 5: Prompting user for version number or list command.")
        user_input = input("Enter the version number (e.g., '2024.7.0') or 'list' to see available versions:\n").strip()
        
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

        print(f"\nStep 6: Displaying images for the selected version {version}.")
        log_info(f"Step 6: Displaying images for the selected version {version}.")
        selected_images = black_duck_versions[version]
        log_info(f"Displaying images for version {version}:")
        for image in selected_images:
            print(image)
            log_info(image)

        print("\nStep 7: Pulling images from GitHub.")
        log_info("Step 7: Pulling images from GitHub.")
        github_images = pull_images_from_github()
        if not github_images:
            log_error("Exiting script due to failure in pulling images from GitHub.")
            print("Exiting script due to failure in pulling images from GitHub.")
            sys.exit(1)

        print("\nStep 8: Pulling manual images.")
        log_info("Step 8: Pulling manual images.")
        manual_images = pull_manual_images(selected_images)
        if not manual_images:
            log_error("Exiting script due to failure in pulling manual images.")
            print("Exiting script due to failure in pulling manual images.")
            sys.exit(1)

        print("\nStep 9: Pulling all images with tags and saving to 'images' file.")
        log_info("Step 9: Pulling all images with tags and saving to 'images' file.")
        save_images_with_tags()

        print("\nStep 10: Saving images to tar files using tags.")
        log_info("Step 10: Saving images to tar files using tags.")
        save_images_to_tar_using_tags()

        print("\nStep 11: Saving images to tar files.")
        log_info("Step 11: Saving images to tar files.")
        save_images_to_tar(github_images + manual_images)

        print(f"\nStep 12: Creating {archive_tool} archive.")
        log_info(f"Step 12: Creating {archive_tool} archive.")
        create_tarball(archive_tool)

        print("\nStep 13: Providing user notes.")
        log_info("Step 13: Providing user notes.")
        if archive_tool == 'tar':
            log_info("Note: Move the tarball (images.tar.gz) to the target server using a jump box.")
            log_info("Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'")
            print("Note: Move the tarball (images.tar.gz) to the target server using a jump box.")
            print("Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'")
        elif archive_tool == '7z':
            log_info("Note: Move the archive (images.7z) to the target server using a jump box.")
            log_info("Once on the target server, extract the archive using: '7z x images.7z'")
            print("Note: Move the archive (images.7z) to the target server using a jump box.")
            print("Once on the target server, extract the archive using: '7z x images.7z'")
        
        log_info("You do not need to untar the individual images as Docker can load them as .tar archives.")
        log_info("Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done")
        log_info("Process complete. If there were no errors, the images should be ready for use.")

        print("You do not need to untar the individual images as Docker can load them as .tar archives.")
        print("Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done")
        print("Process complete. If there were no errors, the images should be ready for use.")

        # Exit the loop and script
        break

if __name__ == "__main__":
    main()
