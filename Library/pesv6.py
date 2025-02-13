from enum import Enum
from binary_file import BinaryFileReader, BinaryFileWriter
from pec import PEC_File_Reader, PEC_File_Writer, PEC

class HOOP(Enum):
    SIZE_100x100 = 0
    SIZE_180x130 = 1 
    SIZE_272x272 = 2
    SIZE_272x408 = 3



class PES_File_Reader(PEC_File_Reader):

    def __init__(self, path):
        super(__class__, self).__init__(path)

    def get_tagged_string(self):
        assert self.get_uint24() == 0xFFFEFF
        length = self.get_uint8()
        return(''.join(chr(self.get_uint16()) for _ in range(length)))  # unicode?


class PES_File_Writer(PEC_File_Writer):

    def __init__(self, path):
        super(__class__, self).__init__(path)

    def put_tagged_string(self, string):
        self.put_uint24(0xFFFEFF)
        self.put_uint8(len(string))
        for chr in string:
            self.put_uint16(ord(chr))


class Thread:

    def __init__(self, /,
                 color_type     = 0,
                 color_rgb      = (0, 0, 0),
                 catalog_number = '',
                 chart_index    = '',
                 thread_brand   = '',
                 chart_length   = ''):
        self.color_type     = color_type
        self.rgbx           = bytes(color_rgb + (0,))
        self.thread_brand   = thread_brand
        self.catalog_number = catalog_number
        self.chart_index    = chart_index
        self.chart_length   = chart_length

    def __repr__(self):
        name = __class__.__name__
        return '{:s}({:s})'.format(name, (',\n'+(' '*(len(name)+1))).join((
            "color_type     = {:d}"  .format(self.color_type),
            "color_rgb      = {}"    .format(tuple(self.rgbx)[:3]),
            "thread_brand   = '{:s}'".format(self.thread_brand),
            "catalog_number = '{:s}'".format(self.catalog_number),
            "chart_index    = '{:s}'".format(self.chart_index),
            "chart_length   = '{:s}'".format(self.chart_length) )))

    def __str__(self):
        return '{:s} {:s} {}'.format(
            self.thread_brand,
            self.catalog_number,
            tuple(self.rgbx)[:3])

    def __eq__(self, other):
        return isinstance(other, type(self)) and all((
            self.color_type     == other.color_type,
            self.rgbx           == other.rgbx,
            self.thread_brand   == other.thread_brand,
            self.catalog_number == other.catalog_number,
            self.chart_index    == other.chart_index,
            self.chart_length   == other.chart_length))

    def get(self, file):
        self.catalog_number = file.get_tagged_string()
        self.rgbx           = file.get_data(4)
        self.color_type     = file.get_uint32()
        self.chart_index    = file.get_tagged_string()
        self.thread_brand   = file.get_tagged_string()
        self.chart_length   = file.get_tagged_string() # chart name?
        return self

    def put(self, file):
        file.put_tagged_string(self.catalog_number)
        file.put_data(self.rgbx)
        file.put_uint32(self.color_type)
        file.put_tagged_string(self.chart_index)
        file.put_tagged_string(self.thread_brand)
        file.put_tagged_string(self.chart_length) # chart name?



class PES_Object:

    def __init__(self):
        pass

    def get(self, file):
        self.extents1 = file.get_vector_int16(4)
        self.extents2 = file.get_vector_int16(4)
        self.transform_matrix = file.get_vector_float32(6)
        self.unknown1 = file.get_data(2)
        self.x_translation = file.get_int16()
        self.y_translation = file.get_int16()
        self.width = file.get_int16()
        self.height = file.get_int16()
        self.unknown2 = file.get_data(8)
        self.n_blocks = file.get_uint16()
        assert file.get_uint32() == 0x0000FFFF
        self.__class__ = eval(file.get_utf8(length_size=2)) # make a young girl squeal
        return self.get(file)


    def put(self, file):
        file.put_vector_int16(self.extents1)
        file.put_vector_int16(self.extents2)
        file.put_vector_float32(self.transform_matrix)
        file.put_data(self.unknown1)
        file.put_int16(self.x_translation)
        file.put_int16(self.y_translation)
        file.put_int16(self.width)
        file.put_int16(self.height)
        file.put_data(self.unknown2)
        file.put_uint16(self.n_blocks)
        file.put_uint32(0x0000FFFF)
        file.put_utf8(self.__class__.__name__, length_size=2)


