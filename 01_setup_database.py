
import mysql.connector
from mysql.connector import errorcode

# --- Database Configuration ---
# IMPORTANT: Connect without specifying a database initially
DB_CONFIG = {
    'user': 'root',
    'password': 'Abs)*m12d31',
    'host': '127.0.0.1'
}

DB_NAME = 'cc'

TABLES = {}
TABLES['images'] = (
    "CREATE TABLE `images` ("
    "  `id` int(11) NOT NULL AUTO_INCREMENT,"
    "  `filename` varchar(255) NOT NULL,"
    "  `base64_image` LONGTEXT NOT NULL,"
    "  PRIMARY KEY (`id`)"
    ") ENGINE=InnoDB")

def setup_database():
    """Connects to MySQL, creates the database and the images table."""
    cnx = None
    cursor = None
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        
        # Create database
        try:
            cursor.execute(f"CREATE DATABASE {DB_NAME} DEFAULT CHARACTER SET 'utf8mb4'")
            print(f"数据库 '{DB_NAME}' 创建成功。")
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_DB_CREATE_EXISTS:
                print(f"数据库 '{DB_NAME}' 已存在。")
            else:
                raise err
        
        cnx.database = DB_NAME
        
        # Create table
        for table_name in TABLES:
            table_description = TABLES[table_name]
            try:
                print(f"正在创建表 '{table_name}'... ", end='')
                cursor.execute(table_description)
                print("成功。")
            except mysql.connector.Error as err:
                if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                    print("已存在。")
                else:
                    print(err.msg)

    except mysql.connector.Error as err:
        print(f"数据库连接或设置失败: {err}")
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

if __name__ == "__main__":
    setup_database()
