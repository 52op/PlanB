# -*- coding: utf-8 -*-
"""
IP 访问控制服务
IP Access Control Service
"""

import ipaddress
from flask import request, abort, current_app
from models import SystemSetting


class IPAccessControl:
    """IP 访问控制"""
    
    @staticmethod
    def get_client_ip():
        """
        获取客户端真实 IP
        考虑代理情况，从 X-Forwarded-For 获取
        """
        if request.headers.get('X-Forwarded-For'):
            # X-Forwarded-For 可能包含多个 IP，取第一个
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr
    
    @staticmethod
    def parse_ip_list(ip_text):
        """
        解析 IP 列表文本
        支持格式：
        - 单个 IP: 192.168.1.100
        - CIDR: 192.168.1.0/24
        - IP 范围: 192.168.1.100-192.168.1.200
        
        Returns:
            list: IP 网络对象列表
        """
        if not ip_text:
            return []
        
        networks = []
        lines = ip_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                # 处理 CIDR 格式
                if '/' in line:
                    networks.append(ipaddress.ip_network(line, strict=False))
                # 处理 IP 范围
                elif '-' in line:
                    start_ip, end_ip = line.split('-')
                    start = ipaddress.ip_address(start_ip.strip())
                    end = ipaddress.ip_address(end_ip.strip())
                    
                    # 将范围转换为网络列表
                    current = start
                    while current <= end:
                        networks.append(ipaddress.ip_network(f"{current}/32", strict=False))
                        current += 1
                # 处理单个 IP
                else:
                    networks.append(ipaddress.ip_network(f"{line}/32", strict=False))
            except Exception as e:
                current_app.logger.warning(f"解析 IP 失败: {line}, 错误: {str(e)}")
                continue
        
        return networks
    
    @staticmethod
    def is_ip_in_list(ip_str, ip_networks):
        """
        检查 IP 是否在列表中
        
        Args:
            ip_str: IP 字符串
            ip_networks: IP 网络对象列表
            
        Returns:
            bool: 是否在列表中
        """
        if not ip_networks:
            return False
        
        try:
            ip = ipaddress.ip_address(ip_str)
            for network in ip_networks:
                if ip in network:
                    return True
        except Exception as e:
            current_app.logger.warning(f"检查 IP 失败: {ip_str}, 错误: {str(e)}")
        
        return False
    
    @staticmethod
    def check_shared_secret():
        """
        检查共享密钥
        
        Returns:
            bool: 密钥是否正确
        """
        settings = {s.key: s.value for s in SystemSetting.query.all()}
        
        # 如果未启用共享密钥，返回 True
        if settings.get('security_shared_secret_enabled') != 'true':
            return True
        
        secret = settings.get('security_shared_secret', '').strip()
        if not secret:
            return True
        
        header_name = settings.get('security_shared_secret_header', 'X-Internal-Secret').strip()
        request_secret = request.headers.get(header_name, '').strip()
        
        return request_secret == secret
    
    @staticmethod
    def check_access():
        """
        检查访问权限
        
        Returns:
            tuple: (是否允许, 拒绝原因)
        """
        # 获取客户端 IP
        client_ip = IPAccessControl.get_client_ip()
        
        # 获取设置
        settings = {s.key: s.value for s in SystemSetting.query.all()}
        
        # 1. 检查共享密钥
        if not IPAccessControl.check_shared_secret():
            return False, f"共享密钥验证失败 (IP: {client_ip})"
        
        # 2. 检查黑名单
        if settings.get('security_ip_blacklist_enabled') == 'true':
            blacklist_text = settings.get('security_ip_blacklist', '')
            blacklist = IPAccessControl.parse_ip_list(blacklist_text)
            
            if IPAccessControl.is_ip_in_list(client_ip, blacklist):
                return False, f"IP 在黑名单中 (IP: {client_ip})"
        
        # 3. 检查白名单
        if settings.get('security_ip_whitelist_enabled') == 'true':
            whitelist_text = settings.get('security_ip_whitelist', '')
            whitelist = IPAccessControl.parse_ip_list(whitelist_text)
            
            if not IPAccessControl.is_ip_in_list(client_ip, whitelist):
                return False, f"IP 不在白名单中 (IP: {client_ip})"
        
        return True, None


def ip_access_control_middleware():
    """
    IP 访问控制中间件
    在每个请求前检查 IP 访问权限
    """
    # 跳过静态文件
    if request.path.startswith('/static/'):
        return
    
    # 检查访问权限
    allowed, reason = IPAccessControl.check_access()
    
    if not allowed:
        current_app.logger.warning(f"访问被拒绝: {reason}")
        abort(403, description=reason)
