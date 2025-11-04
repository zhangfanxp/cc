项目起源于同事,说经常要提报一些图片资料,长期提交图片材料量大以后,很难人工区分图片是否曾经提交过,因此,使用Gemini CLI设计了一整套的系统,从数据库、表创建到倒入初始化图片,都可以通过脚本执行.

<img width="1534" height="1023" alt="ScreenShot_2025-11-04_141400_590" src="https://github.com/user-attachments/assets/61d0ca5c-aa76-4924-b851-5a76f4de4876" />

***********************************************************************************************

1、安装mysql

sudo apt install mysql-server

2、进行安全配置

sudo mysql_secure_installation

3、查看mysql状态

sudo systemctl status mysql

4、设置root密码(root密码要与01,02两个创建数据库表脚本中的一致)

sudo mysql

ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'your_new_password';

FLUSH PRIVILEGES;

EXIT;

5、使用root新密码登陆

mysql -u root -p

6、安装uv虚拟环境

sudo apt install nodejs npm -y


uv --version

检查uv的版本信息


7、拉取项目文件

git clone https://github.com/zhangfanxp/cc.git && cd cc

8、创建并激活虚拟环境

uv venv && source .venv/bin/activate

9、安装依赖库

uv pip install -r requirements.txt

10、执行脚本创建数据库表

python 01_setup_database.py

python 02_populate_data.py

11、运行webui的启动服务程序

python image_deduplicator.py

12、上传zip压缩包,查重

-------------------------------------------------

设置Ubuntu系统开机后自动启动服务:


a、创建自启动文件(image-deduplicator.service)

vi ~/image-deduplicator.service

b、写入下面的代码(根据ubuntu实际用户名修改下面三处your_username)

[Unit]
Description=Image Deduplicator Service

After=network.target

[Service]
User=your_username

WorkingDirectory=/home/your_username/env/cc

ExecStart=/home/your_username/env/cc/.venv/bin/python image_deduplicator.py

Restart=on-failure

[Install]
WantedBy=multi-user.target

c、保存并退出

:wq

d、把文件移入系统目录并重新加载systemd配置

sudo mv ~/image-deduplicator.service /etc/systemd/system/

sudo systemctl daemon-reload

e、设置为开机后自启动服务

sudo systemctl enable image-deduplicator.service

---------------------------------------------

固定IP地址,建议在路由器中设置,本地设置容易产生IP冲突!
