# OFC Auto Checkin System

一个用于自动执行 OFC (Onefootball) 每日签到的 Python 脚本。

## 功能特点

- 支持多账户管理
- 多线程并发签到
- 支持代理配置

## 1. 安装

## 2. 创建并激活虚拟环境(推荐):

```bash
python -m venv venv
source venv/Scripts/activate
```

## 3. 安装依赖:

```bash
pip install -r requirements.txt
```

## 配置

在程序目录下创建以下配置文件:

1. `proxy.txt`: 代理服务器列表

```text
http://x.x.x.x:xxxxx
```

2. 配置token.txt和配置refresh_token.txt

在浏览器的开发者工具中找到priv:token，复制到token.txt中，找到priv:refresh_token，复制到refresh_token.txt中。

## 运行

python ofc.py

