# # -*- coding: utf-8 -*-
# # @Time    : 2017/1/25 17:37
# # @Author  : sbybfai
# # @Site    :
# # @File    : fabfile
# # @Software: PyCharm
#
# import os, re
# from datetime import datetime
#
# from datetime import datetime
#
# # 导入Fabric API:
# from fabric.api import *
#
# # 服务器登录用户名:
# env.user = 'root'
# # sudo用户为root:
# env.sudo_user = 'root'
# # 服务器地址，可以有多个，依次部署:
# env.hosts = ['192.168.1.197']
#
# # 服务器MySQL用户名和口令:
# db_user = 'root'
# db_password = '861511'
#
# _TAR_FILE = 'dist-awesome.tar.gz'
#
#
# def build():
# 	includes = ['static', 'templates', 'transwarp', 'favicon.ico', '*.py']
# 	excludes = ['test', '.*', '*.pyc', '*.pyo']
# 	local('rm -f dist/%s' % _TAR_FILE)
# 	with lcd(os.path.join(os.path.abspath('.'), 'www')):
# 		cmd = ['tar', '--dereference', '-czvf', '../dist/%s' % _TAR_FILE]
# 		cmd.extend(['--exclude=\'%s\'' % ex for ex in excludes])
# 		cmd.extend(includes)
# 		local(' '.join(cmd))

from fabric.api import run

def host_type():
    run('uname -s')
