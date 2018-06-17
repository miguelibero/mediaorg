import argparse
import os
import piexif
from datetime import datetime
import shutil
import re
import parsedatetime
import magic


class DatetimePattern:
    """
    combines regular expressions and strftime markers
    to get a datetime from a string.
    """

    PLACEHOLDERS = {
        '%Y': (r'\d{4}', 0),
        '%y': (r'\d{2}', 0, lambda v, w: 2000+int(v)),
        '%m': (r'\d{1,2}', 1),
        '%d': (r'\d{1,2}', 2),
        '%H': (r'\d{1,2}', 3),
        '%I': (r'\d{1,2}', 3),
        '%M': (r'\d{1,2}', 4),
        '%S': (r'\d{1,2}', 5),
        '%p': (
            r'am|pm|AM|PM', 3,
            lambda v, w: w + (12 if v.lower() == "pm" else 0))
    }
    SEPARATOR = ';'

    def __find_placeholder(self, pattern, idx):
        midx = len(pattern)
        mph = None
        mpre = None
        for ph, phdata in self.PLACEHOLDERS.items():
            pidx = pattern.find(ph, idx)
            if pidx >= 0 and pidx <= midx:
                midx = pidx
                mph = ph
                mpre = phdata[0]
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

    def __get_placeholder_values(self, m):
        if not m:
            return None
        vals = {}
        i = 0
        for ph in self.__placeholders:
            val = m.group(i+1)
            if ph in vals:
                if vals[ph] != val:
                    raise ValueError("not all placeholder values are the same")
            else:
                vals[ph] = val
            i += 1
        return vals

    def __placeholder_values_to_time(self, vals):
        struct = [1, 1, 1, 0, 0, 0, 0]
        for ph, pdata in self.PLACEHOLDERS.items():
            if len(pdata) < 2:
                continue
            pos = pdata[1]
            w = int(struct[pos])
            if ph in vals:
                if len(pdata) > 2:
                    w = pdata[2](vals[ph], w)
                else:
                    w = int(vals[ph])
            struct[pos] = w
        return datetime(*struct)

    def __process(self, m):
        if not m:
            return None
        vals = self.__get_placeholder_values(m)
        timeval = self.__placeholder_values_to_time(vals)
        if self.__timefmt:
            cal = parsedatetime.Calendar()
            timeval, _ = cal.parse(timeval.strftime(self.__timefmt))
            timeval = datetime(*timeval[:7])
        return timeval

    def search(self, string):
        m = re.search(self.__re, string)
        return self.__process(m)

    def match(self, string):
        m = re.match(self.__re, string)
        return self.__process(m)

    def __repr__(self):
        return "<DatetimePattern %s>" % (self.__pattern,)

    def __str__(self):
        return self.__repr__()


