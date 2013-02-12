import sys
import os
import re
import time
from datetime import timedelta

from svtplay.utils import get_http_data, select_quality
from svtplay.output import progressbar, progress_stream
from svtplay.log import log

if sys.version_info > (3, 0):
    from io import BytesIO as StringIO
else:
    from StringIO import StringIO

def download_hls(options, url, baseurl=None):
    data = get_http_data(url)
    globaldata, files = parsem3u(data)
    streams = {}
    for i in files:
        streams[int(i[1]["BANDWIDTH"])] = i[0]

    test = select_quality(options, streams)
    m3u8 = get_http_data(test)
    globaldata, files = parsem3u(m3u8)
    encrypted = False
    key = None
    try:
        keydata = globaldata["KEY"]
        encrypted = True
    except:
        pass

    if encrypted:
        try:
            from Crypto.Cipher import AES
        except ImportError:
            log.error("You need to install pycrypto to download encrypted HLS streams")
            sys.exit(2)
        match = re.search("URI=\"(http://.*)\"", keydata)
        key = get_http_data(match.group(1))
        rand = os.urandom(16)
        decryptor = AES.new(key, AES.MODE_CBC, rand)
    n = 1
    if options.output != "-":
        extension = re.search("(\.[a-z0-9]+)$", options.output)
        if not extension:
            options.output = "%s.ts" % options.output
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    start = time.time()
    estimated = ""
    for i in files:
        item = i[0]
        if options.output != "-":
            progressbar(len(files), n, estimated)
        if item[0:5] != "http:":
            item = "%s/%s" % (baseurl, item)
        data = get_http_data(item)
        if encrypted:
            lots = StringIO(data)

            plain = b""
            crypt = lots.read(1024)
            decrypted = decryptor.decrypt(crypt)
            while decrypted:
                plain += decrypted
                crypt = lots.read(1024)
                decrypted = decryptor.decrypt(crypt)
            data = plain

        file_d.write(data)
        now = time.time()
        dt = now - start
        et = dt / (n + 1) * len(files)
        rt = et - dt
        td = timedelta(seconds = int(rt))
        estimated = "Estimated Remaining: " + str(td)
        n += 1

    if options.output != "-":
        file_d.close()
        progress_stream.write('\n')

def parsem3u(data):
    if not data.startswith("#EXTM3U"):
        raise ValueError("Does not apprear to be a ext m3u file")

    files = []
    streaminfo = {}
    globdata = {}

    data = data.replace("\r", "\n")
    for l in data.split("\n")[1:]:
        if not l:
            continue
        if l.startswith("#EXT-X-STREAM-INF:"):
            #not a proper parser
            info = [x.strip().split("=", 1) for x in l[18:].split(",")]
            streaminfo.update({info[1][0]: info[1][1]})
        elif l.startswith("#EXT-X-ENDLIST"):
            break
        elif l.startswith("#EXT-X-"):
            globdata.update(dict([l[7:].strip().split(":", 1)]))
        elif l.startswith("#EXTINF:"):
            dur, title = l[8:].strip().split(",", 1)
            streaminfo['duration'] = dur
            streaminfo['title'] = title
        elif l[0] == '#':
            pass
        else:
            files.append((l, streaminfo))
            streaminfo = {}

    return globdata, files

