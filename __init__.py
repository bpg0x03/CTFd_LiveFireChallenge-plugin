from flask import Blueprint
from flask import request
from flask import render_template
import datetime
from CTFd.models import Challenges, db
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge
from CTFd.plugins.migrations import upgrade
import atexit
import configparser
import ssl
from CTFd.utils.decorators import admins_only
from pyVmomi import vim
from pyVim.task import WaitForTask
from pyVim import connect
from pyVim.connect import Disconnect


inputs = {'vcenter_ip': '192.168.1.1',
          'vcenter_password': 'password',
          'vcenter_user': 'username',
          'snapshot_name': 'BASELINE',
          'ignore_ssl': True
          }

def makeDateTime():
    return str(datetime.datetime.now().isoformat())

class LiveFireChallengeModel(Challenges):
    __mapper_args__ = {"polymorphic_identity": "livefire"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    vmname = db.Column(db.String(64))
    lastrevert = db.Column(db.Text, default=makeDateTime)

    def __init__(self, *args, **kwargs):
        super(LiveFireChallengeModel, self).__init__(**kwargs)
        self.initial = kwargs["value"]


class LiveFireChallenge(BaseChallenge):
    id = "livefire"  # Unique identifier used to register challenges
    name = "livefire"  # Name of a challenge type
    templates = {  # Handlebars templates used for each aspect of challenge editing & viewing
        "create": "/plugins/livefire_challenges/assets/create.html",
        "update": "/plugins/livefire_challenges/assets/update.html",
        "view": "plugins/livefire_challenges/assets/view.html",
    }
    scripts = {  # Scripts that are loaded when a template is loaded
        "create": "/plugins/livefire_challenges/assets/create.js",
        "update": "/plugins/livefire_challenges/assets/update.js",
        "view": "/plugins/livefire_challenges/assets/view.js",
    }
    # Route at which files are accessible. This must be registered using register_plugin_assets_directory()
    route = "/plugins/livefire_challenges/assets/"
    # Blueprint used to access the static_folder directory.
    blueprint = Blueprint(
        "livefire_challenges",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )
    challenge_model = LiveFireChallengeModel
    @classmethod
    def read(cls, challenge):
        """
        This method is in used to access the data of a challenge in a format processable by the front end.

        :param challenge:
        :return: Challenge object, data dictionary to be returned to the user
        """
        challenge = LiveFireChallengeModel.query.filter_by(id=challenge.id).first()
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "description": challenge.description,
            "category": challenge.category,
            "vmname": challenge.vmname,
            "lastrevert": challenge.lastrevert,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
        }
        return data

    @classmethod
    def update(cls, challenge, request):
        """
        This method is used to update the information associated with a challenge. This should be kept strictly to the
        Challenges table and any child tables.

        :param challenge:
        :param request:
        :return:
        """
        data = request.form or request.get_json()

        for attr, value in data.items():
            setattr(challenge, attr, value)
        db.session.commit()
        return challenge

    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)


def load(app):
    app.db.create_all()
    upgrade()
    CHALLENGE_CLASSES["livefire"] = LiveFireChallenge
    register_plugin_assets_directory(
        app, base_path="/plugins/livefire_challenges/assets/"
    )

    @app.route('/admin/revert', methods=['POST','GET'])
    @admins_only
    def revert_chal():
        chalid = request.values.get('id')
        try:
            challenge = LiveFireChallengeModel.query.filter_by(id=chalid).first()
            revert(challenge.vmname)
            challenge.lastrevert = makeDateTime()
            db.session.commit()
            return render_template('page.html', content="<h1> Revert Success <h1>")
        except Exception as e:
            return render_template('page.html', content="<h1> Revert Failed <h1><br>" + str(e))
            
    def revert(vmname):
        context = None
        if inputs['ignore_ssl'] and hasattr(ssl, "_create_unverified_context"):
            context = ssl._create_unverified_context()
        si = connect.Connect(inputs['vcenter_ip'], 443,
                         inputs['vcenter_user'], inputs[
                             'vcenter_password'],
                         sslContext=context)
        atexit.register(Disconnect, si)
        content = si.RetrieveContent()
        vm_name = vmname
        vm = get_obj(content, [vim.VirtualMachine], vm_name)
        if not vm:
            raise Exception("Virtual Machine %s doesn't exists" % vm_name)
        snapshot_name = inputs['snapshot_name']
        snap_obj = get_snapshots_by_name_recursively(vm.snapshot.rootSnapshotList, snapshot_name)
        if len(snap_obj) == 1:
            snap_obj = snap_obj[0].snapshot
            WaitForTask(snap_obj.RevertToSnapshot_Task())
            WaitForTask(vm.PowerOn())
        else:
            raise Exception(("No snapshots found with name: %s on VM: %s" % (
                                                snapshot_name, vm.name)))
        return






def get_obj(content, vimtype, name):
    """
    Get the vsphere object associated with a given text name
    """
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj

def get_snapshots_by_name_recursively(snapshots, snapname):
    snap_obj = []
    for snapshot in snapshots:
        if snapshot.name == snapname:
            snap_obj.append(snapshot)
        else:
            snap_obj = snap_obj + get_snapshots_by_name_recursively(
                                    snapshot.childSnapshotList, snapname)
    return snap_obj
