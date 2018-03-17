# -*- coding: utf-8 -*-
# @Time    : 2017/1/21 12:18
# @Author  : sbybfai
# @Site    : 
# @File    : handlers.py
# @Software: PyCharm
import markdown2 as markdown2

from coroweb import get, post
from models import User, Comment, Blog, next_id
from config import configs
from apis import *
from aiohttp import web

import re, time, json, logging, hashlib, base64, asyncio

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


def user2cookie(user, max_age):
	"""Generate cookie str by user."""
	# build cookie string by: id-expires-sha1
	expires = str(int(time.time() + max_age))
	s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)


def text2html(text):
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
				filter(lambda s: s.strip() != '', text.split('\n')))
	return ''.join(lines)


def get_page_index(page_str):
	p = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p


def check_admin(request):
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissionError()


async def cookie2user(cookie_str):
	"""Parse cookie and load user if cookie is valid."""

	if not cookie_str:
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid, expires, sha1 = L
		if int(expires) < time.time():
			return None
		user = await User.find(uid)
		if user is None:
			return None
		s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('invalid sha1')
			return None
		user.passwd = '******'
		return user
	except Exception as e:
		logging.exception(e)
		return None


@get('/')
async def index(*, page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	page = Page(num, page_index)
	if num == 0:
		blogs = []
	else:
		blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
	return {
		'__template__': 'blogs.html',
		'page': page,
		'blogs': blogs
	}


@get('/blog/category/{category}')
async def get_blog_by_category(*, category, page='1'):
	blogs = []
	if category in g_Category2ID:
		page_index = get_page_index(page)
		lstID = g_Category2ID[category]
		page = Page(len(lstID), page_index)
		lstID = lstID[page.offset: page.limit]
		blogs = await Blog.findAll('id in %s', [tuple(lstID)], orderBy='created_at desc')
	return {
		'__template__': 'blogs.html',
		'page': page,
		'blogs': blogs
	}


@get('/blog/tag/{tag}')
async def get_blog_by_tag(*, tag, page="1"):
	blogs = []
	print("=====", tag, g_Tag2ID)
	if tag in g_Tag2ID:
		page_index = get_page_index(page)
		lstID = g_Tag2ID[tag]
		page = Page(len(lstID), page_index)
		lstID = lstID[page.offset: page.limit]
		blogs = await Blog.findAll('id in %s', [tuple(lstID)], orderBy='created_at desc')
	return {
		'__template__': 'blogs.html',
		'page': page,
		'blogs': blogs
	}


@get('/register')
def register():
	return {
		'__template__': 'register.html'
	}


@get('/signin')
def signin():
	return {
		'__template__': 'signin.html'
	}


@post('/api/authenticate')
async def authenticate(*, email, passwd):
	if not email:
		raise APIValueError('email', 'Invalid email.')
	if not passwd:
		raise APIValueError('passwd', 'Invalid password.')
	users = await User.findAll('email=?', [email])
	if len(users) == 0:
		raise APIValueError('email', 'Email not exist.')
	user = users[0]
	# check passwd:
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd', 'Invalid password.')
	# authenticate ok, set cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r


@get('/signout')
def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
	logging.info('user signed out.')
	return r


@get('/manage/')
def manage():
	return 'redirect:/manage/comments'


@get('/manage/comments')
def manage_comments(*, page='1'):
	return {
		'__template__': 'manage_comments.html',
		'page_index': get_page_index(page)
	}


@get('/manage/blogs')
def manage_blogs(*, page='1'):
	return {
		'__template__': 'manage_blogs.html',
		'page_index': get_page_index(page)
	}


@get('/manage/blogs/create')
def manage_create_blog():
	return {
		'__template__': 'manage_blog_edit.html',
		'id': '',
		'action': '/api/blogs'
	}


@get('/manage/blogs/edit')
def manage_edit_blog(request, id):
	check_admin(request)
	return {
		'__template__': 'manage_blog_edit.html',
		'id': id,
		'action': '/api/blogs/%s' % id
	}


@get('/manage/users')
def manage_users(*, page='1'):
	return {
		'__template__': 'manage_users.html',
		'page_index': get_page_index(page)
	}


@get('/api/comments')
async def api_comments(*, page='1'):
	page_index = get_page_index(page)
	num = await Comment.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, comments=())
	comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, comments=comments)


@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
	user = request.__user__
	if user is None:
		raise APIPermissionError('Please signin first.')
	if not content or not content.strip():
		raise APIValueError('content')
	blog = await Blog.find(id)
	if blog is None:
		raise APIResourceNotFoundError('Blog')
	comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image,
					  content=content.strip())
	await comment.save()
	return comment


@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, category, tags, summary, content):
	check_admin(request)
	blog = await Blog.find(id)
	if not blog:
		raise APIValueError('err', 'can not find the blog.')
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty.')
	sOldCategory = blog.category
	sOldTags = blog.tags
	blog.name = name.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	blog.category = category.strip()  # 两端加:,方便索引
	blog.tags = tags.strip()
	blog.update_time = time.time()
	await blog.update()
	if sOldCategory != category or sOldTags != tags:
		await InitCache(None)
	return blog


