# coding=utf-8
"""
Test
"""
import argparse
import os
import docker
from pathlib import Path

import errno
from secrets import token_hex

import sys

import time
from docker.errors import NotFound
from flask import Flask
from flask_login import LoginManager, login_required
from flask_url_discovery.app_registry import url_discovery
from flask_wtf import CSRFProtect
from ingestion.ingestion_apis.asset_db_api import AssetDbApi
from ingestion.ingestion_apis.gridfs_api import GridFsApi
from ingestion.ingestion_mongo_apis.mongo_asset import MongoAsset
from ingestion.ingestion_server.ingestion_globals import IngestionGlobals
from ingestion.ingestion_server.ingestion_rest_api_v2 import ingestion_bp_v2
from magen_datastore_apis.main_db import MainDb
from magen_mongo_apis.mongo_core_database import MongoCore
from magen_mongo_apis.mongo_utils import MongoUtils

import magen_user_api.user_api as user_api
from magen_user_api.user_api import users_bp, main_bp

from ingestion.ingestion_server.ingestion_file_upload_rest_api import ingestion_file_upload_bp
from ingestion.ingestion_server.asset_rest_api import ingestion_bp
from magen_utils_apis.domain_resolver import mongo_host_port, inside_docker, LOCAL_MONGO_LOCATOR

app = Flask(__name__)

app = url_discovery(app, custom_routes_url='/routes/')

app.template_folder = 'templates'  # providing path to template folder
# app.secret_key = "test_key"
# Using random keys guarantees that sessions are expired every time the
# server is reloaded
app.secret_key = token_hex(16)
# app.config['WTF_CSRF_SECRET_KEY'] = 'test'  # must be secured
# app.config['SECRET_KEY'] = 'test_key'  # must be secured
# app.config['SECURITY_PASSWORD_SALT'] = 'test_salt'  # must be secured
# configuring application with CSRF protection for form security
# CSRFProtect(app)

# configuring application with LoginManger for @login_required and handling login requests
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'users_bp.login'


@login_manager.user_loader
def load_user(user_id):
    """
    User Loader for Flask Login Manager
    :param user_id: user's e-mail
    """
    return user_api.load_user(user_id)


@ingestion_file_upload_bp.before_request
@login_required
def ingestion_before_request():
    """ Custom checks for login requirements """
    pass


recaptcha = user_api.config.init_recaptcha_with_creds(app)


def main(args):
    #: setup parser -----------------------------------------------------------
    parser = argparse.ArgumentParser(description='Magen IO Server',
                                     usage=("\npython3 server.py "
                                            "--csrf"
                                            "--clean-init"
                                            "--ingestion-data-dir"
                                            "\n\nnote:\n"
                                            "root privileges are required "))

    if inside_docker():
        ingestion_data_dir = os.path.join("/opt", "data")
    else:
        home_dir = str(Path.home())
        ingestion_data_dir = os.path.join(home_dir, "magen_data", "ingestion")

    parser.add_argument('--ingestion-data-dir', default=ingestion_data_dir,
                        help='Set directory for data files'
                             'Default is %s' % ingestion_data_dir)

    parser.add_argument('--clean-init', action='store_false',
                        help='Clean All data when initializing'
                             'Default is to clean)')

    parser.add_argument('--csrf', action='store_true',
                        help='Enable Cross Request Forgery protection'
                             'Default is to not use it)')

    parser.add_argument('--test', action='store_true',
                        help='Run server in test mode. Used for unit tests'
                             'Default is to run in production mode)')

    #: parse CMD arguments ----------------------------------------------------
    # args = parser.parse_args()
    args, _ = parser.parse_known_args(args)

    """ Main Magen.io Sever """
    home_dir = str(Path.home())

    ingestion_globals = IngestionGlobals()
    ingestion_globals.data_dir = args.ingestion_data_dir

    try:
        os.makedirs(ingestion_globals.data_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    # Starting OPA server
    docker_client = docker.from_env()
    # if there is no image we pull it
    try:
        opa_image = docker_client.images.get("openpolicyagent/opa")
    except NotFound as e:
        opa_image = docker_client.images.pull("openpolicyagent/opa", tag="latest")

    assert opa_image is not None

    # if container is not running we will start it
    try:
        opa_container = docker_client.containers.get("magen_opa")
        if opa_container.status == "exited" or opa_container.status == "created":
            opa_container.remove()
            raise NotFound("Container Exited or could not be started")
    except NotFound as e:
        print("OPA docker container not found or not running\n")
        opa_container = docker_client.containers.run("openpolicyagent/opa",
                                                     command="run --server --log-level=debug",
                                                     name="magen_opa",
                                                     ports={"8181/tcp": 8181}, detach=True)
        time.sleep(5)

    assert opa_container.status == "running" or (opa_container.status == "created"
                                                 and not opa_container.attrs["State"]["Error"])

    # Initialize Magen Logger
    # logger = initialize_logger(output_dir=ingestion_data_dir)

    mongo_ip, mongo_port = mongo_host_port()

    # We initialize at runtime everything about Mongo and its functions
    # Any client of the API can change it later

    db = MainDb.get_instance()
    db.core_database = MongoCore.get_instance()
    db.core_database.utils_strategy = MongoUtils.get_instance()
    db.core_database.asset_strategy = MongoAsset.get_instance()
    db.core_database.db_ip_port = '{ip}:{port}'.format(ip=mongo_ip, port=mongo_port)
    db.core_database.utils_strategy.check_db(db.core_database.db_ip_port)
    db.core_database.initialize()

    if args.clean_init:
        success, _ = AssetDbApi.delete_all()
        assert success is True
        user_api.drop_user_collection()
        GridFsApi.delete_all()

    if args.csrf:
        app.config['WTF_CSRF_ENABLED'] = True
        app.config['WTF_CSRF_SECRET_KEY'] = token_hex(16)
        CSRFProtect(app)
    else:
        app.config['WTF_CSRF_ENABLED'] = False

    app.register_blueprint(main_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(ingestion_file_upload_bp, url_prefix='/magen/ingestion/v2')
    app.register_blueprint(ingestion_bp_v2, url_prefix='/magen/ingestion/v2')
    app.register_blueprint(ingestion_bp, url_prefix='/magen/ingestion/v2')
    app.run('0.0.0.0', 5005, threaded=True)


if __name__ == "__main__":
    main(sys.argv[1:])
else:
    pass