class CSewSeg(PES_Object):

    def __init__(self, header):
        super(__class__, self).__init__(header)
        
    def get_stitch_list(self, file):
        self.blocks = []
        for i in range(self.n_blocks):
            stitch_type = file.get_uint16()
            thread_index = file.get_uint16()
            n_coordinates = file.get_uint16()
            coordinates = [file.get_vector_int16(2) for _ in range(n_coordinates)]
            self.blocks.append((stitch_type, thread_index, coordinates))
            if i < self.n_blocks-1:
                assert file.get_uint16() == 0x8003 # continuation code

    def put_stitch_list(self, file):
        for j, block in enumerate(self.blocks):
            file.put_uint16(block[0]) # stitch_type
            file.put_uint16(block[1]) # thread_index
            coordinates = block[2]
            file.put_uint16(len(coordinates))
            for coordinate in coordinates:
                file.put_vector_int16(coordinate)
            if j < len(self.blocks)-1:
                file.put_uint16(0x8003) # continuation code

    def get_color_list(self, file):
        n_colors = file.get_uint16()
        self.colors = []
        for i in range(n_colors):
            block_index = file.get_uint16()
            thread_index = file.get_uint16()
            self.colors.append((block_index, thread_index))

    def put_color_list(self, file):
        file.put_uint16(len(self.colors))
        for color in self.colors:
            file.put_uint16(color[0]) # block_index
            file.put_uint16(color[1]) # thread_index

    def get_excess(self, file):
        assert file.get_uint32() == 0 and file.get_uint32() == 0
        for i in range(len(self.colors)):
            assert file.get_uint32() == 0
            assert file.get_uint32() == i

    def put_excess(self, file):
        file.put_uint32(0)
        file.put_uint32(0)
        for i in range(len(self.colors)):
            file.put_uint32(0)
            file.put_uint32(i)

    def get(self, file):
        self.get_stitch_list(file)
        self.get_color_list(file)
        self.get_excess(file)
        return self

    def put(self, file):
        super().put(file)
        self.put_stitch_list(file)
        self.put_color_list(file)
        self.put_excess(file)



