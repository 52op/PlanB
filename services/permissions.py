from models import PermissionRule


def _normalize_target_path(target_path):
    return str(target_path or '').replace('\\', '/').strip('/')


def _get_rule_flag(rule, action):
    if rule is None:
        return False
    if action == 'read':
        return bool(rule.can_read)
    if action == 'edit':
        return bool(rule.can_edit)
    if action == 'upload':
        return bool(rule.can_upload)
    if action == 'delete':
        return bool(rule.can_delete)
    return False


def get_matched_permission_rule(user, target_path):
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    if getattr(user, 'role', '') == 'admin':
        return None

    normalized_target = _normalize_target_path(target_path)
    rules = PermissionRule.query.filter_by(user_id=user.id).all()
    matched_rule = None
    max_len = -1

    for rule in rules:
        rule_path = str(rule.dir_path or '').strip()
        if rule_path == '*':
            candidate_match = True
            candidate_len = 0
        else:
            normalized_rule = _normalize_target_path(rule_path)
            candidate_match = (
                normalized_target == normalized_rule
                or normalized_target.startswith(f'{normalized_rule}/')
            )
            candidate_len = len(normalized_rule)

        if candidate_match and candidate_len > max_len:
            max_len = candidate_len
            matched_rule = rule

    return matched_rule


def has_explicit_permission(user, target_path, action):
    if user is None or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, 'role', '') == 'admin':
        return True

    matched_rule = get_matched_permission_rule(user, target_path)
    return _get_rule_flag(matched_rule, action)


def check_permission(user, target_path, action):
    if user is None or not getattr(user, "is_authenticated", False):
        return action == 'read'

    if user.role == 'admin':
        return True

    matched_rule = get_matched_permission_rule(user, target_path)
    if not matched_rule:
        return action == 'read'

    return _get_rule_flag(matched_rule, action)
