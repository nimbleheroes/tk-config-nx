-------------------------------------------------------------------------
Project-level Nuke configuration
-------------------------------------------------------------------------

Inside this folder are 2 folders that make up the project-level nuke
configuration:

TOOLS
The 'tools' folder is where custom gizmos and nuke scripts should go
to be used on the project. They will show up under a project icon on the
nuke toolbar. You can customize the 'tools.png' for a custom icon. Do not
rename the 'tools' folder, 'tools.png', or 'tools.settings' file.

PYTHON
The 'python' folder contains some boiler-plate init.py and menu.py
files. This is where you can go nuts with scripts (as long as you don't
break nuke for everybody!). Please keep your code tidy and be aware that
these folders are live, so if you save broken code in there, it will
break nuke for everyone. Its a good idea to develop scripts in your own
.nuke folder before deploying them here.

-------------------------------------------------------------------------
