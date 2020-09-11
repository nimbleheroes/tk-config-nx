"""Tools for exporting selected references to fbx.

Author: Henry van der Beek (ninhenzo64@gmail.com)
Minor Udpate: Ethan McCaughey (ethanm@studiowildcard.com)
Release: v010
"""

import functools
import os
import re
import tempfile
import traceback

import pymel.core as pm
from maya import cmds, mel
from PySide2 import QtWidgets, QtGui, QtCore
from PySide2.QtCore import Qt

# DIALOG = None
# _MIN_W = 60
# _MIN_H = 20
#
_SCENE_REGEX = re.compile(('[a-zA-Z]' * 3) + ('[0-9]' * 4))
# _ROOTS_DEFAULT = 'root, JNT_Grp, Bind_Joint_GRP, skeletonGrp'


def _unlock_node(_node):
    """Unlock node and constraint channels.

    Args: _node  (str): Node name
    """
    _trs = ['t', 'tx', 'ty', 'tz', 'r', 'rx', 'ry', 'rz', 's', 'sx', 'sy', 'sz', 'v']
    cmds.lockNode(_node, l=False)
    for _attr in (cmds.listAttr(_node, keyable=True) or []) + _trs:
        if cmds.objExists('{}.{}'.format(_node, _attr)):
            cmds.setAttr('{}.{}'.format(_node, _attr), l=False)


# def _ok_cancel(msg, title="Confirm"):
#     """Raise a simple message box dialog.
#
#     Args:
#         msg (str): message to show in dialog
#         title (str): dialog window title
#     """
#     _box = _MessageBox(title=title, text=msg, buttons=('Ok', 'Cancel'))
#     return _box.get_result()


# def _notify(msg, title="Confirm"):
#     """Raise a simple message box dialog.
#
#     Args:
#         msg (str): message to show in dialog
#         title (str): dialog window title
#     """
#     _box = _MessageBox(title=title, text=msg, buttons=('Ok', ))
#     return _box.get_result()


# class _MessageBox(QtWidgets.QMessageBox):
#     """Simple message box interface."""
#
#     def __init__(self, text, title, buttons):
#         """Constructor.
#
#         Args:
#             text (str): message to display
#             title (str): title for the interface
#             buttons (str list): buttons to show
#         """
#         super(_MessageBox, self).__init__()
#         self.setWindowTitle(title)
#         self.setText(text)
#         self.buttons = self._add_buttons(buttons)
#
#     def _add_buttons(self, buttons):
#         """Add the buttons to the interface.
#
#         Args:
#             buttons (str list): buttons to show
#         """
#         _buttons = list(buttons)
#
#         # Create buttons
#         _btn_map = {}
#         for _button in _buttons:
#             _btn_map[_button] = self.addButton(
#                 _button, QtWidgets.QMessageBox.AcceptRole)
#
#         # Make sure we have cancel behaviour
#         if "Cancel" not in _btn_map:
#             _btn_map["Cancel"] = self.addButton(
#                 "Cancel", QtWidgets.QMessageBox.AcceptRole)
#             _btn_map["Cancel"].hide()
#             _buttons += ["Cancel"]
#         print _btn_map
#         self.setEscapeButton(_btn_map["Cancel"])
#         self.setDefaultButton(_btn_map["Cancel"])
#
#         return _buttons
#
#     def get_result(self):
#         """Read the result of the dialog."""
#         _exec_result = self.exec_()
#         _result = self.buttons[_exec_result]
#         if _result == "Cancel":
#             raise RuntimeError
#         return _result


