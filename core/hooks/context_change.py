# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This hook gets executed before and after the context changes in Toolkit.
"""
import os
from tank import get_hook_baseclass


class ContextChange(get_hook_baseclass()):
    """
    - If an engine **starts up**, the ``current_context`` passed to the hook
      methods will be ``None`` and the ``next_context`` parameter will be set
      to the context that the engine is starting in.

    - If an engine is being **reloaded**, in the context of an engine restart
      for example, the ``current_context`` and ``next_context`` will usually be
      the same.

    - If a **context switch** is requested, for example when a user switches
      from project to shot mode in Nuke Studio, ``current_context`` and ``next_context``
      will contain two different context.

    .. note::

       These hooks are called whenever the context is being set in Toolkit. It is
       possible that the new context will be the same as the old context. If
       you want to trigger some behavior only when the new one is different
       from the old one, you'll need to compare the two arguments using the
       ``!=`` operator.
    """

    __field_camera_raw = "sg_camera_raw"
    __field_lut = "sg_lut"
    __field_cut_in = "sg_cut_in"
    __field_cut_out = "sg_cut_out"
    __field_head_in = "sg_head_in"
    __field_tail_out = "sg_tail_out"

    __shot_fields = ['code', 'sg_sequence', __field_camera_raw,
                     __field_lut, __field_cut_in, __field_cut_out,
                     __field_head_in, __field_tail_out]
    __seq_fields = ['code', __field_camera_raw, __field_lut]
    __show_fields = ['code', __field_camera_raw, __field_lut]

    def pre_context_change(self, current_context, next_context):
        """
        Executed before the context has changed.

        The default implementation does nothing.

        :param current_context: The context of the engine.
        :type current_context: :class:`~sgtk.Context`
        :param next_context: The context the engine is switching to.
        :type next_context: :class:`~sgtk.Context`
        """

        if next_context != current_context and next_context is not None:

            env_vars = {
                "SHOW": None,
                "SEQ": None,
                "SHOT": None,
                "LUT": None,
                "CAMERA_RAW": None,
                "EDIT_CUT_IN": None,
                "EDIT_CUT_OUT": None,
                "EDIT_HEAD_IN": None,
                "EDIT_TAIL_OUT": None,
            }

            if next_context.entity:
                type = next_context.entity['type']
                id = next_context.entity['id']
                if type == "Shot":
                    shot_entity = next_context.sgtk.shotgun.find_one(type, [['id', 'is', id]], self.__shot_fields)
                    shot_code = shot_entity.get('code')

                    seq_id = shot_entity.get('sg_sequence').get('id')
                    seq_entity = next_context.sgtk.shotgun.find_one('Sequence', [['id', 'is', seq_id]], self.__seq_fields)
                    seq_code = seq_entity.get('code')

                    show_id = next_context.project['id']
                    show_entity = next_context.sgtk.shotgun.find_one('Project', [['id', 'is', show_id]], self.__show_fields)
                    show_code = show_entity.get('code')

                    shot_camera_raw, shot_lut = shot_entity.get(self.__field_camera_raw), shot_entity.get(self.__field_lut)
                    seq_camera_raw, seq_lut = seq_entity.get(self.__field_camera_raw), seq_entity.get(self.__field_lut)
                    show_camera_raw, show_lut = show_entity.get(self.__field_camera_raw), show_entity.get(self.__field_lut)

                    env_vars["SHOW"] = show_code
                    env_vars["SEQ"] = seq_code
                    env_vars["SHOT"] = shot_code

                    env_vars["EDIT_CUT_IN"] = shot_entity.get(self.__field_cut_in)
                    env_vars["EDIT_CUT_OUT"] = shot_entity.get(self.__field_cut_out)
                    env_vars["EDIT_HEAD_IN"] = shot_entity.get(self.__field_head_in)
                    env_vars["EDIT_TAIL_OUT"] = shot_entity.get(self.__field_tail_out)

                    if shot_camera_raw:
                        env_vars["CAMERA_RAW"] = shot_camera_raw
                    elif seq_camera_raw:
                        env_vars["CAMERA_RAW"] = seq_camera_raw
                    elif show_camera_raw:
                        env_vars["CAMERA_RAW"] = show_camera_raw

                    if shot_lut:
                        env_vars["LUT"] = shot_lut
                    elif seq_lut:
                        env_vars["LUT"] = seq_lut
                    elif show_lut:
                        env_vars["LUT"] = show_lut

                if type == "Sequence":
                    seq_entity = next_context.sgtk.shotgun.find_one(type, [['id', 'is', id]], self.__seq_fields)
                    seq_code = seq_entity.get('code')

                    show_id = next_context.project['id']
                    show_entity = next_context.sgtk.shotgun.find_one('Project', [['id', 'is', show_id]], self.__show_fields)
                    show_code = show_entity.get('code')

                    seq_camera_raw, seq_lut = seq_entity.get(self.__field_camera_raw), seq_entity.get(self.__field_lut)
                    show_camera_raw, show_lut = show_entity.get(self.__field_camera_raw), show_entity.get(self.__field_lut)

                    env_vars["SHOW"] = show_code
                    env_vars["SEQ"] = seq_code

                    if seq_camera_raw:
                        env_vars["CAMERA_RAW"] = seq_camera_raw
                    elif show_camera_raw:
                        env_vars["CAMERA_RAW"] = show_camera_raw

                    if seq_lut:
                        env_vars["LUT"] = seq_lut
                    elif show_lut:
                        env_vars["LUT"] = show_lut

            if next_context.project:
                show_id = next_context.project['id']
                show_entity = next_context.sgtk.shotgun.find_one('Project', [['id', 'is', show_id]], self.__show_fields)
                show_code = show_entity.get('code')
                show_camera_raw, show_lut = show_entity.get(self.__field_camera_raw), show_entity.get(self.__field_lut)
                env_vars["SHOW"] = show_code
                if show_camera_raw:
                    env_vars["CAMERA_RAW"] = show_camera_raw
                if show_lut:
                    env_vars["LUT"] = show_lut

            # set the env variables for OCIO to pick up
            for key, value in env_vars.iteritems():
                if not value:
                    if os.environ.get(key):
                        self.logger.debug("Clearing ENV variable: {}".format(key))
                        os.environ.pop(key)
                else:
                    self.logger.debug("Setting ENV variable: {} = {}".format(key, value))
                    os.environ[key] = str(value)

    def post_context_change(self, previous_context, current_context):
        """
        Executed after the context has changed.

        The default implementation does nothing.

        :param previous_context: The previous context of the engine.
        :type previous_context: :class:`~sgtk.Context`
        :param current_context: The current context of the engine.
        :type current_context: :class:`~sgtk.Context`
        """
        pass
