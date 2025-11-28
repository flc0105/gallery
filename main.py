import os
import sqlite3
from datetime import datetime

from PIL import Image
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 配置
UPLOAD_FOLDER = 'uploads'
THUMBNAIL_FOLDER = 'thumbnails'
COMPRESSED_FOLDER = 'compressed'
DATABASE = 'gallery.db'

# 确保目录存在
for folder in [UPLOAD_FOLDER, THUMBNAIL_FOLDER, COMPRESSED_FOLDER]:
    os.makedirs(folder, exist_ok=True)


# 初始化数据库
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # 相册表
    c.execute('''
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cover_image_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            shoot_date TEXT,
            model_name TEXT,
            location TEXT
        )
    ''')

    # 图片表
    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            width INTEGER,
            height INTEGER,
            is_favorited BOOLEAN DEFAULT 0,
                        description TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (album_id) REFERENCES albums (id)
        )
    ''')

    # 相册密码表
    c.execute('''
            CREATE TABLE IF NOT EXISTS album_passwords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                album_id INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (album_id) REFERENCES albums (id) ON DELETE CASCADE,
                UNIQUE(album_id)
            )
        ''')

    conn.commit()
    conn.close()


# 数据库连接
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def generate_thumbnail(image_path, output_path, size=(250, 250)):
    with Image.open(image_path) as img:
        # 转换为RGB模式
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background

        # 计算裁剪区域，保持居中裁剪
        width, height = img.size
        # 选择较短的边作为裁剪尺寸
        crop_size = min(width, height)
        # 计算裁剪区域（居中）
        left = (width - crop_size) // 2
        top = (height - crop_size) // 2
        right = left + crop_size
        bottom = top + crop_size

        # 裁剪为正方形
        img_cropped = img.crop((left, top, right, bottom))
        # 调整到目标尺寸
        img_resized = img_cropped.resize(size, Image.Resampling.LANCZOS)
        img_resized.save(output_path, 'JPEG', quality=85)


# 生成压缩图
def generate_compressed(image_path, output_path, max_size=1200):
    with Image.open(image_path) as img:
        # 转换为RGB模式
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background

        # 计算新尺寸，保持宽高比
        if img.width > max_size or img.height > max_size:
            if img.width > img.height:
                new_width = max_size
                new_height = int(img.height * max_size / img.width)
            else:
                new_height = max_size
                new_width = int(img.width * max_size / img.height)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        img.save(output_path, 'JPEG', quality=80)


# API路由

# 获取所有相册
@app.route('/api/albums', methods=['GET'])
def get_albums():
    conn = get_db_connection()
    albums = conn.execute('''
        SELECT a.*, i.filename as cover_filename,
        (SELECT COUNT(*) FROM images WHERE album_id = a.id) as image_count,
        CASE WHEN ap.id IS NOT NULL THEN 1 ELSE 0 END as has_password
        FROM albums a 
        LEFT JOIN images i ON a.cover_image_id = i.id
        LEFT JOIN album_passwords ap ON a.id = ap.album_id
    ''').fetchall()
    conn.close()

    return jsonify([dict(album) for album in albums])


# 创建相册
@app.route('/api/albums', methods=['POST'])
def create_album():
    data = request.get_json()
    name = data.get('name')
    shoot_date = data.get('shoot_date')
    model_name = data.get('model_name')
    location = data.get('location')

    if not name:
        return jsonify({'error': '相册名称不能为空'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO albums (name,shoot_date, model_name, location)
        VALUES (?, ?, ?, ?)
    ''', (name, shoot_date, model_name, location))
    album_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'id': album_id, 'message': '相册创建成功'})


