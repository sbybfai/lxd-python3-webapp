# -*- coding: utf-8 -*-
# @Time    : 2017/1/15 21:25
# @Author  : sbybfai
# @Site    : 
# @File    : app.py
# @Software: PyCharm

from datetime import datetime
from aiohttp import web

import logging
import asyncio, os, json, time

logging.basicConfig(level=logging.INFO)


def index(request):
	return web.Response(body=b'<h1>Hi,my first web!</h1>', content_type="text/html")


async def init(loop):
	app = web.Application(loop=loop)
	app.router.add_route('GET', '/', index)
	ip = '127.0.0.1'
	port = "9000"
	srv = await loop.create_server(app.make_handler(), ip, port)
	logging.info('server started at http://%s' % ip)
	return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
