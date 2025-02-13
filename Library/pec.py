from enum import IntEnum
from turds import twos_complement, sign_extend
from binary_file import BinaryFileReader, BinaryFileWriter

class Cmd(IntEnum):
    STITCH = 0
    JUMP   = 1
    TRIM   = 2
    COLOR  = 7
    STOP   = 15


class PEC_File_Reader(BinaryFileReader):

    def __init__(self, path):
        super(__class__, self).__init__(path)

    def get_coord(self):
        b1 = self.get_uint8()
        if b1 == 0xFF:          # end of coordinates
            return None
        if b1&0x80 == 0:        # single-byte coordinate
            return 0, sign_extend(b1, 7)
        b2 = self.get_uint8()
        w = (b1<<8) | b2
        return (w>>12)&0x7, sign_extend(w&0xFFF, 12)

    def get_instruction(self):
        coord1 = self.get_coord()
        if coord1 is None:
            cmd = Cmd.STOP
            args = []
        else:
            cmd1, value1 = coord1
            if coord1[0] == 7 and coord1[1]&0xFFF == 0xEB0:
                index = self.get_data(1) # alternates between 1 and 2
                cmd = Cmd(cmd1)
                args = [index[0]]
            else:
                cmd2, value2 = self.get_coord()
                assert cmd2 == cmd1
                cmd = Cmd(cmd1)
                args = [value1, value2]
        return cmd, args


class PEC_File_Writer(BinaryFileWriter):

    def __init__(self, path):
        super(__class__, self).__init__(path)

    def put_coord(self, cmd, n):
        if -64 <= n < 64 and cmd == 0:
            self.put_uint8(twos_complement(n, 7))
        elif -1024 <= n < 1024:
            word = 0x8000 | (cmd<<12) | twos_complement(n, 12)
            self.put_uint8(word>>8)   # output in big-endian byte order
            self.put_uint8(word&0xFF)

    def put_instruction(self, cmd, args):
        if cmd == Cmd.STOP:
            self.put_uint8(0xFF)
        elif cmd == Cmd.COLOR:
            self.put_uint8(0xFE)
            self.put_uint8(0xB0)
            self.put_uint8(args[0])
        else:
            self.put_coord(cmd, args[0])
            self.put_coord(cmd, args[1])



class PEC:

    def __init__(self):
        pass

    def get(self, file):

        ## Header
        assert file.get_text(3) == 'LA:'
        self.label          = file.get_text(16)
        assert file.get_uint8() == ord('\r')
        self.unknown1       = file.get_data(11)
        self.unknown2       = file.get_data(3)
        self.thumb_w        = file.get_uint8()   # in bytes, typically 6
        self.thumb_h        = file.get_uint8()   # in scanlines, typically 38 
        self.unknown3a      = file.get_data(1)
        self.unknown3b      = file.get_data(1)
        self.hoop_position  = file.get_vector_int8(2)
        self.unknown4a      = file.get_data(1)
        self.unknown4b      = file.get_data(4)
        self.unknown4c      = file.get_data(1)
        self.unknown4d      = file.get_data(2)

        ## Color Chart Indexes
        self.n_changes      = file.get_uint8()
        self.n_layers       = self.n_changes+1
        self.indexes        = file.get_data(463)

        ## Artwork Dimensions
        self.unknown5            = file.get_data(2)
        self.thumbnail_offset    = file.get_uint24()
        self.unknown6            = file.get_data(3)
        self.width               = file.get_uint16()
        self.height              = file.get_uint16()
        self.unknown_width       = file.get_uint16()
        self.unknown_height      = file.get_uint16()

        ## Stitches
        self.layers = []
        for i in range(self.n_layers):
            self.layers.append(layer := [])
            while True:
                cmd, args = file.get_instruction()
                layer.append((cmd, args))
                if cmd == Cmd.COLOR or cmd == Cmd.STOP:
                    break

        ## Thumbnails
        self.thumbnails = [[file.get_uint(self.thumb_w)
                            for j in range(self.thumb_h)]
                           for i in range(self.n_layers+1)]        

        return self


    def put(self, file):

        ## Header
        file.put_text          ('LA:')
        file.put_text          (self.label)
        file.put_uint8         (ord('\r'))
        file.put_data          (self.unknown1)
        file.put_data          (self.unknown2)
        file.put_uint8         (self.thumb_w)
        file.put_uint8         (self.thumb_h)
        file.put_data          (self.unknown3a)
        file.put_data          (self.unknown3b)
        file.put_vector_int8   (self.hoop_position)
        file.put_data          (self.unknown4a)
        file.put_data          (self.unknown4b)
        file.put_data          (self.unknown4c)
        file.put_data          (self.unknown4d)
        
        ## Color Chart Indexes
        file.put_uint8         (self.n_changes)
        file.put_data          (self.indexes)

        ## Artwork Dimensions
        file.put_data          (self.unknown5)
        file.put_uint24        (self.thumbnail_offset)
        file.put_data          (self.unknown6)
        file.put_uint16        (self.width)
        file.put_uint16        (self.height)
        file.put_uint16        (self.unknown_width)
        file.put_uint16        (self.unknown_height)

        ## Stitches
        for layer in self.layers:
            for cmd, args in layer:
                file.put_instruction(cmd, args)

        ## Thumbnails
        for thumbnail in self.thumbnails:
            for scanline in thumbnail:
                file.put_uint(self.thumb_w, scanline)


    def get_redundant_indexes(self, file):
        assert file.get_uint8() == self.n_changes
        self.redundant_indexes = file.get_data(127)

    def put_redundant_indexes(self, file):
        file.put_uint8 (self.n_changes)
        file.put_data  (self.redundant_indexes)


    def get_thread_bitmaps(self, file):
        w, h = 6, 24
        self.thread_bitmaps = [[file.get_uint(w)
                                for j in range(self.n_layers)]
                               for i in range(h)]

    def put_thread_bitmaps(self, file):
        w, h = 6, 24
        for bitmap in self.thread_bitmaps:
            for scanline in bitmap:
                file.put_uint(w, scanline)

        
    def get_thread_colors(self, file):
        self.rgbs = []
        for i in range(self.n_layers):
            self.rgbs.append(tuple(file.get_data(3)))

    def put_thread_colors(self, file):
        for rgb in self.rgbs:
            file.put_data(bytes(rgb))


    def get_thread_specifications(self, file):
        self.threads = [(file.get_uint8(), file.get_uint16()) # type, code
                        for i in range(self.n_layers)]

    def put_thread_specifications(self, file):
        for thread in self.threads:
            file.put_uint8(thread[0])
            file.put_uint16(thread[1])
