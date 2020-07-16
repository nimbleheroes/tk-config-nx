# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Before App Launch Hook

This hook is executed prior to application launch and is useful if you need
to set environment variables or run scripts as part of the app initialization.
"""

import sgtk
import sys
import re
import os
from collections import defaultdict


class BeforeAppLaunch(sgtk.Hook):
    """
    Hook to set up the system prior to app launch.
    """

    __env_vars_entity = "CustomNonProjectEntity02"
    __version_regex = re.compile(r"(\d+)\.?(\d+)?(?:\.|v)?(\d+)?")

    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        """
        The execute functon of the hook will be called prior to starting the required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.

        """

        # accessing the current context (current shot, etc)
        # can be done via the parent object
        #
        # > multi_launchapp = self.parent
        # > current_entity = multi_launchapp.context.entity

        # you can set environment variables like this:
        # os.environ["MY_SETTING"] = "foo bar"

        current_context = self.parent.context
        self.logger.debug("engine_name: {}".format(engine_name))
        self.logger.debug("current_context: {}".format(current_context))
        self.logger.debug("user: {}".format(current_context.user))
        self.logger.debug("app_path: {}".format(app_path))
        self.logger.debug("app_args: {}".format(app_args))
        self.logger.debug("version: {}".format(version))

        # load up the tk-framework-cbfx
        nx_fw = self.load_framework("tk-framework-nx_v0.0.x")
        nx_utils = nx_fw.import_module("utils")

        # make a dict to store env variables
        env_dict = defaultdict(list)

        # get all the pipe templates and set env vars
        pipe_templates = {
            k: v for k, v in self.sgtk.templates.iteritems() if k.startswith("pipe_")}
        for k, v in pipe_templates.iteritems():
            v = nx_utils.resolve_template(v, current_context)
            v = os.path.expandvars(v)
            k = k.upper()
            self.logger.debug("Setting env {}={}".format(k, v))
            os.environ[k] = v

        # get env var plugins
        if engine_name:
            plugins = self.__get_env_vars(
                current_context, engine_name, version)
            for plugin in plugins:
                paths = plugins[plugin]
                self.logger.debug("[NEXODUS] Parsing plugin: {} = {}".format(
                    plugin, plugins[plugin]))
                for path in paths:
                    env_dict.setdefault(plugin, []).append(path)

        for k, vlist in env_dict.iteritems():
            for v in vlist:
                v = os.path.expandvars(v)
                self.logger.debug(
                    "[NEXODUS] Appending env var: {}={}".format(k, v))
                sgtk.util.append_path_to_env_var(k, v)

        # Sets the current task to in progress
        if self.parent.context.task:
            task_id = self.parent.context.task['id']
            task = self.parent.sgtk.shotgun.find_one(
                "Task", filters=[["id", "is", task_id]], fields=["sg_status_list"])
            self.logger.debug("[NEXODUS] task {} status is {}".format(
                task_id, task['sg_status_list']))
            if task['sg_status_list'] == 'rdy':
                data = {
                    'sg_status_list': 'ip'
                }
                self.parent.shotgun.update("Task", task_id, data)
                self.logger.debug("[NEXODUS] changed task status to 'ip'")

    def __get_env_vars(self, context, engine_name, app_version):

        filters = [
            ['sg_status_list', 'is', 'act'],
            {
                'filter_operator': 'any',
                'filters': [
                    ['sg_host_engines', 'contains', engine_name],
                    ['sg_host_engines', 'is', None],
                ]
            },
            {
                'filter_operator': 'any',
                'filters': [
                    ['sg_projects', 'in', context.project],
                    ['sg_projects', 'is', None],
                ]
            },
            {
                'filter_operator': 'any',
                'filters': [
                    ['sg_users', 'in', context.user],
                    ['sg_users', 'is', None],
                ]
            }
        ]
        os_envs = {'win32': 'sg_env_win',
                   'linux2': 'sg_env_linux', 'darwin': 'sg_env_mac'}
        fields = ['code', 'sg_version',
                  'sg_host_min_version', 'sg_host_max_version']
        fields.append(os_envs[sys.platform])
        results = self.parent.shotgun.find(
            self.__env_vars_entity, filters, fields)

        env_list = []
        for result in results:
            if (
                self.__min_check(app_version, result.get('sg_host_min_version')) and
                self.__max_check(
                    app_version, result.get('sg_host_max_version'))
            ):
                try:
                    self.logger.debug(
                        "[NEXODUS] Valid plugin found: {}".format(result.get('code')))
                    env_list.extend(result.get(
                        os_envs[sys.platform]).split('\n'))
                except AttributeError as e:
                    self.logger.error(
                        'AttributeError on plugin \'{}\': {}'.format(result.get('code'), e))
                    pass

        env_dict = {}
        for i in env_list:
            try:
                env_dict.setdefault(
                    i.split('=')[0], []).append(i.split('=')[1])
            except IndexError as e:
                self.logger.error(
                    'IndexError on plugin \'{}\': {}'.format(result.get('code'), e))
                pass

        return env_dict

    def __min_check(self, curr_version, min_version):
        if min_version is None:
            return True
        else:
            min_version = re.match(self.__version_regex, min_version).groups()
            curr_version = re.match(
                self.__version_regex, curr_version).groups()
            return curr_version >= min_version

    def __max_check(self, curr_version, max_version):
        if max_version is None:
            return True
        else:
            max_version = re.match(self.__version_regex, max_version).groups()
            curr_version = re.match(
                self.__version_regex, curr_version).groups()
            return curr_version <= max_version