@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
	check_admin(request)
	c = await Comment.find(id)
	if c is None:
		raise APIResourceNotFoundError('Comment')
	await c.remove()
	return dict(id=id)


@post('/api/users')
async def api_register_user(*, email, name, passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=? or name=?', [email, name])
	for user in users:
		if user.email == email:
			raise APIError('register:failed', 'email', 'Email is already in use.')
		else:
			raise APIError('register:failed', 'name', 'name is already in use.')
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid, passwd)
	user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
				image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
	await user.save()
	# make session cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r


@get('/api/users')
async def api_get_users():
	users = await User.findAll(orderBy='created_at desc')
	for u in users:
		u.passwd = '******'
	return dict(users=users)


@get('/blog/{id}')
async def get_blog(id, request):
	blog = await Blog.find(id)
	if not blog:
		raise APIPermissionError()
	global g_ClickCache
	global g_ClickTime
	blog_id = blog.id
	ip_address = request.remote
	if not (blog_id, ip_address) in g_ClickTime:
		g_ClickTime[(blog_id, ip_address)] = time.time()
		if not blog_id in g_ClickCache:
			g_ClickCache[blog_id] = blog.click_cnt
		g_ClickCache[blog_id] += 1

	blog.click_cnt = g_ClickCache.get(blog_id, blog.click_cnt)
	comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)
	return {
		'__template__': 'blog.html',
		'blog': blog,
		'comments': comments,
	}


@get('/api/blogs/{id}')
async def api_get_blog(*, id):
	return await Blog.find(id)


@post('/api/blogs')
async def api_create_blog(request, *, name, category, tags, summary, content):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty.')
	blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,
				name=name.strip(), category=category.strip(), tags=tags.strip(), summary=summary.strip(),
				content=content.strip())
	await blog.save()
	await InitCache(None)
	return blog


@get('/api/blogs')
async def api_blogs(*, page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, blogs=())
	blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, blogs=blogs)


@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
	check_admin(request)
	blog = await Blog.find(id)
	await blog.remove()
	await InitCache(None)
	return dict(id=id)


if not hasattr(globals(), 'g_Tag2ID'):
	global g_Tag2ID
	global g_Category2ID
	global g_ClickCache
	global g_ClickTime
	global g_CategoryList
	g_Tag2ID = {}  # {tag:[blog_id1, blog_id2]}
	g_Category2ID = {}  # {category:[blog_id1, blog_id2]}
	g_ClickCache = {}  # {blog_id: iCnt}
	g_ClickTime = {}  # {(blog_id, ip): iTime}
	g_CategoryList = []  # [category1, category2]


# 分类和标签经常要用到，所以把他缓存起来
# 每次博客发生修改时，重新初始化一次
# 因为修改频率低，博客数量不多的情况下，这种做法可以接受
async def InitCache(app):
	blogs = await Blog.findAll()
	global tag_Tag2ID
	global g_Category2ID
	global g_CategoryList
	tag_Tag2ID = {}
	g_Category2ID = {}
	g_CategoryList = []
	lstTmpCategory = []
	for blog in blogs:
		sID = blog.id
		sTag = blog.tags
		sCateGory = blog.category

		for tag in sTag.split(":"):
			if not len(tag):
				continue
			if not tag in g_Tag2ID:
				g_Tag2ID[tag] = []
			g_Tag2ID[tag].append(sID)

		for category in sCateGory.split(":"):
			if not len(category):
				continue
			if not category in g_Category2ID:
				g_Category2ID[category] = []
			g_Category2ID[category].append(sID)

		if not sCateGory in g_CategoryList:
			lstCategory = sCateGory.split(":")
			for i in range(len(lstCategory)):
				category = ":".join(lstCategory[:i + 1])
				if not category in lstTmpCategory:
					lstTmpCategory.append(category)

	for sTag in g_Tag2ID.keys():
		g_Tag2ID[sTag].sort(reverse=True)

	for category in g_Category2ID.keys():
		g_Category2ID[category].sort(reverse=True)

	lstTmpCategory.sort()
	for category in lstTmpCategory:
		lstCategory = category.split(":")
		sEnd = lstCategory[-1]
		g_CategoryList.append((sEnd, len(lstCategory)))

	logging.info("InitCache Done %s %s" % (g_Tag2ID, g_Category2ID))


# 点击缓存每60s检查一次，并清理超过10min的ip点击缓存，并保存点击数
async def ClearClickCache():
	iNowtime = time.time()
	global g_ClickCache
	global g_ClickTime
	for (blog_id, ip), iTime in g_ClickTime.items():
		if iTime - iNowtime > 600:
			del g_ClickTime[(blog_id, ip)]

	lstID = g_ClickCache.keys()
	if lstID:
		blogs = await Blog.findAll('id in %s', [tuple(lstID)])
		for blog in blogs:
			blog.click_cnt = g_ClickCache[blog.id]
			del g_ClickCache[blog.id]
			await blog.update()

	await asyncio.sleep(60)
	loop = asyncio.get_event_loop()
	loop.create_task(ClearClickCache())
