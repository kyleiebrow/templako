"""
File upload utilities for images and media
"""
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import io

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/lako_uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def ensure_upload_folder():
    """Create upload folder if it doesn't exist"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def is_allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image_data, max_width=1200, max_height=1200, quality=85):
    """Compress image to reduce file size"""
    try:
        img = Image.open(io.BytesIO(image_data))
        # Convert RGBA to RGB if needed
        if img.mode in ('RGBA', 'LA'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img
        # Resize
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        # Save compressed
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        print(f"Error compressing image: {e}")
        return image_data

def save_upload(file_obj, category='posts'):
    """
    Save uploaded file and return path
    
    Args:
        file_obj: Flask file object
        category: subfolder category (posts, profiles, vendors, etc)
    
    Returns:
        dict with 'success', 'path', and error info
    """
    ensure_upload_folder()
    
    try:
        if not file_obj or file_obj.filename == '':
            return {'success': False, 'error': 'No file selected'}
        
        if not is_allowed_file(file_obj.filename):
            return {'success': False, 'error': 'File type not allowed'}
        
        # Read file data
        file_data = file_obj.read()
        
        if len(file_data) > MAX_FILE_SIZE:
            return {'success': False, 'error': f'File too large (max {MAX_FILE_SIZE/1024/1024:.0f}MB)'}
        
        # Compress image
        compressed_data = compress_image(file_data)
        
        # Generate unique filename
        ext = file_obj.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        
        # Create category subfolder
        category_path = os.path.join(UPLOAD_FOLDER, category)
        if not os.path.exists(category_path):
            os.makedirs(category_path, exist_ok=True)
        
        # Save file
        file_path = os.path.join(category_path, filename)
        with open(file_path, 'wb') as f:
            f.write(compressed_data)
        
        # Return relative path for storage
        relative_path = f"/{category}/{filename}"
        
        return {'success': True, 'path': relative_path, 'filename': filename}
        
    except Exception as e:
        print(f"Upload error: {e}")
        return {'success': False, 'error': str(e)}

def delete_upload(file_path):
    """Delete an uploaded file"""
    try:
        full_path = os.path.join(UPLOAD_FOLDER, file_path.lstrip('/'))
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
    except Exception as e:
        print(f"Delete error: {e}")
    return False