# class _ProgressBar(object):
#     """Iterator which shows a progress bar dialog."""
#
#     def __init__(self, _items, title='Progress', parent=None):
#         """Constructor.
#
#         Args:
#             _items (list): _items to iterate
#             title (str): progress bar title
#             parent (QDialog): parent interface
#         """
#         self.items = _items[:]
#         self.n_items = len(self.items)
#
#         _args = [parent] if parent else []
#         self.progress = QtWidgets.QProgressBar(*_args)
#
#         self.progress.show()
#         self.progress.setValue(0)
#         self.progress.resize(300, 50)
#         self.progress.setWindowTitle(title)
#         if parent:
#             _pos = (parent.geometry().center() -
#                     parent.geometry().topLeft() -
#                     self.progress.geometry().center())
#             # print parent.geometry().center()
#             # print self.progress.geometry().center()
#             self.progress.move(_pos)
#
#         self.app = QtWidgets.QApplication.instance()
#
#     def next(self):
#         """Get the next iteration.
#
#         Returns:
#             (any): next _item
#         """
#         self.app.processEvents()
#         if not self.items:
#             self.progress.close()
#             raise StopIteration
#         _next = self.items.pop(0)
#         _fr = 1.0 - 1.0 * len(self.items) / self.n_items
#         self.progress.setValue(_fr * 100)
#         return _next
#
#     def __iter__(self):
#         return self


class _Path(object):
    """Represents a path on disk."""

    def __init__(self, path):
        """Constructor.

        Args:
            path (str): path in file structure
        """
        self.path = path
        self.dir = os.path.dirname(path)
        self.filename = os.path.basename(path)
        if '.' in self.filename:
            _tokens = self.filename.split('.')
            self.extn = _tokens[-1]
            self.basename = '.'.join(_tokens[:-1])
        else:
            self.extn = None
            self.basename = self.filename


def _restore_sel(func):
    """Decorator which restores current selection after exection.

    Args:
        func (fn): function to decorate
    """

    @functools.wraps(func)
    def __restore_sel_fn(*args, **kwargs):
        _sel = cmds.ls(selection=True)
        _result = func(*args, **kwargs)
        _sel = [_node for _node in _sel if cmds.objExists(_node)]
        if _sel:
            cmds.select(_sel)
        return _result

    return __restore_sel_fn


def _abs_path(path):
    """Get maya/fbx friendly path.

    Args:
        path (str): path to convert

    Returns:
        (str): path using backslash
    """
    return os.path.abspath(path).replace('\\', '/')


# def _export_fbxs(exportables, dir_, range_, parent=None, add_border_keys=True,
#                  bake_cams_in_world=True, roots=None):
#     """Export fbxs for the given exportables.
#
#     Args:
#         exportables (Exportable list): exportables to build fbxs for
#         dir_ (str): export directory
#         range_ (tuple): export range start/end
#         parent (QDialog): parent dialog for progress bar
#         add_border_keys (bool): add start/end frame keys
#         bake_cams_in_world (bool): bake cameras in world space
#         roots (str list): list of root nodes for rig exports
#     """
#     _cur_scene = cmds.file(query=True, location=True)
#     print 'EXPORT {:d}-{:d}'.format(*range_)
#     print ' - EXPORTABLES', exportables
#     print ' - DIR', dir_
#
#     # Find export paths
#     _to_delete = []
#     _exports = []
#     for _exp in exportables:
#         _fbx = _abs_path('{}/{}.fbx'.format(
#             dir_, _exp.export_name))
#         print ' - CHECKING', _fbx
#         _exports.append((_exp, _fbx))
#         if os.path.exists(_fbx):
#             _to_delete.append(_fbx)
#     if not _exports:
#         _notify('Nothing selected to export')
#         return
#
#     # Make sure export path exists
#     if not os.path.exists(dir_):
#         # _ok_cancel('Create dir?\n\n' + dir_)
#         os.makedirs(dir_)
#
#     # Warn on overwrite
#     if _to_delete:
#         # _ok_cancel('Replace {:d} existing fbxs?\n\n   {}'.format(
#         #     len(_to_delete), '\n   '.join(_to_delete)))
#         for _fbx in _to_delete:
#             os.remove(_fbx)
#
#     # Execute export
#     _title = 'Exporting {:d} fbxs'.format(len(_exports))
#     _kwargs = dict(range_=range_, add_border_keys=add_border_keys)
#     for _exp, _fbx in _ProgressBar(_exports, title=_title, parent=parent):
#         print ' - EXPORTING', _exp, _fbx
#         _kwargs['fbx'] = _fbx
#         if isinstance(_exp, _Camera) and bake_cams_in_world:
#             _exp.export(**_kwargs)
#         elif isinstance(_exp, _Rig) and roots:
#             _possible_nodes = [
#                 '{}:{}'.format(_exp.namespace, _root)
#                 for _root in roots]
#             _nodes = [_node for _node in _possible_nodes
#                       if cmds.objExists(_node)]
#             if not _nodes:
#                 _notify('No root nodes exist in {}:\n\n   '
#                         '{}\n\nNothing was exported.'.format(
#                             _exp.namespace,
#                             '\n   '.join(_possible_nodes)),
#                         title='Warning')
#                 continue
#             _exp.export(nodes=_nodes, **_kwargs)
#         else:
#             _exp.export(**_kwargs)


