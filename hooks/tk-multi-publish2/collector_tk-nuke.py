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
import nuke
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

# A look up of node types to parameters for finding outputs to publish
_NUKE_OUTPUTS = {
    "Write": "file",
    "WriteGeo": "file",
}


class NukeSessionCollector(HookBaseClass):
    """
    Collector that operates on the current nuke/nukestudio session. Should
    inherit from the basic collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = super(NukeSessionCollector, self).settings or {}

        # settings specific to this collector
        nuke_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                "correspond to a template defined in "
                "templates.yml. If configured, is made available"
                "to publish plugins via the collected item's "
                "properties. ",
            },
        }

        # update the base settings with these settings
        collector_settings.update(nuke_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current session open in Nuke/NukeStudio and parents a
        subtree of items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        publisher = self.parent
        engine = publisher.engine

        if (hasattr(engine, "studio_enabled") and engine.studio_enabled) or (
            hasattr(engine, "hiero_enabled") and engine.hiero_enabled
        ):

            # running nuke studio or hiero
            self.collect_current_nukestudio_session(settings, parent_item)

            # since we're in NS, any additional collected outputs will be
            # parented under the root item
            project_item = parent_item
        else:
            # running nuke. ensure additional collected outputs are parented
            # under the session
            project_item = self.collect_current_nuke_session(settings, parent_item)

        # run node collection if not in hiero
        if hasattr(engine, "hiero_enabled") and not engine.hiero_enabled:
            self.collect_sg_writenodes(project_item)
            self.collect_node_outputs(project_item)
            self.collect_selected_read_nodes(project_item)

    def collect_current_nuke_session(self, settings, parent_item):
        """
        Analyzes the current session open in Nuke and parents a subtree of items
        under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        publisher = self.parent
        first_frame = int(nuke.root()["first_frame"].value())
        last_frame = int(nuke.root()["last_frame"].value())

        # get the current path
        path = _session_path()

        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current Nuke Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "nuke.session", "Nuke Script", display_name
        )

        # set the frame range for the session
        session_item.properties["first_frame"] = first_frame
        session_item.properties["last_frame"] = last_frame

        # get the icon path to display for this item
        icon_path = os.path.join(self.disk_location, "icons", "nuke.png")
        session_item.set_icon_from_path(icon_path)

        # if a work template is defined, add it to the item properties so
        # that it can be used by attached publish plugins
        work_template_setting = settings.get("Work Template")
        if work_template_setting:
            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            session_item.properties["work_template"] = work_template
            session_item.properties["path"] = path
            self.logger.debug("Work template defined for Nuke collection.")

        self.logger.info("Collected current Nuke script")
        return session_item

    def collect_current_nukestudio_session(self, settings, parent_item):
        """
        Analyzes the current session open in NukeStudio and parents a subtree of
        items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        # import here since the hooks are imported into nuke and nukestudio.
        # hiero module is only available in later versions of nuke
        import hiero.core

        publisher = self.parent

        # go ahead and build the path to the icon for use by any projects
        icon_path = os.path.join(
            self.disk_location, "icons", "nukestudio.png"
        )

        if hiero.ui.activeSequence():
            active_project = hiero.ui.activeSequence().project()
        else:
            active_project = None

        # attempt to retrive a configured work template. we can attach
        # it to the collected project items
        work_template_setting = settings.get("Work Template")
        work_template = None
        if work_template_setting:
            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

        # FIXME: begin temporary workaround
        # we use different logic here only because we don't have proper support
        # for multi context workflows when templates are in play. So if we have
        # a work template configured, for now we'll only collect the current,
        # active document. Once we have proper multi context support, we can
        # remove this.
        if work_template:
            # same logic as the loop below but only processing the active doc
            if not active_project:
                return
            project_item = parent_item.create_item(
                "nukestudio.project", "NukeStudio Project", active_project.name()
            )
            self.logger.info(
                "Collected Nuke Studio project: %s" % (active_project.name(),)
            )
            project_item.set_icon_from_path(icon_path)
            project_item.properties["project"] = active_project
            project_item.properties["work_template"] = work_template
            self.logger.debug("Work template defined for NukeStudio collection.")
            return
        # FIXME: end temporary workaround

        for project in hiero.core.projects():

            # create the session item for the publish hierarchy
            project_item = parent_item.create_item(
                "nukestudio.project", "NukeStudio Project", project.name()
            )
            project_item.set_icon_from_path(icon_path)

            # add the project object to the properties so that the publish
            # plugins know which open project to associate with this item
            project_item.properties["project"] = project

            self.logger.info("Collected Nuke Studio project: %s" % (project.name(),))

            # enable the active project and expand it. other projects are
            # collapsed and disabled.
            if active_project and active_project.guid() == project.guid():
                project_item.expanded = True
                project_item.checked = True
            elif active_project:
                # there is an active project, but this isn't it. collapse and
                # disable this item
                project_item.expanded = False
                project_item.checked = False

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            if work_template:
                project_item.properties["work_template"] = work_template
                self.logger.debug("Work template defined for NukeStudio collection.")

    def collect_node_outputs(self, parent_item):
        """
        Scan known output node types in the session and see if they reference
        files that have been written to disk.

        :param parent_item: The parent item for any nodes collected
        """

        # iterate over all the known output types
        for node_type in _NUKE_OUTPUTS:

            # get all the instances of the node type
            all_nodes_of_type = [n for n in nuke.allNodes() if n.Class() == node_type]

            first_frame = int(nuke.root()["first_frame"].value())
            last_frame = int(nuke.root()["last_frame"].value())

            # iterate over each instance
            for node in all_nodes_of_type:

                param_name = _NUKE_OUTPUTS[node_type]

                # evaluate the output path parameter which may include frame
                # expressions/format
                file_path = node[param_name].evaluate()

                if not file_path or not os.path.exists(file_path):
                    # no file or file does not exist, nothing to do
                    continue

                self.logger.info("Processing %s node: %s" % (node_type, node.name()))

                # file exists, let the basic collector handle it
                item = super(NukeSessionCollector, self)._collect_file(
                    parent_item, file_path, frame_sequence=True
                )

                # check if the theres a slate frame
                slate_frame = node.input(0).metadata().get('nx/slate_frame')
                if slate_frame:
                    item.properties["slate_frame"] = int(slate_frame)

                item.properties["node"] = node
                item.properties["first_frame"] = first_frame
                item.properties["last_frame"] = last_frame
                item.properties["width"] = node.width()
                item.properties["height"] = node.height()
                item.properties["pixel_aspect"] = node.pixelAspect()

                if node.knob("use_limit"):
                    if node.knob("use_limit").getValue():
                        item.properties["first_frame"] = int(node.knob("first").getValue())
                        item.properties["last_frame"] = int(node.knob("last").getValue())

                # the item has been created. update the display name to include
                # the nuke node to make it clear to the user how it was
                # collected within the current session.
                item.name = "%s (%s)" % (item.name, node.name())

    def collect_selected_read_nodes(self, parent_item):
        """
        Scan selected read nodes in case the user wants to publish them.

        :param parent_item: The parent item for any nodes collected
        """

        # get all the selected Reads
        selected_reads = [n for n in nuke.selectedNodes() if n.Class() == "Read"]

        # first_frame = int(nuke.root()["first_frame"].value())
        # last_frame = int(nuke.root()["last_frame"].value())

        # iterate over each instance
        for node in selected_reads:

            # evaluate the file knob which may include frame
            # expressions/format
            file_path = node["file"].evaluate()

            if not file_path or not os.path.exists(file_path):
                # no file or file does not exist, nothing to do
                continue

            self.logger.info("Processing selected Read node: %s" % (node.name()))

            # file exists, let the basic collector handle it
            item = super(NukeSessionCollector, self)._collect_file(
                parent_item, file_path, frame_sequence=True
            )

            item.properties["node"] = node
            item.properties["skip_version_attach"] = True
            item.properties["start_unchecked"] = True
            item.properties["first_frame"] = first_frame
            item.properties["last_frame"] = last_frame
            item.properties["width"] = node.width()
            item.properties["height"] = node.height()
            item.properties["pixel_aspect"] = node.pixelAspect()

            # the item has been created. update the display name to include
            # the nuke node to make it clear to the user how it was
            # collected within the current session.
            item.name = "%s (%s)" % (item.name, node.name())

    def collect_sg_writenodes(self, parent_item):
        """
        Collect any rendered sg write nodes in the session.

        :param parent_item:  The parent item for any sg write nodes collected
        """

        publisher = self.parent
        engine = publisher.engine

        sg_writenode_app = engine.apps.get("tk-nuke-writenode")
        if not sg_writenode_app:
            self.logger.debug(
                "The tk-nuke-writenode app is not installed. "
                "Will not attempt to collect those nodes."
            )
            return

        first_frame = int(nuke.root()["first_frame"].value())
        last_frame = int(nuke.root()["last_frame"].value())

        for node in sg_writenode_app.get_write_nodes():

            # see if any frames have been rendered for this write node
            rendered_files = sg_writenode_app.get_node_render_files(node)
            if not rendered_files:
                continue

            # some files rendered, use first frame to get some publish item info
            file_path = rendered_files[0]

            if not file_path or not os.path.exists(file_path):
                # no file or file does not exist, nothing to do
                continue

            self.logger.info("Processing sgWrite node: %s" % (node.name()))

            if len(rendered_files) > 1:
                is_frame_sequence = True
            else:
                is_frame_sequence = False

            # file exists, let the basic collector handle it
            item = super(NukeSessionCollector, self)._collect_file(
                parent_item, file_path, frame_sequence=is_frame_sequence
            )

            # check if the theres a slate frame
            # slate_frame = node.input(0).metadata().get('nx/slate_frame')
            # if slate_frame:
            #     item.properties["slate_frame"] = int(slate_frame)

            item.properties["sequence_paths"] = rendered_files
            item.properties["node"] = node
            item.properties["first_frame"] = first_frame
            item.properties["last_frame"] = last_frame
            item.properties["width"] = node.width()
            item.properties["height"] = node.height()
            item.properties["pixel_aspect"] = node.pixelAspect()

            if node.knob("use_limit").getValue():
                item.properties["first_frame"] = int(node.knob("first").getValue())
                item.properties["last_frame"] = int(node.knob("last").getValue())

            # the item has been created. update the display name to include
            # the nuke node to make it clear to the user how it was
            # collected within the current session.
            item.name = "%s (%s)" % (item.name, node.name())

    def _get_node_colorspace(self, node):
        """
        Get the colorspace for the specified nuke node

        :param node:    The nuke node to find the colorspace for
        :returns:       The string representing the colorspace for the node
        """
        cs_knob = node.knob("colorspace")
        if not cs_knob:
            return

        cs = cs_knob.value()
        # handle default value where cs would be something like: 'default (linear)'
        if cs.startswith("default (") and cs.endswith(")"):
            cs = cs[9:-1]
        return cs


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    root_name = nuke.root().name()
    return None if root_name == "Root" else root_name
