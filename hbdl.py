#!/usr/bin/env python3

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
NOTE 2: I really was a newbie... need to clean up all the silly things... eventually
'''

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

import http.cookiejar
import requests
import requests.utils

__GAMEKEY_DIR__ = 'gamekeys'
__GAMEKEY_FILE__ = __GAMEKEY_DIR__ + '/{}.json'
__DOWNLOAD_DIR__ = 'downloads'


def print_msg(*args):
    message = ' '.join([str(arg) for arg in args])
    print(message.encode(print_msg.encoding, errors='replace').decode(print_msg.encoding))


print_msg.encoding = sys.stdout.encoding if sys.stdout.encoding else 'utf-8'


# prettify the file size with a suffix
def pretty_file_size(size):
    units = ('B', 'KiB', 'MiB', 'GiB')
    i = 0

    while size >= 1024.0:
        size /= 1024.0
        i += 1

    return '{:.2f} {}'.format(size, units[i])


# download a file and save it to the disk
def download_file(url, directory, filename):
    stream = urllib.request.urlopen(url)

    with open(os.path.join(directory, filename), 'wb') as f:
        meta = stream.info()
        file_size = int(meta.get('Content-Length'))
        print('Downloading: {}'.format(filename))

        file_size_dl = 0
        block_size = 8192
        while True:
            buff = stream.read(block_size)
            if not buff:
                break

            file_size_dl += len(buff)
            f.write(buff)
            status = r'  {:11s} / {:11s} [{:6.2f}%]'.format(pretty_file_size(file_size_dl), pretty_file_size(file_size), file_size_dl * 100.0 / file_size)
            status = status + chr(8) * (len(status) + 1)
            print(status, end=' ')

    print('')


# refresh the index file (download new versions of the gamekeys)
def refresh_index():
    pattern_home = 'www.humblebundle.com/home'
    pattern_login = 'www.humblebundle.com/login'
    pattern_guard = 'www.humblebundle.com/user/humbleguard'

    url_home = 'https://www.humblebundle.com/home'
    url_login = 'https://www.humblebundle.com/processlogin'
    url_guard = 'https://www.humblebundle.com/user/humbleguard'
    url_order = 'https://www.humblebundle.com/api/v1/order/{}'

    # make sure the directory exists
    try:
        os.makedirs(__GAMEKEY_DIR__)
    except Exception as e:
        pass

    # set up the cookie jar
    cj = http.cookiejar.MozillaCookieJar('cookies.txt')
    try:
        cj.load('cookies.txt')
    except Exception as e:
        pass
    cj.save('cookies.txt', ignore_discard=False, ignore_expires=False)

    # start a new session
    with requests.Session() as session:
        # override the cookie jar
        session.cookies = cj

        # open /home
        print_msg('Opening /home...')
        req = session.get(url_home)

        # stop the collection if we didn't land on /home
        if pattern_home not in req.url:
            print_msg('Did not land on /home, stopping!')
            print_msg('  {}'.format(req.url))
            print_msg('')
            raise Exception('Export the cookies from your browser and put them into the cookies.txt file.')

        # save the cookie jar
        cj.save('cookies.txt', ignore_discard=False, ignore_expires=False)

        # read the content
        content = req.text

        # find the gamekeys
        gamekeys = re.findall(r'var gamekeys\s*=\s*\[(.*?)\]', content)[0]
        gamekeys = re.findall(r'"([^"]+)"', gamekeys)

        # grab all the gamekey data
        key_index = 0
        print_msg('Collecting keys...')

        data = {}
        data['bundles'] = {}
        data['products'] = {}

        for gamekey in gamekeys:
            print_msg('  {}/{}'.format(key_index + 1, len(gamekeys)))
            try:
                req = session.get(url_order.format(gamekey))
                content = req.text

                with open(__GAMEKEY_FILE__.format(gamekey), 'w') as f:
                    json.dump(json.loads(content), f, indent=2, sort_keys=True)

                process_gamekey(data, gamekey, json.loads(content))
            except Exception as e:
                print_msg('error[refresh] {}'.format(e))

            key_index += 1

        # save the index file
        with open(__GAMEKEY_FILE__.format('index'), 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)

        # save the cookie jar
        cj.save('cookies.txt', ignore_discard=False, ignore_expires=False)

        # we're done
        print_msg('Done.')

        return data


# parse out the important bits
def process_gamekey(data, gamekey, keydata):
    bundle_name = keydata['product']['machine_name']
    data['bundles'][bundle_name] = {}
    data['bundles'][bundle_name]['name'] = keydata['product']['human_name']
    data['bundles'][bundle_name]['key'] = gamekey

    print_msg('    {} ({})'.format(keydata['product']['human_name'], len(keydata['subproducts'])))
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
    elif 'asm_config' in download_struct and 'asm_manifest' in download_struct:
        # TODO: download the files
        print_msg('[?] Skipping asm.js resources...')
    else:
        print_msg('[!] Skipping...')
        from pprint import pprint
        pprint(download_struct)

    return data


# print a fancy title
def print_title(title):
    print_msg('================================================================')
    print_msg('== {}'.format(title))
    print_msg('================================================================')


# get the file name from a URL
def get_filename(url):
    filename = url.split('/')[-1]
    return filename.split('?')[0]


# verify the md5 of a file
def verify_md5(filepath, md5):
    computed_md5 = ''

    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            hasher.update(data)
    computed_md5 = hasher.hexdigest()

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
        print_msg('{}'.format(platform))

    print_msg('')


# list all available products
def list_product_names(data):
    products = [(data[machine_name]['human_name'], machine_name, data[machine_name]['bundles']) for machine_name in data]
    products.sort()

    print_title('Products')
    for product in products:
        print_msg('{}; {} [{}]'.format(product[0], product[1], ', '.join(map(str, product[2]))))

    print_msg('')


# process all products
def process_download_products(dirs, products, run):
    size = 0

    for product in products:
        print_title(product['human_name'])
        dirs.append(product['machine_name'])

        try:
            size += process_download_downloads(list(dirs), product['downloads'], run)
        except Exception as e:
            print_msg('error[download/products] {}'.format(e))

        dirs.pop()

    return size


# process all downloads
def process_download_downloads(dirs, downloads, run):
    size = 0

    for download in downloads:
        dirs.append(download['machine_name'])

        try:
            size += process_download_files(list(dirs), download['files'], run)
        except Exception as e:
            print_msg('error[download/downloads] {}'.format(e))

        dirs.pop()

    return size


knownhashes = []

# process all files
def process_download_files(dirs, files, run):
    global knownhashes
    size = 0

    for f in files:
        if 'arch' in f:
            dirs.append(f['arch'])

        if run:
            try:
                os.makedirs(os.path.join(*dirs))
            except Exception as e:
                pass

        url = f['url']
        dirpath = os.path.join(*dirs)

        filename = get_filename(url)
        filepath = os.path.join(dirpath, filename)

        save = False
        try:
            with open(__GAMEKEY_FILE__.format('index'), 'r') as fh:
                data = json.load(fh)
                if not 'downloads' in data:
                    data['downloads'] = {}
        except Exception as e:
            pass

        exists = False
        if data and f['md5'] in data['downloads']:
            path = data['downloads'][f['md5']]
            if os.path.exists(path) and verify_md5(path, f['md5']):
                exists = True
            else:
                data['downloads'].pop(f['md5'], None)

        if f['md5'] in knownhashes:
            exists = True
        else:
            knownhashes.append(f['md5'])

        if os.path.exists(filepath) and verify_md5(filepath, f['md5']) or exists:
            print_msg('Up to date: {}'.format(filename))

            if data and f['md5'] not in data['downloads']:
                save = True
                data['downloads'][f['md5']] = filepath.replace(os.path.sep, '/')
        else:
            size += f['file_size']
            if not run:
                print_msg('Will download: {} ({})'.format(filename, pretty_file_size(f['file_size'])))
            else:
                try:
                    download_file(url, dirpath, filename)
                    if not verify_md5(filepath, f['md5']):
                        print_msg('md5 missmatch for {}!'.format(filename))
                    elif data:
                        save = True
                        data['downloads'][f['md5']] = filepath.replace(os.path.sep, '/')

                except urllib.error.HTTPError as e:
                    if e.code == 403:
                        print_msg('error[download/files] download link expired, refresh the index')
                    else:
                        print_msg('error[download/files] {}'.format(e))
                except Exception as e:
                    print_msg('error[download/files] {}'.format(e))

        if save:
            with open(__GAMEKEY_FILE__.format('index'), 'w') as fh:
                json.dump(data, fh, indent=2, sort_keys=True)

        if 'arch' in f:
            dirs.pop()

    return size


def main():
    parser = argparse.ArgumentParser(description='Download Humble Bundle stuff!')
    parser.add_argument('-r', '--refresh-keys', help='refresh gamekeys', action='store_true')
    parser.add_argument('-l', '--list', help='list all available products', action='store_true')
    parser.add_argument('-d', '--download', help='filter the products by game name (machine and human)', nargs='*')
    parser.add_argument('-n', '--filename', help='filter the products by filename', nargs='*')
    parser.add_argument('-p', '--platform', help='limit the selection to specified platforms', nargs='*')
    parser.add_argument('-f', '--run', help='initiate the download (without this flag it is a dry run)', action='store_true')

    args = parser.parse_args()

    # load up the index file
    force_refresh = False
    try:
        with open(__GAMEKEY_FILE__.format('index'), 'r') as f:
            data = json.load(f)
    except Exception as e:
        print_msg('Failed to read index file, forcing refresh.')
        force_refresh = True

    if args.list:
        list_platforms(data['products'])
        list_product_names(data['products'])
    else:
        if args.refresh_keys or force_refresh:
            data = refresh_index()

        # build initial list
        products = [data['products'][key] for key in data['products']]

        # filter out only products the user wants
        if args.download and len(args.download) > 0:
            downloads = [s.lower() for s in args.download]
            products = [product for product in products if any(dl in product['machine_name'].lower() or dl in product['human_name'].lower() for dl in downloads)]

        # filter out only filenames the user wants
        if args.filename and len(args.filename) > 0:
            filenames = [s.lower() for s in args.filename]
            for product in products:
                for dl in product['downloads']:
                    dl['files'] = [entry for entry in dl['files'] if any(fn in get_filename(entry.get('url', '')) for fn in filenames)]
            products = [product for product in products if any(dl for dl in product['downloads'] if len(dl['files']) > 0)]

        # filter out only platforms the user wants
        if args.platform and len(args.platform) > 0:
            platforms = [s.lower() for s in args.platform]

            for product in products:
                product['downloads'] = [download for download in product['downloads'] if any(platform in download['platform'] for platform in platforms)]

            products = [product for product in products if product['downloads']]

        # set up the root directory
        dirs = [__DOWNLOAD_DIR__]

        # process all products
        size = process_download_products(dirs, products, args.run)

        # print total download amount
        print_msg('\nTotal: {}'.format(pretty_file_size(size)))


if __name__ == '__main__':
    main()
