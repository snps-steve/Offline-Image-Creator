
# Black Duck Image Management Script

## Overview
This script automates the process of pulling, saving, and archiving Docker images for various versions of Black Duck. It supports pulling both standard and UBI (hardened) images, as well as optional BDBA and Reversing Labs containers.

## Prerequisites
- Python 3.x
- Docker installed and running
- Required Python packages: `pyyaml`
- Required command-line tools: `curl`, `tar`, `7z`

## Setup

1. Clone the repository:
   ```sh
   git clone https://github.com/snps-steve/Offline-Image-Creator.git
   cd Offline-Image-Creator
   ```

2. Ensure you have the required Python packages installed:
   ```sh
   pip install pyyaml
   ```

## Usage

Run the script:
```sh
python script.py
```

The script will guide you through the following steps:

1. **Checking for required packages and tools**: The script checks for necessary Python packages and command-line tools.

2. **Cleaning up**: The script deletes any existing `hub` directory and `images` file to ensure a clean environment.

3. **Selecting Black Duck version**: You will be prompted to select a Black Duck version from a list of supported versions. The default version is `2024.7.0`.

4. **Obtaining image names and versions**: The script clones the specified version of the Black Duck repository to obtain the necessary image names and versions.

5. **Asking about 'extra' images required**:
    - Whether you need BDBA containers (default: no).
    - Whether you need Reversing Labs containers (default: no).
    - Whether you need UBI (hardened) images (default: no).

6. **Authentication to Iron Bank registry**: If UBI images are required, you will be prompted to enter your Iron Bank username and CLI secret to authenticate.

7. **Pulling images**: The script pulls the required images from Docker Hub or Iron Bank registry based on your selections.

8. **Saving images to tar files**: The pulled images are saved as tar files.

9. **Creating archive**: The tar files are archived using `tar`.

10. **Providing user notes**: Instructions are provided for transferring and loading the images on the target server.

## Important Notes

- **Moving the tarball**: Move the tarball (`images.tar.gz`) to the target server using a jump box.
- **Untarring the tarball**: On the target server, untar the tarball using:
  ```sh
  tar xvf images.tar.gz
  ```
- **Loading images**: You do not need to untar the individual images as Docker can load them as tar archives. Load the images with the command:
  ```sh
  for i in $(ls *.tar); do docker load -i $i; done
  ```

## Example Usage

```sh
python script.py
```

1. **Checking for required Python packages**.
2. **Checking for required command-line tools**.
3. **Obtaining image names and versions based on your selection of Black Duck v2024.7.0**.
4. **Asking about 'extra' images required**:
    - Do you need the BDBA container? (yes/no) (default is no):
    - Do you need the Reversing Labs container? (yes/no) (default is no):
    - Do you need UBI images? (yes/no) (default is no):
    - Enter your Iron Bank username:
    - Enter your Iron Bank CLI secret:
5. **Creating images archive**.
6. **Providing user notes**:
    - Note: Move the tarball (`images.tar.gz`) to the target server using a jump box.
    - Once on the target server, untar the tarball using:
      ```sh
      tar xvf images.tar.gz
      ```
    - You do not need to untar the individual images as Docker can load them as tar archives. Load the images with the command:
      ```sh
      for i in $(ls *.tar); do docker load -i $i; done
      ```

## Contributing

Feel free to open issues or submit pull requests for any improvements.

## License

This project is licensed under the MIT License.
