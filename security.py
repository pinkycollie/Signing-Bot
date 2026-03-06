"""
Security and protection layer for the Sign to Earn platform.

This module provides comprehensive security features including:
- Rate limiting
- Bot detection
- Request filtering
- IP blacklisting
- Content Security Policy (CSP)
- CSRF protection
- Firewall functionality
"""

import os
import re
import logging
import ipaddress
from functools import wraps
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any, Union

from flask import Flask, request, abort, session, g, jsonify, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_ipban import IpBan

logger = logging.getLogger(__name__)

# Initialize security components with empty defaults
limiter = Limiter(key_func=get_remote_address)
ip_ban = IpBan()
talisman = Talisman()

# Bot detection
BOT_USER_AGENT_PATTERNS = [
    r'bot', r'crawl', r'spider', r'slurp', r'baiduspider', r'yandex', 
    r'wget', r'curl', r'python-requests', r'scrapy', r'phantom', r'selenium', 
    r'headless', r'http\s?client', r'^go-http'
]
BOT_USER_AGENT_REGEX = re.compile('|'.join(BOT_USER_AGENT_PATTERNS), re.IGNORECASE)

# Store failed login attempts
FAILED_LOGIN_ATTEMPTS = {}
MAX_FAILED_ATTEMPTS = 5
FAILED_ATTEMPT_EXPIRY = 900  # 15 minutes

# Trusted proxy list (for getting real IP behind proxies)
TRUSTED_PROXIES = [
    # Cloudflare IP ranges
    '173.245.48.0/20',
    '103.21.244.0/22',
    '103.22.200.0/22',
    '103.31.4.0/22',
    '141.101.64.0/18',
    '108.162.192.0/18',
    '190.93.240.0/20',
    '188.114.96.0/20',
    '197.234.240.0/22',
    '198.41.128.0/17',
    '162.158.0.0/15',
    '104.16.0.0/13',
    '104.24.0.0/14',
    '172.64.0.0/13',
    '131.0.72.0/22',
    # Vercel IP ranges
    '76.76.21.0/24',
]

# Convert to IPNetwork objects once at startup
TRUSTED_PROXY_NETWORKS = [ipaddress.ip_network(proxy) for proxy in TRUSTED_PROXIES]

def get_real_ip() -> str:
    """
    Get the real IP address, accounting for proxies.
    
    Returns:
        Client's real IP address
    """
    # Default to remote_addr
    client_ip = request.remote_addr
    
    # If we have X-Forwarded-For and the request came from a trusted proxy
    if request.headers.get('X-Forwarded-For') and client_ip:
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            is_trusted_proxy = any(client_ip_obj in network for network in TRUSTED_PROXY_NETWORKS)
            
            if is_trusted_proxy:
                # X-Forwarded-For can be a comma-separated list
                # The client's IP is the first one
                forwarded_ips = request.headers.get('X-Forwarded-For', '').split(',')
                if forwarded_ips:
                    return forwarded_ips[0].strip()
        except (ValueError, TypeError):
            # If there's any error parsing IPs, fall back to remote_addr
            pass
    
    return client_ip

def is_bot() -> bool:
    """
    Check if the current request is from a bot.
    
    Returns:
        Boolean indicating if the request is from a bot
    """
    user_agent = request.headers.get('User-Agent', '')
    # Check for bot patterns in User-Agent
    if BOT_USER_AGENT_REGEX.search(user_agent):
        return True
    
    # Check for common bot indicators
    if not request.headers.get('Accept-Language'):
        return True
    
    # Check for suspicious headers combination
    headers = request.headers
    if (not headers.get('Accept') and 
        not headers.get('Accept-Encoding') and 
        not headers.get('Cookie')):
        return True
    
    return False

