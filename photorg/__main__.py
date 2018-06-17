import argparse
import magic
import os
import exifread
from datetime import datetime
import shutil
import re


class DatetimePattern:
    """
    combines regular expressions and strftime markers
    to get a datetime from a string.
    """
    PLACEHOLDERS = {
        '%Y': r'\d{4}',
        '%y': r'\d{2}',
        '%m': r'\d{1,2}',
        '%d': r'\d{1,2}',
        '%H': r'\d{1,2}',
        '%I': r'\d{1,2}',
        '%M': r'\d{1,2}',
        '%S': r'\d{1,2}',
        '%p': r'am|pm|AM|PM',
    }

    def __find_placeholder(self, pattern, idx):
        midx = len(pattern)
        mph = None
        mpre = None
        for ph, pre in self.PLACEHOLDERS.items():
            pidx = pattern.find(ph, idx)
            if pidx >= 0 and pidx <= midx:
                midx = pidx
                mph = ph
                mpre = pre
        return (mph, mpre, midx)

    def __init__(self, pattern):
        self.__placeholders = []
        idx = 0
        while True:
            ph, pre, idx = self.__find_placeholder(pattern, idx)
            if not ph:
                break
            pre = "(" + pre + ")"
            pattern = pattern[0:idx] + pre + pattern[idx+len(ph):]
            self.__placeholders.append(ph)
            idx += len(pre)
        self.__re = re.compile(pattern)

    def __process(self, string, m):
        if not m:
            return None
        phs = list(self.__placeholders)
        phs.reverse()
        i = 0
        timefrmt = string
        for ph in phs:
            s = m.span(len(phs)-i)
            timefrmt = timefrmt[0:s[0]] + ph + timefrmt[s[1]:]
            i += 1
        return datetime.strptime(string, timefrmt)

    def search(self, string):
        m = re.search(self.__re, string)
        return self.__process(string, m)

    def match(self, string):
        m = re.match(self.__re, string)
        return self.__process(string, m)


TIME_TAGS = ('DateTimeOriginal', )
FILE_PATTERNS = (
    DatetimePattern('WhatsApp Image %Y-%m-%d at %I.%M.%S %p'),
    DatetimePattern('WhatsApp Image %Y-%m-%d at %H.%M.%S'),
    DatetimePattern('IMG_%Y%m%d_%H%M%S'),
    DatetimePattern('IMG-%Y%m%d-'),
    DatetimePattern('/%Y-%m-%d.*/'),
    DatetimePattern('-%d-%m-%Y( |\.)'),
)


def get_file_datetime(fpath):
    with open(fpath, 'rb') as fh:
        tags = exifread.process_file(fh, details=False)
    for key, val in tags.items():
        for ttag in TIME_TAGS:
            if not key.endswith(ttag):
                continue
            try:
                return datetime.strptime(str(val), '%Y:%m:%d %H:%M:%S')
            except Exception:
                pass
    for pattern in FILE_PATTERNS:
        time = pattern.search(fpath)
        if time:
            return time


def get_output_path(fpath, fdir, args):
    time = get_file_datetime(fpath)
    faildir = os.path.join(args.outdir, args.faildir)
    if not time:
        opath = os.path.relpath(fpath, fdir)
        print("failed %s" % (opath, ))
        opath = os.path.join(faildir, opath)
        return opath
    return args.pattern.format(
        time=time,
        filename=os.path.basename(fpath),
        ext=os.path.splitext(fpath)[1].lower()
    )


def main():
    parser = argparse.ArgumentParser(description='organize your photo collection')
    parser.add_argument('path', nargs='+', help='directory with photos', default='.')
    parser.add_argument('-o,--outdir', dest='outdir', help='output directory')
    parser.add_argument('-d,--dry', dest='dry', action='store_true', help='run without changing any files')
    parser.add_argument('-p,--pattern', dest='pattern', help='output file pattern', default="{time:%Y}/{time:%Y-%m-%d}/{time:%Y-%m-%d_%H-%M}{ext}")
    parser.add_argument('-f,--faildir', dest='faildir', help='fail output directory', default="./failed")
    args = parser.parse_args()
    if not args.outdir:
        args.outdir = args.path[0]

    mime = magic.Magic(mime=True)
    opaths = []
    for fdir in args.path:
        print("processing %s to %s..." % (fdir, args.outdir))
        for froot, _, fpaths in os.walk(fdir):
            for fpath in fpaths:
                fpath = os.path.join(froot, fpath)
                fmime = mime.from_file(fpath)
                if fmime.startswith("image/"):
                    opath = get_output_path(fpath, fdir, args)
                    opath = os.path.join(args.outdir, opath)
                    i = 1
                    bopath, ext = os.path.splitext(opath)
                    while opath in opaths:
                        opath = "%s-%s%s" % (bopath, i, ext)
                        i += 1
                    opaths.append(opath)
                    if not args.dry:
                        odir = os.path.dirname(opath)
                        if odir:
                            os.makedirs(odir, exist_ok=True)
                        shutil.copyfile(fpath, opath)


if __name__ == "__main__":
    main()