def _fbx_export_selection(fbx, range_, add_border_keys=True):
    """Execute fbx export of selected nodes.

    Args:
        fbx (str): path to export to
        range_ (tuple): export start/end range
        add_border_keys (bool): add start/end frame keys
    """
    print 'FBX EXPORT SELECTION'
    _nodes = cmds.ls(selection=True)
    print ' - NODES', _nodes
    _start, _end = range_
    print ' - EXPORT RANGE', range_

    if add_border_keys:
        mel.eval('DeleteAllStaticChannels')
        for _node in _nodes:
            _attrs = cmds.listAttr(_node, keyable=True) or []
            for _attr in _attrs:
                if '.' in _attr:
                    continue
                _chan = '{}.{}'.format(_node, _attr)
                if not cmds.listConnections(
                        _chan, type='animCurve', destination=False):
                    continue
                cmds.setKeyframe(_chan, time=_start, insert=True)
                cmds.setKeyframe(_chan, time=_end, insert=True)

    _dir = os.path.dirname(fbx)
    if not os.path.exists(_dir):
        os.makedirs(_dir)

    _mel = '\n'.join([
        'FBXResetExport;',
        'FBXExportFileVersion -v "FBX201400";',
        'FBXExportSmoothingGroups -v true;',
        'FBXExportShapes -v true;',
        'FBXExportSkins -v true;',
        'FBXExportTangents -v true;',
        'FBXExportSmoothMesh -v false;',
        'FBXExportBakeComplexAnimation -v true;',
        'FBXExportInputConnections -v false;',
        'FBXExport -f "{fbx}" -s;',
    ]).format(end=_start, start=_end, fbx=fbx)
    print _mel
    print cmds.ls(selection=True)
    cmds.loadPlugin('fbxmaya', quiet=True)
    mel.eval(_mel)


# def _find_cams(default=False):
#     """Find cameras in the scene.
#
#     Args:
#         default (bool): show default cameras
#
#     Returns:
#         (Camera list): cameras
#     """
#     _cams = []
#     for _shp in cmds.ls(type='camera'):
#         _tfm = cmds.listRelatives(_shp, parent=True)[0]
#         if not default and _tfm in ['persp', 'top', 'front', 'side', 'left', 'bottom', 'back']:
#             continue
#         _cam = _Camera(_tfm)
#         _cams.append(_cam)
#
#     return _cams