# 更新相册
@app.route('/api/albums/<int:album_id>', methods=['PUT'])
def update_album(album_id):
    data = request.get_json()
    name = data.get('name')
    shoot_date = data.get('shoot_date')
    model_name = data.get('model_name')
    location = data.get('location')
    cover_image_id = data.get('cover_image_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 构建更新语句
    update_fields = []
    values = []

    if name is not None:
        update_fields.append("name = ?")
        values.append(name)
    if shoot_date is not None:
        update_fields.append("shoot_date = ?")
        values.append(shoot_date)
    if model_name is not None:
        update_fields.append("model_name = ?")
        values.append(model_name)
    if location is not None:
        update_fields.append("location = ?")
        values.append(location)
    if cover_image_id is not None:
        update_fields.append("cover_image_id = ?")
        values.append(cover_image_id)

    if update_fields:
        values.append(album_id)
        cursor.execute(f'''
            UPDATE albums SET {', '.join(update_fields)} WHERE id = ?
        ''', values)
        conn.commit()

    conn.close()
    return jsonify({'message': '相册更新成功'})


# 删除相册
@app.route('/api/albums/<int:album_id>', methods=['DELETE'])
def delete_album(album_id):
    conn = get_db_connection()

    # 获取相册中的所有图片
    images = conn.execute('SELECT * FROM images WHERE album_id = ?', (album_id,)).fetchall()

    # 删除图片文件
    for image in images:
        original_path = os.path.join(UPLOAD_FOLDER, image['filename'])
        thumb_path = os.path.join(THUMBNAIL_FOLDER, image['filename'])
        compressed_path = os.path.join(COMPRESSED_FOLDER, image['filename'])

        for path in [original_path, thumb_path, compressed_path]:
            if os.path.exists(path):
                os.remove(path)

    # 删除数据库记录
    conn.execute('DELETE FROM images WHERE album_id = ?', (album_id,))
    conn.execute('DELETE FROM albums WHERE id = ?', (album_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': '相册删除成功'})


# 获取相册中的图片
@app.route('/api/albums/<int:album_id>/images', methods=['GET'])
def get_album_images(album_id):
    conn = get_db_connection()
    images = conn.execute('''
        SELECT * FROM images WHERE album_id = ? ORDER BY uploaded_at DESC
    ''', (album_id,)).fetchall()
    conn.close()

    return jsonify([dict(image) for image in images])


# 添加收藏API
@app.route('/api/images/<int:image_id>/favorite', methods=['POST'])
def toggle_favorite(image_id):
    conn = get_db_connection()
    image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()

    if not image:
        conn.close()
        return jsonify({'error': '图片不存在'}), 404

    # 切换收藏状态
    new_favorite_state = not image['is_favorited']
    conn.execute('UPDATE images SET is_favorited = ? WHERE id = ?',
                 (new_favorite_state, image_id))
    conn.commit()
    conn.close()

    return jsonify({
        'is_favorited': new_favorite_state,
        'message': '操作成功'
    })


# 上传图片到相册
@app.route('/api/albums/<int:album_id>/images', methods=['POST'])
def upload_image(album_id):
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    # 生成唯一文件名
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"

    original_path = os.path.join(UPLOAD_FOLDER, filename)
    thumb_path = os.path.join(THUMBNAIL_FOLDER, filename)
    compressed_path = os.path.join(COMPRESSED_FOLDER, filename)

    # 保存原图
    file.save(original_path)

    # 获取图片信息
    with Image.open(original_path) as img:
        width, height = img.size
        file_size = os.path.getsize(original_path)

    # 生成缩略图和压缩图
    generate_thumbnail(original_path, thumb_path)
    generate_compressed(original_path, compressed_path)

    # 保存到数据库
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO images (album_id, filename, original_filename, file_size, width, height)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (album_id, filename, file.filename, file_size, width, height))
    image_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'id': image_id,
        'filename': filename,
        'original_filename': file.filename,
        'message': '图片上传成功'
    })


