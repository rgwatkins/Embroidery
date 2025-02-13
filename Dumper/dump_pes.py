###---------------------------------------------------------------------------------------------
### pes_dump
###
### Dumps a .pes embroidery file.
###---------------------------------------------------------------------------------------------

from sys          import argv, stdout
from os           import environ
from os.path      import basename, splitext
from contextlib   import nullcontext
from argparse     import ArgumentParser, RawDescriptionHelpFormatter
from binary_file  import BinaryFileReader
from binary_dump  import BinaryFileDumper
from pesv6_dumper import *
from pec_dumper   import *

SHOW_SVGS      = True
SHOW_ADDRESSES = True
SHOW_BITMAPS   = False
SHOW_STITCHES  = True

PES_DIR = 'U:/Bob/Projects/Embroidery/Tests/'
PES_PATH = 'circle.pes'
PES_PATH = 'rectangle.pes'
PES_PATH = 'holly_200x200_4hoop_moved_y.pes'
PES_PATH = 'holly_200x200_4hoop_moved_x.pes'
PES_PATH = 'holly_200x200_4hoop.pes'
PES_PATH = 'holly_rotated.pes'
PES_PATH = 'holly_unrotated.pes'
PES_PATH = 'combo_resaved.pes'
PES_PATH = 'combo.pes'

description = "Dumps a .pes embroidery file."

class EmbroideryFileDumper(BinaryFileDumper, PecDumperMixin, PesDumperMixin):
    def __init__(self, path, /, ofile=stdout, tab=0,
                 address_length=None, show_stitches=False, show_bitmaps=False):
        super(__class__, self).__init__(path, ofile=ofile, tab=tab,
                                        address_length=address_length)
        self.show_stitches = show_stitches
        self.show_bitmaps = show_bitmaps
    

def main():

    if (script := environ.get('RUNPYTHON')):
        command = basename(script)
    else:
        command = 'python3 {}'.format(argv[0])

    if 'INSIDE_EMACS' in environ:
        import sys
        sys.argv = ['python3', PES_DIR+PES_PATH]
        if SHOW_ADDRESSES:
            sys.argv.append('-a')
        if SHOW_BITMAPS:
            sys.argv.append('-b')
        if SHOW_STITCHES:
            sys.argv.append('-s')
        
    parser = ArgumentParser(prog=command, description=description,
                            allow_abbrev=False,
                            formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument('path', metavar='path', type=str,
                        help="pathname of the file to dump")

    parser.add_argument('-a', '--show-addresses',
                        dest='show_addresses',
                        action='store_true',
                        help="show address at beginning of each line")

    parser.add_argument('-s', '--show-stitches',
                        dest='show_stitches',
                        action='store_true',
                        help="show stitches")

    parser.add_argument('-b', '--show-bitmaps',
                        dest='show_bitmaps',
                        action='store_true',
                        help="show bitmaps")

    parser.add_argument('-t', '--text-file',
                        dest='output_text_file',
                        action='store_true',
                        help="output to text file instead of stdout")

    parser.set_defaults(show_addresses=False, output_text=False,
                        show_bitmaps=False, show_stitches=False)

    args = parser.parse_args()

    ## Determine input an output paths. If the input path had no extension, add
    ## a .pes extension to it. Give the output file a .txt extension.
    base, ext = splitext(args.path)
    if ext == '':
        ext = '.pes'
    ipath = base+ext
    opath = base+'.txt'

    with (open(opath, 'w', newline='\n') if args.output_text_file else
          nullcontext(stdout)) as ofile:
        with EmbroideryFileDumper(ipath, ofile=ofile, tab=30,
                                  address_length=(0, None)[args.show_addresses],
                                  show_stitches=args.show_stitches,
                                  show_bitmaps=args.show_bitmaps) as f:

            if (magic := f.get_text(4)) != '#PES':
                exit('Unrecognized file type (magic="{:s}")'.format(str(magic, encoding='utf8')))

            if (version := int(f.get_text(4))) == 1:
                version = 10
            f.print('PES Version: {:d}.{:d}\n'.format(version//10, version%10))
            if not f.version_supported(version):
                exit('version is not supported')

            n_pecs = dump_pes_data(f)
            pecs = dump_pec_data(f, n_pecs)

            if 'INSIDE_EMACS' in environ and SHOW_SVGS:
                for pec in pecs:
                    pec.render()
                    print()
            
            if (excess := f.size-f.tell()) > 0:
                with f.section('Excess'):
                    f.dump_data(None, excess)


if __name__ == '__main__':
    main()
