# -*- coding: utf-8 -*-
# @Time    : 2017/1/21 11:27
# @Author  : sbybfai
# @Site    : 
# @File    : coroweb
# @Software: PyCharm
import os
from urllib import parse
from apis import APIError
from aiohttp import web

import functools
import asyncio
import inspect
import logging

logging.basicConfig(level=logging.INFO)


def get(path):
	"""Define decorator @get('path')"""

	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)

		wrapper.__method__ = 'GET'
		wrapper.__route__ = path
		return wrapper

	return decorator


def post(path):
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)

		wrapper.__method__ = "POST"
		wrapper.__route__ = path
		return wrapper

	return decorator


def get_required_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)


def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)


def has_named_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True


def has_var_kw_arg(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True


def has_request_arg(fn):
	sig = inspect.signature(fn)
	params = sig.pa下rameters
	found = False
	for name, param in params.items():
		if name == 'request':
			found = True
			continue
		if found and (
							param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
			raise ValueError(
				'request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
	return found

#
# class RequestHandler(object):
# 	def __init__(self, app, fn):
# 		self._app = app
# 		self._func = fn
# 		self._has_request_arg = has_request_arg(fn)
# 		self._has_var_kw_arg = has_var_kw_arg(fn)
# 		self._has_named_kw_args = has_named_kw_args(fn)
# 		self._named_kw_args = get_named_kw_args(fn)
# 		self._required_kw_args = get_required_kw_args(fn)
#
# 	async def __call__(self, request):
# 		kw = None
# 		if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
# 			if request.method == 'POST':
# 				if not request.content_type:
# 					return web.HTTPBadRequest('Missing Content-Type.')
# 				ct = request.content_type.lower()
# 				if ct.startswith('application/json'):
# 					params = await request.json()
# 					if not isinstance(params, dict):
# 						return web.HTTPBadRequest('JSON body must be object.')
# 					kw = params
# 				elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
# 					params = await request.post()
# 					kw = dict(**params)
# 				else:
# 					return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
# 			if request.method == 'GET':
# 				qs = request.query_string
# 				if qs:
# 					kw = dict()
# 					for k, v in parse.parse_qs(qs, True).items():
# 						kw[k] = v[0]
# 		if kw is None:
# 			kw = dict(**request.match_info)
# 		else:
# 			if not self._has_var_kw_arg and self._named_kw_args:
# 				# remove all unamed kw:
# 				copy = dict()
# 				for name in self._named_kw_args:
# 					if name in kw:
# 						copy[name] = kw[name]
# 				kw = copy
# 			# check named arg:
# 			for k, v in request.match_info.items():
# 				if k in kw:
# 					logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
# 				kw[k] = v
# 		if self._has_request_arg:
# 			kw['request'] = request
# 		# check required kw:
# 		if self._required_kw_args:
# 			for name in self._required_kw_args:
# 				if not name in kw:
# 					return web.HTTPBadRequest('Missing argument: %s' % name)
# 		logging.info('call with args: %s' % str(kw))
# 		try:
# 			r = await self._func(**kw)
# 			return r
# 		except APIError as e:
# 			return dict(error=e.error, data=e.data, message=e.message)


# RequestHandler目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，
# URL函数不一定是一个coroutine，因此我们用RequestHandler()来封装一个URL处理函数。
# 调用URL函数，然后把结果转换为web.Response对象，这样，就完全符合aiohttp框架的要求：就完全符合aiohttp框架的要求
class RequestHandler(object):  # 初始化一个请求处理类

	def __init__(self, func):
		self._func = asyncio.coroutine(func)

	async def __call__(self, request):  # 任何类，只需要定义一个__call__()方法，就可以直接对实例进行调用
		# 获取函数的参数表
		required_args = inspect.signature(self._func).parameters
		logging.info('required args: %s' % required_args)

		# 获取从GET或POST传进来的参数值，如果函数参数表有这参数名就加入
		kw = {arg: value for arg, value in request.__data__.items() if arg in required_args}

		# 获取match_info的参数值，例如@get('/blog/{id}')之类的参数值
		kw.update(request.match_info)

		# 如果有request参数的话也加入
		if 'request' in required_args:
			kw['request'] = request

		# 检查参数表中有没参数缺失
		for key, arg in required_args.items():
			# request参数不能为可变长参数
			if key == 'request' and arg.kind in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD):
				return web.HTTPBadRequest(text='request parameter cannot be the var argument.')
			# 如果参数类型不是变长列表和变长字典，变长参数是可缺省的
			if arg.kind not in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD):
				# 如果还是没有默认值，而且还没有传值的话就报错
				if arg.default == arg.empty and arg.name not in kw:
					return web.HTTPBadRequest(text='Missing argument: %s' % arg.name)

		logging.info('call with args: %s' % kw)
		try:
			return await self._func(**kw)
		except APIError as e:
			return dict(error=e.error, data=e.data, message=e.message)


def add_static(app):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	app.router.add_static('/static/', path)
	logging.info('add static %s => %s' % ('/static/', path))


def add_route(app, fn):
	method = getattr(fn, '__method__', None)
	path = getattr(fn, '__route__', None)
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s.' % str(fn))
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info(
		'add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
	app.router.add_route(method, path, RequestHandler(fn))


def add_routes(app, module_name):
	n = module_name.rfind('.')
	if n == (-1):
		mod = __import__(module_name, globals(), locals())
	else:
		name = module_name[n + 1:]
		mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
	for attr in dir(mod):
		if attr.startswith('_'):
			continue
		fn = getattr(mod, attr)
		if callable(fn) and hasattr(fn, '__method__') and hasattr(fn, '__route__'):
			add_route(app, fn)