class OutputPattern:
    """
    converts a string.format pattern into a DatetimePattern
    used to format output paths and to check if the path
    is already an output path
    """

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

    def format(self, path, timeval):
        _, ext = os.path.splitext(path)
        ext = ext.lower() if ext else ""
        return self.__pattern.format(
            time=timeval,
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


class MediaFile:

    METHOD_EXIF = "exif"
    METHOD_PATTERN = "pattern"
    METHOD_MANUAL = "manual"

    EXIF_TAG = "Exif"
    DATETIME_ID = 36867
    EXIF_DATE_FORMAT = '%Y:%m:%d %H:%M:%S'

    TIME_PATTERNS = (
        DatetimePattern('WhatsApp Image %Y-%m-%d at %I.%M.%S %p'),
        DatetimePattern('WhatsApp Image %Y-%m-%d at %H.%M.%S'),
        DatetimePattern('IMG_%Y%m%d_%H%M%S'),
        DatetimePattern('IMG-%Y%m%d-'),
        DatetimePattern('/%Y-%m-%d.*/'),
        DatetimePattern('-%d-%m-%Y( |\.)'),
    )

    def __init__(self, path, patterns=None):
        if not isinstance(path, str):
            raise ValueError("path needs to be a string")
        self.__path = path
        self.__time = None
        self.__method = None
        self.__now = datetime.now()
        if not patterns:
            patterns = []
        patterns.extend(self.TIME_PATTERNS)
        self.__patterns = patterns

    def get_method(self):
        self.get_time()
        return self.__method

    def get_path(self):
        return self.__path

    def get_pattern(self):
        self.get_time()
        return self.__pattern

    def get_time(self):
        if self.__time:
            return self.__time
        self.__time = self.__get_exif_datetime()
        if self.__time:
            self.__method = self.METHOD_EXIF
            return self.__time
        if self.__patterns:
            self.__time, self.__pattern = self.__get_pattern_datetime()
            if self.__time:
                self.__method = self.METHOD_PATTERN
        return self.__time

    def set_time(self, time):
        self.__method = self.METHOD_MANUAL
        self.__time = time

    def __get_exif_datetime(self):
        try:
            data = piexif.load(self.__path)
        except Exception:
            return None
        if self.EXIF_TAG not in data:
            return None
        data = data[self.EXIF_TAG]
        if self.DATETIME_ID not in data:
            return None
        data = data[self.DATETIME_ID].decode('utf-8')
        try:
            timeval = datetime.strptime(data, self.EXIF_DATE_FORMAT)
            if timeval < self.__now:
                return timeval
        except ValueError:
            pass

    def __save_exif_datetime(self, path=None):
        if not path:
            path = self.__path
        data = piexif.load(path)
        if self.EXIF_TAG not in data:
            data[self.EXIF_TAG] = {}
        exif = data[self.EXIF_TAG]
        exif[self.DATETIME_ID] = self.__time.strftime(self.EXIF_DATE_FORMAT)
        piexif.insert(piexif.dump(data), path)

    def __get_pattern_datetime(self):
        for pattern in self.__patterns:
            timeval = pattern.search(self.__path)
            if timeval and timeval < self.__now:
                return (timeval, pattern)
        return (None, None)

    def save(self, path, move=False):
        pdir = os.path.dirname(path)
        if dir:
            os.makedirs(pdir, exist_ok=True)
        if move:
            shutil.move(self.__path, path)
            self.__path = path
        else:
            shutil.copyfile(self.__path, path)
        if self.__method == self.METHOD_EXIF:
            return True
        try:
            self.__save_exif_datetime(path)
            self.__method = self.METHOD_EXIF
            return True
        except Exception:
            return False

    def __path_exists(self, path, paths=None):
        if paths and path in paths:
            return True
        if os.path.exists(path):
            return True
        return False

    def get_outpath(
        self, pattern, outdir=None, fromdir=None,
        faildir=None, outpaths=None
    ):
        path = None
        if self.__time:
            path = pattern.format(self.__path, self.__time)
        elif faildir:
            if fromdir:
                path = os.path.relpath(self.__path, fromdir)
            path = os.path.join(faildir, path)

        if outdir:
            path = os.path.join(outdir, path)
        if path == self.__path:
            return None
        i = 1
        bpath, ext = os.path.splitext(path)
        while self.__path_exists(path, outpaths):
            path = "%s-%s%s" % (bpath, i, ext)
            i += 1
        return path

    def __str__(self):
        if self.get_method() == self.METHOD_EXIF:
            return "%s: exif %s" % (self.get_path(), self.get_time())
        if self.get_method() == self.METHOD_MANUAL:
            return "%s: manual %s" % (self.get_path(), self.get_time())
        elif self.get_method() == self.METHOD_EXIF:
            return "%s: %s %s" % (
                self.get_path(), self.get_pattern(), self.get_time())
        elif self.get_time():
            return "%s: %s" % (self.get_path(), self.get_time())
        else:
            return "%s: failed" % (self.get_path())


class Organizer:
    EXTENSIONS = ('.jpg', '.jpeg', '.png', '.avi', '.mov', '.3gp', '.mpg', '.mpeg')

    def __init__(self):
        self.__opaths = None
        self.__mfiles = None
        self.__dirtimes = None
        self.__mime = magic.Magic(mime=True)

    def __log(self, msg, *args):
        print(msg % args)

    def __load_file(self, path, verbose=False, main=True):
        if path in self.__mfiles:
            mfile = self.__mfiles[path]
        else:
            mfile = MediaFile(path)
            self.__mfiles[path] = mfile
        if main and not mfile.get_time():
            dirtime = self.__load_dir(os.path.dirname(path), verbose)
            mfile.set_time(dirtime)
        if main and verbose:
            self.__log(str(mfile))
        return mfile

    def __load_dir(self, path, verbose=False):
        if path in self.__dirtimes:
            return self.__dirtimes[path]
        total = 0
        count = 0
        for fpath in os.listdir(path):
            fpath = os.path.join(path, fpath)
            if not os.path.isfile(fpath):
                continue
            mfile = self.__load_file(fpath, verbose, False)
            if mfile and mfile.get_time():
                total += mfile.get_time().timestamp()
                count += 1
        if count == 0:
            avg = None
        else:
            avg = datetime.fromtimestamp(total / count)
        self.__dirtimes[path] = avg
        return avg

    def __process_file(
        self, path, outpattern, fromdir,
        inpatterns=None, outdir=None, faildir=None,
        dry=False, verbose=False, move=False
    ):
        if outpattern.match(path, outdir):
            self.__log("skipping output %s...", path)
            return None

        mfile = self.__load_file(path, verbose)
        if not mfile.get_time():
            self.__log(str(mfile))
        opath = mfile.get_outpath(
            pattern=outpattern,
            fromdir=fromdir,
            outdir=outdir,
            faildir=faildir,
            outpaths=self.__opaths
        )
        if not opath:
            if verbose:
                self.__log("skipping operation %s...", path)
            return None
        if dry:
            self.__opaths.append(opath)
        else:
            mfile.save(opath, move)
        return opath

    def __is_valid_type(self, path, exts):
        _, ext = os.path.splitext(path)
        if ext:
            ext = ext.lower()
        if exts and ext in exts:
            return True
        if ext in self.EXTENSIONS:
            return True
        mime = self.__mime.from_file(path)
        if mime.startswith("image/"):
            return True
        if mime.startswith("video/"):
            return True

    def run(self, args):
        self.__opaths = []
        self.__now = datetime.now()
        self.__mfiles = {}
        self.__dirtimes = {}
        inpatterns = []
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
                self.__log("processing %s...", fromdir)
            else:
                self.__log("processing %s to %s...", fromdir, outdir)
            faildir = os.path.join(outdir, args.faildir)
            for froot, _, fpaths in os.walk(fromdir):
                for fpath in fpaths:
                    fpath = os.path.join(froot, fpath)
                    if not self.__is_valid_type(fpath, args.extension):
                        self.__log("skipping type %s...", fpath)
                        continue
                    self.__process_file(
                        path=fpath,
                        inpatterns=inpatterns,
                        outpattern=outpattern,
                        fromdir=fromdir,
                        outdir=outdir,
                        faildir=faildir,
                        dry=args.dry,
                        verbose=args.verbose,
                        move=move)


def main():
    parser = argparse.ArgumentParser(
        description='organize your media collection')
    parser.add_argument(
        'path', action='append', help='directory with files', default=[])
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
    parser.add_argument(
        '--ext,--extension', action='append', dest="extension",
        help='additional extension to organize')
    args = parser.parse_args()
    org = Organizer()
    org.run(args)


if __name__ == "__main__":
    main()
