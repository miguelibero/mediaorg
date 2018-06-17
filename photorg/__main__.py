import argparse
import magic
import os
import piexif
from datetime import datetime
import time
import shutil
import re
import parsedatetime


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
    SEPARATOR = ';'

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
        self.__pattern = pattern
        timefmt = None
        try:
            pattern, timefmt = pattern.split(self.SEPARATOR, 2)
        except ValueError:
            pass
        self.__timefmt = timefmt
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
        val = datetime.strptime(string, timefrmt)
        if self.__timefmt:
            cal = parsedatetime.Calendar()
            val, _ = cal.parse(val.strftime(self.__timefmt))
            val = datetime.fromtimestamp(time.mktime(val))
        return val

    def search(self, string):
        m = re.search(self.__re, string)
        return self.__process(string, m)

    def match(self, string):
        m = re.match(self.__re, string)
        return self.__process(string, m)

    def __repr__(self):
        return "<DatetimePattern %s>" % (self.__pattern,)

    def __str__(self):
        return self.__repr__()


class OutputPattern:
    REPLS = (
        (re.compile(r"\{([^:]+):([^}]*)\}"), "\\2"),
        (re.compile(r"\{([^}]*)\}"), "[^/]*")
    )

    def __init__(self, pattern):
        self.__pattern = pattern
        repattern = pattern
        for p, r in self.REPLS:
            repattern = re.sub(p, r, repattern)
        self.__re = DatetimePattern(repattern)

    def format(self, path, time):
        _, ext = os.path.splitext(path)
        ext = ext.lower() if ext else ""
        return self.__pattern.format(
            time=time,
            filename=os.path.basename(path),
            ext=ext
        )

    def match(self, path, basepath=None):
        if basepath:
            path = os.path.relpath(path, basepath)
        return self.__re.match(path)

    def __repr__(self):
        return "<OutputPattern %s>" % (self.__pattern,)

    def __str__(self):
        return self.__repr__()


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
    EXIF_DATE_FORMAT = '%Y:%m:%d %H:%M:%S'

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
        try:
            return datetime.strptime(data, self.EXIF_DATE_FORMAT)
        except ValueError:
            pass

    def __save_exif_datetime(self, path, time):
        try:
            data = piexif.load(path)
        except Exception:
            return
        if self.EXIF_TAG not in data:
            data[self.EXIF_TAG] = {}
        exif = data[self.EXIF_TAG]
        exif[self.DATETIME_ID] = time.strftime(self.EXIF_DATE_FORMAT)
        piexif.insert(piexif.dump(data), path)

    def __get_pattern_datetime(self, path, patterns):
        for pattern in patterns:
            time = pattern.search(path)
            if time:
                return (time, pattern)
        return (None, None)

    def __log(self, msg, *args):
        print(msg % args)

    def __process(
        self, path, outpattern, fromdir,
        inpatterns=None, outdir=None, faildir=None,
        dry=False, verbose=False, move=False
    ):
        if outpattern.match(path, outdir):
            self.__log("skipping %s...", path)
            return

        save = False
        time = self.__get_exif_datetime(path)
        if time and verbose:
            self.__log("%s: exif %s", path, time)
        if not time and inpatterns:
            time, pattern = self.__get_pattern_datetime(path, inpatterns)
            if time:
                save = True
                if verbose:
                    self.__log("%s: %s %s", path, pattern, time)

        opath = None
        if time:
            opath = outpattern.format(path, time)
        elif faildir:
            if fromdir:
                opath = os.path.relpath(path, fromdir)
            self.__log("failed %s", path)
            opath = os.path.join(faildir, opath)

        if not opath:
            return None
        opath = os.path.join(outdir, opath)
        if opath == path:
            if verbose:
                self.__log("skipping operation %s...", opath)
        else:
            i = 1
            bopath, ext = os.path.splitext(opath)
            while opath in self.__opaths or os.path.exists(opath):
                opath = "%s-%s%s" % (bopath, i, ext)
                i += 1
            if verbose:
                self.__log("%s -> %s", path, opath)
        if not dry:
            if opath != path:
                odir = os.path.dirname(opath)
                if odir:
                    os.makedirs(odir, exist_ok=True)
                if move:
                    shutil.move(path, opath)
                else:
                    shutil.copyfile(path, opath)
            if save:
                if verbose:
                    self.__log("saving %s %s...", opath, time)
                self.__save_exif_datetime(opath, time)

        return opath

    def run(self, args):
        self.__opaths = []
        inpatterns = list(self.FILE_PATTERNS)
        if args.inpattern:
            for pattern in args.inpattern:
                inpatterns.append(DatetimePattern(pattern))
        outpattern = OutputPattern(args.outpattern)
        for fromdir in args.path:
            if args.outdir:
                outdir = os.path.join(fromdir, args.outdir)
            else:
                outdir = fromdir
            
            move = outdir == fromdir
            if outdir == fromdir:
                print("processing %s..." % (fromdir,))
            else:
                print("processing %s to %s..." % (fromdir, outdir))
            faildir = os.path.join(outdir, args.faildir)
            for froot, _, fpaths in os.walk(fromdir):
                for fpath in fpaths:
                    fpath = os.path.join(froot, fpath)
                    fmime = self.__mime.from_file(fpath)
                    if not fmime.startswith("image/"):
                        continue
                    opath = self.__process(
                        path=fpath,
                        inpatterns=inpatterns,
                        outpattern=outpattern,
                        fromdir=fromdir,
                        outdir=outdir,
                        faildir=faildir,
                        dry=args.dry,
                        verbose=args.verbose,
                        move=move)
                    if opath:
                        self.__opaths.append(opath)


def main():
    parser = argparse.ArgumentParser(
        description='organize your photo collection')
    parser.add_argument(
        'path', action='append', help='directory with photos', default=[])
    parser.add_argument(
        '-o,--outdir', dest='outdir', help='output directory')
    parser.add_argument(
        '-d,--dry', dest='dry', action='store_true',
        help='run without changing any files')
    parser.add_argument(
        '-v,--verbose', dest='verbose', action='store_true',
        help='print more stuff')
    parser.add_argument(
        '-p,--outpattern', dest='outpattern', help='output file pattern',
        default="{time:%Y}/{time:%Y-%m-%d}/{time:%Y-%m-%d_%H-%M}{ext}")
    parser.add_argument(
        '-f,--faildir', dest='faildir', help='fail output directory',
        default="./failed")
    parser.add_argument(
        '--inpattern', action='append', dest="inpattern",
        help='add aditional path pattern to find datetime')
    args = parser.parse_args()
    org = Organizer()
    org.run(args)


if __name__ == "__main__":
    main()
