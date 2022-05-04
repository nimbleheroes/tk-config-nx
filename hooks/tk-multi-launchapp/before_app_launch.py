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
from tank_vendor import six


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


        # get all the pipe templates and set env vars
        # pipe_templates = {k: v for k, v in six.iteritems(self.sgtk.templates) if k.startswith("pipe_")}
        # for templ_name, templ_path in six.iteritems(pipe_templates):
        #     template_fields = current_context.as_template_fields(v)
        #     if not templ_path.missing_keys(template_fields):
        #         templ_path = os.path.abspath(v.apply_fields(template_fields))
        #         templ_path = os.path.expandvars(v)
        #         templ_name = templ_name.upper()
        #         self.logger.debug("[NEXODUS] Setting env var: {} = {}".format(k, v))
        #         os.environ[templ_name] = templ_path

        # Apply Environment Variable entities
        env_dicts = self.__get_env_vars(current_context, engine_name, version)

        replace_envs = env_dicts["replace"]
        prepend_envs = env_dicts["prepend"]
        append_envs = env_dicts["append"]

        env_keys = list(set(list(replace_envs.keys()) + list(prepend_envs.keys()) + list(append_envs.keys())))
        for key in env_keys:
            sgtk.util.append_path_to_env_var("SGTK_ENV_VARS", os.path.expandvars(key))
        if os.getenv("TK_DEBUG"):
            sgtk.util.append_path_to_env_var("SGTK_ENV_VARS", "TK_DEBUG")
        self.logger.debug("[NEXODUS] SGTK_ENV_VARS = {}".format(os.getenv("SGTK_ENV_VARS")))

        for env_key, value_list in six.iteritems(replace_envs):
            for env_value in value_list:
                self.logger.debug("[NEXODUS] Setting env var: {} = {}".format(env_key, env_value))
                os.environ[env_key] = os.path.expandvars(env_value)

        for env_key, value_list in six.iteritems(prepend_envs):
            for env_value in value_list:
                self.logger.debug("[NEXODUS] Prepending env var: {} = {}".format(env_key, env_value))
                sgtk.util.prepend_path_to_env_var(env_key, os.path.expandvars(env_value))

        for env_key, value_list in six.iteritems(append_envs):
            for env_value in value_list:
                self.logger.debug("[NEXODUS] Appending env var: {} = {}".format(env_key, env_value))
                sgtk.util.append_path_to_env_var(env_key, os.path.expandvars(env_value))

        for method, env_dict in six.iteritems(env_dicts):
            for env_key in env_dict.keys():
                self.logger.debug("[NEXODUS] Env Var check: {} = {}".format(env_key, os.getenv(env_key)))

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
            ['sg_exclude_projects', 'not_in', context.project],
            ['sg_exclude_users', 'not_in', context.user],
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

        if engine_name is None:

            no_engine_filter = ['sg_host_engines', 'is', None]
            filters.append(no_engine_filter)

        else:

            with_engine_filter = {
                'filter_operator': 'any',
                'filters': [
                    ['sg_host_engines', 'contains', engine_name],
                    ['sg_host_engines', 'is', None],
                ]
            }
            filters.append(with_engine_filter)

        os_envs = {'win32': 'sg_env_win',
                   'linux2': 'sg_env_linux', # python2
                   'linux': 'sg_env_linux', # python3
                   'darwin': 'sg_env_mac'}

        fields = ['code', 'sg_version',
                  'sg_host_min_version', 'sg_host_max_version', 'sg_default_method']

        fields.append(os_envs[sys.platform])

        results = self.parent.shotgun.find(
            self.__env_vars_entity, filters, fields)

        env_lists = {"append": [], "prepend": [], "replace": []}
        for result in results:
            if not result.get(os_envs[sys.platform]):
                pass
            elif (
                self.__min_check(app_version, result.get('sg_host_min_version')) and
                self.__max_check(app_version, result.get('sg_host_max_version'))
            ):
                try:
                    self.logger.debug(
                        "[NEXODUS] Valid plugin found: {}".format(result.get('code')))
                    env_lists[result.get('sg_default_method')].extend(result.get(
                        os_envs[sys.platform]).split('\n'))
                except AttributeError as e:
                    self.logger.error(
                        'AttributeError on plugin \'{}\': {}'.format(result.get('code'), e))
                    pass

        env_dicts = {"append": {}, "prepend": {}, "replace": {}}
        for key, env_list in six.iteritems(env_lists):
            for i in env_list:
                try:
                    env_dicts[key].setdefault(
                        i.split('=')[0], []).append(i.split('=')[1])
                except IndexError as e:
                    self.logger.error(
                        'IndexError on plugin \'{}\': {}'.format(result.get('code'), e))
                    pass

        return env_dicts

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
