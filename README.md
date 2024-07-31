This utility:

Step 1: Checks for required Python packages.
Step 2: Checks for required command-line tools.
Step 3: Checking for the existence of the configuration file containing the Black Duck version and Container image names.
Step 4: Loads the YAML file. 
Step 5: Request that the user enter the version of Black Duck for which they want the script to download the associated images.
Step 6: Displays the image names and versions for the selected Black Duck version.
Step 7: Pulls the images from GitHub.
Step 8: Pulls images not on GitHub manually. 
Step 9: Pulls all images with tags and saves list to 'images' file.
Step 10: Saves images to individual tar files using tags.
Step 11: Saving each image to tar files.
Step 12: Creates a tarball archive (can take a while).

Provides instructions to the user to complete the rest of the process, namely:

Note: Move either the tarball of all of the images (images.tar.gz) or each image 
archive to the Black Duck target server using your preferred method.
Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'
You do not need to untar the individual images as Docker can load them as .tar archives.
Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done
Process complete. If there were no errors, the images should be ready for"