# 删除图片
@app.route('/api/images/<int:image_id>', methods=['DELETE'])
def delete_image(image_id):
    conn = get_db_connection()

    # 获取图片信息
    image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()

    if image:
        # 删除文件
        original_path = os.path.join(UPLOAD_FOLDER, image['filename'])
        thumb_path = os.path.join(THUMBNAIL_FOLDER, image['filename'])
        compressed_path = os.path.join(COMPRESSED_FOLDER, image['filename'])

        for path in [original_path, thumb_path, compressed_path]:
            if os.path.exists(path):
                os.remove(path)

        # 删除数据库记录
        conn.execute('DELETE FROM images WHERE id = ?', (image_id,))
        conn.commit()

    conn.close()
    return jsonify({'message': '图片删除成功'})


# 获取相册图片数量
@app.route('/api/albums/<int:album_id>/image-count')
def get_album_image_count(album_id):
    conn = get_db_connection()
    count = conn.execute('SELECT COUNT(*) as count FROM images WHERE album_id = ?', (album_id,)).fetchone()
    conn.close()

    return jsonify({'count': count['count']})


# 获取图片文件
# @app.route('/api/images/<int:image_id>/file')
# def get_image_file(image_id):
#     file_type = request.args.get('type', 'compressed')  # compressed, thumbnail, original
#
#     conn = get_db_connection()
#     image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
#     conn.close()
#
#     if not image:
#         return jsonify({'error': '图片不存在'}), 404
#
#     if file_type == 'original':
#         file_path = os.path.join(UPLOAD_FOLDER, image['filename'])
#     elif file_type == 'thumbnail':
#         file_path = os.path.join(THUMBNAIL_FOLDER, image['filename'])
#     else:  # compressed
#         file_path = os.path.join(COMPRESSED_FOLDER, image['filename'])
#
#     if not os.path.exists(file_path):
#         return jsonify({'error': '文件不存在'}), 404
#
#     return send_file(file_path)
@app.route('/api/images/<int:image_id>/file')
def get_image_file(image_id):
    file_type = request.args.get('type', 'compressed')  # compressed, thumbnail, original

    conn = get_db_connection()
    image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
    conn.close()

    if not image:
        return jsonify({'error': '图片不存在'}), 404

    # 获取文件路径
    original_path = os.path.join(UPLOAD_FOLDER, image['filename'])
    thumb_path = os.path.join(THUMBNAIL_FOLDER, image['filename'])
    compressed_path = os.path.join(COMPRESSED_FOLDER, image['filename'])

    if file_type == 'original':
        file_path = original_path
    elif file_type == 'thumbnail':
        file_path = thumb_path
    else:  # compressed
        file_path = compressed_path

    # 检查请求的文件是否存在
    if os.path.exists(file_path):
        return send_file(file_path)

    # 如果请求的文件不存在，但原图存在，重新生成
    if file_type != 'original' and os.path.exists(original_path):
        try:
            if file_type == 'thumbnail':
                generate_thumbnail(original_path, thumb_path)
            else:  # compressed
                generate_compressed(original_path, compressed_path)

            # 检查是否生成成功
            if os.path.exists(file_path):
                return send_file(file_path)
        except Exception as e:
            # 生成失败，返回错误
            return jsonify({'error': f'文件生成失败: {str(e)}'}), 500

    # 其他情况返回文件不存在
    return jsonify({'error': '文件不存在'}), 404


# 服务前端页面
@app.route('/')
def index():
    return send_file('index.html')


# 可选的：服务静态文件（如果需要额外的CSS/JS文件）
@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_file(path)
    else:
        return "File not found", 404


@app.route('/api/images/<int:image_id>/rename', methods=['POST'])
def rename_image(image_id):
    data = request.get_json()
    new_filename = data.get('new_filename')

    if not new_filename:
        return jsonify({'error': '新文件名不能为空'}), 400

    conn = get_db_connection()
    image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()

    if not image:
        conn.close()
        return jsonify({'error': '图片不存在'}), 404

    # 检查新文件名是否已存在
    existing = conn.execute('SELECT id FROM images WHERE original_filename = ? AND id != ?',
                            (new_filename, image_id)).fetchone()
    if existing:
        conn.close()
        return jsonify({'error': '文件名已存在'}), 400

    # 更新数据库
    conn.execute('UPDATE images SET original_filename = ? WHERE id = ?',
                 (new_filename, image_id))
    conn.commit()
    conn.close()

    return jsonify({'message': '重命名成功'})


