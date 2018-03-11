# -*- coding: utf-8 -*-
# @Time    : 2017/1/15 21:25
# @Author  : sbybfai
# @Site    : 
# @File    : app.py
# @Software: PyCharm

from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from coroweb import add_routes, add_static
from config import configs
from handlers import COOKIE_NAME, cookie2user
from urllib import parse

import orm_my
import logging
import asyncio, os, json
import handlers

logging.basicConfig(level=logging.INFO)


def init_jinja2(app, **kw):
	logging.info('init jinja2...')
	options = dict(
		autoescape=kw.get('autoescape', True),
		block_start_string=kw.get('block_start_string', '{%'),
		block_end_string=kw.get('block_end_string', '%}'),
		variable_start_string=kw.get('variable_start_string', '{{'),
		variable_end_string=kw.get('variable_end_string', '}}'),
		auto_reload=kw.get('auto_reload', True)
	)
	path = kw.get('path', None)
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
	logging.info('set jinja2 template path: %s' % path)
	env = Environment(loader=FileSystemLoader(path), **options)
	filters = kw.get('filters', None)
	if filters is not None:
		for name, f in filters.items():
			env.filters[name] = f
	app['__templating__'] = env

@web.middleware
async def logger_factory(request, handler):
	logging.info('Request: %s %s' % (request.method, request.path))
	return await handler(request)

@web.middleware
async def data_factory(request, handler):
	request.__data__ = {}
	if request.method == 'POST':
		if request.content_type.startswith('application/json'):
			request.__data__ = await request.json()
			logging.info('POST request json: %s' % str(request.__data__))
		elif request.content_type.startswith('application/x-www-form-urlencoded'):
			request.__data__ = await request.post()
			logging.info('POST request form: %s' % str(request.__data__))
	elif request.method == "GET":
		request.__data__ = {}
		qs = request.query_string
		for k, v in parse.parse_qs(qs, True).items():
			request.__data__[k] = v[0]
		logging.info('GET request form: %s' % str(request.__data__))

	return await handler(request)

@web.middleware
async def response_factory(request, handler):
	logging.info('Response handler...')
	r = await handler(request)
	if isinstance(r, web.StreamResponse):
		return r
	if isinstance(r, bytes):
		resp = web.Response(body=r)
		resp.content_type = 'application/octet-stream'
		return resp
	if isinstance(r, str):
		if r.startswith('redirect:'):
			return web.HTTPFound(r[9:])
		resp = web.Response(body=r.encode('utf-8'))
		resp.content_type = 'text/html;charset=utf-8'
		return resp
	if isinstance(r, dict):
		template = r.get('__template__')
		if template is None:
			resp = web.Response(
				body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
			resp.content_type = 'application/json;charset=utf-8'
			return resp
		else:
			r['__user__'] = request.__user__
			app = request.app()
			resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8'
			return resp
	if isinstance(r, int) and 100 <= r < 600:
		return web.Response(r)
	if isinstance(r, tuple) and len(r) == 2:
		t, m = r
		if isinstance(t, int) and 100 <= t < 600:
			return web.Response(t, str(m))
	# default:
	resp = web.Response(body=str(r).encode('utf-8'))
	resp.content_type = 'text/plain;charset=utf-8'
	return resp

@web.middleware
async def auth_factory(request, handler):
	logging.info('check user: %s %s' % (request.method, request.path))
	request.__user__ = None
	cookie_str = request.cookies.get(COOKIE_NAME)
	if cookie_str:
		user = await cookie2user(cookie_str)
		if user:
			logging.info('set current user: %s' % user.email)
			request.__user__ = user
	if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
		return web.HTTPFound('/signin')
	return await handler(request)


def datetime_filter(t):
	dt = datetime.fromtimestamp(t)
	return u'%s-%s-%s %s:%s:%s' % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

def tags_filter(category):
	tag_link = '<a href="/blog/tag/%s">%s</a>'
	tag_list = category.split(":")
	return ", ".join([tag_link % (sText, sText) for sText in tag_list])

def category_filter(category):
	category_link = '<a href="/blog/category/%s">%s</a>'
	category_list = category.split(":")
	return "/".join([category_link % (sText, sText) for sText in category_list])

dJinjaFilters = {"datetime": datetime_filter, "tag": tags_filter, "category": category_filter}


async def init(loop):
	app = web.Application(loop=loop, middlewares=[
		logger_factory, auth_factory, response_factory, data_factory
	])
	init_jinja2(app, filters=dJinjaFilters)
	add_routes(app, 'handlers')
	add_static(app)
	app["db_config"] = configs.db
	app.on_startup.append(orm_my.InitDB)
	app.on_startup.append(handlers.InitCache)
	app.on_cleanup.append(orm_my.CloseDB)
	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	await app.startup()
	logging.info('server started at http://127.0.0.1:9000...')
	return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
