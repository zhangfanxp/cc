import gradio as gr
import zipfile
import base64
import os
import mysql.connector
import tempfile
import shutil
import datetime

# --- Database and Folder Configuration ---
DB_CONFIG = {
    'user': 'root',
    'password': 'Abs)*m12d31',
    'host': '127.0.0.1',
    'database': 'cc'
}

WORK_DIR = os.getcwd()
INPUT_FOLDER = os.path.join(WORK_DIR, 'input')
TEMP_FOLDER = os.path.join(tempfile.gettempdir(), 'cc_temp')  # ⭐ 使用系统临时目录
os.makedirs(INPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)


def get_db_connection():
    """Connect to MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        raise ConnectionError(f"数据库连接失败: {err}")


def is_image_duplicate(image_path, cursor):
    """Check duplicate by comparing base64."""
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


def safe_clear_temp_folder():
    """Safely clear TEMP_FOLDER without deleting the folder (avoid PermissionError)."""
    os.makedirs(TEMP_FOLDER, exist_ok=True)
    for root, dirs, files in os.walk(TEMP_FOLDER):
        for f in files:
            try:
                os.remove(os.path.join(root, f))
            except:
                pass
        for d in dirs:
            try:
                shutil.rmtree(os.path.join(root, d))
            except:
                pass


def decode_zip_filename(file):
    """Decode ZIP internal filename to support Chinese."""
    try:
        # 尝试 UTF-8 解码
        return file.filename.encode('cp437').decode('utf-8')
    except:
        # 如果失败，用 GBK 解码
        try:
            return file.filename.encode('cp437').decode('gbk')
        except:
            # 最后直接返回原始字符串
            return file.filename


def process_zip_file(zip_file, progress=gr.Progress(track_tqdm=True)):
    """Extract ZIP, check duplicates, show original ZIP paths (support Chinese)."""
    if not zip_file:
        return "请上传一个ZIP文件。", [], None

    safe_clear_temp_folder()
    duplicate_files = []
    new_files_info = []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)

        with zipfile.ZipFile(zip_file.name, 'r') as zip_ref:
            file_list = [
                f for f in zip_ref.infolist()
                if not f.is_dir()
                and not f.filename.startswith('__MACOSX')
                and not os.path.basename(f.filename).startswith('._')
            ]

            for file in progress.tqdm(file_list, desc="解压与查重中"):
                original_zip_path = decode_zip_filename(file)  # ⭐ 中文支持
                flat_name = os.path.basename(original_zip_path)
                if not flat_name:
                    continue

                # 手动 extract
                extracted_path = os.path.join(TEMP_FOLDER, flat_name)
                with zip_ref.open(file) as source, open(extracted_path, "wb") as target:
                    shutil.copyfileobj(source, target)

                db_filename = is_image_duplicate(extracted_path, cursor)
                if db_filename:
                    duplicate_files.append(
                        f"{flat_name} (ZIP内路径: {original_zip_path}, 数据库文件名: {db_filename})"
                    )
                    os.remove(extracted_path)
                else:
                    new_files_info.append(flat_name)

        # 输出结果
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
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def store_new_images(new_files_list):
    """Copy new images from temp to input folder and insert into DB."""
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
            shutil.copy2(temp_path, destination_path)

            with open(destination_path, "rb") as f:
                base64_encoded = base64.b64encode(f.read()).decode('utf-8')

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
        if conn:
            conn.close()


def create_new_images_zip(new_files_list):
    """Create a new ZIP containing new images."""
    if not new_files_list:
        gr.Warning("没有新图片可供打包。")
        return None

    zip_path = None
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}.zip"

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
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)
        return None


# --- Gradio Interface ---
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
    )

    download_zip_button.click(
        fn=create_new_images_zip,
        inputs=shared_state,
        outputs=file_download
    )

if __name__ == "__main__":
    iface.launch(server_name="0.0.0.0", server_port=7860, share=False)
