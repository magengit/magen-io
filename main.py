# coding=utf-8
"""
Test
"""
import os
from pathlib import Path

import errno
from flask import Flask
# from flask_wtf import CSRFProtect
from flask_login import LoginManager, login_required
from flask_url_discovery.app_registry import url_discovery
from ingestion.ingestion_apis.asset_db_api import AssetDbApi
from ingestion.ingestion_mongo_apis.mongo_asset import MongoAsset
from ingestion.ingestion_server.asset_rest_api import ingestion_bp
from ingestion.ingestion_server.ingestion_globals import IngestionGlobals
from magen_datastore_apis.main_db import MainDb
# from magen_logger.logger_config import initialize_logger
from magen_mongo_apis.mongo_core_database import MongoCore
from magen_mongo_apis.mongo_utils import MongoUtils

import magen_user_api.user_api as user_api
from magen_user_api.user_api import users_bp, main_bp

from ingestion.ingestion_server.ingestion_file_upload_rest_api import ingestion_file_upload_bp
from magen_utils_apis.domain_resolver import mongo_host_port

app = Flask(__name__)

app = url_discovery(app, custom_routes_url='/routes/')

app.template_folder = 'templates'  # providing path to template folder
app.secret_key = 'test_key'
# app.config['WTF_CSRF_ENABLED'] = True
# app.config['WTF_CSRF_SECRET_KEY'] = 'test'  # must be secured
app.config['SECRET_KEY'] = 'test_key'  # must be secured
app.config['SECURITY_PASSWORD_SALT'] = 'test_salt'  # must be secured
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


def main():
    """ Main Magen.io Sever """
    home_dir = str(Path.home())
    ingestion_data_dir = os.path.join(home_dir, "magen_data", "ingestion")

    ingestion_globals = IngestionGlobals()
    ingestion_globals.data_dir = ingestion_data_dir
    try:
        os.makedirs(ingestion_globals.data_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

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

    success, _ = AssetDbApi.delete_all()
    assert success is True

    app.register_blueprint(main_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(ingestion_file_upload_bp, url_prefix='/magen/ingestion/v2')
    app.register_blueprint(ingestion_bp, url_prefix='/magen/ingestion/v1')
    app.run('0.0.0.0', 5005)


if __name__ == "__main__":
    main()
