#-*- coding: utf-8 -*-

import cookielib
import logging
import urllib
import urllib2
import urlparse
from StringIO import StringIO
import gzip

import os
import sys
import re
from random import random
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from bs4 import BeautifulSoup

from settings import *

logger = logging.getLogger(__name__)

"""
    Log dos valores retornados em tempo de execução 
"""
def log(f):
    def called(*args, **kargs):
        val = f(*args, **kargs) 
        logger.debug("%s = %s" % (f,val))
        return val
    return called

class BasePageParser:
    """
        Classe base para os parsers
    """
    def __init__(self, html):
        self._soup = BeautifulSoup(html, "html5lib", from_encoding="utf-8")
    
    def _findById(self,id):
        return self._soup.find(id=id).string
    
    def _findByElementClass(self,element,className) :
        return self._soup.find(element, class_ = className).string
    
    def _findByDivClass(self,className):
        return self._findByElementClass('div',className)
 
    def _findBySpanClass(self,className) :
        return self._findByElementClass('span',className)

class FriendsXmlParser(BasePageParser):
    """
        Classe que faz o Parser do Xml dos Amigos
    """
    @log
    def PsnId(self):
        return self._soup.find('onlineid').string
    
    @log    
    def Playing(self) :
        return self._soup.find('current_game').string
    
    @log
    def AvatarSmall(self):
        return UK_AVATAR_URL % (self._soup.find('current_avatar').string)
    
    @log
    def isOnline(self):
        return bool(self._soup.find('current_presence').string.startswith('online'))

class TrophiePageParser(BasePageParser):
    """
        Clase que faz o parser dos Troféus e do Perfil
    """
    
    @log
    def PsnId(self):
        return self._findById("id-handle").strip()
    
    @log    
    def AvatarSmall(self) :
        return self._soup.find('div', id="id-avatar").find('img')['src']
    
    @log
    def Playing(self):
        return self._findBySpanClass("_iamplaying_")
    
    @log
    def isOnline(self):
        return bool(self._soup.find('div', {'class': 'oStatus'}).find('div', {'class': 'onlineStatus online'}))

    @log    
    def Level(self) :
        return int(self._findById("leveltext" ))
    
    @log    
    def Progress(self) :     
        return int(self._findByDivClass("progresstext").replace('%',''))
    
    @log
    def Platinum(self) :
        return int(self._findByDivClass("text platinum").replace('Platinum',''))
    
    @log
    def Gold(self) :
        return int(self._findByDivClass("text gold").replace('Gold',''))
    
    @log
    def Silver(self) :
        return int(self._findByDivClass("text silver").replace('Silver',''))
    
    @log
    def Bronze(self) :
        return int(self._findByDivClass("text bronze").replace('Bronze',''))
    
    @log
    def Total(self) :
        return int(self._soup.find('div', id="totaltrophies" ).find('div', id="text").string)

class GamesPageParser(BasePageParser):
    """
        Classe que faz o Parser dos Jogos
    """
    
    @log
    def Title(self):
        return self._soup.find('a', class_ = 'title').string.encode('ascii','xmlcharrefreplace')
    
    @log
    def Id(self):
        return ''
    
    @log    
    def Image(self):
        return self._soup.find('div', class_='avatarimg').find('img')['src']
    
    @log
    def Progress(self):
        return int(self._findBySpanClass('progressval')[:-1])
    
    @log    
    def Platinum(self) :
        return int(self._soup.find('div','recentplatinum').find('span').string)
    
    @log
    def Gold(self) :
        return int(self._soup.find('div','recentgold').find('span').string)
    
    @log
    def Silver(self) :
        return int(self._soup.find('div','recentsilver').find('span').string)
    
    @log
    def Bronze(self) :
        return int(self._soup.find('div','recentbronze').find('span').string)
    
    @log
    def Total(self) :
        return int(self._findBySpanClass('totalTrophies'))
    
    def __iter__(self):
        games = []
        nodes = self._soup.find_all('div', class_ = 'recentitems')
        logger.debug("Found %d nodes" % len(nodes)) 
        for node in nodes :
            games.append(GamesPageParser(str(node)))
        return iter(games)    

