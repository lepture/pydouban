#-*- coding: utf-8 -*-
"""
pydouban

A lightweight douban api library.

Basic Usage:
    >>> import pydouban
    >>> key = 'your douban oauth consumer key'
    >>> secret = 'your douban oauth consumer secret'
    >>> auth = pydouban.Auth(key, secret)
    >>> dic = auth.login()
    >>> print dic['url']
    ...
    >>> token_qs = auth.get_acs_token(dic['oauth_token'],dic['oauth_token_secret'])

    >>> api = pydouban.Api()
    >>> print api.search_people('ahbei')
    >>> api.set_qs_token(token_qs)
    >>> print api.get_me()
"""
'''
The BSD License

Copyright (c) 2010, Marvour <marvour@gmail.com>
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following
      disclaimer in the documentation and/or other materials provided
      with the distribution.
    * Neither the name of the author nor the names of its contributors
      may be used to endorse or promote products derived from this
      software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT 
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

__version__ = '1.0.0'
__author__ = 'Marvour <marvour@gmail.com>'
__website__ = 'http://i.shiao.org/a/pydouban'

import hmac
import urllib
import httplib
from hashlib import sha1
from random import getrandbits
from time import time
from cgi import escape

AUTH_URL = 'http://www.douban.com/service/auth'
API_URL = 'http://api.douban.com'

def _escape(s):
    try: s = s.encode('utf-8')
    except UnicodeDecodeError: pass
    return escape(s)

def _quote(s):
    return urllib.quote(str(s), '~')

def _qs2dict(s):
    dic = {} 
    for param in s.split('&'):
        (key, value) = param.split('=')
        dic[key] = value
    return dic

def _dict2qs(dic):
    return '&'.join(['%s=%s' % (key, _quote(value)) for key, value in dic.iteritems()]) 

def _dict2header(dic):
    s = ', '.join(['%s="%s"' % (k, _quote(v)) for k, v in dic.iteritems() if k.startswith('oauth_')]) 
    auth_header = 'OAuth realm="", %s' % s
    return {'Authorization': auth_header}

class Auth(object):
    _token = ''
    _token_secret = ''
    def __init__(self, key='', secret=''):
        if key:
            self._key = key
        if secret:
            self._secret = secret

    def set_consumer(self, key, secret):
        self._key = key
        self._secret = secret

    def set_token(self, token, token_secret):
        self._token = token
        self._token_secret = token_secret

    def set_qs_token(self, qs):
        dic = _qs2dict(qs)
        self._token = dic['oauth_token']
        self._token_secret = dic['oauth_token_secret']

    def get_oauth_params(self, url, params, method='GET'):
        assert hasattr(self, '_key'), "need consumer key."
        assert hasattr(self, '_secret'), "need consumer secret."
        oauth_params = {
            'oauth_consumer_key': self._key,
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': int(time()),
            'oauth_nonce': getrandbits(64),
            'oauth_version': '1.0'}
        if self._token:
            oauth_params['oauth_token'] = self._token

        # Add other params
        params.update(oauth_params)

        # Sort and concat
        s = ''
        for k in sorted(params):
            s += _quote(k) + '=' + _quote(params[k]) + '&'
            msg = method + '&' + _quote(url) + '&' + _quote(s[:-1])
        # Maybe token_secret is empty
        key = self._secret + '&' + self._token_secret

        digest = hmac.new(key, msg, sha1).digest()
        params['oauth_signature'] = digest.encode('base64')[:-1]

        return params
    
    def login(self, callback=None):
        req_token_url = AUTH_URL + '/request_token'
        params = self.get_oauth_params(req_token_url, {}) 
        res = urllib.urlopen(url=req_token_url + '?' + _dict2qs(params))
        if 200 != res.code:
            raise Exception('OAuth Request Token Error: ' + res.read())
        dic = _qs2dict(res.read())
        self._token = dic['oauth_token']
        self._token_secret = dic['oauth_token_secret']
        sig_params = {'oauth_signature': params['oauth_signature']}
        dic['params'] = _dict2qs(self.get_oauth_params(req_token_url,sig_params))
        dic['url'] = AUTH_URL + '/authorize?' + dic['params']
        if callback:
            dic['url'] += '&' + _dict2qs({'oauth_callback':callback})
        return dic

    def get_acs_token(self, req_token, req_token_secret):
        acs_token_url = AUTH_URL + '/access_token'

        self._token = req_token
        self._token_secret = req_token_secret

        params = self.get_oauth_params(acs_token_url, {})
        res = urllib.urlopen(url=acs_token_url + '?' + _dict2qs(params))
        if 200 != res.code:
            raise Exception('OAuth Access Token Error: ' + res.read())
        return res.read() # qs

class Api(object):
    """
    more information on http://www.douban.com/service/apidoc/reference/
    """
    def __init__(self, alt='json', start_index=1, max_results=10, skip_read=True):
        if alt in ('atom', 'xml'):
            self._alt = 'atom'
        else:
            self._alt = 'json'
        self._start = start_index
        self._max = max_results
        self._skip = skip_read

    def set_var(self, start_index, max_results):
        self._start = start_index
        self._max = max_results

    def set_key(self, key):
        self._key = key

    def set_oauth(self, key, secret, acs_token, acs_token_secret):
        self._oauth = Auth(key, secret)
        self._oauth.set_token(acs_token, acs_token_secret)

    def set_qs_oauth(self, key, secret, qs):
        self._oauth = Auth(key, secret)
        self._oauth.set_qs_token(qs)
    
    #{{{ method

    def _post(self, path, body, params={}):
        assert hasattr(self, '_oauth'), "need be authed."
        res_url = API_URL + path
        dic = self._oauth.get_oauth_params(res_url, params, 'POST')
        headers = _dict2header(dic)
        headers['Content-Type'] = 'application/atom+xml; charset=utf-8'
        
        con = httplib.HTTPConnection('api.douban.com', 80)
        con.request('POST', path, body, headers)
        res = con.getresponse()
        if 201 != res.status:
            raise Exception('Douban Post Error : ' + str(res.status))
        if self._skip:
            return True
        return res.read()

    def _put(self, path, body, params={}):
        assert hasattr(self, '_oauth'), "need be authed."
        res_url = API_URL + path
        dic = self._oauth.get_oauth_params(res_url, params, 'PUT')
        headers = _dict2header(dic)
        headers['Content-Type'] = 'application/atom+xml; charset=utf-8'
        
        con = httplib.HTTPConnection('api.douban.com', 80)
        con.request('PUT', path, body, headers)
        res = con.getresponse()
        if 202 != res.status:
            raise Exception('Douban Put Error : ' + str(res.status))
        if self._skip:
            return True
        return res.read()

    def _del(self, path, params={}):
        assert hasattr(self, '_oauth'), "need be authed."
        res_url = API_URL + path
        dic = self._oauth.get_oauth_params(res_url, params, 'DELETE')
        headers = _dict2header(dic)

        con = httplib.HTTPConnection('api.douban.com', 80, timeout=5)
        con.request('DELETE', path, None, headers)
        res = con.getresponse()
        if 200 != res.status:
            raise Exception('Douban Delete Error : ' + str(res.status))
        if self._skip:
            return True
        return res.read()
    
    def _get(self, path, params={}):
        assert hasattr(self, '_oauth'), "need be authed."
        res_url = API_URL + path
        params.update({'alt': self._alt})
        dic = self._oauth.get_oauth_params(res_url, params, 'GET')
        res = urllib.urlopen(url=res_url + '?' + _dict2qs(dic))
        if 200 != res.code:
            raise Exception('Douban Get Error : ' + str(res.code))
        return res.read()

    def _get_public(self, path, params={}):
        path += '?alt=' + self._alt
        if params:
            path += '&' + _dict2qs(params)
        if hasattr(self, '_key'):
            path += '&apikey=' + self._key
        res = urllib.urlopen(url=API_URL+path)
        if 200 != res.code:
            raise Exception('Get Public Resouce Error : ' + str(res.code))
        return res.read()

    #}}}
    
    #{{{ public method, no need for oauth

    def get_people(self, userID):
        path = '/people/%s?alt=%s' % (userID, self._alt)
        if hasattr(self, '_key'):
            path = '/people/%s?alt=%s&apikey=%s' % (userID, self._alt, self._key)
        res = urllib.urlopen(url=API_URL+path)
        if 200 != res.code:
            raise Exception('Get People Error : ' + str(res.code))
        return res.read()

    def search_people(self, q):
        try: q = q.encode('utf-8')
        except UnicodeDecodeError: pass
        dic = {'q':q, 'alt':self._alt,'start-index':self._start,'max-results':self._max}
        path = '/people?' + _dict2qs(dic)
        if hasattr(self, '_key'):
            path += '&apikey=' + self._key
        res = urllib.urlopen(url=API_URL+path)
        if 200 != res.code:
            raise Exception('Search People Error : ' + str(res.code))
        return res.read()

    def _sq(self, q, tag=None, var='movie'):
        try: q = q.encode('utf-8')
        except UnicodeDecodeError: pass
        path = '/%s/subjects' % var
        dic = {'q':q, 'alt':self._alt,'start':self._start,'max':self._max}
        s = '?q=%(q)s&alt=%(alt)s&start-index=%(start)s&max-results=%(max)s'\
                % dic
        if tag:
            s += '&tag=' + tag
        if hasattr(self, '_key'):
            s += '&apikey=' + self._key
        url = API_URL + path + s
        res = urllib.urlopen(url)
        if 200 != res.code:
            raise Exception('Search Resource Error : ' + str(res.code))
        return res.read()
    def search_movie(self, q, tag=None):
        return self._sq(q, tag, var='movie')
    def search_book(self, q, tag=None):
        return self._sq(q, tag, var='book')
    def search_music(self, q, tag=None):
        return self._sq(q, tag, var='music')

    #}}}

    #{{{ resource (public and oauth)

    def get_book_byid(self, subjectID):
        path = '/book/subject/%s' % subjectID
        if hasattr(self, '_oauth'):
            return self._get(path)
        return self._get_public(path)
    def get_book_byisbn(self, isbnID):
        path = '/book/subject/isbn/%s' % isbnID
        if hasattr(self, '_oauth'):
            return self._get(path)
        return self._get_public(path)
    def get_movie_byid(self, subjectID):
        path = '/movie/subject/%s' % subjectID
        if hasattr(self, '_oauth'):
            return self._get(path)
        return self._get_public(path)
    def get_movie_byimdb(self, imdbID):
        path = '/movie/subject/imdb/%s' % imdbID
        if hasattr(self, '_oauth'):
            return self._get(path)
        return self._get_public(path)
    def get_music_byid(self, subjectID):
        path = '/music/subject/%s' % subjectID
        if hasattr(self, '_oauth'):
            return self._get(path)
        return self._get_public(path)

    #}}}
    
    #{{{ user info

    def get_me(self):
        """ get authed user's information"""
        path = '/people/%40me'
        return self._get(path)

    def get_friends(self):
        """ get authed user's friends"""
        path = '/people/%40me/friends'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)

    def get_contacts(self):
        ''' get authed user's contacts'''
        path = '/people/%40me/contacts'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)

    #}}}

    #{{{ collection
    # http://www.douban.com/service/apidoc/reference/collection

    def get_collections(self, cat, status=None, tag=None):
        if cat not in ('book','movie','music'):
            cat = 'book'
        path = '/people/%40me/collection'
        params = {'cat': cat, 'start-index': self._start, 'max-results': self._max}
        if tag:
            params.update({'tag':tag})
        if status:
            params.update({'status':status})
        return self._get(path, params)

    def get_collection(self, collectionID):
        path = '/collection/%s' % collectionID
        return self._get(path)

    def _collection_atom(self, sourceURL, status, rating, tags, comment, privacy):
        if not isinstance(tags, list):
            raise TypeError
        if privacy not in ('public', 'private'):
            privacy = 'public'
        atom = '<?xml version="1.0" encoding="UTF-8"?><entry xmlns:ns0="http://www.w3.org/2005/Atom" xmlns:db="http://www.douban.com/xmlns/">'
        atom += '<db:status>' + status + '</db:status>'
        for tag in tags:
            atom += '<db:tag name="%s" />' % _escape(tag)
        atom += '<gd:rating xmlns:gd="http://schemas.google.com/g/2005" value="%s" />' % rating
        atom += '<content>%s</content>' % _escape(comment)
        atom += '<db:subject><id>%s</id></db:subject>' % sourceURL
        atom += '<db:attribute name="privacy">%s</db:attribute></entry>' % privacy
        return atom

    def post_collection(self, sourceURL, status, rating=0, tags=[], comment='', privacy='public'):
        path = 'http://api.douban.com/collection'
        atom = self._collection_atom(sourceURL, status, rating, tags, comment, privacy)
        return self._post(path, atom)

    def update_collection(self, collectionID, sourceURL, status, rating=0, tags=[], comment='', privacy='public'):
        path = 'http://api.douban.com/collection/%s' % collectionID
        atom = self._collection_atom(sourceURL, status, rating, tags, comment, privacy)
        return self._put(path, atom)

    def del_collection(self, collectionID):
        path = 'http://api.douban.com/collection/%s' % collectionID
        return self._del(path)

    #}}}

    #{{{ events
    def get_events(self):
        ''' get authed user's events'''
        path = '/people/%40me/events'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)
    def get_initiate_events(self):
        ''' get authed user's initiate events'''
        path = '/people/%40me/events/initiate'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)
    def get_participate_events(self):
        ''' get authed user's participate events'''
        path = '/people/%40me/events/participate'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)
    def get_wish_events(self):
        ''' get authed user's wish events'''
        path = '/people/%40me/events/wish'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)

    def get_event(self, eventID):
        path = '/event/%s' % eventID
        if hasattr(self, '_oauth'):
            return self._get(path)
        return self._get_public(path)
    def get_event_participants(self, eventID):
        path = '/event/%s/participants' % eventID
        params = {'start-index': self._start, 'max-results': self._max}
        if hasattr(self, '_oauth'):
            return self._get(path, params)
        return self._get_public(path, params)
    def get_event_wishers(self, eventID):
        path = '/event/%s/wishers' % eventID
        params = {'start-index': self._start, 'max-results': self._max}
        if hasattr(self, '_oauth'):
            return self._get(path, params)
        return self._get_public(path, params)

    def get_user_events(self, userID):
        path = '/people/%s/events' % userID
        params = {'start-index': self._start, 'max-results': self._max}
        if hasattr(self, '_oauth'):
            return self._get(path, params)
        return self._get_public(path, params)
    def get_user_initiate_events(self, userID):
        path = '/people/%s/events/initiate' % userID
        params = {'start-index': self._start, 'max-results': self._max}
        if hasattr(self, '_oauth'):
            return self._get(path, params)
        return self._get_public(path, params)
    def get_user_participate_events(self, userID):
        path = '/people/%s/events/participate' % userID
        params = {'start-index': self._start, 'max-results': self._max}
        if hasattr(self, '_oauth'):
            return self._get(path, params)
        return self._get_public(path, params)
    def get_user_wish_events(self, userID):
        path = '/people/%s/events/wish' % userID
        params = {'start-index': self._start, 'max-results': self._max}
        if hasattr(self, '_oauth'):
            return self._get(path, params)
        return self._get_public(path, params)
    def get_location_events(self, locationID):
        path = '/event/location/%s' % locationID
        params = {'start-index': self._start, 'max-results': self._max}
        if hasattr(self, '_oauth'):
            return self._get(path, params)
        return self._get_public(path, params)
    def search_events(self, q, location='all'):
        path = '/events'
        try: q = q.encode('utf-8')
        except UnicodeDecodeError: pass
        params = {'q': q, 'location': location,
                  'start-index': self._start, 'max-results': self._max}
        return self._get_public(path, params)

    #TODO
    def post_event(self):
        pass
    def update_event(self, eventID):
        pass
    def del_event(self, eventID):
        path = '/event/%s' % eventID
        return self._del(path)

    #}}}

    #{{{ note

    def get_notes(self):
        path = '/people/%40me/notes'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)
    
    def get_note(self, noteID):
        path = '/note/%s' % noteID
        return self._get(path)

    def _note_atom(self, title, content, privacy, can_reply): 
        if privacy not in ('public', 'friend', 'private'):
            privacy = 'private'
        if can_reply not in ('yes', 'no'):
            can_reply = 'no'
        if 'private' == privacy:
            can_reply = 'no'
        title = _escape(title)
        content = _escape(content)
        dic = {'title': title, 'content': content,'privacy':privacy, 'can_reply': can_reply}
        atom = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <entry xmlns:ns0="http://www.w3.org/2005/Atom" xmlns:db="http://www.douban.com/xmlns/">
        <title>%(title)s</title>
        <content>%(content)s</content>
        <db:attribute name="privacy">%(privacy)s</db:attribute>
        <db:attribute name="can_reply">%(can_reply)s</db:attribute>
        </entry>''' % dic
        return atom

    def post_note(self, title, content, privacy='public', can_reply='yes'): 
        path = '/notes'
        atom = self._note_atom(title, content, privacy, can_reply)
        return self._post(path, atom)

    def update_note(self, noteID, title, content, privacy='public', can_reply='yes'): 
        path = '/note/%s' % noteID
        atom = self._note_atom(title, content, privacy, can_reply)
        return self._put(path, atom)

    def del_note(self, noteID):
        path = '/note/%s' % noteID
        return self._del(path)

    #}}}

    #{{{ miniblog

    def get_miniblog(self, term=None):
        """
        Get all miniblog:
            >>> get_miniblog()

        Get only saying:
            >>> get_miniblog(term='saying')
        """
        path = '/people/%40me/miniblog'
        params = {'start-index': self._start, 'max-results': self._max}
        if term:
            # set term='saying' to filter
            params.update({'type':term})
        return self._get(path, params)

    def get_contacts_miniblog(self, term=None):
        """
        Get all contacts miniblog:
            >>> get_contacts_miniblog()

        Get only contacts saying:
            >>> get_contacts_miniblog(term='saying')
        """
        path = '/people/%40me/miniblog/contacts'
        params = {'start-index': self._start, 'max-results': self._max}
        if term:
            # set term='saying' to filter
            params.update({'type':term})
        return self._get(path, params)

    def get_miniblog_replies(self, miniblogID):
        path = '/miniblog/%s/comments' % miniblogID
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)

    def post_miniblog(self, msg):
        path = '/miniblog/saying'
        try:
            content = msg.encode('utf-8')
        except UnicodeDecodeError:
            content = msg
        atom = '<?xml version="1.0" encoding="UTF-8"?><entry xmlns:ns0="http://www.w3.org/2005/Atom" xmlns:db="http://www.douban.com/xmlns/"><content>'
        atom += _escape(content)
        atom += '</content></entry>'
        return self._post(path, atom)

    def post_miniblog_reply(self, miniblogID, msg):
        path = '/miniblog/%s/comments' % miniblogID
        try:
            content = msg.encode('utf-8')
        except UnicodeDecodeError:
            content = msg
        atom = '<?xml version="1.0" encoding="UTF-8"?><entry xmlns:ns0="http://www.w3.org/2005/Atom" xmlns:db="http://www.douban.com/xmlns/"><content>'
        atom += _escape(content)
        atom += '</content></entry>'
        return self._post(path, atom)

    def del_miniblog(self, miniblogID):
        path = '/miniblog/%s' % miniblogID
        return self._del(path)

    #}}}

    #{{{ douban mail
    # http://www.douban.com/service/apidoc/reference/doumail

    def get_mail(self, doumailID):
        path = '/doumail/%s' % doumailID
        return self._get(doumail)

    def get_inbox_mails(self):
        path = '/doumail/inbox'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)

    def get_unread_mails(self):
        path = '/doumail/inbox/unread'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)
    
    def get_outbox_mails(self):
        path = '/doumail/outbox'
        params = {'start-index': self._start, 'max-results': self._max}
        return self._get(path, params)

    def post_mail(self, receiverID, title, content):
        atom = '<?xml version="1.0" encoding="UTF-8"?><entry xmlns="http://www.w3.org/2005/Atom" xmlns:db="http://www.douban.com/xmlns/" xmlns:gd="http://schemas.google.com/g/2005" xmlns:opensearch="http://a9.com/-/spec/opensearchrss/1.0/">'
        atom += '<db:entity name="receiver"><uri>http://api.douban.com/people/%s</uri></db:entity>' % _escape(receiverID)
        atom += '<content>%s</content>' % _escape(content)
        atom += '<title>%s</title>' % _escape(title)
        atom += '</entry>'
        return self._post(path, atom)

    def del_mail(self, doumailID):
        path = '/doumail/%s' % doumailID
        return self._del(path)

    def mark_mail_read(self, doumailID):
        path = '/doumail/%s' % doumailID
        atom = '<?xml version="1.0" encoding="UTF-8"?><entry xmlns="http://www.w3.org/2005/Atom" xmlns:db="http://www.douban.com/xmlns/" xmlns:gd="http://schemas.google.com/g/2005" xmlns:opensearch="http://a9.com/-/spec/opensearchrss/1.0/"><db:attribute name="unread">false</db:attribute></entry>'
        return self._put(path, atom)