def bot_protection(allowed_bots: Optional[List[str]] = None) -> Callable:
    """
    Decorator for blocking bots from specific routes.
    
    Args:
        allowed_bots: List of allowed bot user agent substrings
    
    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_agent = request.headers.get('User-Agent', '')
            
            # If it's a bot
            if is_bot():
                # Check if it's an allowed bot
                if allowed_bots and any(bot in user_agent for bot in allowed_bots):
                    return f(*args, **kwargs)
                
                # Log and block other bots
                logger.warning(f"Bot request blocked: {user_agent} to {request.path}")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_request_integrity() -> bool:
    """
    Check if the request has integrity concerns.
    
    Returns:
        Boolean indicating if request is suspicious
    """
    # Check for inconsistent host headers (host header spoofing)
    host = request.headers.get('Host', '')
    if host and host not in current_app.config.get('ALLOWED_HOSTS', [host]):
        logger.warning(f"Host header spoofing detected: {host}")
        return False
    
    # Check for suspicious query parameters (SQL injection attempts)
    for key, value in request.args.items():
        if isinstance(value, str) and any(x in value.lower() for x in ["select", "union", "delete", "drop", "--", ";"]):
            logger.warning(f"Potential SQL injection attempt in query params: {key}={value}")
            return False
    
    # Check for suspicious form data
    for key, value in request.form.items():
        if isinstance(value, str) and any(x in value.lower() for x in ["<script>", "javascript:", "onload=", "onerror="]):
            logger.warning(f"Potential XSS attempt in form data: {key}={value}")
            return False
    
    return True

def record_failed_login(ip: str) -> None:
    """
    Record a failed login attempt.
    
    Args:
        ip: IP address of the attempt
    """
    now = datetime.now()
    
    if ip in FAILED_LOGIN_ATTEMPTS:
        # Clean expired attempts
        attempts = [(time, count) for time, count in FAILED_LOGIN_ATTEMPTS[ip] 
                   if (now - time).seconds < FAILED_ATTEMPT_EXPIRY]
        attempts.append((now, 1))
        FAILED_LOGIN_ATTEMPTS[ip] = attempts
    else:
        FAILED_LOGIN_ATTEMPTS[ip] = [(now, 1)]
    
    # Check if we need to ban this IP
    if sum(count for _, count in FAILED_LOGIN_ATTEMPTS[ip]) >= MAX_FAILED_ATTEMPTS:
        logger.warning(f"IP {ip} banned due to too many failed login attempts")
        ip_ban.block(ip, permanent=False)

def clear_failed_logins(ip: str) -> None:
    """
    Clear failed login attempts for an IP after successful login.
    
    Args:
        ip: IP address to clear
    """
    if ip in FAILED_LOGIN_ATTEMPTS:
        del FAILED_LOGIN_ATTEMPTS[ip]

def configure_security(app: Flask) -> None:
    """
    Configure and initialize all security features for the application.
    
    Args:
        app: Flask application
    """
    global limiter, ip_ban, talisman
    
    # Set up rate limiting
    limiter = Limiter(
        key_func=get_real_ip,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=os.environ.get("REDIS_URL", "memory://"),
        strategy="fixed-window"
    )
    
    # Allow specific whitelisted IPs without rate limiting
    whitelisted_ips = os.environ.get('WHITELISTED_IPS', '').split(',')
    if whitelisted_ips:
        @limiter.request_filter
        def ip_whitelist():
            return get_real_ip() in whitelisted_ips
    
    # Set up IP banning
    ip_ban.init_app(app)
    ip_ban.load_nuisances()  # Load predefined nuisance IP list
    
    # Load banned IPs from environment variable if available
    banned_ips = os.environ.get('BANNED_IPS', '').split(',')
    for ip in banned_ips:
        if ip.strip():
            ip_ban.block(ip.strip(), permanent=True)
    
    # Set up content security policy
    csp = {
        'default-src': "'self'",
        'img-src': ["'self'", 'data:', 'https://cdn.jsdelivr.net'],
        'script-src': ["'self'", 'https://cdn.jsdelivr.net', "'unsafe-inline'"],
        'style-src': ["'self'", 'https://cdn.jsdelivr.net', "'unsafe-inline'"],
        'font-src': ["'self'", 'https://cdn.jsdelivr.net'],
        'connect-src': ["'self'", 'https://api.example.com']  # Add your API domains here
    }
    
    talisman = Talisman(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=['script-src'],
        feature_policy={
            'geolocation': "'none'",
            'microphone': "'none'",
            'camera': "'none'"
        },
        force_https=os.environ.get('FORCE_HTTPS', 'true').lower() == 'true',
        force_https_permanent=True,
        session_cookie_secure=True,
        session_cookie_http_only=True
    )
    
    # Configure allowed hosts
    app.config['ALLOWED_HOSTS'] = os.environ.get('ALLOWED_HOSTS', '*').split(',')
    
    # Add request filtering middleware
    @app.before_request
    def before_request():
        # Bot detection for API endpoints
        if request.path.startswith('/api/') and is_bot():
            # Allow only whitelisted bots if accessing API endpoints
            user_agent = request.headers.get('User-Agent', '')
            allowed_api_bots = app.config.get('ALLOWED_API_BOTS', [])
            if not any(bot in user_agent for bot in allowed_api_bots):
                logger.warning(f"Bot API access blocked: {user_agent} to {request.path}")
                abort(403)
        
        # Request integrity check
        if not check_request_integrity():
            logger.warning(f"Request integrity check failed: {get_real_ip()} to {request.path}")
            abort(400)
        
        # Record excessive 404s from the same IP (path scanning)
        if request.endpoint == 'page_not_found':
            client_ip = get_real_ip()
            key = f"404_count:{client_ip}"
            # This would normally use a cache/redis but we're using the session for simplicity
            count = session.get(key, 0) + 1
            session[key] = count
            if count > 20:  # If more than 20 404s in a session
                logger.warning(f"Excessive 404s from {client_ip}, possible scanning")
                ip_ban.block(client_ip, permanent=False, seconds=3600)  # Ban for an hour
                abort(403)

    # Add CSRF protection globally
    @app.before_request
    def csrf_protection():
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            # Skip CSRF for API endpoints with token auth
            if request.path.startswith('/api/') and request.headers.get('Authorization'):
                return
                
            token = session.get('_csrf_token')
            request_token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
            
            if not token or token != request_token:
                logger.warning(f"CSRF token missing or invalid: {get_real_ip()} to {request.path}")
                abort(403)

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        # Record failed access attempts
        ip = get_real_ip()
        logger.warning(f"403 Forbidden: {ip} to {request.path}")
        
        if request.path.startswith('/api/'):
            return jsonify(error="Access forbidden"), 403
        return "Access Forbidden", 403

    @app.errorhandler(429)
    def ratelimit_handler(e):
        # Log rate limit exceeded
        ip = get_real_ip()
        logger.warning(f"Rate limit exceeded: {ip} on {request.path}")
        
        if request.path.startswith('/api/'):
            return jsonify(error="Rate limit exceeded"), 429
        return "Too many requests, please try again later.", 429

    logger.info("Security layer configured successfully")