import argparse
import magic
import os
import exifread
from datetime import datetime
import shutil


TIME_TAGS = ('DateTimeOriginal', )
FILE_PATTERNS = (
    'WhatsApp Image %Y-%m-%d at %h.%M.%S %p',
    'IMG_%Y%m%d_%H%M%S.jpg'
)


def get_output_path(fpath, args):
    with open(fpath, 'rb') as fh:
        tags = exifread.process_file(fh, details=False)
    time = None
    for key, val in tags.items():
        for ttag in TIME_TAGS:
            if key.endswith(ttag):
                time = val
                break
        if time:
            break
    if time:
        try:
            time = datetime.strptime(str(time), '%Y:%m:%d %H:%M:%S')
        except Exception:
            time = None
    if not time:
        print("no time for: %s" % (fpath, ))
        time = datetime(1, 1, 1)

    return args.pattern.format(
        time=time,
        filename=os.path.basename(fpath),
        ext=os.path.splitext(fpath)[1].lower()
    )


def main():
    parser = argparse.ArgumentParser(description='organize your photo collection')
    parser.add_argument('path', nargs='+', help='directory with photos', default='.')
    parser.add_argument('-o,--outdir', dest='outdir', help='output directory')
    parser.add_argument('-p,--pattern', dest='pattern', help='output file pattern', default="{time:%Y}/{time:%Y-%m-%d}/{time:%Y-%m-%d_%H-%M}{ext}")
    args = parser.parse_args()
    if not args.outdir:
        args.outdir = args.path[0]

    mime = magic.Magic(mime=True)
    for fdir in args.path:
        print("processing %s to %s..." % (fdir, args.outdir))
        for froot, _, fpaths in os.walk(fdir):
            for fpath in fpaths:
                fpath = os.path.join(froot, fpath)
                fmime = mime.from_file(fpath)
                if fmime.startswith("image/"):
                    opath = get_output_path(fpath, args)
                    opath = os.path.join(args.outdir, opath)
                    i = 1
                    bopath, ext = os.path.splitext(opath)
                    while os.path.isfile(opath):
                        opath = "%s-%s%s" % (bopath, i, ext)
                        i += 1
                    # print("copying %s to %s..." % (
                    #     os.path.relpath(fpath, froot),
                    #     os.path.relpath(opath, args.outdir)
                    # ))
                    odir = os.path.dirname(opath)
                    if odir:
                        os.makedirs(odir, exist_ok=True)
                    shutil.copyfile(fpath, opath)


if __name__ == "__main__":
    main()
