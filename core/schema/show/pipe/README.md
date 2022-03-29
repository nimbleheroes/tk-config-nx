-------------------------------------------------------------------------
Project-level Pipeline Repository
-------------------------------------------------------------------------

Inside this folder are 2 folders that make up the project-level nuke
configuration:

./configs
The 'configs' folder contains configuration files for dccs or other
pipeline applications. The folders within are named for the dcc or
app that the configuration is for.

./defaults
The 'python' folder contains some boiler-plate init.py and menu.py
files. This is where you can go nuts with scripts (as long as you don't
break nuke for everybody!). Please keep your code tidy and be aware that
these folders are live, so if you save broken code in there, it will
break nuke for everyone. Its a good idea to develop scripts in your own
.nuke folder before deploying them here.

./templates

-------------------------------------------------------------------------
