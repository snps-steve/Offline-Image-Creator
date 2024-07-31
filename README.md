This utility supports air gapped deployments of Black Duck:<br>
<br>
Step 1: Checks for required Python packages.<br>
Step 2: Checks for required command-line tools.<br>
Step 3: Checking for the existence of the configuration file containing the Black Duck version and Container image names.<br>
Step 4: Loads the YAML file. <br>
Step 5: Request that the user enter the version of Black Duck for which they want the script to download the associated images.<br>
Step 6: Displays the image names and versions for the selected Black Duck version.<br>
Step 7: Pulls the images from GitHub.<br>
Step 8: Pulls images not on GitHub manually.<br> 
Step 9: Pulls all images with tags and saves list to 'images' file.<br>
Step 10: Saves images to individual tar files using tags.<br>
Step 11: Saving each image to tar files.<br>
Step 12: Creates a tarball archive (can take a while).<br>
<br>
Provides instructions to the user to complete the rest of the process, namely:<br>
<br>
Note: Move either the tarball of all of the images (images.tar.gz) or each image <br>
archive to the Black Duck target server using your preferred method.<br>
Once on the target server, untar the tarball using: 'tar xvf images.tar.gz'<br>
You do not need to untar the individual images as Docker can load them as .tar archives.<br>
Load the images with the command: for i in $(ls *.tar); do docker load -i $i; done<br>
Process complete. If there were no errors, the images should be ready for"<br>
