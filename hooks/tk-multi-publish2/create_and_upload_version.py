# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from distutils.command.config import config
import os
import pprint
import traceback

import sgtk
from sgtk.util.filesystem import copy_file, ensure_folder_exists
from tank_vendor import six

HookBaseClass = sgtk.get_hook_baseclass()


class BasicVersionUploadPlugin(HookBaseClass):
    """
    Plugin for creating generic versions in Shotgun.

    """

    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(self.disk_location, "icons", "create_version.png")


    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Create Shotgun Version and Upload Media"


    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        return """
        Creates a <b>Version</b> in Shotgun and Uploads a movie to it. A Version entry will be
        created in Shotgun that represents this workfile. Review quicktimes,
        frame sequences, or geometry can then be attached to this version
        and used for review.
        """


    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts
        as part of its environment configuration.
        """
        
        return {
            "create_version": {
                "type": "bool",
                "default": True,
                "description": (
                    "This gets passed to the item task and helps to "
                    "identify which task is the create_version task."
                ),
            },
        }


    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["file.image", "file.image.sequence", "file.video"]



    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        path = item.properties.get("path")
        accepted = False
    
        if path:
            accept = True

            # lets store the verison name and make a flag for the attach_to_version plugin to catch.
            item.properties.version_name = self._get_version_name(path)
            item.properties.create_version = True

            # log the accepted file and display a button to reveal it in the fs
            self.logger.info(
                "Create version plugin accepted: %s" % (path,)
            )
        else:
            self.logger.debug(
                "Create version plugin not accepted, 'path' was None"
            )
        # return the accepted info
        return {"accepted": True}


    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """

        # create a placeholder for finalize tasks
        item.properties.version_finalize = {"update": {}, "upload": {}}

        # start a count of attachments. This checked in the attach_to_version validation and
        # prevents a user from trying to attach more than 1 of each type to a version entry.
        item.properties.movies_attached = 0
        item.properties.frames_attached = 0
        item.properties.geo_attached = 0

        self.logger.info("A Version entry will be created in Shotgun: %s" % (item.properties.version_name,))

        return True


    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent
        path = item.properties["path"]
        version_name = item.properties["version_name"]
        first_frame = item.properties.get("first_frame")
        last_frame = item.properties.get("last_frame")

        self.logger.debug("Version name: %s" % (version_name,))

        self.logger.info("Creating Version...")
        version_data = {
            "published_files" : [item.properties.sg_publish_data],
            "project": item.context.project,
            "code": version_name,
            "description": item.description,
            "entity": self._get_version_entity(item),
            "sg_task": item.context.task,
            "sg_published": True,
        }

        if first_frame and last_frame:

            version_data["sg_first_frame"] = int(first_frame)
            version_data["sg_last_frame"] = int(last_frame)
            version_data["frame_range"] = "{}-{}".format(first_frame, last_frame)
            version_data["frame_count"] = int(last_frame - first_frame + 1)

        # log the version data for debugging
        self.logger.debug(
            "Populated Version data...",
            extra={
                "action_show_more_info": {
                    "label": "Version Data",
                    "tooltip": "Show the complete Version data dictionary",
                    "text": "<pre>%s</pre>" % (pprint.pformat(version_data),),
                }
            },
        )

        # Create the version
        version = publisher.shotgun.create("Version", version_data)
        self.logger.info("Version created!")

        fw = self.load_framework("tk-framework-deadline_v0.x.x")

        nxfw = self.load_framework("tk-framework-nx_v0.x.x")
        scalar = nxfw.import_module('scalar')

        parent_task = None

        # see if a dispatcher has already been made, if so use it
        upstream_scalar = item.parent.properties['upstream_scalar']
        if upstream_scalar:
            parent_task = upstream_scalar

            dispatcher =  upstream_scalar.dispatcher
        else:
            dispatcher =  scalar.Dispatcher.using_queue('sgtk_deadline', tk_framework_deadline=fw)

        transcodify_template = self.sgtk.templates["transcodify_template"]


        # prepare the path for the Shotgrid reviewable mov
        reviewable_template = self.sgtk.templates["shot_review_movies"]
        reviewable_fields = item.context.as_template_fields(reviewable_template)
        reviewable_fields['version_id'] = version['id']
        reviewable_fields['ext'] = 'mov'
        reviewable_fields['extension'] = 'mov'
        reviewable_fields['Step'] = item.context.step['name'].lower() 
        reviewable_fields['version'] = item.properties.sg_publish_data.get('version_number')
        reviewable_fields['view'] = "main"

        reviewable_path = reviewable_template.apply_fields(reviewable_fields)
    
        #movs = ["mov", "m4v", "mp4", "mxf"]
        sg_transcodify_config  = str(self.sgtk.paths_from_template(transcodify_template, {"ext": "mov", "name": "shotgun"})[0])

        if sg_transcodify_config:

            config_name = os.path.basename(os.path.splitext(sg_transcodify_config)[0])
            t1 = dispatcher.task("transcodify", 
                                name="Creating Reviewable: {}".format(config_name), 
                                input_files="{}:{}-{}".format(path, first_frame, last_frame), 
                                output_file=reviewable_path, 
                                config_file=sg_transcodify_config, 
                                context = item.context,
                                data={"sg_version": version}, 
                                parent=parent_task)
            
            t2 = dispatcher.task("sg_upload", 
                                    name="Uploading Movie to SG Version", 
                                    entity_type=version.get('type'), 
                                    entity_id=version.get('id'),
                                    src=reviewable_paths,
                                    parent=t1 )

            # associate this  as the last-created scalar task so you can either use it's dispatcher or make a child task
            item.parent.properties['upstream_scalar'] =  t2

        # stash the version info in the item just in case
        item.properties["sg_version_data"] = version


    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once
        all the publish tasks have completed, and can for example
        be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        pass



    def _get_version_name(self, path):
        """
        Returns the version name from a file path.

        :param path: The current path with a version number
        """
        # in Python3 this will become: 
        # from pathlib import Path
        # return Path(path).stem

        return os.path.splitext(os.path.basename(path))[0]


    def _get_version_entity(self, item):
        """
        Returns the best entity to link the version to.
        """

        if item.context.entity:
            return item.context.entity
        elif item.context.project:
            return item.context.project
        else:
            return None
