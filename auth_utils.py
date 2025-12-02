from datetime import datetime


token_expire_minutes = 30

# 验证token的函数
def verify_auth_token(token, album_id):
    """验证相册访问token"""
    if not token or not token.startswith('album_'):
        return False

    try:
        # 解析token格式: album_{album_id}_verified_{timestamp}
        parts = token.split('_')
        if len(parts) < 3:
            return False

        token_album_id = int(parts[1])
        if token_album_id != album_id:
            return False

        # 检查token是否过期（5分钟）
        if len(parts) >= 4:
            token_time = int(parts[3])
            current_time = int(datetime.now().timestamp())
            if current_time - token_time > token_expire_minutes * 60:  # 30分钟过期
                return False

        return True
    except:
        return False


# 生成token的函数
def generate_auth_token(album_id):
    """生成相册访问token"""
    timestamp = int(datetime.now().timestamp())
    return f"album_{album_id}_verified_{timestamp}"