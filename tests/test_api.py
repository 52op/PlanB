from tests.support import PlanningTestCase


class ApiRegressionTests(PlanningTestCase):
    def test_user_suggest_requires_login(self):
        response = self.client.get('/api/users/suggest?q=ad', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

    def test_user_suggest_returns_empty_when_commenting_disabled_for_user(self):
        with self.app.app_context():
            user = self._create_user('mentionuser', can_comment=False)
            user_id = user.id
            self._create_user('adminhint')
        self._login(user_id)

        response = self.client.get('/api/users/suggest?q=ad')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'items': []})

    def test_user_suggest_returns_matches_for_commenting_user(self):
        with self.app.app_context():
            user = self._create_user('mentionok')
            user_id = user.id
            self._create_user('adam')
            self._create_user('adair')
            self._create_user('bruce')
        self._login(user_id)

        response = self.client.get('/api/users/suggest?q=ad')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item['username'] for item in payload['items']], ['adair', 'adam'])