# def _find_rigs(roots, verbose=0):
#     """Read references in the scene.
#
#     Args:
#         roots (str list): list of valid skeleton root node names
#         verbose (int): print process data
#
#     Returns:
#         (FileRef list): list of refs
#     """
#     _refs = []
#     for _ref_node in cmds.ls(type='reference'):
#
#         try:
#             _ref = _Rig(_ref_node)
#         except ValueError:
#             continue
#         _lprint('TESTING', _ref, verbose=verbose)
#
#         if not _ref._file:
#             _lprint(' - NO FILE', _ref, verbose=verbose)
#             continue
#         if not cmds.referenceQuery(_ref_node, isLoaded=True):
#             _lprint(' - NOT LOADED', _ref, verbose=verbose)
#             continue
#         if cmds.referenceQuery(_ref_node, parentNamespace=True)[0]:
#             _lprint(' - HAS PARENT', _ref, verbose=verbose)
#             continue
#
#         # Test for root node
#         _ref_has_root = False
#         for _root in roots:
#             _node = '{}:{}'.format(_ref.namespace, _root)
#             if cmds.objExists(_node):
#                 _ref_has_root = True
#                 break
#         if not _ref_has_root:
#             _lprint(' - NO ROOT', roots, verbose=verbose)
#             continue
#
#         _lprint(' - IS RIG', verbose=verbose)
#         _refs.append(_ref)
#
#     return _refs


def _get_ns(node):
    """Get namespace of the given node.

    Args:
        node (str): node name

    Returns:
        (str): namespace
    """
    return str(node.split('|')[-1].split(':')[0])


def _lprint(*args, **kwargs):
    """Print a list of strings to the terminal.

    This aims to replicate the py2 print statement but still be compatible
    with py3. The print can be supressed using verbose=0 kwarg.
    """
    if not kwargs.get('verbose', True):
        return
    print ' '.join([str(_arg) for _arg in args])


def _set_namespace(namespace, clean=False):
    """Set current namespace, creating it if required.

    Args:
        namespace (str): namespace to apply
        clean (bool): delete all nodes in this namespace
    """
    _namespace = namespace
    assert _namespace.startswith(':')

    if clean:
        _nodes = cmds.ls(_namespace + ":*")
        if _nodes:
            cmds.delete(_nodes)

    if not cmds.namespace(exists=_namespace):
        cmds.namespace(addNamespace=_namespace)
    cmds.namespace(setNamespace=_namespace)


class _Exportable(object):
    """Base class for any exportable."""

    @property
    def scene(self):
        return (re.findall(_SCENE_REGEX, os.path.basename(cmds.file(q=True, sn=True))) or [''])[0].lower()

    @property
    def export_name(self):
        _current_scene = self.scene
        if _current_scene:
            return 'A_' + _current_scene + '_' + self.name.replace('_' + _current_scene, '').replace(_current_scene + '_', '').replace(_current_scene, '')
        else:
            return 'A_' + self.name

    def export(self, *_args, **_kwargs):
        self.export_fbx(*_args, **_kwargs)

    def export_fbx(self, fbx, range_, nodes=None, add_border_keys=True):
        """Export fbx to file.

        Args:
            fbx (str): path to export to
            range_ (tuple): start/end frames
            nodes (str list): override list of nodes to export
            add_border_keys (bool): add start/end frame keys
        """
        _nodes = nodes or self.find_nodes()
        cmds.select(_nodes)
        _fbx_export_selection(
            fbx=fbx, range_=range_, add_border_keys=add_border_keys)

    def __repr__(self):
        return '<{}:{}>'.format(type(self).__name__.strip('_'), self.name)


