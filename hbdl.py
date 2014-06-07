#!/usr/bin/env python
import os
import re
import json
import mechanize
import cookielib
import urllib2


__GAMEKEY_DIR__ = 'gamekeys'
__GAMEKEY_FILE__ = __GAMEKEY_DIR__ + '/%s.json'


# prettify the file size with a suffix
def pretty_file_size(size):
    units = ('B', 'KiB', 'MiB', 'GiB')
    i = 0

    while size >= 1024.0:
        size /= 1024.0
        i += 1

    return '%.2f %s' % (size, units[i])


# download a file and save it to the disk
def download_file(url, directory, filename):
    stream = urllib2.urlopen(url)

    with open(os.path.join(directory, filename), 'wb') as f:
        meta = stream.info()
        file_size = int(meta.getheaders('Content-Length')[0])
        print 'Downloading: %s' % (filename)

        file_size_dl = 0
        block_size = 8192
        while True:
            buff = stream.read(block_size)
            if not buff:
                break

            file_size_dl += len(buff)
            f.write(buff)
            status = r'  %11s / %11s [%6.2f%%]' % (pretty_file_size(file_size_dl), pretty_file_size(file_size), file_size_dl * 100.0 / file_size)
            status = status + chr(8) * (len(status) + 1)
            print status,


# refresh the index file (download new versions of the gamekeys)
def refresh_index(username, password):
    url_home = 'https://www.humblebundle.com/home'
    url_login = 'https://www.humblebundle.com/login'
    url_order = 'https://www.humblebundle.com/api/v1/order/%s'

    # make sure the directory exists
    try:
        os.makedirs(__GAMEKEY_DIR__)
    except Exception, e:
        pass

    # set up the browser
    br = mechanize.Browser()
    br.set_handle_robots(False)

    # set up the cookie jar
    cj = cookielib.LWPCookieJar('cookies.txt')
    try:
        cj.load('cookies.txt')
    except Exception, e:
        pass
    cj.save('cookies.txt', ignore_discard=False, ignore_expires=False)

    br.set_cookiejar(cj)

    # open /home
    print 'Opening /home...'
    br.open(url_home)

    # the user is not logged in
    if url_login in br.geturl():
        print 'Trying to log in...'
        form_index = 0

        # find the login form and log in
        for form in br.forms():
            if form.action == url_login:
                print 'Found the form!'
                br.select_form(nr=form_index)
                br.form['username'] = username
                br.form['password'] = password

                br.submit()
                break
            form_index += 1

    # stop the collection if we didn't land on /home
    if url_home not in br.geturl():
        print 'Did not land on /home, stopping!'
        print '  %s' % (br.geturl())
        return

    # save the cookie jar
    cj.save('cookies.txt', ignore_discard=False, ignore_expires=False)

    # read the content
    response = br.response()
    content = response.read()

    # find the gamekeys
    gamekeys = re.findall('gamekeys: \\[(.*?)\\]', content)[0]
    gamekeys = re.findall('"([^"]+)"', gamekeys)

    # grab all the gamekey data
    key_index = 0
    print 'Collecting keys...'
    for gamekey in gamekeys:
        print '  %d/%d' % (key_index + 1, len(gamekeys))
        response = br.open(url_order % gamekey)
        content = response.read()

        with open(__GAMEKEY_FILE__ % gamekey, 'w') as f:
            f.write(content)

        key_index += 1

    # save the index file
    with open(__GAMEKEY_FILE__ % 'index', 'w') as f:
        json.dump(gamekeys, f, indent=2)

    # save the cookie jar
    cj.save('cookies.txt', ignore_discard=False, ignore_expires=False)

    # we're done
    print 'Done.'
