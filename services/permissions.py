from models import PermissionRule


def check_permission(user, target_path, action):
    if user is None or not getattr(user, "is_authenticated", False):
        return action == 'read'

    if user.role == 'admin':
        return True

    rules = PermissionRule.query.filter_by(user_id=user.id).all()
    matched_rule = None
    max_len = -1

    for rule in rules:
        if rule.dir_path == '*' or target_path.startswith(rule.dir_path):
            if len(rule.dir_path) > max_len:
                max_len = len(rule.dir_path)
                matched_rule = rule

    if not matched_rule:
        return action == 'read'

    if action == 'read':
        return bool(matched_rule.can_read)
    if action == 'edit':
        return bool(matched_rule.can_edit)
    if action == 'upload':
        return bool(matched_rule.can_upload)
    if action == 'delete':
        return bool(matched_rule.can_delete)
    return False
