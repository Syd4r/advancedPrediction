'''Configures tests'''

import os
import pytest
from website import create_app

@pytest.fixture(scope='module')
def test_client():
    '''Create test client'''
    # Set the Testing configuration prior to creating the Flask application
    os.environ['CONFIG_TYPE'] = 'config.TestingConfig'
    flask_app = create_app()

    # Create a test client using the Flask application configured for testing
    with flask_app.test_client() as test_return:
        yield test_return # this is where the testing happens!
