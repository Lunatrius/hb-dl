#!/usr/bin/env python
import os
import re
import json
import mechanize
import cookielib
import urllib2
import argparse
import ConfigParser


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
def refresh_index(username, password, headers):
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
    br.addheaders = headers

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

    data = {}
    data['bundles'] = {}
    data['products'] = {}

    for gamekey in gamekeys:
        print '  %d/%d' % (key_index + 1, len(gamekeys))
        response = br.open(url_order % gamekey)
        content = response.read()

        with open(__GAMEKEY_FILE__ % gamekey, 'w') as f:
            f.write(content)

        process_gamekey(data, gamekey, json.loads(content))

        key_index += 1

    # save the index file
    with open(__GAMEKEY_FILE__ % 'index', 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)

    # save the cookie jar
    cj.save('cookies.txt', ignore_discard=False, ignore_expires=False)

    # we're done
    print 'Done.'


# parse out the important bits
def process_gamekey(data, gamekey, keydata):
    bundle_name = keydata['product']['machine_name']
    data['bundles'][bundle_name] = {}
    data['bundles'][bundle_name]['name'] = keydata['product']['human_name']
    data['bundles'][bundle_name]['key'] = gamekey

    print '    %s (%d)' % (keydata['product']['human_name'], len(keydata['subproducts']))
    for item in keydata['subproducts']:
        product = process_product(item)
        if product['machine_name'] not in data['products']:
            data['products'][product['machine_name']] = product
        data['products'][product['machine_name']]['bundles'].append(keydata['product']['machine_name'])


# parse out the important bits
def process_product(product):
    data = {}

    data['bundles'] = []
    data['machine_name'] = product['machine_name']
    data['human_name'] = product['human_name']
    data['icon'] = product['icon']

    downloads = []

    for download in product['downloads']:
        downloads.append(process_download(download))

    data['downloads'] = downloads

    return data


# parse out the important bits
def process_download(download):
    data = {}

    data['machine_name'] = download['machine_name']
    data['platform'] = download['platform']

    files = []
    for download_struct in download['download_struct']:
        f = process_download_struct(download_struct)
        if len(f) > 0:
            files.append(f)

    data['files'] = files

    return data


# parse out the important bits
def process_download_struct(download_struct):
    data = {}

    if 'url' in download_struct:
        data['name'] = download_struct['name']
        data['file_size'] = download_struct['file_size']
        if 'sha1' in download_struct:
            data['sha1'] = download_struct['sha1']
        data['md5'] = download_struct['md5']
        data['url'] = download_struct['url']['web']

        if 'arch' in download_struct:
            data['arch'] = download_struct['arch']
    elif 'external_link' in download_struct:
        data['external'] = download_struct['external_link']
    else:
        print '[!] Skipping %s' % download_struct

    return data


# convert a config section to a map
def section_to_map(config, section):
    m = {}
    options = config.options(section)

    for option in options:
        try:
            m[option] = config.get(section, option)
        except:
            m[option] = None

    return m


if __name__ == '__main__':
    config = ConfigParser.ConfigParser()
    config.read('config.ini')

    parser = argparse.ArgumentParser(description='Download Humble Bundle stuff!')
    parser.add_argument('--refresh-keys', help='refresh gamekeys', action='store_true')
    parser.add_argument('--download', help='download all or the specified items', action='store_true')
    parser.add_argument('item', help='list of items to download', nargs='*')

    args = parser.parse_args()

    if args.refresh_keys:
        login = section_to_map(config, 'login')
        headermap = section_to_map(config, 'headers')

        headers = []
        for k in headermap:
            headers.append((k, headermap[k]))

        refresh_index(login['username'], login['password'], headers)

    if args.download:
        print 'not yet implemented'
        print args.item