class _Camera(_Exportable):
    """Represents a camera in the current scene."""

    def __init__(self, tfm):
        """Constructor.

        Args:
            tfm (str): camera transform
        """
        self.tfm = tfm
        self.shp = cmds.listRelatives(self.tfm, shapes=True)[0]

    @property
    def name(self):
        """Get this cam's display name."""
        if ':' in self.tfm:
            return self.tfm.split(':')[0]
        return self.tfm

    def export(self, *_args, **_kwargs):
        self.export_fbx_in_world_space(*_args, **_kwargs)

    def export_fbx_in_world_space(
            self, fbx, range_, add_border_keys=True, cleanup=True):
        """Export fbx of this canera in world space.

        Args:
            fbx (str): fbx path
            range_ (tuple): start/end frames
            add_border_keys (bool): add start/end frame keys
            cleanup (bool): clean tmp nodes
        """
        print "EXPORT CAM IN WORLD SPACE"
        _set_namespace(':export_tmp', clean=True)

        # Create duplicate cam in world
        _dup = _Camera(cmds.duplicate(self.tfm)[0])
        if cmds.listRelatives(_dup.tfm, parent=True):
            cmds.parent(_dup.tfm, world=True)

        # Drive dup cam by orig
        for _attr in cmds.listAttr(self.shp, keyable=True):
            _type = cmds.attributeQuery(
                _attr, node=self.shp, attributeType=True)
            if _type in ['message']:
                continue
            cmds.setAttr('{}.{}'.format(_dup.shp, _attr), l=False)
            cmds.connectAttr('{}.{}'.format(self.shp, _attr),
                             '{}.{}'.format(_dup.shp, _attr))

        # Unlock
        _unlock_node(_dup.tfm)

        # Constrain
        _p_cons = cmds.parentConstraint(
            self.tfm, _dup.tfm, maintainOffset=False)[0]
        _s_cons = cmds.scaleConstraint(
            self.tfm, _dup.tfm, maintainOffset=False)[0]

        # Bake anim
        print ' - RANGE', range_
        cmds.bakeResults([_dup.tfm, _dup.shp], time=range_)
        cmds.delete(_p_cons, _s_cons)
        mel.eval('DeleteAllStaticChannels')
        _dup.export_fbx(
            fbx=fbx, range_=range_, add_border_keys=add_border_keys)
        if cleanup:
            _set_namespace(':export_tmp', clean=True)
        _set_namespace(':')

    def find_nodes(self):
        """Get nodes in this camera.

        Returns:
            (str list): list of nodes
        """
        return [self.tfm, self.shp]


