"""Loaded by pytest before any test module, so the app never binds to the real database."""
import os
import tempfile

TEST_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'