class PESv6:

    def __init__(self):
        pass

    def get_version(self, file):
        assert file.get_text(8) == '#PES0060'

    def put_version(self, file):
        file.put_text('#PES0060')

    def get_header_prologue(self, file):
        self.pec_offset                  = file.get_uint32()
        self.n_pecs                      = file.get_uint16()
        self.hoop_size                   = file.get_text(2)
        self.name                        = file.get_utf8()
        self.category                    = file.get_utf8()
        self.author                      = file.get_utf8()
        self.keywords                    = file.get_utf8()
        self.comments                    = file.get_utf8()
        self.optimize_hoop_change        = file.get_bool16()
        self.custom_design_page          = file.get_bool16()
        self.hoop_width                  = file.get_uint16()
        self.hoop_height                 = file.get_uint16()
        self.design_page_area            = file.get_uint16()
        self.design_width                = file.get_uint16()
        self.design_height               = file.get_uint16()
        self.section_width               = file.get_uint16()
        self.section_height              = file.get_uint16()
        self.unknown1                    = file.get_uint16()
        self.background_color            = file.get_uint16()
        self.foreground_color            = file.get_uint16()
        self.show_grid                   = file.get_bool16()
        self.with_axes                   = file.get_bool16()
        self.snap_to_grid                = file.get_bool16()
        self.grid_interval               = file.get_uint16()
        self.unknown2                    = file.get_data(2)
        self.optimize_entry_exit_point   = file.get_bool16()
        self.from_image                  = file.get_utf8()
        self.transform                   = file.get_vector_float32(6)

    def put_header_prologue(self, file):
        file.put_uint32              (self.pec_offset)
        file.put_uint16              (self.n_pecs)
        file.put_text                (self.hoop_size)
        file.put_utf8                (self.name)
        file.put_utf8                (self.category)
        file.put_utf8                (self.author)
        file.put_utf8                (self.keywords)
        file.put_utf8                (self.comments)
        file.put_bool16              (self.optimize_hoop_change)
        file.put_bool16              (self.custom_design_page)
        file.put_uint16              (self.hoop_width)
        file.put_uint16              (self.hoop_height)
        file.put_uint16              (self.design_page_area)
        file.put_uint16              (self.design_width)
        file.put_uint16              (self.design_height)
        file.put_uint16              (self.section_width)
        file.put_uint16              (self.section_height)
        file.put_uint16              (self.unknown1)
        file.put_uint16              (self.background_color)
        file.put_uint16              (self.foreground_color)
        file.put_bool16              (self.show_grid)
        file.put_bool16              (self.with_axes)
        file.put_bool16              (self.snap_to_grid)
        file.put_uint16              (self.grid_interval)
        file.put_data                (self.unknown2)
        file.put_bool16              (self.optimize_entry_exit_point)
        file.put_utf8                (self.from_image)
        file.put_vector_float32      ([1.0, 0.0, 0.0, 1.0, 0.0, 0.0])

    def get_header_epilogue(self, file):
        n_objects = file.get_uint16()
        assert file.get_uint32() == 0x0000FFFF  # end of header marker
        return n_objects

    def put_header_epilogue(self, file):
        file.put_uint16(len(self.objects))
        file.put_uint32(0x0000FFFF)             # end of header marker

    def get_header(self, file):
        self.get_header_prologue(file)
        assert (n_fill_patterns    := file.get_uint16()) == 0
        assert (n_motif_patterns   := file.get_uint16()) == 0
        assert (n_feather_patterns := file.get_uint16()) == 0
        n_threads = file.get_uint16()
        self.threads = [Thread().get(file) for i in range(n_threads)]
        return self.get_header_epilogue(file)

    def put_header(self, file):
        self.put_header_prologue(file)
        file.put_uint16 (0) # n_fill_patterns
        file.put_uint16 (0) # n_motif_patterns
        file.put_uint16 (0) # n_feather_patterns
        file.put_uint16 (len(self.threads))
        for thread in self.threads:
            thread.put(file)
        self.put_header_epilogue(file)

    def get_cembone_tag(self, file):
        assert file.get_utf8(length_size=2) == 'CEmbOne'

    def put_cembone_tag(self, file):
        file.put_utf8('CEmbOne', length_size=2)

    def get_object(self, file):
        return PES_Object().get(file)

    def put_object(self, file, obj):
        obj.put(file)



    def get_section_data(self, file):
        self.n_section_thumbnails = file.get_uint16()
        if self.n_section_thumbnails == 0:
            return
        pass  # TODO: complete this method
        
    def put_section_data(self, file):
        file.put_uint16(self.n_section_thumbnails)
        pass  # TODO: complete this method



    def get(self, path):

        with PES_File_Reader(path) as file:

            self.get_version(file)
            n_objects = self.get_header(file)
            self.get_cembone_tag(file)
            self.objects = [self.get_object(file) for _ in range(n_objects)]

            self.pecs = [PEC().get(file) for _ in range(self.n_pecs)]
            for pec in self.pecs:
                pec.get_redundant_indexes(file)
            for pec in self.pecs:
                pec.get_thread_bitmaps(file)
            for pec in self.pecs:
                pec.get_thread_colors(file)
            
            self.get_section_data(file)

            for pec in self.pecs:
                pec.get_thread_specifications(file)
            

        return self


    def put(self, path):

        with PES_File_Writer(path) as file:

            self.put_version(file)
            self.put_header(file)
            self.put_cembone_tag(file)
            for obj in self.objects:
                self.put_object(file, obj)

            for pec in self.pecs:
                pec.put(file)
            for pec in self.pecs:
                pec.put_redundant_indexes(file)
            for pec in self.pecs:
                pec.put_thread_bitmaps(file)
            for pec in self.pecs:
                pec.put_thread_colors(file)

            self.put_section_data(file)

            for pec in self.pecs:
                pec.put_thread_specifications(file)

if __name__ == '__main__':
    p = PESv6().get('../Tests/holly_unrotated.pes')
    ## p = PESv6().get('../Tests/rectangle.pes')
    ## p.put('../Tests/rectum.pes')
