"""
App Launch Hook

This hook is executed to launch the applications.
"""

import os
import sys
import sgtk


class AppLaunch(sgtk.Hook):
    """
    Hook to run an application.
    """

    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        """
        The execute functon of the hook will be called to start the required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.

        :returns: (dict) The two valid keys are 'command' (str) and 'return_code' (int).
        """
        system = sys.platform

        if system in "linux2": # py2/3 compatible
            # on linux, we launch a gnome terminal in debug mode
            if kwargs.get('show_prompt') or os.getenv('TK_DEBUG'):
                cmd = 'gnome-terminal -- bash -c "{} {}; exec bash"'.format(app_path, app_args)
            else:
                cmd = "{} {} &".format(app_path, app_args)

        elif system == "darwin":
            # If we're on OS X, then we have two possibilities: we can be asked
            # to launch an application bundle using the "open" command, or we
            # might have been given an executable that we need to treat like
            # any other Unix-style command. The best way we have to know whether
            # we're in one situation or the other is to check the app path we're
            # being asked to launch; if it's a .app, we use the "open" command,
            # and if it's not then we treat it like a typical, Unix executable.
            if app_path.endswith(".app"):
                # The -n flag tells the OS to launch a new instance even if one is
                # already running. The -a flag specifies that the path is an
                # application and supports both the app bundle form or the full
                # executable form.
                cmd = "open -n -a \"%s\"" % (app_path)
                if app_args:
                    cmd += " --args \"%s\"" % app_args.replace("\"", "\\\"")
            else:
                cmd = "%s %s &" % (app_path, app_args)

        elif system == "win32":
            # on windows, we run the start command.
            if kwargs.get('show_prompt') or os.getenv('TK_DEBUG'):
                prompt_flag = ""
            else:
                # if we're NOT in debug mode we use the the /B flag which suppress
                # the cmd window
                prompt_flag = "/B "
            cmd = "start {}\"{}\" \"{}\" {}".format(prompt_flag, engine_name, app_path, app_args)

        # run the command to launch the app
        exit_code = os.system(cmd)

        return {
            "command": cmd,
            "return_code": exit_code
        }
