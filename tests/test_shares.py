from datetime import timedelta

from models import ShareLink, db

from tests.support import PlanningTestCase


class ShareRegressionTests(PlanningTestCase):
    def test_share_scope_all_returns_all_owned_shares(self):
        with self.app.app_context():
            owner = self._create_user('shareowner')
            owner_id = owner.id
            self._create_doc('docs/a.md')
            self._create_doc('docs/b.md')
            self._create_share(owner, 'token-a', 'docs/a.md')
            self._create_share(owner, 'token-b', 'docs/b.md')
        self._login(owner_id)

        response = self.client.get('/api/shares?scope=all')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(len(payload['items']), 2)
        self.assertEqual({item['token'] for item in payload['items']}, {'token-a', 'token-b'})

    def test_share_crud_flow(self):
        with self.app.app_context():
            owner = self._create_user('sharecrud', role='admin')
            owner_id = owner.id
            self._create_doc('docs/share-flow.md')

        self._login(owner_id)
        create_response = self.client.post(
            '/api/shares',
            json={
                'target_type': 'file',
                'target_path': 'docs/share-flow.md',
                'target_name': '分享测试',
                'password': '',
                'allow_edit': False,
                'expires_at': '7d',
            },
        )
        self.assertEqual(create_response.status_code, 200)
        create_payload = create_response.get_json()
        self.assertTrue(create_payload['success'])
        token = create_payload['share']['token']

        update_response = self.client.patch(
            f'/api/shares/{token}',
            json={'allow_edit': True, 'password_mode': 'set', 'password': 'secret123'},
        )
        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.get_json()
        self.assertTrue(update_payload['share']['allow_edit'])
        self.assertTrue(update_payload['share']['requires_password'])

        list_response = self.client.get('/api/shares?scope=all')
        self.assertEqual(list_response.status_code, 200)
        tokens = {item['token'] for item in list_response.get_json()['items']}
        self.assertIn(token, tokens)

        delete_response = self.client.delete(f'/api/shares/{token}')
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.get_json()['success'])

        with self.app.app_context():
            self.assertIsNone(ShareLink.query.filter_by(token=token).first())

    def test_create_share_rejects_invalid_expiry_format(self):
        with self.app.app_context():
            owner = self._create_user('shareinvalid', role='admin')
            owner_id = owner.id
            self._create_doc('docs/invalid-expiry.md')

        self._login(owner_id)
        response = self.client.post(
            '/api/shares',
            json={
                'target_type': 'file',
                'target_path': 'docs/invalid-expiry.md',
                'expires_at': 'not-a-date',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], '分享有效期格式无效，请使用 ISO 日期时间格式')

    def test_create_share_rejects_past_expiry(self):
        with self.app.app_context():
            owner = self._create_user('sharepast', role='admin')
            owner_id = owner.id
            self._create_doc('docs/past-expiry.md')

        self._login(owner_id)
        response = self.client.post(
            '/api/shares',
            json={
                'target_type': 'file',
                'target_path': 'docs/past-expiry.md',
                'expires_at': '2000-01-01T00:00:00',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], '分享有效期必须晚于当前时间')

    def test_share_raw_rejects_expired_share(self):
        from blueprints.api import _utcnow as api_utcnow

        with self.app.app_context():
            owner = self._create_user('shareexpired', role='admin')
            self._create_doc('docs/share-expired.md', '# expired')
            share = self._create_share(owner, 'expired-token', 'docs/share-expired.md')
            share.allow_edit = True
            share.expires_at = api_utcnow() - timedelta(seconds=1)
            db.session.commit()

        response = self.client.get('/api/shares/expired-token/raw')
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.get_json()['error'], '分享已过期')

    def test_update_share_requires_password_when_password_mode_set(self):
        with self.app.app_context():
            owner = self._create_user('sharepwd', role='admin')
            owner_id = owner.id
            self._create_doc('docs/share-password.md')
            share = self._create_share(owner, 'pwd-token', 'docs/share-password.md')
            token = share.token

        self._login(owner_id)
        response = self.client.patch(
            f'/api/shares/{token}',
            json={'password_mode': 'set', 'password': ''},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], '请先填写新的分享密码')
