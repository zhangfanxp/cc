
import os
import base64
import mysql.connector
from tqdm import tqdm

# --- Database and Folder Configuration ---
DB_CONFIG = {
    'user': 'root',
    'password': 'Abs)*m12d31',
    'host': '127.0.0.1',
    'database': 'cc'
}

WORK_DIR = os.getcwd()
INPUT_FOLDER = os.path.join(WORK_DIR, 'input')

def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        raise ConnectionError(f"数据库连接失败: {err}")

def populate_initial_data():
    """Reads images from the INPUT_FOLDER, base64 encodes them, and inserts them into the 'images' table."""
    if not os.path.isdir(INPUT_FOLDER):
        print(f"错误: input 文件夹不存在于 '{WORK_DIR}'")
        return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        
        all_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(image_extensions)]
        inserted_count = 0

        print("开始将 input 文件夹中的图片写入数据库...")
        for filename in tqdm(all_files, desc="处理图片中"):
            file_path = os.path.join(INPUT_FOLDER, filename)
            try:
                with open(file_path, "rb") as f:
                    image_bytes = f.read()
                    base64_encoded = base64.b64encode(image_bytes).decode('utf-8')

                # Check if this exact image is already in the DB
                cursor.execute("SELECT id FROM images WHERE base64_image = %s LIMIT 1", (base64_encoded,))
                if cursor.fetchone() is None:
                    insert_query = "INSERT INTO images (filename, base64_image) VALUES (%s, %s)"
                    cursor.execute(insert_query, (filename, base64_encoded))
                    inserted_count += 1

            except Exception as e:
                print(f"处理文件 {filename} 时出错: {e}")

        conn.commit()
        print(f"\n操作完成。成功插入 {inserted_count} 张新图片到 'images' 表。")

    except (ConnectionError, mysql.connector.Error) as e:
        print(e)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    populate_initial_data()