# mima start

# 验证相册密码API
@app.route('/api/albums/<int:album_id>/verify-password', methods=['POST'])
def verify_album_password(album_id):
    data = request.get_json()
    password = data.get('password')

    if not password:
        return jsonify({'error': '密码不能为空'}), 400

    conn = get_db_connection()

    # 检查相册是否存在
    album = conn.execute('SELECT * FROM albums WHERE id = ?', (album_id,)).fetchone()
    if not album:
        conn.close()
        return jsonify({'error': '相册不存在'}), 404

    # 获取密码哈希
    password_record = conn.execute(
        'SELECT * FROM album_passwords WHERE album_id = ?',
        (album_id,)
    ).fetchone()
    conn.close()

    if not password_record:
        return jsonify({'error': '此相册未设置密码'}), 400

    # 简单密码验证（实际应该使用加密哈希）
    if password_record['password_hash'] == password:
        return jsonify({
            'success': True,
            'message': '密码验证成功',
            'token': f'album_{album_id}_verified'
        })
    else:
        return jsonify({'error': '密码错误'}), 401


# 设置/更新相册密码
@app.route('/api/albums/<int:album_id>/password', methods=['POST'])
def set_album_password(album_id):
    data = request.get_json()
    password = data.get('password')

    if not password:
        return jsonify({'error': '密码不能为空'}), 400

    conn = get_db_connection()

    # 检查相册是否存在
    album = conn.execute('SELECT * FROM albums WHERE id = ?', (album_id,)).fetchone()
    if not album:
        conn.close()
        return jsonify({'error': '相册不存在'}), 404

    # 检查是否已设置密码
    existing_password = conn.execute(
        'SELECT id FROM album_passwords WHERE album_id = ?',
        (album_id,)
    ).fetchone()

    if existing_password:
        # 更新密码
        conn.execute(
            'UPDATE album_passwords SET password_hash = ? WHERE album_id = ?',
            (password, album_id)
        )
    else:
        # 插入新密码
        conn.execute(
            'INSERT INTO album_passwords (album_id, password_hash) VALUES (?, ?)',
            (album_id, password)
        )

    conn.commit()
    conn.close()

    return jsonify({'message': '密码设置成功'})


# 移除相册密码
@app.route('/api/albums/<int:album_id>/password', methods=['DELETE'])
def remove_album_password(album_id):
    conn = get_db_connection()

    # 检查相册是否存在
    album = conn.execute('SELECT * FROM albums WHERE id = ?', (album_id,)).fetchone()
    if not album:
        conn.close()
        return jsonify({'error': '相册不存在'}), 404

    # 删除密码记录
    conn.execute('DELETE FROM album_passwords WHERE album_id = ?', (album_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': '密码已移除'})


# 检查相册是否有密码
@app.route('/api/albums/<int:album_id>/has-password')
def check_album_password(album_id):
    conn = get_db_connection()

    password_record = conn.execute(
        'SELECT id FROM album_passwords WHERE album_id = ?',
        (album_id,)
    ).fetchone()
    conn.close()

    return jsonify({'has_password': password_record is not None})


## mima end

# 更新图片描述API
@app.route('/api/images/<int:image_id>/description', methods=['PUT'])
def update_image_description(image_id):
    data = request.get_json()
    description = data.get('description', '')

    conn = get_db_connection()

    # 检查图片是否存在
    image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
    if not image:
        conn.close()
        return jsonify({'error': '图片不存在'}), 404

    # 更新描述
    conn.execute('UPDATE images SET description = ? WHERE id = ?',
                 (description, image_id))
    conn.commit()
    conn.close()

    return jsonify({'message': '描述更新成功'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='192.168.2.246', port=5000)
    # app.run(debug=True)
