"""
Custom decorators for the Automated HR application.
Includes role-based access control, rate limiting, and request validation.
"""
import functools
import json
import time
from datetime import datetime, timedelta, timezone
from flask import request, jsonify, current_app, g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

# Redis client for rate limiting (assuming Redis is configured in app)
try:
    from app import redis_client
except ImportError:
    redis_client = None
    print("Warning: Redis not configured. Rate limiting will use in-memory storage (not suitable for production).")
    # Simple in-memory cache as a fallback
    class SimpleCache:
        def __init__(self):
            self.cache = {}
            
        def get(self, key):
            # Clean expired entries
            now = time.time()
            self.cache = {k: v for k, v in self.cache.items() if v['expires'] > now}
            return self.cache.get(key, {}).get('value')
            
        def set(self, key, value, ex=60):
            self.cache[key] = {
                'value': value,
                'expires': time.time() + ex
            }
            
        def incr(self, key):
            value = self.get(key) or 0
            value += 1
            self.set(key, value)
            return value
            
    redis_client = SimpleCache()

def role_required(*roles):
    """
    Decorator for role-based access control.
    Requires that the user has one of the specified roles.
    
    Args:
        *roles: List of allowed roles
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Verify JWT is present and valid
            verify_jwt_in_request()
            
            # Get current user identity
            current_user = get_jwt_identity()
            
            # Check if current_user has required role
            if not current_user or 'role' not in current_user or current_user['role'] not in roles:
                return jsonify({"message": "Access denied: insufficient permissions"}), 403
            
            # Store user info in g for access in the route function
            g.current_user = current_user
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def enterprise_required(fn):
    """
    Shorthand decorator requiring enterprise role.
    """
    @functools.wraps(fn)
    @role_required('enterprise')
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    """
    Shorthand decorator requiring admin role.
    """
    @functools.wraps(fn)
    @role_required('admin')
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def rate_limit(limit=100, period=60, by="ip"):
    """
    Rate limiting decorator.
    
    Args:
        limit: Maximum number of requests allowed in the period
        period: Time period in seconds
        by: What to limit by - 'ip' or 'user' (user requires auth)
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if by == "user":
                # Rate limit by user ID (requires auth)
                try:
                    verify_jwt_in_request()
                    current_user = get_jwt_identity()
                    key = f"rate_limit:{current_user['id']}:{request.endpoint}"
                except Exception:
                    # Fallback to IP if user auth fails
                    key = f"rate_limit:{request.remote_addr}:{request.endpoint}"
            else:
                # Rate limit by IP address
                key = f"rate_limit:{request.remote_addr}:{request.endpoint}"
                
            # Increment the counter
            current = redis_client.incr(key)
            
            # Set expiry on first request
            if current == 1:
                redis_client.set(key, current, ex=period)
            
            # Check if limit exceeded
            if current > limit:
                return jsonify({
                    "message": "Rate limit exceeded. Please try again later.",
                    "retry_after": period
                }), 429
                
            # Add rate limit headers
            response = fn(*args, **kwargs)
            
            # If response is a tuple (response, status_code)
            if isinstance(response, tuple) and len(response) == 2:
                resp_obj, status_code = response
                if isinstance(resp_obj, dict):
                    resp_obj = jsonify(resp_obj)
                resp_obj.headers['X-RateLimit-Limit'] = str(limit)
                resp_obj.headers['X-RateLimit-Remaining'] = str(max(0, limit - current))
                resp_obj.headers['X-RateLimit-Reset'] = str(period)
                return resp_obj, status_code
            
            # If response is a standard response
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(max(0, limit - current))
                response.headers['X-RateLimit-Reset'] = str(period)
                
            return response
        return wrapper
    return decorator

