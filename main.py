import os
import sqlite3
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import json
from datetime import datetime
import exifread

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
            description TEXT,
            cover_image_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            shoot_date TEXT,
            model_name TEXT,
            weather TEXT,
            equipment TEXT
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
            exif_data TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (album_id) REFERENCES albums (id)
        )
    ''')

    conn.commit()
    conn.close()


# 数据库连接
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# 生成缩略图
# def generate_thumbnail(image_path, output_path, size=(200, 200)):
#     with Image.open(image_path) as img:
#         # 转换为RGB模式（处理RGBA图片）
#         if img.mode in ('RGBA', 'LA'):
#             background = Image.new('RGB', img.size, (255, 255, 255))
#             background.paste(img, mask=img.split()[-1])
#             img = background
#
#         # 计算缩略图尺寸，保持宽高比
#         img.thumbnail(size, Image.Resampling.LANCZOS)
#
#         # 创建方形画布
#         thumb = Image.new('RGB', size, (255, 255, 255))
#
#         # 计算居中位置
#         x = (size[0] - img.size[0]) // 2
#         y = (size[1] - img.size[1]) // 2
#
#         # 粘贴图片到画布
#         thumb.paste(img, (x, y))
#         thumb.save(output_path, 'JPEG', quality=85)


def generate_thumbnail(image_path, output_path, size=(250, 250)):  # 改为250x250
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


# 获取EXIF数据
def get_exif_data(image_path):
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f)
            exif_data = {}
            for tag, value in tags.items():
                if tag not in ('JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote'):
                    exif_data[tag] = str(value)
            return exif_data
    except:
        return {}


# API路由

# 获取所有相册
@app.route('/api/albums', methods=['GET'])
def get_albums():
    conn = get_db_connection()
    albums = conn.execute('''
        SELECT a.*, i.filename as cover_filename 
        FROM albums a 
        LEFT JOIN images i ON a.cover_image_id = i.id
    ''').fetchall()
    conn.close()

    return jsonify([dict(album) for album in albums])


# 创建相册
@app.route('/api/albums', methods=['POST'])
def create_album():
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')
    shoot_date = data.get('shoot_date')
    model_name = data.get('model_name')
    weather = data.get('weather')
    equipment = data.get('equipment')

    if not name:
        return jsonify({'error': '相册名称不能为空'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO albums (name, description, shoot_date, model_name, weather, equipment)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, description, shoot_date, model_name, weather, equipment))
    album_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'id': album_id, 'message': '相册创建成功'})


# 更新相册
@app.route('/api/albums/<int:album_id>', methods=['PUT'])
def update_album(album_id):
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    shoot_date = data.get('shoot_date')
    model_name = data.get('model_name')
    weather = data.get('weather')
    equipment = data.get('equipment')
    cover_image_id = data.get('cover_image_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 构建更新语句
    update_fields = []
    values = []

    if name is not None:
        update_fields.append("name = ?")
        values.append(name)
    if description is not None:
        update_fields.append("description = ?")
        values.append(description)
    if shoot_date is not None:
        update_fields.append("shoot_date = ?")
        values.append(shoot_date)
    if model_name is not None:
        update_fields.append("model_name = ?")
        values.append(model_name)
    if weather is not None:
        update_fields.append("weather = ?")
        values.append(weather)
    if equipment is not None:
        update_fields.append("equipment = ?")
        values.append(equipment)
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

    # 获取EXIF数据
    exif_data = get_exif_data(original_path)

    # 保存到数据库
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO images (album_id, filename, original_filename, file_size, width, height, exif_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (album_id, filename, file.filename, file_size, width, height, json.dumps(exif_data)))
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


# 获取图片文件
@app.route('/api/images/<int:image_id>/file')
def get_image_file(image_id):
    file_type = request.args.get('type', 'compressed')  # compressed, thumbnail, original

    conn = get_db_connection()
    image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
    conn.close()

    if not image:
        return jsonify({'error': '图片不存在'}), 404

    if file_type == 'original':
        file_path = os.path.join(UPLOAD_FOLDER, image['filename'])
    elif file_type == 'thumbnail':
        file_path = os.path.join(THUMBNAIL_FOLDER, image['filename'])
    else:  # compressed
        file_path = os.path.join(COMPRESSED_FOLDER, image['filename'])

    if not os.path.exists(file_path):
        return jsonify({'error': '文件不存在'}), 404

    return send_file(file_path)


# 获取图片EXIF信息
@app.route('/api/images/<int:image_id>/exif')
def get_image_exif(image_id):
    conn = get_db_connection()
    image = conn.execute('SELECT exif_data FROM images WHERE id = ?', (image_id,)).fetchone()
    conn.close()

    if not image:
        return jsonify({'error': '图片不存在'}), 404

    exif_data = json.loads(image['exif_data']) if image['exif_data'] else {}
    return jsonify(exif_data)


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


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
