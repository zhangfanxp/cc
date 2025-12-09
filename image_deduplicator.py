import gradio as gr
import zipfile
import base64
import os
import mysql.connector
import tempfile
import shutil
import datetime
import uuid

# --- Database and Folder Configuration ---
DB_CONFIG = {
    'user': 'root',
    'password': 'Abs)*m12d31',
    'host': '127.0.0.1',
    'database': 'cc'
}

WORK_DIR = os.getcwd()
INPUT_FOLDER = os.path.join(WORK_DIR, 'input')
os.makedirs(INPUT_FOLDER, exist_ok=True)

# 使用系统临时目录，避免权限问题
TEMP_ROOT = os.path.join(tempfile.gettempdir(), "image_deduplicator_temp")
os.makedirs(TEMP_ROOT, exist_ok=True)

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        raise ConnectionError(f"数据库连接失败: {err}")

def is_image_duplicate(image_path, cursor):
    try:
        with open(image_path, "rb") as f:
            base64_encoded = base64.b64encode(f.read()).decode("utf-8")

        query = "SELECT filename FROM images WHERE base64_image = %s LIMIT 1"
        cursor.execute(query, (base64_encoded,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"检查图片出错: {e}")
        return None

def process_zip_file(zip_file, progress=gr.Progress(track_tqdm=True)):
    if not zip_file:
        return "请上传一个ZIP文件。", [], None

    # 每次运行创建独立 temp 子目录
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    TEMP_FOLDER = os.path.join(TEMP_ROOT, run_id)
    os.makedirs(TEMP_FOLDER, exist_ok=True)

    duplicate_files = []
    new_files_info = []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)

        with zipfile.ZipFile(zip_file.name, "r") as zip_ref:
            file_list = [
                f for f in zip_ref.infolist()
                if not f.is_dir()
                and not f.filename.startswith("__MACOSX")
                and not os.path.basename(f.filename).startswith("._")
                and os.path.basename(f.filename) != ".DS_Store"
            ]

            for file in progress.tqdm(file_list, desc="解压与查重中"):
                # 强制 UTF-8 解码 ZIP 内文件名
                try:
                    original_path = file.filename.encode("cp437").decode("utf-8")
                except:
                    # 如果解码失败则忽略错误
                    original_path = os.path.basename(file.filename)

                file.filename = os.path.basename(original_path)
                if not file.filename:
                    continue

                extract_path = os.path.join(TEMP_FOLDER, file.filename)
                zip_ref.extract(file, path=TEMP_FOLDER)

                db_filename = is_image_duplicate(extract_path, cursor)
                if db_filename:
                    duplicate_files.append(
                        f"{original_path} (重复, 数据库文件名: {db_filename})"
                    )
                    os.remove(extract_path)
                else:
                    new_files_info.append(file.filename)

        result_message = ""
        if duplicate_files:
            result_message += "发现重复图片：\n" + "\n".join(duplicate_files) + "\n\n"
        if new_files_info:
            result_message += f"发现 {len(new_files_info)} 张新图片可供操作: {new_files_info}"
        if not duplicate_files and not new_files_info:
            result_message = "没有新图片或全是重复图片。"

        # 返回状态包括 TEMP_FOLDER，用于后续入库和打包
        return result_message, (new_files_info, TEMP_FOLDER), None

    except Exception as e:
        return f"发生错误: {e}", [], None

def store_new_images(state):
    if not state:
        return "请先执行查重。"

    new_files_list, TEMP_FOLDER = state
    if not new_files_list:
        return "没有可供入库的新图片。"

    stored = 0
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for filename in new_files_list:
            temp_path = os.path.join(TEMP_FOLDER, filename)
            if not os.path.exists(temp_path):
                continue

            dest = os.path.join(INPUT_FOLDER, filename)
            shutil.copy2(temp_path, dest)

            with open(dest, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            cursor.execute("SELECT id FROM images WHERE base64_image = %s LIMIT 1", (b64,))
            if cursor.fetchone():
                continue

            cursor.execute(
                "INSERT INTO images (filename, base64_image) VALUES (%s, %s)",
                (filename, b64)
            )
            stored += 1

        conn.commit()
        return f"成功入库 {stored} 张图片。"

    except Exception as e:
        return f"入库时发生错误: {e}"

    finally:
        if conn:
            conn.close()

def create_new_images_zip(state):
    if not state:
        gr.Warning("请先查重")
        return None

    new_files_list, TEMP_FOLDER = state
    if not new_files_list:
        gr.Warning("没有新图片可供打包")
        return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    zip_path = os.path.join(tempfile.gettempdir(), f"{timestamp}.zip")

    try:
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for filename in new_files_list:
                fp = os.path.join(TEMP_FOLDER, filename)
                if os.path.exists(fp):
                    zipf.write(fp, arcname=filename)

        gr.Info(f"已生成 ZIP 包 {timestamp}.zip")
        return zip_path

    except Exception as e:
        gr.Warning(f"打包发生错误: {e}")
        return None

# --- Gradio interface ---
with gr.Blocks(title="图片查重工具") as iface:
    shared_state = gr.State([])

    gr.Markdown("## 图片查重与管理")
    zip_upload = gr.File(label="上传ZIP文件")
    check_button = gr.Button("1. 查重")
    store_button = gr.Button("2. 新照片入库")
    download_button = gr.Button("2. 下载新图片包")
    result_output = gr.Textbox(label="查重结果", lines=8)
    file_download = gr.File(label="下载区域")

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
    download_button.click(
        fn=create_new_images_zip,
        inputs=shared_state,
        outputs=file_download
    )

if __name__ == "__main__":
    iface.launch(server_name="0.0.0.0", server_port=7860)
