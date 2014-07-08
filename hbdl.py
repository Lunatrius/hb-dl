#!/usr/bin/env python2.7

'''
Download anything from claimed HB pages!

Usage:
  hbdl.py -p audio -d bastion
    downloads all audio files that contains bastion in the name

  hbdl.py -p windows linux -d nightsky
    downloads all nightsky files that are for windows OR linux

  hbdl.py -d nightsky "the swapper"
    downloads all nightsky AND "the swapper" files

NOTE: I'm no python expert
'''

import os
import re
import json
import hashlib
import mechanize
import cookielib
import urllib2
import getpass
import argparse


__GAMEKEY_DIR__ = 'gamekeys'
__GAMEKEY_FILE__ = __GAMEKEY_DIR__ + '/%s.json'
__DOWNLOAD_DIR__ = 'downloads'


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

    print ''


# refresh the index file (download new versions of the gamekeys)
def refresh_index():
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

        # ask for the username/email
        username = raw_input('Username [%s]: ' % getpass.getuser())
        if not username:
            username = getpass.getuser()

        # ask for a password with confirmation
        pprompt = lambda: (getpass.getpass(), getpass.getpass('Password (retype): '))

        p1, p2 = pprompt()
        while p1 != p2:
            print('Passwords do not match. Try again.')
            p1, p2 = pprompt()

        password = p1

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


# print a fancy title
def print_title(title):
    print '================================================================'
    print '== %s' % title
    print '================================================================'


# get the file name from a URL
def get_filename(url):
    filename = url.split('/')[-1]
    return filename.split('?')[0]


# verify the md5 of a file
def verify_md5(filepath, md5):
    computed_md5 = ''

    with open(filepath, 'rb') as f:
        data = f.read()
        computed_md5 = hashlib.md5(data).hexdigest()

    return computed_md5 == md5


# list all available platforms
def list_platforms(data):
    downloads = []
    for machine_name in data:
        downloads.extend(data[machine_name]['downloads'])

    platforms = list(set([x['platform'] for x in downloads]))
    platforms.sort()

    print_title('Platforms')
    for platform in platforms:
        print '%s' % platform

    print ''


# list all available products
def list_product_names(data):
    products = [(data[machine_name]['human_name'], machine_name, data[machine_name]['bundles']) for machine_name in data]
    products.sort()

    print_title('Products')
    for product in products:
        print '%s; %s [%s]' % (product[0], product[1], ', '.join(map(str, product[2])))

    print ''


# process all products
def process_download_products(dirs, products, dry):
    size = 0

    for product in products:
        print_title(product['human_name'])
        dirs.append(product['machine_name'])

        try:
            size += process_download_downloads(list(dirs), product['downloads'], dry)
        except Exception, e:
            print 'error[download/products]', e

        dirs.pop()

    return size


# process all downloads
def process_download_downloads(dirs, downloads, dry):
    size = 0

    for download in downloads:
        dirs.append(download['machine_name'])

        try:
            size += process_download_files(list(dirs), download['files'], dry)
        except Exception, e:
            print 'error[download/downloads]', e

        dirs.pop()

    return size


# process all files
def process_download_files(dirs, files, dry):
    size = 0

    for f in files:
        if 'arch' in f:
            dirs.append(f['arch'])

        if not dry:
            try:
                os.makedirs(os.path.join(*dirs))
            except Exception, e:
                pass

        url = f['url']
        dirpath = os.path.join(*dirs)

        filename = get_filename(url)
        filepath = os.path.join(dirpath, filename)

        if os.path.exists(filepath) and verify_md5(filepath, f['md5']):
            print 'Up to date: %s' % filename
        else:
            size += f['file_size']
            if dry:
                print 'Will download: %s (%s)' % (filename, pretty_file_size(f['file_size']))
            else:
                try:
                    download_file(url, dirpath, filename)
                    if not verify_md5(filepath, f['md5']):
                        print 'md5 missmatch for %s!' % filename
                except Exception, e:
                    print 'error[download/files]', e

        if 'arch' in f:
            dirs.pop()

    return size

def main():
    parser = argparse.ArgumentParser(description='Download Humble Bundle stuff!')
    parser.add_argument('-r', '--refresh-keys', help='refresh gamekeys', action='store_true')
    parser.add_argument('-l', '--list', help='list all available products', action='store_true')
    parser.add_argument('-d', '--download', help='download the specified products or all if none is given', nargs='*')
    parser.add_argument('-p', '--platform', help='limit the selection to specified platforms', nargs='*')
    parser.add_argument('--dry', help='show a preview of what will be downloaded', action='store_true')

    args = parser.parse_args()

    # load up the index file
    force_refresh = False
    try:
        with open(__GAMEKEY_FILE__ % 'index', 'r') as f:
            data = json.load(f)
    except Exception, e:
        print 'Failed to read index file, forcing refresh.'
        force_refresh = True

    if args.list:
        list_platforms(data['products'])
        list_product_names(data['products'])
    else:
        if args.refresh_keys or force_refresh:
            refresh_index()

        # build initial list
        products = [data['products'][key] for key in data['products']]

        # filter out only things the user wants
        if args.download and len(args.download) > 0:
            downloads = [s.lower() for s in args.download]
            products = [product for product in products if any(dl in product['machine_name'].lower() or dl in product['human_name'].lower() for dl in downloads)]

        # filter out only platforms the user wants
        if args.platform and len(args.platform) > 0:
            platforms = [s.lower() for s in args.platform]

            for product in products:
                product['downloads'] = [download for download in product['downloads'] if any(platform in download['platform'] for platform in platforms)]

            products = [product for product in products if product['downloads']]

        # set up the root directory
        dirs = [__DOWNLOAD_DIR__]

        # process all products
        size = process_download_products(dirs, products, args.dry)

        # print total download amount
        print '\nTotal: %s' % pretty_file_size(size)


if __name__ == '__main__':
    main()
