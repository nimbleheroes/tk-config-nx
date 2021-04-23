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

HookBaseClass = sgtk.get_hook_baseclass()


class AttachToVersionPlugin(HookBaseClass):
    """
    Plugin for creating versions in Shotgun from a Nuke Session.

    """
    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(self.disk_location, "icons", "version_up.png")

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Attach to Version"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        return """
        Attaches the item path to the Version entry.<br><br>Images or Image
        Sequences will be added to the \"Path to Frames\" field.<br>Video files
        will be added to the \"Path to Movie\" field and uploaded to the
        \"Uploaded Movie\" field.
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
        return {}


    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["file.image", "file.image.sequence", "file.video"]

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

        ## Look for an item up the tree that has a version_name, meaning a version will be created.
        version_name = None
        version_item = item

        while not version_name and version_item:
            version_name = version_item.properties.get("version_name")
            if not version_name:
                version_item = version_item.parent

        if version_name:
            item.local_properties.version_item = version_item
            return True
        else:
            return False

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """


        version_item = item.local_properties.version_item

        #check to see if we have any fun stuff to add
        first_frame = item.properties.get("first_frame")
        last_frame = item.properties.get("last_frame")
        width = item.properties.get("width")
        height = item.properties.get("height")
        pixel_aspect = item.properties.get("pixel_aspect")
        slate_frame = item.properties.get("slate_frame")

        # in order for this to grab the published paths, this will need to run
        # AFTER the publish_file.py process so make sure that this plugin is listed
        # after any "Publish to Shotgun" plugins in the tk-multi-publish2.yml
        if item.properties.get("sg_publish_data"):
            path = self.get_publish_path(item.properties.sg_publish_data)
        else:
            path = item.properties.path

        if version_item:

            if item.type_spec in ["file.image", "file.image.sequence"]:
                version_item.properties.version_finalize["update"].update({"sg_path_to_frames": path})
                if width and height and pixel_aspect:
                    aspect_ratio = float((width*pixel_aspect)/height)
                    version_item.properties.version_finalize["update"].update({"sg_frames_aspect_ratio": aspect_ratio})
                if slate_frame:
                    version_item.properties.version_finalize["update"].update({"sg_frames_have_slate": True})

            if item.type_spec in ["file.video"]:
                version_item.properties.version_finalize["update"].update({"sg_path_to_movie": path})
                version_item.properties.version_finalize["upload"].update({"sg_uploaded_movie": path})
                if width and height and pixel_aspect:
                    aspect_ratio = float((width*pixel_aspect)/height)
                    version_item.properties.version_finalize["update"].update({"sg_movie_aspect_ratio": aspect_ratio})
                if slate_frame:
                    version_item.properties.version_finalize["update"].update({"sg_movie_has_slate": True})


            self.logger.debug(
                "Version finalize tasks...",
                extra={
                    "action_show_more_info": {
                        "label": "Version finalize tasks",
                        "tooltip": "Show the complete version finalize list",
                        "text": "<pre>%s</pre>"
                        % (pprint.pformat(version_item.properties.version_finalize),),
                    }
                },
            )
        else:
            self.logger.debug("No version found to attach item paths.")

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
        # publisher = self.parent
        # version = None
        # curr_item = item

        # while not version and curr_item:
        #     version = curr_item.properties.get("sg_version_data")
        #     if not version:
        #         curr_item = curr_item.parent

        # if not version:
        #     self.logger.info("No version found to attach path to.")
        # else:
        #     if item.type_spec in ["file.image", "file.image.sequence"]:
        #         version = publisher.shotgun.update("Version", version["id"], {"sg_path_to_frames": item.properties["path"]})
        #         self.logger.info("path_to_frames added to Version")
        #     elif item.type_spec in ["file.video"]:
        #         version = publisher.shotgun.update("Version", version["id"], {"sg_path_to_movie": item.properties["path"]})
        #         self.logger.info("path_to_movie added to Version")

        pass