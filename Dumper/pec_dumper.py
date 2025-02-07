from enum        import Enum
from binary_file import sign_extend

HIDE_THREAD_INDEXES = False

class Cmd(Enum):
    STITCH = 0
    JUMP   = 1
    TRIM   = 2
    COLOR  = 7
    STOP   = 15

class PecDumperMixin:

    def get_coord(self):
        b1 = self.get_uint8()
        if b1 == 0xFF:          # end of coordinates
            return None
        if b1&0x80 == 0:        # single-byte coordinate
            return 0, sign_extend(b1, 7), bytes((b1,))
        b2 = self.get_uint8()
        w = (b1<<8) | b2
        return (w>>12)&0x7, sign_extend(w&0xFFF, 12), bytes((b1,b2))


    def dump_scanline(self, id, stride, fmt='{:s}'):
        self.print_addr()
        scanline = self.get_uint(stride)
        result = (''.join([' *'[(scanline>>(i))&1] for i in range(stride*8)]))
        ## result = (' '.join([' *'[(scanline>>(i))&1] for i in range(stride*8)]))
        self.print_result(id, result, fmt)


    def dump_instruction(self):
        self.print_addr()
        coord1 = self.get_coord()
        if coord1 is None:
            cmd = Cmd.STOP
            args = []
            raw_data = bytes([0xff])
        else:
            cmd1, value1, raw_data1 = coord1
            if coord1[0] == 7 and coord1[1]&0xFFF == 0xEB0:
                index = self.get_data(1) # alternates between 1 and 2
                cmd = Cmd(cmd1)
                args = [index[0]]
                raw_data = raw_data1+index
            else:
                cmd2, value2, raw_data2 = self.get_coord()
                assert cmd2 == cmd1
                cmd = Cmd(cmd1)
                args = [value1, value2]
                raw_data = raw_data1 + raw_data2
        datastr = ' '.join('{:02X}'.format(b) for b in raw_data)
        argsstr = ','.join('{:d}'.format(arg) for arg in args)
        self.print_result(None, ('{:12s} {:6s} {}'.format(datastr, cmd.name, argsstr)))
        return cmd, args

    
def dump_pec_prologue(f):

    """Dumps the PEC portion of a file. Should be called with the file positioned at
    the beginning of the label (i.e. just after the magic number and version in a PEC
    file, or just after the PES data in a PES file.) Leaves the file positioned at
    end of file."""

    with f.section('PEC Header', tab=20):
        assert f.dump_text('label_marker', 3) == 'LA:'
        label = f.dump_text('label', 16)
        f.dump_uint8('carriage_return')
        unknown1 = f.dump_data('unknown1', 11)
        unknown2 = f.dump_data('unknown2', 3)
        thumb_w = f.dump_uint8('thumb_w')   # in bytes, typically 6
        thumb_h = f.dump_uint8('thumb_h')   # in scanlines, typically 38 
        f.dump_data('unknown3a', 1)
        f.dump_data('unknown3b', 1)
        f.dump_vector_int8('unknown3c', 2)
        f.dump_data('unknown3d', 1)
        f.dump_data('unknown3e', 4)
        f.dump_data('unknown3f', 1)
        f.dump_data('unknown3g', 2)

    with f.section('Thread Indexes', tab=20, hide=HIDE_THREAD_INDEXES):
        n_changes = f.dump_uint8('n_changes')
        n_layers = n_changes+1
        indexes = f.dump_data('thread_indexes', 463)
        end_of_index_list = f.tell()

    with f.section('Pattern', tab=20):

        ## Header
        f.dump_data('unknown', 2)
        thumbnail_offset = f.dump_uint24('thumbnail_offset', fmt='0x{:06X}')
        f.dump_data('unknown', 3)
        width =  f.dump_uint16('width')
        height = f.dump_uint16('height')
        f.dump_uint16('unknown_width')
        f.dump_uint16('unknown_height')
        f.print()

        ## Stitches
        layers = []
        for i in range(n_layers):
            layers.append(layer := [])
            with f.subsection('Layer {:d} Stitches'.format(len(layers)),
                              hide=not f.show_stitches):
                while True:
                    cmd, args = f.dump_instruction()
                    if cmd == Cmd.COLOR or cmd == Cmd.STOP:
                        break
                    layer.append((cmd, args))
 
    ## Thumbnail Bitmaps
    ## There is one main thumbnail plus one for each color.
    assert f.tell() == end_of_index_list + thumbnail_offset
    with f.section('Thumbnail Bitmaps', tab=0, hide=not f.show_bitmaps):
        f.print()
        for color in range(n_layers+1):        
            with f.subsection('Thumbnail {:d}'.format(color)):
                for i in range(thumb_h):
                    f.dump_scanline(None, thumb_w)

    return width, height, indexes[:n_layers], layers


