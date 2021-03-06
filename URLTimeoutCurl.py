#!/usr/bin/python
# Comics Grabber by Tom Parker <palfrey@tevp.net>
# http://tevp.net
#
# URLTimeoutCurl class
# Grabs URLs, but with a timeout to avoid locking on crapped-up sites.
#
# Released under the GPL Version 2 (http://www.gnu.org/copyleft/gpl.html)

import pycurl,re
from ._URLTimeoutCommon import *
from urllib.parse import urlencode

charsetPattern = re.compile("charset=(\S+)")

class URLTimeoutCurl(URLGetter):
	def body_callback(self, buf):
		self.contents += buf
		if hasattr(self, "write_callback"):
			self.write_callback(len(self.contents))

	def head_callback(self, buf):
		self.header = self.header + buf.decode('utf-8')

	def auth(self,user,password):
		self.user = user
		self.password = password

	def get(self,url, headers={}, ref=None, data=None, ignore_move=False, proxy=None):
		resp = handleurl(url)
		if resp!=None:
			return URLObject(url,None,resp.body,resp.msg.headers,data)

		self.contents = b""
		self.header = ""
		origurl = url
		c = pycurl.Curl()
		c.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_1_1)
		if self.debug:
			c.setopt(pycurl.VERBOSE, 1)
		if hasattr(self, "user"):
			c.setopt(c.HTTPAUTH,c.HTTPAUTH_BASIC)
			c.setopt(c.USERPWD,"%s:%s"%(self.user,self.password))
		if type(url) == str:
			c.setopt(c.URL, url.encode("utf-8"))
		else:
			c.setopt(c.URL, url)
		c.setopt(c.WRITEFUNCTION, self.body_callback)
		c.setopt(c.HEADERFUNCTION, self.head_callback)
		c.setopt(c.HTTPHEADER,[x+": "+headers[x] for x in list(headers.keys())])
		c.setopt(pycurl.ENCODING, '')
		if data!=None:
			enc = urlencode(data)
			#c.setopt(c.POST,1)
			c.setopt(c.POSTFIELDS,enc)
			print("enc",enc)

		c.setopt(c.LOW_SPEED_LIMIT, 15) # 15 bytes/sec = dead. Random value.
		c.setopt(c.LOW_SPEED_TIME, self.getTimeout()) # i.e. dead (< 15 bytes/sec)
		if ref!=None:
			c.setopt(c.REFERER, str(ref))

		try:
			c.perform()
		except pycurl.error as msg:
			raise URLTimeoutError(msg.args[1],url)

		c.close()

		if self.contents=="" and self.header == "":
			raise URLTimeoutError("Timed out!",url)

		hdrs = self.header.splitlines()
		converted = False
		if len(hdrs)>1:
			info = self.gen_headers(hdrs[1:])
			if "Content-Type" in info:
				ct = info["Content-Type"]
				if ct.find("image/") == -1 and ct.find("charset")!=-1:
					charset = charsetPattern.search(ct)
					if charset!= None:
						enc = charset.groups()[0]
						try:
							converted = True
							newcontents = str(self.contents, enc)
							self.contents = newcontents
						except LookupError: # can't find the relevant encoding, assume all ok without...
							raise
		if converted == False:
			try:
				newcontents = str(self.contents, "utf-8")
				self.contents = newcontents
			except UnicodeDecodeError:
				pass
		info = {}
		status = 0

		if hdrs != []:
			last_ok = 0
			for x in range(len(hdrs)):
				if hdrs[x].find("HTTP")==0:
					last_ok = x
			hdrs = hdrs[last_ok:]
			ret = re.search("HTTP/1.[01] (\d+) (.*?)",hdrs[0]).group(1,2)
			status = [0,0]
			status[0] = int(ret[0])
			status[1] = ret[1]

			info = self.gen_headers(hdrs[1:])

			ret = self.check_move(status[0], locals())
			if ret!=None:
				return ret

			if status[0] == 304:
				raise URLOldDataError

			if status[0] !=200:
				raise URLTimeoutError(str(status[0])+" "+status[1],url, status[0])

			return URLObject(origurl,None, self.contents,info,data)
		raise URLTimeoutError("No Headers!",url)