def validate_request(schema):
    """
    Validate request data against a schema.
    
    Args:
        schema: Dictionary defining the expected schema
               Keys are field names, values are dictionaries with 'type', 'required', and optional 'validate' function
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if request.is_json:
                data = request.get_json()
            elif request.form:
                data = request.form.to_dict()
            else:
                data = {}
            
            errors = {}
            
            # Validate each field according to schema
            for field, rules in schema.items():
                # Check required fields
                if rules.get('required', False) and (field not in data or data[field] is None):
                    errors[field] = f"{field} is required"
                    continue
                    
                # Skip validation for optional fields that aren't present
                if field not in data:
                    continue
                    
                # Type validation
                if 'type' in rules:
                    expected_type = rules['type']
                    value = data[field]
                    
                    if expected_type == 'string' and not isinstance(value, str):
                        errors[field] = f"{field} must be a string"
                    elif expected_type == 'int' and not (isinstance(value, int) or (isinstance(value, str) and value.isdigit())):
                        errors[field] = f"{field} must be an integer"
                    elif expected_type == 'float' and not (isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit())):
                        errors[field] = f"{field} must be a number"
                    elif expected_type == 'bool' and not isinstance(value, bool) and value not in ('true', 'false', '0', '1'):
                        errors[field] = f"{field} must be a boolean"
                    elif expected_type == 'email' and (not isinstance(value, str) or '@' not in value or '.' not in value.split('@')[1]):
                        errors[field] = f"{field} must be a valid email address"
                    elif expected_type == 'date' and not (isinstance(value, str) and len(value.split('-')) == 3):
                        errors[field] = f"{field} must be a valid date (YYYY-MM-DD)"
                    elif expected_type == 'list' and not isinstance(value, list):
                        # Try to convert JSON string to list
                        if isinstance(value, str):
                            try:
                                data[field] = json.loads(value)
                            except Exception:
                                errors[field] = f"{field} must be a valid list"
                        else:
                            errors[field] = f"{field} must be a list"
                
                # Custom validation function
                if 'validate' in rules and field in data and field not in errors:
                    validator = rules['validate']
                    result = validator(data[field])
                    if result is not True:
                        errors[field] = result
            
            if errors:
                return jsonify({"message": "Validation failed", "errors": errors}), 400
                
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def cache_response(timeout=300):
    """
    Cache decorator for API responses.
    
    Args:
        timeout: Cache timeout in seconds
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Skip caching for non-GET requests
            if request.method != 'GET':
                return fn(*args, **kwargs)
                
            # Create a cache key from the request
            key = f"cache:{request.path}:{request.query_string.decode('utf-8')}"
            
            # Try to get response from cache
            cached = redis_client.get(key)
            if cached:
                response_data = json.loads(cached)
                return jsonify(response_data)
                
            # Generate the response
            response = fn(*args, **kwargs)
            
            # Cache successful JSON responses
            if isinstance(response, tuple):
                resp_obj, status_code = response
                if status_code == 200 and isinstance(resp_obj, dict):
                    redis_client.set(key, json.dumps(resp_obj), ex=timeout)
            else:
                # For direct responses
                try:
                    data = response.get_json()
                    redis_client.set(key, json.dumps(data), ex=timeout)
                except Exception:
                    # Not a JSON response, don't cache
                    pass
                    
            return response
        return wrapper
    return decorator

def track_activity(activity_type):
    """
    Track user activity for analytics.
    
    Args:
        activity_type: String describing the activity type
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Get user ID if authenticated
            user_id = None
            try:
                verify_jwt_in_request(optional=True)
                identity = get_jwt_identity()
                if identity:
                    user_id = identity.get('id')
            except Exception:
                pass
                
            # Record the activity start time
            start_time = time.time()
            
            # Execute the original function
            response = fn(*args, **kwargs)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Prepare activity data
            activity_data = {
                'timestamp':datetime.now(timezone.utc).isoformat(),
                'user_id': user_id,
                'ip_address': request.remote_addr,
                'endpoint': request.endpoint,
                'method': request.method,
                'path': request.path,
                'activity_type': activity_type,
                'execution_time': execution_time,
                'user_agent': request.headers.get('User-Agent', '')
            }
            
            # In a real application, you would save this to a database
            # For now, just log it
            current_app.logger.info(f"Activity: {json.dumps(activity_data)}")
            
            # You could also send this to a queue for async processing
            # app.task_queue.enqueue('log_activity', activity_data)
            
            return response
        return wrapper
    return decorator