def dump_pec_redundant_thread_indexes(f):
    ## One per section, after all prologues
    ## This is redundant, as the indexes were already read above. Here, we only have
    ## room for 127 indexes versus 463 above.
    with f.section('Redundant Thread Indexes'):
        n_changes_2 = f.dump_uint8('n_changes_2')
        f.dump_data('thread_indexes', 127)


def dump_pec_thread_bitmaps(f, indexes):
    ## One per section, after all prologues
    with f.section('Thread Bitmaps', tab=0, hide=not f.show_bitmaps):
        f.print()
        w, h = 6, 24
        for thread in range(len(indexes)):
            with f.subsection('Thread {:d}'.format(thread+1)):
                for i in range(h):
                    f.dump_scanline(None, w)


def dump_pec_thread_colors(f, n):
    ## One per section, after all prologues
    with f.section('Colors'):
        rgbs = []
        for i in range(n):
            r,g,b = f.dump_data('thread_{:d}_color'.format(i+1), 3)
            rgbs.append((r,g,b))
    return rgbs


def dump_pec_epilogue(f, n):
    ## Only one at very end of file
    with f.section('Threads'):
        f.print()
        threads = []
        for i in range(n):
            with f.subsection('Thread {:d}'.format(i+1)):
                thread_type = f.dump_uint8('thread_{:d}_type'.format(i+1))
                thread_code = f.dump_uint16('thread_{:d}_code'.format(i+1))

    return threads



class Pec:

    def __init__(self, width, height, indexes, layers):
        self.width = width
        self.height = height
        self.indexes = indexes
        self.layers = layers
        self.rgbs = []

    def remap(self):

        unique_rgbs = []
        for rgb in self.rgbs:
            if rgb not in unique_rgbs:
                unique_rgbs.append(rgb)
        self.rgbs = unique_rgbs

        mapping = {}
        index = 0
        for old_index in self.indexes:
            if old_index not in mapping:
                mapping[old_index] = index
                index += 1
        self.indexes = [mapping[color] for color in self.indexes]


    def render(self):
        from svg import SVG
        scale = 137.68/25.4/10 # actual size on NEC PA322UHD monitor
        with SVG((self.width*scale, self.height*scale)) as svg:
            x, y = 0,0
            for index, layer in zip(self.indexes, self.layers):
                with svg.path(stroke_width=2,
                              stroke_color=('#{:02X}{:02X}{:02X}'
                                            .format(*self.rgbs[index]))) as path:
                    path.move((x, y))
                    for cmd, (dx, dy) in layer:
                        match Cmd(cmd):
                            case Cmd.STITCH:
                                path.line_rel((dx*scale, dy*scale))
                            case Cmd.JUMP:
                                path.move_rel((dx*scale, dy*scale))
                            case Cmd.TRIM:
                                path.move_rel((dx*scale, dy*scale))
                        x += dx*scale
                        y += dy*scale


def dump_pec_extra_data(f, n):

    with f.section('More Thumbnails', tab=20, hide=not f.show_bitmaps):
        SCAN_W = 11
        for i in range(n):
            with f.subsection('Partial Thumbnail {:d}'.format(i+1)):
                for j in range(69):
                   f.dump_scanline(None, SCAN_W)

    dump_pec_thread_colors(f, n)

    with f.section('Full Thumbnail', hide=not f.show_bitmaps):
        for j in range(69):
           f.dump_scanline(None, SCAN_W)

    with f.section('Physical Dimensions'):
        f.dump_int16('Width')
        f.dump_int16('Height')

    with f.section('Huge Thumbnail', tab=0, hide=not f.show_bitmaps):
        SCAN_W = 30
        for j in range(456):
           f.dump_scanline(None, SCAN_W)


def dump_pec_data(f, n_pecs):
    
    pecs = [Pec(*dump_pec_prologue(f)) for i in range(n_pecs)]

    for pec in pecs:
        dump_pec_redundant_thread_indexes(f)
    for pec in pecs:
        dump_pec_thread_bitmaps(f, pec.indexes)
    for pec in pecs:
        pec.rgbs = dump_pec_thread_colors(f, len(pec.indexes))
        pec.remap()

    n = f.dump_uint16('Number of Partial Thumbnails')
    if n > 0:
        dump_pec_extra_data(f, n)

    for pec in pecs:
        threads = dump_pec_epilogue(f, len(pec.indexes))

    return pecs



if __name__ == '__main__':
    import pes_dump
    pes_dump.main()