class _Rig(_Exportable):
    """Represents a file referenced into maya."""

    def __init__(self, ref_node):
        """Constructor.

        Args:
            ref_node (str): reference node
        """
        self.ref_node = ref_node

    @property
    def _file(self):
        """Get this ref's file path (with copy number)."""
        try:
            return str(cmds.referenceQuery(self.ref_node, filename=True))
        except RuntimeError:
            return None

    @property
    def name(self):
        """Get this ref's display name."""
        _name = self.namespace
        _scene = self.scene
        _version = None
        for _regex in ['(v[0-9]+)', '(ver[0-9]+)', '(version[0-9]+)']:
            _check = (re.findall(_regex, _name, re.IGNORECASE) or [''])[0]
            if _check and not _version and _check != _scene:
                _version = _check

        if _version:
            _name = _name.replace('_' + _version, '').replace(_version + '_', '').replace(_version, '')

        return _name

    @property
    def namespace(self):
        """Get this ref's namespace."""
        return str(cmds.file(self._file, query=True, namespace=True))

    def find_nodes(self):
        """Find nodes within this reference.

        Returns:
            (str list): list of nodes
        """
        return cmds.ls(self.namespace + ":*", referencedNodes=True)

    def export(self, *_args, **_kwargs):
        # self.export_fbx(*_args, **_kwargs)
        # return

        _roots = _kwargs.get('nodes') or self.find_nodes()
        if not _roots:
            _lprint(' - NO ROOT', _roots, self.name, verbose=verbose)

        # implementing this section in pymel for simplicity if not speed.

        # Find true root joint (largest number of attached joitns)
        def _pm_name_sort(x):
            return len(x.longName())
        _root = None
        _roots = pm.ls(_roots)
        _max_children = -1

        for _item in sorted(_roots, key=_pm_name_sort):
            _num_children = len(pm.listRelatives(_item, ad=True, type='joint'))
            if _num_children > _max_children:
                _root = _item
                _max_children = _num_children

        try:
            # duplicate skeleton and lock root at zero
            _stay_grp = pm.createNode('transform', ss=True, name='stayGrp')
            _matches = {}
            # duplicate, reparent, and constrain all children of rrot
            for _item in [_root] + sorted(pm.listRelatives(_root, ad=True), key=_pm_name_sort):
                if not cmds.nodeType(_item.longName()).lower() in ['transform', 'joint']:
                    continue

                _matches[_item] = pm.duplicate(_item, rr=True, po=True)[0]
                pm.select(cl=True)
                _parent = (pm.listRelatives(_item, p=True, f=True) or [None])[0]

                if not _parent and _item != _root:
                    _parent = _root

                _unlock_node(_matches[_item].longName())
                _matches[_item].setAttr('v', 1)
                source = _item
                matrix = pm.xform(_matches[_item], q=True, ws=True, matrix=True)

                if _item == _root:
                    pm.parent(_matches[_item], w=True, r=True)
                    source = _stay_grp
                else:
                    pm.parent(_matches[_item], _matches[_parent], r=True)

                pm.select(cl=True)
                pm.xform(_matches[_item], a=True, ws=True, matrix=matrix)
                _matches[_item].rename(str(_item).split('|')[-1].split(':')[-1])

                pm.pointConstraint(source, _matches[_item], mo=False)
                pm.orientConstraint(source, _matches[_item], mo=False).setAttr('interpType', 2)
                pm.scaleConstraint(source, _matches[_item], mo=False)

            for _item in sorted(_matches.values(), key=_pm_name_sort):
                if cmds.objExists(_item.longName() + '.segmentScaleCompensate'):
                    _item.setAttr('segmentScaleCompensate', l=False)
                    _item.setAttr('segmentScaleCompensate', 0)

            # send duplicate root
            _kwargs['nodes'] = [_matches[_root].longName()]
            self.export_fbx(*_args, **_kwargs)
            pm.delete(_matches.values() + [_stay_grp])

        except:
            pm.delete(*(_matches.values() + [_stay_grp]))
            raise


