import hashlib
import os
import time

token_expire_minutes = 10


# 生成更安全的token
def generate_auth_token(album_id):
    """生成带时间戳和签名的token"""
    timestamp = int(time.time())
    # 使用密钥签名（可以配置在环境变量中）
    secret_key = os.getenv('TOKEN_SECRET', 'flc')
    # 生成签名: md5(album_id + timestamp + secret_key)
    sign_str = f"{album_id}_{timestamp}_{secret_key}"
    signature = hashlib.md5(sign_str.encode()).hexdigest()[:8]
    return f"album_{album_id}_{timestamp}_{signature}"


# 验证token
def verify_auth_token(token, album_id):
    """验证token的有效性"""
    if not token or not token.startswith('album_'):
        return False

    try:
        # 解析token: album_{album_id}_{timestamp}_{signature}
        parts = token.split('_')
        if len(parts) != 4:
            return False

        token_album_id = int(parts[1])
        token_timestamp = int(parts[2])
        token_signature = parts[3]

        # 验证相册ID匹配
        if token_album_id != album_id:
            return False

        # 验证时间戳（30分钟有效期）
        current_time = int(time.time())
        if current_time - token_timestamp > token_expire_minutes * 60:  # 30分钟
            return False

        # 验证签名
        secret_key = os.getenv('TOKEN_SECRET', 'flc')
        expected_sign_str = f"{album_id}_{token_timestamp}_{secret_key}"
        expected_signature = hashlib.md5(expected_sign_str.encode()).hexdigest()[:8]

        return token_signature == expected_signature

    except:
        return False