class PSN:
    """
        Classe principal de acesso ao conteúdo do site da PSN
    """

    def __init__(self, email, passwd, site):
        self._email = email
        self._passwd = passwd

        # Install global opener for urllib2 using a cookie fiel named after
        self._cookie_file = email.lower().strip() + '.lwp'
        self._cookie_jar = cookielib.LWPCookieJar()

        self._opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self._cookie_jar))
        
        logger.info("Finish PSN init")
        
        if site == 'US' :
            self._login(US_LOGIN_URL, US_LOGIN_RETURN, US_LOGIN_LANDING)
        elif site == 'UK' :
            self._login(UK_LOGIN_POST_URL,UK_LOGIN_RETURN_URL,UK_LOGIN_PAGE)
        else :
            raise Exception("Login Site %s not recognized by engine")        

    def _getUrl(self,url,referer=None,data=None,fix_markup=True):
        logger.debug("GET %s" % (url))
        logger.debug("Referer %s" % (referer))
        logger.debug("Data %s" % (data))
        
        headers = DEFAULT_HEADERS
        if referer is not None :
            headers.update({'Referer': referer })
        
        if data is not None :
            data = urllib.urlencode(data)
        
        rq = urllib2.Request(url=url, data=data, headers=headers)
        
        try:
            rs = self._opener.open(rq, timeout=10000)
            if rs.info().get('Content-Encoding') == 'gzip':
                logger.debug("Reponse is Gzipped, decompressing")
                html = self._uncompress(rs)
            else :
                html = rs.read()
        
            logger.debug("Response: %s" % (html))
        
            if fix_markup == True :
                return self._fix_markup(html)
            else :
                return html

        except urllib2.HTTPError:
            logger.warning("Bypass HTTP ERROR")
            pass # this just happens, but it needs to happen


    def _fix_markup(self,html):
        """
            Retira o xml do html, caso exista
        """
        html = html.lstrip()
        if html.startswith("<?xml"):
            html = "\n".join(html.split("\n")[1:])
        return html    
        
    def _uncompress(self,rs):
        """ 
            Descomprimi uma resposta gzip
        """
        buf = StringIO( rs.read() )
        f = gzip.GzipFile(fileobj=buf)
        return f.read()

    def _login(self, login_url, login_return, login_landing):
        logger.info("Logging in")

        ## Post the login form to get a session id
        data = {'j_username': self._email,
                'j_password': self._passwd,
                'returnURL': login_return }
        
        self._getUrl(login_url,login_landing,data)
        
        # Store session id
        for cookie in self._cookie_jar:
            logger.debug('%s --> %s'%(cookie.name,cookie.value))
            if(cookie.name == "SONYCOOKIE1" or cookie.name == "JSESSIONID") :
                self._sess_id = cookie.value
        
        logger.info("Logged in with session ID=%s" % (self._sess_id))

    def trophies(self,psnId):

        html = self._getUrl(PSN_PROFILE % (psnId), PING_PAGE % (psnId))
        
        # Verify a valid user response
        if NO_USER_PROFILE in html :
            raise Exception("UserNotFoundFault") 

        return TrophiePageParser(html)
    
    def games(self,psnId):
        
        html = self._getUrl(PSN_GAMES % (psnId), PSN_PROFILE % (psnId))
        
        return GamesPageParser(html)
    
    def friends(self):
        
        html = self._getUrl(PSN_PERFECT_FRIENDS_XML,UK_REFERER_SESSION_ID % (self._sess_id),fix_markup=False)
        
        soup = BeautifulSoup(html, "html5lib", from_encoding="utf-8")

        friends = []

        nodes = soup.find_all('psn_friend')
        logger.debug("Found %d nodes" % len(nodes)) 
        for node in nodes :
            friend = FriendsXmlParser(str(node))
            
            #if friend.isOnline() :
            #logger.debug("Friend %s is Online" % (friend.PsnId()))
            friends.append(friend)
        
        return friends
