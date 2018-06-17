import argparse
import magic
import os
import piexif
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


class Organizer:

    FILE_PATTERNS = (
        DatetimePattern('WhatsApp Image %Y-%m-%d at %I.%M.%S %p'),
        DatetimePattern('WhatsApp Image %Y-%m-%d at %H.%M.%S'),
        DatetimePattern('IMG_%Y%m%d_%H%M%S'),
        DatetimePattern('IMG-%Y%m%d-'),
        DatetimePattern('/%Y-%m-%d.*/'),
        DatetimePattern('-%d-%m-%Y( |\.)'),
    )
    EXIF_TAG = "Exif"
    DATETIME_ID = 36867

    def __init__(self):
        self.__mime = magic.Magic(mime=True)
        self.__opaths = None

    def __get_exif_datetime(self, path):
        try:
            data = piexif.load(path)
        except Exception:
            return None
        if self.EXIF_TAG not in data:
            return None
        data = data[self.EXIF_TAG]
        if self.DATETIME_ID not in data:
            return None
        data = data[self.DATETIME_ID].decode('utf-8')
        return datetime.strptime(data, '%Y:%m:%d %H:%M:%S')

    def __get_pattern_datetime(self, path):
        for pattern in self.FILE_PATTERNS:
            time = pattern.search(path)
            if time:
                return time

    def __get_output_path(self, path, time, pattern):
        return pattern.format(
            time=time,
            filename=os.path.basename(path),
            ext=os.path.splitext(path)[1].lower()
        )

    def __process(self, path, pattern, fromdir, outdir=None, faildir=None, dry=False):
        time = self.__get_exif_datetime(path)
        if not time:
            time = self.__get_pattern_datetime(path)
        opath = None
        if time:
            opath = self.__get_output_path(path, time, pattern)
        elif faildir:
            if fromdir:
                opath = os.path.relpath(path, fromdir)
            print("failed %s" % (opath, ))
            opath = os.path.join(faildir, opath)

        if not opath:
            return None
        opath = os.path.join(outdir, opath)
        i = 1
        bopath, ext = os.path.splitext(opath)
        while opath in self.__opaths:
            opath = "%s-%s%s" % (bopath, i, ext)
            i += 1
        if dry:
            print("%s -> %s" % (path, opath))
        else:
            odir = os.path.dirname(opath)
            if odir:
                os.makedirs(odir, exist_ok=True)
            shutil.copyfile(path, opath)
        return opath

    def run(self, args):
        self.__opaths = []
        for fromdir in args.path:
            print("processing %s to %s..." % (fromdir, args.outdir))
            outdir = os.path.join(fromdir, args.outdir)
            faildir = os.path.join(outdir, args.faildir)
            for froot, _, fpaths in os.walk(fromdir):
                for fpath in fpaths:
                    fpath = os.path.join(froot, fpath)
                    fmime = self.__mime.from_file(fpath)
                    if not fmime.startswith("image/"):
                        continue
                    opath = self.__process(
                        path=fpath,
                        pattern=args.pattern,
                        fromdir=fromdir,
                        outdir=outdir,
                        faildir=faildir,
                        dry=args.dry)
                    if opath:
                        self.__opaths.append(opath)


def main():
    parser = argparse.ArgumentParser(description='organize your photo collection')
    parser.add_argument('path', nargs='+', help='directory with photos', default='.')
    parser.add_argument('-o,--outdir', dest='outdir', help='output directory')
    parser.add_argument('-d,--dry', dest='dry', action='store_true', help='run without changing any files')
    parser.add_argument('-p,--pattern', dest='pattern', help='output file pattern', default="{time:%Y}/{time:%Y-%m-%d}/{time:%Y-%m-%d_%H-%M}{ext}")
    parser.add_argument('-f,--faildir', dest='faildir', help='fail output directory', default="./failed")
    args = parser.parse_args()
    org = Organizer()
    org.run(args)


if __name__ == "__main__":
    main()
