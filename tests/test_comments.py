from datetime import timedelta

from models import Comment, db
from services.comments import create_comment, update_comment

from tests.support import PlanningTestCase


class CommentRegressionTests(PlanningTestCase):
    def test_comment_approval_requires_confirmation_page(self):
        with self.app.app_context():
            author = self._create_user('author')
            comment = create_comment('docs/a.md', '待审核评论', user=author)
            token = comment.approval_token
            comment_id = comment.id

        response = self.client.get(f'/comment/approve/{token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('确认通过这条评论？', response.get_data(as_text=True))

        post_response = self.client.post(f'/comment/approve/{token}', follow_redirects=False)
        self.assertEqual(post_response.status_code, 302)

        with self.app.app_context():
            updated = db.session.get(Comment, comment_id)
            self.assertEqual(updated.status, 'approved')
            self.assertIsNone(updated.approval_token)
            self.assertIsNone(updated.approval_token_expires_at)

        invalid_response = self.client.get(f'/comment/approve/{token}')
        self.assertEqual(invalid_response.status_code, 200)
        self.assertIn('审核链接无效或已失效', invalid_response.get_data(as_text=True))

    def test_comment_approval_expired_token_shows_expired_message(self):
        from services.comments import _utcnow

        with self.app.app_context():
            author = self._create_user('expiredauthor')
            self._create_doc('docs/a.md')
            comment = create_comment('docs/a.md', '过期审核评论', user=author)
            comment.approval_token_expires_at = _utcnow() - timedelta(minutes=1)
            db.session.commit()
            token = comment.approval_token

        response = self.client.get(f'/comment/approve/{token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('审核链接已过期', response.get_data(as_text=True))

        post_response = self.client.post(f'/comment/approve/{token}', follow_redirects=False)
        self.assertEqual(post_response.status_code, 302)

    def test_create_comment_rejects_cross_document_parent(self):
        with self.app.app_context():
            author = self._create_user('commenter')
            parent = Comment(
                filename='docs/other.md',
                user_id=author.id,
                content='父评论',
                status='approved',
            )
            db.session.add(parent)
            db.session.commit()

            with self.assertRaisesRegex(ValueError, '回复目标与当前文章不匹配'):
                create_comment('docs/current.md', '跨文档回复', user=author, parent_id=parent.id)

    def test_deleted_comment_cannot_be_edited_back(self):
        with self.app.app_context():
            author = self._create_user('editor')
            comment = Comment(
                filename='docs/a.md',
                user_id=author.id,
                content='已删除评论',
                status='deleted',
            )
            db.session.add(comment)
            db.session.commit()

            with self.assertRaisesRegex(PermissionError, '已删除评论不支持编辑'):
                update_comment(comment, '试图恢复', user=author)
