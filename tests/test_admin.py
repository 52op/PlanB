from models import Comment, User, db

from tests.support import PlanningTestCase


class AdminRegressionTests(PlanningTestCase):
    def test_admin_delete_user_reassigns_comments_to_deleted_user(self):
        with self.app.app_context():
            admin = self._create_user('adminuser', role='admin')
            author = self._create_user('retiredauthor')
            comment = Comment(
                filename='docs/a.md',
                user_id=author.id,
                content='历史评论',
                status='approved',
            )
            db.session.add(comment)
            db.session.commit()
            author_id = author.id
            comment_id = comment.id
            admin_id = admin.id

        self._login(admin_id)
        response = self.client.post(f'/admin/users/{author_id}/delete', follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            deleted_user = User.query.filter_by(username='__deleted_user__').first()
            self.assertIsNotNone(deleted_user)
            self.assertIsNone(db.session.get(User, author_id))
            updated_comment = db.session.get(Comment, comment_id)
            self.assertEqual(updated_comment.user_id, deleted_user.id)
            self.assertEqual(deleted_user.nickname, '已注销用户')

    def test_admin_restore_comment_sets_approved(self):
        with self.app.app_context():
            admin = self._create_user('adminrestore', role='admin')
            author = self._create_user('pendingauthor')
            comment = Comment(
                filename='docs/a.md',
                user_id=author.id,
                content='待恢复评论',
                status='deleted',
            )
            db.session.add(comment)
            db.session.commit()
            admin_id = admin.id
            comment_id = comment.id

        self._login(admin_id)
        response = self.client.post(f'/admin/comments/{comment_id}/restore', follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            updated_comment = db.session.get(Comment, comment_id)
            self.assertEqual(updated_comment.status, 'approved')
            self.assertIsNone(updated_comment.approval_token)

    def test_admin_hard_delete_requires_deleted_status(self):
        with self.app.app_context():
            admin = self._create_user('adminharddelete', role='admin')
            author = self._create_user('activeauthor')
            comment = Comment(
                filename='docs/a.md',
                user_id=author.id,
                content='未删除评论',
                status='approved',
            )
            db.session.add(comment)
            db.session.commit()
            admin_id = admin.id
            comment_id = comment.id

        self._login(admin_id)
        response = self.client.post(f'/admin/comments/{comment_id}/hard-delete', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('请先将评论标记为已删除，再执行彻底删除', response.get_data(as_text=True))

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Comment, comment_id))

    def test_admin_routes_require_admin_role(self):
        with self.app.app_context():
            regular_user = self._create_user('regularviewer')
            user_id = regular_user.id
        self._login(user_id)

        response = self.client.get('/admin/base')
        self.assertEqual(response.status_code, 403)

    def test_admin_toggle_comment_permission_blocks_deleted_system_user(self):
        with self.app.app_context():
            admin = self._create_user('adminblocker', role='admin')
            admin_id = admin.id
            deleted_user = self._create_user('__deleted_user__', role='guest', can_comment=False)
            deleted_user.nickname = '已注销用户'
            db.session.commit()
            deleted_user_id = deleted_user.id

        self._login(admin_id)
        response = self.client.post(
            f'/admin/users/{deleted_user_id}/toggle-comment',
            data={},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('系统保留账号不支持此操作', response.get_data(as_text=True))