# class _FbxExporterUi(object):
#     """Interface for exporter."""
#
#     def __init__(self, parent):
#         """Constructor.
#
#         Args:
#             parent (QDialog): parent dialog
#         """
#         self.main_layout = QtWidgets.QVBoxLayout(parent)
#         parent.setLayout(self.main_layout)
#
#         # Build elements
#         self._setup_path()
#         self._setup_roots()
#         self._setup_range()
#         self._setup_exportables()
#         self._setup_opts()
#         self._setup_export()
#
#         self._setup_settings()
#
#     def _setup_settings(self):
#         """Setup and load settings."""
#         _settings_file = _abs_path('{}/.qt_settings/{}.ini'.format(
#             tempfile.gettempdir(), type(self).__name__).strip('_'))
#         self._settings = QtCore.QSettings(
#             _settings_file, QtCore.QSettings.IniFormat)
#         self._save_attrs = [
#             'add_border_keys', 'bake_cams_in_world', 'path',
#             'show_default_cams', 'roots']
#         self.load_settings()
#
#     def _setup_path(self):
#         """Setup path line elements."""
#         _line = QtWidgets.QHBoxLayout()
#         self.main_layout.addLayout(_line)
#
#         _label = QtWidgets.QLabel('Folder')
#         _label.setMinimumSize(_MIN_W, _MIN_H)
#         _line.addWidget(_label)
#
#         self.path = QtWidgets.QLineEdit()
#         _line.addWidget(self.path)
#
#         self.browse = QtWidgets.QPushButton('Browse')
#         _line.addWidget(self.browse)
#
#     def _setup_roots(self):
#         """Setup root nodes line elements."""
#         _line = QtWidgets.QHBoxLayout()
#         self.main_layout.addLayout(_line)
#
#         _label = QtWidgets.QLabel('Roots')
#         _label.setMinimumSize(_MIN_W, _MIN_H)
#         _line.addWidget(_label)
#
#         self.roots = QtWidgets.QLineEdit()
#         self.roots.setText(_ROOTS_DEFAULT)
#         _line.addWidget(self.roots)
#
#     def _setup_range(self):
#         """Setup range line elements."""
#         _line = QtWidgets.QHBoxLayout()
#         self.main_layout.addLayout(_line)
#
#         _label = QtWidgets.QLabel('Range')
#         _label.setMinimumSize(_MIN_W, _MIN_H)
#
#         # Add start
#         _start = int(cmds.playbackOptions(query=True, minTime=True))
#         _line.addWidget(_label)
#         self.start = QtWidgets.QSpinBox()
#         self.start.setMaximum(9999999)
#         self.start.setValue(_start)
#         self.start.setMinimumSize(_MIN_W, _MIN_H)
#         _line.addWidget(self.start)
#
#         # Add end
#         _end = int(cmds.playbackOptions(query=True, maxTime=True))
#         self.end = QtWidgets.QSpinBox()
#         self.end.setMaximum(9999999)
#         self.end.setValue(_end)
#         self.end.setMinimumSize(_MIN_W, _MIN_H)
#         _line.addWidget(self.end)
#
#         _line.addStretch()
#
#     def _setup_exportables(self):
#         """Setup exportables list."""
#         self.exportables = QtWidgets.QListWidget()
#         self.exportables.setSelectionMode(
#             QtWidgets.QListWidget.ExtendedSelection)
#         self.main_layout.addWidget(self.exportables)
#
#     def _setup_opts(self):
#         """Setup camera options."""
#         self.show_default_cams = QtWidgets.QCheckBox('Show default cams')
#         self.show_default_cams.setChecked(False)
#         self.main_layout.addWidget(self.show_default_cams)
#
#         self.bake_cams_in_world = QtWidgets.QCheckBox('Bake cams in world')
#         self.bake_cams_in_world.setChecked(True)
#         self.main_layout.addWidget(self.bake_cams_in_world)
#
#         self.add_border_keys = QtWidgets.QCheckBox('Add start/end keys')
#         self.add_border_keys.setChecked(True)
#         self.add_border_keys.setToolTip('\n'.join([
#             "Maya's FBX exporter ignores keys outside the export range. ",
#             "This means that if your anim isn't keyed on the start/end ",
#             "frames then you could lose animation."
#         ]))
#         self.main_layout.addWidget(self.add_border_keys)
#
#     def _setup_export(self):
#         """Setup export button."""
#         self.export = QtWidgets.QPushButton('Export')
#         self.main_layout.addWidget(self.export)
#
#     def save_settings(self):
#         """Save interface settings."""
#         print 'SAVING SETTINGS'
#         for _attr in self._save_attrs:
#             _elem = getattr(self, _attr)
#             if isinstance(_elem, QtWidgets.QCheckBox):
#                 _val = _elem.isChecked()
#             elif isinstance(_elem, QtWidgets.QLineEdit):
#                 _val = _elem.text()
#             else:
#                 raise ValueError(_val)
#             self._settings.setValue(_attr, _val)
#
#     def load_settings(self):
#         """Load interface settings."""
#         print 'LOADING SETTINGS'
#         for _attr in self._save_attrs:
#             _elem = getattr(self, _attr)
#             _val = self._settings.value(_attr)
#             if _val is None:
#                 continue
#             print ' -', _attr, self._settings.value(_attr)
#             if isinstance(_elem, QtWidgets.QCheckBox):
#                 _val = {'true': True, 'false': False}.get(_val, _val)
#                 if isinstance(_val, bool):
#                     _elem.setChecked(_val)
#             elif isinstance(_elem, QtWidgets.QLineEdit):
#                 _elem.setText(_val)
#             else:
#                 raise ValueError(_val)


