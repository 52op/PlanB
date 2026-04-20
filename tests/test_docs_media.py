import os
from io import BytesIO

from models import Image, PermissionRule, SystemSetting, db
from services.paths import get_docs_root

from tests.support import PlanningTestCase


class DocsMediaRegressionTests(PlanningTestCase):
    def _create_local_image(self, unique_filename='sample.png', *, referenced=False):
        uploads_dir = self.app.config['UPLOADS_DIR']
        relative_path = f'tests/{unique_filename}'
        absolute_path = os.path.join(uploads_dir, relative_path.replace('/', os.sep))
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, 'wb') as file_obj:
            file_obj.write(b'fake-image-bytes')

        image = Image(
            filename='sample.png',
            unique_filename=unique_filename,
            storage_type='local',
            path=relative_path,
            url=f'/media/{relative_path}',
            size=16,
            is_referenced=referenced,
        )
        db.session.add(image)
        db.session.commit()
        return image, absolute_path

    def test_document_create_rename_delete_flow(self):
        with self.app.app_context():
            admin = self._create_user('docadmin', role='admin')
            admin_id = admin.id

        self._login(admin_id)

        create_response = self.client.post(
            '/api/documents/create',
            json={'target_dir': 'guides', 'filename': 'intro'},
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.get_json()['path'], 'guides/intro.md')
        with self.app.app_context():
            created_path = os.path.join(get_docs_root(), 'guides', 'intro.md')
        self.assertTrue(os.path.exists(created_path))

        rename_response = self.client.post(
            '/api/documents/rename',
            json={'source_path': 'guides/intro.md', 'new_name': 'quick-start'},
        )
        self.assertEqual(rename_response.status_code, 200)
        self.assertEqual(rename_response.get_json()['path'], 'guides/quick-start.md')
        with self.app.app_context():
            renamed_abs_path = os.path.join(get_docs_root(), 'guides', 'quick-start.md')
        self.assertTrue(os.path.exists(renamed_abs_path))

        delete_response = self.client.delete(
            '/api/documents/delete',
            json={'filename': 'guides/quick-start.md'},
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.get_json()['success'])
        self.assertFalse(os.path.exists(renamed_abs_path))

    def test_directory_delete_rejects_non_empty_directory(self):
        with self.app.app_context():
            admin = self._create_user('diradmin', role='admin')
            admin_id = admin.id
            self._create_doc('manuals/readme.md')

        self._login(admin_id)
        response = self.client.delete('/api/directories/delete', json={'dirname': 'manuals'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], '目录不为空，请先清理其中的文档')

    def test_delete_image_rejects_referenced_image(self):
        with self.app.app_context():
            admin = self._create_user('imageadmin', role='admin')
            admin_id = admin.id
            image, absolute_path = self._create_local_image('referenced.png', referenced=True)
            image_id = image.id

        self._login(admin_id)
        response = self.client.delete(f'/api/images/{image_id}')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'Image is currently in use and cannot be deleted.')
        self.assertTrue(os.path.exists(absolute_path))

    def test_delete_image_removes_unreferenced_local_file(self):
        with self.app.app_context():
            admin = self._create_user('imagecleaner', role='admin')
            admin_id = admin.id
            image, absolute_path = self._create_local_image('cleanup.png', referenced=False)
            image_id = image.id

        self._login(admin_id)
        response = self.client.delete(f'/api/images/{image_id}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        self.assertFalse(os.path.exists(absolute_path))

        with self.app.app_context():
            self.assertIsNone(db.session.get(Image, image_id))

    def test_upload_markdown_strips_front_matter_for_non_manage_user(self):
        with self.app.app_context():
            user = self._create_user('markdownuploader')
            user_id = user.id
            permission = PermissionRule(
                user_id=user.id,
                dir_path='uploads',
                can_read=True,
                can_upload=True,
                can_edit=False,
                can_delete=False,
                can_manage=False,
            )
            db.session.add(permission)
            db.session.commit()

        self._login(user_id)
        response = self.client.post(
            '/api/upload',
            data={
                'target_dir': 'uploads',
                'file': (
                    BytesIO(
                        b"---\ntitle: Hidden Title\npublic: true\n---\n\n# Visible Body\n"
                    ),
                    'sample.md',
                ),
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['path'], 'uploads/sample.md')

        with self.app.app_context():
            saved_path = os.path.join(get_docs_root(), 'uploads', 'sample.md')
        with open(saved_path, 'r', encoding='utf-8') as file_obj:
            content = file_obj.read()
        self.assertEqual(content, '# Visible Body\n')

    def test_media_upload_returns_local_media_url_and_creates_image_record(self):
        with self.app.app_context():
            admin = self._create_user('mediaadmin', role='admin')
            admin_id = admin.id

        self._login(admin_id)
        response = self.client.post(
            '/api/media_upload',
            data={
                'file': (BytesIO(b'png-bytes'), 'banner.png'),
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertTrue(payload['url'].startswith('/media/'))

        with self.app.app_context():
            image = Image.query.filter_by(url=payload['url']).first()
            self.assertIsNotNone(image)
            absolute_path = os.path.join(self.app.config['UPLOADS_DIR'], image.path.replace('/', os.sep))
        self.assertTrue(os.path.exists(absolute_path))

    def test_site_logo_setting_requires_admin(self):
        with self.app.app_context():
            user = self._create_user('logouser')
            user_id = user.id

        self._login(user_id)
        response = self.client.post('/api/settings/site-logo', data={'site_logo': '/media/logo/test.png'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['error'], 'Permission denied')

    def test_site_logo_setting_normalizes_local_path(self):
        with self.app.app_context():
            admin = self._create_user('logoadmin', role='admin')
            admin_id = admin.id

        self._login(admin_id)
        response = self.client.post('/api/settings/site-logo', data={'site_logo': 'media/logo/test.png'})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['site_logo'], '/media/logo/test.png')

        with self.app.app_context():
            setting = db.session.get(SystemSetting, 'site_logo')
            self.assertIsNotNone(setting)
            self.assertEqual(setting.value, '/media/logo/test.png')
