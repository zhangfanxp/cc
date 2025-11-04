import gradio as gr
import zipfile
import base64
import os
import mysql.connector
import tempfile
import shutil

# --- Database and Folder Configuration ---
DB_CONFIG = {
    'user': 'root',
    'password': 'Abs)*m12d31',
    'host': '127.0.0.1',
    'database': 'cc'
}

# Use a local, visible temp folder as suggested
WORK_DIR = os.getcwd()
INPUT_FOLDER = os.path.join(WORK_DIR, 'input')
TEMP_FOLDER = os.path.join(WORK_DIR, 'temp')

def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        raise ConnectionError(f"数据库连接失败: {err}")

def is_image_duplicate(image_path, cursor):
    """Checks if an image is a duplicate by comparing its base64 representation."""
    try:
        with open(image_path, "rb") as f:
            base64_encoded = base64.b64encode(f.read()).decode('utf-8')
        query = "SELECT filename FROM images WHERE base64_image = %s LIMIT 1"
        cursor.execute(query, (base64_encoded,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"检查图片 {os.path.basename(image_path)} 时出错: {e}")
        return None

def process_zip_file(zip_file, progress=gr.Progress(track_tqdm=True)):
    """Cleans up, extracts the ZIP to a local ./temp folder, and checks for duplicates."""
    if not zip_file:
        return "请上传一个ZIP文件。", [], None

    # Clean up previous temp folder and create a new one
    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER)
    os.makedirs(TEMP_FOLDER)

    duplicate_files = []
    new_files_info = []
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)

        with zipfile.ZipFile(zip_file.name, 'r') as zip_ref:
            file_list = [f for f in zip_ref.infolist() if not f.is_dir() and not f.filename.startswith('__MACOSX') and not os.path.basename(f.filename).startswith('._')]
            
            for file in progress.tqdm(file_list, desc="解压与查重中"):
                # Extracting to a flat structure in TEMP_FOLDER
                # This avoids issues with nested folders inside the zip
                file.filename = os.path.basename(file.filename)
                if not file.filename: continue

                zip_ref.extract(file, path=TEMP_FOLDER)
                image_path = os.path.join(TEMP_FOLDER, file.filename)

                db_filename = is_image_duplicate(image_path, cursor)

                if db_filename:
                    duplicate_files.append(f"{file.filename} (数据库中已存在, 文件名: {db_filename})")
                    os.remove(image_path) # Clean up duplicate file right away
                else:
                    new_files_info.append(file.filename)

        result_message = ""
        if duplicate_files:
            result_message += "发现重复图片:\n" + "\n".join(duplicate_files) + "\n\n"
        if new_files_info:
            result_message += f"发现 {len(new_files_info)} 张新图片可供操作: {new_files_info}"
        if not duplicate_files and not new_files_info:
            result_message = "ZIP文件中未找到有效图片，或所有图片均已存在于数据库中。"
        
        return result_message, new_files_info, None

    except Exception as e:
        return f"发生错误: {e}", [], None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def store_new_images(new_files_list):
    """Copies new images from ./temp to the input folder and adds them to the database."""
    if not new_files_list:
        return "没有可供入库的新图片。请先执行查重操作。"

    stored_count = 0
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for filename in new_files_list:
            temp_path = os.path.join(TEMP_FOLDER, filename)
            if not os.path.exists(temp_path):
                continue

            destination_path = os.path.join(INPUT_FOLDER, filename)
            shutil.copy2(temp_path, destination_path) # Use copy to preserve temp file
            
            with open(destination_path, "rb") as f:
                base64_encoded = base64.b64encode(f.read()).decode('utf-8')
            
            # Check if this image was somehow already added to prevent crash
            cursor.execute("SELECT id FROM images WHERE base64_image = %s LIMIT 1", (base64_encoded,))
            if cursor.fetchone():
                continue

            insert_query = "INSERT INTO images (filename, base64_image) VALUES (%s, %s)"
            cursor.execute(insert_query, (filename, base64_encoded))
            stored_count += 1

        conn.commit()
        return f"成功入库 {stored_count} 张新图片。"
    except Exception as e:
        return f"入库过程中发生错误: {e}"
    finally:
        if conn: conn.close()


import datetime

def create_new_images_zip(new_files_list):
    """Creates a new ZIP file from images in the ./temp folder with a timestamped name."""
    if not new_files_list:
        gr.Warning("没有新图片可供打包。")
        return None
    
    zip_path = None
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}.zip"
        
        # Create the file in the system's temp directory
        temp_dir = tempfile.gettempdir()
        zip_path = os.path.join(temp_dir, filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for filename in new_files_list:
                temp_path = os.path.join(TEMP_FOLDER, filename)
                if os.path.exists(temp_path):
                    zipf.write(temp_path, arcname=filename)
        
        gr.Info(f"已成功生成包含 {len(new_files_list)} 张新图片的ZIP包: {filename}")
        return zip_path
    except Exception as e:
        gr.Warning(f"创建ZIP包时发生错误: {e}")
        if zip_path and os.path.exists(zip_path): os.remove(zip_path)
        return None

# --- Gradio Interface with Blocks ---
with gr.Blocks(title="图片查重工具") as iface:
    gr.Markdown("## 图片查重与管理")
    gr.Markdown("上传ZIP包 -> 点击查重 -> 选择入库或打包下载新图片。")

    shared_state = gr.State([])

    with gr.Row():
        zip_upload = gr.File(label="上传ZIP文件")
    
    with gr.Row():
        check_button = gr.Button("1. 查重")
    
    result_output = gr.Textbox(label="查重结果", lines=8, interactive=False)

    with gr.Row():
        store_button = gr.Button("2. 新照片入库")
        download_zip_button = gr.Button("2. 下载新图片包")
    
    file_download = gr.File(label="下载区域", interactive=False)

    check_button.click(
        fn=process_zip_file,
        inputs=zip_upload,
        outputs=[result_output, shared_state, file_download]
    )

    store_button.click(
        fn=store_new_images,
        inputs=shared_state,
        outputs=result_output
    ) # .then() clause removed

    download_zip_button.click(
        fn=create_new_images_zip,
        inputs=shared_state,
        outputs=file_download
    )

if __name__ == "__main__":
    iface.launch(server_name="0.0.0.0",server_port=7860,share=False)