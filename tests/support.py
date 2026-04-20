import os
import shutil
import tempfile
import unittest


TEST_DATA_DIR = tempfile.mkdtemp(prefix='planning-tests-')
os.environ['PLANNING_DATA_DIR'] = TEST_DATA_DIR

from app import create_app  # noqa: E402
from models import ShareLink, SystemSetting, User, db  # noqa: E402
from services.paths import get_docs_root  # noqa: E402


class PlanningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self._set_setting('comments_enabled', 'true')
            self._set_setting('comments_require_approval', 'true')
            self._set_setting('blog_enabled', 'false')

    def _set_setting(self, key, value):
        setting = db.session.get(SystemSetting, key)
        if not setting:
            setting = SystemSetting(key=key, value=value)
            db.session.add(setting)
        else:
            setting.value = value
        db.session.commit()

    def _create_user(self, username, *, email_verified=True, role='regular', can_comment=True):
        user = User(
            username=username,
            email=f'{username}@example.com',
            role=role,
            email_verified=email_verified,
            can_comment=can_comment,
        )
        user.set_password('Password1')
        db.session.add(user)
        db.session.commit()
        return user

    def _create_share(self, owner, token, target_path):
        share = ShareLink(
            token=token,
            target_type='file',
            target_path=target_path,
            title=target_path,
            allow_edit=False,
            created_by_user_id=owner.id,
        )
        db.session.add(share)
        db.session.commit()
        return share

    def _create_doc(self, relative_path, content='# Test\n'):
        abs_path = os.path.join(get_docs_root(), relative_path.replace('/', os.sep))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as file_obj:
            file_obj.write(content)
        return abs_path

    def _login(self, user_or_id):
        user_id = user_or_id if isinstance(user_or_id, int) else user_or_id.id
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True
