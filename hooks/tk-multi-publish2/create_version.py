# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import pprint
import traceback

import sgtk
from sgtk.util.filesystem import copy_file, ensure_folder_exists
from tank_vendor import six

HookBaseClass = sgtk.get_hook_baseclass()


class BasicVersionPlugin(HookBaseClass):
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
        return "Create Shotgun Version"


    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        return """
        Creates a <b>Version</b> in Shotgun. A Version entry will be
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
        return ["*.*"]

    ############################################################################
    # standard publish plugin methods


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
        return {"accepted": accept}


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
        publisher = self.parent
        thumb = item.get_thumbnail_as_path()
        upload_thumb = True
        version = item.properties["sg_version_data"]
        finalize_tasks = item.properties.get("version_finalize")

        if version and finalize_tasks:

            if finalize_tasks["update"]:
                publisher.shotgun.update("Version", version["id"], finalize_tasks["update"])

            if finalize_tasks["upload"]:
                for field, path in finalize_tasks["upload"].iteritems():
                    self.logger.info("Uploading content...")

                    # on windows, ensure the path is utf-8 encoded to avoid issues with
                    # the shotgun api
                    if sgtk.util.is_windows():
                        upload_path = six.ensure_text(path)
                    else:
                        upload_path = path

                    publisher.shotgun.upload(
                        "Version", version["id"], upload_path, field
                    )
                    upload_thumb = False

        if upload_thumb:
            # only upload thumb if we are not uploading the content. with
            # uploaded content, the thumb is automatically extracted.
            self.logger.info("Uploading thumbnail...")
            publisher.shotgun.upload_thumbnail("Version", version["id"], thumb)


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
