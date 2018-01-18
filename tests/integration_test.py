# coding=utf-8
"""
This is Integration TestSuit for Ingestion + Magen User
"""
import http
import os
import unittest
from unittest import mock

from ingestion.ingestion_apis.asset_db_api import AssetDbApi
from ingestion.ingestion_mongo_apis.mongo_asset import MongoAsset
from ingestion.ingestion_server.asset_rest_api import ingestion_bp
from ingestion.ingestion_server.ingestion_file_upload_rest_api import ingestion_file_upload_bp
from ingestion.ingestion_server.ingestion_globals import IngestionGlobals
from magen_datastore_apis.main_db import MainDb
from magen_mongo_apis.mongo_core_database import MongoCore
from magen_mongo_apis.mongo_utils import MongoUtils
from magen_user_api import db
from magen_user_api.user_api import main_bp, users_bp
from magen_utils_apis.domain_resolver import mongo_host_port

import magen_user_api.config as config

from main import app


class TestIngestionUser(unittest.TestCase):
    """ Class to test integration of file upload and magen user """
    def setUp(self):
        self.ingestion_globals = IngestionGlobals()
        self.ingestion_globals.data_dir = os.getcwd() + '/'

        mongo_server_ip, mongo_port = mongo_host_port()

        magen_mongo = "{ip}:{port}".format(ip=mongo_server_ip, port=mongo_port)
        magen_db = MainDb.get_instance()
        magen_db.core_database = MongoCore.get_instance()
        magen_db.core_database.utils_strategy = MongoUtils.get_instance()
        magen_db.core_database.asset_strategy = MongoAsset.get_instance()
        magen_db.core_database.db_ip_port = magen_mongo
        magen_db.core_database.utils_strategy.check_db(magen_mongo)
        magen_db.core_database.initialize()

        app.config['TESTING'] = True
        app.register_blueprint(main_bp)
        app.register_blueprint(users_bp)
        app.register_blueprint(ingestion_file_upload_bp, url_prefix='/magen/ingestion/v2')
        app.register_blueprint(ingestion_bp, url_prefix='/magen/ingestion/v1')
        self.test_app = app.test_client()

        success, _ = AssetDbApi.delete_all()
        self.assertTrue(success)

        with db.connect(config.TEST_DB_NAME) as db_instance:
            db_instance.drop_collection(config.USER_COLLECTION_NAME)
        config.DEV_DB_NAME = config.TEST_DB_NAME

    def test_upload_file(self):
        """ Test to upload file with required login or registration """

        test_user_email = 'test@test.com'
        test_password = 'test_password'

        # Try to access upload_file view without registration or login
        resp = self.test_app.get('/magen/ingestion/v2/file_upload/', follow_redirects=True)
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)

        # redirected to login page
        self.assertIn('password', resp.data.decode('utf-8'))
        self.assertIn('email', resp.data.decode('utf-8'))

        # Register user
        data = {'email': test_user_email, 'password': test_password, 'confirm': test_password}
        with mock.patch('magen_user_api.user_api.send_confirmation'):
            self.test_app.post(
                '/register/',
                data=data
            )

        # redirected to login page after registration
        self.assertIn('password', resp.data.decode('utf-8'))
        self.assertIn('email', resp.data.decode('utf-8'))

        self.assertEqual(resp.status_code, http.HTTPStatus.OK)

        # make sure that new user is able to login
        post_data2 = {'email': test_user_email, 'password': test_password}
        resp = self.test_app.post(
            '/login/',
            data=post_data2, follow_redirects=True
        )

        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
        # here should go a check for home page

        # Try to access upload_file view without registration or login
        resp = self.test_app.get('/magen/ingestion/v2/file_upload/', follow_redirects=True)
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)

        # here goes check for file_upload page