# class _FbxExporter(QtWidgets.QDialog):
#     """Tool for batch exporting cams/refs to fbx."""
#
#     def __init__(self):
#         """Constructor."""
#         super(_FbxExporter, self).__init__()
#         self.default_path = _abs_path(
#             '{}/Documents'.format(os.path.expanduser("~")))
#         self.setup_ui()
#         self._redraw__exportables()
#
#     def setup_ui(self):
#         """Build ui elements."""
#         self.ui = _FbxExporterUi(self)
#         if not self.ui.path.text() or not os.path.exists(self.ui.path.text()):
#             self.ui.path.setText(self.default_path)
#
#         # Connect callbacks
#         self.ui.show_default_cams.stateChanged.connect(
#             self._redraw__exportables)
#         self.ui.browse.clicked.connect(
#             self._callback__browse)
#         self.ui.export.clicked.connect(
#             self._callback__export)
#         self.ui.roots.textChanged.connect(
#             self._redraw__exportables)
#
#         self.resize(468, 326)
#         self.setWindowTitle("Camera/anim fbx exporter")
#         self.show()
#
#     def _redraw__exportables(self):
#
#         self.ui.exportables.clear()
#
#         _show_default_cams = self.ui.show_default_cams.isChecked()
#         for _cam in _find_cams(default=_show_default_cams):
#             _item = QtWidgets.QListWidgetItem(_cam.name)
#             _item.setForeground(QtGui.QColor('Yellow'))
#             _item.setData(Qt.UserRole, _cam)
#             self.ui.exportables.addItem(_item)
#
#         _roots = re.split('[ ,]', self.ui.roots.text())
#         for _ref in _find_rigs(roots=_roots):
#             _item = QtWidgets.QListWidgetItem(_ref.name)
#             _item.setForeground(QtGui.QColor('Aquamarine'))
#             _item.setData(Qt.UserRole, _ref)
#             self.ui.exportables.addItem(_item)
#
#     def _callback__browse(self):
#
#         _dialog = QtWidgets.QFileDialog()
#         _dialog.setOption(_dialog.ShowDirsOnly)
#         _dialog.setDirectory(self.default_path)
#         _dir = _dialog.getExistingDirectory()
#         if _dir:
#             self.ui.path.setText(_dir)
#             self.ui.save_settings()
#
#     def _callback__export(self):
#
#         self.ui.save_settings()
#
#         _dir = _abs_path(self.ui.path.text())
#         _start = self.ui.start.value()
#         _end = self.ui.end.value()
#         _bake_cams_in_world = self.ui.bake_cams_in_world.isChecked()
#         _add_border_keys = self.ui.add_border_keys.isChecked()
#         _exportables = [_item.data(Qt.UserRole)
#                         for _item in self.ui.exportables.selectedItems()]
#         _roots = re.split('[ ,]', self.ui.roots.text())
#
#         _export_fbxs(exportables=_exportables, range_=(_start, _end),
#                      dir_=_dir, bake_cams_in_world=_bake_cams_in_world,
#                      add_border_keys=_add_border_keys, parent=self,
#                      roots=_roots)
#
#     def closeEvent(self, event):
#         """Triggered by close interface.
#
#         Args:
#             event (QEvent): close event
#         """
#         print 'CLOSING INTERFACE'
#         self.ui.save_settings()


# def launch_fbx_exporter(path=None, roots=None):
#     """Launch export dialog.
#
#     Args:
#         path (str): default dialog path
#         roots (str): override roots list
#     """
#     global DIALOG
#
#     DIALOG = _FbxExporter()
#     if path:
#         DIALOG.ui.path.setText(path)
#     if roots:
#         DIALOG.ui.roots.setText(roots)
#
#     return DIALOG


# if __name__ == '__main__':
#     launch_fbx_exporter()
